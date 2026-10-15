# FIXES.md — Bug Report & Remediation Plan

Audit of the AI Visitor Security System. Each item lists the problem, the exact
location, the impact, and a suggested fix. Severity order: Critical → High →
Medium → Low → Future.

Status legend: `[ ]` todo, `[x]` done.

---

## CRITICAL

### 1. `visitor_logs.py` uses relative file paths (wrong working directory)
- **Where:** `visitor_logs.py:6-7`
  ```python
  LOG_FILE = "visitor_logs.csv"
  VISIT_TRACKING_FILE = "visitor_tracking.json"
  ```
- **Why it's a bug:** Every other module anchors paths to `BASE_DIR`
  (`app.py:41-43`, `visitor_registration.py:6-7`). These two are relative to the
  process **current working directory**. If the app is started from any folder
  other than the project root:
  - Recognition events are written to `<cwd>/visitor_logs.csv`, but the
    dashboard reads `<project>/visitor_logs.csv` → **logged visitors never show
    up**.
  - Entry/exit records are split across two different files.
- **Fix:**
  ```python
  BASE_DIR = os.path.dirname(os.path.abspath(__file__))
  LOG_FILE = os.path.join(BASE_DIR, "visitor_logs.csv")
  VISIT_TRACKING_FILE = os.path.join(BASE_DIR, "visitor_tracking.json")
  ```
- [ ]

### 2. Dashboard references a non-existent element `cameraMessage`
- **Where:** `templates/dashboard.html:1024` and `:1030`
  ```js
  $("cameraMessage").textContent = data.message;
  ```
  There is **no** element with `id="cameraMessage"` in the template (verified).
- **Impact:** In `checkCamera()`, the assignment throws `TypeError`, which is
  caught by the surrounding `catch`. The result: the camera status **always**
  shows "Status Unavailable" / red error badge and the message "Could not
  contact the Flask server", even when the camera is perfectly fine.
- **Fix (pick one):**
  - Remove both `cameraMessage` lines, **or**
  - Add the missing element in the Camera Status panel, e.g.
    ```html
    <p id="cameraMessage" style="font-size:12px; color:var(--muted);"></p>
    ```
    inside the `panel-heading` block near `cameraBadge`.
- [ ]

### 3. Missing `cv2` prevents the entire app from starting
- **Where:** `app.py:31-34` imports from `face_recognition`, which does
  `import cv2` at module top (`face_recognition.py:5`).
- **Impact:** If OpenCV isn't installed, `import` fails and **Flask never
  starts** — the registration/tracking dashboard is unusable, not just the
  camera. (Confirmed: this environment has Flask + numpy but no `cv2`.)
- **Fix:** Guard the CV import so the dashboard still runs without a camera:
  ```python
  try:
      from face_recognition import generate_frames, camera_available
      CV_AVAILABLE = True
  except ImportError as exc:
      CV_AVAILABLE = False
      _cv_error = exc
      def generate_frames(): ...
      def camera_available(): return False
  ```
  Also add `requirements.txt` (already added) and document the optional import.
- [ ]

---

## HIGH

### 4. "Approved Visitors" never clears; visitors can be marked in repeatedly
- **Where:** `templates/dashboard.html:1135-1181` (`loadApprovedVisitors`) and
  `visitor_registration.py` / `visitor_logs.py:19-49` (`mark_entry`).
- **Impact:** A registration's `Approval Status` becomes `Approved` and stays
  that way forever. It keeps appearing under "Approved Visitors" even after the
  visitor has entered and exited, so staff can click "Mark Entry" again and again.
  There is no link between an approved registration and an active/closed visit.
- **Fix:** Introduce an entry lifecycle on the registration:
  - Add `Entry Status` (`Awaiting Entry` → `Entered` → `Exited`) to each
    registration record.
  - On `/mark-entry`, set the matching registration to `Entered` and reject if
    it isn't `Awaiting Entry`.
  - On `/mark-exit`, set it to `Exited`.
  - In `loadApprovedVisitors`, filter to
    `Approval Status == "Approved" && Entry Status == "Awaiting Entry"`.
- [ ]

### 5. Visitor names are matched case-sensitively / inconsistently
- **Where:** `visitor_logs.py:30,56` compare `visit["Visitor Name"] == name`
  exactly; `visitor_registration.py` stores `Name`; the live file
  `visitor_tracking.json` already contains a lowercase `"tannu"` while
  registrations use `"Tannu"`.
- **Impact:** `mark_entry` / `mark_exit` / duplicate detection fail or create
  duplicate open records when casing or spacing differs.
- **Fix:** Normalize names consistently, e.g. a helper
  ```python
  def _norm(name): return " ".join(str(name).split()).casefold()
  ```
  and compare `_norm(visit["Visitor Name"]) == _norm(name)`. Better: key visits
  by `Registration ID` instead of name.
- [ ]

### 6. Unsynchronized concurrent writes can corrupt the JSON files
- **Where:** `visitor_registration.py:53-55`, `host_approval.py:31-33`,
  `visitor_logs.py:45-46,64-65`. Flask runs with `threaded=True`
  (`app.py:428`), and `face_recognition` writes CSV from a background loop.
- **Impact:** Two simultaneous requests (e.g. two approvals, or an approval plus
  a registration) can interleave `open(...,"w")`/`json.dump`, producing
  truncated/invalid JSON that breaks every reader.
- **Fix:** Add a module-level `threading.Lock()` (or a shared storage helper)
  around read-modify-write, and write atomically:
  ```python
  tmp = path + ".tmp"
  with open(tmp, "w", encoding="utf-8") as f:
      json.dump(data, f, indent=4)
  os.replace(tmp, path)
  ```
- [ ]

---

## MEDIUM

### 7. Camera concurrency & no shutdown release
- **Where:** `face_recognition.py:118-228`.
- **Issues:**
  - Every `/video_feed` client spawns a generator that reads the **same**
    `_camera`; two browser tabs → interleaved/corrupt frames.
  - `_last_logged` (`face_recognition.py:27`) is shared and mutated without a
    lock.
  - `release_camera()` (`:218`) is never called — the webcam stays locked until
    the process dies, and other tools (`face_capture.py`) can't use it.
- **Fix:** Allow only one active stream (guard with a flag), lock `_last_logged`,
  and register cleanup with `atexit.register(release_camera)` in `app.py`.
- [ ]

### 8. Recognition never retries after a failed init
- **Where:** `face_recognition.py:45-46, 86-89` — `_initialization_error` is set
  and permanently short-circuits future calls.
- **Impact:** If the model is missing at startup, recognizing can never recover
  even after you run `train_model.py`; you must restart the server.
- **Fix:** Re-attempt initialization when the cached error exists (optionally
  after the model files' mtime changes), or expose a `/reload-model` endpoint.
- [ ]

### 9. Inconsistent date formats and a corrupted CSV row
- **Where:** `visitor_logs.csv` mixes `DD-MM-YYYY` (legacy rows 2-19) with
  `YYYY-MM-DD` (rows 20+, produced by `visitor_logs.py:88`), and row 4 is junk:
  `{0: 'Vandana'},09-10-2026,10:21:05,Recognized`.
- **Impact:** Sorting/filtering and any date parsing is unreliable; the junk row
  surfaces in the UI.
- **Fix:** Standardize on ISO `YYYY-MM-DD` in code (already used), clean the
  existing file, and parse/normalize legacy rows once.
- [ ]

### 10. Thin server-side validation
- **Where:** `visitor_registration.py:22-35` only checks required fields.
- **Issues:** No phone format check server-side (frontend `pattern` can be
  bypassed), no email validation, duplicate registrations allowed, no
  registration-ID collision guard beyond timestamp.
- **Fix:** Validate `phone` (10 digits), `email` (if present), reject duplicate
  active registrations for the same name/phone.
- [ ]

### 11. `MAX_CONTENT_LENGTH` overshoot returns HTML, not JSON
- **Where:** `app.py:52` sets 12 MB; `save_capture` independently checks 10 MB.
- **Impact:** A request over 12 MB triggers Flask's default 413 HTML page; the
  dashboard's `fetchJSON` throws on non-JSON and shows a generic error.
- **Fix:** Add a `@app.errorhandler(413)` returning JSON, and align limits.
- [ ]

### 12. Non-dict JSON bodies crash handlers
- **Where:** `app.py:218-221, 299-307, 343-351` call `data.get(...)` after
  `request.get_json(silent=True)`. A JSON array/string body yields a non-dict.
- **Fix:** Coerce/validate: `if not isinstance(data, dict): data = request.form`
  (form is mapping-like) or return 400.
- [ ]

---

## LOW / CLEANUP

### 13. Delete dead backup files
`app_backup.py`, `face_recognition_backup.py`, `visitor_logs_backup.py`,
`visitor_logs_backup.csv`, `templates/dashboard_backup.html`.
`visitor_logs_backup.py` is byte-identical to `visitor_logs.py`; `app_backup.py`
returns raw dicts and uses `redirect` — none are imported anywhere. Safe to remove.
- [ ]

### 14. Stop tracking `__pycache__/` and add `.gitignore`
`__pycache__/*.pyc` and `__pycache__/templates/dashboard.html` are committed.
Add a `.gitignore` (`__pycache__/`, `*.pyc`, `venv/`, `visitor_captures/`) and
`git rm -r --cached __pycache__`.
- [ ]

### 15. `face_detection.py` uses bundled cv2 cascade instead of the repo file
It loads `cv2.data.haarcascades + "haarcascade_frontalface_default.xml"` while
the repo ships its own XML. Harmless stand-alone demo, but inconsistent — align
it or mark the file as a demo. Comments are in Hindi.
- [ ]

### 16. No authentication on any endpoint
`/host-approval/*`, `/mark-entry`, `/mark-exit`, `/register-visitor`,
`/save-capture`, and all `/api/*` are open. Anyone who can reach port 5000 can
approve visitors or forge entries. Add at least host/staff auth (or bind to
localhost only, which it already does by default).
- [ ]

### 17. Redundant decision normalization
`app.py:250-256` converts `approved→approve`, then `host_approval.py:9-12`
converts `approve→Approved`. Pick one place to normalize.
- [ ]

### 18. Minor: unbounded growth
`visitor_captures/`, `visitor_logs.csv`, and `visitor_tracking.json` grow
forever. Add retention/archival or a `cleanup` script. Also `_last_logged` never
pruned.
- [ ]

---

## FUTURE FEATURE (do NOT implement yet)

### WhatsApp bot integration
Deferred by request. When implemented, likely surface points:
- On `/register-visitor` → notify the **host** with an approve/reject link
  (reuse `/host-approval/<id>/<decision>`).
- On host decision → notify the **visitor** with entry instructions.
- On `/mark-entry` / `/mark-exit` → optional status messages.

Design notes for later: choose a provider (Twilio WhatsApp API, Meta Cloud API,
or a library like `pywhatkit`/`whatsapp-web.js` bridge), keep credentials in
environment variables, and make sending asynchronous so it can't block the
webcam/HTTP threads. Also add an outbound-message log + retry queue, and only
send after items **4** and **6** above are fixed so state is consistent.
- [ ] (deferred)

---

## Verified-good (no action)
- `train_model.py` label ordering matches `face_recognition.py` indexing
  (sorted folder names → `label_names.npy`).
- LBPH threshold logic (`distance < 50`) and `100 - distance` score are correct.
- `/save-capture` validates the base64 prefix, JPEG magic bytes, and size.
- Frontend escapes HTML in list/table rendering (`escapeHTML`), mitigating XSS.
- `app.run(use_reloader=False)` correctly avoids double camera acquisition.
