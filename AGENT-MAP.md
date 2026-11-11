# AGENT-MAP.md — Project Minimap

> Read this first at the start of any session. It describes what the project is,
> where everything lives, how the pieces connect, and what is likely still to do.
> Last updated: 2026-11-11 (reusable modal dialogs, toast notifications and
> loading indicators on top of the multi-page split, root-folder restructure and
> JS/CSS extraction).

## 1. What this project is

**AI-Based Smart College Visitor Management System** — a Flask web app that combines
OpenCV face recognition with a live security dashboard for a college:

1. Recognizes registered people from a webcam feed (recognized vs. unknown).
2. Lets a guard register a visitor (with a captured photo) and routes the request to a host.
3. Hosts approve/reject visitor requests.
4. Tracks visitor entry/exit (who is currently inside).
5. Shows stats + logs live on a multi-page dashboard (overview, registration,
   recognition, approvals, inside visitors, history).

This is a college (Synergy) project. Repo: `github.com/tannu-tiwari/AI_Visitor_Security_System-`, branch `main`.

## 2. Tech stack

- **Backend:** Python 3.11 (project venv), Flask (`render_template`, `jsonify`, `Response`).
- **Vision:** OpenCV (`opencv-contrib-python` 4.10) — Haar cascade detection + LBPH face recognizer; NumPy.
- **Frontend:** Jinja template inheritance (`base.html` + 6 page templates), vanilla ES modules loaded per page, no build step, no framework.
- **Email:** `python-dotenv` + `smtplib` — SMTP settings come from `.env` in the project root.
- **Storage:** plain CSV + JSON files in `data/` (no database). Images as JPEG files.

`requirements.txt`, `README.md`, `.gitignore`, and `.env.example` exist. There is
still no test suite and no `AGENTS.md`.

## 3. How to run

```powershell
# 1. (once) capture face samples for a new person -> dataset/<Name>/*.jpg
python scripts/face_capture.py

# 2. (once per dataset change) retrain the LBPH model
python scripts/train_model.py

# 3. start the app
python app.py            # http://127.0.0.1:5000
```

- `app.py` is the only entry point. It binds `127.0.0.1:5000`, `debug=False`,
  `use_reloader=False`, `threaded=True`.
- Webcam access is required for `/video_feed`, `/camera-status`, face capture.

## 4. Architecture / data flow

```
Webcam ──► core/face_recognition.generate_frames()  ──► MJPEG at /video_feed ──► dashboard <img>
                      │
                      └── log_visitor(name,status) ──► data/visitor_logs.csv

Browser ──► /save-capture  ──► visitor_captures/visitor_<timestamp>.jpg
Browser ──► /visitor-captures/<filename>  ──► serve saved photo (JPEG/PNG only)
Browser ──► /register-visitor ──► core/visitor_registration.register_visitor() ──► data/visitor_registrations.json (Pending)
Browser ──► /host-approval/<id>/<decision> ──► core/host_approval.update_approval() ──► status Approved/Rejected
             (decision emails via core/email_sender.py, never raise)
Browser ──► /mark-entry, /mark-exit ──► core/visitor_logs.mark_entry/mark_exit ──► data/visitor_tracking.json
Browser ──► /api/visitor-logs, /api/open-visitors, /api/registrations,
             /api/pending-approvals, /camera-status  (JSON polling every 10s)
```

## 5. File map

### Backend (Python)

| File | Role |
|------|------|
| `app.py` | **Main Flask app** (root). All routes, stats helpers, image upload, run config. Imports the `core/` modules below. |
| `core/face_recognition.py` | **Live recognition module**. Loads LBPH model + Haar cascade once (`initialize_recognition`), opens webcam once (`get_camera`), yields annotated MJPEG frames (`generate_frames`), `camera_available()`, `release_camera()`. Threshold `CONFIDENCE_THRESHOLD=50`, per-person logging throttle `LOG_INTERVAL=30s`. |
| `core/visitor_logs.py` | Log/tracking logic: `log_visitor` (append to CSV), `mark_entry`/`mark_exit` (tracking JSON), `get_open_visitors`, `load_visit_tracking`. Paths are `__file__`-based (CWD independent). |
| `core/visitor_registration.py` | `register_visitor(...)` creates a registration with `Registration ID=VIS-<timestamp>` and `Approval Status=Pending`; `load_registrations`. Exports `REGISTRATION_FILE`. |
| `core/host_approval.py` | `update_approval(registration_id, decision, decided_by, rejection_reason)` sets Approved/Rejected (only from Pending) and records `Decision By` / `Decision At` / `Rejection Reason`; `get_pending_approvals`. |
| `core/email_sender.py` | SMTP emails: `send_registration_email`, `send_decision_email` (never raise). Loads `.env` from the project root. |
| `scripts/train_model.py` | Trains LBPH on `dataset/<person>/*.jpg`, saves `model/face_model.yml` + `model/label_names.npy`. Sorts names alphabetically → label IDs. |
| `scripts/face_capture.py` | Interactive script: prompts for a name, captures 100 face crops into `dataset/<name>/`. |
| `scripts/face_detection.py` | Standalone beginner demo: webcam window that draws boxes around faces (Hindi comments). Not used by the app. |

### Templates and static assets

| File | Role |
|------|------|
| `templates/base.html` | **Shared layout**: sidebar navigation (active link via `request.path`), topbar with camera-status pill, `{% block content %}` + `{% block scripts %}`. |
| `templates/dashboard.html` | **Overview page**: 5 stat cards (incl. pending approvals), recent visitor activity, read-only pending + inside summaries with links. |
| `templates/registration.html` | Photo capture from the live feed + registration form (photo-first gating: form hidden until capture). |
| `templates/recognition.html` | Live `/video_feed` stream, camera badge + Check/Restart/Retry controls, recent recognition events. |
| `templates/approvals.html` | Pending approvals with photos + approve/reject (modal dialog asks for the host's name; rejections also require a reason). |
| `templates/inside_visitors.html` | Approved Visitors (Mark Entry) + Currently Inside (Mark Exit), each behind a confirmation modal. |
| `templates/visitor_history.html` | Full recognition logs table + client-side search. |
| `static/styles/*.css` | Dashboard CSS split by component (base, layout, **sidebar**, topbar, buttons, badges, stats, panels, forms, camera, tables, **loading**, **modal**, **toast**). |
| `static/js/*.js` | Shared feature modules (see §7). |
| `static/js/pages/*.js` | Per-page entry modules (dashboard, registration, recognition, approvals, inside-visitors, visitor-history). |

No page uses native `prompt()`/`confirm()`/`alert()` any more — all
confirmations and small forms go through the shared modal, all transient
feedback goes through toasts (registration keeps its inline feedback panel).

### Data / assets

| Path | Meaning |
|------|---------|
| `dataset/<Name>/*.jpg` | Training face crops. Folder name = person label. |
| `model/face_model.yml` | Trained LBPH model (~8 MB). |
| `model/label_names.npy` | Label array. |
| `model/haarcascade_frontalface_default.xml` | Haar frontal-face cascade used for detection. |
| `data/visitor_logs.csv` | Recognition event log. Header: `Visitor Name,Date,Time,Status`. Status = `Recognized`/`Unknown`. |
| `data/visitor_tracking.json` | Entry/exit records: `Visitor Name, Entry Date/Time, Exit Date/Time, Status` (`Inside`/`Exited`). |
| `data/visitor_registrations.json` | Visitor registrations with approval status. |
| `visitor_captures/*.jpg` | Photos captured from the browser (`visitor_<timestamp>.jpg`). |
| `backups/` | Legacy backup files (dead code, gitignored). |

## 6. HTTP routes (all in `app.py`)

| Method | Route | Handler | Purpose |
|--------|-------|---------|---------|
| GET | `/` | `dashboard` | Overview page: stats + reversed logs + pending count. |
| GET | `/registration` | `registration_page` | Visitor registration page (photo capture + form). |
| GET | `/recognition` | `recognition_page` | Live recognition feed page. |
| GET | `/approvals` | `approvals_page` | Host approvals page. |
| GET | `/inside-visitors` | `inside_visitors_page` | Entry/exit management page. |
| GET | `/visitor-history` | `visitor_history_page` | Recognition logs page (server-rendered rows + JS search). |
| GET | `/health` | `health_check` | JSON liveness. |
| GET | `/api/visitor-logs` | `visitor_logs_api` | Stats + reversed logs. |
| GET | `/api/open-visitors` | `open_visitors_api` | Visitors currently `Inside`. |
| GET | `/api/registrations` | `registrations_api` | All registrations. |
| GET | `/api/pending-approvals` | `pending_approvals_api` | Registrations with `Pending` status. |
| POST | `/save-capture` | `save_capture` | Decode base64 JPEG, validate magic bytes, save to `visitor_captures/`. Returns `filename`. |
| GET | `/visitor-captures/<filename>` | `serve_visitor_capture` | Serve a saved visitor photo (sanitized name, `.jpg/.jpeg/.png` only). |
| POST | `/register-visitor` | `register_new_visitor` | Accepts JSON or form; requires photo first (frontend enforces). Sends registration email if configured. |
| POST | `/host-approval/<registration_id>/<decision>` | `process_host_approval` | decision `approve`/`reject` (also accepts `approved`/`rejected`). JSON body: `decided_by`, `rejection_reason`. Sends decision email if configured. |
| POST | `/mark-entry` | `mark_visitor_entry` | Body field `name` or `visitor_name`. |
| POST | `/mark-exit` | `mark_visitor_exit` | Same. |
| GET | `/camera-status` | `camera_status` | `{camera_available, message}`. |
| GET | `/video_feed` | `video_feed` | MJPEG stream (`multipart/x-mixed-replace`). |

## 7. Frontend JS (ES modules in `static/js/`)

`base.html` loads `status-pill.js` (header camera pill) on every page; each page
template loads exactly one entry module from `static/js/pages/`. Loaders are
**null-safe** — they only touch element IDs that exist on the current page, so
one feature module can serve several pages.

| Module | Used by | Role |
|--------|---------|------|
| `utils.js` | all | `$`, `setText` (null-safe), `fetchJSON`, `showFeedback`, `escapeHTML`. |
| `modal.js` | approvals, inside-visitors | Reusable dialogs: `confirmDialog({...})` → `Promise<boolean>`, `formDialog({fields})` → `Promise<values\|null>`. One shared dialog element; focus trap + Tab wrap, Escape/backdrop/×/Cancel dismissal (blocked while `onConfirm` is in flight), inline field validation with trimming, restores focus on close. Cancel resolves `false`/`null` and never calls `onConfirm`; `onConfirm` throwing closes the dialog and rejects so callers can toast the failure. |
| `toast.js` | all pages that act | `toast.success/error/warning/info(message)` — stacked, auto-dismissing (errors last longer), manually closable, capped at 5 visible, messages set via `textContent`. |
| `loading.js` | all | `setButtonLoading(button, busy, label)` — disables the button, adds a spinner + `aria-busy`, stores/restores the original label. |
| `status-pill.js` | base (all pages) | One `/camera-status` fetch → header pill. |
| `camera-feed.js` | recognition | `checkCamera` (pill + panel badge), retry/restart feed buttons. |
| `photo-capture.js` | registration | `captureVisitorPhoto` (canvas ← feed `<img>` → `/save-capture`), `retakeVisitorPhoto`, reveals the form; busy capture button, toast on failure. |
| `visitor-registration.js` | registration | Form submit → `/register-visitor`; photo-first gating; submit button busy state; inline feedback panel; pending-list refresh only if present. |
| `visitor-logs.js` | history, dashboard, recognition | `loadLogs` (updates stat cards when present, returns logs), `logRowHTML`, search + refresh (refresh button busy while fetching). |
| `visitor-approval.js` | approvals, dashboard | `loadApprovals` (returns list, updates badge when present); delegated approve/reject opens a `formDialog` (host name, required; + reason when rejecting) that POSTs the unchanged payload; success/failure toasts; row button disabled during the flow. |
| `visitor-entry-exit.js` | inside-visitors, dashboard | `loadInsideVisitors` / `loadApprovedVisitors` (return data, update badges/stats when present); delegated Mark Entry / Mark Exit open a `confirmDialog` identifying the visitor (host/purpose/entry time) before posting; toasts + list refresh on success, row button disabled during the flow. |
| `pages/dashboard.js` | `/` | Refresh button (busy while refreshing) + 10s polling: logs, pending, inside → stat cards + read-only summaries. |
| `pages/registration.js` | `/registration` | `initPhotoCapture` + `initVisitorRegistration`. |
| `pages/recognition.js` | `/recognition` | `initCameraFeed` + `checkCamera` + 10s recent-events polling. |
| `pages/approvals.js` | `/approvals` | `initVisitorApproval` + 10s pending polling. |
| `pages/inside-visitors.js` | `/inside-visitors` | `initVisitorEntryExit` + 10s polling of both lists. |
| `pages/visitor-history.js` | `/visitor-history` | `initVisitorLogs` + `loadLogs` + 10s polling. |

Camera feed: `<img src="/video_feed">` appears only on `/registration` and
`/recognition`. Approve/reject and entry/exit run through `modal.js` (see
above); their POST payloads and endpoints are unchanged.

## 8. Key facts / gotchas

- **Confidence is a distance** — lower is better. `distance < 50` ⇒ recognized; display score is `100 - distance`.
- **Label IDs come from sorted folder names** in `train_model.py`; if `label_names.npy` and model get out of sync, recognition names will be wrong. Retrain after adding/renaming dataset folders.
- **`visitor_logs.py` uses relative paths** ~~(`"visitor_logs.csv"`, `"visitor_tracking.json"`)~~ — **fixed**: all module paths are now `__file__`-based and point into `data/`, so logging/tracking works from any CWD.
- **`release_camera()` is never called** — no shutdown hook/`atexit`; camera may stay locked until process exit.
- `log_interval` throttle key is `name_status`, so frequent unknown events are throttled per status, not globally.
- CSV has **mixed date formats** historically (`DD-MM-YYYY` legacy rows vs `YYYY-MM-DD` new rows) and one junk row `{0: 'Vandana'}` — see `data/visitor_logs.csv`.
- First 3 rows of `data/visitor_registrations.json` lack the `Photo Filename` key (added later feature); frontend tolerates missing keys.
- `register_visitor` requires `name, phone, purpose, host, department`; `email` optional.
- `scripts/face_capture.py` and `scripts/face_detection.py` open their own `cv2.VideoCapture(0)` — do not run them while `app.py` streams the same camera.
- Emails only send when `.env` has `SMTP_USER` + `SMTP_PASSWORD` (`is_email_configured()`); `core/email_sender.py` never raises — failures are logged and the API still succeeds with `email_sent: false`.
- `MAX_CONTENT_LENGTH = 12 MB`; uploaded image additionally rejected if > 10 MB or not JPEG.
- Legacy backup files were moved to `backups/` (dead code, gitignored).

## 9. Likely to-do / improvement backlog (inferred, confirm with user)

Completed in recent refactors (uncommitted, see §10):

- [x] Add `requirements.txt` (flask, opencv-contrib-python, numpy, python-dotenv).
- [x] Add `README.md` with setup/run steps.
- [x] Fix relative-path bug in `core/visitor_logs.py` (paths are `__file__`-based now).
- [x] Add `.gitignore` (`__pycache__/`, logs, backups, captures, dataset).
- [x] Move legacy `*_backup.*` files out of the root (now in `backups/`, gitignored).
- [x] Extract the dashboard CSS and JS from `dashboard.html` into `static/styles/` + `static/js/`.
- [x] Reorganize the root into `core/`, `scripts/`, `data/`, `model/` (all paths CWD-independent).
- [x] Split the single-page dashboard into six pages with a shared `base.html`
      sidebar layout and per-page JS entry modules.
- [x] Replace native `prompt()`/`confirm()` with a reusable modal system
      (`modal.js` + `modal.css`), with validation, focus trap and busy-state
      dismissal protection.
- [x] Add reusable toast notifications (`toast.js` + `toast.css`) and loading
      indicators (`loading.js` + `loading.css`) for actions and refreshes.
- [x] Add confirmation dialogs to Mark Entry / Mark Exit identifying the
      visitor before any request is sent.

Still open:

- [ ] Release camera on app shutdown (`atexit`/`signal`).
- [ ] Clean `data/visitor_logs.csv` date formats + stray `{0: 'Vandana'}` row.
- [ ] Add tests / basic validation; consider a database instead of flat files.
- [ ] Add authentication for the dashboard and host-approval endpoints.
- [ ] Optionally expose past entry/exit records (Exited visits) for the history
      page — currently only recognition logs are shown (user declined the extra
      endpoint for now).

## 10. Git state

- Branch `main`. The working tree has **uncommitted changes** (kept unstaged on
  purpose — the user asked not to push yet): backend reorganization into
  `core/`/`scripts/`/`data/`, JS/CSS extraction, approval-workflow and
  email-template improvements, the multi-page split (`base.html` + 6 page
  templates + `static/js/pages/`), the modal/toast/loading UI system, the
  two-column approval cards, `.gitignore`/README/AGENT-MAP updates.
- Tracked junk (`server_*.log`, `server_test.pid`, `visitor_registrations.json.testbak`,
  `__pycache__/` incl. a stray `__pycache__/templates/dashboard.html`) has been
  deleted from the working tree; `.gitignore` now prevents them from returning.
- When committing: stage the new `core/`, `scripts/`, `data/`, `model/haarcascade…`
  folders together with the deletions so git records the moves as renames.
