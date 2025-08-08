import xml.etree.ElementTree as ET
import os
from collections import defaultdict

class XMLToYOLOConverter:
    def __init__(self):
        self.class_mapping = {}
        self.class_counter = 0
        self.attribute_combinations = set()
        
    def parse_xml(self, xml_file_path):
        """Parse XML file and extract annotations with attributes"""
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        
        annotations = []
        
        for image in root.findall('image'):
            image_info = {
                'id': image.get('id'),
                'name': image.get('name'),
                'width': int(image.get('width')),
                'height': int(image.get('height')),
                'annotations': []
            }
            
            # Process bounding boxes
            for box in image.findall('box'):
                label = box.get('label')
                
                # Extract attributes
                attributes = {}
                for attr in box.findall('attribute'):
                    attr_name = attr.get('name')
                    attr_value = attr.text
                    attributes[attr_name] = attr_value
                
                # Create unique class identifier
                class_key = self.create_class_key(label, attributes)
                
                annotation = {
                    'label': label,
                    'attributes': attributes,
                    'class_key': class_key,
                    'bbox': {
                        'xtl': float(box.get('xtl')),
                        'ytl': float(box.get('ytl')),
                        'xbr': float(box.get('xbr')),
                        'ybr': float(box.get('ybr'))
                    }
                }
                
                image_info['annotations'].append(annotation)
            
            annotations.append(image_info)
        
        return annotations
    
    def create_class_key(self, label, attributes):
        """Create a unique class key from label and attributes"""
        # Sort attributes to ensure consistent ordering
        attr_parts = []
        for key in sorted(attributes.keys()):
            attr_parts.append(f"{key}_{attributes[key]}")
        
        class_key = f"{label}_{'_'.join(attr_parts)}"
        
        # Add to class mapping if not exists
        if class_key not in self.class_mapping:
            self.class_mapping[class_key] = self.class_counter
            self.class_counter += 1
        
        self.attribute_combinations.add(class_key)
        return class_key
    
    def bbox_to_yolo_format(self, bbox, img_width, img_height):
        """Convert bounding box to YOLO format (normalized x_center, y_center, width, height)"""
        x_center = (bbox['xtl'] + bbox['xbr']) / 2.0 / img_width
        y_center = (bbox['ytl'] + bbox['ybr']) / 2.0 / img_height
        width = (bbox['xbr'] - bbox['xtl']) / img_width
        height = (bbox['ybr'] - bbox['ytl']) / img_height
        
        return x_center, y_center, width, height
    
    def convert_to_yolo(self, xml_file_path, output_dir):
        """Convert XML annotations to YOLO format"""
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Parse XML
        annotations = self.parse_xml(xml_file_path)
        
        # Convert each image's annotations
        for image_data in annotations:
            image_name = image_data['name']
            # Create output filename (replace extension with .txt)
            output_filename = os.path.splitext(image_name)[0] + '.txt'
            output_path = os.path.join(output_dir, output_filename)
            
            with open(output_path, 'w') as f:
                for annotation in image_data['annotations']:
                    class_id = self.class_mapping[annotation['class_key']]
                    
                    # Convert bbox to YOLO format
                    x_center, y_center, width, height = self.bbox_to_yolo_format(
                        annotation['bbox'], 
                        image_data['width'], 
                        image_data['height']
                    )
                    
                    # Write YOLO format line: class_id x_center y_center width height
                    f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
        
        # Save class mapping
        self.save_class_mapping(output_dir)
        
        print(f"Conversion completed! Generated {len(annotations)} annotation files.")
        print(f"Total unique classes: {len(self.class_mapping)}")
        
    def save_class_mapping(self, output_dir):
        """Save class mapping to files"""
        # Save classes.txt (YOLO format)
        classes_file = os.path.join(output_dir, 'classes.txt')
        with open(classes_file, 'w') as f:
            # Sort by class ID
            sorted_classes = sorted(self.class_mapping.items(), key=lambda x: x[1])
            for class_key, class_id in sorted_classes:
                f.write(f"{class_key}\n")
        
        # Save detailed mapping
        mapping_file = os.path.join(output_dir, 'class_mapping.txt')
        with open(mapping_file, 'w') as f:
            f.write("Class ID -> Class Name (Label + Attributes)\n")
            f.write("=" * 50 + "\n")
            sorted_classes = sorted(self.class_mapping.items(), key=lambda x: x[1])
            for class_key, class_id in sorted_classes:
                f.write(f"{class_id} -> {class_key}\n")
        
        print(f"Class mapping saved to {classes_file} and {mapping_file}")
    
    def print_class_statistics(self):
        """Print statistics about the classes found"""
        print("\nClass Statistics:")
        print("=" * 50)
        
        # Group by base label
        label_groups = defaultdict(list)
        for class_key in self.attribute_combinations:
            base_label = class_key.split('_')[0]
            label_groups[base_label].append(class_key)
        
        for label, variations in label_groups.items():
            print(f"{label}: {len(variations)} variations")
            for variation in variations:
                class_id = self.class_mapping[variation]
                print(f"  {class_id}: {variation}")
            print()

# Usage example
def main():
    # Initialize converter
    converter = XMLToYOLOConverter()
    
    # Convert XML to YOLO
    xml_file = "annotations-1.xml"  # Your XML file
    output_directory = "batch1"
    
    try:
        converter.convert_to_yolo(xml_file, output_directory)
        converter.print_class_statistics()
        
        print(f"\nFiles generated in '{output_directory}':")
        print("- Individual .txt files for each image")
        print("- classes.txt (list of class names)")
        print("- class_mapping.txt (detailed ID to name mapping)")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure your XML file path is correct and the file is accessible.")

if __name__ == "__main__":
    main()