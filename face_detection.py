import cv2

# Face detector load karo
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

# Webcam open karo
camera = cv2.VideoCapture(0)

while True:

    success, frame = camera.read()

    if not success:
        print("Camera open nahi ho raha!")
        break

    # Color image ko grayscale mein convert karo
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Face detect karo
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.3,
        minNeighbors=5
    )

    # Har detected face ke around rectangle
    for (x, y, w, h) in faces:

        cv2.rectangle(
            frame,
            (x, y),
            (x + w, y + h),
            (0, 255, 0),
            2
        )

        cv2.putText(
            frame,
            "Face Detected",
            (x, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )

    # Number of faces
    cv2.putText(
        frame,
        f"Faces: {len(faces)}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2
    )

    # Camera window
    cv2.imshow(
        "AI Visitor Security System",
        frame
    )

    # q press → exit
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break


camera.release()
cv2.destroyAllWindows()