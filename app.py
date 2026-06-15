import os
from dotenv import load_dotenv
load_dotenv()
import threading
import uuid
import datetime
import time
import qrcode
from io import BytesIO
from flask import Flask, jsonify, request, render_template, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from ocr_service import process_image
import cv2
from PIL import Image
import re
from flask_socketio import SocketIO, emit
from flask_apscheduler import APScheduler
from functools import wraps

from logger import logger, log_sla, log_error

def time_api(operation_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            try:
                response = f(*args, **kwargs)
                return response
            finally:
                duration_ms = int((time.time() - start_time) * 1000)
                log_sla("API", operation_name, duration_ms)
                if duration_ms > 500:
                    logger.warning(f"[API] SLOW REQUEST: {operation_name} took {duration_ms} ms")
        return decorated_function
    return decorator

def db_commit(operation="DB Commit"):
    start_time = time.time()
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log_error("DB Commit Failed", e)
        raise e
    finally:
        duration_ms = int((time.time() - start_time) * 1000)
        log_sla("DB", operation, duration_ms)

def db_rollback():
    start_time = time.time()
    db.session.rollback()
    duration_ms = int((time.time() - start_time) * 1000)
    log_sla("DB", "DB Rollback", duration_ms)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'enterprise-secret-key')

# Initialize SocketIO and APScheduler for real-time and background tasks
socketio = SocketIO(app, cors_allowed_origins="*")

def emit_socket_event(event_name, data=None):
    if data is None:
        data = {}
    data['server_timestamp'] = int(time.time() * 1000)
    socketio.emit(event_name, data)

@app.route('/api/log-latency', methods=['POST'])
def log_latency():
    data = request.json
    event = data.get('event')
    latency = data.get('latency')
    logger.info(f"[Socket.IO] [{event}] Latency: {latency} ms")
    return jsonify({"success": True})

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# Configure Database Connection (Defaulting to SQLite for out-of-the-box running)
# To use MySQL (as requested in the enterprise Tech Stack), uncomment the following line:
# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:password@localhost/smart_parking'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'smart_parking.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Image Upload Configuration
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB Limit
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

db = SQLAlchemy(app)

# Gate Status
entrance_gate_status = "CLOSED"
exit_gate_status = "CLOSED"
trigger_capture = False
last_scan_time = None
last_scan_plate = None
esp32_cam_ip = None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Database Models ---

class ParkingSlot(db.Model):
    __tablename__ = 'parking_slots'
    slot_id = db.Column(db.String(10), primary_key=True)
    status = db.Column(db.String(20), default="Available") # "Available", "Reserved", "Occupied"
    distance_score = db.Column(db.Integer, default=1)
    priority_score = db.Column(db.Integer, default=1)

class VehicleLog(db.Model):
    __tablename__ = 'vehicle_logs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    vehicle_id = db.Column(db.String(50))
    slot_id = db.Column(db.String(10))
    entry_time = db.Column(db.DateTime)
    exit_time = db.Column(db.DateTime, nullable=True)
    image_path = db.Column(db.String(255), nullable=True)
    image_bounded = db.Column(db.String(255), nullable=True)
    image_cropped = db.Column(db.String(255), nullable=True)
    plate_number = db.Column(db.String(50), nullable=True)
    vehicle_type = db.Column(db.String(50), default="Car")
    payment_status = db.Column(db.String(20), default="Pending")
    payment_amount = db.Column(db.Numeric(10, 2), nullable=True)
    status = db.Column(db.String(20), default="ACTIVE") # "ACTIVE", "COMPLETED"
    confidence = db.Column(db.Numeric(5, 4), nullable=True)
    duration = db.Column(db.String(50), nullable=True)
    gate_open_time = db.Column(db.DateTime, nullable=True)
    vehicle_entry_confirmed = db.Column(db.Boolean, default=False)

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    vehicle_id = db.Column(db.String(50))
    slot_id = db.Column(db.String(10), nullable=True)
    amount = db.Column(db.Numeric(10, 2))
    payment_status = db.Column(db.String(20)) # "Pending" or "Paid"
    payment_time = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)

# --- Initialize Database (Run once) ---
def init_db():
    with app.app_context():
        db.create_all()
        if ParkingSlot.query.count() == 0:
            # Initialize with deterministic distances
            db.session.add(ParkingSlot(slot_id="A1", status="Available", distance_score=1, priority_score=100))
            db.session.add(ParkingSlot(slot_id="A2", status="Available", distance_score=2, priority_score=90))
            db.session.add(ParkingSlot(slot_id="A3", status="Available", distance_score=3, priority_score=80))
            db.session.commit()

@scheduler.task('interval', id='log_system_performance', seconds=60)
def log_system_performance():
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        logger.info(f"[PERFORMANCE] CPU: {cpu}% | RAM: {ram}%")
        if ram > 85:
            logger.warning("[PERFORMANCE] High RAM Usage Detected!")
    except ImportError:
        pass

@scheduler.task('interval', id='timeout_reservations', seconds=60)
def timeout_reservations():
    with app.app_context():
        # Find payments pending for more than 5 minutes
        timeout_threshold = datetime.datetime.now() - datetime.timedelta(minutes=5)
        pending_payments = Payment.query.filter(Payment.payment_status == "Pending", Payment.created_at <= timeout_threshold).all()
        
        for payment in pending_payments:
            # Release slot
            if payment.slot_id:
                slot = ParkingSlot.query.get(payment.slot_id)
                if slot and slot.status == "Reserved":
                    slot.status = "Available"
            
            # Cancel payment
            payment.payment_status = "Cancelled"
            
        if pending_payments:
            try:
                db.session.commit()
                broadcast_stats()
                emit_socket_event('reservation_timeout', {"message": "Reservation timed out."})
                print(f"Timed out {len(pending_payments)} reservations.")
            except Exception as e:
                db.session.rollback()
                print("Error timing out reservations:", e)

# Removed Advanced ML Prediction & Background Task as per deterministic priority requirements.
def predict_occupancy(target_hour=17):
    # Fallback for stats endpoint without ML
    slots = ParkingSlot.query.all()
    occupied = sum(1 for s in slots if s.status in ["Occupied", "Reserved"])
    return occupied

def get_dynamic_price():
    # Advanced Surge Pricing based on current occupancy
    slots = ParkingSlot.query.all()
    occupied = sum(1 for s in slots if s.status == "Occupied")
    total = len(slots)
    occupancy_rate = occupied / max(total, 1)
    
    base_price = 20.00
    if occupancy_rate >= 0.8:
        return base_price * 1.5  # 50% surge
    elif occupancy_rate >= 0.6:
        return base_price * 1.2  # 20% surge
    return base_price

def get_stats_data():
    slots = ParkingSlot.query.all()
    total = len(slots)
    occupied = sum(1 for s in slots if s.status == "Occupied")
    available = total - occupied
    slots_dict = {s.slot_id: s.status for s in slots}
    
    today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    today_entries = VehicleLog.query.filter(VehicleLog.entry_time >= today_start).count()
    today_exits = VehicleLog.query.filter(VehicleLog.exit_time >= today_start).count()
    
    today_payments = Payment.query.filter(Payment.payment_time >= today_start, Payment.payment_status == 'Paid').all()
    revenue = sum(p.amount for p in today_payments)
    
    return {
        "total_slots": total,
        "occupied": occupied,
        "available": available,
        "slots": slots_dict,
        "today_entries": today_entries,
        "today_exits": today_exits,
        "revenue_today": float(revenue),
        "predicted_occupancy": f"{predict_occupancy(17)} / 50 Slots"
    }

def broadcast_stats():
    with app.app_context():
        emit_socket_event('stats_update', get_stats_data())

def broadcast_logs():
    with app.app_context():
        logs = VehicleLog.query.order_by(VehicleLog.entry_time.desc()).limit(50).all()
        logs_data = []
        for l in logs:
            logs_data.append({
                "vehicle_id": l.vehicle_id,
                "slot": l.slot_id,
                "plate_number": l.plate_number or "N/A",
                "entry_time": l.entry_time.strftime("%Y-%m-%d %H:%M:%S") if l.entry_time else "-",
                "exit_time": l.exit_time.strftime("%Y-%m-%d %H:%M:%S") if l.exit_time else "-",
                "image_url": url_for('static', filename=l.image_path) if l.image_path else None
            })
        emit_socket_event('logs_update', {"logs": logs_data})

# --- Routes ---

@app.route('/sw.js')
def sw():
    return app.send_static_file('sw.js')

@app.route('/manifest.json')
def manifest():
    return app.send_static_file('manifest.json')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/monitor')
def monitor():
    return render_template('monitor.html')

@app.route('/entrance')
def entrance_kiosk():
    return render_template('entrance.html')

@app.route('/exit')
def exit_display():
    return render_template('exit.html')

@app.route('/api/dashboard-stats', methods=['GET'])
def get_dashboard_stats_endpoint():
    return jsonify(get_stats_data())

@app.route('/api/logs', methods=['GET'])
def get_logs_endpoint():
    logs = VehicleLog.query.order_by(VehicleLog.entry_time.desc()).limit(50).all()
    logs_data = []
    for l in logs:
        logs_data.append({
            "vehicle_id": l.vehicle_id,
            "slot": l.slot_id,
            "plate_number": l.plate_number or "N/A",
            "entry_time": l.entry_time.strftime("%Y-%m-%d %H:%M:%S") if l.entry_time else "-",
            "exit_time": l.exit_time.strftime("%Y-%m-%d %H:%M:%S") if l.exit_time else "-",
            "image_url": url_for('static', filename=l.image_path) if l.image_path else None,
            "payment_status": "Paid" if Payment.query.filter_by(vehicle_id=l.vehicle_id, payment_status="Paid").first() else "Pending",
            "amount": sum(p.amount for p in Payment.query.filter_by(vehicle_id=l.vehicle_id).all()),
            "status": "Completed" if l.exit_time else "In Parking"
        })
    return jsonify({"logs": logs_data})

@app.route('/api/assign-slot', methods=['POST'])
@time_api("Assign Slot")
def assign_slot():
    data = request.json
    vehicle_id = data.get('vehicle_id')
    
    if not vehicle_id:
        return jsonify({"success": False, "message": "Vehicle ID is required."}), 400

    # --- Duplicate Vehicle Check ---
    existing = VehicleLog.query.filter_by(plate_number=vehicle_id, status="ACTIVE").first()
    if existing:
        return jsonify({
            "success": False, 
            "duplicate": True,
            "message": "Vehicle Already Inside Parking",
            "assigned_slot": existing.slot_id,
            "plate_number": vehicle_id
        })

    # --- Intelligent Allocation Engine ---
    # Ignore Reserved and Occupied slots.
    # Choose available slot with highest priority, then shortest distance.
    slot = ParkingSlot.query.filter_by(status="Available") \
        .order_by(ParkingSlot.priority_score.desc(), ParkingSlot.distance_score.asc()).first()
    
    if slot:
        dynamic_fee = get_dynamic_price()
        
        try:
            # Create Pending Payment
            payment = Payment(vehicle_id=vehicle_id, slot_id=slot.slot_id, amount=dynamic_fee, payment_status="Pending")
            db.session.add(payment)
            
            # Reserve the slot to prevent duplicate allocations
            slot.status = "Reserved"
            db_commit("Assign Slot")
        except Exception as e:
            db_rollback()
            return jsonify({"success": False, "message": "Database transaction failed."}), 500
            
        broadcast_stats()
        
        return jsonify({
            "success": True, 
            "assigned_slot": slot.slot_id,
            "payment_id": payment.id,
            "amount": float(dynamic_fee),
            "reason": f"Highest Priority (Score: {slot.priority_score}) & Nearest Distance ({slot.distance_score})",
            "message": f"Assigned Slot: {slot.slot_id} (Dynamic Fee: ₹{dynamic_fee:.2f})"
        })
    else:
        return jsonify({"success": False, "message": "Parking Full. No slots available."}), 400

@app.route('/api/generate-qr/<int:payment_id>')
def generate_qr(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    qr_data = f"PaymentID:{payment.id}|Vehicle:{payment.vehicle_id}|Amount:Rs.{payment.amount}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill='black', back_color='white')
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    return send_file(img_io, mimetype='image/png')

@app.route('/api/process-payment', methods=['POST'])
@time_api("Process Payment")
def process_payment():
    data = request.json
    payment_id = data.get('payment_id')
    
    payment = Payment.query.get(payment_id)
    if not payment:
        return jsonify({"success": False, "message": "Payment not found."}), 404
        
    if payment.payment_status != "Pending":
        return jsonify({"success": False, "message": "Payment already processed or cancelled."}), 400
        
    try:
        payment.payment_status = "Paid"
        payment.payment_time = datetime.datetime.now()
        
        # Pre-create the VehicleLog here so we have a record that payment was made
        new_log = VehicleLog(
            vehicle_id=payment.vehicle_id,
            slot_id=payment.slot_id,
            entry_time=datetime.datetime.now(),
            plate_number=payment.vehicle_id,
            payment_status="Paid",
            payment_amount=payment.amount,
            status="PENDING_ENTRY"
        )
        db.session.add(new_log)
        
        db_commit("Process Payment")
        
        global entrance_gate_status
        if entrance_gate_status == "CLOSED":
            entrance_gate_status = "OPENING"
            emit_socket_event('entrance_gate_update', {"gate_status": entrance_gate_status})
            
        # Emit WebSocket event for instant UI update
        emit_socket_event('payment_success', {"payment_id": payment.id, "vehicle_id": payment.vehicle_id})
        
        broadcast_stats()
        return jsonify({"success": True, "message": "Payment successful."})
    except Exception as e:
        db_rollback()
        log_error("Process Payment", e)
        return jsonify({"success": False, "message": "Payment transaction failed."}), 500

@app.route('/api/open-entrance-gate', methods=['POST'])
def open_entrance_gate():
    global entrance_gate_status
    if entrance_gate_status not in ["OPEN", "OPENING"]:
        entrance_gate_status = "OPENING"
        emit_socket_event('entrance_gate_update', {"gate_status": entrance_gate_status})
        entrance_gate_status = "OPEN"
        emit_socket_event('entrance_gate_update', {"gate_status": entrance_gate_status})
    return jsonify({"success": True, "gate_status": entrance_gate_status})

@app.route('/api/close-entrance-gate', methods=['POST'])
def close_entrance_gate():
    global entrance_gate_status
    if entrance_gate_status not in ["CLOSED", "CLOSING"]:
        entrance_gate_status = "CLOSING"
        emit_socket_event('entrance_gate_update', {"gate_status": entrance_gate_status})
        entrance_gate_status = "CLOSED"
        emit_socket_event('entrance_gate_update', {"gate_status": entrance_gate_status})
    return jsonify({"success": True, "gate_status": entrance_gate_status})

@app.route('/api/open-exit-gate', methods=['POST'])
def open_exit_gate():
    global exit_gate_status
    if exit_gate_status not in ["OPEN", "OPENING"]:
        exit_gate_status = "OPENING"
        emit_socket_event('exit_gate_update', {"gate_status": exit_gate_status})
        exit_gate_status = "OPEN"
        emit_socket_event('exit_gate_update', {"gate_status": exit_gate_status})
    return jsonify({"success": True, "gate_status": exit_gate_status})

@app.route('/api/close-exit-gate', methods=['POST'])
def close_exit_gate():
    global exit_gate_status
    if exit_gate_status not in ["CLOSED", "CLOSING"]:
        exit_gate_status = "CLOSING"
        emit_socket_event('exit_gate_update', {"gate_status": exit_gate_status})
        exit_gate_status = "CLOSED"
        emit_socket_event('exit_gate_update', {"gate_status": exit_gate_status})
    return jsonify({"success": True, "gate_status": exit_gate_status})

@app.route('/api/gate-status', methods=['GET'])
def get_gate_status():
    global entrance_gate_status
    global exit_gate_status
    return jsonify({
        "entrance_gate_status": entrance_gate_status,
        "exit_gate_status": exit_gate_status
    })

@app.route('/api/scan-plate', methods=['POST'])
@time_api("Scan Plate")
def scan_plate():
    if 'vehicle_image' not in request.files:
        return jsonify({"success": False, "message": "No image provided."}), 400
        
    file = request.files['vehicle_image']
    if file and file.filename and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"scan_{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # Delegate entirely to the new AI-powered ANPR modular service
            plate, conf, crop_path, bound_path, v_type, source = process_image(filepath, app.config['UPLOAD_FOLDER'])
            
            return jsonify({
                "success": True, 
                "plate_number": plate,
                "confidence": f"{conf*100:.1f}%",
                "bounded_image": bound_path,
                "cropped_image": crop_path,
                "vehicle_type": v_type,
                "source": source,
                "original_image": f"uploads/{filename}"
            })
            
        except Exception as e:
            print("OCR Service Integration Error:", e)
            return jsonify({"success": True, "plate_number": "NO_PLATE_FOUND"})
    
    return jsonify({"success": False, "message": "Invalid file type."}), 400

@app.route('/api/vehicle-entry', methods=['POST'])
@time_api("Vehicle Entry")
def vehicle_entry():
    vehicle_id = request.form.get('vehicle_id') or (request.json and request.json.get('vehicle_id'))
    
    if not vehicle_id:
        # If hardware just trips IR sensor, we might not have ID from request.
        # But assuming the hardware passes the ID, or we just look up the currently PENDING_ENTRY log.
        pending_log = VehicleLog.query.filter_by(status="PENDING_ENTRY").order_by(VehicleLog.id.desc()).first()
        if not pending_log:
            return jsonify({"success": False, "message": "No pending vehicle entry."}), 400
        vehicle_id = pending_log.vehicle_id
        
    try:
        log = VehicleLog.query.filter_by(vehicle_id=vehicle_id, status="PENDING_ENTRY").order_by(VehicleLog.id.desc()).first()
        if not log:
            return jsonify({"success": False, "message": "Valid payment not found for entry."}), 403

        slot = ParkingSlot.query.get(log.slot_id)
        if slot and slot.status == "Reserved":
            slot.status = "Occupied"
            
        log.status = "ACTIVE"
        log.gate_open_time = datetime.datetime.now()
        log.vehicle_entry_confirmed = True
        
        # Set optional image data if available
        if request.form.get('original_image'): log.image_path = request.form.get('original_image')
        if request.form.get('bounded_image'): log.image_bounded = request.form.get('bounded_image')
        if request.form.get('cropped_image'): log.image_cropped = request.form.get('cropped_image')
        if request.form.get('confidence'): log.confidence = request.form.get('confidence')
        if request.form.get('vehicle_type'): log.vehicle_type = request.form.get('vehicle_type')

        db_commit("Vehicle Entry")
        
        # Close gate after entry
        global entrance_gate_status
        if entrance_gate_status == "OPEN" or entrance_gate_status == "OPENING":
            entrance_gate_status = "CLOSING"
            emit_socket_event('entrance_gate_update', {"gate_status": entrance_gate_status})
            entrance_gate_status = "CLOSED"
            emit_socket_event('entrance_gate_update', {"gate_status": entrance_gate_status})
        
        broadcast_stats()
        broadcast_logs()
        
        return jsonify({"success": True})
    except Exception as e:
        db_rollback()
        log_error("Vehicle Entry", e)
        return jsonify({"success": False, "message": "Database transaction failed."}), 500

@app.route('/api/camera/register', methods=['POST'])
def camera_register():
    global esp32_cam_ip
    data = request.json
    if data and data.get('ip'):
        esp32_cam_ip = data.get('ip')
        print(f"ESP32-CAM Registered with IP: {esp32_cam_ip}")
        return jsonify({"success": True, "message": "Camera registered successfully."})
    return jsonify({"success": False, "message": "IP address missing."}), 400

@app.route('/api/camera/info', methods=['GET'])
def camera_info():
    global esp32_cam_ip
    if esp32_cam_ip:
        return jsonify({
            "online": True,
            "ip": esp32_cam_ip,
            "stream_url": f"http://{esp32_cam_ip}:81/stream"
        })
    else:
        return jsonify({
            "online": False,
            "ip": None,
            "stream_url": None
        })

def process_camera_upload_async(filepath, full_path, filename, location, upload_folder):
    try:
        plate, conf, crop_path, bound_path, v_type, source = process_image(filepath, upload_folder)
        
        global last_scan_time, last_scan_plate
        now = datetime.datetime.now()
        is_duplicate = False
        
        if last_scan_time and (now - last_scan_time).total_seconds() < 10 and last_scan_plate == plate:
            is_duplicate = True
            print(f"Duplicate scan detected for {plate}. Ignoring.")
        else:
            last_scan_plate = plate
            last_scan_time = now
        
        image_url = f"/static/{bound_path}" if bound_path else f"/static/uploads/{filename}"
        
        result_data = {
            "success": True, 
            "is_duplicate": is_duplicate,
            "plate_number": plate,
            "confidence": round(float(conf), 2) if conf else 0.0,
            "confidence_str": f"{conf*100:.1f}%" if conf else "0.0%",
            "bounded_image": bound_path,
            "cropped_image": crop_path,
            "vehicle_type": v_type,
            "source": "ESP32-CAM",
            "original_image": f"uploads/{filename}",
            "image_url": image_url,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        if os.path.exists(full_path):
            emit_socket_event(f'camera_ocr_result_{location}', result_data)
        
    except Exception as e:
        print("OCR Service Integration Error (ESP32):", e)
        image_url = f"/static/uploads/{filename}"
        result_data = {
            "success": False,
            "is_duplicate": False,
            "plate_number": "NO_PLATE_FOUND",
            "confidence": 0.0,
            "confidence_str": "0%",
            "bounded_image": None,
            "cropped_image": None,
            "vehicle_type": "Unknown",
            "source": "ESP32-CAM",
            "original_image": f"uploads/{filename}",
            "image_url": image_url,
            "timestamp": datetime.datetime.now().isoformat()
        }
        if os.path.exists(full_path):
            emit_socket_event(f'camera_ocr_result_{location}', result_data)

@app.route('/api/camera/upload', methods=['POST'])
@time_api("Camera Upload")
def camera_upload():
    if 'vehicle_image' not in request.files:
        return jsonify({"success": False, "message": "No image provided."}), 400
        
    location = request.form.get('location', 'entrance')
        
    file = request.files['vehicle_image']
    if file and file.filename and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"esp32_{location}_{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        full_path = os.path.abspath(filepath)
        
        emit_socket_event('camera_upload_complete', {"location": location})
        
        threading.Thread(target=process_camera_upload_async, args=(filepath, full_path, filename, location, app.config['UPLOAD_FOLDER'])).start()
        
        return jsonify({"success": True, "message": "Processing in background."})
    
    return jsonify({"success": False, "message": "Invalid file format."}), 400

@app.route('/api/vehicle-exit', methods=['POST'])
@time_api("Vehicle Exit")
def vehicle_exit():
    vehicle_id = request.form.get('vehicle_id') or (request.json and request.json.get('vehicle_id'))
    
    if not vehicle_id or vehicle_id == "NO_PLATE_FOUND":
        return jsonify({"success": False, "message": "OCR Failed. Please Retake Scan"}), 400
        
    try:
        # Find the most recent log for this vehicle
        log = VehicleLog.query.filter_by(vehicle_id=vehicle_id).order_by(VehicleLog.id.desc()).first()
        
        if not log:
            return jsonify({"success": False, "message": "Vehicle Not Found. Please Contact Administrator"}), 404
            
        if log.status == "COMPLETED":
            return jsonify({"success": False, "message": "Vehicle Already Exited"}), 400
            
        if log.status != "ACTIVE":
            return jsonify({"success": False, "message": "Vehicle parking session is not active."}), 400
            
        log.exit_time = datetime.datetime.now()
        
        # Calculate duration
        duration_td = log.exit_time - log.entry_time
        duration_str = str(duration_td).split('.')[0]
        log.duration = duration_str
        
        # Update optional exit image path
        exit_image = request.form.get('original_image') or (request.json and request.json.get('original_image'))
        if exit_image:
            log.exit_image_path = exit_image
            
        # Release the slot
        slot = ParkingSlot.query.get(log.slot_id)
        if slot:
            slot.status = "Available"
            
        db_commit("Vehicle Exit")
        
        global exit_gate_status
        if exit_gate_status in ["CLOSED", "CLOSING"]:
            exit_gate_status = "OPENING"
            emit_socket_event('exit_gate_update', {"gate_status": exit_gate_status})
        
        # Broadcast success event to UI
        emit_socket_event('exit_success', {
            "vehicle_id": vehicle_id,
            "duration": duration_str,
            "entry_time": log.entry_time.strftime("%Y-%m-%d %H:%M:%S")
        })
        
        broadcast_stats()
        broadcast_logs()
        
        return jsonify({
            "success": True, 
            "duration": duration_str, 
            "entry_time": log.entry_time.strftime("%Y-%m-%d %H:%M:%S")
        })
    except Exception as e:
        db_rollback()
        log_error("Vehicle Exit", e)
        return jsonify({"success": False, "message": "Database transaction failed."}), 500

@app.route('/api/exit-gate-crossed', methods=['POST'])
def exit_gate_crossed():
    global exit_gate_status
    if exit_gate_status in ["OPEN", "OPENING"]:
        exit_gate_status = "CLOSING"
        emit_socket_event('exit_gate_update', {"gate_status": exit_gate_status})
        exit_gate_status = "CLOSED"
        emit_socket_event('exit_gate_update', {"gate_status": exit_gate_status})
        
    try:
        # Find the most recently completed log to mark the gate close time
        log = VehicleLog.query.filter_by(status="COMPLETED").order_by(VehicleLog.id.desc()).first()
        if log and not log.gate_close_time:
            log.gate_close_time = datetime.datetime.now()
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Exit Gate Close Update Error:", e)
        
    return jsonify({"success": True})

@app.route('/api/logs', methods=['GET'])
def get_logs():
    logs = VehicleLog.query.order_by(VehicleLog.entry_time.desc()).limit(50).all()
    logs_data = []
    for l in logs:
        # Get payment amount if exists
        payment = Payment.query.filter_by(vehicle_id=l.plate_number, payment_status="Paid").first()
        amount = payment.amount if payment else 0.0
        
        logs_data.append({
            "vehicle_id": l.vehicle_id,
            "slot": l.slot_id,
            "plate_number": l.plate_number or "N/A",
            "vehicle_type": l.vehicle_type or "Car",
            "entry_time": l.entry_time.strftime("%Y-%m-%d %H:%M:%S") if l.entry_time else "-",
            "exit_time": l.exit_time.strftime("%Y-%m-%d %H:%M:%S") if l.exit_time else "-",
            "payment_status": "Paid" if l.exit_time else l.payment_status,
            "amount": amount,
            "image_url": url_for('static', filename=l.image_path) if l.image_path else None
        })
    return jsonify({"logs": logs_data})

@app.route('/api/hardware/update-slot', methods=['POST'])
def hardware_update_slot():
    data = request.json
    slot_id = data.get('slot_id')
    status = data.get('status')
    
    if not slot_id or not status:
         return jsonify({"success": False, "message": "Missing parameters."}), 400
         
    slot = ParkingSlot.query.get(slot_id)
    if slot:
         slot.status = status
         db.session.commit()
         broadcast_stats()
         return jsonify({"success": True})
    return jsonify({"success": False, "message": "Slot not found."}), 404

# --- Hardware Simulation Endpoints (For Presentation) ---

@app.route('/api/demo/arrive', methods=['POST'])
def demo_arrive():
    emit_socket_event('camera_motion_detected')
    return jsonify({"success": True})

@app.route('/api/demo/capture', methods=['POST'])
def demo_capture():
    emit_socket_event('camera_capture_started')
    return jsonify({"success": True})

@app.route('/api/demo/ocr', methods=['POST'])
def demo_ocr():
    emit_socket_event('camera_upload_complete', {"location": "entrance"})
    time.sleep(1)
    # emit success
    result_data = {
        "success": True, 
        "is_duplicate": False,
        "plate_number": "DEMO1234",
        "confidence": 0.99,
        "confidence_str": "99.0%",
        "bounded_image": None,
        "cropped_image": None,
        "vehicle_type": "Car",
        "source": "DEMO",
        "original_image": None,
        "image_url": None,
        "timestamp": datetime.datetime.now().isoformat()
    }
    emit_socket_event('camera_ocr_result_entrance', result_data)
    return jsonify({"success": True})

@app.route('/api/camera/motion-detected', methods=['POST'])
def motion_detected():
    emit_socket_event('camera_motion_detected')
    return jsonify({"success": True})

@app.route('/api/camera/capture-started', methods=['POST'])
def capture_started():
    emit_socket_event('camera_capture_started')
    return jsonify({"success": True})

@app.route('/api/camera/status', methods=['GET'])
def camera_status():
    global trigger_capture
    should_capture = trigger_capture
    if trigger_capture:
        trigger_capture = False
    return jsonify({"trigger_capture": should_capture, "status": "active"})

@app.route('/api/camera/request-capture', methods=['POST'])
def request_capture():
    global trigger_capture
    trigger_capture = True
    return jsonify({"success": True, "message": "Capture requested"})

@app.route('/api/simulate/camera', methods=['POST'])
def sim_camera():
    data = request.json or {}
    status = data.get('status', 'success')
    if status == 'success':
        import random
        plate = f"TN09AB{random.randint(1000,9999)}"
        emit_socket_event('camera_ocr_result', {"success": True, "plate_number": plate})
    else:
        emit_socket_event('camera_ocr_result', {"success": False, "message": "Image too blurry. Could not read plate."})
    return jsonify({"success": True})

# --- Socket.IO Events ---
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    init_db()
    print("\n" + "="*55)
    print("🚀 SMART PARKING SYSTEM IS LIVE! 🚀")
    print("="*55)
    print("Click the links below (Ctrl+Click) to open the interfaces:")
    print("👉 Admin Dashboard : http://127.0.0.1:5000/admin")
    print("👉 Entrance Kiosk  : http://127.0.0.1:5000/entrance")
    print("👉 Exit Kiosk      : http://127.0.0.1:5000/exit")
    print("="*55 + "\n")
    
    socketio.run(app, host='0.0.0.0', debug=True, port=5000, use_reloader=False) # disabled reloader for apscheduler compatibility
