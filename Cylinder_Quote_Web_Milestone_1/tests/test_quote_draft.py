from __future__ import annotations

from decimal import Decimal

import pytest

from app import create_app


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
def client():
    app = create_app()
    app.testing = True
    return app.test_client()


def test_quote_draft_matches_calculate(client):
    """Draft pricing is identical to the authoritative /api/calculate output."""
    base = sample_payload()
    calc_resp = client.post("/api/calculate", json=base)
    assert calc_resp.status_code == 200
    expected_breakdown = calc_resp.get_json()["result"]

    resp = client.post("/api/quote/draft", json=base)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    draft = data["draft"]

    assert draft["model_code"] == expected_breakdown["model_code"]
    assert draft["price_breakdown"] == expected_breakdown
    assert draft["manual_items"] == []
    assert "quote_number" not in draft
    assert draft["presentation"]["customer_name"] == ""
    assert draft["pricing_engine_version"] == "Pricing Engine v1.2"
    assert "timestamp" in draft
    assert draft["cylinder_inputs"]["series"] == "H"


def test_quote_draft_computes_manual_item_extended_price(client):
    """Server computes extended_price authoritatively from quantity * unit_price."""
    base = sample_payload()
    base["manual_items"] = [
        {"part_number": "SP-001", "description": "Bracket", "quantity": 3, "unit_price": "12.50"},
        {"description": "No part number line", "quantity": 1, "unit_price": "10.00"},
    ]

    resp = client.post("/api/quote/draft", json=base)
    assert resp.status_code == 200
    draft = resp.get_json()["draft"]
    assert len(draft["manual_items"]) == 2
    assert Decimal(draft["manual_items"][0]["extended_price"]) == Decimal("37.50")
    assert draft["manual_items"][0]["part_number"] == "SP-001"
    assert draft["manual_items"][1]["part_number"] is None


def test_quote_draft_rejects_invalid_manual_items(client):
    """Bad manual item rows return a clear 400 without crashing the endpoint."""
    base = sample_payload()

    # Missing description.
    payload = dict(base)
    payload["manual_items"] = [{"quantity": 1, "unit_price": "5.00"}]
    resp = client.post("/api/quote/draft", json=payload)
    assert resp.status_code == 400
    assert "description" in resp.get_json()["error"].lower()

    # Zero quantity.
    payload = dict(base)
    payload["manual_items"] = [{"description": "Bad qty", "quantity": 0, "unit_price": "5.00"}]
    resp = client.post("/api/quote/draft", json=payload)
    assert resp.status_code == 400
    assert "quantity" in resp.get_json()["error"].lower()

    # Negative quantity.
    payload = dict(base)
    payload["manual_items"] = [{"description": "Bad qty", "quantity": -1, "unit_price": "5.00"}]
    resp = client.post("/api/quote/draft", json=payload)
    assert resp.status_code == 400
    assert "quantity" in resp.get_json()["error"].lower()

    # Negative unit price.
    payload = dict(base)
    payload["manual_items"] = [{"description": "Bad price", "quantity": 1, "unit_price": "-5.00"}]
    resp = client.post("/api/quote/draft", json=payload)
    assert resp.status_code == 400
    assert "unit_price" in resp.get_json()["error"].lower()


def test_quote_draft_sanitizes_presentation_fields(client):
    """Presentation fields are trimmed and truncated but preserved as plain text."""
    base = sample_payload()
    base["customer_name"] = "  Acme Cylinders  "
    base["customer_contact"] = "John Doe"
    base["customer_reference"] = "PO-123"
    base["comments"] = "Rush order"

    resp = client.post("/api/quote/draft", json=base)
    assert resp.status_code == 200
    presentation = resp.get_json()["draft"]["presentation"]
    assert presentation["customer_name"] == "Acme Cylinders"
    assert presentation["customer_contact"] == "John Doe"
    assert presentation["customer_reference"] == "PO-123"
    assert presentation["comments"] == "Rush order"


def test_quote_draft_keeps_special_parts_and_manual_items_independent(client):
    """Catalog-backed special_parts and free-text manual_items are separate fields."""
    base = sample_payload()
    base["special_parts"] = {"AC044": "2"}
    base["manual_items"] = [
        {"part_number": "CUSTOM-1", "description": "Custom bracket", "quantity": 2, "unit_price": "25.00"}
    ]

    resp = client.post("/api/quote/draft", json=base)
    assert resp.status_code == 200
    draft = resp.get_json()["draft"]

    assert draft["cylinder_inputs"]["special_parts"] == {"AC044": "2"}
    assert len(draft["manual_items"]) == 1
    assert draft["manual_items"][0]["part_number"] == "CUSTOM-1"
    assert Decimal(draft["manual_items"][0]["extended_price"]) == Decimal("50.00")
