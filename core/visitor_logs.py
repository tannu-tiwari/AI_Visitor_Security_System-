import os
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from .database import app_scope, commit_session, db
from .models import RecognitionEvent, Visit, Visitor

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Legacy CSV/JSON stores. They are kept on disk (see
# scripts/migrate_to_sqlite.py) but are no longer written or read by the
# running application.
LOG_FILE = os.path.join(BASE_DIR, "data", "visitor_logs.csv")
VISIT_TRACKING_FILE = os.path.join(BASE_DIR, "data", "visitor_tracking.json")


def load_logs():
    """Recognition events in the order they were recorded (oldest first)."""
    with app_scope():
        events = (
            db.session.execute(
                db.select(RecognitionEvent).order_by(RecognitionEvent.id)
            )
            .scalars()
            .all()
        )
        return [event.to_dict() for event in events]


def load_visit_tracking():
    with app_scope():
        visits = (
            db.session.execute(db.select(Visit).order_by(Visit.id))
            .scalars()
            .all()
        )
        return [visit.to_dict() for visit in visits]


def _find_visitor(name):
    """Best-effort link from a tracking name to a registration."""
    visitor = db.session.execute(
        db.select(Visitor).where(Visitor.name == name).order_by(Visitor.id)
    ).scalars().first()

    if visitor is not None:
        return visitor

    return db.session.execute(
        db.select(Visitor)
        .where(db.func.lower(Visitor.name) == name.lower())
        .order_by(Visitor.id)
    ).scalars().first()


def mark_entry(name):
    name = name.strip()

    if not name or name == "Unknown Visitor":
        print("Cannot register entry for an unknown visitor.")
        return False

    with app_scope():
        active = db.session.execute(
            db.select(Visit).where(
                Visit.visitor_name == name,
                Visit.status == "Inside",
            )
        ).scalars().first()

        # Avoid duplicate active entries for the same visitor
        if active is not None:
            print(f"{name} is already marked as inside.")
            return False

        visitor = _find_visitor(name)
        visit = Visit(
            visitor_id=visitor.id if visitor is not None else None,
            visitor_name=name,
            entry_at=datetime.now(),
            exit_at=None,
            status="Inside",
        )

        try:
            db.session.add(visit)
            commit_session()
        except SQLAlchemyError:
            print("Warning: Could not save visitor entry.")
            raise

    print(f"Entry recorded for {name}.")
    return True


def mark_exit(name):
    name = name.strip()

    with app_scope():
        visit = db.session.execute(
            db.select(Visit)
            .where(
                Visit.visitor_name == name,
                Visit.status == "Inside",
            )
            .order_by(Visit.id.desc())
        ).scalars().first()

        if visit is None:
            print(f"No active visit found for {name}.")
            return False

        visit.exit_at = datetime.now()
        visit.status = "Exited"

        try:
            commit_session()
        except SQLAlchemyError:
            print("Warning: Could not save visitor exit.")
            raise

    print(f"Exit recorded for {name}.")
    return True


def log_visitor(name, status):
    now = datetime.now()

    event = RecognitionEvent(
        visitor_name=name,
        event_date=now.strftime("%Y-%m-%d"),
        event_time=now.strftime("%H:%M:%S"),
        status=status,
    )

    try:
        with app_scope():
            db.session.add(event)
            commit_session()
    except SQLAlchemyError:
        print("Warning: Could not save visitor log.")
        raise

    print(f"Visitor logged: {name} - {status}")


def get_open_visitors():
    """Return visitors who are currently inside."""
    with app_scope():
        visits = (
            db.session.execute(
                db.select(Visit)
                .where(Visit.status == "Inside")
                .order_by(Visit.id)
            )
            .scalars()
            .all()
        )
        return [visit.to_dict() for visit in visits]
