import paho.mqtt.client as mqtt
import json
import signal
import threading
import time
import sys

# Define list of OBUs and central broker
obu_brokers = [
    {"id": "OBU1", "host": "192.168.98.10", "port": 1883},
    {"id": "OBU2", "host": "192.168.98.20", "port": 1883},
]
central_broker = {"host": "192.168.98.30", "port": 1883}

# Shutdown flag
running = True

# Connect to central broker
central_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
central_client.connect(central_broker["host"], central_broker["port"])
central_client.loop_start()

def make_on_message(obu_id):
    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            lat = payload.get("latitude")
            lon = payload.get("longitude")

            if lat is not None and lon is not None:
                simplified_msg = {
                    "obu_id": obu_id,
                    "latitude": lat,
                    "longitude": lon
                }
                central_client.publish("frontend/obu_position", json.dumps(simplified_msg))
                print(f"[{obu_id}] Published to frontend: {simplified_msg}")
            else:
                print(f"[{obu_id}] Received CAM message without position")

        except Exception as e:
            print(f"Error processing message from {obu_id}: {e}")
    return on_message


# Track all OBU clients for cleanup
obu_clients = []

# Connect to each OBU broker
for obu in obu_brokers:
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.on_message = make_on_message(obu["id"])
        client.connect(obu["host"], obu["port"])
        client.subscribe("vanetza/out/#")
        client.loop_start()
        obu_clients.append(client)
        print(f"Connected and subscribed to {obu['id']} at {obu['host']}:{obu['port']}")
    except Exception as e:
        print(f"Failed to connect to {obu['id']} at {obu['host']}: {e}")

# Signal handling for clean exit
def shutdown(signum, frame):
    global running
    print("\nShutting down gracefully...")
    running = False

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

# Keep alive loop
try:
    while running:
        time.sleep(1)
except KeyboardInterrupt:
    shutdown(None, None)

# Cleanup
for client in obu_clients:
    client.loop_stop()
    client.disconnect()

central_client.loop_stop()
central_client.disconnect()

print("All MQTT clients disconnected. Bye!")