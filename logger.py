import logging
import time

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(name)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler("smart_parking.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("SmartParking")

def log_sla(module, operation, execution_time_ms):
    logger.info(f"[{module}] [{operation}] [{execution_time_ms} ms]")

def log_ai_metrics(yolo_time, yolo_conf, ocr_time, ocr_conf, plate):
    msg = f"\nYOLO:\n{yolo_time} ms\nConfidence:\n{yolo_conf:.2f}\nOCR:\n{ocr_time} ms\nConfidence:\n{ocr_conf:.2f}\nPlate:\n{plate}"
    logger.info(msg)

def log_error(operation, exception):
    logger.error(f"[{operation}] Error: {str(exception)}", exc_info=True)
