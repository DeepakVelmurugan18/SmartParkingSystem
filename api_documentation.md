# Smart Parking API Documentation

## 1. REST Endpoints

### Hardware & Sensor APIs
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/camera/register` | `POST` | ESP32-CAM calls this on boot to register its IP address with the backend. |
| `/api/camera/upload` | `POST` | Receives raw JPEG frames from the ESP32-CAM and pipes them into the AI pipeline. |
| `/api/vehicle-entry` | `POST` | Triggered by the Entrance IR Sensor to confirm the vehicle passed the barrier. |
| `/api/exit-gate-crossed` | `POST` | Triggered by the Exit IR Sensor to confirm vehicle departure and trigger gate closure. |

### Core Workflow APIs
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/scan-plate` | `POST` | Manually processes an uploaded image through YOLO+PaddleOCR. Returns JSON with confidence and bounding boxes. |
| `/api/assign-slot` | `POST` | Uses deterministic priority/distance logic to allocate a slot. Creates a pending Payment. |
| `/api/process-payment` | `POST` | Validates a payment ID, opens the entrance gate, and sets the DB log to `PENDING_ENTRY`. |
| `/api/vehicle-exit` | `POST` | Finds `ACTIVE` log, calculates duration, releases slot, and opens the exit gate. |

### Gate Control APIs
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/open-entrance-gate` | `POST` | Transitions `entrance_gate_status` to `OPENING`. |
| `/api/close-entrance-gate` | `POST` | Transitions `entrance_gate_status` to `CLOSING`. |
| `/api/open-exit-gate` | `POST` | Transitions `exit_gate_status` to `OPENING`. |
| `/api/close-exit-gate` | `POST` | Transitions `exit_gate_status` to `CLOSING`. |

## 2. WebSocket Events (Socket.IO)

The system relies heavily on WebSockets to push UI updates instantly, bypassing the need for frontend polling.

| Event | Direction | Payload Example |
| :--- | :--- | :--- |
| `payment_success` | Backend → UI | `{"payment_id": 5, "vehicle_id": "TN09A1234"}` |
| `entrance_gate_update` | Backend → UI | `{"gate_status": "OPENING"}` |
| `exit_gate_update` | Backend → UI | `{"gate_status": "OPENING"}` |
| `camera_ocr_result_entrance` | Backend → UI | `{"plate_number": "TN09...", "confidence": "94.5%"}` |
| `exit_success` | Backend → UI | `{"duration": "0:45:12", "entry_time": "..."}` |
| `reservation_timeout` | Backend → UI | `{"message": "Reservation timed out"}` |
