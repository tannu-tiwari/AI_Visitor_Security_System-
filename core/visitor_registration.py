import logging
import os
import secrets
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from .database import app_scope, commit_session, db
from .models import User, Visitor

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Legacy JSON store. It is kept on disk (see scripts/migrate_to_sqlite.py) but
# is no longer written or read by the running application.
REGISTRATION_FILE = os.path.join(BASE_DIR, "data", "visitor_registrations.json")


def load_registrations():
    with app_scope():
        visitors = (
            db.session.execute(db.select(Visitor).order_by(Visitor.id))
            .scalars()
            .all()
        )
        return [visitor.to_dict() for visitor in visitors]


def get_host_departments():
    """Distinct departments of active host accounts, sorted for display."""
    with app_scope():
        rows = db.session.execute(
            db.select(User.department).where(
                User.role == "host",
                User.is_active.is_(True),
                User.department.isnot(None),
            )
        ).scalars().all()

    departments = {
        department.strip()
        for department in rows
        if department and department.strip()
    }
    return sorted(departments, key=str.casefold)


def get_hosts_for_department(department):
    """Active hosts in one department, returned as id/name pairs."""
    department = (department or "").strip()
    if not department:
        return []

    with app_scope():
        hosts = db.session.execute(
            db.select(User)
            .where(
                User.role == "host",
                User.is_active.is_(True),
                db.func.trim(User.department) == department,
            )
            .order_by(db.func.lower(User.full_name), User.id)
        ).scalars().all()

        return [
            {"id": host.id, "full_name": host.full_name}
            for host in hosts
        ]


def host_owns_capture(filename, host_user_id):
    """Return True when a visitor photo belongs to this host's requests."""
    if not filename or host_user_id is None:
        return False

    with app_scope():
        row = db.session.execute(
            db.select(Visitor.id).where(
                Visitor.photo_filename == filename,
                Visitor.host_user_id == host_user_id,
            ).limit(1)
        ).first()
    return row is not None


def _validate_host(host_id, department):
    """Return (host, error) for an active host in the submitted department."""
    try:
        host_id = int(str(host_id).strip())
    except (TypeError, ValueError):
        return None, "Please select a valid host."

    host = db.session.get(User, host_id)

    if host is None:
        return None, "The selected host no longer exists."

    if host.role != "host":
        return None, "The selected user is not a host."

    if not host.is_active:
        return None, "The selected host is inactive."

    host_department = (host.department or "").strip()
    if not host_department:
        return None, "The selected host has no department."

    if host_department.casefold() != department.casefold():
        return None, "The selected host does not belong to this department."

    return host, None


def register_visitor(
    name, phone, email, purpose, host_id, department,
    capture_filename=""
):
    name = name.strip()
    phone = phone.strip()
    email = email.strip()
    purpose = purpose.strip()
    department = department.strip()
    host_id = str(host_id or "").strip()

    if not all([name, phone, purpose, department]):
        return False, "Please fill in all required fields.", None

    if not host_id:
        return False, "Please select a host.", None

    with app_scope():
        host, error = _validate_host(host_id, department)
        if error:
            return False, error, None

        host_name = (host.full_name or "").strip()
        if not host_name:
            return False, "The selected host has no name.", None

        now = datetime.now()

        visitor = Visitor(
            registration_id=(
                f"VIS-{now.strftime('%Y%m%d%H%M%S%f')}"
                f"{secrets.token_hex(3).upper()}"
            ),
            name=name,
            phone=phone,
            email=email,
            purpose=purpose,
            host=host_name,
            host_user_id=host.id,
            department=host.department.strip(),
            photo_filename=capture_filename or "",
            registered_at=now,
            approval_status="Pending",
        )

        try:
            db.session.add(visitor)
            commit_session()
            registration = visitor.to_dict()
        except SQLAlchemyError:
            logging.getLogger(__name__).exception(
                "Could not save visitor registration"
            )
            return False, "Could not save registration.", None

    return True, "Visitor registered. Host approval is pending.", registration
