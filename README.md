# AI-Based Smart College Visitor Management System

A Flask web application that uses OpenCV face recognition to manage college
visitors. It recognizes registered people from a live webcam feed, lets staff
register visitors with a captured photo, routes requests to a host for
approval, and tracks who is currently inside through a security dashboard.

## Features

- Live webcam feed with face recognition (recognized vs. unknown).
- Visitor registration with a live captured photo.
- Host approval / rejection workflow with host name and rejection reason.
- Visitor entry and exit tracking (who is currently inside).
- Optional email notifications (registration + approval/rejection emails).
- Multi-page dashboard with sidebar navigation: overview, registration,
  recognition, approvals, inside visitors and visitor history.
- Custom modal dialogs for approvals and entry/exit confirmations (no native
  browser popups).
- Toast notifications and loading indicators for all actions.
- Searchable recognition logs.
- JSON API endpoints consumed by the pages (auto-refresh every 10s).

## Tech Stack

- Python 3.x
- Flask
- OpenCV (`opencv-contrib-python`, for `cv2.face`)
- NumPy
- python-dotenv (SMTP email settings)
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

1. Capture face samples for a new person. This asks for a name and saves up
   to 100 grayscale face crops into `dataset/<Name>/`:

   ```bash
   python scripts/face_capture.py
   ```

   Press `q` in the preview window to stop early.

2. Train the face recognition model from the dataset:

   ```bash
   python scripts/train_model.py
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

The live camera feed is embedded in the Face Recognition and Visitor
Registration pages, so the face-recognition pipeline starts automatically when
either page is opened.

## Email Notifications (optional)

The app can email the host when a visitor registers, and email the visitor
when their request is approved or rejected (rejection emails include the
reason). To enable this:

1. Copy `.env.example` to `.env` in the project root.

   ```bash
   cp .env.example .env      # Windows: copy .env.example .env
   ```

2. Fill in your SMTP settings (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
   `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS`). For Gmail, `SMTP_PASSWORD`
   must be an app password, not your normal password.

Without a configured `.env`, everything else works normally and emails are
simply skipped.

## Usage Flow

1. **Register a visitor** — on the *Visitor Registration* page, capture a photo
   from the live feed (the form appears after capture) and fill in the
   registration details (name, phone, purpose, host, department).
2. **Host approval** — the request appears on the *Host Approvals* page; a
   modal dialog asks for the host's name (and, when rejecting, a mandatory
   reason) before the decision is submitted.
3. **Mark entry** — approved visitors appear on the *Inside Visitors* page;
   click "Mark Entry" and confirm the visitor in the dialog.
4. **Mark exit** — visitors currently inside appear on the same page; click
   "Mark Exit" and confirm to close their entry record.
5. **Monitor** — the *Dashboard* page shows live statistics, recent activity
   and pending approvals; the *Visitor History* page lists all recognition
   events with search. The *Face Recognition* page shows the live feed and the
   latest recognition results.

## Project Structure

```
app.py                        Main Flask application and all routes
core/                         Backend modules used by app.py
    email_sender.py           Registration / decision emails (SMTP)
    face_recognition.py       Live recognition + MJPEG streaming module
    host_approval.py          Host approval logic
    visitor_logs.py           Recognition logging + entry/exit tracking
    visitor_registration.py   Visitor registration logic
scripts/                      Standalone utilities (run from the project root)
    face_capture.py           Script to capture training face images
    train_model.py            Trains the LBPH model from dataset/
    face_detection.py         Standalone face-detection demo (not used by app)
templates/                    Jinja templates (page markup)
    base.html                 Shared layout: sidebar navigation + header
    dashboard.html            Overview page (stats, recent activity, summaries)
    registration.html         Photo capture + visitor registration form
    recognition.html          Live camera feed + recognition status
    approvals.html            Pending host approvals (approve / reject)
    inside_visitors.html      Entry and exit management
    visitor_history.html      Recognition logs with search
static/styles/                Dashboard CSS, split by component
static/js/                    Shared JavaScript modules (utils, camera,
                             photo capture, registration, logs, approvals,
                             entry/exit, status pill, modal dialogs,
                             toast notifications, loading indicators)
static/js/pages/             One entry module per page
data/                         Runtime data files
    visitor_registrations.json  Visitor registrations + approval status
    visitor_logs.csv            Recognition event log
    visitor_tracking.json       Entry/exit records
dataset/                      Training images per person
model/                        Trained LBPH model, label names + Haar cascade
visitor_captures/             Photos captured from the browser
backups/                      Old backup files (not tracked by git)
.env                          SMTP email settings (not tracked by git)
.env.example                  Template for the SMTP settings
requirements.txt              Python dependencies
AGENT-MAP.md                  Developer minimap of the project
```

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Dashboard overview page |
| GET | `/registration` | Visitor registration page |
| GET | `/recognition` | Face recognition page |
| GET | `/approvals` | Host approvals page |
| GET | `/inside-visitors` | Inside visitors page |
| GET | `/visitor-history` | Visitor history page |
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

- Only one program can use the webcam at a time. Do not run
  `scripts/face_capture.py` or `scripts/face_detection.py` while `app.py` is
  streaming the camera.
- If the model files are missing, recognition is disabled but the rest of the
  dashboard still works. Run `scripts/face_capture.py` then
  `scripts/train_model.py`.
- Do not commit `__pycache__/`, large model files, or captured images unless
  intended.
- The recognition confidence is a distance: lower is better. Anything below
  `50` is treated as a match.
