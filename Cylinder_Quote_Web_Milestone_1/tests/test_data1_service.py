from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from app import create_app
from app.data1_service import (
    approval_submission_to_json,
    build_approval_payload,
    is_data1_configured,
    submit_approval,
)
from app.db import get_session, init_db
from app.models_db import ApprovalSubmission, Quote

ROOT = Path(__file__).resolve().parents[1]


def sample_payload():
    return {
        "series": "H",
        "bore": "2",
        "rod_diameter": "1",
        "mount": "MX0",
        "stroke": "12",
        "cushion": "NC",
        "port_code": "N",
        "seal_code": "",
        "rod_style": 1,
        "discount": "0.10",
        "dre": False,
    }


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the app at a temporary SQLite database and create tables."""
    db_path = tmp_path / "test_data1_service.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("ACCOUNTS_DATABASE_PATH", str(tmp_path / "test_data1_service_accounts.db"))

    for var in ("DATA1_BASE_URL", "DATA1_APPROVAL_ENDPOINT"):
        monkeypatch.delenv(var, raising=False)

    import app.db as db_mod

    db_mod._engine = None
    db_mod._accounts_engine = None
    db_mod._Session = None
    init_db()

    app = create_app()
    app.testing = True
    yield app

    db_mod._engine = None
    db_mod._accounts_engine = None
    db_mod._Session = None


def _headers(user: str = "test-user"):
    return {"X-User-Name": user}


def _make_quote(app, payload, user: str = "alice"):
    """Create a quote via the API and return its id."""
    client = app.test_client()
    resp = client.post("/api/quotes", json=payload, headers=_headers(user))
    assert resp.status_code == 200
    return resp.get_json()["quote"]["id"]


def test_is_data1_configured_false_when_unset(temp_db):
    assert is_data1_configured() is False


def test_is_data1_configured_true_when_base_url_set(temp_db, monkeypatch):
    monkeypatch.setenv("DATA1_BASE_URL", "http://data1.example.com")
    assert is_data1_configured() is True


def test_approve_unconfigured_returns_503_and_does_not_mark_approved(temp_db):
    """When Data1 is not configured, the route returns a structured 503, stores
    a failed ApprovalSubmission, and leaves the quote unapproved."""
    app = temp_db
    quote_id = _make_quote(app, sample_payload())

    client = app.test_client()
    resp = client.post(f"/api/quotes/{quote_id}/approve", headers=_headers("bob"))

    assert resp.status_code == 503
    body = resp.get_json()
    assert body["ok"] is False
    assert "not configured" in body["error"].lower()
    approval = body["approval"]
    assert approval["success"] is False
    assert approval["idempotency_key"] == f"quote-{quote_id}-rev1"

    with app.app_context():
        with get_session() as session:
            submissions = session.query(ApprovalSubmission).all()
            assert len(submissions) == 1
            assert submissions[0].success is False
            assert submissions[0].request_sent_at is None
            quote = session.get(Quote, quote_id)
            assert quote.approved_at is None
            assert quote.approved_by_user_id is None


def test_approve_configured_success_marks_approved_and_is_idempotent(
    temp_db, monkeypatch
):
    """A valid Data1 config + mocked 200 response marks the quote approved,
    stores a successful ApprovalSubmission, and does not resend on repeats."""
    app = temp_db
    monkeypatch.setenv("DATA1_BASE_URL", "http://data1.example.com")

    quote_id = _make_quote(app, sample_payload())

    post_calls = []

    def fake_post(url, json, timeout):
        post_calls.append({"url": url, "json": json, "timeout": timeout})
        response = MagicMock()
        response.status_code = 200
        response.text = "ack"
        return response

    monkeypatch.setattr("app.data1_service.requests.post", fake_post)

    client = app.test_client()
    resp = client.post(f"/api/quotes/{quote_id}/approve", headers=_headers("bob"))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    approval = body["approval"]
    assert approval["success"] is True
    assert approval["response_status_code"] == 200
    assert approval["idempotency_key"] == f"quote-{quote_id}-rev1"
    assert body["quote"]["approved_by"] == "bob"
    assert body["quote"]["approved_at"] is not None

    assert len(post_calls) == 1
    assert post_calls[0]["url"] == "http://data1.example.com/api/approved-quote"

    with app.app_context():
        with get_session() as session:
            quote = session.get(Quote, quote_id)
            assert quote.approved_by_user_id is not None
            assert quote.approved_at is not None
            assert quote.approved_by.display_name == "bob"
            assert quote.status == "approved"

    # Second approval for the same revision must reuse the existing success.
    resp2 = client.post(f"/api/quotes/{quote_id}/approve", headers=_headers("bob"))
    assert resp2.status_code == 200
    body2 = resp2.get_json()
    assert body2["ok"] is True
    assert body2["approval"]["success"] is True
    assert body2["approval"]["id"] == approval["id"]
    assert len(post_calls) == 1


def test_approve_configured_connection_error_allows_retry(
    temp_db, monkeypatch
):
    """A failed Data1 request returns 502, records the error, and allows a
    later retry that updates the same ApprovalSubmission row."""
    app = temp_db
    monkeypatch.setenv("DATA1_BASE_URL", "http://data1.example.com")

    quote_id = _make_quote(app, sample_payload())
    payload_override = {
        **sample_payload(),
        "manual_line_items": [
            {
                "reference_part_number": "HIDDEN-REF",
                "description": "Internal special part",
                "quantity": 1,
                "unit_price": "99.00",
                "internal_note": "secret vendor note",
                "show_on_customer_quote": False,
            }
        ],
    }
    client = app.test_client()
    patch_resp = client.patch(
        f"/api/quotes/{quote_id}", json=payload_override, headers=_headers("alice")
    )
    assert patch_resp.status_code == 200
    quote_id = patch_resp.get_json()["quote"]["id"]

    call_count = {"n": 0}

    def failing_post(url, json, timeout):
        call_count["n"] += 1
        raise requests.ConnectionError("Data1 unreachable")

    monkeypatch.setattr("app.data1_service.requests.post", failing_post)

    resp = client.post(f"/api/quotes/{quote_id}/approve", headers=_headers("bob"))

    assert resp.status_code == 502
    body = resp.get_json()
    assert body["ok"] is False
    approval = body["approval"]
    assert approval["success"] is False
    assert "unreachable" in approval["error_message"]
    assert approval["idempotency_key"] == f"quote-{quote_id}-rev2"

    with app.app_context():
        with get_session() as session:
            quote = session.get(Quote, quote_id)
            assert quote.approved_at is None
            assert quote.approved_by_user_id is None
            first_id = approval["id"]

    # Retry with a successful mock.
    def success_post(url, json, timeout):
        call_count["n"] += 1
        response = MagicMock()
        response.status_code = 201
        response.text = "created"
        return response

    monkeypatch.setattr("app.data1_service.requests.post", success_post)

    resp2 = client.post(f"/api/quotes/{quote_id}/approve", headers=_headers("bob"))

    assert resp2.status_code == 200
    body2 = resp2.get_json()
    assert body2["ok"] is True
    assert body2["approval"]["success"] is True
    assert body2["approval"]["id"] == first_id
    assert body2["approval"]["response_status_code"] == 201
    assert call_count["n"] == 2


def test_build_approval_payload_includes_internal_manual_item_fields(temp_db):
    """Data1 payloads include internal-only manual item fields regardless of
    show_on_customer_quote, unlike customer-facing outputs."""
    app = temp_db
    payload = sample_payload()
    payload["manual_line_items"] = [
        {
            "reference_part_number": "HIDDEN-REF",
            "description": "Internal special part",
            "quantity": 2,
            "unit_price": "50.00",
            "internal_note": "secret vendor note",
            "show_on_customer_quote": False,
        }
    ]

    with app.app_context():
        with get_session() as session:
            from app.current_user import get_or_create_current_user
            from app.quote_service import create_quote_snapshot
            from cylinder_quote_engine import QuotePricingEngine

            current_user = get_or_create_current_user(display_name="alice")
            engine = QuotePricingEngine(ROOT / "data")
            quote = create_quote_snapshot(session, payload, current_user, engine=engine)
            session.commit()

            built = build_approval_payload(quote, current_user)
            assert built["quote_number"] == quote.quote_number
            assert built["revision"] == quote.revision
            items = built["manual_line_items"]
            assert len(items) == 1
            assert items[0]["reference_part_number"] == "HIDDEN-REF"
            assert items[0]["internal_note"] == "secret vendor note"
            assert items[0]["show_on_customer_quote"] is False
            assert Decimal(items[0]["extended_price"]) == Decimal("100.00")


def test_approval_submission_to_json_shape(temp_db):
    """ApprovalSubmission serialization exposes the fields the UI expects."""
    app = temp_db
    quote_id = _make_quote(app, sample_payload())

    client = app.test_client()
    resp = client.post(f"/api/quotes/{quote_id}/approve", headers=_headers("bob"))
    assert resp.status_code == 503
    approval_json = resp.get_json()["approval"]
    assert approval_json["idempotency_key"]
    assert "success" in approval_json
    assert "error_message" in approval_json
    assert "request_payload" in approval_json
