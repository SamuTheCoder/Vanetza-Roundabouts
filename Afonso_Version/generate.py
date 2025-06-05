#!/usr/bin/env python3
import json
import paho.mqtt.client as mqtt
import threading
from time import sleep
import gpxpy
from geopy.distance import geodesic
from math import atan2, degrees
import argparse
import sys

# ========== CONFIGURATION PER OBU ID ==========
# Add as many OBU IDs as you need here. The keys are the IDs you pass via --obu-id.
CONFIG = {
    "1": {
        "GPX_FILE": "Sim1.gpx",
        "ROUNDABOUT_FILE": "roundabout1.gpx",
        "MQTT_BROKER": "192.168.98.10"
    },
    "2": {
        "GPX_FILE": "Sim2.gpx",
        "ROUNDABOUT_FILE": "roundabout1.gpx",
        "MQTT_BROKER": "192.168.98.20"
    },
    # Example for OBU 3:
    "3": {
        "GPX_FILE": "Sim3.gpx",
        "ROUNDABOUT_FILE": "roundabout1.gpx",
        "MQTT_BROKER": "192.168.98.40"
    },
}
# ===============================================

# ---------- Argument Parsing ----------
parser = argparse.ArgumentParser(
    description="Generalized generate.py for multiple OBUs. "
                "Specify --obu-id to select GPX files and MQTT broker."
)
parser.add_argument(
    "--obu-id",
    required=True,
    choices=CONFIG.keys(),
    help="ID of the OBU (e.g. 1, 2, 3, ...). Determines which GPX files and broker to use."
)
args = parser.parse_args()
obu_id = args.obu_id

# Retrieve the three variables from CONFIG:
try:
    GPX_FILE = CONFIG[obu_id]["GPX_FILE"]
    ROUNDABOUT_FILE = CONFIG[obu_id]["ROUNDABOUT_FILE"]
    MQTT_BROKER = CONFIG[obu_id]["MQTT_BROKER"]
except KeyError:
    print(f"> Error: No configuration found for OBU ID '{obu_id}'")
    sys.exit(1)

MQTT_PORT = 1883
MQTT_TOPIC_IN = "vanetza/in/cam"
MQTT_TOPIC_OUT = "vanetza/out/cam"

SLEEP_INTERVAL = 1  # seconds between messages
ROUNDABOUT_MARGIN = 15  # meters around the roundabout
OBU_PROXIMITY_THRESHOLD = 35  # meters (tweak as needed)
# ===============================================

print(f"> Using configuration for OBU {obu_id}:")
print(f"    GPX_FILE       = {GPX_FILE}")
print(f"    ROUNDABOUT_FILE= {ROUNDABOUT_FILE}")
print(f"    MQTT_BROKER    = {MQTT_BROKER}")
print(f"    MQTT_PORT      = {MQTT_PORT}\n")


# ---------- Global Data ----------
trajectory = []
other_obu_position = None  # Last known position of other OBU
other_obu_position_lock = threading.Lock()


# ---------- GPX Loader ----------
def load_gpx_coordinates(gpx_path):
    coords = []
    try:
        with open(gpx_path, "r") as gpx_file:
            gpx = gpxpy.parse(gpx_file)
            # Extract track/segment points
            for track in gpx.tracks:
                for segment in track.segments:
                    for point in segment.points:
                        coords.append((point.latitude, point.longitude))
            # Also include waypoints (if any)
            for waypoint in gpx.waypoints:
                coords.append((waypoint.latitude, waypoint.longitude))
    except Exception as e:
        print(f"> Error loading GPX '{gpx_path}': {e}")
        sys.exit(1)

    if not coords:
        print(f"> Warning: No coordinates found in {gpx_path}")
    return coords


# ---------- Roundabout Geometry ----------
roundabout_coords = load_gpx_coordinates(ROUNDABOUT_FILE)

if len(roundabout_coords) < 2:
    print("> Roundabout GPX must have at least 2 points (center and edge)")
    sys.exit(1)

ROUNDABOUT_CENTER = roundabout_coords[0]
ROUNDABOUT_RADIUS = geodesic(ROUNDABOUT_CENTER, roundabout_coords[1]).meters

print(f"> Roundabout center: {ROUNDABOUT_CENTER}, radius: {ROUNDABOUT_RADIUS:.2f} m\n")


# ---------- Trajectory ----------
trajectory = load_gpx_coordinates(GPX_FILE)
print(f"> Loaded {len(trajectory)} total points from '{GPX_FILE}'\n")


# ---------- Distance & Bearing Helpers ----------
def is_inside_roundabout(pos):
    """Return True if pos is inside the roundabout radius."""
    if pos is None or pos[0] is None:
        return False
    return geodesic(pos, ROUNDABOUT_CENTER).meters <= ROUNDABOUT_RADIUS


def is_near_roundabout(pos, margin=ROUNDABOUT_MARGIN):
    """Return True if pos is within [radius, radius + margin]."""
    if pos is None or pos[0] is None:
        return False
    d = geodesic(pos, ROUNDABOUT_CENTER).meters
    return ROUNDABOUT_RADIUS < d < (ROUNDABOUT_RADIUS + margin)


def calculate_bearing(from_pos, to_pos):
    """
    Calculate bearing in degrees from from_pos to to_pos.
    """
    lat1, lon1 = map(float, from_pos)
    lat2, lon2 = map(float, to_pos)

    dLon = lon2 - lon1
    x = atan2(dLon, lat2 - lat1)
    brng = degrees(x)
    return (brng + 360) % 360


def get_heading(current_pos, next_pos):
    """
    Returns absolute heading (0–360°) from current to next position.
    """
    return calculate_bearing(current_pos, next_pos)


def is_threatening_position(my_pos, other_pos, my_heading):
    """
    Determine if other OBU inside the roundabout poses a threat:
    - other_pos must be inside the roundabout
    - within proximity threshold
    - bearing falls within rear-left cone (210°–350°) relative to my heading
    """
    if other_pos is None or not is_inside_roundabout(other_pos):
        return False

    distance = geodesic(my_pos, other_pos).meters
    if distance > OBU_PROXIMITY_THRESHOLD:
        return False

    bearing_to_other = calculate_bearing(my_pos, other_pos)
    relative_bearing = (bearing_to_other - my_heading + 360) % 360

    print(f"> Distance to other OBU: {distance:.2f} m")
    print(f"> Relative bearing to other OBU: {relative_bearing:.2f}°")

    return 210 <= relative_bearing <= 350


# ---------- MQTT Callbacks ----------
def on_connect(client, userdata, flags, rc, properties=None):
    print(f"> Connected to MQTT broker '{MQTT_BROKER}:{MQTT_PORT}' with result code {rc}")
    client.subscribe(MQTT_TOPIC_OUT)


def on_message(client, userdata, msg):
    global other_obu_position
    try:
        payload = msg.payload.decode("utf-8")
        obj = json.loads(payload)
        lat = obj.get("latitude")
        lon = obj.get("longitude")
        sender_obu_id = obj.get("obu_id")

        if sender_obu_id is not None and lat is not None and lon is not None and sender_obu_id != obu_id:
            with other_obu_position_lock:
                other_obu_position = (lat, lon)
            # Uncomment below to log received CAMs
            # print(f"> Received CAM from OBU {sender_obu_id}: lat={lat}, lon={lon}")
    except Exception as e:
        print(f"> Error parsing incoming CAM JSON: {e}")


# ---------- Main Sending Loop ----------
stop = False

def send_trajectory():
    global stop
    for idx, (lat, lon) in enumerate(trajectory):
        my_pos = (lat, lon)

        with other_obu_position_lock:
            other_pos = other_obu_position

        # Determine heading: if not at the last point, compute towards next
        if idx < len(trajectory) - 1:
            next_pos = trajectory[idx + 1]
            my_heading = get_heading(my_pos, next_pos)
        else:
            my_heading = 0

        # --- Decision logic: Should I yield? ---
        print(f"> OBU {obu_id} near roundabout: {is_near_roundabout(my_pos)}")
        print(f"> OBU {obu_id} inside roundabout: {is_inside_roundabout(my_pos)}")

        if (is_near_roundabout(my_pos) or is_inside_roundabout(my_pos)) and is_threatening_position(my_pos, other_pos, my_heading):
            print("> Yielding — other OBU is a threat (left and close)")
            stop = True
            while stop:
                with other_obu_position_lock:
                    current_other = other_obu_position
                if not is_threatening_position(my_pos, current_other, my_heading):
                    stop = False
                    print("> Proceeding — other OBU is no longer a threat (left side cleared)")
                    break
                sleep(SLEEP_INTERVAL)

        # --- Proceed and send CAM ---
        try:
            with open("in_cam.json", "r") as f:
                msg_obj = json.load(f)
        except Exception as e:
            print(f"> Error reading 'in_cam.json': {e}")
            sys.exit(1)

        msg_obj["stationID"] = int(obu_id)
        msg_obj["latitude"] = lat
        msg_obj["longitude"] = lon
        message = json.dumps(msg_obj)

        client.publish(MQTT_TOPIC_IN, message)
        print(f"> Sent CAM lat={lat:.6f}, lon={lon:.6f}, on topic '{MQTT_TOPIC_IN}'")

        sleep(SLEEP_INTERVAL)


# ---------- MQTT Setup ----------
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message
sleep(2)
client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

# Start the MQTT network loop in a separate thread
thread = threading.Thread(target=client.loop_forever)
thread.daemon = True
thread.start()

# Begin sending trajectory
try:
    send_trajectory()
finally:
    client.disconnect()
    thread.join()
    print("\n> Disconnected and exiting.")
