from __future__ import annotations

from decimal import Decimal

import app.db as db_mod
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
    from app import create_app

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("ACCOUNTS_DATABASE_PATH", str(tmp_path / "accounts.db"))
    monkeypatch.setenv("QUOTES_DATABASE_PATH", str(tmp_path / "quotes.db"))
    monkeypatch.setenv("ORDERS_DATABASE_PATH", str(tmp_path / "orders.db"))
    monkeypatch.setenv("PRICING_DATABASE_PATH", str(tmp_path / "Pricing.db"))
    _reset_engines()

    app = create_app()
    app.testing = True
    with get_session() as session:
        session.add_all([
            CatalogPart(
                part_number="RS044", description="Rod Stud 7/16-20",
                unit_cost=Decimal("14.3000"), sell_price=Decimal("16.0000"),
                sell_price_source="ShipVia", shipvia_sell_values="16.0", acc_sell_values="20.0",
                review_needed="YES", review_reason="ShipVia and Acc sell prices differ",
            ),
            CatalogPart(part_number="S-100", description="Viton Rod Seal 1.000", sell_price=Decimal("100.0000"), unit_cost=Decimal("40.0000")),
            CatalogPart(part_number="W-050", description="Rod Wiper 0.500", sell_price=Decimal("5.0000"), unit_cost=Decimal("2.0000")),
            User(
                display_name="Catalog Admin", username="admin@example.com", email="admin@example.com",
                password_hash=generate_password_hash("pw"), role="employee", access_level="admin", is_active=True,
            ),
        ])
        session.commit()
        ids = {p.part_number: p.id for p in session.query(CatalogPart).all()}

    client = app.test_client()
    client.post("/employee/login", data={"identity": "admin@example.com", "password": "pw"})
    return app, client, ids


def test_conflict_column_removed_and_contents_present(tmp_path, monkeypatch):
    _, client, _ = _admin_client(tmp_path, monkeypatch)
    page = client.get("/parts-catalog").get_data(as_text=True)
    assert "Review / Conflict Status" not in page
    assert "catalog-contents" in page
    assert "catalog-index" not in page
    assert "Back to Index" not in page
    assert "Seals" in page
    assert "Wipers" in page
    assert "Add Part" in page


def test_conflict_details_and_resolve_use_source(tmp_path, monkeypatch):
    _, client, ids = _admin_client(tmp_path, monkeypatch)
    details = client.get(f"/parts-catalog/conflict/{ids['RS044']}?field=sell_price").get_json()
    assert details["ok"] is True
    assert {s["name"] for s in details["sources"]} == {"ShipVia", "Acc"}
    assert details["has_conflict"] is True

    resolved = client.post(
        f"/parts-catalog/conflict/{ids['RS044']}/resolve",
        json={"field": "sell_price", "resolution": "use_source", "source_name": "Acc"},
    ).get_json()
    assert resolved["ok"] is True
    assert resolved["formatted"] == "$20.00"

    with get_session() as session:
        row = session.get(CatalogPart, ids["RS044"])
        assert row.sell_price == Decimal("20.0000")
        assert row.review_needed == "NO"
        assert "Resolved by Catalog Admin" in row.review_reason
        assert session.query(PriceChangeLog).filter_by(change_type="conflict_resolved").count() == 1


def test_conflict_resolve_keep_leaves_unresolved(tmp_path, monkeypatch):
    _, client, ids = _admin_client(tmp_path, monkeypatch)
    resolved = client.post(
        f"/parts-catalog/conflict/{ids['RS044']}/resolve",
        json={"field": "sell_price", "resolution": "keep"},
    ).get_json()
    assert resolved["resolved"] is False
    with get_session() as session:
        row = session.get(CatalogPart, ids["RS044"])
        assert row.sell_price == Decimal("16.0000")
        assert row.review_needed == "YES"


def test_bulk_preview_flags_conflicted_rows(tmp_path, monkeypatch):
    _, client, ids = _admin_client(tmp_path, monkeypatch)
    preview = client.post(
        "/parts-catalog/bulk-price/preview",
        json={"table": "catalog_parts", "field": "sell_price", "ids": [ids["RS044"], ids["S-100"]], "method": "increase_percent", "amount": "10"},
    ).get_json()
    flags = {row["id"]: row["conflicted"] for row in preview["rows"]}
    assert flags[ids["RS044"]] is True
    assert flags[ids["S-100"]] is False


def test_add_part_success_and_duplicate_rejected(tmp_path, monkeypatch):
    _, client, _ = _admin_client(tmp_path, monkeypatch)
    created = client.post(
        "/parts-catalog/parts",
        json={"part_number": "NEW-001", "description": "New Barrel Tube 2.000", "category": "Barrels", "unit_cost": "10", "sell_price": "20"},
    ).get_json()
    assert created["ok"] is True

    with get_session() as session:
        row = session.query(CatalogPart).filter_by(part_number="NEW-001").one()
        assert row.category == "Barrels"
        assert row.sell_price == Decimal("20.0000")
        assert session.query(PriceChangeLog).filter_by(change_type="created").count() == 1

    page = client.get("/parts-catalog").get_data(as_text=True)
    assert "NEW-001" in page

    dup = client.post(
        "/parts-catalog/parts",
        json={"part_number": "NEW-001", "description": "Duplicate", "category": "Barrels"},
    )
    assert dup.status_code == 400
    assert "already exists" in dup.get_json()["error"]


def test_add_part_requires_fields_and_nonnegative_numbers(tmp_path, monkeypatch):
    _, client, _ = _admin_client(tmp_path, monkeypatch)
    missing = client.post("/parts-catalog/parts", json={"part_number": "", "description": "x", "category": "Seals"})
    assert missing.status_code == 400

    bad_price = client.post(
        "/parts-catalog/parts",
        json={"part_number": "NEG-1", "description": "Test", "category": "Seals", "sell_price": "-5"},
    )
    assert bad_price.status_code == 400
