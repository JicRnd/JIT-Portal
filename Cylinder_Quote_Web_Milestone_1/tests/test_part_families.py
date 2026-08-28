from __future__ import annotations

import io
from decimal import Decimal

import app.db as db_mod
import app.part_family_service as family_mod
from app.db import get_session
from app.models_db import CatalogPart, User
from app.part_family_service import decode_size
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
    monkeypatch.setattr(family_mod, "FAMILY_IMAGE_DIRECTORY", tmp_path / "family_images")
    _reset_engines()

    app = create_app()
    app.testing = True
    with get_session() as session:
        session.add_all([
            CatalogPart(part_number="062GV", description="Rod Seal", sell_price=Decimal("9.0000")),
            CatalogPart(part_number="100GV", description="Rod Seal", sell_price=Decimal("10.0000")),
            CatalogPart(part_number="300GV", description="Rod Seal", sell_price=Decimal("11.0000")),
            CatalogPart(part_number="GVX", description="Viton Rod Seal odd size", sell_price=Decimal("12.0000")),
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


def _create_gv_family(client, template="{part_number} is a {size}-inch Viton/FKM rod seal."):
    return client.post("/parts-catalog/families", json={
        "family_code": "GV",
        "display_name": "Viton Rod Seals",
        "material": "Viton/FKM",
        "part_type": "Rod Seal",
        "description_template": template,
        "size_rule": "prefix_hundredths",
        "auto_description_enabled": True,
    }).get_json()


def test_size_decoding_rules():
    assert decode_size("300GV", "prefix_hundredths") == 3.0
    assert decode_size("100GV", "prefix_hundredths") == 1.0
    assert decode_size("062GV", "prefix_hundredths") == 0.625
    assert decode_size("GVX", "prefix_hundredths") is None
    assert decode_size("062GV", "none") is None
    assert decode_size("0625GV", "prefix_thousandths") == 0.625
    assert decode_size("062GV", r"regex:^(\d+)GV$:100") == 0.62


def test_family_create_edit_and_template_substitution(tmp_path, monkeypatch):
    _, client, ids = _admin_client(tmp_path, monkeypatch)
    created = _create_gv_family(client)
    assert created["ok"] is True
    family_id = created["family"]["id"]

    assigned = client.post("/parts-catalog/families/assign", json={
        "family_code": "GV",
        "ids": [ids["062GV"], ids["100GV"], ids["300GV"], ids["GVX"]],
    }).get_json()
    assert assigned["assigned"] == 4

    preview = client.get(f"/parts-catalog/families/{family_id}/preview").get_json()
    rows = {row["part_number"]: row for row in preview["rows"]}
    assert rows["062GV"]["description"] == "062GV is a 0.625-inch Viton/FKM rod seal."
    assert rows["100GV"]["description"] == "100GV is a 1.000-inch Viton/FKM rod seal."
    assert rows["300GV"]["description"] == "300GV is a 3.000-inch Viton/FKM rod seal."
    # Undecodable part is flagged, never guessed.
    assert rows["GVX"]["generated"] is False
    assert rows["GVX"]["description"] == "Viton Rod Seal odd size"
    assert preview["unresolved"] == 1

    updated = client.post(f"/parts-catalog/families/{family_id}", json={
        "family_code": "GV",
        "display_name": "Viton / FKM Rod Seals",
        "material": "Viton/FKM",
        "part_type": "Rod Seal",
        "description_template": "{part_number} is a {size}-inch Viton/FKM rod seal.",
        "size_rule": "prefix_hundredths",
        "auto_description_enabled": True,
    }).get_json()
    assert updated["family"]["display_name"] == "Viton / FKM Rod Seals"


def test_catalog_page_shows_family_band_and_generated_descriptions(tmp_path, monkeypatch):
    _, client, ids = _admin_client(tmp_path, monkeypatch)
    family_id = _create_gv_family(client)["family"]["id"]
    client.post("/parts-catalog/families/assign", json={
        "family_code": "GV", "ids": [ids["062GV"], ids["100GV"], ids["300GV"], ids["GVX"]],
    })
    client.post(
        f"/parts-catalog/families/{family_id}/image",
        data={"image": (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 32), "diagram.png")},
        content_type="multipart/form-data",
    )

    page = client.get("/parts-catalog").get_data(as_text=True)
    assert "Viton Rod Seals" in page
    assert "family_images/gv.png" in page
    assert "062GV is a 0.625-inch Viton/FKM rod seal." in page
    # Stored description is untouched for the undecodable part.
    assert "Viton Rod Seal odd size" in page
    # Existing catalog features remain on the page.
    assert "catalog-contents" in page
    assert "Pricing Catalog Settings" in page
    assert "Assign Selected Parts to a Family" in page
    assert "Bulk Price Update" in page
    assert "Price Change History" in page
    assert "Add Part" in page

    with get_session() as session:
        stored = session.get(CatalogPart, ids["062GV"])
        assert stored.description == "Rod Seal"

    # Family parts stay sorted smallest to largest.
    order = [page.index(part) for part in ("062GV", "100GV", "300GV")]
    assert order == sorted(order)


def test_family_validation_and_admin_only(tmp_path, monkeypatch):
    app, client, _ = _admin_client(tmp_path, monkeypatch)

    bad_variable = client.post("/parts-catalog/families", json={
        "family_code": "XX", "display_name": "X", "description_template": "{bogus}",
    }).get_json()
    assert bad_variable["ok"] is False

    size_without_rule = client.post("/parts-catalog/families", json={
        "family_code": "YY", "display_name": "Y",
        "description_template": "{part_number} {size}",
        "size_rule": "none", "auto_description_enabled": True,
    }).get_json()
    assert size_without_rule["ok"] is False

    _create_gv_family(client)
    duplicate = client.post("/parts-catalog/families", json={
        "family_code": "GV", "display_name": "Copy",
    }).get_json()
    assert duplicate["ok"] is False

    anonymous = app.test_client()
    assert anonymous.get("/parts-catalog/families").status_code == 302
    assert anonymous.post("/parts-catalog/families", json={}).status_code == 302


def test_family_image_rejects_unsupported_file(tmp_path, monkeypatch):
    _, client, _ = _admin_client(tmp_path, monkeypatch)
    family_id = _create_gv_family(client)["family"]["id"]
    response = client.post(
        f"/parts-catalog/families/{family_id}/image",
        data={"image": (io.BytesIO(b"nope"), "evil.svg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert response.get_json()["ok"] is False
