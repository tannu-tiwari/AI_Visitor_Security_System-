import cv2
import os
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

name = input("Enter visitor name: ").strip()

if not name:
    print("Name cannot be empty!")
    raise SystemExit

save_path = os.path.join(BASE_DIR, "dataset", name)
os.makedirs(save_path, exist_ok=True)

cascade_path = os.path.join(
    BASE_DIR, "model", "haarcascade_frontalface_default.xml"
)

face_cascade = cv2.CascadeClassifier(cascade_path)

if face_cascade.empty():
    print("ERROR: Face detector XML file not found.")
    print("Path:", cascade_path)
    raise SystemExit


def preprocess_face(image, size=(200, 200)):
    """Grayscale + CLAHE; resize to 200x200 unless size is None."""
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    image = clahe.apply(image)
    if size is not None:
        image = cv2.resize(image, size)
    return image


def detect_faces(frame):
    """Upright pass first, then retry on rotated frames for head tilt."""
    gray = preprocess_face(frame, size=None)

    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(50, 50)
    )

    if len(faces) > 0:
        return [
            ((x, y, w, h), frame[y:y + h, x:x + w])
            for (x, y, w, h) in faces
        ]

    results = []
    height, width = gray.shape[:2]
    center = (width / 2.0, height / 2.0)

    for angle in (-20, 20, -35, 35):
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            gray,
            matrix,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE
        )

        rotated_faces = face_cascade.detectMultiScale(
            rotated,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(50, 50)
        )

        if len(rotated_faces) == 0:
            continue

        # Crop from the rotated (upright) image, map the box back for drawing.
        rotated_frame = cv2.warpAffine(
            frame,
            matrix,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE
        )
        inverse = cv2.invertAffineTransform(matrix)

        for (x, y, w, h) in rotated_faces:
            cx = x + w / 2.0
            cy = y + h / 2.0
            ox = inverse[0, 0] * cx + inverse[0, 1] * cy + inverse[0, 2]
            oy = inverse[1, 0] * cx + inverse[1, 1] * cy + inverse[1, 2]

            box = (
                int(round(ox - w / 2.0)),
                int(round(oy - h / 2.0)),
                int(w),
                int(h)
            )
            results.append((box, rotated_frame[y:y + h, x:x + w]))

        break

    return results


capture_instructions = [
    "Look straight at the camera",
    "Slowly tilt your head LEFT",
    "Slowly tilt your head RIGHT",
    "Turn your head slightly LEFT",
    "Turn your head slightly RIGHT",
    "Move slightly CLOSER, then FARTHER"
]

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("ERROR: Camera could not be opened!")
    raise SystemExit

count = 0
target_images = 200
save_interval = 0.35
last_save_time = 0.0
paused = False

while count < target_images:
    success, frame = camera.read()

    if not success:
        print("ERROR: Could not read camera frame.")
        break

    # Face detect karo
    faces = detect_faces(frame)

    if len(faces) > 0:
        faces = sorted(faces, key=lambda item: item[0][2] * item[0][3], reverse=True)
        (x, y, w, h), face_crop = faces[0]

        cv2.rectangle(
            frame,
            (x, y),
            (x + w, y + h),
            (0, 255, 0),
            2
        )

        # Save slower so poses vary instead of 100 near-identical frames.
        if not paused:
            now = time.time()

            if now - last_save_time >= save_interval:
                face = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
                face = cv2.resize(face, (200, 200))

                count += 1

                file_path = os.path.join(save_path, f"{count}.jpg")
                cv2.imwrite(file_path, face)

                last_save_time = now

    cv2.putText(
        frame,
        f"Images: {count}/{target_images}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    phase = min(count * len(capture_instructions) // target_images,
                len(capture_instructions) - 1)
    cv2.putText(
        frame,
        capture_instructions[phase],
        (20, frame.shape[0] - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 255),
        2
    )

    if paused:
        cv2.putText(
            frame,
            "PAUSED - press SPACE to resume",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2
        )
    else:
        cv2.putText(
            frame,
            "SPACE: pause | Q: quit",
            (20, frame.shape[0] - 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            1
        )

    cv2.imshow("Visitor Face Registration", frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

    if key == ord(" "):
        paused = not paused

        if not paused:
            last_save_time = time.time()

camera.release()
cv2.destroyAllWindows()

print("Images saved:", count)
print("Folder:", os.path.abspath(save_path))