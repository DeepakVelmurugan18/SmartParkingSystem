# 🚗 Enterprise AI Smart Parking System

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" />
  <img src="https://img.shields.io/badge/Flask-Backend-green.svg" />
  <img src="https://img.shields.io/badge/YOLOv8-AI-red.svg" />
  <img src="https://img.shields.io/badge/EasyOCR-OCR-orange.svg" />
  <img src="https://img.shields.io/badge/ESP32--CAM-IoT-success.svg" />
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" />
</p>

## 📌 Overview

**Enterprise AI Smart Parking System** is a production-style Intelligent Transportation System that combines **Computer Vision, IoT, Artificial Intelligence, and Real-Time Web Technologies** to automate vehicle entry, parking slot allocation, QR payment processing, and exit management.

The system performs **Automatic Number Plate Recognition (ANPR)** using **YOLOv8 + EasyOCR/OpenCV**, communicates with **ESP32-CAM and NodeMCU hardware**, and provides a **real-time dashboard** powered by Flask and Socket.IO.

---

# ✨ Key Features

* 🤖 AI-based Automatic Number Plate Recognition (ANPR)
* 📷 ESP32-CAM Live Vehicle Monitoring
* 🅿️ Intelligent Parking Slot Allocation
* 💳 QR Code Payment System
* 🚪 Automatic Entrance & Exit Gate Control
* 📡 Real-Time Socket.IO Dashboard
* 📊 Live Occupancy Analytics
* 🧠 Custom YOLOv8 Training Support
* 📈 SLA & Performance Monitoring
* 🔒 Transaction-Safe Backend

---

# 🏗️ System Architecture

```text
                ESP32-CAM (Entrance)
                        │
                        ▼
             Flask + Socket.IO Backend
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
   YOLOv8 Model     EasyOCR        SQLite/MySQL
        │               │
        └───────► ANPR Pipeline ◄───────┘
                        │
        ┌───────────────┼───────────────┐
        │                               │
        ▼                               ▼
 NodeMCU + IR Sensors            Admin Dashboard
 Servo Gate Control           (Real-Time Monitoring)
```

---

# 🛠️ Tech Stack

## Backend

* Flask
* Flask-SocketIO
* Flask-SQLAlchemy
* APScheduler
* Gunicorn

## AI & Computer Vision

* Ultralytics YOLOv8
* EasyOCR
* OpenCV
* NumPy

## Frontend

* HTML5
* CSS3
* Vanilla JavaScript
* Socket.IO

## Hardware

* ESP32-CAM
* NodeMCU (ESP8266)
* IR Sensors
* Servo Motor

---

# 📂 Project Structure

```text
SmartParkingSystem/

├── app.py
├── ocr_service.py
├── requirements.txt
├── README.md
├── templates/
├── static/
├── models/
├── scripts/
├── ESP32/
├── NodeMCU/
├── docs/
└── datasets/
```

---

# 🚀 Installation

## Clone Repository

```bash
git clone https://github.com/yourusername/SmartParkingSystem.git

cd SmartParkingSystem
```

## Create Virtual Environment

```bash
python -m venv venv
```

Windows

```bash
venv\Scripts\activate
```

Linux/macOS

```bash
source venv/bin/activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# ⚙️ Configuration

Create:

```text
.env
```

Configure:

* SECRET_KEY
* Database URL
* Server URL
* Wi-Fi credentials (for firmware)

If available, place your trained model at:

```text
models/anpr/best.pt
```

Otherwise the application automatically falls back to the default model.

---

# ▶️ Run Application

```bash
python app.py
```

Backend:

```
http://localhost:5000
```

---

# 📷 ESP32-CAM Setup

1. Open `ESP32/ESP32.ino`
2. Configure Wi-Fi credentials
3. Configure backend URL
4. Flash firmware
5. Restart device

---

# 🔌 NodeMCU Setup

1. Open `NodeMCU/NodeMCU.ino`
2. Configure Wi-Fi credentials
3. Configure backend URL
4. Connect IR sensors
5. Connect Servo
6. Upload firmware

---

# 🔄 Complete Workflow

```
Vehicle Arrives

↓

ESP32-CAM Detects Vehicle

↓

YOLOv8 Detects Plate

↓

EasyOCR Reads Plate

↓

Slot Allocated

↓

QR Payment Generated

↓

Payment Verified

↓

Entrance Gate Opens

↓

Vehicle Parks

↓

Dashboard Updates

↓

Vehicle Exits

↓

ANPR Verification

↓

Duration Calculated

↓

Slot Released

↓

Exit Gate Opens
```

---

# 📊 Dashboard

The Admin Dashboard provides:

* Live Parking Status
* Available Slots
* Occupied Slots
* Revenue Analytics
* Vehicle Logs
* Entrance Monitoring
* Exit Monitoring
* Performance Metrics

---

# 🔮 Future Enhancements

* PostgreSQL Support
* AWS EC2 Deployment
* Docker & Kubernetes
* JWT Authentication
* Multi-Level Parking
* Mobile Application
* Per-Slot Camera Verification

---

# 📄 License

This project is licensed under the **MIT License**.

---

# ⭐ Support

If you found this project useful, please consider giving it a **Star ⭐** on GitHub.
