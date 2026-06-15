import os
import cv2
import json
from ultralytics import YOLO

def main():
    print("ANPR Model Validation Script")
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    model_path = os.path.join(base_dir, "models", "anpr", "best.pt")
    test_dir = os.path.join(base_dir, "datasets", "indian_plates", "images", "test")
    output_dir = os.path.join(base_dir, "runs", "detect", "test_results")
    logs_dir = os.path.join(base_dir, "logs")
    out_json = os.path.join(logs_dir, "validation_summary.json")
    
    if not os.path.exists(model_path):
        print(f"Error: Model not found at {model_path}")
        return
        
    if not os.path.exists(test_dir):
        print(f"Error: Test dataset not found at {test_dir}")
        return
        
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)
    
    print(f"Loading custom model from {model_path}...")
    model = YOLO(model_path)
    
    test_images = [f for f in os.listdir(test_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]
    
    if not test_images:
        print("No test images found in the test directory.")
        return
        
    print(f"Running inference on {len(test_images)} test images...")
    
    summary = {
        "total_images": len(test_images),
        "correct_detections": 0,
        "missed_detections": 0,
        "false_positives": 0, # Since we assume 1 plate per image
        "detection_accuracy": 0.0
    }
    
    for img_file in test_images:
        img_path = os.path.join(test_dir, img_file)
        results = model(img_path, verbose=False)
        
        detections = len(results[0].boxes) if len(results) > 0 else 0
        
        if detections == 1:
            summary["correct_detections"] += 1
        elif detections == 0:
            summary["missed_detections"] += 1
        else:
            summary["correct_detections"] += 1
            summary["false_positives"] += (detections - 1)
        
        for idx, result in enumerate(results):
            annotated_frame = result.plot()
            out_path = os.path.join(output_dir, f"result_{img_file}")
            cv2.imwrite(out_path, annotated_frame)
            
    summary["detection_accuracy"] = (summary["correct_detections"] / summary["total_images"]) * 100
    
    with open(out_json, 'w') as f:
        json.dump(summary, f, indent=4)
        
    print(f"\nValidation complete! All visual results saved in {output_dir}")
    print(f"Validation summary saved to {out_json}")
    for k, v in summary.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.2f}%")
        else:
            print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
