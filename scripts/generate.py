import json
import paho.mqtt.client as mqtt
import threading
from time import sleep
import math

# Define roundabout center and radius
center_lat = 40.0
center_lon = -8.0
radius = 0.0001  # ~11 meters

# Define approach, arc, and exit steps
approach_steps = 10
arc_steps = 20
exit_steps = 10

# Precompute trajectory points
trajectory = []

# Approach: move up along y-axis (latitude increases)
for i in range(approach_steps):
    lat = center_lat - 3*radius + i * (radius / approach_steps)
    lon = center_lon
    trajectory.append((lat, lon))

# Arc: half-circle from south to east (second exit)
for i in range(arc_steps):
    angle = math.pi/2 + (i * (math.pi/2) / arc_steps)  # from 90° to 180°
    lat = center_lat + radius * math.sin(angle)
    lon = center_lon + radius * math.cos(angle)
    trajectory.append((lat, lon))

# Exit: move along x-axis (longitude increases)
for i in range(exit_steps):
    lat = center_lat
    lon = center_lon + radius + i * (radius / exit_steps)
    trajectory.append((lat, lon))

# Shared variable for the other OBU's position
other_obu_pos = {"lat": None, "lon": None}
lock = threading.Lock()

def on_connect(client, userdata, flags, rc, properties):
    print("Connected with result code "+str(rc))
    client.subscribe("vanetza/out/cam")

def on_message(client, userdata, msg):
    message = msg.payload.decode('utf-8')
    obj = json.loads(message)

    lat = obj["latitude"]
    lon = obj["longitude"]

    print("Latitude: " + str(lat))
    print("Longitude: " + str(lon))
    # Update the other OBU's position
    with lock:
        other_obu_pos["lat"] = obj["latitude"]
        other_obu_pos["lon"] = obj["longitude"]

def distance(lat1, lon1, lat2, lon2):
    # Simple Euclidean distance (for small distances)
    return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

def generate_trajectory():
    for lat, lon in trajectory:
        # Wait if too close to the other OBU
        while True:
            with lock:
                other_lat = other_obu_pos["lat"]
                other_lon = other_obu_pos["lon"]
            if other_lat is not None and other_lon is not None:
                d = distance(lat, lon, other_lat, other_lon)
                print(f"Distance to other OBU: {d:.4f}")
                if d < 0.000001: # 0.0001 degrees ~ 11 meters, adjust as needed
                    print("Too close to other OBU, waiting...")
                    sleep(0.5)
                    continue
            break
        with open('in_cam.json') as f:
            m = json.load(f)
        m["latitude"] = lat
        m["longitude"] = lon
        m = json.dumps(m)
        client.publish("vanetza/in/cam", m)
        sleep(1)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message
client.connect("192.168.98.10", 1883, 60)

thread = threading.Thread(target=client.loop_forever)
thread.start()

generate_trajectory()

client.disconnect()
thread.join()