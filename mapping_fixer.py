import os
import shutil
from collections import defaultdict

class YOLOClassStandardizer:
    def __init__(self, master_classes):
        """
        Initialize with a master class list
        
        Args:
            master_classes: List of class names in desired order
        """
        self.master_classes = master_classes
        self.master_mapping = {name: idx for idx, name in enumerate(master_classes)}
    
    def read_classes_file(self, classes_file):
        """Read classes from a classes.txt file"""
        with open(classes_file, 'r') as f:
            classes = [line.strip() for line in f if line.strip()]
        return classes
    
    def remap_annotation_file(self, annotation_file, old_mapping, output_file=None):
        """
        Remap class IDs in a single YOLO annotation file
        
        Args:
            annotation_file: Path to .txt annotation file
            old_mapping: Dict mapping class_name -> old_id
            output_file: Output path (if None, overwrites original)
        """
        if output_file is None:
            output_file = annotation_file
        
        # Create reverse mapping for old IDs
        old_id_to_name = {v: k for k, v in old_mapping.items()}
        
        lines = []
        line_count = 0
        
        with open(annotation_file, 'r') as f:
            for line in f:
                line_count += 1
                line = line.strip()
                
                # Skip empty lines
                if not line:
                    continue
                
                parts = line.split()
                
                # YOLO format should have exactly 5 parts: class_id x_center y_center width height
                if len(parts) >= 5:
                    try:
                        # Try to parse the first part as class ID
                        old_class_id = int(parts[0])
                        
                        # Validate that other parts are floats (coordinates)
                        for i in range(1, 5):
                            float(parts[i])
                        
                        # Get class name from old ID
                        if old_class_id in old_id_to_name:
                            class_name = old_id_to_name[old_class_id]
                            
                            # Get new ID for this class
                            if class_name in self.master_mapping:
                                new_class_id = self.master_mapping[class_name]
                                parts[0] = str(new_class_id)
                                lines.append(' '.join(parts))
                            else:
                                print(f"⚠️  Warning: Class '{class_name}' not found in master mapping")
                        else:
                            print(f"⚠️  Warning: Old class ID {old_class_id} not found in mapping (file: {annotation_file}, line: {line_count})")
                    
                    except ValueError as e:
                        print(f"⚠️  Skipping invalid line {line_count} in {annotation_file}: '{line}'")
                        print(f"     Error: {e}")
                        continue
                
                else:
                    print(f"⚠️  Skipping malformed line {line_count} in {annotation_file}: '{line}' (expected 5 parts, got {len(parts)})")
        
        # Write remapped file
        with open(output_file, 'w') as f:
            for line in lines:
                f.write(line + '\n')
    
    def standardize_dataset(self, dataset_path, output_path=None, backup=True):
        """
        Standardize a single dataset to use the master class mapping
        
        Args:
            dataset_path: Path to dataset folder
            output_path: Output path (if None, modifies in place)
            backup: Whether to create backup of original
        """
        if output_path is None:
            output_path = dataset_path
        
        # Read current classes
        classes_file = os.path.join(dataset_path, 'classes.txt')
        if not os.path.exists(classes_file):
            print(f"❌ No classes.txt found in {dataset_path}")
            return False
        
        current_classes = self.read_classes_file(classes_file)
        current_mapping = {name: idx for idx, name in enumerate(current_classes)}
        
        print(f"Standardizing dataset: {dataset_path}")
        print(f"Current classes: {current_classes}")
        print(f"Output: {output_path}")
        
        # Create backup if requested
        if backup and dataset_path == output_path:
            backup_path = dataset_path + "_backup"
            if os.path.exists(backup_path):
                shutil.rmtree(backup_path)
            shutil.copytree(dataset_path, backup_path)
            print(f"✅ Backup created: {backup_path}")
        
        # Create output directory if different
        if output_path != dataset_path:
            os.makedirs(output_path, exist_ok=True)
        
        # Process all .txt files (excluding classes.txt)
        txt_files = [f for f in os.listdir(dataset_path) 
                    if f.endswith('.txt') and f != 'classes.txt']
        
        remapped_count = 0
        for txt_file in txt_files:
            input_file = os.path.join(dataset_path, txt_file)
            output_file = os.path.join(output_path, txt_file)
            
            # Check if file is empty before processing
            if os.path.getsize(input_file) == 0:
                print(f"⚠️  Skipping empty file: {txt_file}")
                # Still copy empty file to output
                if input_file != output_file:
                    shutil.copy2(input_file, output_file)
                continue
            
            self.remap_annotation_file(input_file, current_mapping, output_file)
            remapped_count += 1
        
        # Copy other files if output is different directory
        if output_path != dataset_path:
            for file in os.listdir(dataset_path):
                if not file.endswith('.txt'):
                    src = os.path.join(dataset_path, file)
                    dst = os.path.join(output_path, file)
                    if os.path.isfile(src):
                        shutil.copy2(src, dst)
                    elif os.path.isdir(src):
                        shutil.copytree(src, dst, dirs_exist_ok=True)
        
        # Write new classes.txt with master class order
        new_classes_file = os.path.join(output_path, 'classes.txt')
        with open(new_classes_file, 'w') as f:
            for class_name in self.master_classes:
                f.write(class_name + '\n')
        
        print(f"✅ Remapped {remapped_count} annotation files")
        print(f"✅ Updated classes.txt with {len(self.master_classes)} classes in preferred order")
        
        return True
    
    def standardize_multiple_datasets(self, dataset_paths, output_dir=None, backup=True):
        """
        Standardize multiple datasets to use the master class mapping
        
        Args:
            dataset_paths: List of dataset folder paths
            output_dir: Directory to save standardized datasets (if None, modifies in place)
            backup: Whether to create backups
        """
        print("Master Class Mapping:")
        print("=" * 40)
        for idx, class_name in enumerate(self.master_classes):
            print(f"  {idx}: {class_name}")
        print()
        
        # Standardize each dataset
        print("Standardizing datasets...")
        print("=" * 40)
        
        for i, dataset_path in enumerate(dataset_paths):
            if output_dir:
                dataset_name = os.path.basename(dataset_path.rstrip('/\\'))
                output_path = os.path.join(output_dir, f"standardized_{dataset_name}")
            else:
                output_path = dataset_path
            
            success = self.standardize_dataset(dataset_path, output_path, backup)
            if success:
                print(f"✅ Dataset {i+1} standardized successfully")
            else:
                print(f"❌ Failed to standardize dataset {i+1}")
            print()
        
        print("🎉 All datasets standardized!")
        print(f"All datasets now use the same class mapping with {len(self.master_classes)} classes")

def main():
    """Example usage"""
    
    # Dataset paths
    dataset_paths = [
        "batch1",
        "batch2" 
        # Add more dataset paths here
    ]
    
    # Your preferred class order - this will be the final mapping for all datasets
    preferred_class_order = [
        "archer",
        "goblin", 
        "dart-goblin",
        "barbarian",
        "bomber",
        "archer-queen",
        "princess",
        "pekka",
        "giant-skeleton",
        "prince",
        "valkyrie",
        "golden-knight",
        "spear-goblin",
        "goblin-machine",
        "knight",
        "mega-knight",
        "bandit",
        "executioner",
        "royal-ghost",
        "skeleton-king"
        # Add your classes in preferred order
    ]
    
    # Initialize standardizer with your preferred class order
    standardizer = YOLOClassStandardizer(master_classes=preferred_class_order)
    
    try:
        # Standardize all datasets to use the preferred class order
        standardizer.standardize_multiple_datasets(
            dataset_paths=dataset_paths,
            output_dir=None,  # None = modify in place, or provide output directory
            backup=True       # Create backups before modifying
        )
        
        print("\n📋 Final Master Classes (used by all datasets):")
        for idx, class_name in enumerate(standardizer.master_classes):
            print(f"  {idx}: {class_name}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()