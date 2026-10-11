
import cv2
import numpy as np
import os

DATASET_DIR = "dataset"
MODEL_DIR = "model"

os.makedirs(MODEL_DIR, exist_ok=True)

recognizer = cv2.face.LBPHFaceRecognizer_create()

faces = []
labels = []
label_names = {}

label_id = 0

if not os.path.exists(DATASET_DIR):
    print("Error: Dataset folder not found!")
    exit()

for person_name in sorted(os.listdir(DATASET_DIR)):
    person_path = os.path.join(DATASET_DIR, person_name)

    if not os.path.isdir(person_path):
        continue

    image_files = [
        f for f in os.listdir(person_path)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    if not image_files:
        continue

    label_names[label_id] = person_name

    for image_file in image_files:
        image_path = os.path.join(person_path, image_file)

        image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

        if image is None:
            print(f"Skipping unreadable image: {image_path}")
            continue

        image = cv2.resize(image, (200, 200))

        faces.append(image)
        labels.append(label_id)

    print(f"Loaded {len(image_files)} images for {person_name}")
    label_id += 1

if not faces:
    print("Error: No face images found in dataset!")
    exit()

recognizer.train(faces, np.array(labels))

recognizer.save(os.path.join(MODEL_DIR, "face_model.yml"))

np.save(
    os.path.join(MODEL_DIR, "label_names.npy"),
    np.array([label_names[i] for i in sorted(label_names.keys())])
)

print("Model trained successfully!")
print("Model saved in model/face_model.yml")
print("Labels saved in model/label_names.npy")
print("Registered people:", label_names)
