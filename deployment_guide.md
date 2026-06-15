# Deployment Guide

Follow these instructions to safely deploy the Smart Parking System to a production environment (e.g., AWS EC2, local server, or Raspberry Pi).

## 1. Environment Setup

### Prerequisites
- Python 3.10+
- Git
- OpenCV System Dependencies (`libgl1-mesa-glx`)

### Installation
1. Clone the repository to your host machine.
2. Create an isolated virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Or `venv\Scripts\activate` on Windows
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## 2. Database Initialization
By default, the system uses SQLite for out-of-the-box compatibility. 
For heavy production traffic, it is highly recommended to transition to MySQL.
- To use MySQL, uncomment the `SQLALCHEMY_DATABASE_URI` line in `app.py` and replace with your RDS/MySQL credentials.
- Run `app.py` once to trigger `db.create_all()` and initialize the deterministic slot rows (A1, A2, A3).

## 3. Custom AI Model Configuration
- The system expects your trained Indian ANPR model at `models/anpr/best.pt`.
- If the model is not found, the system will elegantly fallback to standard `yolov8n.pt`. Note that the fallback model is NOT optimized for Indian number plates and will have a significantly higher failure rate.
- Run `python scripts/train_anpr.py` to bake your custom weights using your proprietary dataset.

## 4. Hardware Node Deployment
- **NodeMCU:** Flash `esp8266_smart_parking.ino` via Arduino IDE. Ensure the WiFi credentials match your local intranet router.
- **ESP32-CAM (Entrance/Exit):** Flash `esp32_cam_entrance.ino`. Change the internal `location` variable to either `"entrance"` or `"exit"`.

## 5. Launching the Platform
Start the core orchestrator using a production-ready WSGI server:
```bash
gunicorn -k eventlet -w 1 app:app -b 0.0.0.0:5000
```
*(Note: Because this application heavily relies on background `APScheduler` threads and Socket.IO, it is critical to run with `-w 1` worker to prevent thread duplication, or use a proper Redis message queue if horizontally scaling).*
