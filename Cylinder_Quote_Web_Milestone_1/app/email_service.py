from __future__ import annotations

import logging
import os
import re
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from .models_db import EmailLog, Quote, utc_now
from .pdf_service import quote_pdf_absolute_path

logger = logging.getLogger(__name__)

_RECIPIENT_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value in ("1", "true", "yes", "on")


def is_email_configured() -> bool:
    """Return True only when the minimum required SMTP settings are present."""
    host = (os.environ.get("SMTP_HOST") or "").strip()
    from_address = (os.environ.get("SMTP_FROM_ADDRESS") or "").strip()
    return bool(host and from_address)


def _is_valid_email(address: str) -> bool:
    return bool(_RECIPIENT_RE.match(address))


def validate_recipients(recipients: Any) -> list[str]:
    """Validate and normalize a list of recipient email addresses.

    Raises:
        ValueError: if recipients is missing, not a list, empty, or contains
            syntactically invalid addresses.
    """
    if not isinstance(recipients, list):
        raise ValueError("recipients must be a list")

    cleaned = [str(addr).strip() for addr in recipients if str(addr).strip()]
    if not cleaned:
        raise ValueError("recipients is required")

    invalid = [addr for addr in cleaned if not _is_valid_email(addr)]
    if invalid:
        raise ValueError(f"Invalid recipient email addresses: {', '.join(invalid)}")

    return cleaned


def _smtp_port() -> int:
    raw = os.environ.get("SMTP_PORT", "587") or "587"
    try:
        return int(raw)
    except ValueError:
        return 587


def send_quote_email(
    session,
    quote: Quote,
    document,
    recipients: list[str],
    *,
    subject_override: str | None = None,
    sent_by_user=None,
) -> EmailLog:
    """Send a quote PDF by email and persist an EmailLog row.

    If email is not configured, an ``EmailLog`` with
    ``status='not_configured'`` is returned and no SMTP connection is
    attempted. SMTP failures are captured in an ``EmailLog`` with
    ``status='failed'`` and are not re-raised.
    """
    recipients = validate_recipients(recipients)
    subject = subject_override or f"Quote {quote.quote_number} rev {quote.revision}"

    if not is_email_configured():
        return EmailLog(
            quote=quote,
            revision=quote.revision,
            recipients=recipients,
            subject=subject,
            sent_by_user_id=sent_by_user.id if sent_by_user else None,
            status="not_configured",
            error_message="Email is not configured in this environment",
            document_id=document.id if document else None,
        )

    from_address = os.environ.get("SMTP_FROM_ADDRESS", "").strip()
    host = os.environ.get("SMTP_HOST", "").strip()
    port = _smtp_port()
    use_tls = _env_bool("SMTP_USE_TLS", default=True)
    username = (os.environ.get("SMTP_USERNAME") or "").strip() or None
    password = os.environ.get("SMTP_PASSWORD") or ""

    pdf_path = quote_pdf_absolute_path(quote)

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_address
        msg["To"] = ", ".join(recipients)
        msg.set_content(
            f"Please find attached Quote {quote.quote_number} revision {quote.revision}."
        )
        msg.add_attachment(
            pdf_path.read_bytes(),
            maintype="application",
            subtype="pdf",
            filename=pdf_path.name,
        )

        with smtplib.SMTP(host, port) as server:
            if use_tls:
                server.starttls()
            if username:
                server.login(username, password)
            server.send_message(msg)

        return EmailLog(
            quote=quote,
            revision=quote.revision,
            recipients=recipients,
            subject=subject,
            sent_by_user_id=sent_by_user.id if sent_by_user else None,
            status="sent",
            document_id=document.id if document else None,
        )
    except (smtplib.SMTPException, OSError) as exc:
        logger.exception("Failed to send quote email for quote %s", quote.quote_number)
        return EmailLog(
            quote=quote,
            revision=quote.revision,
            recipients=recipients,
            subject=subject,
            sent_by_user_id=sent_by_user.id if sent_by_user else None,
            status="failed",
            error_message=str(exc),
            document_id=document.id if document else None,
        )



def send_order_approval_email(
    quote: Quote,
    approval_url: str,
    recipient: str,
    *,
    sent_by_user,
) -> EmailLog:
    """Email an internal link to the editable Order Form."""
    recipients = validate_recipients([recipient])
    subject = f"Order approval requested: {quote.quote_number}"

    if not is_email_configured():
        return EmailLog(
            quote=quote, revision=quote.revision, recipients=recipients,
            subject=subject, sent_by_user_id=sent_by_user.id,
            status="not_configured",
            error_message="Email is not configured in this environment",
            document_id=None,
        )

    from_address = os.environ.get("SMTP_FROM_ADDRESS", "").strip()
    host = os.environ.get("SMTP_HOST", "").strip()
    port = _smtp_port()
    use_tls = _env_bool("SMTP_USE_TLS", default=True)
    username = (os.environ.get("SMTP_USERNAME") or "").strip() or None
    password = os.environ.get("SMTP_PASSWORD") or ""

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_address
        msg["To"] = recipient
        msg.set_content(
            f"Order {quote.quote_number} is ready for in-house review.\n\n"
            f"Open the editable Order Form:\n{approval_url}\n"
        )
        with smtplib.SMTP(host, port) as server:
            if use_tls:
                server.starttls()
            if username:
                server.login(username, password)
            server.send_message(msg)
        return EmailLog(
            quote=quote, revision=quote.revision, recipients=recipients,
            subject=subject, sent_by_user_id=sent_by_user.id,
            status="sent", document_id=None,
        )
    except (smtplib.SMTPException, OSError) as exc:
        logger.exception("Failed to send order approval email for quote %s", quote.quote_number)
        return EmailLog(
            quote=quote, revision=quote.revision, recipients=recipients,
            subject=subject, sent_by_user_id=sent_by_user.id,
            status="failed", error_message=str(exc), document_id=None,
        )

def email_log_to_json(email_log: EmailLog) -> dict[str, Any]:
    """Serialize an EmailLog for API responses."""
    return {
        "id": email_log.id,
        "quote_id": email_log.quote_id,
        "revision": email_log.revision,
        "recipients": email_log.recipients,
        "subject": email_log.subject,
        "sent_at": email_log.sent_at.isoformat() if email_log.sent_at else None,
        "sent_by": email_log.sent_by.display_name if email_log.sent_by else None,
        "status": email_log.status,
        "error_message": email_log.error_message,
        "document_id": email_log.document_id,
    }
