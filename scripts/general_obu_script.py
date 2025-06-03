import json
import paho.mqtt.client as mqtt
import threading
from time import sleep
import math
import sys

if len(sys.argv) < 2:
    print("Usage: python generate.py <obu_id>")
    sys.exit(1)

obu_id = int(sys.argv[1])

# Define roundabout center and radius
center_lat = 40.0
center_lon = -8.0
radius = 0.0001  # ~11 meters

# Define approach, arc, and exit steps
approach_steps = 10
arc_steps = 20
exit_steps = 10

def generate_trajectory_points(obu_id):
    trajectory = []
    if obu_id == 1:
        # OBU 1: Approach from south, exit east
        for i in range(approach_steps):
            lat = center_lat - 3*radius + i * (radius / approach_steps)
            lon = center_lon
            trajectory.append((lat, lon))
        for i in range(arc_steps):
            angle = math.pi/2 + (i * (math.pi/2) / arc_steps)  # 90° to 180°
            lat = center_lat + radius * math.sin(angle)
            lon = center_lon + radius * math.cos(angle)
            trajectory.append((lat, lon))
        for i in range(exit_steps):
            lat = center_lat
            lon = center_lon + radius + i * (radius / exit_steps)
            trajectory.append((lat, lon))
    elif obu_id == 2:
        # OBU 2: Approach from west, exit south
        for i in range(approach_steps):
            lat = center_lat
            lon = center_lon - 3*radius + i * (radius / approach_steps)
            trajectory.append((lat, lon))
        for i in range(arc_steps):
            angle = math.pi + (i * (math.pi/2) / arc_steps)  # 180° to 270°
            lat = center_lat + radius * math.sin(angle)
            lon = center_lon + radius * math.cos(angle)
            trajectory.append((lat, lon))
        for i in range(exit_steps):
            lat = center_lat - radius - i * (radius / exit_steps)
            lon = center_lon
            trajectory.append((lat, lon))
    else:
        print(f"Unknown OBU ID: {obu_id}")
        sys.exit(1)
    return trajectory

trajectory = generate_trajectory_points(obu_id)

# Select MQTT broker IP based on OBU ID
if obu_id == 1:
    broker_ip = "192.168.98.10"
elif obu_id == 2:
    broker_ip = "192.168.98.20"
else:
    print(f"Unknown OBU ID: {obu_id}")
    sys.exit(1)

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
    #print("Latitude: " + str(lat))
    #print("Longitude: " + str(lon))
    with lock:
        other_obu_pos["lat"] = lat
        other_obu_pos["lon"] = lon

def distance(lat1, lon1, lat2, lon2):
    return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

def is_in_arc(lat, lon):
    arc_start = approach_steps
    arc_end = approach_steps + arc_steps
    arc_points = trajectory[arc_start:arc_end]
    threshold = radius * 1.2
    for arc_lat, arc_lon in arc_points:
        if distance(lat, lon, arc_lat, arc_lon) < threshold:
            return True
    return False

def generate_trajectory():
    for idx, (lat, lon) in enumerate(trajectory):
        # Yield before entering arc if other OBU is in arc
        if idx == approach_steps:
            print("Approaching roundabout")
            while True:
                with lock:
                    other_lat = other_obu_pos["lat"]
                    other_lon = other_obu_pos["lon"]
                if other_lat is not None and other_lon is not None:
                    if is_in_arc(other_lat, other_lon):
                        print("Other OBU is in the roundabout, waiting to yield...")
                        sleep(0.5)
                        continue
                break

        if is_in_arc(lat, lon):
            print("I'm inside the roundabout")
        

        if idx > approach_steps + arc_steps:
            print("I left the roundabout")

        # Collision avoidance
        while True:
            with lock:
                other_lat = other_obu_pos["lat"]
                other_lon = other_obu_pos["lon"]
            if other_lat is not None and other_lon is not None:
                d = distance(lat, lon, other_lat, other_lon)
                print(f"Distance to other OBU: {d:.4f}")
                if d < 0.000001:
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
client.connect(broker_ip, 1883, 60)

thread = threading.Thread(target=client.loop_forever)
thread.start()

generate_trajectory()

client.disconnect()
thread.join()
