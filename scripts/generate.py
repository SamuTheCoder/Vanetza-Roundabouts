import json
import paho.mqtt.client as mqtt
import threading
from time import sleep
import gpxpy
from geopy.distance import geodesic

# ========== CONFIGURATION ==========
GPX_FILE = 'path1.gpx'
ROUNDABOUT_FILE = 'roundabout.gpx'
MQTT_BROKER = '192.168.98.20'
MQTT_PORT = 1883
MQTT_TOPIC_IN = 'vanetza/in/cam'
MQTT_TOPIC_OUT = 'vanetza/out/cam'
SLEEP_INTERVAL = 1 # seconds
ROUNDABOUT_MARGIN = 15  # meters
# ===================================

# ---------- Global Data ----------
trajectory = []
other_obu_position = (None, None)  # Last known position of other OBU

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
    print("❌ Roundabout GPX must have at least 2 points (center and edge)")
    exit(1)

ROUNDABOUT_CENTER = roundabout_coords[0]
ROUNDABOUT_RADIUS = geodesic(ROUNDABOUT_CENTER, roundabout_coords[1]).meters

print(f"🏁 Roundabout center: {ROUNDABOUT_CENTER}, radius: {ROUNDABOUT_RADIUS:.2f}m")

# ---------- Trajectory ----------
trajectory = load_gpx_coordinates(GPX_FILE)
print(f"✅ Loaded {len(trajectory)} points from GPX file")

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
    print("🔌 Connected with result code", rc)
    client.subscribe(MQTT_TOPIC_OUT)

def on_message(client, userdata, msg):
    try:
        global other_obu_position
        obj = json.loads(msg.payload.decode('utf-8'))

        lat = obj.get("latitude")
        lon = obj.get("longitude")
        print("OBU 1 Recv lat: ", lat, "lon:", lon)

        if lat is not None and lon is not None:
            other_obu_position = (lat, lon)
            print(f"📡 Received CAM from other OBU: lat={lat}, lon={lon}")

    except Exception as e:
        print("❌ Error parsing CAM:", e)

#stop tag (if False, it only turns truei when obu 1 exits the roundabout)
stop = False
# ---------- Main Sending Loop ----------
def send_trajectory():
    global stop
    for lat, lon in trajectory:
        my_pos = (lat, lon)

        # --- Decision logic: Should I yield? ---
        print(f"Other obu position: {other_obu_position}")
        print(f"OBU 1 is near roundabout: {is_near_roundabout(my_pos)}")
        print(f"OBU 1 is inside roundabout: {is_inside_roundabout(my_pos)}")
        print(f"OBU 2 is inside roundabout: {is_inside_roundabout(other_obu_position)}")
        if stop:
            if is_inside_roundabout(other_obu_position):
                print("🛑 Waiting — other OBU is still inside roundabout")
                sleep(SLEEP_INTERVAL)
                continue
            else:
                stop = False
                print("✅ Proceeding — other OBU has exited roundabout")
        if is_near_roundabout(my_pos) and is_inside_roundabout(other_obu_position):
            stop = True
            print("🛑 Waiting — other OBU is inside roundabout")
            sleep(SLEEP_INTERVAL)
            continue

        # --- Proceed and send CAM ---
        with open('in_cam.json') as f:
            m = json.load(f)

        m["latitude"] = lat
        m["longitude"] = lon

        message = json.dumps(m)
        client.publish(MQTT_TOPIC_IN, message)
        print(f"📤 Sent CAM: lat={lat}, lon={lon}")
        print("Connected to 192.168.98.20, it's supposed to be OBU 2")
        sleep(SLEEP_INTERVAL)

# ---------- MQTT Setup ----------
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)

# ---------- Start Everything ----------
thread = threading.Thread(target=client.loop_forever)
thread.start()
send_trajectory()
client.disconnect()
thread.join()
