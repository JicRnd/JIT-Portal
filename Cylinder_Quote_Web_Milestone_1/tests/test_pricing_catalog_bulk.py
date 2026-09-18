from __future__ import annotations

from decimal import Decimal

import app.db as db_mod
from app import create_app
from app.db import get_session
from app.models_db import CatalogPart, PriceChangeLog, User
from werkzeug.security import generate_password_hash


def _reset_engines() -> None:
    db_mod._engine = None
    db_mod._accounts_engine = None
    db_mod._quotes_engine = None
    db_mod._orders_engine = None
    db_mod._pricing_engine = None
    db_mod._Session = None


def _admin_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("ACCOUNTS_DATABASE_PATH", str(tmp_path / "accounts.db"))
    monkeypatch.setenv("QUOTES_DATABASE_PATH", str(tmp_path / "quotes.db"))
    monkeypatch.setenv("ORDERS_DATABASE_PATH", str(tmp_path / "orders.db"))
    monkeypatch.setenv("PRICING_DATABASE_PATH", str(tmp_path / "Pricing.db"))
    monkeypatch.setenv("INVENTORY_DATABASE_PATH", str(tmp_path / "Inventory.db"))
    _reset_engines()

    app = create_app()
    app.testing = True
    with get_session() as session:
        session.add_all([
            CatalogPart(part_number="S-100", description="Viton Rod Seal 1.000", sell_price=Decimal("100.0000"), unit_cost=Decimal("40.0000")),
            CatalogPart(part_number="S-200", description="Viton Rod Seal 2.000", sell_price=Decimal("57.5000"), unit_cost=Decimal("20.0000")),
            CatalogPart(part_number="S-300", description="Buna Rod Seal 1.500", sell_price=Decimal("10.0000"), unit_cost=Decimal("5.0000")),
            User(
                display_name="Catalog Admin",
                username="admin@example.com",
                email="admin@example.com",
                password_hash=generate_password_hash("pw"),
                role="employee",
                access_level="admin",
                is_active=True,
            ),
            User(
                display_name="Standard Employee",
                username="standard@example.com",
                email="standard@example.com",
                password_hash=generate_password_hash("pw"),
                role="employee",
                access_level="standard",
                is_active=True,
            ),
        ])
        session.commit()
        ids = {p.part_number: p.id for p in session.query(CatalogPart).all()}

    client = app.test_client()
    client.post("/employee/login", data={"identity": "admin@example.com", "password": "pw"})
    return app, client, ids


def test_bulk_preview_apply_history_and_restore(tmp_path, monkeypatch):
    _, client, ids = _admin_client(tmp_path, monkeypatch)
    viton_ids = [ids["S-100"], ids["S-200"]]

    page = client.get("/parts-catalog").get_data(as_text=True)
    assert "select-all-parts" in page
    assert "Bulk Price Update" in page
    assert "Apply Changes" in page

    preview = client.post(
        "/parts-catalog/bulk-price/preview",
        json={"table": "catalog_parts", "field": "sell_price", "ids": viton_ids, "method": "increase_percent", "amount": "30"},
    ).get_json()
    assert preview["count"] == 2
    assert {row["new_formatted"] for row in preview["rows"]} == {"$130.00", "$74.75"}

    # Preview alone must not change stored prices.
    with get_session() as session:
        assert session.get(CatalogPart, ids["S-100"]).sell_price == Decimal("100.0000")

    applied = client.post(
        "/parts-catalog/bulk-price/apply",
        json={
            "table": "catalog_parts",
            "field": "sell_price",
            "ids": viton_ids,
            "method": "increase_percent",
            "amount": "30",
            "context": "Viton seals",
        },
    ).get_json()
    assert applied["count"] == 2
    assert "Viton seals" in applied["summary"]

    with get_session() as session:
        assert session.get(CatalogPart, ids["S-100"]).sell_price == Decimal("130.0000")
        assert session.get(CatalogPart, ids["S-200"]).sell_price == Decimal("74.7500")
        assert session.get(CatalogPart, ids["S-300"]).sell_price == Decimal("10.0000")
        assert session.query(PriceChangeLog).filter_by(change_type="bulk").count() == 2

    # Fixed-dollar update on a different field.
    client.post(
        "/parts-catalog/bulk-price/apply",
        json={"table": "catalog_parts", "field": "unit_cost", "ids": [ids["S-300"]], "method": "add_amount", "amount": "2.50"},
    )
    with get_session() as session:
        assert session.get(CatalogPart, ids["S-300"]).unit_cost == Decimal("7.5000")

    history = client.get("/parts-catalog/price-history").get_json()["changes"]
    assert history[0]["changed_by"] == "Catalog Admin"
    target = next(c for c in history if c["label"] == "S-100" and c["change_type"] == "bulk")
    assert (target["old_formatted"], target["new_formatted"]) == ("$100.00", "$130.00")

    restored = client.post(f"/parts-catalog/price-history/{target['id']}/restore").get_json()
    assert restored["formatted"] == "$100.00"
    with get_session() as session:
        assert session.get(CatalogPart, ids["S-100"]).sell_price == Decimal("100.0000")
        assert session.query(PriceChangeLog).filter_by(change_type="restore").count() == 1


def test_individual_edit_is_audited_and_non_admin_blocked(tmp_path, monkeypatch):
    _, client, ids = _admin_client(tmp_path, monkeypatch)

    assert client.post(
        "/parts-catalog/price",
        json={"table": "catalog_parts", "id": ids["S-300"], "field": "sell_price", "value": "12.00"},
    ).status_code == 200
    with get_session() as session:
        entry = session.query(PriceChangeLog).filter_by(change_type="individual").one()
        assert (entry.old_value, entry.new_value) == (Decimal("10.0000"), Decimal("12.0000"))
        assert entry.changed_by_name == "Catalog Admin"

    client.get("/logout")
    client.post("/employee/login", data={"identity": "standard@example.com", "password": "pw"})
    for url in ("/parts-catalog/bulk-price/preview", "/parts-catalog/bulk-price/apply"):
        assert client.post(url, json={}).status_code == 302
    assert client.get("/parts-catalog/price-history").status_code == 302
    assert client.post("/parts-catalog/price-history/1/restore").status_code == 302
