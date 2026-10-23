import os
import csv
import base64
import binascii
from datetime import datetime
from email_sender import (
    send_registration_email,
    send_decision_email,
    is_email_configured
)

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    Response
)

from visitor_logs import (
    mark_entry,
    mark_exit,
    get_open_visitors
)

from visitor_registration import (
    register_visitor,
    load_registrations
)

from host_approval import (
    get_pending_approvals,
    update_approval
)

from face_recognition import (
    generate_frames,
    camera_available
)


# --------------------------------------------------
# APPLICATION CONFIGURATION
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "visitor_logs.csv")
CAPTURE_DIR = os.path.join(BASE_DIR, "visitor_captures")

os.makedirs(CAPTURE_DIR, exist_ok=True)

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates")
)

app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024


# --------------------------------------------------
# VISITOR LOGS AND STATISTICS
# --------------------------------------------------

def get_visitor_logs():
    if not os.path.exists(LOG_FILE):
        return []

    try:
        with open(
            LOG_FILE, "r", newline="", encoding="utf-8"
        ) as file:
            return list(csv.DictReader(file))

    except OSError:
        app.logger.exception("Could not read visitor logs")
        return []


def get_visitor_stats(logs):
    return {
        "total_visitors": len(logs),
        "recognized": sum(
            1 for log in logs
            if log.get("Status") == "Recognized"
        ),
        "unknown": sum(
            1 for log in logs
            if log.get("Status") == "Unknown"
        )
    }


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

@app.route("/")
def dashboard():
    logs = get_visitor_logs()

    return render_template(
        "dashboard.html",
        logs=logs[::-1],
        **get_visitor_stats(logs)
    )


@app.route("/health")
def health_check():
    return jsonify({
        "application": "AI-Based Smart College Visitor Management",
        "status": "running"
    })


# --------------------------------------------------
# VISITOR LOG API
# --------------------------------------------------

@app.route("/api/visitor-logs")
def visitor_logs_api():
    logs = get_visitor_logs()

    return jsonify({
        **get_visitor_stats(logs),
        "logs": logs[::-1]
    })


@app.route("/api/open-visitors")
def open_visitors_api():
    return jsonify({
        "visitors": get_open_visitors()
    })


@app.route("/api/registrations")
def registrations_api():
    return jsonify(load_registrations())


@app.route("/api/pending-approvals")
def pending_approvals_api():
    return jsonify(get_pending_approvals())


# --------------------------------------------------
# SAVE VISITOR CAMERA IMAGE
# --------------------------------------------------

@app.route("/save-capture", methods=["POST"])
def save_capture():
    data = request.get_json(silent=True) or {}
    image_data = data.get("image", "")

    prefix = "data:image/jpeg;base64,"

    if not isinstance(image_data, str) or not image_data.startswith(prefix):
        return jsonify({
            "success": False,
            "message": "Please provide a valid JPEG camera image."
        }), 400

    try:
        encoded_image = image_data.split(",", 1)[1]

        image_bytes = base64.b64decode(
            encoded_image,
            validate=True
        )

        if not image_bytes or len(image_bytes) > 10 * 1024 * 1024:
            return jsonify({
                "success": False,
                "message": "Image is empty or too large."
            }), 400

        # Verify that the data is actually a JPEG image.
        if not image_bytes.startswith(b"\xff\xd8\xff"):
            return jsonify({
                "success": False,
                "message": "Invalid JPEG image data."
            }), 400

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        filename = f"visitor_{timestamp}.jpg"
        filepath = os.path.join(CAPTURE_DIR, filename)

        with open(filepath, "wb") as image_file:
            image_file.write(image_bytes)

        return jsonify({
            "success": True,
            "filename": filename,
            "message": "Visitor image saved successfully."
        })

    except (ValueError, binascii.Error):
        return jsonify({
            "success": False,
            "message": "The image data could not be decoded."
        }), 400

    except OSError:
        app.logger.exception("Could not save visitor image")

        return jsonify({
            "success": False,
            "message": "Could not save the visitor image."
        }), 500


# --------------------------------------------------
# VISITOR REGISTRATION
# --------------------------------------------------


@app.route("/register-visitor", methods=["POST"])
def register_new_visitor():
    data = request.get_json(silent=True)

    if data is None:
        data = request.form

    success, message, visitor = register_visitor(
        data.get("name", ""),
        data.get("phone", ""),
        data.get("email", ""),
        data.get("purpose", ""),
        data.get("host", ""),
        data.get("department", ""),
        data.get("capture_filename", "")
    )

    email_sent = False

    if success and visitor:
        email_sent = send_registration_email(visitor)

    if request.is_json:
        return jsonify({
            "success": success,
            "message": message,
            "email_sent": email_sent
        }), 200 if success else 400

    return message, 200 if success else 400

# --------------------------------------------------
# HOST APPROVAL
# --------------------------------------------------

@app.route(
    "/host-approval/<registration_id>/<decision>",
    methods=["POST"]
)
def process_host_approval(registration_id, decision):
    decision = decision.lower()

    if decision == "approved":
        decision = "approve"
    elif decision == "rejected":
        decision = "reject"

    if decision not in ("approve", "reject"):
        return jsonify({
            "success": False,
            "message": "Invalid approval decision."
        }), 400

    try:
        success, message, visitor = update_approval(
            registration_id, decision
        )

        email_sent = False

        if success and visitor:
            try:
                email_sent = send_decision_email(visitor)
            except Exception:
                app.logger.exception("Could not send approval email")

        return jsonify({
            "success": success,
            "message": message,
            "email_sent": email_sent
        }), 200 if success else 400

    except Exception:
        app.logger.exception("Host approval failed")

        return jsonify({
            "success": False,
            "message": "Could not update host approval."
        }), 500


# --------------------------------------------------
# VISITOR ENTRY
# --------------------------------------------------

@app.route("/mark-entry", methods=["POST"])
def mark_visitor_entry():
    data = request.get_json(silent=True)

    if data is None:
        data = request.form

    name = data.get(
        "name",
        data.get("visitor_name", "")
    ).strip()

    if not name:
        return jsonify({
            "success": False,
            "message": "Visitor name is required."
        }), 400

    try:
        success = mark_entry(name)

        return jsonify({
            "success": bool(success),
            "message": (
                "Entry recorded."
                if success else
                "Entry was not recorded. Check the visitor's current status."
            )
        }), 200 if success else 400

    except Exception:
        app.logger.exception("Could not record visitor entry")

        return jsonify({
            "success": False,
            "message": "Could not record visitor entry."
        }), 500


# --------------------------------------------------
# VISITOR EXIT
# --------------------------------------------------

@app.route("/mark-exit", methods=["POST"])
def mark_visitor_exit():
    data = request.get_json(silent=True)

    if data is None:
        data = request.form

    name = data.get(
        "name",
        data.get("visitor_name", "")
    ).strip()

    if not name:
        return jsonify({
            "success": False,
            "message": "Visitor name is required."
        }), 400

    try:
        success = mark_exit(name)

        return jsonify({
            "success": bool(success),
            "message": (
                "Exit recorded."
                if success else
                "No active visit found for this visitor."
            )
        }), 200 if success else 400

    except Exception:
        app.logger.exception("Could not record visitor exit")

        return jsonify({
            "success": False,
            "message": "Could not record visitor exit."
        }), 500


# --------------------------------------------------
# CAMERA STATUS
# --------------------------------------------------

@app.route("/camera-status")
def camera_status():
    try:
        available = camera_available()

        return jsonify({
            "camera_available": bool(available),
            "message": (
                "Camera is available."
                if available else
                "Could not open the camera."
            )
        })

    except Exception:
        app.logger.exception("Camera status check failed")

        return jsonify({
            "camera_available": False,
            "message": "Camera check failed."
        }), 500


# --------------------------------------------------
# LIVE CAMERA FEED WITH FACE RECOGNITION
# --------------------------------------------------

@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


# --------------------------------------------------
# APPLICATION START
# --------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )