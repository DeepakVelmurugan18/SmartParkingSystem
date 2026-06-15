import os
import shutil
from ultralytics import YOLO

def main():
    print("Loading YOLOv8 base model...")
    model = YOLO("yolov8n.pt")
    
    dataset_yaml = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "datasets", "indian_plates", "dataset.yaml"))
    
    if not os.path.exists(dataset_yaml):
        print(f"Error: Dataset configuration file not found at {dataset_yaml}")
        return

    print("Starting training process for custom ANPR model...")
    results = model.train(
        data=dataset_yaml,
        epochs=100,            # Number of training epochs
        imgsz=640,             # Image size
        batch=16,              # Batch size
        device="cpu",          # Change to '0' if NVIDIA GPU is available
        name="indian_anpr_v1", # Name of the experiment
        project="runs/detect", # Where to save results
        patience=20,           # Early stopping patience
        save=True,             # Save best weights
    )
    
    # Export best weights to models/anpr/best.pt
    best_weights = os.path.join("runs", "detect", "indian_anpr_v1", "weights", "best.pt")
    export_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "anpr"))
    
    if not os.path.exists(export_dir):
        os.makedirs(export_dir)
        
    export_path = os.path.join(export_dir, "best.pt")
    
    if os.path.exists(best_weights):
        shutil.copy(best_weights, export_path)
        print("\nTraining Complete!")
        print(f"Best weights have been exported to: {export_path}")
        print("ocr_service.py will automatically load this model upon server restart.")
    else:
        print("\nTraining completed but best weights were not found. Check runs/detect directory.")

if __name__ == "__main__":
    main()
