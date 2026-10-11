import csv
import os
import json
from datetime import datetime

LOG_FILE = "visitor_logs.csv"
VISIT_TRACKING_FILE = "visitor_tracking.json"
def load_visit_tracking():
    if not os.path.exists(VISIT_TRACKING_FILE):
        return []

    try:
        with open(VISIT_TRACKING_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        print("Warning: Could not read visitor tracking file.")
        return []

def mark_entry(name):
    name = name.strip()

    if not name or name == "Unknown Visitor":
        print("Cannot register entry for an unknown visitor.")
        return False

    visits = load_visit_tracking()

    # Avoid duplicate active entries for the same visitor
    for visit in visits:
        if visit["Visitor Name"] == name and visit["Status"] == "Inside":
            print(f"{name} is already marked as inside.")
            return False

    now = datetime.now()

    visits.append({
        "Visitor Name": name,
        "Entry Date": now.strftime("%Y-%m-%d"),
        "Entry Time": now.strftime("%H:%M:%S"),
        "Exit Date": "",
        "Exit Time": "",
        "Status": "Inside"
    })

    with open(VISIT_TRACKING_FILE, "w", encoding="utf-8") as file:
        json.dump(visits, file, indent=4)

    print(f"Entry recorded for {name}.")
    return True

def mark_exit(name):
    visits = load_visit_tracking()

    for visit in reversed(visits):
        if (
            visit["Visitor Name"] == name
            and visit["Status"] == "Inside"
        ):
            now = datetime.now()
            visit["Exit Date"] = now.strftime("%Y-%m-%d")
            visit["Exit Time"] = now.strftime("%H:%M:%S")
            visit["Status"] = "Exited"

            with open(VISIT_TRACKING_FILE, "w", encoding="utf-8") as file:
                json.dump(visits, file, indent=4)

            print(f"Exit recorded for {name}.")
            return True

    print(f"No active visit found for {name}.")
    return False


def log_visitor(name, status):
    file_exists = os.path.exists(LOG_FILE)

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        if not file_exists or os.path.getsize(LOG_FILE) == 0:
            writer.writerow(["Visitor Name", "Date", "Time", "Status"])

        now = datetime.now()

        writer.writerow([
            name,
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            status
        ])

    print(f"Visitor logged: {name} - {status}")


def get_open_visitors():
    """Return visitors who are currently inside."""
    visits = load_visit_tracking()
    return [
        visit for visit in visits
        if visit.get("Status") == "Inside"
    ]
