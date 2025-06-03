import json
import paho.mqtt.client as mqtt
import threading
from time import sleep
import math
import gpxpy

# ========== CONFIGURATION ==========
GPX_FILE = 'obu2.gpx'
MQTT_BROKER = '192.168.98.20'
MQTT_PORT = 1883
MQTT_TOPIC_IN = 'vanetza/in/cam'
MQTT_TOPIC_OUT = 'vanetza/out/cam'
DISTANCE_THRESHOLD = 0.00005  # ~5.5 meters
SLEEP_INTERVAL = 1  # seconds
# ===================================

def load_gpx_coordinates(gpx_path):
    with open(gpx_path, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)
        coords = []

        for waypoint in gpx.waypoints:
            coords.append((waypoint.latitude, waypoint.longitude))

        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    coords.append((point.latitude, point.longitude))

        return coords

trajectory = load_gpx_coordinates(GPX_FILE)

print(f"Loaded {len(trajectory)} points from GPX file")

# Shared variable for the other OBU's position
other_obu_pos = {"lat": None, "lon": None}
lock = threading.Lock()

def on_connect(client, userdata, flags, rc, properties):
    print("Connected with result code", rc)
    client.subscribe(MQTT_TOPIC_OUT)

def on_message(client, userdata, msg):
    try:
        obj = json.loads(msg.payload.decode('utf-8'))
        lat = obj.get("latitude")
        lon = obj.get("longitude")
        if lat is not None and lon is not None:
            with lock:
                other_obu_pos["lat"] = lat
                other_obu_pos["lon"] = lon
            print(f"Received other OBU position: lat={lat}, lon={lon}")
    except Exception as e:
        print("Error parsing incoming CAM message:", e)

def distance(lat1, lon1, lat2, lon2):
    return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

def generate_trajectory():
    print("a")
    for lat, lon in trajectory:
        # Wait if too close to the other OBU
        print("2")
        while True:
            with lock:
                other_lat = other_obu_pos["lat"]
                other_lon = other_obu_pos["lon"]
            if other_lat is not None and other_lon is not None:
                d = distance(lat, lon, other_lat, other_lon)
                print(f"Distance to other OBU: {d:.7f}")
                if d < DISTANCE_THRESHOLD:
                    print("Too close to other OBU, waiting...")
                    sleep(0.5)
                    continue
            break

        with open('in_cam.json') as f:
            m = json.load(f)

        # Inject new coordinates into CAM message
        m["latitude"] = lat
        m["longitude"] = lon

        message = json.dumps(m)
        client.publish(MQTT_TOPIC_IN, message)
        print(f"Sent CAM message: lat={lat}, lon={lon}")
        sleep(SLEEP_INTERVAL)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_BROKER, MQTT_PORT, 60)

# Start MQTT loop in a separate thread
thread = threading.Thread(target=client.loop_forever)
thread.start()

# Start sending trajectory
generate_trajectory()

# Clean shutdown
client.disconnect()
thread.join()