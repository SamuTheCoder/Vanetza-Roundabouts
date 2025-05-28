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


def on_connect(client, userdata, flags, rc, properties):
    print("Connected with result code "+str(rc))
    client.subscribe("vanetza/out/cam")


# É chamada automaticamente sempre que recebe uma mensagem nos tópicos subscritos em cima
def on_message(client, userdata, msg):
    message = msg.payload.decode('utf-8')
    
    
    #print('Message' + message)

    obj = json.loads(message)

    lat = obj["latitude"]
    lon = obj["longitude"]

    print("Latitude: " + str(lat))
    print("Longitude: " + str(lon))


def generate_trajectory_one():
    for lat, lon in trajectory:
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
client.connect("192.168.98.20", 1883, 60)

threading.Thread(target=client.loop_forever).start()

generate_trajectory_one()
