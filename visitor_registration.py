
import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRATION_FILE = os.path.join(BASE_DIR, "visitor_registrations.json")


def load_registrations():
    if not os.path.exists(REGISTRATION_FILE):
        return []

    try:
        with open(REGISTRATION_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        print("Warning: Could not read visitor registrations.")
        return []


def register_visitor(
    name, phone, email, purpose, host, department,
    capture_filename=""
):
    name = name.strip()
    phone = phone.strip()
    email = email.strip()
    purpose = purpose.strip()
    host = host.strip()
    department = department.strip()

    if not all([name, phone, purpose, host, department]):
        return False, "Please fill in all required fields.", None

    registrations = load_registrations()

    visitor = {
        "Registration ID": f"VIS-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "Name": name,
        "Phone": phone,
        "Email": email,
        "Purpose": purpose,
        "Host": host,
        "Department": department,
        "Photo Filename": capture_filename,
        "Registration Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Approval Status": "Pending"
    }

    registrations.append(visitor)

    try:
        with open(REGISTRATION_FILE, "w", encoding="utf-8") as file:
            json.dump(registrations, file, indent=4)
    except OSError:
        return False, "Could not save registration.", None

    return True, "Visitor registered. Host approval is pending.", visitor