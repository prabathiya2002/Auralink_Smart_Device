# main.py
from flask import Flask
from threading import Thread
from mqtt_client import start_mqtt

app = Flask(__name__)

@app.route("/")
def home():
    return "AuraLink Backend Running with MQTT + LangChain + Gmail"

if __name__ == "__main__":
    # Run MQTT in a separate thread
    Thread(target=start_mqtt).start()
    app.run(host="0.0.0.0", port=5000)
