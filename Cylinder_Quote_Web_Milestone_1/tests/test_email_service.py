from __future__ import annotations

import smtplib
from decimal import Decimal
from pathlib import Path

import pytest

from app import create_app
from app.db import get_session, init_db
from app.email_service import is_email_configured
from app.models_db import EmailLog, Quote
from app.pdf_service import quote_pdf_absolute_path

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
    """Point the app at a temporary SQLite database and clear email env vars."""
    db_path = tmp_path / "test_email_service.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("ACCOUNTS_DATABASE_PATH", str(tmp_path / "test_email_service_accounts.db"))
    monkeypatch.setenv("QUOTE_DOCUMENTS_DIR", str(tmp_path / "quote_documents"))

    for var in (
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_USE_TLS",
        "SMTP_FROM_ADDRESS",
    ):
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


def _pdf_render_monkeypatch(monkeypatch, return_bytes: bytes | None = None):
    """Avoid requiring Playwright/Chromium in email tests."""
    if return_bytes is None:
        return_bytes = b"%PDF-1.4 test pdf"
    monkeypatch.setattr(
        "app.pdf_service._render_pdf_with_playwright", lambda _html: return_bytes
    )


def test_is_email_configured_false_when_missing(temp_db):
    assert is_email_configured() is False


def test_is_email_configured_true_when_host_and_from_set(temp_db, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM_ADDRESS", "from@example.com")
    assert is_email_configured() is True


def test_is_email_configured_false_with_only_host(temp_db, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    assert is_email_configured() is False


def test_email_unconfigured_returns_clean_error_and_log(temp_db, monkeypatch):
    """When SMTP is not configured, the route returns a structured 503, creates
    a not_configured EmailLog, and does not mark the quote as emailed."""
    app = temp_db
    quote_id = _make_quote(app, sample_payload())
    _pdf_render_monkeypatch(monkeypatch)

    client = app.test_client()
    resp = client.post(
        f"/api/quotes/{quote_id}/email",
        json={"recipients": ["someone@example.com"]},
        headers=_headers("bob"),
    )

    assert resp.status_code == 503
    body = resp.get_json()
    assert body["ok"] is False
    assert body["email_log"]["status"] == "not_configured"
    assert "not configured" in body["email_log"]["error_message"].lower()
    assert body["email_log"]["recipients"] == ["someone@example.com"]

    with app.app_context():
        with get_session() as session:
            logs = session.query(EmailLog).all()
            assert len(logs) == 1
            assert logs[0].status == "not_configured"
            quote = session.get(Quote, quote_id)
            assert quote.emailed_at is None
            assert quote.emailed_by_user_id is None


def test_email_configured_success_creates_sent_log_and_pdf_regenerated(
    temp_db, monkeypatch
):
    """A valid SMTP config + mocked successful send records a sent EmailLog,
    marks the quote as emailed, and regenerates the PDF."""
    app = temp_db
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM_ADDRESS", "quotes@example.com")
    monkeypatch.setenv("SMTP_USE_TLS", "false")

    quote_id = _make_quote(app, sample_payload())

    render_calls = []

    def fake_render(html):
        render_calls.append(html)
        return b"%PDF-1.4 emailed pdf"

    monkeypatch.setattr("app.pdf_service._render_pdf_with_playwright", fake_render)

    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def send_message(self, msg):
            sent_messages.append(msg)

    monkeypatch.setattr("app.email_service.smtplib.SMTP", FakeSMTP)

    client = app.test_client()
    resp = client.post(
        f"/api/quotes/{quote_id}/email",
        json={"recipients": ["a@example.com", "b@example.com"]},
        headers=_headers("bob"),
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    log = body["email_log"]
    assert log["status"] == "sent"
    assert log["recipients"] == ["a@example.com", "b@example.com"]
    assert "Quote" in log["subject"] and "rev 1" in log["subject"]
    assert log["sent_by"] == "bob"
    assert log["document_id"] is not None

    with app.app_context():
        with get_session() as session:
            quote = session.get(Quote, quote_id)
            assert quote.emailed_by_user_id is not None
            assert quote.emailed_at is not None
            assert quote.emailed_by.display_name == "bob"

    assert len(render_calls) >= 1
    assert len(sent_messages) == 1
    assert sent_messages[0]["To"] == "a@example.com, b@example.com"


def test_email_configured_send_failure_returns_clean_error(temp_db, monkeypatch):
    """If smtplib raises, the route returns a structured 502 with a failed
    EmailLog and does not mark the quote as emailed."""
    app = temp_db
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM_ADDRESS", "quotes@example.com")
    monkeypatch.setenv("SMTP_USE_TLS", "false")

    quote_id = _make_quote(app, sample_payload())
    _pdf_render_monkeypatch(monkeypatch)

    class FailingSMTP:
        def __init__(self, host, port):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def send_message(self, msg):
            raise smtplib.SMTPException("relay denied")

    monkeypatch.setattr("app.email_service.smtplib.SMTP", FailingSMTP)

    client = app.test_client()
    resp = client.post(
        f"/api/quotes/{quote_id}/email",
        json={"recipients": ["someone@example.com"]},
        headers=_headers("bob"),
    )

    assert resp.status_code == 502
    body = resp.get_json()
    assert body["ok"] is False
    assert body["email_log"]["status"] == "failed"
    assert "relay denied" in body["email_log"]["error_message"]

    with app.app_context():
        with get_session() as session:
            quote = session.get(Quote, quote_id)
            assert quote.emailed_at is None
            assert quote.emailed_by_user_id is None


def test_email_invalid_recipients_returns_400_and_no_log(temp_db, monkeypatch):
    """Obvious invalid recipient formats are rejected before any PDF or SMTP work."""
    app = temp_db
    quote_id = _make_quote(app, sample_payload())
    _pdf_render_monkeypatch(monkeypatch)

    client = app.test_client()
    resp = client.post(
        f"/api/quotes/{quote_id}/email",
        json={"recipients": ["not-an-email"]},
        headers=_headers("bob"),
    )

    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False
    assert "not-an-email" in resp.get_json()["error"]

    with app.app_context():
        with get_session() as session:
            assert session.query(EmailLog).count() == 0


def test_email_missing_recipients_returns_400(temp_db, monkeypatch):
    app = temp_db
    quote_id = _make_quote(app, sample_payload())
    _pdf_render_monkeypatch(monkeypatch)

    client = app.test_client()
    resp = client.post(
        f"/api/quotes/{quote_id}/email", json={"recipients": []}, headers=_headers("bob")
    )

    assert resp.status_code == 400


def test_email_applies_presentation_edits_before_send(temp_db, monkeypatch):
    """The email endpoint can carry pending presentation edits, which are
    applied (bumping the revision) before the PDF is regenerated and sent."""
    app = temp_db
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM_ADDRESS", "quotes@example.com")
    monkeypatch.setenv("SMTP_USE_TLS", "false")

    quote_id = _make_quote(app, sample_payload())
    _pdf_render_monkeypatch(monkeypatch)

    class FakeSMTP:
        def __init__(self, host, port):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def send_message(self, msg):
            pass

    monkeypatch.setattr("app.email_service.smtplib.SMTP", FakeSMTP)

    client = app.test_client()
    resp = client.post(
        f"/api/quotes/{quote_id}/email",
        json={
            "recipients": ["customer@example.com"],
            "subject": "Custom subject",
            "customer_name": "Updated Customer",
            "comments": "Please review",
            "manual_line_items": [
                {
                    "description": "Email line",
                    "quantity": 2,
                    "unit_price": "5.00",
                }
            ],
        },
        headers=_headers("bob"),
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["email_log"]["revision"] == 2
    assert body["email_log"]["subject"] == "Custom subject"

    with app.app_context():
        with get_session() as session:
            quote = session.get(Quote, quote_id)
            assert quote.revision == 2
            assert quote.customer_name == "Updated Customer"
            assert quote.comments == "Please review"
            assert len(quote.line_items) == 1
            assert Decimal(quote.line_items[0].extended_price) == Decimal("10.00")


def test_email_pdf_engine_unavailable_returns_clean_error_no_sent_log(
    temp_db, monkeypatch
):
    """If PDF generation fails, the email route returns the PDF error and does
    not create a 'sent' EmailLog."""
    app = temp_db
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM_ADDRESS", "quotes@example.com")
    monkeypatch.setenv("SMTP_USE_TLS", "false")

    quote_id = _make_quote(app, sample_payload())
    from app.pdf_service import PdfEngineUnavailableError

    monkeypatch.setattr(
        "app.pdf_service._render_pdf_with_playwright",
        lambda _html: (_ for _ in ()).throw(
            PdfEngineUnavailableError("Chromium is not installed")
        ),
    )

    client = app.test_client()
    resp = client.post(
        f"/api/quotes/{quote_id}/email",
        json={"recipients": ["someone@example.com"]},
        headers=_headers("bob"),
    )

    assert resp.status_code == 503
    assert resp.get_json()["ok"] is False

    with app.app_context():
        with get_session() as session:
            assert session.query(EmailLog).count() == 0


def test_unconfigured_email_does_not_break_other_routes(temp_db, monkeypatch):
    """With no SMTP configuration, quote creation and calculation still work."""
    app = temp_db
    _pdf_render_monkeypatch(monkeypatch)
    client = app.test_client()

    health = client.get("/api/health")
    assert health.status_code == 200

    calc = client.post("/api/calculate", json=sample_payload())
    assert calc.status_code == 200
    assert Decimal(calc.get_json()["result"]["quote_net_each"]) > 0

    quote_id = _make_quote(app, sample_payload())
    get_resp = client.get(f"/api/quotes/{quote_id}")
    assert get_resp.status_code == 200
