
from flask import Flask, render_template, request, redirect, url_for
import csv
import os

from visitor_logs import mark_entry, mark_exit, get_open_visitors
from visitor_registration import register_visitor
from host_approval import get_pending_approvals, update_approval

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates")
)

LOG_FILE = os.path.join(BASE_DIR, "visitor_logs.csv")


def get_visitor_logs():
    if not os.path.exists(LOG_FILE):
        return []

    with open(LOG_FILE, "r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


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


@app.route("/api/visitor-logs")
def visitor_logs_api():
    logs = get_visitor_logs()
    stats = get_visitor_stats(logs)

    return {
        **stats,
        "logs": logs[::-1]
    }


@app.route("/api/open-visitors")
def open_visitors_api():
    return {"visitors": get_open_visitors()}


@app.route("/api/pending-approvals")
def pending_approvals_api():
    return {"approvals": get_pending_approvals()}



@app.route("/mark-entry", methods=["POST"])
def mark_visitor_entry():
    name = request.form.get("visitor_name", "").strip()

    if not name:
        print("Please enter a visitor name.")
        return redirect(url_for("dashboard"))

    registrations = get_pending_approvals()

    # Pending requests must not be allowed entry.
    if any(
        visitor.get("Name", "").casefold() == name.casefold()
        for visitor in registrations
    ):
        print("Entry blocked: visitor approval is still pending.")
        return redirect(url_for("dashboard"))

    from visitor_registration import load_registrations
    all_registrations = load_registrations()

    matching_visitors = [
        visitor for visitor in all_registrations
        if visitor.get("Name", "").casefold() == name.casefold()
    ]

    if matching_visitors and not any(
        visitor.get("Approval Status") == "Approved"
        for visitor in matching_visitors
    ):
        print("Entry blocked: visitor has not been approved.")
        return redirect(url_for("dashboard"))

    mark_entry(name)
    return redirect(url_for("dashboard"))



@app.route("/mark-exit", methods=["POST"])
def mark_visitor_exit():
    name = request.form.get("visitor_name", "").strip()

    if name:
        mark_exit(name)

    return redirect(url_for("dashboard"))


@app.route("/register-visitor", methods=["POST"])
def register_new_visitor():
    name = request.form.get("name", "")
    phone = request.form.get("phone", "")
    email = request.form.get("email", "")
    purpose = request.form.get("purpose", "")
    host = request.form.get("host", "")
    department = request.form.get("department", "")

    success, message = register_visitor(
        name, phone, email, purpose, host, department
    )

    print(message)
    return redirect(url_for("dashboard"))


@app.route(
    "/host-approval/<registration_id>/<decision>",
    methods=["POST"]
)
def process_host_approval(registration_id, decision):
    if decision == "approve":
        success, message = update_approval(
            registration_id, "Approved"
        )
    elif decision == "reject":
        success, message = update_approval(
            registration_id, "Rejected"
        )
    else:
        success, message = False, "Invalid approval decision."

    print(message)
    return redirect(url_for("dashboard"))


@app.route("/")
def dashboard():
    logs = get_visitor_logs()
    stats = get_visitor_stats(logs)

    return render_template(
        "dashboard.html",
        logs=logs[::-1],
        **stats
    )


if __name__ == "__main__":
    app.run(debug=True)
