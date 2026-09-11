from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app import create_app
from app.db import get_session, init_db
from app.models_db import Quote


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
    db_path = tmp_path / "test_quote_history.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("ACCOUNTS_DATABASE_PATH", str(tmp_path / "test_quote_history_accounts.db"))

    import app.db as db_mod

    db_mod._engine = None
    db_mod._Session = None
    init_db()

    app = create_app()
    app.testing = True
    yield app

    db_mod._engine = None
    db_mod._Session = None


def _headers(user: str = "test-user"):
    return {"X-User-Name": user}


def _create_quote(client, user, customer_name, **overrides):
    payload = sample_payload()
    payload["customer_name"] = customer_name
    payload.update(overrides)
    resp = client.post("/api/quotes", json=payload, headers=_headers(user))
    assert resp.status_code == 200
    return resp.get_json()["quote"]


def _set_quote_meta(quote_id, *, status=None, created_at=None):
    with get_session() as session:
        quote = session.get(Quote, quote_id)
        if status is not None:
            quote.status = status
        if created_at is not None:
            quote.created_at = created_at
        session.commit()


def _seed_quotes(client):
    """Create a small set of quotes with varied metadata for search tests."""
    today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)

    q1 = _create_quote(client, "alice", "Acme Corp", rod_style=1)
    _set_quote_meta(q1["id"], status="draft", created_at=today - timedelta(days=5))

    q2 = _create_quote(client, "bob", "Beta LLC", rod_style=2)
    _set_quote_meta(q2["id"], status="sent", created_at=today - timedelta(days=3))

    q3 = _create_quote(client, "alice", "Gamma Inc", rod_style=2)
    _set_quote_meta(q3["id"], status="approved", created_at=today - timedelta(days=1))

    q4 = _create_quote(client, "bob", "Acme Subsidiary", rod_style=1)
    _set_quote_meta(q4["id"], status="draft", created_at=today)

    q5 = _create_quote(client, "alice", "Delta Co", rod_style=1)
    _set_quote_meta(q5["id"], status="draft", created_at=today)

    return [q1, q2, q3, q4, q5]


def test_list_quotes_no_filters_is_paginated(temp_db):
    client = temp_db.test_client()
    _seed_quotes(client)

    resp = client.get("/api/quotes")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 25
    assert len(data["results"]) == 5

    # List rows are lightweight.
    row = data["results"][0]
    assert "id" in row
    assert "quote_number" in row
    assert "status" in row
    assert "model_code" in row
    assert "customer_name" in row
    assert "created_by" in row
    assert "created_at" in row
    assert "revision" in row
    assert "quote_net_each" in row
    assert "cylinder_inputs_snapshot" not in row
    assert "price_breakdown_snapshot" not in row
    assert "manual_line_items" not in row


def test_filter_by_quote_number_partial(temp_db):
    client = temp_db.test_client()
    quotes = _seed_quotes(client)

    # Each quote number is DEV-YYYY-NNNNN; search for the unique sequence.
    target = quotes[0]["quote_number"]
    unique_fragment = target.split("-")[-1]
    resp = client.get(f"/api/quotes?quote_number={unique_fragment}")
    results = resp.get_json()["results"]
    assert len(results) == 1
    assert results[0]["quote_number"] == target


def test_filter_by_customer_name_case_insensitive(temp_db):
    client = temp_db.test_client()
    _seed_quotes(client)

    resp = client.get("/api/quotes?customer_name=ACME")
    results = resp.get_json()["results"]
    assert len(results) == 2
    assert {r["customer_name"] for r in results} == {"Acme Corp", "Acme Subsidiary"}

    resp = client.get("/api/quotes?customer_name=subsidiary")
    results = resp.get_json()["results"]
    assert len(results) == 1
    assert results[0]["customer_name"] == "Acme Subsidiary"


def test_filter_by_model_code(temp_db):
    client = temp_db.test_client()
    quotes = _seed_quotes(client)

    style2_code = quotes[1]["model_code"]
    resp = client.get(f"/api/quotes?model_code={style2_code}")
    results = resp.get_json()["results"]
    assert len(results) == 2
    assert all(r["model_code"] == style2_code for r in results)


def test_filter_by_status(temp_db):
    client = temp_db.test_client()
    _seed_quotes(client)

    resp = client.get("/api/quotes?status=sent")
    results = resp.get_json()["results"]
    assert len(results) == 1
    assert results[0]["customer_name"] == "Beta LLC"


def test_filter_by_created_by(temp_db):
    client = temp_db.test_client()
    _seed_quotes(client)

    resp = client.get("/api/quotes?created_by=ALICE")
    results = resp.get_json()["results"]
    assert len(results) == 3
    assert all(r["created_by"] == "alice" for r in results)

    resp = client.get("/api/quotes?created_by=bob")
    results = resp.get_json()["results"]
    assert len(results) == 2
    assert all(r["created_by"] == "bob" for r in results)


def test_filter_by_date_range(temp_db):
    client = temp_db.test_client()
    quotes = _seed_quotes(client)

    today = datetime.utcnow().date().isoformat()
    five_days_ago = (datetime.utcnow() - timedelta(days=5)).date().isoformat()
    four_days_ago = (datetime.utcnow() - timedelta(days=4)).date().isoformat()

    resp = client.get(f"/api/quotes?date_from={today}")
    results = resp.get_json()["results"]
    assert len(results) == 2
    assert {r["customer_name"] for r in results} == {"Acme Subsidiary", "Delta Co"}

    resp = client.get(f"/api/quotes?date_to={four_days_ago}")
    results = resp.get_json()["results"]
    assert len(results) == 1
    assert results[0]["id"] == quotes[0]["id"]

    resp = client.get(f"/api/quotes?date_from={five_days_ago}&date_to={four_days_ago}")
    results = resp.get_json()["results"]
    assert len(results) == 1
    assert results[0]["id"] == quotes[0]["id"]


def test_pagination_page_size_capped_and_invalid_defaults(temp_db):
    client = temp_db.test_client()
    _seed_quotes(client)

    resp = client.get("/api/quotes?page_size=200")
    data = resp.get_json()
    assert data["page_size"] == 100
    assert len(data["results"]) == 5

    resp = client.get("/api/quotes?page=2&page_size=2")
    data = resp.get_json()
    assert data["page"] == 2
    assert data["page_size"] == 2
    assert len(data["results"]) == 2

    resp = client.get("/api/quotes?page=-1&page_size=abc")
    data = resp.get_json()
    assert data["page"] == 1
    assert data["page_size"] == 25
    assert data["total"] == 5


def test_duplicate_quote_creates_new_quote_copy(temp_db):
    client = temp_db.test_client()
    source = _create_quote(
        client,
        "alice",
        "Original Customer",
        comments="Keep me",
        manual_line_items=[
            {
                "reference_part_number": "M-001",
                "description": "Manual item",
                "quantity": 2,
                "unit_price": "9.99",
                "internal_note": "note",
                "show_on_customer_quote": True,
            }
        ],
    )

    # Mark the source as emailed/approved so we can verify those are not copied.
    emailed_at = datetime.utcnow() - timedelta(days=1)
    approved_at = datetime.utcnow() - timedelta(hours=1)
    with get_session() as session:
        quote = session.get(Quote, source["id"])
        quote.emailed_at = emailed_at
        quote.approved_at = approved_at
        session.commit()

    resp = client.post(f"/api/quotes/{source['id']}/duplicate", headers=_headers("bob"))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True

    duplicate = data["quote"]
    assert duplicate["id"] != source["id"]
    assert duplicate["quote_number"] != source["quote_number"]
    assert duplicate["status"] == "new"
    assert duplicate["revision"] == 1
    assert duplicate["created_by"] == "bob"
    assert duplicate["model_code"] == source["model_code"]
    assert duplicate["cylinder_inputs_snapshot"] == source["cylinder_inputs_snapshot"]
    assert duplicate["price_breakdown_snapshot"] == source["price_breakdown_snapshot"]
    assert duplicate["customer_name"] == "Original Customer"
    assert duplicate["comments"] == "Keep me"

    # The duplicate must not carry over emailed/approved timestamps.
    with get_session() as session:
        source_row = session.get(Quote, source["id"])
        duplicate_row = session.get(Quote, duplicate["id"])
        assert source_row.emailed_at is not None
        assert source_row.approved_at is not None
        assert duplicate_row.emailed_at is None
        assert duplicate_row.approved_at is None

    assert len(duplicate["manual_line_items"]) == 1
    item = duplicate["manual_line_items"][0]
    assert item["description"] == "Manual item"
    assert Decimal(item["quantity"]) == Decimal("2")
    assert Decimal(item["unit_price"]) == Decimal("9.99")
    assert Decimal(item["extended_price"]) == Decimal("19.98")
    assert item["reference_part_number"] == "M-001"


def test_duplicate_nonexistent_quote_returns_404(temp_db):
    client = temp_db.test_client()
    resp = client.post("/api/quotes/999999/duplicate", headers=_headers("alice"))
    assert resp.status_code == 404
    assert resp.get_json()["ok"] is False
