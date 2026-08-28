from __future__ import annotations

import app.db as db_mod
from app import create_app
from app.db import get_session, get_pricing_engine
from app.models_db import BaseAssemblyPrice, CatalogPart, User
from app.pricing_catalog_service import import_pricing_catalog
from decimal import Decimal
from sqlalchemy import inspect
from werkzeug.security import generate_password_hash


def _reset_engines() -> None:
    db_mod._engine = None
    db_mod._accounts_engine = None
    db_mod._quotes_engine = None
    db_mod._orders_engine = None
    db_mod._pricing_engine = None
    db_mod._Session = None


def test_pricing_catalog_import_and_admin_page(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("ACCOUNTS_DATABASE_PATH", str(tmp_path / "accounts.db"))
    monkeypatch.setenv("QUOTES_DATABASE_PATH", str(tmp_path / "quotes.db"))
    monkeypatch.setenv("ORDERS_DATABASE_PATH", str(tmp_path / "orders.db"))
    monkeypatch.setenv("PRICING_DATABASE_PATH", str(tmp_path / "Pricing.db"))
    _reset_engines()

    try:
        app = create_app()
        app.testing = True
        first_import = import_pricing_catalog()
        second_import = import_pricing_catalog()

        assert first_import == second_import
        assert set(inspect(get_pricing_engine()).get_table_names()) == {
            "base_assembly_prices",
            "catalog_parts",
            "common_modification_prices",
            "ph_va_prices",
            "price_change_log",
        }

        with get_session() as session:
            assert session.query(CatalogPart).count() == first_import["catalog_parts"]
            session.add_all([
                User(
                    display_name="Standard Employee",
                    username="standard@example.com",
                    email="standard@example.com",
                    password_hash=generate_password_hash("pw"),
                    role="employee",
                    access_level="standard",
                    is_active=True,
                ),
                User(
                    display_name="Catalog Admin",
                    username="admin@example.com",
                    email="admin@example.com",
                    password_hash=generate_password_hash("pw"),
                    role="employee",
                    access_level="admin",
                    is_active=True,
                ),
            ])
            session.commit()

        client = app.test_client()
        client.post("/employee/login", data={"identity": "standard@example.com", "password": "pw"})
        assert client.get("/parts-catalog", follow_redirects=False).status_code == 302
        assert client.post(
            "/parts-catalog/price",
            json={"table": "catalog_parts", "id": 1, "field": "unit_cost", "value": "1.00"},
            follow_redirects=False,
        ).status_code == 302

        client.get("/logout")
        client.post("/employee/login", data={"identity": "admin@example.com", "password": "pw"})
        page = client.get("/parts-catalog")
        content = page.get_data(as_text=True)
        assert page.status_code == 200
        assert "Pricing Catalog" in content
        assert "Polyurethane Rod Seal" in content
        assert "Base Cylinder Pricing" in content
        assert "Common Modifications" in content
        assert "PH / VA Pricing" in content
        assert "$" in content
        assert " / in" in content or " / mm" in content
        assert "CATEGORY_SEARCHES" in content
        assert "wipers" in content
        assert "pistons" in content
        assert "barrels" in content
        assert "tie rods" in content
        assert "jam nuts" in content
        assert "Other / Unclassified" in content
        assert "function partSize" in content

        with get_session() as session:
            part = session.query(CatalogPart).filter(CatalogPart.unit_cost.is_not(None)).first()
            dimensioned_row = session.query(BaseAssemblyPrice).filter(BaseAssemblyPrice.unit.in_(["in", "mm"])).first()
            assert part is not None
            assert dimensioned_row is not None

        response = client.post(
            "/parts-catalog/price",
            json={
                "table": "catalog_parts",
                "id": part.id,
                "field": "unit_cost",
                "value": "1234.56",
            },
        )
        assert response.status_code == 200
        assert response.get_json()["formatted"] == "$1,234.56"

        invalid = client.post(
            "/parts-catalog/price",
            json={
                "table": "catalog_parts",
                "id": part.id,
                "field": "unit_cost",
                "value": "-1",
            },
        )
        assert invalid.status_code == 400

        per_unit = client.post(
            "/parts-catalog/price",
            json={
                "table": "base_assembly_prices",
                "id": dimensioned_row.id,
                "field": "per_unit_price",
                "value": "12",
            },
        )
        assert per_unit.status_code == 200
        assert per_unit.get_json()["formatted"] in {"$12.00 / in", "$12.00 / mm"}

        readonly = client.post(
            "/parts-catalog/price",
            json={
                "table": "base_assembly_prices",
                "id": dimensioned_row.id,
                "field": "bore",
                "value": "3",
            },
        )
        assert readonly.status_code == 400

        with get_session() as session:
            assert session.get(CatalogPart, part.id).unit_cost == Decimal("1234.5600")

        refreshed = client.get("/parts-catalog").get_data(as_text=True)
        assert "$1,234.56" in refreshed
        assert " in" in refreshed or " mm" in refreshed
    finally:
        _reset_engines()