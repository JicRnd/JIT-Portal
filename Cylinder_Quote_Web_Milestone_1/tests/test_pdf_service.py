from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app import create_app
from app.db import get_session, init_db
from app.pdf_service import (
    PdfEngineUnavailableError,
    build_quote_pdf_context,
    quote_pdf_absolute_path,
)


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
    """Point the app at a temporary SQLite database and store PDFs in temp dir."""
    db_path = tmp_path / "test_pdf_service.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("ACCOUNTS_DATABASE_PATH", str(tmp_path / "test_pdf_service_accounts.db"))
    monkeypatch.setenv("QUOTE_DOCUMENTS_DIR", str(tmp_path / "quote_documents"))

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


def _make_quote(app, payload, user="alice"):
    """Create a quote via the API and return its id."""
    client = app.test_client()
    resp = client.post("/api/quotes", json=payload, headers=_headers(user))
    assert resp.status_code == 200
    return resp.get_json()["quote"]["id"]


def test_build_quote_pdf_context_filters_hidden_line_items(temp_db):
    """Only customer-visible manual line items reach the PDF template context."""
    app = temp_db
    payload = sample_payload()
    payload["manual_line_items"] = [
        {
            "reference_part_number": "PUBLIC-1",
            "description": "Visible bracket",
            "quantity": 2,
            "unit_price": "10.00",
            "show_on_customer_quote": True,
        },
        {
            "reference_part_number": "INTERNAL-1",
            "description": "Hidden note",
            "quantity": 1,
            "unit_price": "5.00",
            "show_on_customer_quote": False,
        },
    ]
    quote_id = _make_quote(app, payload)

    with app.app_context():
        with get_session() as session:
            from app.quote_service import get_quote

            quote = get_quote(session, quote_id)
            context = build_quote_pdf_context(quote)

    items = context["customer_line_items"]
    assert len(items) == 1
    assert items[0]["reference_part_number"] == "PUBLIC-1"
    assert items[0]["description"] == "Visible bracket"
    assert Decimal(items[0]["quantity"]) == Decimal("2")
    assert Decimal(items[0]["unit_price"]) == Decimal("10.00")
    assert Decimal(items[0]["extended_price"]) == Decimal("20.00")


def test_post_pdf_creates_document_and_file(temp_db, monkeypatch):
    """POST /api/quotes/<id>/pdf stores a QuoteDocument row and file."""
    app = temp_db
    payload = sample_payload()
    payload["customer_name"] = "Acme Cylinders"
    quote_id = _make_quote(app, payload, user="alice")

    fake_bytes = b"%PDF-1.4 fake pdf content"
    monkeypatch.setattr(
        "app.pdf_service._render_pdf_with_playwright", lambda _html: fake_bytes
    )

    client = app.test_client()
    resp = client.post(f"/api/quotes/{quote_id}/pdf", headers=_headers("bob"))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    document = body["document"]
    assert "id" in document
    assert document["revision"] == 1
    assert document["download_path"] == f"/api/quotes/{quote_id}/documents/{document['id']}"

    # Verify database row.
    with app.app_context():
        with get_session() as session:
            from app.models_db import QuoteDocument

            doc = session.get(QuoteDocument, document["id"])
            assert doc is not None
            assert doc.quote_id == quote_id
            assert doc.revision == 1
            assert doc.created_by.display_name == "bob"
            assert doc.file_path.startswith("instance/quote_documents/")
            assert doc.file_path.endswith("/rev1.pdf")

    # Verify file on disk.
    with app.app_context():
        with get_session() as session:
            from app.quote_service import get_quote

            quote = get_quote(session, quote_id)
            absolute_path = quote_pdf_absolute_path(quote)
    assert absolute_path.exists()
    assert absolute_path.read_bytes() == fake_bytes


def test_get_pdf_download_returns_file(temp_db, monkeypatch):
    """GET /api/quotes/<id>/documents/<doc_id> returns the stored PDF file."""
    app = temp_db
    payload = sample_payload()
    quote_id = _make_quote(app, payload)

    fake_bytes = b"%PDF-1.4 downloadable content"
    monkeypatch.setattr(
        "app.pdf_service._render_pdf_with_playwright", lambda _html: fake_bytes
    )

    client = app.test_client()
    post_resp = client.post(f"/api/quotes/{quote_id}/pdf", headers=_headers("bob"))
    doc_id = post_resp.get_json()["document"]["id"]

    get_resp = client.get(f"/api/quotes/{quote_id}/documents/{doc_id}")
    assert get_resp.status_code == 200
    assert get_resp.content_type == "application/pdf"
    assert get_resp.data == fake_bytes
    assert get_resp.headers.get("Content-Disposition", "").startswith("attachment")


def test_post_pdf_for_missing_quote_returns_404(temp_db):
    """Requesting a PDF for a nonexistent quote returns a clean 404."""
    client = temp_db.test_client()
    resp = client.post("/api/quotes/99999/pdf", headers=_headers("bob"))
    assert resp.status_code == 404
    body = resp.get_json()
    assert body["ok"] is False
    assert "not found" in body["error"].lower()


def test_pdf_engine_unavailable_returns_clean_error_and_no_document(
    temp_db, monkeypatch
):
    """If the PDF engine is unavailable, the route returns a clean JSON error
    and does not create a QuoteDocument row.
    """
    app = temp_db
    payload = sample_payload()
    quote_id = _make_quote(app, payload)

    def raise_unavailable(_html):
        raise PdfEngineUnavailableError("Chromium is not installed")

    monkeypatch.setattr(
        "app.pdf_service._render_pdf_with_playwright", raise_unavailable
    )

    client = app.test_client()
    resp = client.post(f"/api/quotes/{quote_id}/pdf", headers=_headers("bob"))
    assert resp.status_code == 503
    body = resp.get_json()
    assert body["ok"] is False
    assert "not available" in body["error"].lower()
    assert "stack" not in resp.get_data(as_text=True).lower()

    with app.app_context():
        with get_session() as session:
            from app.models_db import QuoteDocument

            docs = session.query(QuoteDocument).where(QuoteDocument.quote_id == quote_id).all()
            assert len(docs) == 0


def test_download_document_wrong_quote_returns_404(temp_db, monkeypatch):
    """A document id belonging to a different quote cannot be accessed under
    another quote id.
    """
    app = temp_db
    quote_id_1 = _make_quote(app, sample_payload())
    quote_id_2 = _make_quote(app, sample_payload())

    fake_bytes = b"%PDF-1.4 another pdf"
    monkeypatch.setattr(
        "app.pdf_service._render_pdf_with_playwright", lambda _html: fake_bytes
    )

    client = app.test_client()
    post_resp = client.post(f"/api/quotes/{quote_id_1}/pdf", headers=_headers("bob"))
    doc_id = post_resp.get_json()["document"]["id"]

    resp = client.get(f"/api/quotes/{quote_id_2}/documents/{doc_id}")
    assert resp.status_code == 404
    assert resp.get_json()["ok"] is False
