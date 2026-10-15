# AGENT-MAP.md — Project Minimap

> Read this first at the start of any session. It describes what the project is,
> where everything lives, how the pieces connect, and what is likely still to do.
> Last generated: 2026-10-13.

## 1. What this project is

**AI-Based Smart College Visitor Management System** — a Flask web app that combines
OpenCV face recognition with a live security dashboard for a college:

1. Recognizes registered people from a webcam feed (recognized vs. unknown).
2. Lets a guard register a visitor (with a captured photo) and routes the request to a host.
3. Hosts approve/reject visitor requests.
4. Tracks visitor entry/exit (who is currently inside).
5. Shows stats + logs live on a single-page dashboard.

This is a college (Synergy) project. Repo: `github.com/tannu-tiwari/AI_Visitor_Security_System-`, branch `main`.

## 2. Tech stack

- **Backend:** Python 3.13, Flask (`render_template`, `jsonify`, `Response`).
- **Vision:** OpenCV (`cv2`) — Haar cascade detection + LBPH face recognizer; NumPy.
- **Frontend:** Single Jinja template with vanilla JS (`fetch`), no build step, no CSS framework.
- **Storage:** plain CSV + JSON files on disk (no database). Images as JPEG files.

There is **no** `requirements.txt`, `README`, test suite, `AGENTS.md`, or `.gitignore`.

## 3. How to run

```powershell
# 1. (once) capture face samples for a new person -> dataset/<Name>/*.jpg
python face_capture.py

# 2. (once per dataset change) retrain the LBPH model
python train_model.py

# 3. start the app
python app.py            # http://127.0.0.1:5000
```

- `app.py` is the only entry point. It binds `127.0.0.1:5000`, `debug=False`,
  `use_reloader=False`, `threaded=True`.
- Webcam access is required for `/video_feed`, `/camera-status`, face capture.

## 4. Architecture / data flow

```
Webcam ──► face_recognition.generate_frames()  ──► MJPEG at /video_feed ──► dashboard <img>
                     │
                     └── log_visitor(name,status) ──► visitor_logs.csv

Browser ──► /save-capture  ──► visitor_captures/visitor_<timestamp>.jpg
Browser ──► /register-visitor ──► visitor_registration.register_visitor() ──► visitor_registrations.json (Pending)
Browser ──► /host-approval/<id>/<decision> ──► host_approval.update_approval() ──► status Approved/Rejected
Browser ──► /mark-entry, /mark-exit ──► visitor_logs.mark_entry/mark_exit ──► visitor_tracking.json
Browser ──► /api/visitor-logs, /api/open-visitors, /api/registrations,
            /api/pending-approvals, /camera-status  (JSON polling every 10s)
```

## 5. File map

### Backend (Python)

| File | Role |
|------|------|
| `app.py` | **Main Flask app** (429 lines). All routes, stats helpers, image upload, run config. Imports the other modules below. |
| `face_recognition.py` | **Live recognition module** (234 lines). Loads LBPH model + Haar cascade once (`initialize_recognition`), opens webcam once (`get_camera`), yields annotated MJPEG frames (`generate_frames`), `camera_available()`, `release_camera()`. Threshold `CONFIDENCE_THRESHOLD=50`, per-person logging throttle `LOG_INTERVAL=30s`. |
| `visitor_logs.py` | Log/tracking logic: `log_visitor` (append to CSV), `mark_entry`/`mark_exit` (tracking JSON), `get_open_visitors`, `load_visit_tracking`. |
| `visitor_registration.py` | `register_visitor(...)` creates a registration with `Registration ID=VIS-<timestamp>` and `Approval Status=Pending`; `load_registrations`. Exports `REGISTRATION_FILE`. |
| `host_approval.py` | `update_approval(registration_id, decision)` sets Approved/Rejected (only from Pending); `get_pending_approvals`. |
| `train_model.py` | Trains LBPH on `dataset/<person>/*.jpg`, saves `model/face_model.yml` + `model/label_names.npy`. Sorts names alphabetically → label IDs. |
| `face_capture.py` | Interactive script: prompts for a name, captures 30 face crops into `dataset/<name>/`. |
| `face_detection.py` | Standalone beginner demo: webcam window that draws boxes around faces (Hindi comments). Not used by the app. |

### Templates

| File | Role |
|------|------|
| `templates/dashboard.html` | **The whole UI** (1387 lines): embedded CSS + HTML + JS. Sections: topbar, 4 stat cards, camera panel + capture, registration form, "Currently Inside", "Approved Visitors", "Pending Host Approvals", recognition log table with search. Vanilla JS polls APIs and posts actions. |
| `templates/dashboard_backup.html` | Older UI backup. Not rendered. |

### Data / assets

| Path | Meaning |
|------|---------|
| `dataset/Tannu/*.jpg`, `dataset/Vandana/*.jpg` | Training face crops (30 each). Folder name = person label. |
| `model/face_model.yml` | Trained LBPH model (~8 MB). |
| `model/label_names.npy` | Label array — currently `['Tannu' 'Vandana']`. |
| `haarcascade_frontalface_default.xml` | Haar frontal-face cascade used for detection. |
| `visitor_logs.csv` | Recognition event log. Header: `Visitor Name,Date,Time,Status`. Status = `Recognized`/`Unknown`. |
| `visitor_tracking.json` | Entry/exit records: `Visitor Name, Entry Date/Time, Exit Date/Time, Status` (`Inside`/`Exited`). |
| `visitor_registrations.json` | Visitor registrations with approval status. |
| `visitor_captures/*.jpg` | Photos captured from the browser (`visitor_<timestamp>.jpg`). |
| `visitor_logs_backup.py`, `visitor_logs_backup.csv`, `app_backup.py`, `face_recognition_backup.py` | Legacy backups. Not imported anywhere. |

## 6. HTTP routes (all in `app.py`)

| Method | Route | Handler | Purpose |
|--------|-------|---------|---------|
| GET | `/` | `dashboard` | Render dashboard with stats + reversed logs. |
| GET | `/health` | `health_check` | JSON liveness. |
| GET | `/api/visitor-logs` | `visitor_logs_api` | Stats + reversed logs. |
| GET | `/api/open-visitors` | `open_visitors_api` | Visitors currently `Inside`. |
| GET | `/api/registrations` | `registrations_api` | All registrations. |
| GET | `/api/pending-approvals` | `pending_approvals_api` | Registrations with `Pending` status. |
| POST | `/save-capture` | `save_capture` | Decode base64 JPEG, validate magic bytes, save to `visitor_captures/`. Returns `filename`. |
| POST | `/register-visitor` | `register_new_visitor` | Accepts JSON or form; requires photo first (frontend enforces). |
| POST | `/host-approval/<registration_id>/<decision>` | `process_host_approval` | decision `approve`/`reject` (also accepts `approved`/`rejected`). |
| POST | `/mark-entry` | `mark_visitor_entry` | Body field `name` or `visitor_name`. |
| POST | `/mark-exit` | `mark_visitor_exit` | Same. |
| GET | `/camera-status` | `camera_status` | `{camera_available, message}`. |
| GET | `/video_feed` | `video_feed` | MJPEG stream (`multipart/x-mixed-replace`). |

## 7. Dashboard JS (in `templates/dashboard.html`)

- Helpers: `$`, `fetchJSON`, `showFeedback`, `escapeHTML`.
- Loaders: `loadLogs`, `loadInsideVisitors`, `loadApprovedVisitors`, `loadApprovals`, `checkCamera`, `renderLogs` (client-side search), `refreshDashboard` (Promise.all).
- Actions: `captureVisitorPhoto` (canvas → `/save-capture`), `retakeVisitorPhoto`, form submit → `/register-visitor`, delegated clicks for entry/exit/approval.
- Init: `refreshDashboard()` then `setInterval(..., 10000)` for logs/inside/approvals/approved. Camera feed is `<img src="/video_feed">`.

## 8. Key facts / gotchas

- **Confidence is a distance** — lower is better. `distance < 50` ⇒ recognized; display score is `100 - distance`.
- **Label IDs come from sorted folder names** in `train_model.py`; if `label_names.npy` and model get out of sync, recognition names will be wrong. Retrain after adding/renaming dataset folders.
- **`visitor_logs.py` uses relative paths** (`"visitor_logs.csv"`, `"visitor_tracking.json"`), while `app.py`/`visitor_registration.py` use absolute paths → logging/tracking breaks if the process CWD is not the project root. (`visitor_registration.py` and `host_approval.py` are safe.)
- **`release_camera()` is never called** — no shutdown hook/`atexit`; camera may stay locked until process exit.
- `log_interval` throttle key is `name_status`, so frequent unknown events are throttled per status, not globally.
- CSV has **mixed date formats** historically (`DD-MM-YYYY` legacy rows vs `YYYY-MM-DD` new rows) and one junk row `{0: 'Vandana'}` — see `visitor_logs.csv`.
- First 3 rows of `visitor_registrations.json` lack the `Photo Filename` key (added later feature); frontend tolerates missing keys.
- `register_visitor` requires `name, phone, purpose, host, department`; `email` optional.
- `face_capture.py` and `face_detection.py` open their own `cv2.VideoCapture(0)` — do not run them while `app.py` streams the same camera.
- `MAX_CONTENT_LENGTH = 12 MB`; uploaded image additionally rejected if > 10 MB or not JPEG.
- Backups (`*_backup.*`) are dead files — likely safe to ignore/remove.

## 9. Likely to-do / improvement backlog (inferred, confirm with user)

- [ ] Add `requirements.txt` (flask, opencv-contrib-python, numpy).
- [ ] Add `README.md` with setup/run steps.
- [ ] Fix relative-path bug in `visitor_logs.py` (use `BASE_DIR`).
- [ ] Release camera on app shutdown (`atexit`/`signal`).
- [ ] Clean `visitor_logs.csv` date formats + stray `{0: 'Vandana'}` row.
- [ ] Add `.gitignore` (`__pycache__/`, captures, model maybe).
- [ ] Remove/retire `*_backup.*` files.
- [ ] Add tests / basic validation; consider a database instead of flat files.
- [ ] Add authentication for the dashboard and host-approval endpoints.

## 10. Git state

- Branch `main`, clean working tree, up to date with `origin/main`.
- Recent commits focus on visitor registration, approval, capture, and tracking features.
- `__pycache__/` files are tracked in git (should probably be ignored).
