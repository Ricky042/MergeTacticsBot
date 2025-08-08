from ultralytics import YOLO

def main():
    # Load a model
    model = YOLO('yolo11n.pt')  # load a pretrained model (recommended for training)

    # Train the model
    results = model.train(data='batch1/data.yaml', epochs=500, imgsz=640, batch=64)

if __name__ == '__main__':
    main()
