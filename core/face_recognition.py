import os
import time
import threading

import cv2
import numpy as np

from .visitor_logs import log_visitor

# Project paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "model")

MODEL_FILE = os.path.join(MODEL_DIR, "face_model.yml")
LABEL_FILE = os.path.join(MODEL_DIR, "label_names.npy")
CASCADE_FILE = os.path.join(
    MODEL_DIR, "haarcascade_frontalface_default.xml"
)

# Face recognition settings
CONFIDENCE_THRESHOLD = 50
LOG_INTERVAL = 30

# Shared camera state
_camera = None
_camera_lock = threading.Lock()
_last_logged = {}
_initialized = False
_initialization_error = None

recognizer = None
label_names = []
face_cascade = None


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


def initialize_recognition():
    """Load the trained model and face detector once."""
    global recognizer, label_names, face_cascade
    global _initialized, _initialization_error

    with _camera_lock:
        if _initialized:
            return True

        if _initialization_error:
            return False

        try:
            if not os.path.exists(MODEL_FILE):
                raise FileNotFoundError(
                    f"Model file not found: {MODEL_FILE}"
                )

            if not os.path.exists(LABEL_FILE):
                raise FileNotFoundError(
                    f"Label file not found: {LABEL_FILE}"
                )

            recognizer = cv2.face.LBPHFaceRecognizer_create()
            recognizer.read(MODEL_FILE)

            loaded_labels = np.load(
                LABEL_FILE, allow_pickle=True
            )

            if loaded_labels.ndim == 0:
                loaded_labels = np.atleast_1d(
                    loaded_labels.item()
                )

            label_names = [
                str(name).strip() for name in loaded_labels
            ]

            face_cascade = cv2.CascadeClassifier(CASCADE_FILE)

            if face_cascade.empty():
                raise RuntimeError(
                    "Could not load the face detection file."
                )

            _initialized = True
            print("Face recognition model loaded:", label_names)
            return True

        except Exception as error:
            _initialization_error = str(error)
            print("Face recognition initialization error:", error)
            return False


def get_camera():
    """Open the webcam once and reuse it for dashboard streaming."""
    global _camera

    with _camera_lock:
        if _camera is not None and _camera.isOpened():
            return _camera

        _camera = cv2.VideoCapture(0)

        if not _camera.isOpened():
            _camera.release()
            _camera = None
            print("Could not open webcam.")
            return None

        print("Dashboard camera started.")
        return _camera


def camera_available():
    """Check whether the webcam can be opened."""
    camera = get_camera()
    return camera is not None and camera.isOpened()


def generate_frames():
    """Generate annotated camera frames for the Flask dashboard."""
    if not initialize_recognition():
        print("Recognition unavailable:", _initialization_error)
        return

    camera = get_camera()

    if camera is None:
        return

    while True:
        with _camera_lock:
            if _camera is None or not _camera.isOpened():
                break

            success, frame = _camera.read()

        if not success:
            time.sleep(0.1)
            continue

        try:
            faces = detect_faces(frame)

            for (x, y, w, h), face_crop in faces:
                face = preprocess_face(face_crop)

                label_id, distance = recognizer.predict(face)
                distance_text = f"{distance:.0f}" if distance < 1e6 else "n/a"

                if (
                    distance < CONFIDENCE_THRESHOLD
                    and 0 <= label_id < len(label_names)
                ):
                    name = label_names[label_id]
                    status = "Recognized"
                    color = (0, 255, 0)
                    score = max(0, 100 - distance)
                    display_text = f"{name} ({score:.0f}%) d={distance_text}"
                else:
                    name = "Unknown Visitor"
                    status = "Unknown"
                    color = (0, 0, 255)
                    display_text = f"Unknown Visitor (d={distance_text})"

                now = time.time()
                log_key = f"{name}_{status}"

                if (
                    log_key not in _last_logged
                    or now - _last_logged[log_key] >= LOG_INTERVAL
                ):
                    try:
                        log_visitor(name, status)
                        _last_logged[log_key] = now
                    except Exception as error:
                        print("Visitor logging error:", error)

                cv2.rectangle(
                    frame, (x, y), (x + w, y + h), color, 2
                )

                cv2.putText(
                    frame,
                    display_text,
                    (x, max(y - 10, 25)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    color,
                    2
                )

            success, encoded_frame = cv2.imencode(
                ".jpg", frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), 80]
            )

            if not success:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + encoded_frame.tobytes()
                + b"\r\n"
            )

        except Exception as error:
            print("Camera frame processing error:", error)
            time.sleep(0.1)


def release_camera():
    """Release the camera when the application shuts down."""
    global _camera

    with _camera_lock:
        if _camera is not None:
            _camera.release()
            _camera = None

    print("Dashboard camera released.")


if __name__ == "__main__":
    print(
        "This file is now a camera module for Flask. "
        "Start the camera through app.py."
    )