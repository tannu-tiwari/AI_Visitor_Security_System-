import os
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from .database import app_scope, commit_session, db
from .models import Visitor

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

    now = datetime.now()

    visitor = Visitor(
        registration_id=f"VIS-{now.strftime('%Y%m%d%H%M%S%f')}",
        name=name,
        phone=phone,
        email=email,
        purpose=purpose,
        host=host,
        department=department,
        photo_filename=capture_filename or "",
        registered_at=now,
        approval_status="Pending",
    )

    try:
        with app_scope():
            db.session.add(visitor)
            commit_session()
            registration = visitor.to_dict()
    except SQLAlchemyError:
        print("Warning: Could not save visitor registration.")
        return False, "Could not save registration.", None

    return True, "Visitor registered. Host approval is pending.", registration
