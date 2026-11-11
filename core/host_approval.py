from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from .database import app_scope, commit_session, db
from .models import Approval, Visitor


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

    with app_scope():
        visitor = db.session.execute(
            db.select(Visitor).where(
                Visitor.registration_id == registration_id
            )
        ).scalar_one_or_none()

        if visitor is None:
            return False, "Visitor registration not found.", None

        if visitor.approval_status != "Pending":
            return False, "This request has already been processed.", None

        approval = Approval(
            visitor=visitor,
            decision=decision,
            decision_maker=decided_by.strip(),
            decided_at=datetime.now(),
            rejection_reason=(
                rejection_reason.strip()
                if decision == "Rejected" else None
            ),
        )

        visitor.approval_status = decision

        try:
            db.session.add(approval)
            commit_session()
            registration = visitor.to_dict(approval=approval)
        except SQLAlchemyError:
            print("Warning: Could not save approval decision.")
            return False, "Could not save approval decision.", None

    return True, f"Visitor request {decision.lower()} successfully.", registration


def get_pending_approvals():
    with app_scope():
        visitors = (
            db.session.execute(
                db.select(Visitor)
                .where(Visitor.approval_status == "Pending")
                .order_by(Visitor.id)
            )
            .scalars()
            .all()
        )
        return [visitor.to_dict() for visitor in visitors]


def get_approval_history():
    """
    Processed approval decisions, newest first.

    A decision is any registration whose status is Approved or Rejected.
    Pending requests are not decisions and are excluded. Older approvals may
    predate the Decision By / Decision At fields; those records are returned
    exactly as stored so callers can show them as "not recorded" instead of
    inventing decision details.
    """
    with app_scope():
        rows = db.session.execute(
            db.select(Approval, Visitor)
            .join(Visitor, Approval.visitor_id == Visitor.id)
            .order_by(
                db.func.coalesce(
                    Approval.decided_at,
                    Visitor.registered_at
                ).desc(),
                Approval.id.desc()
            )
        ).all()

        return [
            visitor.to_dict(approval=approval)
            for approval, visitor in rows
        ]
