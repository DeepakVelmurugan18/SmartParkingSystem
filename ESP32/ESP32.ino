#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "esp_camera.h"

#include "img_converters.h"
#include "esp_http_server.h"

// ========================================================
// Wi-Fi Credentials
// ========================================================
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// ========================================================
// Flask Server URLs
// ========================================================
String serverStatusUrl = "http://YOUR_SERVER_IP:5000/api/camera/status";
String serverUploadUrl = "http://YOUR_SERVER_IP:5000/api/camera/upload";
String serverMotionUrl = "http://YOUR_SERVER_IP:5000/api/camera/motion-detected";
String serverCaptureUrl = "http://YOUR_SERVER_IP:5000/api/camera/capture-started";
String serverRegisterUrl = "http://YOUR_SERVER_IP:5000/api/camera/register";

// ========================================================
// CAMERA_MODEL_AI_THINKER Pin Definition
// ========================================================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

enum State { IDLE, STABILIZING, COOLDOWN };
State currentState = IDLE;
unsigned long stateTimer = 0;
unsigned long lastPollTime = 0;

#define GRID_SIZE 10
uint8_t prevGrid[GRID_SIZE * GRID_SIZE] = {0};

int computeMotion(camera_fb_t * fb) {
  // Decode JPEG to RGB888 to perform lightweight motion check
  uint8_t * rgb = (uint8_t *)malloc(fb->width * fb->height * 3);
  if (!rgb) {
    return 0;
  }
  
  if (!fmt2rgb888(fb->buf, fb->len, fb->format, rgb)) {
    free(rgb);
    return 0;
  }
  
  int motionCount = 0;
  int cellW = fb->width / GRID_SIZE;
  int cellH = fb->height / GRID_SIZE;
  
  // 60% Region of Interest (ROI) - Ignore 20% on all borders
  int startGrid = GRID_SIZE * 0.2;
  int endGrid = GRID_SIZE * 0.8;
  
  for (int y = startGrid; y < endGrid; y++) {
    for (int x = startGrid; x < endGrid; x++) {
      int px = x * cellW + cellW/2;
      int py = y * cellH + cellH/2;
      int idx = (py * fb->width + px) * 3;
      
      // Grayscale approximation
      uint8_t val = (rgb[idx] + rgb[idx+1] + rgb[idx+2]) / 3;
      
      int diff = abs((int)val - (int)prevGrid[y*GRID_SIZE + x]);
      if (diff > 30) { // Motion threshold
        motionCount++;
      }
      prevGrid[y*GRID_SIZE + x] = val;
    }
  }
  
  free(rgb);
  return motionCount;
}

void notifyMotion() {
  WiFiClient client;
  HTTPClient http;
  http.begin(client, serverMotionUrl);
  http.POST("");
  http.end();
}

void notifyCapture() {
  WiFiClient client;
  HTTPClient http;
  http.begin(client, serverCaptureUrl);
  http.POST("");
  http.end();
}

void uploadFrame(camera_fb_t * fb) {
  WiFiClient client;
  HTTPClient http;
  http.begin(client, serverUploadUrl);
  http.setTimeout(15000);
  
  String boundary = "----ESP32Boundary" + String(millis());
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
  
  String head = "--" + boundary + "\r\n";
  head += "Content-Disposition: form-data; name=\"location\"\r\n\r\n";
  head += "entrance\r\n";
  head += "--" + boundary + "\r\n";
  head += "Content-Disposition: form-data; name=\"vehicle_image\"; filename=\"capture.jpg\"\r\n";
  head += "Content-Type: image/jpeg\r\n\r\n";
  
  String tail = "\r\n--" + boundary + "--\r\n";
  
  uint32_t contentLength = head.length() + fb->len + tail.length();
  
  uint8_t *body = (uint8_t *)malloc(contentLength);
  if (body) {
    memcpy(body, head.c_str(), head.length());
    memcpy(body + head.length(), fb->buf, fb->len);
    memcpy(body + head.length() + fb->len, tail.c_str(), tail.length());
    
    int httpResponseCode = http.POST(body, contentLength);
    
    if (httpResponseCode > 0) {
      Serial.println("Image uploaded successfully.");
    }
    
    free(body);
  }
  
  http.end();
}

// ========================================================
// MJPEG STREAM SERVER
// ========================================================
#define PART_BOUNDARY "123456789000000000000987654321"
static const char* _STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* _STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char* _STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

httpd_handle_t stream_httpd = NULL;

static esp_err_t stream_handler(httpd_req_t *req) {
  camera_fb_t * fb = NULL;
  esp_err_t res = ESP_OK;
  size_t _jpg_buf_len = 0;
  uint8_t * _jpg_buf = NULL;
  char * part_buf[64];

  res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
  if (res != ESP_OK) return res;

  while(true) {
    fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Camera capture failed");
      res = ESP_FAIL;
    } else {
      _jpg_buf_len = fb->len;
      _jpg_buf = fb->buf;
    }
    if (res == ESP_OK) {
      size_t hlen = snprintf((char *)part_buf, 64, _STREAM_PART, _jpg_buf_len);
      res = httpd_resp_send_chunk(req, (const char *)part_buf, hlen);
    }
    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(req, (const char *)_jpg_buf, _jpg_buf_len);
    }
    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
    }
    if (fb) {
      esp_camera_fb_return(fb);
      fb = NULL;
      _jpg_buf = NULL;
    } else if (_jpg_buf) {
      free(_jpg_buf);
      _jpg_buf = NULL;
    }
    if (res != ESP_OK) {
      break;
    }
    vTaskDelay(50 / portTICK_PERIOD_MS);
  }
  return res;
}

void startCameraServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 81;
  config.task_priority = 1;

  httpd_uri_t stream_uri = {
    .uri       = "/stream",
    .method    = HTTP_GET,
    .handler   = stream_handler,
    .user_ctx  = NULL
  };

  if (httpd_start(&stream_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(stream_httpd, &stream_uri);
    Serial.println("MJPEG Stream server started on port 81");
  }
}

void registerWithFlask() {
  WiFiClient client;
  HTTPClient http;
  http.begin(client, serverRegisterUrl);
  http.addHeader("Content-Type", "application/json");
  String payload = "{\"ip\":\"" + WiFi.localIP().toString() + "\"}";
  int responseCode = http.POST(payload);
  if(responseCode > 0) {
    Serial.println("Registered IP with Flask.");
  } else {
    Serial.println("Failed to register IP with Flask.");
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(false); // Clean up logs
  Serial.println();

  // 1. Connect to Wi-Fi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to WiFi!");
  registerWithFlask();

  // 2. Initialize the Camera
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  
  if (psramFound()) {
    config.frame_size = FRAMESIZE_VGA;   // 640x480
    config.jpeg_quality = 10;
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_QVGA;  // 320x240
    config.jpeg_quality = 12;
    config.fb_count = 1;
  }
  
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    return;
  }
  
  Serial.println("Camera initialized successfully.");
  startCameraServer();
  Serial.println("Monitoring...");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.reconnect();
    delay(1000);
    if(WiFi.status() == WL_CONNECTED) {
       registerWithFlask();
    }
    return;
  }

  // 1. Cooldown Period (Ignore new detections for 3-5 seconds)
  if (currentState == COOLDOWN) {
    if (millis() - stateTimer > 4000) {
      currentState = IDLE;
      Serial.println("Monitoring resumed.");
    }
    delay(100);
    return;
  }

  // 2. Manual Retake Polling (Every 1 second)
  if (millis() - lastPollTime > 1000 && currentState == IDLE) {
    lastPollTime = millis();
    WiFiClient client;
    HTTPClient http;
    http.begin(client, serverStatusUrl);
    int httpResponseCode = http.GET();
    
    if (httpResponseCode > 0) {
      String payload = http.getString();
      StaticJsonDocument<200> doc;
      if (!deserializeJson(doc, payload)) {
        if (doc["trigger_capture"]) {
          Serial.println("Capture started.");
          notifyCapture();
          
          camera_fb_t * fb = esp_camera_fb_get();
          if (fb) {
            uploadFrame(fb);
            esp_camera_fb_return(fb);
          }
          
          Serial.println("Cooldown active.");
          currentState = COOLDOWN;
          stateTimer = millis();
          http.end();
          return;
        }
      }
    }
    http.end();
  }

  // 3. Autonomous Frame-Differencing
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) return;
  
  int motionScore = computeMotion(fb);
  
  if (currentState == IDLE) {
    if (motionScore > 2) { // Motion detected inside ROI
      Serial.println("Motion detected.");
      notifyMotion();
      currentState = STABILIZING;
      stateTimer = millis();
    }
  } 
  else if (currentState == STABILIZING) {
    if (motionScore > 2) {
      // Still moving, keep resetting the timer
      stateTimer = millis();
    } else {
      // Stable! Wait for ~800-1000ms of NO motion to capture.
      if (millis() - stateTimer >= 900) {
        Serial.println("Vehicle stable.");
        Serial.println("Capture started.");
        
        notifyCapture();
        uploadFrame(fb);
        
        Serial.println("Cooldown active.");
        currentState = COOLDOWN;
        stateTimer = millis();
      }
    }
  }
  
  esp_camera_fb_return(fb);
  delay(150); // ~6-7 FPS for motion detection
}
