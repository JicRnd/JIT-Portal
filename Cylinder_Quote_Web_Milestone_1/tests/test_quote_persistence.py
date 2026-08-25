from __future__ import annotations

from decimal import Decimal

import pytest

from app import create_app
from app.db import get_engine, get_session, init_db


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
    db_path = tmp_path / "test_quote_persistence.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("ACCOUNTS_DATABASE_PATH", str(tmp_path / "test_quote_persistence_accounts.db"))

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


def _client(app):
    return app.test_client()


def _headers(user: str = "test-user"):
    return {"X-User-Name": user}


def _cylinder_payload():
    return sample_payload()


def test_create_quote_persists_snapshot_and_line_items(temp_db):
    client = _client(temp_db)
    payload = _cylinder_payload()
    payload["customer_name"] = "Acme Cylinders"
    payload["comments"] = "Rush order"
    payload["manual_line_items"] = [
        {
            "description": "Special mounting bracket",
            "quantity": 2,
            "unit_price": "15.50",
            "internal_note": "fab shop",
            "show_on_customer_quote": True,
        }
    ]

    calc_resp = client.post("/api/calculate", json=_cylinder_payload())
    assert calc_resp.status_code == 200
    expected_breakdown = calc_resp.get_json()["result"]

    resp = client.post("/api/quotes", json=payload, headers=_headers())
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True

    quote = data["quote"]
    assert quote["quote_number"].startswith("A")
    assert len(quote["quote_number"]) == 11
    assert quote["status"] == "draft"
    assert quote["pricing_version"] == "v1.2"
    assert quote["revision"] == 1
    assert quote["model_code"] == expected_breakdown["model_code"]
    assert quote["created_by"] == "test-user"

    assert quote["customer_name"] == "Acme Cylinders"
    assert quote["comments"] == "Rush order"
    assert quote["price_breakdown_snapshot"] == expected_breakdown

    line_items = quote["manual_line_items"]
    assert len(line_items) == 1
    assert line_items[0]["description"] == "Special mounting bracket"
    assert Decimal(line_items[0]["quantity"]) == Decimal("2")
    assert Decimal(line_items[0]["unit_price"]) == Decimal("15.50")
    assert Decimal(line_items[0]["extended_price"]) == Decimal("31.00")
    assert line_items[0]["show_on_customer_quote"] is True


def test_get_quote_returns_saved_snapshot(temp_db):
    client = _client(temp_db)
    payload = _cylinder_payload()

    create_resp = client.post("/api/quotes", json=payload, headers=_headers())
    quote_id = create_resp.get_json()["quote"]["id"]
    original_breakdown = create_resp.get_json()["quote"]["price_breakdown_snapshot"]

    get_resp = client.get(f"/api/quotes/{quote_id}")
    assert get_resp.status_code == 200
    quote = get_resp.get_json()["quote"]
    assert quote["id"] == quote_id
    assert quote["price_breakdown_snapshot"] == original_breakdown


def test_get_missing_quote_returns_404(temp_db):
    client = _client(temp_db)
    resp = client.get("/api/quotes/9999")
    assert resp.status_code == 404
    assert resp.get_json()["ok"] is False


def test_patch_quote_updates_presentation_fields_and_bumps_revision(temp_db):
    client = _client(temp_db)
    payload = _cylinder_payload()
    payload["manual_line_items"] = [
        {
            "description": "Original line",
            "quantity": 1,
            "unit_price": "10.00",
        }
    ]

    create_resp = client.post("/api/quotes", json=payload, headers=_headers("alice"))
    quote_id = create_resp.get_json()["quote"]["id"]
    original_breakdown = create_resp.get_json()["quote"]["price_breakdown_snapshot"]
    original_inputs = create_resp.get_json()["quote"]["cylinder_inputs_snapshot"]

    patch_payload = {
        "customer_name": "Updated Customer",
        "comments": "Updated comment",
        # Cylinder/pricing inputs must be ignored by this endpoint.
        "bore": "99",
        "discount": "0.99",
        "manual_line_items": [
            {
                "reference_part_number": "SP-001",
                "description": "Edited special part",
                "quantity": 3,
                "unit_price": "12.34",
                "internal_note": "vendor note",
                "show_on_customer_quote": False,
            }
        ],
    }

    patch_resp = client.patch(
        f"/api/quotes/{quote_id}", json=patch_payload, headers=_headers("bob")
    )
    assert patch_resp.status_code == 200
    quote = patch_resp.get_json()["quote"]

    assert quote["customer_name"] == "Updated Customer"
    assert quote["comments"] == "Updated comment"
    assert quote["revision"] == 2
    assert quote["edited_by"] == "bob"
    assert quote["created_by"] == "alice"
    assert quote["price_breakdown_snapshot"] == original_breakdown
    assert quote["cylinder_inputs_snapshot"] == original_inputs

    line_items = quote["manual_line_items"]
    assert len(line_items) == 1
    assert line_items[0]["reference_part_number"] == "SP-001"
    assert line_items[0]["description"] == "Edited special part"
    assert Decimal(line_items[0]["quantity"]) == Decimal("3")
    assert Decimal(line_items[0]["unit_price"]) == Decimal("12.34")
    assert Decimal(line_items[0]["extended_price"]) == Decimal("37.02")
    assert line_items[0]["show_on_customer_quote"] is False


def test_create_quote_rejects_invalid_manual_line_items(temp_db):
    client = _client(temp_db)
    base = _cylinder_payload()

    # Missing description.
    payload = dict(base)
    payload["manual_line_items"] = [{"quantity": 1, "unit_price": "5.00"}]
    resp = client.post("/api/quotes", json=payload, headers=_headers())
    assert resp.status_code == 400
    assert "description" in resp.get_json()["error"].lower()

    # Negative quantity.
    payload = dict(base)
    payload["manual_line_items"] = [
        {"description": "Bad qty", "quantity": -1, "unit_price": "5.00"}
    ]
    resp = client.post("/api/quotes", json=payload, headers=_headers())
    assert resp.status_code == 400
    assert "quantity" in resp.get_json()["error"].lower()

    # Negative unit price.
    payload = dict(base)
    payload["manual_line_items"] = [
        {"description": "Bad price", "quantity": 1, "unit_price": "-5.00"}
    ]
    resp = client.post("/api/quotes", json=payload, headers=_headers())
    assert resp.status_code == 400
    assert "unit_price" in resp.get_json()["error"].lower()


def test_quote_numbers_are_unique_customer_timestamp_format(temp_db):
    client = _client(temp_db)
    payload = _cylinder_payload()
    payload["customer_name"] = "Acme Cylinders"

    resp1 = client.post("/api/quotes", json=payload, headers=_headers())
    resp2 = client.post("/api/quotes", json=payload, headers=_headers())

    n1 = resp1.get_json()["quote"]["quote_number"]
    n2 = resp2.get_json()["quote"]["quote_number"]
    assert n1 != n2
    assert n1.startswith("A")
    assert n2.startswith("A")
    assert len(n1) == 11
    assert len(n2) == 11


def test_saved_quote_breakdown_is_immutable_snapshot(temp_db):
    client = _client(temp_db)
    payload = _cylinder_payload()

    resp = client.post("/api/quotes", json=payload, headers=_headers())
    quote_id = resp.get_json()["quote"]["id"]
    saved_breakdown = resp.get_json()["quote"]["price_breakdown_snapshot"]

    # Simulate a pricing-engine change after the quote was saved. Because the
    # quote stores a snapshot, the saved record must not pick up the change.
    import app.quote_service as qs

    original_calculate = qs.calculate_payload
    qs.calculate_payload = lambda engine, payload: {
        **original_calculate(engine, payload),
        "quote_net_each": "999999.99",
    }

    try:
        get_resp = client.get(f"/api/quotes/{quote_id}")
        assert get_resp.status_code == 200
        fetched_breakdown = get_resp.get_json()["quote"]["price_breakdown_snapshot"]
        assert fetched_breakdown == saved_breakdown
        assert fetched_breakdown["quote_net_each"] != "999999.99"
    finally:
        qs.calculate_payload = original_calculate
