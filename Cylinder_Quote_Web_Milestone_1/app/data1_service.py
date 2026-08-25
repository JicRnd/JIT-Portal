from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models_db import ApprovalSubmission, Quote, User, utc_now
from .service import decimal_to_json


DEFAULT_APPROVAL_ENDPOINT = "/api/approved-quote"
REQUEST_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BODY_LENGTH = 4000


def _env(key: str, default: str | None = None) -> str | None:
    value = os.environ.get(key, default)
    if value is None:
        return None
    value = value.strip()
    return value if value else default


def is_data1_configured() -> bool:
    """Return True only when DATA1_BASE_URL is explicitly configured."""
    base_url = _env("DATA1_BASE_URL")
    return bool(base_url)


def _approval_endpoint() -> str:
    """Resolve the approval endpoint, falling back to the AGENTS.md default."""
    return _env("DATA1_APPROVAL_ENDPOINT") or DEFAULT_APPROVAL_ENDPOINT


def _make_idempotency_key(quote: Quote) -> str:
    return f"quote-{quote.id}-rev{quote.revision}"


def _approval_url() -> str:
    base = _env("DATA1_BASE_URL", "").rstrip("/")
    endpoint = _approval_endpoint()
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"
    return f"{base}{endpoint}"


def build_approval_payload(quote: Quote, current_user: User | None = None) -> dict[str, Any]:
    """Build the JSON payload sent to Data1 for an approved quote.

    Includes all manual line items, including internal fields that are hidden
    from customer-facing outputs, because Data1 is an internal downstream
    system.
    """
    approved_by_name = None
    approved_at_iso = None
    if quote.approved_by is not None:
        approved_by_name = quote.approved_by.display_name
        if quote.approved_at is not None:
            approved_at_iso = quote.approved_at.isoformat()
    elif current_user is not None:
        approved_by_name = current_user.display_name
        approved_at_iso = utc_now().isoformat()

    manual_items = []
    for item in quote.line_items:
        manual_items.append(
            {
                "reference_part_number": item.reference_part_number,
                "description": item.description,
                "quantity": decimal_to_json(item.quantity),
                "unit_price": decimal_to_json(item.unit_price),
                "extended_price": decimal_to_json(item.extended_price),
                "internal_note": item.internal_note,
                "show_on_customer_quote": item.show_on_customer_quote,
                "sort_order": item.sort_order,
            }
        )

    return {
        "quote_number": quote.quote_number,
        "revision": quote.revision,
        "model_code": quote.model_code,
        "cylinder_inputs_snapshot": decimal_to_json(quote.cylinder_inputs_snapshot),
        "price_breakdown_snapshot": decimal_to_json(quote.price_breakdown_snapshot),
        "customer_name": quote.customer_name,
        "customer_address": quote.customer_address,
        "customer_contact": quote.customer_contact,
        "customer_reference": quote.customer_reference,
        "comments": quote.comments,
        "manual_line_items": manual_items,
        "approved_by": approved_by_name,
        "approved_at": approved_at_iso,
    }


def _truncate_response_body(text: str | None) -> str | None:
    if text is None:
        return None
    if len(text) <= MAX_RESPONSE_BODY_LENGTH:
        return text
    return text[:MAX_RESPONSE_BODY_LENGTH]


def submit_approval(
    session: Session,
    quote: Quote,
    current_user: User,
) -> ApprovalSubmission:
    """Submit an approved quote to Data1, recording the outcome.

    Idempotency: for a given quote + revision, only one successful submission
    is performed. Repeat calls return the existing successful submission.
    Failed submissions can be retried; the same ApprovalSubmission row is
    updated rather than creating duplicates.
    """
    idempotency_key = _make_idempotency_key(quote)

    existing = session.execute(
        select(ApprovalSubmission).where(
            ApprovalSubmission.idempotency_key == idempotency_key
        )
    ).scalar_one_or_none()

    if existing is not None and existing.success:
        # Already successfully submitted for this revision; do not resend.
        return existing

    payload = build_approval_payload(quote, current_user)

    if existing is None:
        submission = ApprovalSubmission(
            quote_id=quote.id,
            revision=quote.revision,
            idempotency_key=idempotency_key,
            request_payload=payload,
            created_by_user_id=current_user.id,
        )
        session.add(submission)
    else:
        submission = existing
        submission.request_payload = payload

    if not is_data1_configured():
        submission.success = False
        submission.error_message = "Data1 is not configured; approval was not transmitted."
        submission.request_sent_at = None
        return submission

    submission.request_sent_at = utc_now()

    try:
        response = requests.post(
            _approval_url(),
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        submission.response_status_code = response.status_code
        submission.response_body = _truncate_response_body(response.text)
    except requests.RequestException as exc:
        submission.success = False
        submission.response_status_code = None
        submission.error_message = f"Data1 request failed: {exc}"
        return submission

    if 200 <= response.status_code < 300:
        submission.success = True
        submission.error_message = None
    else:
        submission.success = False
        submission.error_message = (
            f"Data1 returned HTTP {response.status_code}; approval was not acknowledged."
        )

    return submission


def approval_submission_to_json(submission: ApprovalSubmission) -> dict[str, Any]:
    """Serialize an ApprovalSubmission for API responses."""
    return {
        "id": submission.id,
        "quote_id": submission.quote_id,
        "revision": submission.revision,
        "idempotency_key": submission.idempotency_key,
        "request_payload": submission.request_payload,
        "request_sent_at": submission.request_sent_at.isoformat() if submission.request_sent_at else None,
        "response_status_code": submission.response_status_code,
        "response_body": submission.response_body,
        "success": submission.success,
        "error_message": submission.error_message,
        "created_by": submission.created_by.display_name if submission.created_by else None,
        "created_at": submission.created_at.isoformat() if submission.created_at else None,
    }
