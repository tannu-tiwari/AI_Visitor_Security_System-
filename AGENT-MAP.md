# AGENT-MAP.md — Project Minimap

> Read this first at the start of any session. It describes what the project is,
> where everything lives, how the pieces connect, and what is likely still to do.
> Last updated: 2026-11-11 (Auth/RBAC completion: host-owned approvals via
> `Visitor.host_user_id`, host-filtered pages/APIs/captures, admin User
> Management (`/users`, `/api/users`), logout/session and `no-store` cache
> hardening, dynamic department/host dropdowns, and 33 auth/RBAC/ownership
> tests; on top of authentication step 2 (RBAC, role-aware
> navigation/dashboard, `assign-role`), step 1 (Flask-Login, `/login`,
> `/logout`, safe `next`, session hardening) and the SQLite migration,
> Approval History, pagination, empty/error states, Visitor History
> search/filters, the multi-page split, root-folder restructure and
> modal/toast/loading UI system).

## 1. What this project is

**AI-Based Smart College Visitor Management System** — a Flask web app that combines
OpenCV face recognition with a live security dashboard for a college:

1. Recognizes registered people from a webcam feed (recognized vs. unknown).
2. Lets a guard register a visitor (with a captured photo) and routes the request to a host.
3. Hosts approve/reject visitor requests.
4. Tracks visitor entry/exit (who is currently inside).
5. Shows stats + logs live on a multi-page dashboard (overview, registration,
   recognition, approvals, approval history, inside visitors, history).

This is a college (Synergy) project. Repo: `github.com/tannu-tiwari/AI_Visitor_Security_System-`, branch `main`.

## 2. Tech stack

- **Backend:** Python 3.11 (project venv), Flask (`render_template`, `jsonify`, `Response`).
- **Vision:** OpenCV (`opencv-contrib-python` 4.10) — Haar cascade detection + LBPH face recognizer; NumPy.
- **Frontend:** Jinja template inheritance (`base.html` + 8 page templates, plus the standalone `login.html`), vanilla ES modules loaded per page, no build step, no framework.
- **Auth:** Flask-Login 0.6.3 + Werkzeug password hashes + RBAC (`admin`, `security`, `host`); `SECRET_KEY` from `.env` (ephemeral fallback with a warning).
- **Email:** `python-dotenv` + `smtplib` — SMTP settings come from `.env` in the project root.
- **Storage:** SQLite via Flask-SQLAlchemy (`data/visitor_management.db`, override with `VISITOR_DB_PATH`). Legacy CSV/JSON files are kept on disk but no longer read/written. Images as JPEG files.

`requirements.txt`, `README.md`, `.gitignore`, and `.env.example` exist. The only
test suite is `tests/test_auth.py` (stdlib `unittest`); there is no `AGENTS.md`.

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
                      └── log_visitor(name,status) ──► SQLite recognition_events

Browser ──► /save-capture  ──► visitor_captures/visitor_<timestamp>.jpg
Browser ──► /visitor-captures/<filename>  ──► serve saved photo (JPEG/PNG only)
Browser ──► /api/departments ──► active host departments ──► Department <select>
Browser ──► /api/hosts?department=… ──► active hosts (id, full_name) ──► Host <select>
Browser ──► /register-visitor (host_id + department)
             └──► validate active host role/department ──► SQLite visitors (Pending, host_user_id)
Browser ──► /host-approval/<id>/<decision> ──► ownership check ──► core/host_approval.update_approval() ──► visitors + approvals
             (hosts: own assigned requests only; admins: any; decision emails never raise)
Browser ──► /mark-entry, /mark-exit ──► core/visitor_logs.mark_entry/mark_exit ──► SQLite visits
Browser ──► /api/visitor-logs, /api/open-visitors, /api/registrations,
             /api/pending-approvals, /api/approval-history, /camera-status
             (JSON polling every 10s)

Browser ──► /login ──► core/auth.py ──► User table (Werkzeug hash check)
             └──► session.clear() + Flask-Login session (HttpOnly, SameSite=Lax, 8h)
Browser ──► /logout (POST) ──► session.clear() + logout_user() ──► /login
Browser ──► every page/API ──► core/permissions.py role decorators
             ├── no session: page → /login?next=…, API → 401 JSON
             └── wrong role: 403 (403.html or JSON)
Browser ──► /auth-test ──► @login_required JSON session check
Browser ──► /users, /api/users ──► admin_required ──► core/users.py CRUD
Browser ──► all non-static responses ──► no-store cache headers; session-guard.js reloads bfcache pages
```

## 5. File map

### Backend (Python)

| File | Role |
|------|------|
| `app.py` | **Main Flask app** (root). All routes, stats helpers, image upload, run config. Calls `init_database(app)` at startup and reads logs from the database. |
| `core/face_recognition.py` | **Live recognition module**. Loads LBPH model + Haar cascade once (`initialize_recognition`), opens webcam once (`get_camera`), yields annotated MJPEG frames (`generate_frames`), `camera_available()`, `release_camera()`. Threshold `CONFIDENCE_THRESHOLD=50`, per-person logging throttle `LOG_INTERVAL=30s`. |
| `core/database.py` | `db = SQLAlchemy()`, `init_database(app)` (resolves `VISITOR_DB_PATH` or `data/visitor_management.db`, creates tables, enables SQLite FKs, then calls `ensure_user_schema()` + `ensure_visitor_schema()`), `ensure_user_schema()` (idempotent `users.role/department`; never assigns roles), `ensure_visitor_schema()` (idempotent `visitors.host_user_id` + index; backfills only unique case-insensitive host-name matches), `app_scope()`, `commit_session()`. |
| `core/models.py` | `Visitor` (registration fields + status, unique `registration_id`, nullable `host_user_id` FK → `users.id` with `assigned_host` relationship), `Approval` (decision/maker/time/reason, legacy nulls allowed), `Visit` (nullable visitor link + name snapshot, entry/exit), `RecognitionEvent` (raw date/time strings), `User` (unique username, hashed password, unique nullable email, `is_active`, `role` nullable at DB level + `department`, role CheckConstraint, role validator, `role_label`, Werkzeug `set_password`/`check_password`). New users require a valid role; legacy accounts may be `NULL` until assigned. Legacy-shaped `to_dict()` serializers live here. |
| `core/auth.py` | **Auth module** (same `db`, no second instance): `LoginManager` with inactive-user rejection, `auth_bp` with `GET/POST /login`, `POST /logout`, `GET /auth-test` (`@login_required`); safe-`next` validation; login does `session.clear()` before `login_user()` and sets 8h permanent sessions; logout does `session.clear()` then `logout_user()`; session hardening (`SESSION_COOKIE_*`, `REMEMBER_COOKIE_*`, `session_protection="strong"`); `init_auth(app)`; `flask create-user` and `flask assign-role`. |
| `core/permissions.py` | **RBAC decorators**: `roles_required(*roles)`, `admin_required`, `security_required` (admin/security), `host_required` (admin/host); JSON detection and 401/403 responses (redirect to login for pages, JSON for APIs). Unassigned/inactive users are denied. |
| `core/users.py` | **Admin user management**: `list_users`, `create_user_account`, `update_user_account`; required username/full name/role/password on create, host requires department, unique username/email validation, role/active/password edits, and self-protection against removing one's own admin role or deactivating oneself. |
| `core/visitor_logs.py` | DB-backed log/tracking: `load_logs`, `log_visitor`, `mark_entry`/`mark_exit`, `get_open_visitors`, `load_visit_tracking`. Legacy file path constants kept for reference. |
| `core/visitor_registration.py` | `get_host_departments()` (distinct non-empty departments of active hosts), `get_hosts_for_department(dept)` (`id`/`full_name` of active hosts), `_validate_host()` (exists, role `host`, active, department matches), `register_visitor(...)` which resolves `host_id`, stores the host's real `full_name`/department **and** `host_user_id`, and `host_owns_capture()` for host photo access; `load_registrations` orders by insertion. |
| `core/host_approval.py` | `update_approval(..., host_user_id=None)` updates status + inserts Approval atomically (only Pending), enforcing ownership for hosts and returning `(success, message, registration, status_code)`; `get_pending_approvals(host_user_id=None)` and `get_approval_history(host_user_id=None)` filter to one host; admins pass `None` for all. |
| `core/email_sender.py` | SMTP emails: `send_registration_email`, `send_decision_email` (never raise). Loads `.env` from the project root. |
| `scripts/train_model.py` | Trains LBPH on `dataset/<person>/*.jpg`, saves `model/face_model.yml` + `model/label_names.npy`. Sorts names alphabetically → label IDs. |
| `scripts/face_capture.py` | Interactive script: prompts for a name, captures 100 face crops into `dataset/<name>/`. |
| `scripts/face_detection.py` | Standalone beginner demo: webcam window that draws boxes around faces (Hindi comments). Not used by the app. |
| `scripts/migrate_to_sqlite.py` | Idempotent importer: backs up the legacy JSON/CSV into `backups/migration_<timestamp>/`, imports visitors/approvals/visits/recognition events per record, reports migrated/skipped/failed, never touches sources. Flags: `--source-dir`, `--database`, `--backup-dir`. |

### Templates and static assets

| File | Role |
|------|------|
| `templates/base.html` | **Shared layout**: role-gated sidebar navigation (active link via `request.path`), topbar with camera-status pill + user name/role/logout form, `{% block content %}` + `{% block scripts %}`. Admin nav includes User Management and Approval History; hosts see only their own approval pages; `session-guard.js` is loaded for bfcache reloads. |
| `templates/login.html` | **Standalone login page** (no sidebar): username/password form, flashed messages, inline error, safe `next` hidden field, show/hide password toggle. |
| `templates/403.html` | Permission-denied page for authenticated users with the wrong role. |
| `templates/dashboard.html` | **Role-aware overview**: admin sees visitor stats/activity + pending + inside; security sees visitor stats/activity + inside; host sees pending only. Links are permission-gated too. |
| `templates/registration.html` | Photo capture from the live feed + registration form (photo-first gating: form hidden until capture). |
| `templates/recognition.html` | Live `/video_feed` stream, camera badge + Check/Restart/Retry controls, recent recognition events. |
| `templates/approvals.html` | Assigned pending approvals with photos + approve/reject; decision maker is the signed-in account, and rejections require a reason in the modal. |
| `templates/users.html` | Admin User Management table + create/edit modals (role, department, password, active status); self-demotion/deactivation is blocked server-side. |
| `templates/inside_visitors.html` | Approved Visitors (Mark Entry) + Currently Inside (Mark Exit), each behind a confirmation modal. |
| `templates/visitor_history.html` | **Visitor Records panel** (all registrations, client-side search/filters/date range) + **Recognition Events panel** (full logs table + client-side search); both paginated 10 rows/page. |
| `templates/approval_history.html` | **Approval History page**: recorded Approved/Rejected decisions (host, decision time, rejection reason), search, 10 decisions/page; legacy records show "Not recorded". |
| `static/styles/*.css` | Dashboard CSS split by component (base, layout, **sidebar**, topbar, buttons, badges, stats, panels, forms, camera, tables, **history**, **pagination**, **loading**, **modal**, **toast**, **auth**). |
| `static/js/*.js` | Shared feature modules (see §7), including `session-guard.js` for browser-back session safety. |
| `static/js/pages/*.js` | Per-page entry modules (dashboard, registration, recognition, approvals, approval-history, inside-visitors, visitor-history, users, login). |

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
| `data/visitor_management.db` | **Live SQLite database** (auto-created, gitignored). Tables: `visitors` (incl. `host_user_id` ownership FK), `approvals`, `visits`, `recognition_events`, `users`. Current migration left 1 of 16 visitors host-assigned (legacy names that did not uniquely match). |
| `data/visitor_logs.csv` | Legacy recognition log (migrated; no longer read/written). Header: `Visitor Name,Date,Time,Status`. |
| `data/visitor_tracking.json` | Legacy entry/exit records (migrated; no longer read/written). |
| `data/visitor_registrations.json` | Legacy registrations (migrated; no longer read/written). |
| `visitor_captures/*.jpg` | Photos captured from the browser (`visitor_<timestamp>.jpg`). |
| `backups/` | Legacy backup files (dead code, gitignored). |

## 6. HTTP routes (`app.py` plus `core/auth.py`)

| Method | Route | Access | Handler | Purpose |
|--------|-------|--------|---------|---------|
| GET | `/` | admin, security, host | `dashboard` | Role-aware overview: logs/pending stats filtered by role; reversed logs. |
| GET | `/registration` | admin, security | `registration_page` | Visitor registration page (photo capture + form). |
| GET | `/recognition` | admin, security | `recognition_page` | Live recognition feed page. |
| GET | `/approvals` | admin, host | `approvals_page` | Assigned host approvals page (host-filtered). |
| GET | `/users` | admin | `users_page` | Admin User Management page. |
| GET | `/inside-visitors` | admin, security | `inside_visitors_page` | Entry/exit management page. |
| GET | `/approval-history` | admin, host | `approval_history_page` | Approval History page: first page of processed decisions server-rendered, searched/paged client-side. |
| GET | `/visitor-history` | admin, security | `visitor_history_page` | Visitor Records (server-rendered first 10 registrations, searched/filtered/paged client-side) + recognition logs (first 10 rows + JS search/pagination). |
| GET/POST | `/login` | public | `auth.login` | Login form / credential check (`core/auth.py`). Authenticated GET redirects to dashboard or a safe `next`. |
| POST | `/logout` | public | `auth.logout` | `session.clear()` + `logout_user()`, redirect to `/login`. |
| GET | `/auth-test` | any logged-in user | `auth.auth_test` | `@login_required` JSON session check. |
| GET | `/health` | public | `health_check` | JSON liveness. |
| GET | `/api/visitor-logs` | admin, security | `visitor_logs_api` | Stats + reversed logs. |
| GET | `/api/open-visitors` | admin, security | `open_visitors_api` | Visitors currently `Inside`. |
| GET | `/api/registrations` | admin, security | `registrations_api` | All registrations. |
| GET | `/api/departments` | admin, security | `host_departments_api` | `{departments: [...]}` from active hosts (non-empty, distinct). |
| GET | `/api/hosts?department=<name>` | admin, security | `hosts_api` | `{hosts: [{id, full_name}]}` for active hosts in that department; missing department → 400. |
| GET | `/api/pending-approvals` | admin, host | `pending_approvals_api` | Pending registrations; hosts see only `host_user_id == current_user.id`. |
| GET | `/api/approval-history` | admin, host | `approval_history_api` | Approved/Rejected registrations (host-filtered), newest decision first. |
| GET/POST | `/api/users` | admin | `users_api` | List or create user accounts (`{success, message, user}`). |
| PATCH | `/api/users/<id>` | admin | `user_api` | Update role/department/password/active; 404 for missing user, 400 for validation/self-protection errors. |
| POST | `/save-capture` | admin, security | `save_capture` | Decode base64 JPEG, validate magic bytes, save to `visitor_captures/`. Returns `filename`. |
| GET | `/visitor-captures/<filename>` | admin, security, host | `serve_visitor_capture` | Serve a saved visitor photo; hosts only for their own assigned visitors, admins/security all. |
| POST | `/register-visitor` | admin, security | `register_new_visitor` | Accepts JSON or form with `host_id` + `department`; resolves/validates the active host and stores their real name/department + `host_user_id`. Requires photo first (frontend enforces). Sends registration email if configured. |
| POST | `/host-approval/<registration_id>/<decision>` | admin, host | `process_host_approval` | decision `approve`/`reject` (also `approved`/`rejected`); host ownership enforced (403), Pending-only (400), missing (404). Decision maker is taken server-side from `current_user`; JSON body only needs optional `rejection_reason`. |
| POST | `/mark-entry` | admin, security | `mark_visitor_entry` | Body field `name` or `visitor_name`. |
| POST | `/mark-exit` | admin, security | `mark_visitor_exit` | Same. |
| GET | `/camera-status` | admin, security, host | `camera_status` | `{camera_available, message}`. |
| GET | `/video_feed` | admin, security | `video_feed` | MJPEG stream (`multipart/x-mixed-replace`). |

All non-static responses also get `Cache-Control: no-store, no-cache,
must-revalidate, max-age=0`, `Pragma: no-cache`, `Expires: 0` via
`after_request`. `/logout` and `/health` remain intentionally public.

## 7. Frontend JS (ES modules in `static/js/`)

`base.html` loads `status-pill.js` (header camera pill) and `session-guard.js`
(bfcache reload after logout) on every protected page; each page template loads
exactly one entry module from `static/js/pages/`. Loaders are **null-safe** —
they only touch element IDs that exist on the current page, so one feature
module can serve several pages.

| Module | Used by | Role |
|--------|---------|------|
| `utils.js` | all | `$`, `setText` (null-safe), `fetchJSON` (parses JSON error messages from failed responses), `showFeedback`, `escapeHTML`. |
| `modal.js` | approvals, inside-visitors, users | Reusable dialogs: `confirmDialog({...})` → `Promise<boolean>`, `formDialog({fields})` → `Promise<values\|null>`. Supports text/password/select fields, focus trap + Tab wrap, Escape/backdrop/×/Cancel dismissal (blocked while `onConfirm` is in flight), inline field validation with trimming, restores focus on close. Cancel resolves `false`/`null`; `onConfirm` throwing closes and rejects so callers can toast the failure. |
| `toast.js` | all pages that act | `toast.success/error/warning/info(message)` — stacked, auto-dismissing (errors last longer), manually closable, capped at 5 visible, messages set via `textContent`. |
| `loading.js` | all | `setButtonLoading(button, busy, label)` — disables the button, adds a spinner + `aria-busy`, stores/restores the original label. |
| `empty-state.js` | all list/table pages | `emptyStateHTML({icon, title, message, action, variant})` — shared empty/error markup. Action is a link (`href`) or a delegated button (`id`); `variant: "error"` styles request failures differently from genuinely empty data. All strings escaped. |
| `pagination.js` | all data-heavy lists | `createPaginator({controlsId, summaryId, pageSize, label, onChange})` → `paginate(items)` returns `{items, page, totalPages, total, start, end}` and paints `Previous / Page X of Y / Next` + "Showing A–B of N …". Clamps the page when data shrinks, `reset()` on filter/search changes, disables boundary buttons, blocks duplicate clicks while `onChange` is pending (`aria-busy` + busy class), and tolerates missing elements. Client-side: filter/sort first, then paginate. |
| `status-pill.js` | base (all pages) | One `/camera-status` fetch → header pill. |
| `camera-feed.js` | recognition | `checkCamera` (pill + panel badge), retry/restart feed buttons. |
| `photo-capture.js` | registration | `captureVisitorPhoto` (canvas ← feed `<img>` → `/save-capture`), `retakeVisitorPhoto`, reveals the form; busy capture button, toast on failure. |
| `host-directory.js` | registration | Loads `/api/departments` into the Department select, then loads `/api/hosts?department=…` on change. Clears the previous host immediately, disables Host until a department is chosen, uses host `id` as option value and `full_name` as text, shows loading/no-hosts/error messages, guards against stale fetch responses, and resets the pair on form reset. |
| `visitor-registration.js` | registration | Form submit → `/register-visitor` with `host_id` + department; photo-first gating; submit button busy state; inline feedback panel; pending-list refresh only if present. |
| `visitor-logs.js` | history, dashboard, recognition | `loadLogs` (updates stat cards when present, returns logs; returns `null` if the request fails and no stale data exists), `logRowHTML`, search + refresh (refresh button busy while fetching). Search has three distinct states: matching rows, "no match" (with a clear-search action) and "no logs yet"; failures keep stale rows or show an error state. Paged 10 events/page; search resets to page 1. |
| `visitor-records.js` | history | Visitor Records table: `loadVisitorHistory` fetches `/api/registrations` + `/api/open-visitors` (for the Inside badge), sorts newest-first, then paginates (10/page); `initVisitorHistory` wires the debounced search (name/phone/email/registration ID/host/department/purpose), approval-status, department, visit-status and date-range filters, plus "Clear Filters". Filtering is client-side (small dataset already returned by the API); any filter/search change resets to page 1. Invalid date ranges show an inline error and skip only the date part. |
| `approval-history.js` | approval-history | `loadApprovalHistory` fetches `/api/approval-history`, filters by search (visitor, ID, host, status, decision maker, rejection reason), sorts newest-first and paginates (10/page); `initApprovalHistory` wires the debounced search, refresh button and clear-search action. Missing legacy `Decision By`/`Decision At` render as "Not recorded"; `T` in stored timestamps is displayed as a space. |
| `visitor-approval.js` | approvals, dashboard | `loadApprovals` (returns host-filtered list, updates badge, paginates cards 10/page); delegated approve/reject opens a `formDialog` (reason required only when rejecting) and POSTs without any client-supplied decision maker; success/failure toasts; row button disabled during the flow. Pager re-renders from cache. |
| `visitor-entry-exit.js` | inside-visitors, dashboard | `loadInsideVisitors` / `loadApprovedVisitors` (return data, update badges/stats when present) each paginate their list 10/page; delegated Mark Entry / Mark Exit open a `confirmDialog` identifying the visitor (host/purpose/entry time) before posting; toasts + list refresh on success, row button disabled during the flow. Pager re-renders from cache. |
| `pages/dashboard.js` | `/` | Refresh button (busy while refreshing) + 10s polling, fetching only the panels present for the current role (logs / pending / inside). |
| `pages/registration.js` | `/registration` | `initPhotoCapture` + `initHostDepartmentDropdowns` + `initVisitorRegistration`. |
| `pages/recognition.js` | `/recognition` | `initCameraFeed` + `checkCamera` + 10s recent-events polling. |
| `pages/approvals.js` | `/approvals` | `initVisitorApproval` + 10s pending polling. |
| `pages/approval-history.js` | `/approval-history` | `initApprovalHistory` + `loadApprovalHistory` + 10s polling (page preserved; clamped when records shrink). |
| `pages/inside-visitors.js` | `/inside-visitors` | `initVisitorEntryExit` + 10s polling of both lists. |
| `pages/visitor-history.js` | `/visitor-history` | `initVisitorLogs` + `initVisitorHistory` + `loadLogs` + `loadVisitorHistory` + 10s polling of both panels. |
| `pages/users.js` | `/users` | Loads `/api/users`; create/edit modals with role/department/password/active fields; POST/PATCH, busy states, toasts, and refresh after changes. |
| `pages/login.js` | `/login` | Null-safe show/hide password toggle (`type`, label, `aria-pressed`). |

Camera feed: `<img src="/video_feed">` appears only on `/registration` and
`/recognition`. Approve/reject and entry/exit run through `modal.js` (see
above); their POST payloads and endpoints are unchanged.

## 8. Key facts / gotchas

- **Confidence is a distance** — lower is better. `distance < 50` ⇒ recognized; display score is `100 - distance`.
- **Label IDs come from sorted folder names** in `train_model.py`; if `label_names.npy` and model get out of sync, recognition names will be wrong. Retrain after adding/renaming dataset folders.
- **Database:** SQLite file defaults to `data/visitor_management.db` (gitignored); set `VISITOR_DB_PATH` before startup to override. `init_database(app)` creates missing tables on every start, then `ensure_user_schema()` adds missing `users.role`/`users.department` and `ensure_visitor_schema()` adds `visitors.host_user_id` + its index. Legacy ownership is backfilled only for unique case-insensitive host-name matches; it never drops data or assigns roles.
- **Auth/RBAC:** `SECRET_KEY` is read from `.env` (loaded by `python-dotenv`); if unset, `app.py` uses an ephemeral key and logs a warning, so sessions reset on every restart. Passwords are Werkzeug hashes only; blank emails are stored as `NULL` (unique constraint applies to real addresses only). Login failures use one generic message; inactive accounts cannot log in. `next` redirects are local-path-only.
  - Roles are `admin`/`security`/`host` (`ROLE_LABELS` in `core/models.py`). Admin is a superuser for existing features; security = admin+security; host = admin+host. Decorators live in `core/permissions.py`; hiding nav links is not the security boundary.
  - New accounts require a role in the constructor/CLI (`ValueError("A role is required.")` / `create-user --role`). The DB keeps `users.role` nullable only for legacy rows; `ensure_user_schema()` runs on every startup and adds `role`/`department` without assigning anything. Unassigned users can log in but get 403 until `flask assign-role`.
  - Unauthenticated pages redirect to `/login` with `next`; unauthenticated APIs return 401 JSON. Wrong-role requests return 403 (HTML `403.html` for pages, JSON for APIs). `/health` and `/login` are public; `/logout` is public POST.
  - Login does `session.clear()` before `login_user()` and sets an 8h permanent session; logout does `session.clear()` then `logout_user()`. Non-static responses get `no-store` cache headers, and `session-guard.js` reloads pages restored from bfcache.
  - Dashboard data is role-filtered server-side: admin sees visitor activity + all pending + inside; security sees activity + inside; host sees only their assigned pending approvals. Host ownership is checked again for each decision and capture.
  - Admin User Management lives at `/users` and `/api/users`; accounts are deactivated rather than deleted, and the server blocks self-demotion/self-deactivation.
- **Migration is idempotent:** `scripts/migrate_to_sqlite.py` skips visitors by unique `registration_id`, skips visits by `(visitor_name, entry_at)`, and compares natural-key counts for recognition events (duplicate CSV rows are preserved, not collapsed). Sources are copied to `backups/migration_<timestamp>/` and never modified.
- **Concurrency:** SQLite connections use `check_same_thread=False` + a 30s busy timeout. Core modules run queries inside `app_scope()` because the MJPEG streaming generator can execute outside the request context.
- **Foreign keys:** `PRAGMA foreign_keys=ON`; approvals cascade with a visitor, while `visits.visitor_id` is `SET NULL` and the visitor name is snapshotted. Historical tracking names may not match registrations (`tannu` vs `Tannu`, `Demo` vs `Demo Visitor`), so the link is best-effort and nullable.
- **`release_camera()` is never called** — no shutdown hook/`atexit`; camera may stay locked until process exit.
- `log_interval` throttle key is `name_status`, so frequent unknown events are throttled per status, not globally.
- Recognition events keep `event_date`/`event_time` as **strings**, preserving the historical mixed `DD-MM-YYYY`/`YYYY-MM-DD` formats and the junk `{0: 'Vandana'}` row. API shapes are unchanged.
- Legacy registrations lacking `Photo Filename` import as `""`; serializers always include the key, so the frontend's optional access still works. Decision keys are omitted when there is no stored decision detail.
- Visits use the key **`Visitor Name`** (not `Name`) and expose exactly the legacy tracking shape (`Entry Date/Time`, `Exit Date/Time`, `Status`). `app.py` joins open visitors to registrations by that key for the server-rendered Inside badge; `visitor-records.js` prefers `Name` but falls back through `name`/`Visitor Name`.
- Registration timestamps are stored as `DATETIME` and serialized as `"YYYY-MM-DD HH:MM:SS"`; the history date filter still compares the first 10 characters against `<input type="date">` values. Rows without a parseable timestamp are excluded only while a date filter is active.
- **Approval decisions:** each decision inserts an `approvals` row and updates the visitor status in one transaction. Hosts can decide only where `Visitor.host_user_id` matches their id; admins can decide any request. `decided_by` comes from `current_user.full_name`/`username`, not the request body. `decided_at` is serialized as ISO with `T`; the UI swaps `T` for a space. Older approvals have NULL maker/time and serialize without those keys, so the UI shows "Not recorded". Deleting is not exposed; history is append-only.
- **Pagination is client-side**: every API above still returns the full array; the shared paginator slices 10/page after search/filter/sort. Data refresh keeps the current page (clamped); changing search/filters resets to page 1. Server-rendered pages show only the first 10 rows for no-JS parity (`[:10]` in Jinja).
- `register_visitor` requires `name, phone, purpose, department, host_id` (`email` optional). It resolves `host_id` against `users` and rejects a missing/non-host/inactive host or a department mismatch; the Visitor row stores the host's real `full_name`, department, and `host_user_id`. Registration IDs append `secrets.token_hex(3).upper()` to avoid timestamp collisions.
- `/api/departments` and `/api/hosts` are admin/security only and read live from `users`; there is no hardcoded department/host list. Departments are distinct, non-empty values from active `host` accounts; Hosts are filtered by exact department and return `{id, full_name}` with `id` as the form value.
- The registration Department/Host selects start disabled (`Loading departments...` / `Select Department First`). Selecting a department clears the previous host and fetches that department's hosts; loading, no-host and request-error messages are shown without breaking the form. A form reset returns the Host select to its initial disabled state.
- `scripts/face_capture.py` and `scripts/face_detection.py` open their own `cv2.VideoCapture(0)` — do not run them while `app.py` streams the same camera.
- Emails only send when `.env` has `SMTP_USER` + `SMTP_PASSWORD` (`is_email_configured()`); `core/email_sender.py` never raises — failures are logged and the API still succeeds with `email_sent: false`.
- `MAX_CONTENT_LENGTH = 12 MB`; uploaded image additionally rejected if > 10 MB or not JPEG.
- Legacy data files (`data/*.json`, `data/visitor_logs.csv`) and old backups remain on disk untouched for inspection; the app no longer reads or writes them. Migration backups live in `backups/migration_<timestamp>/` (gitignored).
- To reset to a clean database, stop the app and delete `data/visitor_management.db`; tables are recreated empty on the next start. Re-run `scripts/migrate_to_sqlite.py` to re-import the legacy snapshot.

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
- [x] Consistent empty/error states everywhere (`empty-state.js`): approval
      cards, both inside-visitor lists, dashboard summaries + recent activity,
      both history tables and recent recognition events — each distinct from
      loading spinners, with actions where useful (register / review approvals /
      clear search / clear filters).
- [x] Visitor History now has a Visitor Records panel: search over name, phone,
      email, registration ID, host, department and purpose; approval-status,
      department and visit-status (inside/outside) filters; From/To date range
      on Registration Time; result count; clear-filters; client-side filtering.
- [x] Approval History page (`/approval-history` + `/api/approval-history`):
      Approved/Rejected decisions only, newest first, visitor/host/decision-maker/
      status/rejection reason; search; honest "Not recorded" for legacy approvals.
- [x] Reusable pagination (`pagination.js` + `pagination.css`, 10/page) on
      Visitor Records, Recognition Events, Approval History, Pending Approvals
      cards and both Inside Visitors lists; boundary-disabled controls, page
      clamping, reset on search/filter change, busy state during page changes,
      duplicate-click protection, and server-rendered first page for no-JS.
- [x] Authentication foundation (step 1): `User` model + hashed passwords,
      `/login`, `/logout`, `/auth-test`, safe `next`, session hardening,
      `flask create-user` CLI, and `tests/test_auth.py`.
- [x] Role-based access control (step 2): `role`/`department` + schema upgrade,
      `core/permissions.py` decorators, role-gated nav/topbar with logout,
      permission-aware dashboard, `assign-role` CLI, `403.html`, and RBAC tests.
- [x] Dynamic registration Department/Host dropdowns: `/api/departments` +
      `/api/hosts?department=…`, active-host filtering, `host_id` validation
      (role/active/department), and `host-directory.js`.
- [x] Host-owned approvals: `Visitor.host_user_id` + idempotent migration,
      host-filtered dashboard/pending/history APIs, ownership checks on
      decisions and visitor captures, server-recorded decision maker.
- [x] Admin User Management (`/users`, `/api/users`): create/edit/deactivate,
      role/department assignment, password reset, self-protection, nav link.
- [x] Logout/session/cache hardening: `session.clear()` on login/logout,
      `no-store` response headers, `session-guard.js` bfcache reload.
- [x] Test suite expanded to 33 tests (including route audit, ownership,
      admin-only user APIs, session/cache, and visitor schema migration).

Still open:

- [ ] Release camera on app shutdown (`atexit`/`signal`).
- [x] Replace flat-file storage with SQLite (Flask-SQLAlchemy) + idempotent importer; mixed legacy dates/rows preserved verbatim.
- [ ] Grow the automated test suite further (auth/RBAC/host ownership/admin users/schema migration are covered; the camera/recognition/email paths are not).
- [ ] CSRF tokens for state-changing POSTs; rate limiting is not implemented.
- [ ] Optionally expose past entry/exit records (Exited visits) in the history
      page — currently the records panel covers registrations, the logs panel
      covers recognition events, but full entry/exit history is not listed.

## 10. Git state

- Branch `main`. The working tree has **uncommitted changes** (kept unstaged on
  purpose — the user asked not to push yet): backend reorganization into
  `core/`/`scripts/`/`data/`, JS/CSS extraction, approval-workflow and
  email-template improvements, the multi-page split (`base.html` + 6 page
  templates + `static/js/pages/`), the modal/toast/loading UI system, the
  two-column approval cards, consistent empty/error states (`empty-state.js`),
  the Visitor History records panel (`visitor-records.js` + `history.css`),
  the Approval History page (`approval-history.js`, `approval_history.html`,
  `/api/approval-history`), shared pagination (`pagination.js` +
  `pagination.css`), the SQLite migration (`core/database.py`,
  `core/models.py`, `scripts/migrate_to_sqlite.py`, all core storage modules,
  `app.py` startup/log reads, requirements), the auth foundation
  (`core/auth.py`, `User` model, `templates/login.html`,
  `static/styles/auth.css`, `static/js/pages/login.js`, `tests/test_auth.py`,
  `app.py` secret/init, requirements, `.env.example`), the RBAC step
  (`core/permissions.py`, `User.role/department`, `ensure_user_schema()`,
  `create-user`/`assign-role`, route decorators, role-gated `base.html`/topbar,
  role-aware `dashboard.html`/`dashboard.js`, `templates/403.html`,
  sidebar/topbar CSS, expanded `tests/test_auth.py`), the dynamic host directory
  (`core/visitor_registration.py`, `app.py` endpoints, `templates/registration.html`,
  `static/js/host-directory.js`, `static/js/pages/registration.js`, `forms.css`),
  host-owned approvals (`Visitor.host_user_id`, `ensure_visitor_schema()`,
  host-filtered `core/host_approval.py`/`app.py`, capture ownership,
  server-recorded decision maker), admin User Management (`core/users.py`,
  `/users`, `/api/users`, `templates/users.html`,
  `static/js/pages/users.js`, `modal.js` select support), session/cache hardening
  (`core/auth.py`, `app.py` cache headers, `session-guard.js`), expanded tests,
  and `.gitignore`/README/AGENT-MAP updates. The SQLite database itself and
  migration backups are gitignored.
- Live DB was migrated after backing up to
  `backups/auth_upgrade_20261111_174358/visitor_management.db`; 1 of 16 visitor
  rows was assigned to a host (legacy names that did not uniquely match remain
  unassigned, visible only to admins).
- Tracked junk (`server_*.log`, `server_test.pid`, `visitor_registrations.json.testbak`,
  `__pycache__/` incl. a stray `__pycache__/templates/dashboard.html`) has been
  deleted from the working tree; `.gitignore` now prevents them from returning.
- When committing: stage the new `core/`, `scripts/`, `data/`, `model/haarcascade…`
  folders together with the deletions so git records the moves as renames.
