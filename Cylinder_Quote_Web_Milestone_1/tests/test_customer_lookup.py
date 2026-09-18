from __future__ import annotations

import pytest
from pathlib import Path

from app import create_app
from app.db import get_session, init_db
from app.models_db import Customer, User


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the app at a temporary SQLite database and create tables."""
    db_path = tmp_path / "test_customer_lookup.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("ACCOUNTS_DATABASE_PATH", str(tmp_path / "test_customer_lookup_accounts.db"))
    monkeypatch.setenv("CONTACTS_DATABASE_PATH", str(tmp_path / "test_customer_lookup_contacts.db"))
    monkeypatch.setenv("QUOTES_DATABASE_PATH", str(tmp_path / "test_customer_lookup_quotes.db"))
    monkeypatch.setenv("ORDERS_DATABASE_PATH", str(tmp_path / "test_customer_lookup_orders.db"))

    import app.db as db_mod

    db_mod._engine = None
    db_mod._accounts_engine = None
    db_mod._contacts_engine = None
    db_mod._quotes_engine = None
    db_mod._orders_engine = None
    db_mod._Session = None
    init_db()

    app = create_app()
    app.testing = True
    yield app

    db_mod._engine = None
    db_mod._accounts_engine = None
    db_mod._contacts_engine = None
    db_mod._quotes_engine = None
    db_mod._orders_engine = None
    db_mod._Session = None


def _headers(user: str = "test-employee"):
    return {"X-User-Name": user}


def test_search_returns_member_and_customer_status(temp_db):
    client = temp_db.test_client()
    with get_session() as session:
        member_customer = Customer(name="Member Co", email="member@example.com")
        visitor_customer = Customer(name="Visitor Co", email="visitor@example.com")
        blank_email_customer = Customer(name="Blank Email Co", email=None)
        session.add_all([member_customer, visitor_customer, blank_email_customer])
        member_user = User(
            display_name="Member User",
            email="MEMBER@EXAMPLE.COM",
            role="customer",
        )
        session.add(member_user)
        session.commit()

    resp = client.get("/api/customers/search?q=Co", headers=_headers())
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    customers = {c["name"]: c for c in data["customers"]}
    assert customers["Member Co"]["status"] == "Member"
    assert customers["Member Co"]["email"] == "member@example.com"
    assert customers["Visitor Co"]["status"] == "Customer"
    assert customers["Blank Email Co"]["status"] == "Customer"


def test_patch_updates_customer_and_rejects_blank_name(temp_db):
    client = temp_db.test_client()
    with get_session() as session:
        customer = Customer(name="Old Name", email="old@example.com")
        session.add(customer)
        session.commit()
        customer_id = customer.id

    resp = client.patch(
        f"/api/customers/{customer_id}",
        json={"name": "New Name", "phone": "555-1234"},
        headers=_headers(),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["customer"]["name"] == "New Name"
    assert data["customer"]["phone"] == "555-1234"
    assert data["customer"]["email"] == "old@example.com"
    assert data["customer"]["status"] == "Customer"

    resp_blank = client.patch(
        f"/api/customers/{customer_id}",
        json={"name": "   "},
        headers=_headers(),
    )
    assert resp_blank.status_code == 400
    assert resp_blank.get_json()["ok"] is False


def test_patch_returns_404_for_missing_customer(temp_db):
    client = temp_db.test_client()
    resp = client.patch(
        "/api/customers/99999",
        json={"name": "New Name"},
        headers=_headers(),
    )
    assert resp.status_code == 404
    assert resp.get_json()["ok"] is False


def test_list_all_customers_ordered_by_name(temp_db):
    client = temp_db.test_client()
    with get_session() as session:
        customer_a = Customer(name="Alpha Co", email="alpha@example.com")
        customer_z = Customer(name="Zulu Co", email="zulu@example.com")
        customer_m = Customer(name="Mike Co", email="MIKE@EXAMPLE.COM")
        member_user = User(
            display_name="Mike User",
            email="mike@example.com",
            role="customer",
        )
        session.add_all([customer_a, customer_z, customer_m, member_user])
        session.commit()

    resp = client.get("/api/customers/all", headers=_headers())
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    names = [c["name"] for c in data["customers"]]
    assert names == ["Alpha Co", "Mike Co", "Zulu Co"]
    by_name = {c["name"]: c for c in data["customers"]}
    assert by_name["Alpha Co"]["status"] == "Customer"
    assert by_name["Mike Co"]["status"] == "Member"
    assert by_name["Zulu Co"]["status"] == "Customer"


def test_customer_lookup_returns_company_poc_address_city_and_notes(temp_db):
    client = temp_db.test_client()
    with get_session() as session:
        customer = Customer(
            company_name="Acme Industries",
            poc="Pat Customer",
            name="Legacy Customer Name",
            address="100 Main Street",
            city_state_zip="Nashville, TN 37201",
            email="pat@example.com",
            notes="Call before quoting.",
        )
        session.add(customer)
        session.commit()

    response = client.get("/api/customers/search?q=Acme", headers=_headers())
    row = response.get_json()["customers"][0]
    assert row["company_name"] == "Acme Industries"
    assert row["poc"] == "Pat Customer"
    assert row["address"] == "100 Main Street"
    assert row["city_state_zip"] == "Nashville, TN 37201"
    assert row["notes"] == "Call before quoting."

    updated = client.patch(
        f"/api/customers/{row['id']}",
        json={"notes": "Updated customer note."},
        headers=_headers(),
    )
    assert updated.status_code == 200
    assert updated.get_json()["customer"]["notes"] == "Updated customer note."


def test_customer_search_matches_name_fields_at_word_starts(temp_db):
    client = temp_db.test_client()
    with get_session() as session:
        customer = Customer(
            company_name="Northwind Cylinders",
            name="Northwind Legacy",
            poc="Pat Contact",
            address="742 Cedar Avenue",
            city_state_zip="Springfield, TN 37172",
            shipping_address="Dock 4 Receiving",
            phone="555-0198",
            email="orders@northwind.example",
            notes="Call after 2 PM for receiving.",
        )
        session.add(customer)
        session.commit()

    for query in ("north", "Cyl", "Con"):
        response = client.get(f"/api/customers/search?q={query}", headers=_headers())
        assert response.status_code == 200
        assert [row["name"] for row in response.get_json()["customers"]] == [
            "Northwind Legacy"
        ]

    for query in ("wind", "orthwind", "at Con", "edar", "field", "ock", "019", "northwind.example", "receiving"):
        response = client.get(f"/api/customers/search?q={query}", headers=_headers())
        assert response.status_code == 200
        assert response.get_json()["customers"] == []


def test_customer_search_surfaces_keep_two_character_trigger():
    app_root = Path(__file__).parents[1]
    required_guard = 'if (term.length < 2)'
    for relative_path in (
        "app/static/app.js",
        "app/Employee_dashboard/employee_dashboard.html",
        "app/Admin_Dashboard/Admin_dashboard.html",
    ):
        source = (app_root / relative_path).read_text(encoding="utf-8")
        assert required_guard in source


def test_employee_can_create_company_only_contact_without_poc(temp_db):
    client = temp_db.test_client()

    response = client.post(
        "/api/customers",
        json={
            "company_name": "Company Only Contact",
            "address": "1 Main Street",
            "city_state_zip": "Nashville, TN 37201",
            "phone": "555-0100",
            "email": "company@example.com",
        },
        headers=_headers(),
    )

    assert response.status_code == 201
    customer = response.get_json()["customer"]
    assert customer["company_name"] == "Company Only Contact"
    assert customer["poc"] is None
    assert customer["address"] == "1 Main Street"


def test_employee_can_open_customer_dashboard_history_view(temp_db):
    client = temp_db.test_client()
    with get_session() as session:
        employee = User(
            display_name="Lookup Employee",
            username="lookup-employee",
            role="employee",
            access_level="standard",
            is_active=True,
        )
        customer = Customer(
            name="BrightPath Solutions",
            company_name="BrightPath Solutions",
            address="2 Main Street",
        )
        session.add_all([employee, customer])
        session.commit()
        employee_id = employee.id
        customer_id = customer.id

    with client.session_transaction() as session:
        session["user_id"] = employee_id
        session["role"] = "employee"

    response = client.get(f"/employee/customer-dashboard/{customer_id}")

    assert response.status_code == 200
    assert b"JIT BrightPath Solutions's Dashboard" in response.data
    assert b"Back to Dashboard" in response.data
