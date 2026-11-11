from datetime import datetime

from .database import db


REGISTRATION_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def format_registration_time(value):
    """Format a stored timestamp the way the JSON API always has."""
    return value.strftime(REGISTRATION_TIME_FORMAT) if value else ""


def format_decision_time(value):
    """Decision timestamps keep the original ISO (T-separated) format."""
    return value.isoformat(timespec="seconds") if value else ""


class Visitor(db.Model):
    """
    A visitor registration.

    This replaces data/visitor_registrations.json. The approval status is kept
    on the visitor (the current workflow has exactly one decision per request)
    while each decision is also recorded in Approval for history.
    """

    __tablename__ = "visitors"

    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(
        db.String(64), nullable=False, unique=True, index=True
    )
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=False, default="")
    email = db.Column(db.String(200), nullable=True, default="")
    purpose = db.Column(db.String(200), nullable=False, default="")
    host = db.Column(db.String(120), nullable=False, default="")
    department = db.Column(db.String(120), nullable=False, default="")
    photo_filename = db.Column(db.String(255), nullable=True, default="")
    registered_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    approval_status = db.Column(
        db.String(20), nullable=False, default="Pending", index=True
    )

    __table_args__ = (
        db.CheckConstraint(
            "approval_status IN ('Pending', 'Approved', 'Rejected')",
            name="ck_visitor_approval_status",
        ),
    )

    approvals = db.relationship(
        "Approval",
        back_populates="visitor",
        cascade="all, delete-orphan",
        order_by="Approval.id",
    )
    visits = db.relationship(
        "Visit",
        back_populates="visitor",
        order_by="Visit.id",
    )

    def latest_approval(self):
        return self.approvals[-1] if self.approvals else None

    def to_dict(self, approval=None):
        """
        Serialize to the legacy registration dictionary shape.

        Missing optional values are omitted so API responses match the JSON
        files this replaces (e.g. legacy approvals have no Decision fields).
        """
        if approval is None:
            approval = self.latest_approval()

        data = {
            "Registration ID": self.registration_id,
            "Name": self.name,
            "Phone": self.phone or "",
            "Email": self.email or "",
            "Purpose": self.purpose or "",
            "Host": self.host or "",
            "Department": self.department or "",
            "Registration Time": format_registration_time(self.registered_at),
            "Approval Status": self.approval_status,
        }

        data["Photo Filename"] = self.photo_filename or ""

        if approval is not None:
            if approval.decision_maker:
                data["Decision By"] = approval.decision_maker
            if approval.decided_at:
                data["Decision At"] = format_decision_time(approval.decided_at)
            if approval.rejection_reason:
                data["Rejection Reason"] = approval.rejection_reason

        return data


class Approval(db.Model):
    """
    One recorded approval/rejection decision.

    Replaces the Decision By / Decision At / Rejection Reason fields that used
    to be written into the registration JSON. Rows imported from pre-audit
    approvals may have no decision maker or timestamp; those stay NULL rather
    than being invented.
    """

    __tablename__ = "approvals"

    id = db.Column(db.Integer, primary_key=True)
    visitor_id = db.Column(
        db.Integer,
        db.ForeignKey("visitors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision = db.Column(db.String(20), nullable=False)
    decision_maker = db.Column(db.String(120), nullable=True)
    decided_at = db.Column(db.DateTime, nullable=True, index=True)
    rejection_reason = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.CheckConstraint(
            "decision IN ('Approved', 'Rejected')",
            name="ck_approval_decision",
        ),
    )

    visitor = db.relationship("Visitor", back_populates="approvals")


class Visit(db.Model):
    """
    An entry/exit record.

    Replaces data/visitor_tracking.json. Tracking records only store a visitor
    name, so the name is snapshotted here; the visitor link is best-effort and
    nullable (some historical names have no matching registration).
    """

    __tablename__ = "visits"

    id = db.Column(db.Integer, primary_key=True)
    visitor_id = db.Column(
        db.Integer,
        db.ForeignKey("visitors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    visitor_name = db.Column(db.String(120), nullable=False, index=True)
    entry_at = db.Column(db.DateTime, nullable=False, index=True)
    exit_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Inside")

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('Inside', 'Exited')",
            name="ck_visit_status",
        ),
    )

    visitor = db.relationship("Visitor", back_populates="visits")

    def to_dict(self):
        """Serialize to the legacy tracking-record shape."""
        return {
            "Visitor Name": self.visitor_name,
            "Entry Date": self.entry_at.strftime("%Y-%m-%d"),
            "Entry Time": self.entry_at.strftime("%H:%M:%S"),
            "Exit Date": self.exit_at.strftime("%Y-%m-%d") if self.exit_at else "",
            "Exit Time": self.exit_at.strftime("%H:%M:%S") if self.exit_at else "",
            "Status": self.status,
        }


class RecognitionEvent(db.Model):
    """
    A face-recognition event.

    Replaces data/visitor_logs.csv. Date and time stay as strings because the
    CSV contains a mix of legacy DD-MM-YYYY and newer YYYY-MM-DD values; this
    preserves every historical row exactly and keeps the dashboard display
    unchanged.
    """

    __tablename__ = "recognition_events"

    id = db.Column(db.Integer, primary_key=True)
    visitor_name = db.Column(db.String(120), nullable=False, index=True)
    event_date = db.Column(db.String(20), nullable=False)
    event_time = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False)

    def to_dict(self):
        """Serialize to the legacy CSV row shape."""
        return {
            "Visitor Name": self.visitor_name,
            "Date": self.event_date,
            "Time": self.event_time,
            "Status": self.status,
        }
