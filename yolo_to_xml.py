import os
import cv2
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from ultralytics import YOLO
import random

class YOLOToXMLConverter:
    def __init__(self, model_path, class_names=None):
        """
        Initialize the converter with trained YOLO model
        
        Args:
            model_path: Path to your trained YOLO model (.pt file)
            class_names: List of class names (optional, will be read from model if not provided)
        """
        self.model = YOLO(model_path)
        self.class_names = class_names or self.model.names
        
    def generate_job_id(self):
        """Generate a random job ID for CVAT"""
        return random.randint(1000000, 9999999)
    
    def generate_colors(self, num_classes):
        """Generate random colors for each class"""
        colors = []
        for _ in range(num_classes):
            # Generate random hex color
            color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
            colors.append(color)
        return colors
    
    def yolo_to_bbox(self, yolo_coords, img_width, img_height):
        """Convert YOLO format to bounding box coordinates"""
        x_center, y_center, width, height = yolo_coords
        
        # Convert from normalized to pixel coordinates
        x_center *= img_width
        y_center *= img_height
        width *= img_width
        height *= img_height
        
        # Calculate top-left and bottom-right coordinates
        xtl = x_center - width / 2
        ytl = y_center - height / 2
        xbr = x_center + width / 2
        ybr = y_center + height / 2
        
        return xtl, ytl, xbr, ybr
    
    def run_inference(self, image_folder, confidence_threshold=0.5):
        """
        Run YOLO inference on all images in a folder
        
        Args:
            image_folder: Path to folder containing images
            confidence_threshold: Minimum confidence for detections
        
        Returns:
            Dictionary with image results
        """
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
        image_files = []
        
        # Get all image files
        for file in os.listdir(image_folder):
            if any(file.lower().endswith(ext) for ext in image_extensions):
                image_files.append(file)
        
        image_files.sort()  # Sort for consistent ordering
        
        results_dict = {}
        
        print(f"Running inference on {len(image_files)} images...")
        
        for idx, image_file in enumerate(image_files):
            image_path = os.path.join(image_folder, image_file)
            
            # Load image to get dimensions
            img = cv2.imread(image_path)
            if img is None:
                print(f"Warning: Could not load {image_file}")
                continue
                
            height, width = img.shape[:2]
            
            # Run YOLO inference
            results = self.model(image_path, conf=confidence_threshold)
            
            detections = []
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        # Get detection data
                        conf = float(box.conf[0])
                        cls_id = int(box.cls[0])
                        coords = box.xywhn[0].tolist()  # normalized coordinates
                        
                        # Convert to pixel coordinates
                        xtl, ytl, xbr, ybr = self.yolo_to_bbox(coords, width, height)
                        
                        # Get class name (simple label only)
                        class_name = self.class_names[cls_id]
                        
                        detection = {
                            'label': class_name,
                            'bbox': {
                                'xtl': xtl,
                                'ytl': ytl,
                                'xbr': xbr,
                                'ybr': ybr
                            },
                            'confidence': conf
                        }
                        detections.append(detection)
            
            results_dict[idx] = {
                'filename': image_file,
                'width': width,
                'height': height,
                'detections': detections
            }
            
            print(f"Processed {image_file}: {len(detections)} detections")
        
        return results_dict
    
    def create_cvat_xml(self, results_dict, output_path):
        """Create CVAT-compatible XML from inference results"""
        
        # Create root element
        root = ET.Element("annotations")
        
        # Add version
        version = ET.SubElement(root, "version")
        version.text = "1.1"
        
        # Create meta section
        meta = ET.SubElement(root, "meta")
        
        # Job info
        job = ET.SubElement(meta, "job")
        job_id = ET.SubElement(job, "id")
        job_id.text = str(self.generate_job_id())
        
        size = ET.SubElement(job, "size")
        size.text = str(len(results_dict))
        
        mode = ET.SubElement(job, "mode")
        mode.text = "annotation"
        
        overlap = ET.SubElement(job, "overlap")
        overlap.text = "0"
        
        bugtracker = ET.SubElement(job, "bugtracker")
        
        created = ET.SubElement(job, "created")
        created.text = datetime.now().isoformat() + "+00:00"
        
        updated = ET.SubElement(job, "updated")
        updated.text = datetime.now().isoformat() + "+00:00"
        
        subset = ET.SubElement(job, "subset")
        subset.text = "default"
        
        start_frame = ET.SubElement(job, "start_frame")
        start_frame.text = "0"
        
        stop_frame = ET.SubElement(job, "stop_frame")
        stop_frame.text = str(len(results_dict) - 1)
        
        frame_filter = ET.SubElement(job, "frame_filter")
        
        # Segments
        segments = ET.SubElement(job, "segments")
        segment = ET.SubElement(segments, "segment")
        seg_id = ET.SubElement(segment, "id")
        seg_id.text = "1"
        start = ET.SubElement(segment, "start")
        start.text = "0"
        stop = ET.SubElement(segment, "stop")
        stop.text = str(len(results_dict) - 1)
        url = ET.SubElement(segment, "url")
        url.text = f"https://app.cvat.ai/api/jobs/{job_id.text}"
        
        # Owner (you can customize this)
        owner = ET.SubElement(job, "owner")
        username = ET.SubElement(owner, "username")
        username.text = "auto_annotator"
        email = ET.SubElement(owner, "email")
        email.text = "auto@example.com"
        
        assignee = ET.SubElement(job, "assignee")
        
        # Labels section - simplified for basic classes only
        labels = ET.SubElement(job, "labels")
        
        # Get unique class names
        unique_labels = set()
        for image_data in results_dict.values():
            for detection in image_data['detections']:
                unique_labels.add(detection['label'])
        
        # Generate colors for labels
        unique_labels = sorted(unique_labels)
        colors = self.generate_colors(len(unique_labels))
        
        # Create simple label definitions (no attributes)
        for idx, label_name in enumerate(unique_labels):
            label_elem = ET.SubElement(labels, "label")
            
            name_elem = ET.SubElement(label_elem, "name")
            name_elem.text = label_name
            
            color_elem = ET.SubElement(label_elem, "color")
            color_elem.text = colors[idx]
            
            type_elem = ET.SubElement(label_elem, "type")
            type_elem.text = "rectangle"
            
            # Empty attributes section (no custom attributes)
            attributes_elem = ET.SubElement(label_elem, "attributes")
        
        # Dumped timestamp
        dumped = ET.SubElement(meta, "dumped")
        dumped.text = datetime.now().isoformat() + "+00:00"
        
        # Add image annotations
        for img_id, image_data in results_dict.items():
            image_elem = ET.SubElement(root, "image")
            image_elem.set("id", str(img_id))
            image_elem.set("name", image_data['filename'])
            image_elem.set("width", str(image_data['width']))
            image_elem.set("height", str(image_data['height']))
            
            # Add detections as simple boxes
            for detection in image_data['detections']:
                box_elem = ET.SubElement(image_elem, "box")
                box_elem.set("label", detection['label'])
                box_elem.set("source", "manual")
                box_elem.set("occluded", "0")
                box_elem.set("xtl", f"{detection['bbox']['xtl']:.2f}")
                box_elem.set("ytl", f"{detection['bbox']['ytl']:.2f}")
                box_elem.set("xbr", f"{detection['bbox']['xbr']:.2f}")
                box_elem.set("ybr", f"{detection['bbox']['ybr']:.2f}")
                box_elem.set("z_order", "0")
                
                # No attributes - just simple bounding boxes
        
        # Write XML file
        rough_string = ET.tostring(root, 'unicode')
        reparsed = minidom.parseString(rough_string)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(reparsed.toprettyxml(indent="  "))
        
        print(f"CVAT XML file saved to: {output_path}")
        return output_path

def main():
    """Example usage"""
    
    # Configuration - UPDATE THESE PATHS
    model_path = "runs/detect/train4/weights/best.pt"  # Path to your trained model
    image_folder = "frames"  # Folder with images to annotate
    output_xml = "auto_annotations.xml"   # Output XML file name
    confidence_threshold = 0.5            # Minimum confidence for detections
    
    try:
        # Initialize converter
        print("Loading YOLO model...")
        converter = YOLOToXMLConverter(model_path)
        
        print(f"Model loaded with {len(converter.class_names)} classes:")
        for idx, class_name in converter.class_names.items():
            print(f"  {idx}: {class_name}")
        
        # Run inference on images
        print("\nRunning inference on images...")
        results = converter.run_inference(image_folder, confidence_threshold)
        
        if not results:
            print("❌ No images found or processed. Check your image folder path.")
            return
        
        # Create CVAT XML
        print("Creating CVAT XML...")
        xml_path = converter.create_cvat_xml(results, output_xml)
        
        # Summary
        total_detections = sum(len(img_data['detections']) for img_data in results.values())
        print(f"\n✅ Conversion completed!")
        print(f"📁 Processed {len(results)} images")
        print(f"🎯 Found {total_detections} total detections")
        print(f"📄 XML saved to: {xml_path}")
        print(f"\nYou can now import '{xml_path}' into CVAT!")
        
        # Show detection breakdown by class
        class_counts = {}
        for img_data in results.values():
            for detection in img_data['detections']:
                label = detection['label']
                class_counts[label] = class_counts.get(label, 0) + 1
        
        if class_counts:
            print(f"\n📊 Detection breakdown:")
            for label, count in sorted(class_counts.items()):
                print(f"  {label}: {count} detections")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure your model path and image folder are correct.")

if __name__ == "__main__":
    main()