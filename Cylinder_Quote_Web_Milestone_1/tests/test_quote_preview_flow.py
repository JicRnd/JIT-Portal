from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app import create_app
from app.db import get_session, init_db
from app.models_db import Order, Quote, User

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
    monkeypatch.setenv("QUOTES_DATABASE_PATH", str(tmp_path / "test_quote_preview_flow_quotes.db"))
    monkeypatch.setenv("ORDERS_DATABASE_PATH", str(tmp_path / "test_quote_preview_flow_orders.db"))

    import app.db as db_mod

    db_mod._engine = None
    db_mod._accounts_engine = None
    db_mod._quotes_engine = None
    db_mod._orders_engine = None
    db_mod._Session = None
    init_db()

    app = create_app()
    app.testing = True
    yield app

    db_mod._engine = None
    db_mod._accounts_engine = None
    db_mod._quotes_engine = None
    db_mod._orders_engine = None
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


def test_order_now_creates_order_and_opens_order_form_by_order_id(temp_db):
    client = temp_db.test_client()
    create_resp = client.post("/api/quotes", json=sample_payload(), headers=_headers("alice"))
    quote_id = create_resp.get_json()["quote"]["id"]

    order_resp = client.post(f"/api/quotes/{quote_id}/order", json={}, headers=_headers("alice"))

    assert order_resp.status_code == 200
    order_body = order_resp.get_json()
    assert order_body["order_id"] > 0
    assert order_body["order_number"].startswith("J")
    assert order_body["approval_url"].endswith(f"/order-form?order_id={order_body['order_id']}")

    form_resp = client.get(
        f"/order-form?order_id={order_body['order_id']}", headers=_headers("alice")
    )
    assert form_resp.status_code == 200
    assert 'data-quote-id="' + str(quote_id) + '"' in form_resp.get_data(as_text=True)


def test_customer_can_cancel_quote_and_order_status_is_updated(temp_db):
    client = temp_db.test_client()
    create_resp = client.post(
        "/api/quotes", json=sample_payload(), headers=_headers("alice")
    )
    quote_id = create_resp.get_json()["quote"]["id"]

    order_resp = client.post(
        f"/api/quotes/{quote_id}/order", json={}, headers=_headers("alice")
    )
    assert order_resp.status_code == 200

    cancel_resp = client.post(
        f"/api/quotes/{quote_id}/cancel", json={}, headers=_headers("alice")
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.get_json()["quote"]["status"] == "canceled"

    with get_session() as session:
        quote = session.get(Quote, quote_id)
        order = session.execute(
            select(Order).where(Order.quote_id == quote_id)
        ).scalar_one()
        assert quote.status == "canceled"
        assert order.status == "canceled"


def test_customer_quote_entry_stays_on_calculator(temp_db):
    client = temp_db.test_client()
    create_resp = client.post(
        "/api/quotes", json=sample_payload(), headers=_headers("alice")
    )
    quote_id = create_resp.get_json()["quote"]["id"]

    with get_session() as session:
        customer = session.execute(
            select(User).where(User.display_name == "alice")
        ).scalar_one()
        customer.role = "customer"
        session.commit()
        customer_id = customer.id
    with client.session_transaction() as session:
        session["user_id"] = customer_id
        session["role"] = "customer"

    response = client.get(
        f"/customer/quote-entry?quote_id={quote_id}", headers=_headers("alice")
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="series"' in text
    assert 'id="pv_customer_name"' not in text
    assert 'JIT Customer Quote Form' not in text


def test_index_page_renders_calculator_and_employee_quote_preview(temp_db):
    """The customer and employee calculators remain separate from quote forms."""
    client = temp_db.test_client()
    resp = client.get("/quote-entry")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "Quote" in text

    preview_resp = client.get("/quote-entry?draft=1")
    assert preview_resp.status_code == 200
    preview_text = preview_resp.get_data(as_text=True)
    assert "Quote Form" in preview_text
    assert "Order Now" in preview_text
    assert "Email Customer" in preview_text
    assert "Attach Quote Form" in preview_text
    assert "Attach Report Image" in preview_text
    assert "Attach Report Images" not in preview_text

    order_resp = client.get("/order-form?quote_id=1")
    assert order_resp.status_code == 200
    order_text = order_resp.get_data(as_text=True)
    assert "Order Form" in order_text
    assert "Email Customer" in order_text
    assert "Attach Quote Form" in order_text
    assert "Attach Report Images" in order_text
    assert 'id="orderBarcode"' in order_text
    assert 'data-field="ordered_by"' in order_text
    assert order_text.index('data-field="ordered_by"') < order_text.index('data-field="quote_number"')
    assert order_text.index('data-field="quote_number"') < order_text.index('data-field="assembled_by"')
    assert order_text.index('data-field="assembled_by"') < order_text.index('data-field="date_passed_test"')


def test_quote_form_page_omits_internal_note_controls(temp_db):
    """The dedicated quote form no longer exposes internal note/show toggles for manual items."""
    client = temp_db.test_client()
    resp = client.get("/quote-entry?draft=1")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "Internal note" not in text
    assert "Show" not in text
