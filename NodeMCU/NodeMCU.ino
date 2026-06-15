#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h>
#include <Servo.h>

// --- WiFi Credentials ---
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// --- Flask Server URLs ---
// Replace YOUR_SERVER_IP with your laptop's local IPv4 Address
const char* serverUrlSlot = "http://YOUR_SERVER_IP:5000/api/hardware/update-slot";
const char* serverUrlGate = "http://YOUR_SERVER_IP:5000/api/gate-status";
 

// --- Hardware Pins ---
const int irPin1 = 5;     // IR1 (Slot A1) - D1
const int irPin2 = 4;     // IR2 (Slot A2) - D2
const int irPin3 = 14;    // IR3 (Slot A3) - D5

 
const int servoPin = 16;  // Gate Servo - D0 (D8 is a boot pin, D0 is safer)

Servo gateServo;

// --- State Variables ---
bool isSlotA1Occupied = false;
bool isSlotA2Occupied = false;
bool isSlotA3Occupied = false;
 
String currentGateStatus = "CLOSED";

void setup() {
  Serial.begin(115200);
  
  // Connect to WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to WiFi!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());

  // Initialize Pins
  pinMode(irPin1, INPUT);
  pinMode(irPin2, INPUT);
  pinMode(irPin3, INPUT);
  
 
  
  // Initialize Servo
  gateServo.attach(servoPin);
  gateServo.write(0); // 0 degrees = Closed Gate
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi Disconnected! Attempting to reconnect...");
    WiFi.reconnect();
    delay(1000);
    return;
  }

  checkParkingSlots();    // Poll IR Sensors for A1, A2, A3
 
  checkGateStatus();      // Poll Flask API for Gate Commands
  
  delay(1000); // Wait 1 second before next poll to prevent spamming
}

void checkParkingSlots() {
  // Read IR sensors (LOW usually means obstacle detected / occupied for standard IR sensors)
  bool currentA1 = (digitalRead(irPin1) == LOW);
  bool currentA2 = (digitalRead(irPin2) == LOW);
  bool currentA3 = (digitalRead(irPin3) == LOW);

  // Update Slot A1
  if (currentA1 != isSlotA1Occupied) {
    isSlotA1Occupied = currentA1;
    sendSlotUpdate("A1", isSlotA1Occupied ? "Occupied" : "Available");
  }
  
  // Update Slot A2
  if (currentA2 != isSlotA2Occupied) {
    isSlotA2Occupied = currentA2;
    sendSlotUpdate("A2", isSlotA2Occupied ? "Occupied" : "Available");
  }
  
  // Update Slot A3
  if (currentA3 != isSlotA3Occupied) {
    isSlotA3Occupied = currentA3;
    sendSlotUpdate("A3", isSlotA3Occupied ? "Occupied" : "Available");
  }
}

 

void sendSlotUpdate(String slotId, String status) {
  WiFiClient client;
  HTTPClient http;
  http.begin(client, serverUrlSlot);
  http.setTimeout(3000);
  http.addHeader("Content-Type", "application/json");

  // Create JSON Payload
  StaticJsonDocument<200> doc;
  doc["slot_id"] = slotId;
  doc["status"] = status;
  
  String requestBody;
  serializeJson(doc, requestBody);
  
  // Send POST Request
  int httpResponseCode = http.POST(requestBody);
  if (httpResponseCode > 0) {
    Serial.printf("Slot %s is now %s. Server response: %d\n", slotId.c_str(), status.c_str(), httpResponseCode);
  } else {
    Serial.printf("Error updating slot %s. HTTP Code: %d\n", slotId.c_str(), httpResponseCode);
  }
  http.end();
}

void checkGateStatus() {
  WiFiClient client;
  HTTPClient http;
  http.begin(client, serverUrlGate);
  http.setTimeout(3000);
  
  int httpResponseCode = http.GET();
  if (httpResponseCode > 0) {
    String payload = http.getString();
    
    // Parse JSON Response
    StaticJsonDocument<200> doc;
    DeserializationError error = deserializeJson(doc, payload);
    
    if (!error) {
      String newGateStatus = doc["gate_status"].as<String>();
      
      // If gate status changed on the server, move the servo!
      if (newGateStatus != currentGateStatus) {
        currentGateStatus = newGateStatus;
        if (currentGateStatus == "OPEN") {
          Serial.println("Command Received: OPENING GATE!");
          gateServo.write(90); // Rotate 90 degrees to open
        } else {
          Serial.println("Command Received: CLOSING GATE!");
          gateServo.write(0);  // Rotate back to 0 degrees to close
        }
      }
    }
  }
  http.end();
}
