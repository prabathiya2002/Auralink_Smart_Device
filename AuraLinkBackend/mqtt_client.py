# mqtt_client.py
import paho.mqtt.client as mqtt
import json
from llm_module import generate_quote, summarize_email
from email_handler import get_latest_email
import os

BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
PORT = int(os.getenv("MQTT_PORT", 1883))
SENSOR_TOPIC = "auralink/sensor/data"
RESPONSE_TOPIC = "auralink/backend/response"

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT Broker:", BROKER)
    client.subscribe(SENSOR_TOPIC)

def on_message(client, userdata, msg):
    try:
        # Decode sensor data
        payload = json.loads(msg.payload.decode())
        temp = payload.get("temperature")
        hum = payload.get("humidity")
        tds = payload.get("tds")

        # Generate quote (poetic part only)
        quote = generate_quote(temp, hum)

        # Get latest email and summarize
        email_text = get_latest_email()
        summary, urgency = summarize_email(email_text)

        # Build structured response
        response = {
            "temperature": temp,
            "humidity": hum,
            "tds": tds,
            "quote": quote,            # Just the poetic text
            "email_summary": summary,
            "urgency": urgency
        }

        # Publish to ESP32
        client.publish(RESPONSE_TOPIC, json.dumps(response))
        print("Published response:", response)

    except Exception as e:
        print(f"[MQTT Message Error] {e}")

def start_mqtt():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER, PORT, 60)
    print("MQTT Client Started — Listening for ESP32 data...")
    client.loop_forever()
