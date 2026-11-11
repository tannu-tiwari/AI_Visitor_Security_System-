import json
from .visitor_registration import REGISTRATION_FILE, load_registrations

def update_approval(registration_id, decision, decided_by, rejection_reason=None):
    if decision == "approve":
        decision = "Approved"
    elif decision == "reject":
        decision = "Rejected"

    if decision not in ("Approved", "Rejected"):
        return False, "Invalid approval decision.", None

    if not decided_by or not decided_by.strip():
        return False, "Host name is required.", None

    if decision == "Rejected" and not rejection_reason:
        return False, "A rejection reason is required.", None

    registrations = load_registrations()
    visitor = None

    for registration in registrations:
        if registration.get("Registration ID") == registration_id:
            if registration.get("Approval Status") != "Pending":
                return False, "This request has already been processed.", None

            visitor = registration
            break

    if visitor is None:
        return False, "Visitor registration not found.", None

    visitor["Approval Status"] = decision
    visitor["Decision By"] = decided_by.strip()
    visitor["Decision At"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")

    if decision == "Rejected":
        visitor["Rejection Reason"] = rejection_reason.strip()

    try:
        with open(REGISTRATION_FILE, "w", encoding="utf-8") as file:
            json.dump(registrations, file, indent=4)

    except OSError:
        return False, "Could not save approval decision.", None

    return True, f"Visitor request {decision.lower()} successfully.", visitor


def get_pending_approvals():
    registrations = load_registrations()

    return [
        visitor for visitor in registrations
        if visitor.get("Approval Status") == "Pending"
    ]
