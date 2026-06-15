import os
import shutil
import random
import yaml
import xml.etree.ElementTree as ET

def convert_voc_to_yolo(xml_file, classes):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    size = root.find('size')
    w = int(size.find('width').text)
    h = int(size.find('height').text)
    
    yolo_annotations = []
    
    for obj in root.findall('object'):
        name = obj.find('name').text
        if name not in classes:
            continue
        
        cls_id = classes.index(name)
        xmlbox = obj.find('bndbox')
        
        # Pascal VOC coordinates
        xmin = float(xmlbox.find('xmin').text)
        xmax = float(xmlbox.find('xmax').text)
        ymin = float(xmlbox.find('ymin').text)
        ymax = float(xmlbox.find('ymax').text)
        
        # YOLO normalized coordinates
        center_x = ((xmin + xmax) / 2.0) / w
        center_y = ((ymin + ymax) / 2.0) / h
        width = (xmax - xmin) / w
        height = (ymax - ymin) / h
        
        yolo_annotations.append(f"{cls_id} {center_x:.6f} {center_y:.6f} {width:.6f} {height:.6f}")
        
    return yolo_annotations

def main():
    print("Parsing Dataset into YOLOv8 format...")
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "datasets"))
    extract_dir = os.path.join(base_dir, "temp_extract")
    yolo_dir = os.path.join(base_dir, "indian_plates")
    
    # Target directories
    dirs = {
        'images/train': os.path.join(yolo_dir, "images", "train"),
        'images/val': os.path.join(yolo_dir, "images", "val"),
        'images/test': os.path.join(yolo_dir, "images", "test"),
        'labels/train': os.path.join(yolo_dir, "labels", "train"),
        'labels/val': os.path.join(yolo_dir, "labels", "val"),
        'labels/test': os.path.join(yolo_dir, "labels", "test")
    }
    
    # Ensure clean target dirs
    for d in dirs.values():
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)
        
    # Source mappings (XML dir -> JPG dir)
    sources = [
        (
            os.path.join(extract_dir, "Annotations", "Annotations"),
            os.path.join(extract_dir, "Indian_Number_Plates", "Sample_Images")
        ),
        (
            os.path.join(extract_dir, "number_plate_annos_ocr", "number_plate_annos_ocr"),
            os.path.join(extract_dir, "number_plate_images_ocr", "number_plate_images_ocr")
        )
    ]
    
    classes = ['license_plate']
    dataset_pairs = []
    
    # Discover pairs
    for xml_dir, img_dir in sources:
        if not os.path.exists(xml_dir) or not os.path.exists(img_dir):
            continue
            
        for xml_file in os.listdir(xml_dir):
            if not xml_file.endswith('.xml'): continue
            
            base_name = xml_file[:-4]
            jpg_file = base_name + '.jpg'
            
            xml_path = os.path.join(xml_dir, xml_file)
            img_path = os.path.join(img_dir, jpg_file)
            
            if os.path.exists(img_path):
                # The Kaggle dataset used "number_plate" as class name, we map it to "license_plate"
                # To handle this, we'll temporarily map 'number_plate' -> 'license_plate' during extraction
                dataset_pairs.append((xml_path, img_path, base_name))
                
    if len(dataset_pairs) == 0:
        print("No image/annotation pairs found!")
        return
        
    # Shuffle and split 80/10/10
    random.shuffle(dataset_pairs)
    train_idx = int(0.8 * len(dataset_pairs))
    val_idx = train_idx + int(0.1 * len(dataset_pairs))
    
    train_pairs = dataset_pairs[:train_idx]
    val_pairs = dataset_pairs[train_idx:val_idx]
    test_pairs = dataset_pairs[val_idx:]
    
    def process_split(pairs, split_name):
        for xml_path, img_path, base_name in pairs:
            # Copy Image
            target_img = os.path.join(dirs[f'images/{split_name}'], base_name + '.jpg')
            shutil.copy(img_path, target_img)
            
            # Map "number_plate" from XML to "license_plate" requirement
            # So pass ['number_plate'] to grab it but the output cls_id will be 0
            yolo_annotations = convert_voc_to_yolo(xml_path, ['number_plate'])
            target_label = os.path.join(dirs[f'labels/{split_name}'], base_name + '.txt')
            with open(target_label, 'w') as f:
                f.write('\n'.join(yolo_annotations))
                
    process_split(train_pairs, 'train')
    process_split(val_pairs, 'val')
    process_split(test_pairs, 'test')
    
    # 3. Create dataset.yaml automatically
    yaml_content = {
        'path': os.path.abspath(yolo_dir),
        'train': 'images/train',
        'val': 'images/val',
        'test': 'images/test',
        'names': {0: 'license_plate'}
    }
    
    yaml_path = os.path.join(yolo_dir, 'dataset.yaml')
    with open(yaml_path, 'w') as f:
        yaml.dump(yaml_content, f, sort_keys=False)
    
    print(f"Processed {len(train_pairs)} training images.")
    print(f"Processed {len(val_pairs)} validation images.")
    print(f"Processed {len(test_pairs)} test images.")
    print(f"Created {yaml_path}")
    print("Dataset is now ready for YOLOv8 training!")

if __name__ == "__main__":
    main()
