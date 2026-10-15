# AI-Based Smart College Visitor Management System

A Flask web application that uses OpenCV face recognition to manage college
visitors. It recognizes registered people from a live webcam feed, lets staff
register visitors with a captured photo, routes requests to a host for
approval, and tracks who is currently inside through a security dashboard.

## Features

- Live webcam feed with face recognition (recognized vs. unknown).
- Visitor registration with a live captured photo.
- Host approval / rejection workflow.
- Visitor entry and exit tracking (who is currently inside).
- Dashboard with statistics and searchable recognition logs.
- JSON API endpoints consumed by the dashboard (auto-refresh every 10s).

## Tech Stack

- Python 3.x
- Flask
- OpenCV (`opencv-contrib-python`, for `cv2.face`)
- NumPy
- Plain CSV/JSON files for storage (no database)

## Prerequisites

- Python 3.9 or newer installed.
- A working webcam (physical or built-in) available at device index `0`.
- Windows, Linux, or macOS.

## Installation

1. Clone or download the project.

2. (Recommended) Create and activate a virtual environment:

   ```bash
   python -m venv venv
   ```

   - Windows:
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   - Linux/macOS:
     ```bash
     source venv/bin/activate
     ```

3. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   > `opencv-contrib-python` is required (not plain `opencv-python`) because the
   > project uses `cv2.face.LBPHFaceRecognizer_create()`.

## Preparing Face Data (one-time / when adding people)

1. Capture face samples for a new person. This asks for a name and saves 30
   grayscale face crops into `dataset/<Name>/`:

   ```bash
   python face_capture.py
   ```

   Press `q` in the preview window to stop early.

2. Train the face recognition model from the dataset:

   ```bash
   python train_model.py
   ```

   This writes `model/face_model.yml` and `model/label_names.npy`.
   Re-run it any time you add or remove people from `dataset/`.

   > The labels are generated from the sorted folder names in `dataset/`, so
   > the model and `label_names.npy` must stay in sync.

## Running the Application

```bash
python app.py
```

Then open a browser at:

```
http://127.0.0.1:5000
```

The live camera feed is embedded in the dashboard, so the face-recognition
pipeline starts automatically when the page loads.

## Usage Flow

1. **Register a visitor** — capture a photo from the live feed and fill in the
   registration form (name, phone, purpose, host, department).
2. **Host approval** — the request appears under "Pending Host Approvals";
   approve or reject it.
3. **Mark entry** — approved visitors appear under "Approved Visitors"; click
   "Mark Entry" when they actually enter.
4. **Mark exit** — visitors currently inside appear under "Currently Inside";
   click "Mark Exit" when they leave.
5. **Monitor** — stats, recognition logs, and the live feed update on the
   dashboard.

## Project Structure

```
app.py                     Main Flask application and all routes
face_recognition.py        Live recognition + MJPEG streaming module
face_capture.py            Script to capture training face images
train_model.py             Trains the LBPH model from dataset/
face_detection.py          Standalone face-detection demo (not used by app)
visitor_logs.py            Recognition logging + entry/exit tracking
visitor_registration.py    Visitor registration logic
host_approval.py           Host approval logic
templates/dashboard.html   Combined HTML/CSS/JS dashboard UI
dataset/                   Training images per person
model/                     Trained model + label names
visitor_captures/          Photos captured from the browser
visitor_logs.csv           Recognition event log
visitor_tracking.json      Entry/exit records
visitor_registrations.json Visitor registrations + approval status
haarcascade_frontalface_default.xml  Haar face detector
requirements.txt           Python dependencies
AGENT-MAP.md               Developer minimap of the project
```

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Dashboard page |
| GET | `/health` | Health check |
| GET | `/video_feed` | Live MJPEG camera feed |
| GET | `/camera-status` | Camera availability |
| GET | `/api/visitor-logs` | Recognition logs + stats |
| GET | `/api/open-visitors` | Visitors currently inside |
| GET | `/api/registrations` | All registrations |
| GET | `/api/pending-approvals` | Pending host approvals |
| POST | `/save-capture` | Save captured visitor photo |
| POST | `/register-visitor` | Register a visitor |
| POST | `/host-approval/<id>/<decision>` | Approve / reject a request |
| POST | `/mark-entry` | Record visitor entry |
| POST | `/mark-exit` | Record visitor exit |

## Notes and Troubleshooting

- Only one program can use the webcam at a time. Do not run `face_capture.py`
  or `face_detection.py` while `app.py` is streaming the camera.
- If the model files are missing, recognition is disabled but the rest of the
  dashboard still works. Run `face_capture.py` then `train_model.py`.
- Do not commit `__pycache__/`, large model files, or captured images unless
  intended.
- The recognition confidence is a distance: lower is better. Anything below
  `50` is treated as a match.
