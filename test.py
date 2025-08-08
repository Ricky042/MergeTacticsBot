from ultralytics import YOLO

model = YOLO('runs/detect/train4/weights/best.pt')

img_path = 'callum-photos/IMG_8492.PNG'  # your training image path

results = model.predict(img_path, imgsz=640, conf=0.25, verbose=True)

if len(results[0].boxes) == 0:
    print("No detections found on image. Check data and training!")
else:
    names = results[0].names
    boxes = results[0].boxes

    for cls_id, conf, box in zip(boxes.cls.cpu().numpy(), boxes.conf.cpu().numpy(), boxes.xyxy.cpu().numpy()):
        label = names[int(cls_id)]
        # shorten the label if needed by cutting off after first underscore or so
        short_label = label.split('_')[0]
        print(f"Detected: {label} with confidence {conf:.4f} at {box}")

    results[0].show()
