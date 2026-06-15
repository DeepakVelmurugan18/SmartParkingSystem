import os
import json
import difflib
import sys

# Add root directory to sys.path so we can import ocr_service
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import ocr_service

def calculate_char_accuracy(truth, pred):
    if not truth or not pred: return 0.0
    matcher = difflib.SequenceMatcher(None, truth, pred)
    return matcher.ratio() * 100.0

def main():
    print("OCR Pipeline Evaluation")
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    test_dir = os.path.join(base_dir, "datasets", "indian_plates", "images", "test")
    logs_dir = os.path.join(base_dir, "logs")
    out_json = os.path.join(logs_dir, "ocr_evaluation.json")
    
    if not os.path.exists(test_dir):
        print(f"Error: {test_dir} not found.")
        return
        
    os.makedirs(logs_dir, exist_ok=True)
    test_images = [f for f in os.listdir(test_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]
    
    if not test_images:
        print("No test images found.")
        return
        
    print(f"Evaluating OCR accuracy on {len(test_images)} images...")
    
    results = {
        "total_evaluated": 0,
        "full_plate_matches": 0,
        "average_char_accuracy": 0.0,
        "average_ocr_confidence": 0.0,
        "details": []
    }
    
    total_char_acc = 0.0
    total_conf = 0.0
    
    # In a real production scenario, we need a mapping of filename -> Ground Truth string.
    # Since the Kaggle dataset doesn't provide OCR ground truths, we will extract it from
    # the filename if possible, or use a placeholder to demonstrate the pipeline.
    
    for img_file in test_images:
        filepath = os.path.join(test_dir, img_file)
        
        # Ground Truth Extraction Logic (Placeholder since Kaggle dataset lacks it)
        # Assuming the plate might be in the filename or we just mock it for pipeline validation
        ground_truth = "TN09AB1234" # Dummy GT for demonstration of the script
        
        # Run OCR Service
        # We pass logs_dir as save_dir to avoid cluttering uploads
        plate, conf, crop, bound, v_type, source = ocr_service.process_image(filepath, logs_dir)
        
        if plate == "NO_PLATE_FOUND":
            plate = ""
            conf = 0.0
            
        char_acc = calculate_char_accuracy(ground_truth, plate)
        is_full_match = (char_acc == 100.0)
        
        if is_full_match:
            results["full_plate_matches"] += 1
            
        total_char_acc += char_acc
        total_conf += conf
        results["total_evaluated"] += 1
        
        results["details"].append({
            "image": img_file,
            "ground_truth": ground_truth,
            "predicted": plate,
            "confidence": conf,
            "char_accuracy": char_acc
        })
        
        print(f"Image: {img_file} | GT: {ground_truth} | Pred: {plate} | Conf: {conf:.2f}")

    if results["total_evaluated"] > 0:
        results["average_char_accuracy"] = total_char_acc / results["total_evaluated"]
        results["average_ocr_confidence"] = total_conf / results["total_evaluated"]
        results["full_plate_accuracy"] = (results["full_plate_matches"] / results["total_evaluated"]) * 100
        
    with open(out_json, 'w') as f:
        json.dump(results, f, indent=4)
        
    print(f"\nOCR Evaluation saved to {out_json}")
    print(f"Average Char Accuracy: {results['average_char_accuracy']:.2f}%")
    print(f"Full Plate Accuracy:   {results.get('full_plate_accuracy', 0.0):.2f}%")
    print(f"Average Confidence:    {results['average_ocr_confidence']:.2f}")

if __name__ == "__main__":
    main()
