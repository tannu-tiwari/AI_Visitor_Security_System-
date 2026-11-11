from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from .database import app_scope, commit_session, db
from .models import Approval, Visitor


def update_approval(
    registration_id,
    decision,
    decided_by,
    rejection_reason=None,
    host_user_id=None,
):
    """
    Record an approval decision.

    `host_user_id` is the signed-in host's database id. Administrators pass
    None so they can act on any request; hosts may only act on requests
    assigned to their own account.
    """
    if decision == "approve":
        decision = "Approved"
    elif decision == "reject":
        decision = "Rejected"

    if decision not in ("Approved", "Rejected"):
        return False, "Invalid approval decision.", None, 400

    if not decided_by or not decided_by.strip():
        return False, "A decision maker is required.", None, 400

    if decision == "Rejected" and not rejection_reason:
        return False, "A rejection reason is required.", None, 400

    with app_scope():
        visitor = db.session.execute(
            db.select(Visitor).where(
                Visitor.registration_id == registration_id
            )
        ).scalar_one_or_none()

        if visitor is None:
            return False, "Visitor registration not found.", None, 404

        if host_user_id is not None and visitor.host_user_id != host_user_id:
            return (
                False,
                "This request is assigned to another host.",
                None,
                403,
            )

        if visitor.approval_status != "Pending":
            return False, "This request has already been processed.", None, 400

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
            return False, "Could not save approval decision.", None, 500

    return (
        True,
        f"Visitor request {decision.lower()} successfully.",
        registration,
        200,
    )


def get_pending_approvals(host_user_id=None):
    with app_scope():
        query = (
            db.select(Visitor)
            .where(Visitor.approval_status == "Pending")
            .order_by(Visitor.id)
        )
        if host_user_id is not None:
            query = query.where(Visitor.host_user_id == host_user_id)

        visitors = db.session.execute(query).scalars().all()
        return [visitor.to_dict() for visitor in visitors]


def get_approval_history(host_user_id=None):
    """
    Processed approval decisions, newest first.

    A decision is any registration whose status is Approved or Rejected.
    Pending requests are not decisions and are excluded. Older approvals may
    predate the Decision By / Decision At fields; those records are returned
    exactly as stored so callers can show them as "not recorded" instead of
    inventing decision details.

    When `host_user_id` is supplied, only decisions for requests assigned to
    that host are returned.
    """
    with app_scope():
        query = (
            db.select(Approval, Visitor)
            .join(Visitor, Approval.visitor_id == Visitor.id)
            .order_by(
                db.func.coalesce(
                    Approval.decided_at,
                    Visitor.registered_at
                ).desc(),
                Approval.id.desc()
            )
        )
        if host_user_id is not None:
            query = query.where(Visitor.host_user_id == host_user_id)

        rows = db.session.execute(query).all()

        return [
            visitor.to_dict(approval=approval)
            for approval, visitor in rows
        ]
