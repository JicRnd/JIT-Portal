from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

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
    db_path = tmp_path / "test_quote_history.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("ACCOUNTS_DATABASE_PATH", str(tmp_path / "test_quote_history_accounts.db"))
    monkeypatch.setenv("QUOTES_DATABASE_PATH", str(tmp_path / "test_quote_history_quotes.db"))
    monkeypatch.setenv("ORDERS_DATABASE_PATH", str(tmp_path / "test_quote_history_orders.db"))

    import app.db as db_mod

    db_mod._engine = None
    db_mod._Session = None
    init_db()

    app = create_app()
    app.testing = True
    yield app

    db_mod._engine = None
    db_mod._Session = None


def _headers(user: str = "test-user"):
    return {"X-User-Name": user}


def _create_quote(client, user, customer_name, **overrides):
    payload = sample_payload()
    payload["customer_name"] = customer_name
    payload.update(overrides)
    resp = client.post("/api/quotes", json=payload, headers=_headers(user))
    assert resp.status_code == 200
    return resp.get_json()["quote"]


def _set_quote_meta(quote_id, *, status=None, created_at=None):
    with get_session() as session:
        quote = session.get(Quote, quote_id)
        if status is not None:
            quote.status = status
        if created_at is not None:
            quote.created_at = created_at
        session.commit()


def _set_quote_approved_at(quote_id, approved_at):
    with get_session() as session:
        quote = session.get(Quote, quote_id)
        quote.approved_at = approved_at
        session.commit()


def _login_client(client, user: User):
    with client.session_transaction() as session:
        session["user_id"] = user.id
        session["role"] = user.role


def _seed_quotes(client):
    """Create a small set of quotes with varied metadata for search tests."""
    today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)

    q1 = _create_quote(client, "alice", "Acme Corp", rod_style=1)
    _set_quote_meta(q1["id"], status="draft", created_at=today - timedelta(days=5))

    q2 = _create_quote(client, "bob", "Beta LLC", rod_style=2)
    _set_quote_meta(q2["id"], status="sent", created_at=today - timedelta(days=3))

    q3 = _create_quote(client, "alice", "Gamma Inc", rod_style=2)
    _set_quote_meta(q3["id"], status="approved", created_at=today - timedelta(days=1))

    q4 = _create_quote(client, "bob", "Acme Subsidiary", rod_style=1)
    _set_quote_meta(q4["id"], status="draft", created_at=today)

    q5 = _create_quote(client, "alice", "Delta Co", rod_style=1)
    _set_quote_meta(q5["id"], status="draft", created_at=today)

    return [q1, q2, q3, q4, q5]


def test_list_quotes_no_filters_is_paginated(temp_db):
    client = temp_db.test_client()
    _seed_quotes(client)

    resp = client.get("/api/quotes")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 25
    assert len(data["results"]) == 5

    # List rows are lightweight.
    row = data["results"][0]
    assert "id" in row
    assert "quote_number" in row
    assert "status" in row
    assert "model_code" in row
    assert "customer_name" in row
    assert "created_by" in row
    assert "created_at" in row
    assert "revision" in row
    assert "quote_net_each" in row
    assert "cylinder_inputs_snapshot" not in row
    assert "price_breakdown_snapshot" not in row
    assert "manual_line_items" not in row


def test_approved_order_is_saved_and_visible_to_approver_history(temp_db):
    client = temp_db.test_client()
    approver = User(
        display_name="Approving Employee",
        role="employee",
        access_level="admin",
        is_active=True,
    )
    with get_session() as session:
        session.add(approver)
        session.commit()
        session.refresh(approver)

    quote = _create_quote(client, "creator", "Approved Customer")
    _set_quote_meta(quote["id"], status="pending_approval")
    _login_client(client, approver)
    response = client.post(
        f"/api/quotes/{quote['id']}/order/approve",
        json={"order_form": {"order_number": "JTEST-001"}},
    )

    assert response.status_code == 200
    with get_session() as session:
        saved_quote = session.get(Quote, quote["id"])
        saved_order = session.query(Order).filter_by(quote_id=quote["id"]).one()
        assert saved_quote.status == "approved"
        assert saved_quote.approved_by_user_id == approver.id
        assert saved_order is not None
        assert saved_order.status == "approved"
        assert saved_order.order_form_snapshot["order_number"] == "JTEST-001"

    history = client.get("/employee_order_history/employee_order_history.html")
    assert history.status_code == 200
    assert "JTEST-001" in history.get_data(as_text=True)


def test_employee_order_history_search_scans_all_orders(temp_db):
    client = temp_db.test_client()
    approver = User(
        display_name="Approving Employee",
        role="employee",
        access_level="admin",
        is_active=True,
    )
    searcher = User(
        display_name="Searching Employee",
        role="employee",
        access_level="employee",
        is_active=True,
    )
    with get_session() as session:
        session.add_all([approver, searcher])
        session.commit()
        session.refresh(approver)
        session.refresh(searcher)

    quote = _create_quote(client, "creator", "Searchable Customer")
    _set_quote_meta(quote["id"], status="pending_approval")
    _login_client(client, approver)
    approved = client.post(
        f"/api/quotes/{quote['id']}/order/approve",
        json={"order_form": {"order_number": "JSEARCH-001"}},
    )
    assert approved.status_code == 200

    _login_client(client, searcher)
    history = client.get("/employee_order_history/employee_order_history.html?q=JSEARCH")

    assert history.status_code == 200
    assert "JSEARCH-001" in history.get_data(as_text=True)


def test_employee_order_history_suggests_from_any_snapshot_value(temp_db):
    client = temp_db.test_client()
    employee = User(
        display_name="Searching Employee",
        role="employee",
        access_level="employee",
        is_active=True,
    )
    with get_session() as session:
        session.add(employee)
        session.commit()
        session.refresh(employee)

    quote = _create_quote(client, "creator", "Snapshot Customer")
    _set_quote_meta(quote["id"], status="pending_approval")
    _login_client(client, employee)
    approved = client.post(
        f"/api/quotes/{quote['id']}/order/approve",
        json={
            "order_form": {
                "order_number": "JFULL-001",
                "parts": [{"description": "ZX-UNIQUE-PART"}],
            }
        },
    )
    assert approved.status_code == 200

    too_short = client.get("/employee/order-history-search?q=Z")
    assert too_short.status_code == 200
    assert too_short.get_json()["results"] == []

    suggestions = client.get("/employee/order-history-search?q=ZX")
    assert suggestions.status_code == 200
    assert suggestions.get_json()["results"] == [{
        "order_number": "JFULL-001",
        "customer": "",
        "model_code": "",
    }]


def test_employee_order_history_ignores_assigned_and_quoted_by_values(temp_db):
    client = temp_db.test_client()
    quote = _create_quote(client, "creator", "Visible Customer")
    employee = User(
        display_name="Searching Employee",
        role="employee",
        access_level="employee",
        is_active=True,
    )
    with get_session() as session:
        session.add(employee)
        session.add(Order(
            quote_id=quote["id"],
            quote_number="JIGNORE-001",
            status="approved",
            order_form_snapshot={
                "order_number": "JIGNORE-001",
                "assigned_to": "ONLY-ASSIGNED-VALUE",
                "quoted_by": "ONLY-QUOTED-VALUE",
                "ordered_by": "ONLY-ORDERED-BY-VALUE",
                "quote_form_edits": {
                    "text_nodes": [{"value": "ONLY-QUOTE-FORM-VALUE"}],
                    "inputs": {"pv_customer_name": "VISIBLE-CUSTOMER-DATA"},
                },
                "description": "VISIBLE-ORDER-DATA",
            },
        ))
        session.commit()
        session.refresh(employee)

    _login_client(client, employee)

    ignored = client.get("/employee/order-history-search?q=ONLY")
    assert ignored.status_code == 200
    assert ignored.get_json()["results"] == []

    visible = client.get("/employee/order-history-search?q=VISIBLE")
    assert visible.status_code == 200
    assert visible.get_json()["results"][0]["order_number"] == "JIGNORE-001"


def test_employee_quote_history_suggests_from_quote_database(temp_db):
    client = temp_db.test_client()
    employee = User(
        display_name="Searching Employee",
        role="employee",
        access_level="employee",
        is_active=True,
    )
    with get_session() as session:
        session.add(employee)
        session.commit()
        session.refresh(employee)

    quote = _create_quote(client, "creator", "Quote Search Customer")
    _login_client(client, employee)

    too_short = client.get("/employee_quote_history_search?q=Q")
    assert too_short.status_code == 200
    assert too_short.get_json()["results"] == []

    suggestions = client.get("/employee_quote_history_search?q=Qu")
    assert suggestions.status_code == 200
    assert suggestions.get_json()["results"] == [{
        "id": quote["id"],
        "quote_number": quote["quote_number"],
        "customer": "Quote Search Customer",
        "model_code": quote["model_code"],
    }]


def test_employee_quote_history_lists_pending_before_approved_newest_first(temp_db):
    client = temp_db.test_client()
    employee = User(
        display_name="History Employee",
        role="employee",
        access_level="employee",
        is_active=True,
    )
    with get_session() as session:
        session.add(employee)
        session.commit()
        session.refresh(employee)

    pending_old = _create_quote(client, "creator", "Pending Old")
    _set_quote_meta(
        pending_old["id"], status="pending_approval", created_at=datetime(2026, 9, 10)
    )
    pending_new = _create_quote(client, "creator", "Pending New")
    _set_quote_meta(
        pending_new["id"], status="accepted", created_at=datetime(2026, 9, 12)
    )
    approved_old = _create_quote(client, "creator", "Approved Old")
    _set_quote_meta(
        approved_old["id"], status="approved", created_at=datetime(2026, 9, 11)
    )
    _set_quote_approved_at(approved_old["id"], datetime(2026, 9, 14))
    approved_new = _create_quote(client, "creator", "Approved New")
    _set_quote_meta(
        approved_new["id"], status="approved", created_at=datetime(2026, 9, 13)
    )
    _set_quote_approved_at(approved_new["id"], datetime(2026, 9, 15))

    _login_client(client, employee)
    response = client.get("/employee_quote_history/employee_quote_history.html")

    assert response.status_code == 200
    text = response.get_data(as_text=True)
    order = [
        text.index("Pending New"),
        text.index("Pending Old"),
        text.index("Approved New"),
        text.index("Approved Old"),
    ]
    assert order == sorted(order)


def test_employee_quote_history_delete_soft_deletes_quote(temp_db):
    client = temp_db.test_client()
    employee = User(
        display_name="Deleting Employee",
        role="employee",
        access_level="employee",
        is_active=True,
    )
    with get_session() as session:
        session.add(employee)
        session.commit()
        session.refresh(employee)

    quote = _create_quote(client, "creator", "Delete Quote Customer")
    _login_client(client, employee)

    response = client.post(
        f"/employee_quote_history/{quote['id']}/delete",
    )

    assert response.status_code == 302
    with get_session() as session:
        deleted_quote = session.get(Quote, quote["id"])
        assert deleted_quote.status == "canceled"
        assert deleted_quote.deleted_by_user_id == employee.id
        assert deleted_quote.deleted_at is not None


def test_employee_order_history_delete_moves_order_to_trash_and_restores(temp_db):
    client = temp_db.test_client()
    quote = _create_quote(client, "creator", "Delete Order Customer")
    employee = User(
        display_name="Deleting Employee",
        role="employee",
        access_level="employee",
        is_active=True,
    )
    with get_session() as session:
        session.add(employee)
        session.add(Order(
            quote_id=quote["id"],
            quote_number="JDELETE-001",
            status="approved",
            order_form_snapshot={"order_number": "JDELETE-001"},
        ))
        session.commit()
        session.refresh(employee)
        order = session.query(Order).filter_by(quote_id=quote["id"]).one()
        order_id = order.id

    _login_client(client, employee)
    response = client.post(f"/employee/order-history/{order_id}/delete")

    assert response.status_code == 302
    with get_session() as session:
        deleted_order = session.get(Order, order_id)
        assert deleted_order is not None
        assert deleted_order.status == "canceled"
        assert deleted_order.deleted_status == "approved"
        assert deleted_order.deleted_by_user_id == employee.id
        assert deleted_order.deleted_at is not None

    trash = client.get("/employee_order_history/employee_order_history.html?trash=1")
    assert trash.status_code == 200
    assert "JDELETE-001" in trash.get_data(as_text=True)

    restored = client.post(f"/employee/order-history/{order_id}/restore")
    assert restored.status_code == 302
    with get_session() as session:
        restored_order = session.get(Order, order_id)
        assert restored_order.status == "approved"
        assert restored_order.deleted_status is None
        assert restored_order.deleted_at is None


def test_employee_quote_history_delete_moves_quote_to_trash_and_restores(temp_db):
    client = temp_db.test_client()
    employee = User(
        display_name="Restoring Employee",
        role="employee",
        access_level="employee",
        is_active=True,
    )
    with get_session() as session:
        session.add(employee)
        session.commit()
        session.refresh(employee)

    quote = _create_quote(client, "creator", "Restore Quote Customer")
    _set_quote_meta(quote["id"], status="draft")
    _login_client(client, employee)

    deleted = client.post(f"/employee_quote_history/{quote['id']}/delete")
    assert deleted.status_code == 302

    active = client.get("/employee_quote_history/employee_quote_history.html")
    assert "Restore Quote Customer" not in active.get_data(as_text=True)
    trash = client.get("/employee_quote_history/employee_quote_history.html?trash=1")
    assert "Restore Quote Customer" in trash.get_data(as_text=True)

    restored = client.post(f"/employee_quote_history/{quote['id']}/restore")
    assert restored.status_code == 302
    with get_session() as session:
        restored_quote = session.get(Quote, quote["id"])
        assert restored_quote.status == "draft"
        assert restored_quote.deleted_status is None
        assert restored_quote.deleted_at is None


def test_employee_quote_history_ignores_attribution_and_has_no_result_cap(temp_db):
    client = temp_db.test_client()
    employee = User(
        display_name="Searching Employee",
        role="employee",
        access_level="employee",
        is_active=True,
    )
    with get_session() as session:
        session.add(employee)
        session.commit()
        session.refresh(employee)

    first_quote = _create_quote(client, "creator", "Visible Quote Customer")
    with get_session() as session:
        quote = session.get(Quote, first_quote["id"])
        quote.order_form_snapshot = {
            "assigned_to": "ONLY-ASSIGNED-VALUE",
            "quoted_by": "ONLY-QUOTED-VALUE",
            "created_by": "ONLY-CREATED-VALUE",
            "description": "VISIBLE-QUOTE-DATA",
        }
        session.commit()

    with get_session() as session:
        session.add_all([
            Quote(
                quote_number=f"TEST-COMMON-{index:02d}",
                status="draft",
                customer_name=f"Common Quote Customer {index}",
                created_by_user_id=1,
                created_at=datetime.utcnow() - timedelta(seconds=index),
            )
            for index in range(29)
        ])
        session.commit()

    _login_client(client, employee)

    ignored = client.get("/employee_quote_history_search?q=ONLY")
    assert ignored.status_code == 200
    assert ignored.get_json()["results"] == []

    visible = client.get("/employee_quote_history_search?q=VISIBLE")
    assert visible.status_code == 200
    assert len(visible.get_json()["results"]) == 1

    uncapped = client.get("/employee_quote_history_search?q=Common")
    assert uncapped.status_code == 200
    assert len(uncapped.get_json()["results"]) == 29


def test_employee_quote_history_does_not_search_order_attribution(temp_db):
    client = temp_db.test_client()
    employee = User(
        display_name="Searching Employee",
        role="employee",
        access_level="employee",
        is_active=True,
    )
    with get_session() as session:
        session.add(employee)
        session.commit()
        session.refresh(employee)

    unrelated = _create_quote(client, "creator", "Unrelated Customer")
    visible = _create_quote(client, "creator", "Kane Whiteside")
    with get_session() as session:
        unrelated_quote = session.get(Quote, unrelated["id"])
        unrelated_quote.order_form_snapshot = {
            "ordered_by": "Kane Whiteside",
            "quote_form_edits": {
                "textNodes": [{"value": "Kane Whiteside"}],
            },
        }
        session.commit()

    _login_client(client, employee)
    response = client.get("/employee_quote_history_search?q=kane")

    assert response.status_code == 200
    results = response.get_json()["results"]
    assert [result["id"] for result in results] == [visible["id"]]


def test_filter_by_quote_number_partial(temp_db):
    client = temp_db.test_client()
    quotes = _seed_quotes(client)

    # Each quote number is DEV-YYYY-NNNNN; search for the unique sequence.
    target = quotes[0]["quote_number"]
    unique_fragment = target.split("-")[-1]
    resp = client.get(f"/api/quotes?quote_number={unique_fragment}")
    results = resp.get_json()["results"]
    assert len(results) == 1
    assert results[0]["quote_number"] == target


def test_filter_by_customer_name_case_insensitive(temp_db):
    client = temp_db.test_client()
    _seed_quotes(client)

    resp = client.get("/api/quotes?customer_name=ACME")
    results = resp.get_json()["results"]
    assert len(results) == 2
    assert {r["customer_name"] for r in results} == {"Acme Corp", "Acme Subsidiary"}

    resp = client.get("/api/quotes?customer_name=subsidiary")
    results = resp.get_json()["results"]
    assert len(results) == 1
    assert results[0]["customer_name"] == "Acme Subsidiary"


def test_filter_by_model_code(temp_db):
    client = temp_db.test_client()
    quotes = _seed_quotes(client)

    style2_code = quotes[1]["model_code"]
    resp = client.get(f"/api/quotes?model_code={style2_code}")
    results = resp.get_json()["results"]
    assert len(results) == 2
    assert all(r["model_code"] == style2_code for r in results)


def test_filter_by_status(temp_db):
    client = temp_db.test_client()
    _seed_quotes(client)

    resp = client.get("/api/quotes?status=sent")
    results = resp.get_json()["results"]
    assert len(results) == 1
    assert results[0]["customer_name"] == "Beta LLC"


def test_filter_by_created_by(temp_db):
    client = temp_db.test_client()
    _seed_quotes(client)

    resp = client.get("/api/quotes?created_by=ALICE")
    results = resp.get_json()["results"]
    assert len(results) == 3
    assert all(r["created_by"] == "alice" for r in results)

    resp = client.get("/api/quotes?created_by=bob")
    results = resp.get_json()["results"]
    assert len(results) == 2
    assert all(r["created_by"] == "bob" for r in results)


def test_filter_by_date_range(temp_db):
    client = temp_db.test_client()
    quotes = _seed_quotes(client)

    today = datetime.utcnow().date().isoformat()
    five_days_ago = (datetime.utcnow() - timedelta(days=5)).date().isoformat()
    four_days_ago = (datetime.utcnow() - timedelta(days=4)).date().isoformat()

    resp = client.get(f"/api/quotes?date_from={today}")
    results = resp.get_json()["results"]
    assert len(results) == 2
    assert {r["customer_name"] for r in results} == {"Acme Subsidiary", "Delta Co"}

    resp = client.get(f"/api/quotes?date_to={four_days_ago}")
    results = resp.get_json()["results"]
    assert len(results) == 1
    assert results[0]["id"] == quotes[0]["id"]

    resp = client.get(f"/api/quotes?date_from={five_days_ago}&date_to={four_days_ago}")
    results = resp.get_json()["results"]
    assert len(results) == 1
    assert results[0]["id"] == quotes[0]["id"]


def test_pagination_page_size_capped_and_invalid_defaults(temp_db):
    client = temp_db.test_client()
    _seed_quotes(client)

    resp = client.get("/api/quotes?page_size=200")
    data = resp.get_json()
    assert data["page_size"] == 100
    assert len(data["results"]) == 5

    resp = client.get("/api/quotes?page=2&page_size=2")
    data = resp.get_json()
    assert data["page"] == 2
    assert data["page_size"] == 2
    assert len(data["results"]) == 2

    resp = client.get("/api/quotes?page=-1&page_size=abc")
    data = resp.get_json()
    assert data["page"] == 1
    assert data["page_size"] == 25
    assert data["total"] == 5


def test_duplicate_quote_creates_new_quote_copy(temp_db):
    client = temp_db.test_client()
    source = _create_quote(
        client,
        "alice",
        "Original Customer",
        comments="Keep me",
        manual_line_items=[
            {
                "reference_part_number": "M-001",
                "description": "Manual item",
                "quantity": 2,
                "unit_price": "9.99",
                "internal_note": "note",
                "show_on_customer_quote": True,
            }
        ],
    )

    # Mark the source as emailed/approved so we can verify those are not copied.
    emailed_at = datetime.utcnow() - timedelta(days=1)
    approved_at = datetime.utcnow() - timedelta(hours=1)
    with get_session() as session:
        quote = session.get(Quote, source["id"])
        quote.emailed_at = emailed_at
        quote.approved_at = approved_at
        session.commit()

    resp = client.post(f"/api/quotes/{source['id']}/duplicate", headers=_headers("bob"))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True

    duplicate = data["quote"]
    assert duplicate["id"] != source["id"]
    assert duplicate["quote_number"] != source["quote_number"]
    assert duplicate["status"] == "new"
    assert duplicate["revision"] == 1
    assert duplicate["created_by"] == "bob"
    assert duplicate["model_code"] == source["model_code"]
    assert duplicate["cylinder_inputs_snapshot"] == source["cylinder_inputs_snapshot"]
    assert duplicate["price_breakdown_snapshot"] == source["price_breakdown_snapshot"]
    assert duplicate["customer_name"] == "Original Customer"
    assert duplicate["comments"] == "Keep me"

    # The duplicate must not carry over emailed/approved timestamps.
    with get_session() as session:
        source_row = session.get(Quote, source["id"])
        duplicate_row = session.get(Quote, duplicate["id"])
        assert source_row.emailed_at is not None
        assert source_row.approved_at is not None
        assert duplicate_row.emailed_at is None
        assert duplicate_row.approved_at is None

    assert len(duplicate["manual_line_items"]) == 1
    item = duplicate["manual_line_items"][0]
    assert item["description"] == "Manual item"
    assert Decimal(item["quantity"]) == Decimal("2")
    assert Decimal(item["unit_price"]) == Decimal("9.99")
    assert Decimal(item["extended_price"]) == Decimal("19.98")
    assert item["reference_part_number"] == "M-001"


def test_duplicate_nonexistent_quote_returns_404(temp_db):
    client = temp_db.test_client()
    resp = client.post("/api/quotes/999999/duplicate", headers=_headers("alice"))
    assert resp.status_code == 404
    assert resp.get_json()["ok"] is False
