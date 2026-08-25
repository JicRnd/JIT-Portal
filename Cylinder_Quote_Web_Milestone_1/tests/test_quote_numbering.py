from __future__ import annotations

import re
from datetime import datetime

import pytest

from app.db import get_session, init_db
from app.models_db import Quote, User
from app.quote_numbering import generate_quote_number


QUOTE_ID_RE = re.compile(r"^[A-Z]\d{10}$")


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the global engine at a temporary SQLite file and create tables."""
    db_path = tmp_path / "test_quote_numbers.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("ACCOUNTS_DATABASE_PATH", str(tmp_path / "test_quote_numbers_accounts.db"))

    import app.db as db_mod

    db_mod._engine = None
    db_mod._accounts_engine = None
    db_mod._Session = None
    init_db()
    yield db_path
    db_mod._engine = None
    db_mod._accounts_engine = None
    db_mod._Session = None


def test_generate_customer_timestamp_format(temp_db):
    with get_session() as session:
        number = generate_quote_number(session, "AC Hotels")

    assert QUOTE_ID_RE.match(number)
    assert number.startswith("A")
    assert len(number) == 11


def test_generate_uses_customer_initial(temp_db):
    with get_session() as session:
        number = generate_quote_number(session, "Motion Industries")

    assert number.startswith("M")
    assert QUOTE_ID_RE.match(number)


def test_generate_uses_first_letter_of_spaced_name(temp_db):
    with get_session() as session:
        number = generate_quote_number(session, "A C")

    assert number.startswith("A")
    assert QUOTE_ID_RE.match(number)


def test_generate_unique_when_same_minute_already_used(temp_db):
    with get_session() as session:
        user = User(display_name="num-tester", is_active=True)
        session.add(user)
        session.flush()

        first = generate_quote_number(session, "Acme")
        session.add(
            Quote(
                quote_number=first,
                status="draft",
                pricing_version="v1.2",
                created_by_user_id=user.id,
                created_at=datetime.now(),
            )
        )
        session.flush()

        second = generate_quote_number(session, "Acme")

    assert first != second
    assert first.startswith("A")
    assert second.startswith("A")
    assert QUOTE_ID_RE.match(first)
    assert QUOTE_ID_RE.match(second)
