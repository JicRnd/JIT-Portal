from __future__ import annotations

import pytest

from sqlalchemy import select

from app import create_app
from app.db import get_session, init_db
from app.models_db import Quote, User


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

    import app.db as db_mod

    db_mod._engine = None
    db_mod._accounts_engine = None
    db_mod._Session = None
    init_db()

    app = create_app()
    app.testing = True
    yield app

    db_mod._engine = None
    db_mod._accounts_engine = None
    db_mod._Session = None


def _headers(user: str = "creator"):
    return {"X-User-Name": user}


def _create_employee_user(display_name: str) -> User:
    with get_session() as session:
        user = User(display_name=display_name, role="employee", is_active=True)
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


def _unassigned_pending_count() -> int:
    with get_session() as session:
        return session.execute(
            select(Quote)
            .where(
                Quote.status == "pending_approval",
                Quote.assigned_employee_user_id.is_(None),
            )
        ).scalars().all().__len__()


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


def test_draft_quote_not_in_pending_queue(temp_db):
    """Draft quotes are not listed in the pending approval queue."""
    client = temp_db.test_client()
    employee = _create_employee_user("employee")
    quote = _create_quote(client, employee.display_name, "Draft Customer")
    assert quote["status"] == "draft"

    _login_client(client, employee)
    resp = client.get("/employee/dashboard")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "Pending Approvals" in text
    assert "No quotes awaiting approval." in text
    assert "Draft Customer" not in text


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
