import os
import shutil

def merge_datasets(source_dir, dest_dir):
    """
    Merges YOLO format dataset from source_dir into dest_dir.
    Assumes structure:
    - images/train, images/val, images/test
    - labels/train, labels/val, labels/test
    """
    print(f"Merging dataset from {source_dir} into {dest_dir}...")
    
    if not os.path.exists(source_dir):
        print(f"Error: Source directory {source_dir} does not exist.")
        return
        
    os.makedirs(dest_dir, exist_ok=True)
    
    splits = ['train', 'val', 'test']
    types = ['images', 'labels']
    
    copied_count = 0
    
    for t in types:
        for s in splits:
            src_path = os.path.join(source_dir, t, s)
            dst_path = os.path.join(dest_dir, t, s)
            
            if not os.path.exists(src_path):
                continue
                
            os.makedirs(dst_path, exist_ok=True)
            
            for item in os.listdir(src_path):
                s_item = os.path.join(src_path, item)
                d_item = os.path.join(dst_path, item)
                
                # Handle filename collisions
                if os.path.exists(d_item):
                    base, ext = os.path.splitext(item)
                    new_name = f"{base}_merged{ext}"
                    d_item = os.path.join(dst_path, new_name)
                    
                if os.path.isfile(s_item):
                    shutil.copy2(s_item, d_item)
                    copied_count += 1
                    
    print(f"Successfully merged {copied_count} files into {dest_dir}")

def main():
    print("YOLO Dataset Merger")
    print("Use this tool to expand the main ANPR dataset with new Kaggle datasets.")
    
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "datasets"))
    primary_dataset = os.path.join(base_dir, "indian_plates")
    
    print("\nExpected directory structure for new dataset:")
    print("new_dataset/")
    print("  ├── images/ (train, val, test)")
    print("  └── labels/ (train, val, test)")
    
    source = input("\nEnter the absolute path to the new YOLO dataset to merge: ").strip()
    
    if source:
        merge_datasets(source, primary_dataset)
        print("\nMerge complete. You can now run scripts/train_anpr.py to train on the expanded dataset.")
    else:
        print("Merge cancelled.")

if __name__ == "__main__":
    main()
