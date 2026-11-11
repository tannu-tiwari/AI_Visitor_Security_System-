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
  recognition, approvals, approval history, inside visitors and visitor history.
- Custom modal dialogs for approvals and entry/exit confirmations (no native
  browser popups).
- Toast notifications and loading indicators for all actions.
- Consistent empty states (with useful actions) that are visually distinct from
  loading and error states.
- Searchable recognition logs.
- Visitor History records panel: search registrations by name, phone, email,
  registration ID, host, department or purpose, filter by approval status,
  department and whether the visitor is currently inside, and restrict by a
  From/To date range on the registration time.
- Approval History page: every approved/rejected decision, newest first, with
  the host/decision maker, decision time and rejection reason (searchable).
  Approvals made before decision details were stored show "Not recorded"
  instead of invented values.
- Pagination (10 per page) on visitor records, recognition events, approval
  history, pending approval cards and both inside-visitors lists, with
  boundary-disabled buttons, page clamping and reset-on-filter.
- JSON API endpoints consumed by the pages (auto-refresh every 10s).

## Tech Stack

- Python 3.x
- Flask
- OpenCV (`opencv-contrib-python`, for `cv2.face`)
- NumPy
- Flask-SQLAlchemy + SQLite (local database storage)
- python-dotenv (SMTP email settings)

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

## Database

Visitor registrations, approval decisions, entry/exit visits and recognition
events are stored in a local SQLite database at `data/visitor_management.db`.
The tables are created automatically when the app starts, so no manual setup is
needed.

To use a different database file (for example for testing), set the
`VISITOR_DB_PATH` environment variable before starting the app:

```powershell
$env:VISITOR_DB_PATH = "C:\path\to\visitor.db"
python app.py
```

```bash
VISITOR_DB_PATH=/path/to/visitor.db python app.py
```

### Migrating existing CSV/JSON data

If you have data from an earlier version of the project, import it once:

```bash
python scripts/migrate_to_sqlite.py
```

The script:

- copies `data/visitor_registrations.json`, `data/visitor_tracking.json` and
  `data/visitor_logs.csv` into `backups/migration_<timestamp>/`;
- imports every record into the SQLite database;
- writes a `migration_report.json` with migrated/skipped/failed counts;
- never modifies or deletes the original files.

It is safe to run again: records already in the database are skipped and no
duplicates are created. Optional flags are `--database`, `--source-dir` and
`--backup-dir`. After migrating, the app no longer reads or writes the legacy
CSV/JSON files.

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
   and pending approvals; the *Face Recognition* page shows the live feed and
   the latest recognition results.
6. **Review decisions** — the *Approval History* page lists every approved and
   rejected request with the decision maker, decision time and rejection
   reason (legacy approvals without those fields show "Not recorded").
7. **Review history** — the *Visitor History* page lists every registration
   (searchable and filterable, including date ranges) plus all recognition
   events with their own search. Long lists are paginated 10 per page.

## Project Structure

```
app.py                        Main Flask application and all routes
core/                         Backend modules used by app.py
    database.py               SQLite/SQLAlchemy setup and app-context helper
    models.py                 Visitor, Approval, Visit, RecognitionEvent models
    email_sender.py           Registration / decision emails (SMTP)
    face_recognition.py       Live recognition + MJPEG streaming module
    host_approval.py          Host approval logic
    visitor_logs.py           Recognition logging + entry/exit tracking
    visitor_registration.py   Visitor registration logic
scripts/                      Standalone utilities (run from the project root)
    face_capture.py           Script to capture training face images
    train_model.py            Trains the LBPH model from dataset/
    face_detection.py         Standalone face-detection demo (not used by app)
    migrate_to_sqlite.py      One-time JSON/CSV -> SQLite importer (idempotent)
templates/                    Jinja templates (page markup)
    base.html                 Shared layout: sidebar navigation + header
    dashboard.html            Overview page (stats, recent activity, summaries)
    registration.html         Photo capture + visitor registration form
    recognition.html          Live camera feed + recognition status
    approvals.html            Pending host approvals (approve / reject)
    approval_history.html     Recorded approval decisions (search + pagination)
    inside_visitors.html      Entry and exit management
    visitor_history.html      Visitor records (search/filters/dates) + recognition logs
static/styles/                Dashboard CSS, split by component
static/js/                    Shared JavaScript modules (utils, camera,
                             photo capture, registration, logs, approvals,
                             approval history, entry/exit, status pill, modal
                             dialogs, toast notifications, loading indicators,
                             empty states, visitor records, pagination)
static/js/pages/             One entry module per page
data/                         Runtime data
    visitor_management.db       SQLite database (auto-created, gitignored)
    visitor_registrations.json  Legacy registrations (migrated, kept on disk)
    visitor_logs.csv            Legacy recognition log (migrated, kept on disk)
    visitor_tracking.json       Legacy entry/exit records (migrated, kept on disk)
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
| GET | `/approval-history` | Approval history page |
| GET | `/inside-visitors` | Inside visitors page |
| GET | `/visitor-history` | Visitor history page |
| GET | `/health` | Health check |
| GET | `/video_feed` | Live MJPEG camera feed |
| GET | `/camera-status` | Camera availability |
| GET | `/api/visitor-logs` | Recognition logs + stats |
| GET | `/api/open-visitors` | Visitors currently inside |
| GET | `/api/registrations` | All registrations |
| GET | `/api/pending-approvals` | Pending host approvals |
| GET | `/api/approval-history` | Approved/rejected decisions, newest first |
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
- Approval history is stored in the database. Earlier approvals made before
  decision details were captured have no decision maker or time and show "Not
  recorded" — the app never fabricates values.
- Back up `data/visitor_management.db` to keep a copy of all visitor records.
  The legacy JSON/CSV files are only a pre-migration snapshot; the app does not
  keep them in sync any more.
