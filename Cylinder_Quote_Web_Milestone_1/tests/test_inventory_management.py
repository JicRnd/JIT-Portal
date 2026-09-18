from __future__ import annotations

import io
from decimal import Decimal

import app.db as db_mod
from app import create_app
from app.db import get_session
from app.models_db import CatalogPart, InventoryPart, User
from werkzeug.security import generate_password_hash


def _admin_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("ACCOUNTS_DATABASE_PATH", str(tmp_path / "accounts.db"))
    monkeypatch.setenv("QUOTES_DATABASE_PATH", str(tmp_path / "quotes.db"))
    monkeypatch.setenv("ORDERS_DATABASE_PATH", str(tmp_path / "orders.db"))
    monkeypatch.setenv("PRICING_DATABASE_PATH", str(tmp_path / "Pricing.db"))
    monkeypatch.setenv("INVENTORY_DATABASE_PATH", str(tmp_path / "Inventory.db"))
    db_mod.reset_engines()

    app = create_app()
    app.testing = True
    with get_session() as session:
        session.add_all([
            CatalogPart(part_number="S-100", description="Seal"),
            User(
                display_name="Inventory Admin",
                username="inventory@example.com",
                email="inventory@example.com",
                password_hash=generate_password_hash("pw"),
                role="employee",
                access_level="admin",
                is_active=True,
            ),
        ])
        session.commit()

    client = app.test_client()
    client.post("/employee/login", data={"identity": "inventory@example.com", "password": "pw"})
    return client


def test_inventory_import_rounds_up_and_supports_search_and_edit(tmp_path, monkeypatch):
    client = _admin_client(tmp_path, monkeypatch)
    upload = io.BytesIO(
        b"Part Number,Product Description,On Hand,Allocated\n"
        b"S-100,Seal,12.001,3\n"
        b"UNMATCHED,Other,4.0,0\n"
    )

    preview = client.post(
        "/parts-catalog/inventory/preview",
        data={"inventory_file": (upload, "inventory.csv")},
        content_type="multipart/form-data",
    )
    assert preview.status_code == 200
    assert {row["inventory"] for row in preview.get_json()["rows"]} == {10, 4}

    upload = io.BytesIO(
        b"Part Number,Product Description,On Hand,Allocated\n"
        b"S-100,Seal,12.001,3\n"
        b"UNMATCHED,Other,4.0,0\n"
    )
    applied = client.post(
        "/parts-catalog/inventory/apply",
        data={"inventory_file": (upload, "inventory.csv")},
        content_type="multipart/form-data",
    )
    assert applied.status_code == 200
    assert applied.get_json()["total"] == 2

    with get_session() as session:
        stored = session.query(InventoryPart).filter_by(part_number="S-100").one()
        assert stored.inventory == 10
        assert session.query(CatalogPart).filter_by(part_number="S-100").one().inventory is None

    search = client.get("/parts-catalog/inventory/search?q=S-100")
    assert search.status_code == 200
    assert search.get_json()["rows"][0]["inventory"] == "10"

    edited = client.post(
        "/parts-catalog/inventory/part",
        json={"part_number": "S-100", "inventory": "10.01"},
    )
    assert edited.status_code == 200
    assert edited.get_json()["row"]["inventory"] == "11"

    with get_session() as session:
        assert session.query(InventoryPart).filter_by(part_number="S-100").one().inventory == 11


def test_inventory_search_formats_allocated_by_allocation_category(tmp_path, monkeypatch):
    client = _admin_client(tmp_path, monkeypatch)
    with get_session() as session:
        session.add_all([
            InventoryPart(part_number="COUNT-1", product_description="Seal", inventory=4, allocated=3),
            InventoryPart(part_number="LENGTH-1", product_description="Rod", inventory=4, allocated=22.188),
        ])
        session.commit()

    response = client.get("/parts-catalog/inventory/search?q=-1")
    rows = {row["part_number"]: row for row in response.get_json()["rows"]}
    assert rows["COUNT-1"]["allocated"] == "3"
    assert rows["LENGTH-1"]["allocated"] == "22.188"


def test_catalog_uses_dedicated_inventory_quantity(tmp_path, monkeypatch):
    client = _admin_client(tmp_path, monkeypatch)
    with get_session() as session:
        session.add(
            InventoryPart(
                part_number="S-100",
                product_description="Seal",
                inventory=17,
                allocated=Decimal("0"),
            )
        )
        session.commit()

    page = client.get("/parts-catalog")
    assert page.status_code == 200
    assert 'data-field="inventory" data-value="17"' in page.get_data(as_text=True)
