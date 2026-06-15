import os
import csv
import json

def main():
    print("Evaluating Model Training Metrics...")
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    results_csv = os.path.join(base_dir, "runs", "detect", "indian_anpr_v1", "results.csv")
    logs_dir = os.path.join(base_dir, "logs")
    out_json = os.path.join(logs_dir, "training_metrics.json")
    
    if not os.path.exists(results_csv):
        print(f"Error: {results_csv} not found. Ensure training has completed.")
        return
        
    os.makedirs(logs_dir, exist_ok=True)
    
    # Read CSV and get last row (final epoch)
    final_metrics = {}
    with open(results_csv, 'r') as f:
        reader = csv.reader(f)
        headers = [h.strip() for h in next(reader)]
        
        last_row = None
        for row in reader:
            if row: last_row = [x.strip() for x in row]
            
        if last_row:
            for idx, col_name in enumerate(headers):
                final_metrics[col_name] = float(last_row[idx])
                
    # Format output
    output_data = {
        "status": "COMPLETED",
        "total_epochs": final_metrics.get("epoch", 0),
        "train_box_loss": final_metrics.get("train/box_loss", 0),
        "val_box_loss": final_metrics.get("val/box_loss", 0),
        "metrics": {
            "mAP50": final_metrics.get("metrics/mAP50(B)", 0),
            "mAP50-95": final_metrics.get("metrics/mAP50-95(B)", 0),
            "precision": final_metrics.get("metrics/precision(B)", 0),
            "recall": final_metrics.get("metrics/recall(B)", 0)
        }
    }
    
    with open(out_json, 'w') as f:
        json.dump(output_data, f, indent=4)
        
    print(f"Training metrics successfully exported to {out_json}")
    for k, v in output_data["metrics"].items():
        print(f"  {k}: {v:.4f}")

if __name__ == "__main__":
    main()
