# AI-Based Smart College Visitor Management System

A Flask web application that uses OpenCV face recognition to manage college
visitors. It recognizes registered people from a live webcam feed, lets staff
register visitors with a captured photo, routes requests to a host for
approval, and tracks who is currently inside through a security dashboard.

## Features

- Live webcam feed with face recognition (recognized vs. unknown).
- Visitor registration with a live captured photo.
- Department and host dropdowns populated from active `host` accounts in the
  SQLite `users` table (hosts filtered by department).
- Host approval / rejection workflow with the recorded decision maker and rejection reason.
- Visitor entry and exit tracking (who is currently inside).
- Optional email notifications (registration + approval/rejection emails).
- Multi-page dashboard with sidebar navigation: overview, registration,
  recognition, approvals, approval history, inside visitors and visitor history.
- Role-based access control (Administrator, Security Guard, Host) with
  role-specific navigation and server-side protection on pages and APIs.
- Administrator User Management: create accounts, edit roles/departments,
  reset passwords and activate/deactivate accounts without deleting history.
- Host-specific approval queues: hosts only see and decide requests assigned
  to their own account; administrators can review all requests.
- Logout invalidates the Flask-Login session and protected responses are sent
  with `no-store` cache headers for safe browser-back behavior.
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
- Flask-Login (authentication + role-based access control)
- python-dotenv (environment / SMTP email settings)

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

Visitor registrations, approval decisions, entry/exit visits, recognition
events and application user accounts are stored in a local SQLite database at
`data/visitor_management.db`. The tables are created automatically when the app
starts, so no manual setup is needed. On startup the app also adds missing
`role`/`department` user columns and the visitor `host_user_id` ownership column;
existing accounts and visitor records are preserved and are not given a role
automatically. Legacy visitor ownership is backfilled only when the stored host
name uniquely matches an active host account.

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

## Authentication and Roles

The app uses Flask-Login for sessions and role-based access control (RBAC).
Passwords are stored as Werkzeug hashes; a single generic error is shown for
unknown usernames, wrong passwords and inactive accounts.

The three roles are:

- **Administrator** — full access including User Management, all approvals and
  approval history.
- **Security Guard** — dashboard, visitor registration, face recognition, inside
  visitors and visitor history. Cannot approve or reject requests.
- **Host** — dashboard plus only the approval requests assigned to their own
  account and their own approval history. Cannot use security-only pages.

Pages and APIs are protected on the server with decorators from
`core/permissions.py`; hiding sidebar links is only a convenience, not the
security boundary. Unauthenticated page requests redirect to `/login` with a
safe `next`; unauthenticated API requests return `401` JSON. Authenticated users
without the required role get a `403` (HTML page or JSON, depending on the
request). `/health`, `/login`, and `POST /logout` are public.

Role-specific dashboard data is also enforced: Administrators see visitor
activity, all pending approvals and inside visitors; Security Guards see visitor
activity and inside visitors; Hosts see only approvals assigned to them.
Approval ownership is checked again on every approve/reject action, so a host
cannot act on another host's request by guessing its registration ID.

Logout clears the Flask-Login session and remember-cookie state, then redirects
to `/login`. Non-static responses (pages and APIs) are sent with
`Cache-Control: no-store`, `Pragma: no-cache` and `Expires: 0`; a small
`session-guard.js` reloads pages restored from the browser back-forward cache.
Directly reopening any protected URL after logout redirects to login.

1. Set a `SECRET_KEY` in `.env` (see `.env.example`). Without it the app starts
   with an ephemeral key and logs a warning, but every restart invalidates
   sessions. Generate one with:

   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. Create an account with an explicit role:

   ```bash
   flask --app app create-user --username guard1 --full-name "Guard One" \
     --role security --department "Security Office"
   ```

   `--role` accepts `admin`, `security` or `host`. Omit flags to be prompted
   (the password is hidden and entered twice; email and department are
   optional).

   Host accounts drive the registration form: only active `host` users with a
   non-empty department appear there. For example:

   ```bash
   flask --app app create-user --username rahul --full-name "Rahul Sharma" \
     --role host --department "Computer Science"
   ```

   Administrators can also manage accounts in the browser at `/users`, or through
   `GET/POST /api/users` and `PATCH /api/users/<id>`. Accounts are deactivated
   rather than deleted so approval/visit history is preserved.

3. Assign a role to an account created before roles existed (or change one):

   ```bash
   flask --app app assign-role --username admin --role admin
   ```

   Existing accounts have no role (`NULL`) after the automatic schema upgrade.
   They can still log in, but protected pages/APIs return `403` ("Unassigned")
   until an administrator assigns a role. Roles are never assigned silently.

Authentication routes: `GET/POST /login`, `POST /logout` and `GET /auth-test`
(a protected JSON route used to verify the session).

Sessions use the Flask defaults hardened in `core/auth.py`: HttpOnly and
SameSite=Lax cookies, `session_protection="strong"`, and an 8-hour lifetime.
Set `SESSION_COOKIE_SECURE=True` in `.env` only when serving over HTTPS.

### Tests

The 33 auth/RBAC/ownership tests use a temporary SQLite database and never touch
`data/visitor_management.db`:

```bash
python -m unittest discover -v
```

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
   must be an app password, not your normal password. The same `.env` holds
   `SECRET_KEY` (and optionally `SESSION_COOKIE_SECURE`).

Without SMTP settings, everything else works normally and emails are simply
skipped.

## Usage Flow

1. **Log in** — open `/login` (unauthenticated pages redirect there) and use an
   account with `admin`, `security` or `host` role. The sidebar only shows the
   pages that role can use.
2. **Register a visitor** — on the *Visitor Registration* page, capture a photo
   from the live feed (the form appears after capture) and fill in the
   registration details. Choose a department (loaded from active host accounts),
   then choose the host from that department's active hosts.
3. **Host approval** — the request appears only for the assigned host (admins
   see all requests). The decision maker is recorded from the signed-in account;
   rejecting requires a reason in the modal.
4. **Mark entry** — approved visitors appear on the *Inside Visitors* page;
   click "Mark Entry" and confirm the visitor in the dialog.
5. **Mark exit** — visitors currently inside appear on the same page; click
   "Mark Exit" and confirm to close their entry record.
6. **Monitor** — the *Dashboard* shows the statistics and summaries allowed for
   the current role; the *Face Recognition* page shows the live feed and the
   latest recognition results (admin/security).
7. **Review decisions** — the *Approval History* page lists every approved and
   rejected request with the decision maker, decision time and rejection
   reason (legacy approvals without those fields show "Not recorded").
8. **Review history** — the *Visitor History* page lists every registration
   (searchable and filterable, including date ranges) plus all recognition
   events with their own search. Long lists are paginated 10 per page.
9. **Manage users** — administrators can open *User Management* (`/users`) to
   create accounts, change roles/departments, reset passwords and
   activate/deactivate users without deleting their history.

## Project Structure

```
app.py                        Main Flask application and all routes
core/                         Backend modules used by app.py
    database.py               SQLite/SQLAlchemy setup and app-context helper
    models.py                 Visitor, Approval, Visit, RecognitionEvent, User models
    auth.py                   Flask-Login setup, login/logout routes, user CLIs
    permissions.py            Role-based access decorators and 401/403 responses
    users.py                  Admin user list/create/update validation
    email_sender.py           Registration / decision emails (SMTP)
    face_recognition.py       Live recognition + MJPEG streaming module
    host_approval.py          Host-filtered approvals + ownership-checked decisions
    visitor_logs.py           Recognition logging + entry/exit tracking
    visitor_registration.py   Registration logic + active-host directory queries
scripts/                      Standalone utilities (run from the project root)
    face_capture.py           Script to capture training face images
    train_model.py            Trains the LBPH model from dataset/
    face_detection.py         Standalone face-detection demo (not used by app)
    migrate_to_sqlite.py      One-time JSON/CSV -> SQLite importer (idempotent)
templates/                    Jinja templates (page markup)
    base.html                 Shared layout: sidebar navigation + header
    login.html                Standalone login page (no sidebar)
    403.html                  Permission-denied page
    dashboard.html            Overview page (role-aware stats + summaries)
    registration.html         Photo capture + visitor registration form
    recognition.html          Live camera feed + recognition status
    approvals.html            Assigned pending host approvals (approve / reject)
    approval_history.html     Recorded approval decisions (search + pagination)
    users.html                Admin user management (create/edit/deactivate)
    inside_visitors.html      Entry and exit management
    visitor_history.html      Visitor records (search/filters/dates) + recognition logs
static/styles/                Dashboard CSS, split by component
static/js/                    Shared JavaScript modules (utils, camera,
                             photo capture, registration, logs, approvals,
                             approval history, entry/exit, status pill, modal
                             dialogs, toast notifications, loading indicators,
                             empty states, visitor records, pagination,
                             session-guard)
static/js/pages/             One entry module per page (incl. login.js, users.js)
tests/                       Standard-library unittest suite (33 auth/RBAC/ownership tests)
data/                         Runtime data
    visitor_management.db       SQLite database (auto-created, gitignored)
    visitor_registrations.json  Legacy registrations (migrated, kept on disk)
    visitor_logs.csv            Legacy recognition log (migrated, kept on disk)
    visitor_tracking.json       Legacy entry/exit records (migrated, kept on disk)
dataset/                      Training images per person
model/                        Trained LBPH model, label names + Haar cascade
visitor_captures/             Photos captured from the browser
backups/                      Old backup files (not tracked by git)
.env                          SECRET_KEY + SMTP email settings (not tracked by git)
.env.example                  Template for environment settings
requirements.txt              Python dependencies
AGENT-MAP.md                  Developer minimap of the project
```

## API Endpoints

`Access` lists the roles allowed (admin / security / host). `Public` means no
login is required.

| Method | Endpoint | Access | Purpose |
|--------|----------|--------|---------|
| GET | `/` | admin, security, host | Role-aware dashboard overview |
| GET | `/registration` | admin, security | Visitor registration page |
| GET | `/recognition` | admin, security | Face recognition page |
| GET | `/approvals` | admin, host | Assigned host approvals page |
| GET | `/approval-history` | admin, host | Approval history page (host-filtered) |
| GET | `/users` | admin | User Management page |
| GET | `/inside-visitors` | admin, security | Inside visitors page |
| GET | `/visitor-history` | admin, security | Visitor history page |
| GET/POST | `/login` | Public | Log in (GET shows the form) |
| POST | `/logout` | Public (POST) | Clear the session and return to login |
| GET | `/auth-test` | Any logged-in user | Session check |
| GET | `/health` | Public | Health check |
| GET | `/video_feed` | admin, security | Live MJPEG camera feed |
| GET | `/camera-status` | admin, security, host | Camera availability |
| GET | `/api/visitor-logs` | admin, security | Recognition logs + stats |
| GET | `/api/open-visitors` | admin, security | Visitors currently inside |
| GET | `/api/registrations` | admin, security | All registrations |
| GET | `/api/departments` | admin, security | Distinct departments of active host accounts |
| GET | `/api/hosts?department=<name>` | admin, security | Active hosts (`id`, `full_name`) in a department |
| GET | `/api/pending-approvals` | admin, host | Pending approvals (hosts see only their own) |
| GET | `/api/approval-history` | admin, host | Approved/rejected decisions (host-filtered) |
| GET/POST | `/api/users` | admin | List or create user accounts |
| PATCH | `/api/users/<id>` | admin | Update role, department, password or active status |
| GET | `/visitor-captures/<filename>` | admin, security, host | Saved visitor photo (hosts: own visitors only) |
| POST | `/save-capture` | admin, security | Save captured visitor photo |
| POST | `/register-visitor` | admin, security | Register a visitor (`host_id` + `department`; host is resolved, validated and recorded as `host_user_id`) |
| POST | `/host-approval/<id>/<decision>` | admin, host | Approve / reject an assigned request |
| POST | `/mark-entry` | admin, security | Record visitor entry |
| POST | `/mark-exit` | admin, security | Record visitor exit |

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
- Accounts upgraded from the pre-role schema show "Unassigned" and are denied
  protected pages until `flask --app app assign-role` gives them a role.
- New registrations store both the resolved host's `full_name` and
  `host_user_id`; approval ownership and filtering use `host_user_id`. On startup
  the app adds this column if needed and backfills it only for legacy visitors
  whose stored host name uniquely matches an active host account. Ambiguous,
  missing or departed-host records stay unassigned and are visible only to
  administrators.
- The registration form's Department dropdown lists distinct departments from
  active `host` accounts, and the Host dropdown lists active hosts in the chosen
  department. A host without a department, an inactive host, a non-host user or a
  mismatched department is rejected by `/register-visitor`.
- Do not delete accounts to remove access; deactivate them in User Management so
  their historical approvals and visit records remain attributed.
- Back up `data/visitor_management.db` to keep a copy of all visitor records.
  The legacy JSON/CSV files are only a pre-migration snapshot; the app does not
  keep them in sync any more.
