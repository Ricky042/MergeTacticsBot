import cv2
import os

# Set paths
video_path = 'assassin.mp4'  # <-- Replace with your video filename
output_folder = 'frames'

# Create output folder if it doesn't exist
os.makedirs(output_folder, exist_ok=True)

# Open video
cap = cv2.VideoCapture(video_path)
if not cap.isOpened():
    print(f"Error: Could not open video file {video_path}")
    exit()

frame_number = 0
saved_count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break  # End of video

    if frame_number % 500 == 0:
        filename = os.path.join(output_folder, f"frame_{frame_number}.jpg")
        cv2.imwrite(filename, frame)
        saved_count += 1

    frame_number += 1

cap.release()
print(f"Done. Saved {saved_count} frames to '{output_folder}'")
