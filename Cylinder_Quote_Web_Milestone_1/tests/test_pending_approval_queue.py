from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from sqlalchemy import select

from app import create_app
from app.db import get_session, init_db
from app.models_db import Order, Quote, User


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
    db_path = tmp_path / "test_pending_approval_queue.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("ACCOUNTS_DATABASE_PATH", str(tmp_path / "test_pending_approval_queue_accounts.db"))
    monkeypatch.setenv("QUOTES_DATABASE_PATH", str(tmp_path / "test_pending_approval_queue_quotes.db"))
    monkeypatch.setenv("ORDERS_DATABASE_PATH", str(tmp_path / "test_pending_approval_queue_orders.db"))

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


def _headers(user: str = "creator"):
    return {"X-User-Name": user}


def _create_employee_user(display_name: str, access_level: str = "standard") -> User:
    with get_session() as session:
        user = User(
            display_name=display_name,
            role="employee",
            access_level=access_level,
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def _create_customer_user(display_name: str) -> User:
    with get_session() as session:
        user = User(
            display_name=display_name,
            role="customer",
            company_name=display_name,
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def _login_client(client, user: User):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["role"] = user.role


def _create_quote(client, creator_name: str, customer_name: str, **overrides):
    payload = sample_payload()
    payload["customer_name"] = customer_name
    payload.update(overrides)
    resp = client.post("/api/quotes", json=payload, headers=_headers(creator_name))
    assert resp.status_code == 200
    return resp.get_json()["quote"]


def _set_quote_status(quote_id: int, status: str):
    with get_session() as session:
        quote = session.get(Quote, quote_id)
        quote.status = status
        session.commit()


def _set_quote_created_at(quote_id: int, created_at: datetime):
    with get_session() as session:
        quote = session.get(Quote, quote_id)
        quote.created_at = created_at
        session.commit()


def _assign_quote(quote_id: int, user_id: int):
    with get_session() as session:
        quote = session.get(Quote, quote_id)
        quote.assigned_employee_user_id = user_id
        session.commit()


def _unassigned_pending_count() -> int:
    with get_session() as session:
        return session.execute(
            select(Quote)
            .where(
                Quote.status == "pending_approval",
                Quote.assigned_employee_user_id.is_(None),
            )
        ).scalars().all().__len__()


def test_customer_dashboard_uses_only_customer_status_labels(temp_db):
    client = temp_db.test_client()
    customer = _create_customer_user("Customer Status Test")
    quote = _create_quote(client, customer.display_name, customer.display_name)

    _login_client(client, customer)
    for internal_status, customer_label in (
        ("new", "Pending Approval"),
        ("accepted", "Pending Approval"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("denied", "Denied"),
        ("canceled", "Canceled"),
    ):
        _set_quote_status(quote["id"], internal_status)
        response = client.get("/customer/dashboard")
        assert response.status_code == 200
        text = response.get_data(as_text=True)
        assert customer_label in text
        assert all(label in text for label in ("Pending Approval", "Approved", "Denied") if label == customer_label)


def test_customer_dashboard_displays_quote_number_not_order_number(temp_db):
    client = temp_db.test_client()
    customer = _create_customer_user("Bob White")
    quote = _create_quote(client, customer.display_name, customer.display_name)

    with get_session() as session:
        saved_quote = session.get(Quote, quote["id"])
        saved_quote.status = "pending_approval"
        saved_quote.order_form_snapshot = {"order_number": "J0910261343"}
        session.commit()

    _login_client(client, customer)
    response = client.get("/customer/dashboard")

    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert quote["quote_number"] in text
    assert "J0910261343" not in text


def test_customer_dashboard_contact_jit_opens_external_contact_page(temp_db):
    client = temp_db.test_client()
    customer = _create_customer_user("Contact JIT Test")

    _login_client(client, customer)
    response = client.get("/customer/dashboard")

    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert (
        '<a class="portal-button secondary" '
        'href="https://jitindustries.com/contact-us" '
        'target="_blank" rel="noopener noreferrer">'
        "\n          Contact JIT\n        </a>"
    ) in text


def test_customer_dashboard_open_uses_dedicated_customer_quote_form_route(temp_db):
    client = temp_db.test_client()
    customer = _create_customer_user("Bob White")
    quote = _create_quote(client, customer.display_name, customer.display_name)

    _login_client(client, customer)
    response = client.get("/customer/dashboard")

    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert f'href="/customer/quote-form?quote_number={quote["quote_number"]}"' in text
    assert f'href="/customer/quote-entry?quote_id={quote["id"]}"' not in text

    form_response = client.get(f"/customer/quote-form?quote_number={quote['quote_number']}")
    assert form_response.status_code == 200
    form_text = form_response.get_data(as_text=True)
    assert "JIT Customer Quote Form" in form_text
    assert 'Quoted for <span id="pv_created_by_footer">&mdash;</span>' in form_text
    assert "Quoted by" not in form_text


def test_unclaimed_pending_quote_appears_system_wide(temp_db):
    """A pending quote created by one employee shows in the queue for any employee."""
    client = temp_db.test_client()
    creator = _create_employee_user("creator")
    other = _create_employee_user("other")

    quote = _create_quote(client, creator.display_name, "Acme Corp")
    _set_quote_status(quote["id"], "pending_approval")

    _login_client(client, other)
    resp = client.get("/employee/dashboard")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "Pending Approvals" in text
    assert quote["quote_number"] in text
    assert "Acme Corp" in text


def test_new_quote_appears_in_new_accept_queue(temp_db):
    """New quotes use new status and appear in New Accept Request."""
    client = temp_db.test_client()
    employee = _create_employee_user("employee")
    quote = _create_quote(client, employee.display_name, "Draft Customer")
    assert quote["status"] == "new"

    _login_client(client, employee)
    resp = client.get("/employee/dashboard")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "Pending Approvals" in text
    assert "Draft Customer" in text


def test_accept_endpoint_race_safe(temp_db):
    """Two employees attempting to claim the same quote: only one succeeds."""
    client = temp_db.test_client()
    creator = _create_employee_user("creator")
    first = _create_employee_user("first")
    second = _create_employee_user("second")

    quote = _create_quote(client, creator.display_name, "Race Customer")
    _set_quote_status(quote["id"], "pending_approval")

    _login_client(client, first)
    resp1 = client.post(f"/employee/quotes/{quote['id']}/accept")
    assert resp1.status_code == 200
    assert resp1.get_json()["ok"] is True

    _login_client(client, second)
    resp2 = client.post(f"/employee/quotes/{quote['id']}/accept")
    assert resp2.status_code == 409
    body = resp2.get_json()
    assert body["ok"] is False
    assert "Already claimed" in body["error"]


def test_pending_queue_is_capped_at_25_oldest_quotes(temp_db):
    client = temp_db.test_client()
    creator = _create_employee_user("creator")
    viewer = _create_employee_user("viewer")

    for index in range(26):
        quote = _create_quote(
            client,
            creator.display_name,
            f"{chr(65 + index)} Queue Customer {index}",
        )
        _set_quote_created_at(
            quote["id"],
            datetime(2024, 1, 1) + timedelta(days=index),
        )
        _set_quote_status(quote["id"], "pending_approval")

    _login_client(client, viewer)
    resp = client.get("/employee/dashboard")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert text.count('data-pending-id="') == 25
    for index in range(25):
        assert f"Queue Customer {index}" in text
    assert "Queue Customer 25" not in text


def test_delete_pending_quote_preserves_canceled_record_and_redirects(temp_db):
    client = temp_db.test_client()
    employee = _create_employee_user("delete employee")
    quote = _create_quote(client, employee.display_name, "Delete Customer")
    _set_quote_status(quote["id"], "pending_approval")
    _assign_quote(quote["id"], employee.id)

    _login_client(client, employee)
    response = client.post(f"/employee/quotes/{quote['id']}/delete")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/employee/dashboard")
    with get_session() as session:
        saved_quote = session.get(Quote, quote["id"])
        assert saved_quote is not None
        assert saved_quote.status == "canceled"
        assert saved_quote.deleted_by_user_id == employee.id
        assert saved_quote.deleted_at is not None

    dashboard = client.get("/employee/dashboard")
    assert quote["quote_number"] not in dashboard.get_data(as_text=True)


def test_pending_approval_types_use_new_labels(temp_db):
    client = temp_db.test_client()
    employee = _create_employee_user("Employee One")
    with get_session() as session:
        session.add(
            User(
                display_name="Pending Customer",
                role="customer",
                is_active=False,
                approval_status="pending",
            )
        )
        session.add(
            User(
                display_name="Pending Employee",
                role="employee",
                is_active=False,
                approval_status="pending",
            )
        )
        session.commit()

    quote = _create_quote(client, employee.display_name, "Pending Quote")
    _set_quote_status(quote["id"], "pending_approval")
    assigned_quote = _create_quote(client, employee.display_name, "Assigned Pending Quote")
    _set_quote_status(assigned_quote["id"], "pending_approval")
    _assign_quote(assigned_quote["id"], employee.id)
    _login_client(client, employee)
    response = client.get("/employee/dashboard")
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "NEW - Quote" in text
    assert "NEW - Customer Request" in text
    assert "NEW - Employee Request" in text
    assert "Pending Approval" in text
    pending_section = text.split("<h2>Pending Approvals</h2>", 1)[1].split(
        "</section>", 1
    )[0]
    assert "<td>Quote</td>" in pending_section
    assert "<td>Pending Approval</td>" in pending_section
    assert "<td>Accepted</td>" not in pending_section
    assert "<td>Pending</td>" not in pending_section
    assert "Accepted Pending Quote" not in text
    assert "Pending Customer" not in pending_section
    assert "Pending Employee" not in pending_section


def test_pending_account_requests_are_capped_at_25(temp_db):
    client = temp_db.test_client()
    employee = _create_employee_user("Employee One")
    with get_session() as session:
        for index in range(26):
            session.add(
                User(
                    display_name=f"Pending Customer {index}",
                    role="customer",
                    is_active=False,
                    approval_status="pending",
                )
            )
        session.commit()

    _login_client(client, employee)
    response = client.get("/employee/dashboard")
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert text.count("NEW - Customer Request") == 25


def test_quote_history_includes_new_quotes(temp_db):
    client = temp_db.test_client()
    creator = _create_employee_user("creator")
    other = _create_employee_user("other")

    pending = _create_quote(client, creator.display_name, "Blocked History Customer")
    _set_quote_status(pending["id"], "pending_approval")
    open_quote = _create_quote(client, creator.display_name, "Open History Customer")
    _set_quote_status(open_quote["id"], "new")
    _set_quote_created_at(open_quote["id"], datetime(2024, 1, 1))
    _set_quote_created_at(pending["id"], datetime(2024, 1, 2))

    _login_client(client, creator)
    response = client.get("/employee_quote_history/employee_quote_history.html")
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "Open History Customer" in text
    assert "Blocked History Customer" in text

    _login_client(client, other)
    response = client.get("/employee_quote_history/employee_quote_history.html")
    assert response.status_code == 200
    assert "Open History Customer" in response.get_data(as_text=True)
    assert "Blocked History Customer" in response.get_data(as_text=True)


def test_order_history_includes_new_quotes(temp_db):
    client = temp_db.test_client()
    creator = _create_employee_user("creator")

    submitted = _create_quote(client, creator.display_name, "Submitted Order Customer")
    _set_quote_status(submitted["id"], "approved")
    with get_session() as session:
        session.get(Quote, submitted["id"]).order_form_snapshot = {
            "order_number": "J123456"
        }
        session.commit()

    unsubmitted = _create_quote(client, creator.display_name, "Unsubmitted Order Customer")
    _set_quote_status(unsubmitted["id"], "new")
    _set_quote_created_at(unsubmitted["id"], datetime(2024, 1, 1))
    _set_quote_created_at(submitted["id"], datetime(2024, 1, 2))

    _login_client(client, creator)
    response = client.get("/employee_order_history/employee_order_history.html")
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "Unsubmitted Order Customer" in text
    assert "Submitted Order Customer" in text


def test_employee_histories_are_capped_at_25_newest_quotes(temp_db):
    client = temp_db.test_client()
    creator = _create_employee_user("creator")

    for index in range(26):
        quote = _create_quote(
            client,
            creator.display_name,
            f"{chr(65 + index)} History Customer {index}",
        )
        _set_quote_created_at(
            quote["id"],
            datetime(2024, 1, 1) + timedelta(days=index),
        )
        _set_quote_status(quote["id"], "approved")

    _login_client(client, creator)
    for path in ("/employee_order_history/employee_order_history.html", "/employee_quote_history/employee_quote_history.html"):
        resp = client.get(path)
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert text.count("History Customer ") == 25
        for index in range(1, 26):
            assert f"History Customer {index}" in text
        assert "History Customer 0" not in text


def test_pending_quote_must_be_accepted_before_opening(temp_db):
    client = temp_db.test_client()
    creator = _create_employee_user("creator")
    viewer = _create_employee_user("viewer")

    quote = _create_quote(client, creator.display_name, "Blocked Customer")
    _set_quote_status(quote["id"], "pending_approval")

    _login_client(client, viewer)
    blocked = client.get(f"/employee/quote-entry?quote_id={quote['id']}")
    assert blocked.status_code == 302
    assert blocked.headers["Location"].endswith("/employee/dashboard")

    client.post(f"/employee/quotes/{quote['id']}/accept")
    opened = client.get(f"/employee/quote-entry?quote_id={quote['id']}")
    assert opened.status_code == 200
    assert "Quote Form" in opened.get_data(as_text=True)


def test_pending_order_must_be_accepted_before_opening(temp_db):
    client = temp_db.test_client()
    creator = _create_employee_user("creator")
    viewer = _create_employee_user("viewer")

    quote = _create_quote(client, creator.display_name, "Blocked Order Customer")
    _set_quote_status(quote["id"], "pending_approval")

    _login_client(client, viewer)
    blocked = client.get(f"/order-form?quote_id={quote['id']}")
    assert blocked.status_code == 403
    assert "Accept the pending order before opening it." in blocked.get_data(as_text=True)

    _assign_quote(quote["id"], viewer.id)
    opened = client.get(f"/order-form?quote_id={quote['id']}")
    assert opened.status_code == 200
    assert "Order Form" in opened.get_data(as_text=True)


def test_hold_keeps_order_pending_and_saves_order_form(temp_db):
    client = temp_db.test_client()
    creator = _create_employee_user("creator")
    reviewer = _create_employee_user("reviewer")
    quote = _create_quote(client, creator.display_name, "Hold Customer")
    _set_quote_status(quote["id"], "pending_approval")
    _assign_quote(quote["id"], reviewer.id)

    _login_client(client, reviewer)
    response = client.post(
        f"/api/quotes/{quote['id']}/order/hold",
        json={"order_form": {"parts": [{"part_number": "CHECK-PRICE"}]}},
    )

    assert response.status_code == 200
    assert response.get_json()["quote"]["status"] == "pending_approval"
    with get_session() as session:
        saved = session.get(Quote, quote["id"])
        assert saved.status == "pending_approval"
        assert saved.assigned_employee_user_id == reviewer.id
        assert saved.order_form_snapshot["parts"][0]["part_number"] == "CHECK-PRICE"


def test_accepted_quote_stays_visible_to_claimer_but_hidden_from_others(temp_db):
    """A claimed quote stays in the claimer's pending queue but leaves the unclaimed queue for everyone else."""
    client = temp_db.test_client()
    creator = _create_employee_user("creator")
    claimer = _create_employee_user("claimer")
    other = _create_employee_user("other")

    quote = _create_quote(client, creator.display_name, "Claim Customer")
    _set_quote_status(quote["id"], "pending_approval")

    _login_client(client, claimer)
    accept_resp = client.post(f"/employee/quotes/{quote['id']}/accept")
    assert accept_resp.status_code == 200

    # Claimer's own dashboard still shows the quote until it is actually approved.
    dash_resp = client.get("/employee/dashboard")
    assert dash_resp.status_code == 200
    text = dash_resp.get_data(as_text=True)
    assert "Claim Customer" in text

    # A different employee no longer sees it in their unclaimed queue.
    _login_client(client, other)
    dash_resp = client.get("/employee/dashboard")
    assert dash_resp.status_code == 200
    text = dash_resp.get_data(as_text=True)
    assert "Claim Customer" not in text
    assert "No quotes awaiting approval." in text


def test_viewing_pending_quote_does_not_claim_or_change_status(temp_db):
    """Merely opening/viewing a pending quote leaves its status and assignment untouched."""
    client = temp_db.test_client()
    creator = _create_employee_user("creator")
    viewer = _create_employee_user("viewer")

    quote = _create_quote(client, creator.display_name, "View Customer")
    _set_quote_status(quote["id"], "pending_approval")

    _login_client(client, viewer)
    blocked = client.get(f"/employee/quote-entry?quote_id={quote['id']}")
    assert blocked.status_code == 302

    with get_session() as session:
        row = session.get(Quote, quote["id"])
        assert row.status == "pending_approval"
        assert row.assigned_employee_user_id is None


def test_unrelated_pending_quotes_remain_after_accept(temp_db):
    """Accepting one pending quote does not hide other pending quotes from eligible employees."""
    client = temp_db.test_client()
    creator = _create_employee_user("creator")
    claimer = _create_employee_user("claimer")
    other = _create_employee_user("other")

    first = _create_quote(client, creator.display_name, "First Customer")
    _set_quote_status(first["id"], "pending_approval")
    second = _create_quote(client, creator.display_name, "Second Customer")
    _set_quote_status(second["id"], "pending_approval")

    _login_client(client, claimer)
    accept_resp = client.post(f"/employee/quotes/{first['id']}/accept")
    assert accept_resp.status_code == 200

    _login_client(client, other)
    dash_resp = client.get("/employee/dashboard")
    assert dash_resp.status_code == 200
    text = dash_resp.get_data(as_text=True)
    assert "First Customer" not in text
    assert "Second Customer" in text


def test_unchanged_pending_quote_not_in_order_history(temp_db):
    """An untouched pending quote never appears in any employee's My Order History."""
    client = temp_db.test_client()
    creator = _create_employee_user("creator")
    other = _create_employee_user("other")

    quote = _create_quote(client, creator.display_name, "Pending History Customer")
    _set_quote_status(quote["id"], "pending_approval")

    for employee in (creator, other):
        _login_client(client, employee)
        resp = client.get("/employee_order_history/employee_order_history.html")
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert "Pending History Customer" not in text


def test_accepted_then_approved_quote_appears_in_claimer_history(temp_db):
    """A quote accepted by one employee and later approved shows in that employee's history."""
    client = temp_db.test_client()
    creator = _create_employee_user("creator")
    claimer = _create_employee_user("claimer")

    quote = _create_quote(client, creator.display_name, "Claimed Approved Customer")
    _set_quote_status(quote["id"], "pending_approval")

    _login_client(client, claimer)
    accept_resp = client.post(f"/employee/quotes/{quote['id']}/accept")
    assert accept_resp.status_code == 200

    _set_quote_status(quote["id"], "approved")

    resp = client.get("/employee_order_history/employee_order_history.html")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "Claimed Approved Customer" in text
    assert quote["quote_number"] in text


@pytest.mark.parametrize("access_level", ["standard", "admin"])
def test_approved_order_leaves_pending_dashboard_queue(temp_db, access_level):
    client = temp_db.test_client()
    creator = _create_employee_user("creator")
    approver = _create_employee_user(f"approver-{access_level}", access_level=access_level)

    quote = _create_quote(client, creator.display_name, f"Approved {access_level} Customer")
    _set_quote_status(quote["id"], "pending_approval")
    _assign_quote(quote["id"], approver.id)

    _login_client(client, approver)
    approval = client.post(
        f"/api/quotes/{quote['id']}/order/approve",
        json={"order_form": {"order_number": f"J-{access_level}"}},
    )
    assert approval.status_code == 200
    assert approval.get_json()["quote"]["status"] == "approved"

    dashboard = client.get("/employee/dashboard")
    assert dashboard.status_code == 200
    pending_section = dashboard.get_data(as_text=True).split(
        "<h2>Pending Approvals</h2>", 1
    )[1].split("</section>", 1)[0]
    assert f"Approved {access_level} Customer" not in pending_section
    assert quote["quote_number"] not in pending_section


def test_created_approved_quote_appears_in_creator_history(temp_db):
    """A quote created by an employee and later approved remains in that employee's history."""
    client = temp_db.test_client()
    creator = _create_employee_user("creator")

    quote = _create_quote(client, creator.display_name, "Created Approved Customer")
    _set_quote_status(quote["id"], "approved")

    _login_client(client, creator)
    resp = client.get("/employee_order_history/employee_order_history.html")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "Created Approved Customer" in text
    assert quote["quote_number"] in text


def test_accepted_unordered_quote_stays_pending_and_is_quote_history_only(temp_db):
    """Accepting a quote without opening the order form keeps it in limbo."""
    client = temp_db.test_client()
    creator = _create_employee_user("creator")
    reviewer = _create_employee_user("reviewer")

    quote = _create_quote(client, creator.display_name, "Accepted But Unordered")
    _set_quote_status(quote["id"], "pending_approval")

    _login_client(client, reviewer)
    accept_response = client.post(f"/employee/quotes/{quote['id']}/accept")
    assert accept_response.status_code == 200

    dashboard = client.get("/employee/dashboard")
    assert dashboard.status_code == 200
    dashboard_text = dashboard.get_data(as_text=True)
    assert "Accepted But Unordered" in dashboard_text
    assert "Pending Approvals" in dashboard_text

    quote_history = client.get("/employee_quote_history/employee_quote_history.html")
    assert quote_history.status_code == 200
    assert "Accepted But Unordered" in quote_history.get_data(as_text=True)

    order_history = client.get("/employee_order_history/employee_order_history.html")
    assert order_history.status_code == 200
    assert "Accepted But Unordered" not in order_history.get_data(as_text=True)


def test_admin_dashboard_renders_pending_approval_queue(temp_db):
    client = temp_db.test_client()
    creator = _create_employee_user("creator")
    admin = _create_employee_user("admin", access_level="admin")
    quote = _create_quote(client, creator.display_name, "Admin Pending Customer")
    _set_quote_status(quote["id"], "pending_approval")
    _assign_quote(quote["id"], admin.id)

    _login_client(client, admin)
    response = client.get("/employee/dashboard")
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "Pending Approvals" in text
    assert "Admin Pending Customer" in text
    pending_section = text.split("<h2>Pending Approvals</h2>", 1)[1].split(
        "</section>", 1
    )[0]
    assert "<td>Quote</td>" in pending_section
    assert "<td>Pending Approval</td>" in pending_section
    assert "<td>Accepted</td>" not in pending_section
    assert "<td>Pending</td>" not in pending_section


@pytest.mark.parametrize("access_level, dashboard_template_marker", [
    ("standard", 'href="/order-form?quote_id='),
    ("admin", 'href="/order-form?quote_id='),
])
def test_pending_approval_open_link_uses_order_form(temp_db, access_level, dashboard_template_marker):
    client = temp_db.test_client()
    creator = _create_employee_user("creator")
    employee = _create_employee_user(f"reviewer-{access_level}", access_level=access_level)
    quote = _create_quote(client, creator.display_name, f"Order Form {access_level} Customer")
    _set_quote_status(quote["id"], "pending_approval")
    _assign_quote(quote["id"], employee.id)

    _login_client(client, employee)
    response = client.get("/employee/dashboard")

    assert response.status_code == 200
    assert f'{dashboard_template_marker}{quote["id"]}' in response.get_data(as_text=True)


def test_denied_order_is_stored_and_sorted_last_in_histories(temp_db):
    client = temp_db.test_client()
    employee = _create_employee_user("employee")

    approved = _create_quote(client, employee.display_name, "Approved Customer")
    _set_quote_status(approved["id"], "approved")
    denied = _create_quote(client, employee.display_name, "Denied Customer")
    _set_quote_status(denied["id"], "pending_approval")
    _assign_quote(denied["id"], employee.id)

    order_response = client.post(
        f"/api/quotes/{denied['id']}/order",
        json={},
        headers=_headers(employee.display_name),
    )
    assert order_response.status_code == 200

    deny_response = client.post(
        f"/api/quotes/{denied['id']}/order/deny",
        json={},
        headers=_headers(employee.display_name),
    )
    assert deny_response.status_code == 200
    assert deny_response.get_json()["quote"]["status"] == "denied"

    with get_session() as session:
        quote = session.get(Quote, denied["id"])
        order = session.execute(
            select(Order).where(Order.quote_id == denied["id"])
        ).scalar_one()
        assert quote.status == "denied"
        assert order.status == "denied"

    _login_client(client, employee)
    for path in ("/employee_order_history/employee_order_history.html", "/employee_quote_history/employee_quote_history.html"):
        response = client.get(path)
        assert response.status_code == 200
        text = response.get_data(as_text=True)
        assert text.index("Approved Customer") < text.index("Denied Customer")
