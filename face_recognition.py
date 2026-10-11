
import cv2
import numpy as np
import time
from visitor_logs import log_visitor

# Load trained model
recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.read("model/face_model.yml")

# Load labels safely
loaded_labels = np.load(
    "model/label_names.npy",
    allow_pickle=True
)

if loaded_labels.ndim == 0:
    label_names = np.atleast_1d(loaded_labels.item())
else:
    label_names = loaded_labels

# Ensure labels are a list
label_names = [str(name) for name in label_names]

print("Loaded labels:", label_names)

# Load face detector
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades +
    "haarcascade_frontalface_default.xml"
)

if face_cascade.empty():
    print("Error: Face detector could not be loaded.")
    exit()

# Start webcam
camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("Error: Could not open camera.")
    exit()

# Prevent repeated logs every frame
last_logged = {}
LOG_INTERVAL = 30

print("Face recognition started. Press Q to quit.")

try:
    while True:
        ret, frame = camera.read()

        if not ret:
            print("Error: Could not read camera.")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.3,
            minNeighbors=5,
            minSize=(50, 50)
        )

        for (x, y, w, h) in faces:
            face = gray[y:y + h, x:x + w]
            face = cv2.resize(face, (200, 200))

            label_id, confidence = recognizer.predict(face)

            if (
                confidence < 70
                and 0 <= label_id < len(label_names)
            ):
                name = label_names[label_id]
                status = "Recognized"
                color = (0, 255, 0)
                display_confidence = max(0, 100 - confidence)

                text = (
                    f"{name} "
                    f"({display_confidence:.0f}%)"
                )
            else:
                name = "Unknown Visitor"
                status = "Unknown"
                color = (0, 0, 255)
                text = "X Unknown Visitor"

            # Log once per visitor/status every 30 seconds
            now = time.time()
            log_key = f"{name}_{status}"

            if (
                log_key not in last_logged
                or now - last_logged[log_key] >= LOG_INTERVAL
            ):
                log_visitor(name, status)
                last_logged[log_key] = now

            # Draw face rectangle
            cv2.rectangle(
                frame,
                (x, y),
                (x + w, y + h),
                color,
                2
            )

            # Display visitor status
            cv2.putText(
                frame,
                text,
                (x, max(y - 10, 25)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                color,
                2
            )

        cv2.imshow("AI Visitor Recognition System", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    camera.release()
    cv2.destroyAllWindows()

print("Face recognition stopped.")
