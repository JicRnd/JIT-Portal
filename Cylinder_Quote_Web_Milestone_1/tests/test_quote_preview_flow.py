from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app import create_app
from app.db import init_db

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
    db_path = tmp_path / "test_quote_preview_flow.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("ACCOUNTS_DATABASE_PATH", str(tmp_path / "test_quote_preview_flow_accounts.db"))

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


def test_quote_preview_flow_create_get_patch_preserves_breakdown(temp_db):
    """End-to-end API flow used by the Quote Preview screen.

    A saved quote returns the pricing snapshot; PATCH updates presentation
    fields and manual line items, bumps revision, and leaves the original
    price breakdown untouched.
    """
    client = temp_db.test_client()
    base = sample_payload()
    base["customer_name"] = "Acme Cylinders"
    base["comments"] = "Initial comment"
    base["manual_line_items"] = [
        {
            "description": "Mounting bracket",
            "quantity": 2,
            "unit_price": "12.50",
            "show_on_customer_quote": True,
        }
    ]

    calc_resp = client.post("/api/calculate", json=sample_payload())
    assert calc_resp.status_code == 200
    expected_breakdown = calc_resp.get_json()["result"]

    create_resp = client.post("/api/quotes", json=base, headers=_headers("alice"))
    assert create_resp.status_code == 200
    created = create_resp.get_json()["quote"]
    quote_id = created["id"]

    assert created["quote_number"].startswith("A")
    assert len(created["quote_number"]) == 11
    assert created["revision"] == 1
    assert created["status"] == "draft"
    assert created["pricing_version"] == "v1.2"
    assert created["created_by"] == "alice"
    assert created["customer_name"] == "Acme Cylinders"
    assert created["comments"] == "Initial comment"
    assert created["price_breakdown_snapshot"] == expected_breakdown
    assert len(created["manual_line_items"]) == 1
    assert Decimal(created["manual_line_items"][0]["extended_price"]) == Decimal("25.00")

    get_resp = client.get(f"/api/quotes/{quote_id}")
    assert get_resp.status_code == 200
    fetched = get_resp.get_json()["quote"]
    assert fetched["id"] == quote_id
    assert fetched["price_breakdown_snapshot"] == expected_breakdown

    patch_payload = {
        "customer_name": "Beta Cylinders",
        "customer_address": "123 Main St",
        "customer_contact": "John Doe",
        "reference_notes": "PO-123",
        "comments": "Updated comment",
        "manual_line_items": [
            {
                "reference_part_number": "SP-001",
                "description": "Edited bracket",
                "quantity": 3,
                "unit_price": "10.00",
                "internal_note": "vendor note",
                "show_on_customer_quote": False,
            }
        ],
    }
    patch_resp = client.patch(
        f"/api/quotes/{quote_id}", json=patch_payload, headers=_headers("bob")
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.get_json()["quote"]

    assert updated["revision"] == 2
    assert updated["edited_by"] == "bob"
    assert updated["created_by"] == "alice"
    assert updated["customer_name"] == "Beta Cylinders"
    assert updated["customer_address"] == "123 Main St"
    assert updated["customer_contact"] == "John Doe"
    assert updated["reference_notes"] == "PO-123"
    assert updated["comments"] == "Updated comment"
    assert updated["price_breakdown_snapshot"] == expected_breakdown

    line_items = updated["manual_line_items"]
    assert len(line_items) == 1
    assert line_items[0]["reference_part_number"] == "SP-001"
    assert Decimal(line_items[0]["quantity"]) == Decimal("3")
    assert Decimal(line_items[0]["unit_price"]) == Decimal("10.00")
    assert Decimal(line_items[0]["extended_price"]) == Decimal("30.00")
    assert line_items[0]["show_on_customer_quote"] is False


def test_index_page_renders_quote_preview(temp_db):
    """The quote-entry template still renders without Jinja errors and contains
    the Quote Form controls."""
    client = temp_db.test_client()
    resp = client.get("/quote-entry")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "Quote Form" in text
    assert "Order Now" in text
