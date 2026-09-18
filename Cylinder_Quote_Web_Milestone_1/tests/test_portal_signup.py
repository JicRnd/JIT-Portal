from __future__ import annotations

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from app import create_app
from app.db import get_session, init_db
from app.models_db import Customer, User


@pytest.fixture
def portal_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "quotes.db"))
    monkeypatch.setenv(
        "ACCOUNTS_DATABASE_PATH",
        str(tmp_path / "accounts.db"),
    )
    monkeypatch.setenv("QUOTES_DATABASE_PATH", str(tmp_path / "quote_records.db"))
    monkeypatch.setenv("ORDERS_DATABASE_PATH", str(tmp_path / "orders.db"))

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


def test_customer_signup_submit_creates_pending_account(portal_app):
    response = portal_app.test_client().post(
        "/customer/signup",
        data={
            "display_name": "Ada Customer",
            "company_name": "Ada Cylinders",
            "email": "ada@example.com",
            "password": "test-password",
            "phone": "555-0100",
            "billing_street_address": "10 Billing Street",
            "billing_city_state_zip": "Nashville, TN 37201",
            "shipping_street_address": "20 Shipping Street",
            "shipping_city_state_zip": "Franklin, TN 37064",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/customer/login")

    with get_session() as db:
        user = db.query(User).filter_by(email="ada@example.com").one()

    assert user.role == "customer"
    assert user.is_active is False
    assert user.approval_status == "pending"
    assert user.company_name == "Ada Cylinders"
    assert user.phone == "555-0100"

    with get_session() as db:
        customer = db.query(Customer).filter_by(email="ada@example.com").one()

    assert customer.name == "Ada Customer"
    assert customer.company_name == "Ada Cylinders"
    assert customer.poc == "Ada Customer"
    assert customer.phone == "555-0100"
    assert customer.address == "10 Billing Street"
    assert customer.city_state_zip == "Nashville, TN 37201"
    assert customer.shipping_address == "20 Shipping Street, Franklin, TN 37064"


def test_company_only_signup_requires_no_full_name_and_creates_customer(portal_app):
    response = portal_app.test_client().post(
        "/customer/signup",
        data={
            "company_name": "Company Only Account",
            "email": "company-only@example.com",
            "password": "test-password",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with get_session() as db:
        customer = db.query(Customer).filter_by(email="company-only@example.com").one()

    assert customer.name == "Company Only Account"
    assert customer.company_name == "Company Only Account"
    assert customer.poc is None


def test_employee_created_customer_account_syncs_contact_directory(portal_app):
    client = portal_app.test_client()
    with get_session() as db:
        employee = User(
            display_name="Employee One",
            username="employee@example.com",
            email="employee@example.com",
            password_hash=generate_password_hash("pw"),
            role="employee",
            is_active=True,
        )
        db.add(employee)
        db.commit()
        employee_id = employee.id

    with client.session_transaction() as session:
        session["user_id"] = employee_id
        session["role"] = "employee"

    response = client.post(
        "/customer/signup",
        data={
            "display_name": "New Customer Contact",
            "company_name": "New Customer Company",
            "email": "new-contact@example.com",
            "password": "test-password",
            "billing_street_address": "10 Main Street",
            "billing_city_state_zip": "Nashville, TN 37201",
            "phone": "555-0142",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with get_session() as db:
        customer = db.query(Customer).filter_by(email="new-contact@example.com").one()
    assert customer.company_name == "New Customer Company"
    assert customer.poc == "New Customer Contact"
    assert customer.address == "10 Main Street"
    assert customer.city_state_zip == "Nashville, TN 37201"


def test_login_form_keeps_browser_autofill_fields(portal_app):
    response = portal_app.test_client().get("/employee/login")

    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert 'autocomplete="on"' in text
    assert 'id="username"' in text
    assert 'name="identity"' in text
    assert 'autocomplete="username"' in text
    assert 'id="password"' in text
    assert 'autocomplete="current-password"' in text


def test_employee_signup_submit_creates_pending_account(portal_app):
    response = portal_app.test_client().post(
        "/employee/signup",
        data={
            "display_name": "Ed Employee",
            "email": "ed@example.com",
            "password": "test-password",
            "phone": "555-0199",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/employee/login")

    with get_session() as db:
        user = db.query(User).filter_by(email="ed@example.com").one()

    assert user.role == "employee"
    assert user.is_active is False
    assert user.approval_status == "pending"
    assert user.access_level == "standard"


def test_inactive_account_can_resubmit_signup_credentials(portal_app):
    with get_session() as db:
        db.add(
            User(
                display_name="Inactive Employee",
                username="inactive@example.com",
                email="inactive@example.com",
                password_hash=generate_password_hash("old-password"),
                role="employee",
                is_active=False,
                approval_status="approved",
            )
        )
        db.commit()

    response = portal_app.test_client().post(
        "/employee/signup",
        data={
            "display_name": "Inactive Employee",
            "email": "inactive@example.com",
            "password": "new-password",
            "phone": "555-2020",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/employee/login")

    with get_session() as db:
        user = db.query(User).filter_by(email="inactive@example.com").one()

    assert user.is_active is False
    assert user.approval_status == "pending"
    assert user.phone == "555-2020"
    assert check_password_hash(user.password_hash, "new-password")


def test_forgot_access_resets_existing_password(portal_app):
    with get_session() as db:
        db.add(
            User(
                display_name="Recover Me",
                username="recover@example.com",
                email="recover@example.com",
                password_hash=generate_password_hash("old-password"),
                role="employee",
                is_active=True,
            )
        )
        db.commit()

    client = portal_app.test_client()
    page = client.get("/forgot-access")
    assert page.status_code == 200
    assert "Reset Password" in page.get_data(as_text=True)

    response = client.post(
        "/forgot-access",
        data={
            "identity": "recover@example.com",
            "new_password": "new-password",
            "confirm_password": "new-password",
        },
    )
    assert response.status_code == 200
    assert "password has been updated" in response.get_data(as_text=True)

    with get_session() as db:
        user = db.query(User).filter_by(email="recover@example.com").one()

    assert check_password_hash(user.password_hash, "new-password")


def test_employee_dashboard_has_pending_decision_buttons(portal_app):
    with get_session() as db:
        db.add(
            User(
                display_name="Employee One",
                username="employee@example.com",
                email="employee@example.com",
                password_hash=generate_password_hash("pw"),
                role="employee",
                is_active=True,
            )
        )
        db.add(
            User(
                display_name="Pending Customer",
                username="pending@example.com",
                email="pending@example.com",
                password_hash=generate_password_hash("pw"),
                role="customer",
                is_active=False,
                company_name="Pending Co",
                approval_status="pending",
            )
        )
        db.add(
            User(
                display_name="Pending Employee",
                username="pending-employee@example.com",
                email="pending-employee@example.com",
                password_hash=generate_password_hash("pw"),
                role="employee",
                is_active=False,
                approval_status="pending",
            )
        )
        db.commit()

    client = portal_app.test_client()
    client.post(
        "/employee/login",
        data={"identity": "employee@example.com", "password": "pw"},
        follow_redirects=False,
    )

    dashboard_response = client.get("/employee/dashboard")
    assert dashboard_response.status_code == 200
    text = dashboard_response.get_data(as_text=True)
    assert "Approve" in text
    assert "Hold" in text
    assert "Deny" in text
    assert "Details" in text
    assert 'data-user-email="pending@example.com"' in text
    assert 'data-user-role="customer"' in text
    assert "Pending Customer" in text
    assert "Pending Employee" in text
    assert "Employee Request" in text


def test_employee_dashboard_lists_pending_customer_account_requests(portal_app):
    with get_session() as db:
        db.add(
            User(
                display_name="Employee One",
                username="employee@example.com",
                email="employee@example.com",
                password_hash=generate_password_hash("pw"),
                role="employee",
                is_active=True,
            )
        )
        db.add(
            User(
                display_name="Pending Customer",
                username="pending@example.com",
                email="pending@example.com",
                password_hash=generate_password_hash("pw"),
                role="customer",
                is_active=False,
                company_name="Pending Co",
            )
        )
        db.commit()

    client = portal_app.test_client()
    login_response = client.post(
        "/employee/login",
        data={"identity": "employee@example.com", "password": "pw"},
        follow_redirects=False,
    )
    assert login_response.status_code == 302

    dashboard_response = client.get("/employee/dashboard")
    assert dashboard_response.status_code == 200
    text = dashboard_response.get_data(as_text=True)
    assert "Pending Approvals" in text
    accept_section = text.split("<h2>New Accept Request</h2>", 1)[1].split(
        "</section>", 1
    )[0]
    pending_section = text.split("<h2>Pending Approvals</h2>", 1)[1].split(
        "</section>", 1
    )[0]
    assert "Pending Customer" in accept_section
    assert "Pending Co" in accept_section
    assert "Pending Customer" not in pending_section
    assert "Pending Co" not in pending_section


def test_manage_users_can_update_password_and_employee_access_level(portal_app):
    with get_session() as db:
        admin = User(
            display_name="Admin Employee",
            username="admin@example.com",
            email="admin@example.com",
            password_hash=generate_password_hash("pw"),
            role="employee",
            is_active=True,
            access_level="standard",
        )
        target = User(
            display_name="Target Employee",
            username="target@example.com",
            email="target@example.com",
            password_hash=generate_password_hash("old-password"),
            role="employee",
            is_active=True,
            access_level="standard",
        )
        db.add_all([admin, target])
        db.commit()
        target_id = target.id

    client = portal_app.test_client()
    client.post(
        "/employee/login",
        data={"identity": "admin@example.com", "password": "pw"},
        follow_redirects=False,
    )

    page = client.get("/manage-users")
    assert page.status_code == 200
    text = page.get_data(as_text=True)
    assert "Standard User" in text
    assert "Admin User" in text
    assert "New password" in text

    access_response = client.post(
        f"/manage-users/{target_id}/access-level",
        data={"access_level": "admin"},
        follow_redirects=False,
    )
    assert access_response.status_code == 302

    password_response = client.post(
        f"/manage-users/{target_id}/password",
        data={"new_password": "new-password"},
        follow_redirects=False,
    )
    assert password_response.status_code == 302

    with get_session() as db:
        target = db.get(User, target_id)

    assert target.access_level == "admin"
    assert check_password_hash(target.password_hash, "new-password")


def test_account_directories_are_separated_by_role(portal_app):
    with get_session() as db:
        db.add_all(
            [
                User(
                    display_name="Directory Employee",
                    username="directory-employee@example.com",
                    email="directory-employee@example.com",
                    password_hash=generate_password_hash("pw"),
                    role="employee",
                    is_active=True,
                ),
                User(
                    display_name="Directory Customer",
                    username="directory-customer@example.com",
                    email="directory-customer@example.com",
                    password_hash=generate_password_hash("pw"),
                    role="customer",
                    is_active=True,
                    company_name="Directory Co",
                ),
            ]
        )
        db.commit()

    client = portal_app.test_client()
    client.post(
        "/employee/login",
        data={"identity": "directory-employee@example.com", "password": "pw"},
    )

    employee_page = client.get("/manage-users")
    customer_page = client.get("/customer-accounts")

    assert employee_page.status_code == 200
    assert customer_page.status_code == 200
    assert "Directory Employee" in employee_page.get_data(as_text=True)
    assert "Directory Customer" not in employee_page.get_data(as_text=True)
    assert "Directory Customer" in customer_page.get_data(as_text=True)
    assert ">Directory Employee</strong></td>" not in customer_page.get_data(as_text=True)
    assert "Access Level" not in customer_page.get_data(as_text=True)


def test_customer_account_password_action_returns_to_customer_directory(portal_app):
    with get_session() as db:
        admin = User(
            display_name="Account Admin",
            username="account-admin@example.com",
            email="account-admin@example.com",
            password_hash=generate_password_hash("pw"),
            role="employee",
            is_active=True,
        )
        customer = User(
            display_name="Password Customer",
            username="password-customer@example.com",
            email="password-customer@example.com",
            password_hash=generate_password_hash("old-password"),
            role="customer",
            is_active=True,
        )
        db.add_all([admin, customer])
        db.commit()
        customer_id = customer.id

    client = portal_app.test_client()
    client.post(
        "/employee/login",
        data={"identity": "account-admin@example.com", "password": "pw"},
    )

    response = client.post(
        f"/manage-users/{customer_id}/password",
        data={"new_password": "new-password", "return_to": "customer_accounts"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/customer-accounts")
    with get_session() as db:
        assert check_password_hash(db.get(User, customer_id).password_hash, "new-password")


def test_employee_dashboard_customer_lookup_has_email_and_attachment_controls(portal_app):
    with get_session() as db:
        db.add(
            User(
                display_name="Employee One",
                username="employee@example.com",
                email="employee@example.com",
                password_hash=generate_password_hash("pw"),
                role="employee",
                is_active=True,
            )
        )
        db.add(
            Customer(
                name="Email Customer Co",
                email="contact@example.com",
                phone="555-1212",
            )
        )
        db.commit()

    client = portal_app.test_client()
    client.post(
        "/employee/login",
        data={"identity": "employee@example.com", "password": "pw"},
        follow_redirects=False,
    )

    dashboard_response = client.get("/employee/dashboard?q=Email%20Customer")
    assert dashboard_response.status_code == 200
    text = dashboard_response.get_data(as_text=True)
    assert "mailto:contact%40example.com" in text
    assert "Email Customer" in text
    assert "Attach Quote Form" in text
    assert "Attach Report Images" in text
    assert 'if (term.length < 2)' in text