from functools import wraps

from flask import jsonify, render_template, request
from flask_login import current_user, logout_user

from .auth import login_manager

JSON_PATH_PREFIXES = (
    "/api/",
    "/video_feed",
    "/camera-status",
    "/visitor-captures/",
    "/host-approval/",
)

JSON_PATHS = {
    "/save-capture",
    "/register-visitor",
    "/mark-entry",
    "/mark-exit",
}


def wants_json_response():
    """Return True for API/AJAX requests that must not receive HTML pages."""
    if request.path.startswith(JSON_PATH_PREFIXES):
        return True
    if request.path in JSON_PATHS:
        return True
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        return True
    if request.is_json:
        return True

    best = request.accept_mimetypes.best
    return best == "application/json" and (
        request.accept_mimetypes[best]
        > request.accept_mimetypes["text/html"]
    )


def _unauthenticated_response():
    if wants_json_response():
        return jsonify({"error": "Authentication required."}), 401

    return login_manager.unauthorized()


def _forbidden_response():
    if wants_json_response():
        return jsonify({
            "error": "You do not have permission to access this resource."
        }), 403

    return render_template("403.html"), 403


def roles_required(*roles):
    """
    Restrict a view to the given roles.

    Unauthenticated browser requests are redirected to the login page; API
    requests get 401 JSON. Authenticated users without an allowed role get 403
    (HTML page for browser requests, JSON for APIs). Inactive accounts are
    treated as unauthenticated.
    """
    allowed = frozenset(str(role).strip().lower() for role in roles)

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return _unauthenticated_response()

            if not current_user.is_active:
                logout_user()
                return _unauthenticated_response()

            role = str(getattr(current_user, "role", "") or "").lower()
            if role not in allowed:
                return _forbidden_response()

            return view(*args, **kwargs)

        return wrapped

    return decorator


def admin_required(view):
    return roles_required("admin")(view)


def security_required(view):
    return roles_required("admin", "security")(view)


def host_required(view):
    return roles_required("admin", "host")(view)
