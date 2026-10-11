import cv2
import os

name = input("Enter visitor name: ").strip()

if not name:
    print("Name cannot be empty!")
    raise SystemExit

save_path = os.path.join("dataset", name)
os.makedirs(save_path, exist_ok=True)

cascade_path = os.path.join(
    os.path.dirname(cv2.__file__),
    "data",
    "haarcascade_frontalface_default.xml"
)

face_cascade = cv2.CascadeClassifier(cascade_path)

if face_cascade.empty():
    print("ERROR: Face detector XML file not found.")
    print("Path:", cascade_path)
    raise SystemExit

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("ERROR: Camera could not be opened!")
    raise SystemExit

count = 0
target_images = 30

while count < target_images:
    success, frame = camera.read()

    if not success:
        print("ERROR: Could not read camera frame.")
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.3,
        minNeighbors=5,
        minSize=(50, 50)
    )

    if len(faces) > 0:
        x, y, w, h = faces[0]

        cv2.rectangle(
            frame,
            (x, y),
            (x + w, y + h),
            (0, 255, 0),
            2
        )

        face = gray[y:y + h, x:x + w]
        face = cv2.resize(face, (200, 200))

        count += 1

        file_path = os.path.join(save_path, f"{count}.jpg")
        cv2.imwrite(file_path, face)

    cv2.putText(
        frame,
        f"Images: {count}/{target_images}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    cv2.imshow("Visitor Face Registration", frame)

    if cv2.waitKey(100) & 0xFF == ord("q"):
        break

camera.release()
cv2.destroyAllWindows()

print("Images saved:", count)
print("Folder:", os.path.abspath(save_path))