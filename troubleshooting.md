# Troubleshooting Guide

This guide covers common edge-cases, hardware failures, and exception states you may encounter while operating the Smart Parking System.

## 1. OCR Failures (`NO_PLATE_FOUND`)
**Symptom:** The vehicle approaches the kiosk, but the AI returns `NO_PLATE_FOUND`.
**Cause:**
- The plate is extremely dirty, severely bent, or non-standard.
- The `yolov8n.pt` fallback model is being used instead of the custom `best.pt`.
- Lighting conditions (e.g. intense glare) washed out the ESP32-CAM frame.
**Resolution:**
- The UI will flash "Retrying" and safely prompt the driver to adjust their vehicle. The backend fails safely and will not lock up database resources. Ensure the Entrance is well-lit and the custom ANPR model is properly trained and located at `models/anpr/best.pt`.

## 2. Duplicate Entry Rejection
**Symptom:** A driver pays, but the Kiosk flashes `"Vehicle Already Inside Parking"`.
**Cause:**
- A vehicle with the identical license plate is currently marked `ACTIVE` in the system.
**Resolution:**
- The system rigidly enforces 1:1 plate-to-slot mapping. Either the driver physically cloned a plate, or the previous parking session was never properly closed. The Admin must manually resolve the `ACTIVE` record in the database.

## 3. Ghost Reservations (Slot Stuck as `RESERVED`)
**Symptom:** The Dashboard shows a slot is `RESERVED` for over an hour.
**Cause:**
- A driver scanned their plate, received an allocation, but drove away without scanning the payment QR, and the background cleanup job failed.
**Resolution:**
- The `APScheduler` job `timeout_reservations` automatically purges unpaid reservations after 5 minutes. If it fails, ensure `scheduler.start()` is actively running in `app.py` and you are only running a single WSGI worker thread.

## 4. Hardware Desync (Gate Doesn't Open)
**Symptom:** Payment is successful, but the barrier gate physically remains closed.
**Cause:**
- The NodeMCU has lost WiFi connectivity or the Flask server IP changed.
**Resolution:**
- The backend `entrance_gate_status` safely remains at `OPENING`. Check the NodeMCU serial monitor. Ensure the Flask server IP hardcoded into `esp8266_smart_parking.ino` matches the active server IP.

## 5. UI Fails to Update (Dashboard is Frozen)
**Symptom:** A car enters, but the Dashboard slot map doesn't update unless manually refreshed.
**Cause:**
- The Socket.IO connection dropped, or there is a frontend memory leak caused by duplicate listeners.
**Resolution:**
- Check the browser console. If you see WebSocket disconnects, ensure your network allows ws:// traffic. The system has been audited to prevent duplicate `socket.on` listeners, so a hard refresh of the browser will instantly pull the latest state from the REST API.
