# System Architecture

The Smart Parking System is an enterprise-grade IoT + AI architecture designed for fully autonomous vehicle tracking, payment collection, and gate operation.

## 1. Hardware Layer (Edge Nodes)
- **Entrance ESP32-CAM**: Deployed at the Entrance barrier. Continuously streams an MJPEG live feed to the local network. Features onboard motion detection to trigger capture events.
- **Exit ESP32-CAM**: Deployed at the Exit barrier. Continuously streams to the Exit Kiosk UI and handles departure captures.
- **NodeMCU ESP8266**: The central hardware orchestrator. It connects to the WiFi network and operates:
  - Entrance Servo Motor
  - Exit Servo Motor
  - Entrance IR Sensor (Post-gate vehicle verification)
  - Exit IR Sensor (Departure confirmation)

## 2. Artificial Intelligence Layer (Python/Flask)
When an ESP32-CAM captures a frame, the image is passed to a high-performance, locally-hosted AI inference pipeline (`ocr_service.py`):
1. **YOLOv8 Detection**: A custom-trained Indian ANPR model locates the exact bounding box of the vehicle's license plate.
2. **OpenCV Preprocessing**: A 4-stage cascading filter (CLAHE, Histogram Equalization, Bilateral Filtering, Adaptive Thresholding) sharpens blurry or skewed plate crops.
3. **PaddleOCR**: Extracts text from the preprocessed crops.
4. **Regex Validation**: Enforces strict Indian license plate formats (`^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$`).

## 3. Application & Database Layer
- **Flask Framework**: Provides the REST APIs and WebSockets required to synchronize the edge devices with the dashboard.
- **Flask-SocketIO**: Enables event-driven architecture, instantly updating the frontend Kiosks without HTTP polling.
- **SQLAlchemy (SQLite / MySQL)**: Tracks `VehicleLog`, `ParkingSlot`, and `Payment` models.
- **APScheduler**: Runs silent background jobs (like the `timeout_reservations` job which frees unpaid reservations after 5 minutes).

## 4. Presentation Layer (Frontend UIs)
Built with Vanilla CSS implementing modern Glassmorphism, tailored for 3 distinct user roles:
- **Admin Dashboard (`admin.html`)**: Real-time overview of occupied slots, system revenue, and connected camera feeds.
- **Entrance Kiosk (`entrance.html`)**: Driver-facing portal that handles QR payments, OCR success visuals, and Entrance Gate opening.
- **Exit Kiosk (`exit.html`)**: Driver-facing portal that displays final parking duration and Exit Gate operation.
