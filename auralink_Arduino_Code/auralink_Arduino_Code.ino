#include <WiFi.h>
#include <PubSubClient.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>
#include <ArduinoJson.h>

//  WiFi & MQTT 
const char* ssid = "Dialog 4G 135";
const char* password = "2099EDF7";
const char* mqtt_server = "broker.hivemq.com";

WiFiClient espClient;
PubSubClient client(espClient);

//  OLED 
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

//  Sensors & Pins 
#define DHTPIN 4
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

#define TDS_PIN 34
#define RED_LED 25
#define GREEN_LED 26
#define BLUE_LED 27
#define BUZZER 13

//  Timing 
unsigned long previousMillis = 0;
const long interval = 2000; // 2 seconds

//  Buzzer Timing 
bool buzzerActive = false;
unsigned long buzzerStart = 0;
const unsigned long BUZZER_DURATION = 500; // 0.5 seconds

//  Alert Variables 
String lastUrgency = "";
String currentUrgency = "";

//  Latest Sensor & MQTT Data 
float latestTemp = 0;
float latestHum = 0;
float latestTDS = 0;
String latestQuote = "";
String latestEmail = "";

//  Functions 
void setLED(int r, int g, int b) {
  analogWrite(RED_LED, 255 - r);    // Common Anode
  analogWrite(GREEN_LED, 255 - g);
  analogWrite(BLUE_LED, 255 - b);
}

float readTDS() {
  int analogBuffer[30];
  for (int i = 0; i < 30; i++) {
    analogBuffer[i] = analogRead(TDS_PIN);
    delay(5);
  }
  long avg = 0;
  for (int i = 0; i < 30; i++) avg += analogBuffer[i];
  avg /= 30;
  float voltage = avg * (3.3 / 4095.0);
  float tdsValue = (133.42 * voltage * voltage * voltage
                    - 255.86 * voltage * voltage
                    + 857.39 * voltage) * 0.5;
  return tdsValue;
}

void activateAlert(String urgency) {
  // Set RGB continuously
  if (urgency == "High") setLED(255, 0, 0);
  else if (urgency == "Moderate") setLED(255, 255, 0);
  else if (urgency == "Low") setLED(0, 255, 0);
  else setLED(0,0,0);

  // Start buzzer using tone() only once
  if (!buzzerActive) {
    tone(BUZZER, 2000); // 2kHz continuous beep
    buzzerStart = millis();
    buzzerActive = true;
  }
}

void updateOLED() {
  display.clearDisplay();
  display.setCursor(0,0);
  // Show sensors first
  display.println("Temp: " + String(latestTemp) + " C");
  display.println("Hum: " + String(latestHum) + " %");
  display.println("TDS: " + String(latestTDS) + " ppm");
  display.println(""); // blank line
  // Show quote/email below
  //display.println("Quote: " + latestQuote);
  display.println("Email: " + latestEmail);
  display.display();
}

// ---------- MQTT Callback ----------
void callback(char* topic, byte* payload, unsigned int length) {
  String msg = "";
  for (int i = 0; i < length; i++) msg += (char)payload[i];
  msg.trim();

  StaticJsonDocument<384> doc;
  DeserializationError error = deserializeJson(doc, msg);
  if (error) return;

  currentUrgency = doc["urgency"] | "";
  latestQuote = doc["quote"] | "";
  latestEmail = doc["email_summary"] | "";

  if (currentUrgency != "" && currentUrgency != lastUrgency) {
    lastUrgency = currentUrgency;
    activateAlert(currentUrgency);
  }

  updateOLED();
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Connecting to MQTT...");
    if (client.connect("ESP32-AuraLink")) {
      Serial.println("Connected!");
      client.subscribe("auralink/backend/response");
    } else {
      Serial.print("Failed, rc=");
      Serial.print(client.state());
      delay(2000);
    }
  }
}

//  Setup 
void setup() {
  Serial.begin(115200);

  pinMode(RED_LED, OUTPUT);
  pinMode(GREEN_LED, OUTPUT);
  pinMode(BLUE_LED, OUTPUT);
  pinMode(BUZZER, OUTPUT);
  setLED(0,0,0);
  noTone(BUZZER);

  dht.begin();
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED not found!");
    for (;;);
  }
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0,10);
  display.println("AuraLink Ready");
  display.display();

  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("Connected!");

  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);
}

//  Main Loop 
void loop() {
  if (!client.connected()) reconnect();
  client.loop();

  unsigned long now = millis();

  // Sensor reading and publishing
  if (now - previousMillis >= interval) {
    previousMillis = now;
    latestTemp = dht.readTemperature();
    latestHum = dht.readHumidity();
    latestTDS = readTDS();

    StaticJsonDocument<128> doc;
    doc["temperature"] = latestTemp;
    doc["humidity"] = latestHum;
    doc["tds"] = latestTDS;
    char buffer[128];
    serializeJson(doc, buffer);
    client.publish("auralink/sensor/data", buffer);

    Serial.printf("Temp: %.1f C | Hum: %.1f %% | TDS: %.1f ppm\n", latestTemp, latestHum, latestTDS);

    // Update OLED with latest sensors and previous quote/email
    updateOLED();
  }

  // Non-blocking buzzer off after 0.5 seconds
  if (buzzerActive && (now - buzzerStart >= BUZZER_DURATION)) {
    noTone(BUZZER); // Stop buzzer
    buzzerActive = false;
  }
}
