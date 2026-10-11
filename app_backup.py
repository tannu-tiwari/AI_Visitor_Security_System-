
from flask import Flask, render_template, request, redirect, url_for
import csv
import os
from visitor_logs import mark_entry, mark_exit, get_open_visitors

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


@app.route("/mark-entry", methods=["POST"])
def mark_visitor_entry():
    name = request.form.get("visitor_name", "").strip()

    if name:
        mark_entry(name)

    return redirect(url_for("dashboard"))


@app.route("/mark-exit", methods=["POST"])
def mark_visitor_exit():
    name = request.form.get("visitor_name", "").strip()

    if name:
        mark_exit(name)

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
