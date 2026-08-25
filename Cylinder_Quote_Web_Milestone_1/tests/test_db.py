from __future__ import annotations

import pytest
from sqlalchemy import inspect

from app.current_user import DEFAULT_USER_NAME, get_or_create_current_user
from app.db import get_accounts_engine, get_engine, get_session, init_db
from app.models_db import User


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the global engine at a temporary SQLite file and create tables."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("ACCOUNTS_DATABASE_PATH", str(tmp_path / "test_accounts.db"))

    import app.db as db_mod

    db_mod._engine = None
    db_mod._accounts_engine = None
    db_mod._Session = None
    init_db()
    yield db_path
    db_mod._engine = None
    db_mod._accounts_engine = None
    db_mod._Session = None


def test_init_creates_tables(temp_db):
    engine = get_engine()
    table_names = inspect(engine).get_table_names()
    assert "quotes" in table_names
    assert "quote_number_sequences" in table_names

    accounts_table_names = inspect(get_accounts_engine()).get_table_names()
    assert "users" in accounts_table_names


def test_user_get_or_create_is_case_insensitive(temp_db):
    class FakeRequest:
        headers = {}
        is_json = False

    u1 = get_or_create_current_user(FakeRequest(), display_name="Alice")
    u1_id = u1.id

    u2 = get_or_create_current_user(FakeRequest(), display_name="alice")
    assert u2.id == u1_id

    u3 = get_or_create_current_user(FakeRequest(), display_name="BOB")
    u3_id = u3.id

    u4 = get_or_create_current_user(FakeRequest(), display_name="bob")
    assert u4.id == u3_id

    # Mixed case should be preserved on the first-created row.
    assert u1.display_name == "Alice"


def test_default_user_created_when_none_specified(temp_db):
    class FakeRequest:
        headers = {}
        is_json = False

    user = get_or_create_current_user(FakeRequest())
    assert user.display_name == DEFAULT_USER_NAME


def test_user_can_be_provided_by_header(temp_db):
    class FakeRequest:
        headers = {"X-User-Name": " quoting-user "}
        is_json = False

    user = get_or_create_current_user(FakeRequest())
    assert user.display_name == "quoting-user"


def test_user_can_be_provided_by_json_payload(temp_db):
    class FakeRequest:
        headers = {}
        is_json = True

        @staticmethod
        def get_json(silent=True):
            return {"current_user": "json-user"}

    user = get_or_create_current_user(FakeRequest())
    assert user.display_name == "json-user"
