import csv
import os
from datetime import datetime

LOG_FILE = "visitor_logs.csv"

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


if __name__ == "__main__":
    log_visitor("Vandana", "Recognized")
    log_visitor("Unknown Visitor", "Unknown")
    print("Visitor logs saved to", LOG_FILE)