
from flask import Flask, render_template
import csv
import os

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


@app.route("/")
def dashboard():
    logs = get_visitor_logs()

    total_visitors = len(logs)

    recognized = sum(
        1 for log in logs
        if log.get("Status") == "Recognized"
    )

    unknown = sum(
        1 for log in logs
        if log.get("Status") == "Unknown"
    )

    return render_template(
        "dashboard.html",
        logs=logs[::-1],
        total_visitors=total_visitors,
        recognized=recognized,
        unknown=unknown
    )


if __name__ == "__main__":
    app.run(debug=True)
