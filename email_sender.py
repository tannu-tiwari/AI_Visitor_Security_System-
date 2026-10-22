
import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() in (
    "true",
    "1",
    "yes",
)


def is_email_configured() -> bool:
    """Return True if SMTP username and password are configured."""
    return bool(SMTP_USER and SMTP_PASSWORD)


def build_registration_email(visitor: dict) -> tuple[str, str]:
    """Build the registration email subject and plain-text body."""
    subject = "Visitor Registration - Pending Host Approval"

    body = f"""Visitor Registration Details

Name: {visitor.get('Name', '')}
Registration ID: {visitor.get('Registration ID', '')}
Phone: {visitor.get('Phone', '')}
Email: {visitor.get('Email', '')}
Department: {visitor.get('Department', '')}
Purpose: {visitor.get('Purpose', '')}
Host: {visitor.get('Host', '')}
Registration Time: {visitor.get('Registration Time', '')}

Status: Pending host approval
"""

    return subject, body


def send_registration_email(visitor: dict) -> bool:
    """Send a registration email. Never raise exceptions."""
    try:
        recipient = visitor.get("Email")

        if not recipient or not recipient.strip():
            return False

        if not is_email_configured():
            return False

        if not SMTP_HOST or not SMTP_FROM:
            return False

        subject, body = build_registration_email(visitor)

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = SMTP_FROM
        message["To"] = recipient.strip()
        message.set_content(body)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            if SMTP_USE_TLS:
                server.starttls()

            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)

        return True

    except Exception:
        return False
