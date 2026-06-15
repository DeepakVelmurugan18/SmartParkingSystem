import cv2
import re
import numpy as np
import os
from ultralytics import YOLO
import easyocr
import time
from logger import logger, log_ai_metrics, log_sla

# The custom weights should be here after training
MODEL_PATH = 'models/anpr/best.pt'
FALLBACK_PATH = 'yolov8n.pt'

YOLO_CONF_THRESHOLD = 0.25
OCR_CONF_THRESHOLD = 0.30

if not os.path.exists(MODEL_PATH):
    print(f"\n[WARNING] Custom model not found at '{MODEL_PATH}'.")
    print("Please run `python scripts/train_anpr.py` to train your Indian ANPR model.")
    print("Falling back to standard YOLOv8n, which is NOT optimal for number plates!\n")
    yolo_plate_model = YOLO(FALLBACK_PATH)
    source_model = "Fallback YOLOv8n"
else:
    yolo_plate_model = YOLO(MODEL_PATH)
    source_model = "Custom Indian ANPR"
    
print(f"YOLO model loaded: {source_model}")

yolo_vehicle_model = YOLO('yolov8n.pt')
reader = easyocr.Reader(['en'])

def extract_indian_plate(text):
    """
    Strict Regex for Indian number plates:
    Must match valid Indian formats (e.g., TN09AB1234, KA01AA0001, MH12XY4567, KL07BC9876)
    ^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$
    """
    cleaned_text = re.sub(r'[^A-Z0-9]', '', text.upper())
    
    # Try exact match first
    match = re.search(r'^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$', cleaned_text)
    if match:
        return match.group(0)
    
    # Try finding inside text
    plates = re.findall(r'[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}', cleaned_text)
    if plates:
        return plates[0]
    return None

def apply_filters(img, step):
    """
    Step 1: Original crop
    Step 2: CLAHE + Bilateral Filter
    Step 3: Histogram Equalization + Resize ×2 + Sharpen
    Step 4: Adaptive Threshold
    """
    if step == 1:
        return img
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if step == 2:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        return cv2.bilateralFilter(enhanced, 11, 17, 17)
        
    if step == 3:
        eq = cv2.equalizeHist(gray)
        resized = cv2.resize(eq, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        # Sharpening kernel
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        return cv2.filter2D(resized, -1, kernel)
        
    if step == 4:
        # We use a slight blur before adaptive thresholding to reduce noise
        blurred = cv2.GaussianBlur(gray, (5,5), 0)
        return cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        
    return img

def process_image(filepath, save_dir):
    try:
        img = cv2.imread(filepath)
        if img is None:
            return "NO_PLATE_FOUND", 0.0, None, None, "Unknown", "Error"

        # 1. Detect Vehicle Type
        veh_results = yolo_vehicle_model(img, classes=[2, 3, 5, 7], verbose=False)
        vehicle_type = "Car"
        if len(veh_results) > 0 and len(veh_results[0].boxes) > 0:
            cls_id = int(veh_results[0].boxes.cls[0].item())
            if cls_id == 2: vehicle_type = "Car"
            elif cls_id == 3: vehicle_type = "Bike"
            elif cls_id == 5: vehicle_type = "Bus"
            elif cls_id == 7: vehicle_type = "Truck"

        # 2. Detect Plate
        t0_yolo = time.time()
        plate_results = yolo_plate_model(img, verbose=False)
        yolo_time_ms = int((time.time() - t0_yolo) * 1000)
        log_sla("ANPR", "YOLO Detection", yolo_time_ms)
        
        plate_img = None
        box_coords = None
        
        num_detections = len(plate_results[0].boxes) if len(plate_results) > 0 else 0
        
        if num_detections > 0:
            boxes = plate_results[0].boxes.xyxy.cpu().numpy()
            confidences = plate_results[0].boxes.conf.cpu().numpy()
            
            best_idx = np.argmax(confidences)
            best_det_conf = confidences[best_idx]
            
            logger.info(f"YOLO Plate Detection Confidence: {best_det_conf:.4f}")
            
            if best_det_conf >= YOLO_CONF_THRESHOLD:
                x1, y1, x2, y2 = map(int, boxes[best_idx])
                
                pad = 5
                x1 = max(0, x1 - pad)
                y1 = max(0, y1 - pad)
                x2 = min(img.shape[1], x2 + pad)
                y2 = min(img.shape[0], y2 + pad)
                
                plate_img = img[y1:y2, x1:x2]
                box_coords = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
                source = f"{source_model} + PaddleOCR"
            else:
                logger.info(f"YOLO Confidence ({best_det_conf:.4f}) below threshold ({YOLO_CONF_THRESHOLD}). Falling back to full image OCR.")
                plate_img = img
                box_coords = [[0, 0], [img.shape[1], 0], [img.shape[1], img.shape[0]], [0, img.shape[0]]]
                source = "Full Image + EasyOCR"
        else:
            logger.info("No plate detected by YOLO. Falling back to full image OCR.")
            best_det_conf = 0.0
            plate_img = img
            box_coords = [[0, 0], [img.shape[1], 0], [img.shape[1], img.shape[0]], [0, img.shape[0]]]
            source = "Full Image + EasyOCR"

        # 3. Cascading OCR Fallback Pipeline
        best_overall_plate = None
        best_overall_conf = 0.0
        
        debug_dir = os.path.join(save_dir, "debug")
        os.makedirs(debug_dir, exist_ok=True)
        
        for step in range(1, 5):
            processed_img = apply_filters(plate_img, step)
            cv2.imwrite(os.path.join(debug_dir, f"step_{step}.jpg"), processed_img)
            
            t0_ocr = time.time()
            ocr_result = reader.readtext(processed_img)
            ocr_time_ms = int((time.time() - t0_ocr) * 1000)
            
            step_best_plate = None
            step_best_conf = 0.0
            
            if ocr_result:
                for line in ocr_result:
                    bbox, text, conf = line
                    logger.debug(f"[Step {step}] EasyOCR Raw: '{text}' | Conf: {conf:.4f}")
                    plate = extract_indian_plate(text)
                    logger.debug(f"[Step {step}] Regex output for '{text}': {plate}")
                    if plate:
                        if conf > step_best_conf:
                            step_best_plate = plate
                            step_best_conf = conf
            
            if step_best_plate:
                logger.debug(f"[Step {step}] Regex Validated: '{step_best_plate}' with Conf: {step_best_conf:.4f}")
                if step_best_conf > best_overall_conf:
                    best_overall_plate = step_best_plate
                    best_overall_conf = step_best_conf
                    
                if best_overall_conf >= OCR_CONF_THRESHOLD:
                    logger.info(f"[Step {step}] Success! Reached threshold ({OCR_CONF_THRESHOLD}). Exiting cascade.")
                    log_sla("ANPR", f"EasyOCR Step {step}", ocr_time_ms)
                    break
            else:
                logger.debug(f"[Step {step}] No valid Indian plate format found.")

        # 4. Result Validation
        if best_overall_plate and best_overall_conf >= OCR_CONF_THRESHOLD:
            log_ai_metrics(yolo_time_ms, best_det_conf, ocr_time_ms, best_overall_conf, best_overall_plate)
            bounded_img = img.copy()
            box_points = np.array(box_coords, dtype=np.int32)
            x1, y1 = int(box_points[0][0]), int(box_points[0][1])
                
            cv2.polylines(bounded_img, [box_points], isClosed=True, color=(0, 255, 0), thickness=3)
            conf_text = f"{best_overall_plate} ({best_overall_conf*100:.1f}%)"
            cv2.putText(bounded_img, conf_text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            
            base_name = os.path.basename(filepath).split('.')[0]
            cropped_filename = f"{base_name}_cropped.jpg"
            bounded_filename = f"{base_name}_bounded.jpg"
            
            if plate_img.size > 0:
                cv2.imwrite(os.path.join(save_dir, cropped_filename), plate_img)
            cv2.imwrite(os.path.join(save_dir, bounded_filename), bounded_img)
            
            print(f"Final Output: {best_overall_plate} with {best_overall_conf:.4f} confidence.")
            return best_overall_plate, float(best_overall_conf), f"uploads/{cropped_filename}", f"uploads/{bounded_filename}", vehicle_type, source
            
        print(f"OCR Pipeline Exhausted: Best confidence {best_overall_conf:.4f} failed to reach threshold {OCR_CONF_THRESHOLD}.")
        return "NO_PLATE_FOUND", 0.0, None, None, vehicle_type, source
        
    except Exception as e:
        print(f"[OCR SERVICE ERROR]: {e}")
        return "NO_PLATE_FOUND", 0.0, None, None, "Unknown", "Error"
