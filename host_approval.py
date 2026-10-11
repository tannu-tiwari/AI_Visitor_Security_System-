
import json
import os

from visitor_registration import REGISTRATION_FILE, load_registrations


def update_approval(registration_id, decision):
    if decision not in ("Approved", "Rejected"):
        return False, "Invalid approval decision."

    registrations = load_registrations()
    found = False

    for visitor in registrations:
        if visitor.get("Registration ID") == registration_id:
            if visitor.get("Approval Status") != "Pending":
                return False, "This request has already been processed."

            visitor["Approval Status"] = decision
            found = True
            break

    if not found:
        return False, "Visitor registration not found."

    try:
        with open(REGISTRATION_FILE, "w", encoding="utf-8") as file:
            json.dump(registrations, file, indent=4)
    except OSError:
        return False, "Could not save approval decision."

    return True, f"Visitor request {decision.lower()} successfully."


def get_pending_approvals():
    registrations = load_registrations()

    return [
        visitor for visitor in registrations
        if visitor.get("Approval Status") == "Pending"
    ]
