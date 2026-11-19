import cv2
import numpy as np
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
MODEL_DIR = os.path.join(BASE_DIR, "model")

os.makedirs(MODEL_DIR, exist_ok=True)

recognizer = cv2.face.LBPHFaceRecognizer_create(
    radius=1,
    neighbors=8,
    grid_x=8,
    grid_y=8,
    threshold=80
)


def preprocess_face(image, size=(200, 200)):
    """Grayscale + CLAHE; resize to 200x200 unless size is None."""
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    image = clahe.apply(image)
    if size is not None:
        image = cv2.resize(image, size)
    return image


def augment_face(face):
    """In-memory variants for tilt, lighting and mirror tolerance."""
    variants = [face]
    height, width = face.shape[:2]
    center = (width / 2.0, height / 2.0)

    for angle in (-15, -10, 10, 15):
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        variants.append(
            cv2.warpAffine(
                face,
                matrix,
                (width, height),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REPLICATE
            )
        )

    variants.append(cv2.flip(face, 1))
    variants.append(cv2.convertScaleAbs(face, alpha=1.15, beta=20))
    variants.append(cv2.convertScaleAbs(face, alpha=0.85, beta=-20))

    bright_lut = np.array(
        [((i / 255.0) ** 0.8) * 255 for i in range(256)],
        dtype=np.uint8
    )
    dark_lut = np.array(
        [((i / 255.0) ** 1.2) * 255 for i in range(256)],
        dtype=np.uint8
    )
    variants.append(cv2.LUT(face, bright_lut))
    variants.append(cv2.LUT(face, dark_lut))

    return variants

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

        image = preprocess_face(image)

        for variant in augment_face(image):
            faces.append(variant)
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
