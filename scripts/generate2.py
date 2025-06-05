import json
import paho.mqtt.client as mqtt
import threading
from time import sleep
import gpxpy
from geopy.distance import geodesic

# ========== CONFIGURATION ==========
GPX_FILE = 'path2.gpx'
ROUNDABOUT_FILE = 'roundabout.gpx'
MQTT_BROKER = '192.168.98.10'
MQTT_PORT = 1883
MQTT_TOPIC_IN = 'vanetza/in/cam'
MQTT_TOPIC_OUT = 'vanetza/out/cam'
SLEEP_INTERVAL = 1  # seconds
ROUNDABOUT_MARGIN = 15  # meters
# ===================================

# ---------- Global Data ----------
trajectory = []
other_obu_position = None  # Last known position of other OBU

# ---------- GPX Loader ----------
def load_gpx_coordinates(gpx_path):
    with open(gpx_path, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)
        coords = []
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    coords.append((point.latitude, point.longitude))
        for waypoint in gpx.waypoints:
            coords.append((waypoint.latitude, waypoint.longitude))
        return coords

# ---------- Roundabout Geometry ----------
roundabout_coords = load_gpx_coordinates(ROUNDABOUT_FILE)

if len(roundabout_coords) < 2:
    print(": Roundabout GPX must have at least 2 points (center and edge)")
    exit(1)

ROUNDABOUT_CENTER = roundabout_coords[0]
ROUNDABOUT_RADIUS = geodesic(ROUNDABOUT_CENTER, roundabout_coords[1]).meters

print(f": Roundabout center: {ROUNDABOUT_CENTER}, radius: {ROUNDABOUT_RADIUS:.2f}m")

# ---------- Trajectory ----------
trajectory = load_gpx_coordinates(GPX_FILE)
print(f": Loaded {len(trajectory)} points from GPX file")

# ---------- Distance Helpers ----------
def is_inside_roundabout(pos):
    if pos is None:
        return False
    return geodesic(pos, ROUNDABOUT_CENTER).meters <= ROUNDABOUT_RADIUS

def is_near_roundabout(pos, margin=ROUNDABOUT_MARGIN):
    d = geodesic(pos, ROUNDABOUT_CENTER).meters
    return ROUNDABOUT_RADIUS < d < (ROUNDABOUT_RADIUS + margin)

# ---------- MQTT Callbacks ----------
def on_connect(client, userdata, flags, rc, properties):
    print(": Connected with result code", rc)
    client.subscribe(MQTT_TOPIC_OUT)

other_obu_position_lock = threading.Lock()

def on_message(client, userdata, msg):
    global other_obu_position
    try:
        obj = json.loads(msg.payload.decode('utf-8'))

        lat = obj.get("latitude")
        lon = obj.get("longitude")

        if lat is not None and lon is not None:
            with other_obu_position_lock:
                other_obu_position = (lat, lon)
            print(f": Received CAM from other OBU: lat={lat}, lon={lon}")

    except Exception as e:
        print(": Error parsing CAM:", e)

# ---------- Main Sending Loop ----------
#stop tag (if False, it only turns truei when obu 1 exits the roundabout)
stop = False
def send_trajectory():
    global stop
    for lat, lon in trajectory:
        my_pos = (lat, lon)

        with other_obu_position_lock:  # Acquire lock before reading
            other_obu_pos = other_obu_position

        # --- Decision logic: Should I yield? ---
        print(f":OBU 2 is near roundabout: {is_near_roundabout(my_pos)}")
        print(f":OBU 2 is inside roundabout: {is_inside_roundabout(my_pos)}")
        print(f":OBU 1 is inside roundabout: {is_inside_roundabout(other_obu_pos)}")

        if is_near_roundabout(my_pos) and is_inside_roundabout(other_obu_pos):
            stop = True
            while stop:
                with other_obu_position_lock:
                    if not is_inside_roundabout(other_obu_position):
                        stop = False
                        print(": Proceeding — other OBU has exited roundabout")
                        break
                sleep(SLEEP_INTERVAL)

        # --- Proceed and send CAM ---
        with open('in_cam.json') as f:
            m = json.load(f)

        m["latitude"] = lat
        m["longitude"] = lon

        message = json.dumps(m)
        client.publish(MQTT_TOPIC_IN, message)
        print(f": Sent CAM: lat={lat}, lon={lon}")
        sleep(SLEEP_INTERVAL)

# ---------- MQTT Setup ----------
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message
sleep(2)
client.connect(MQTT_BROKER, MQTT_PORT, 60)

# ---------- Start Everything ----------
thread = threading.Thread(target=client.loop_forever)
thread.start()
send_trajectory()
client.disconnect()
thread.join()
