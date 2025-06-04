import json
import paho.mqtt.client as mqtt
import threading
from time import sleep
import math
import gpxpy
import numpy as np
from collections import deque

# ========== CONFIGURATION ==========
GPX_FILE = 'path2.gpx'
MQTT_BROKER = '192.168.98.20'
MQTT_PORT = 1883
MQTT_TOPIC_IN = 'vanetza/in/cam'
MQTT_TOPIC_OUT = 'vanetza/out/cam'
SLEEP_INTERVAL = 1  # seconds
# ===================================

# Distance thresholds (~meters)
DISTANCE_SLOWDOWN = 0.00025   # ~22m
DISTANCE_STOP = 0.00015      # ~11m

# Circle detection
ROUNDABOUT_RADIUS_TOLERANCE = 0.00004  # Max radius deviation allowed
POSITION_HISTORY_LENGTH = 5
EMA_ALPHA = 0.3  # For smoothing radius estimates

trajectory = []
other_obu_pos = {"lat": None, "lon": None}
lock = threading.Lock()
prev_my_position = None
other_positions = deque(maxlen=POSITION_HISTORY_LENGTH)
my_positions = deque(maxlen=POSITION_HISTORY_LENGTH)

# ---------- Load GPX Coordinates ----------
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

trajectory = load_gpx_coordinates(GPX_FILE)
print(f"Loaded {len(trajectory)} points from GPX file")

# ---------- MQTT Setup ----------
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
                other_positions.append((lat, lon))
            print(f"Received other OBU position: lat={lat}, lon={lon}")
    except Exception as e:
        print("Error parsing CAM:", e)

# ---------- Geometry Helpers ----------
def distance(lat1, lon1, lat2, lon2):
    return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

def calculate_heading(p1, p2):
    dy = p2[0] - p1[0]
    dx = p2[1] - p1[1]
    return math.degrees(math.atan2(dy, dx)) % 360

def is_in_left_front_quarter(my_lat, my_lon, my_heading, other_lat, other_lon):
    dx = other_lon - my_lon
    dy = other_lat - my_lat
    angle_to_other = math.degrees(math.atan2(dy, dx)) % 360
    diff = (angle_to_other - my_heading + 360) % 360
    return 45 < diff < 135

# ---------- Circle Detection ----------
ema_r = None  # Global EMA radius

def is_moving_in_circle(positions):
    global ema_r
    if len(positions) < POSITION_HISTORY_LENGTH:
        return False

    lats, lons = zip(*positions)
    x = np.array(lons)
    y = np.array(lats)

    x_m, y_m = np.mean(x), np.mean(y)
    u, v = x - x_m, y - y_m
    Suu = np.sum(u*u)
    Suv = np.sum(u*v)
    Svv = np.sum(v*v)
    Suuu = np.sum(u*u*u)
    Suvv = np.sum(u*v*v)
    Svvv = np.sum(v*v*v)
    Svuu = np.sum(v*u*u)

    A = np.array([[Suu, Suv], [Suv, Svv]])
    b = np.array([0.5*(Suuu + Suvv), 0.5*(Svvv + Svuu)])
    try:
        uc, vc = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        return False

    xc = x_m + uc
    yc = y_m + vc
    radii = np.sqrt((x - xc)**2 + (y - yc)**2)
    avg_r = np.mean(radii)

    # Apply EMA smoothing to radius
    if ema_r is None:
        ema_r = avg_r
    else:
        ema_r = EMA_ALPHA * avg_r + (1 - EMA_ALPHA) * ema_r

    deviation = np.max(np.abs(radii - ema_r))
    print(f"Radii: {radii}, EMA radius: {ema_r:.7f}, Max deviation: {deviation:.7f}")
    return deviation < ROUNDABOUT_RADIUS_TOLERANCE

# ---------- Main Trajectory Function ----------
def generate_trajectory():
    global prev_my_position
    for lat, lon in trajectory:
        my_positions.append((lat, lon))

        with lock:
            other_lat = other_obu_pos["lat"]
            other_lon = other_obu_pos["lon"]
            positions = list(other_positions)

        heading = calculate_heading(prev_my_position, (lat, lon)) if prev_my_position else 0
        prev_my_position = (lat, lon)

        myself_in_circle = is_moving_in_circle(list(my_positions))

        if other_lat is not None and other_lon is not None:
            d = distance(lat, lon, other_lat, other_lon)
            other_in_circle = is_moving_in_circle(positions)
            in_left_front = is_in_left_front_quarter(lat, lon, heading, other_lat, other_lon)

            print(f"Distance: {d:.7f}, I_in_circle: {myself_in_circle}, Other_in_circle: {other_in_circle}, LeftFront: {in_left_front}")
            if not myself_in_circle and other_in_circle and in_left_front and d < DISTANCE_SLOWDOWN:
                print("SLOWDOWN CONDITION MET!")
                if d < DISTANCE_STOP:
                    print("Too close! Stopping...")
                    sleep(0.5)
                    continue
                else:
                    print("⚠️ Slowing down due to roundabout proximity...")
                    sleep(SLEEP_INTERVAL * 1.5)

        # Send CAM
        with open('in_cam.json') as f:
            m = json.load(f)
        m["latitude"] = lat
        m["longitude"] = lon
        message = json.dumps(m)
        client.publish(MQTT_TOPIC_IN, message)
        print(f"Sent CAM: lat={lat}, lon={lon}")
        sleep(SLEEP_INTERVAL)

# ---------- MQTT Client ----------
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message
sleep(2)
client.connect(MQTT_BROKER, MQTT_PORT, 60)

# ---------- Threads ----------
thread = threading.Thread(target=client.loop_forever)
thread.start()
generate_trajectory()
client.disconnect()
thread.join()