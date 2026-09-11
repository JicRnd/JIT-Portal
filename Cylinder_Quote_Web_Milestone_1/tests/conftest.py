from __future__ import annotations

import pytest

from app import db


@pytest.fixture(autouse=True)
def isolated_databases(tmp_path, monkeypatch):
    """Give every test using the shared DB layer isolated SQLite files."""
    database_paths = {
        "DATABASE_PATH": tmp_path / "app.db",
        "ACCOUNTS_DATABASE_PATH": tmp_path / "accounts.db",
        "QUOTES_DATABASE_PATH": tmp_path / "quotes.db",
        "ORDERS_DATABASE_PATH": tmp_path / "orders.db",
        "PRICING_DATABASE_PATH": tmp_path / "pricing.db",
    }
    for variable, path in database_paths.items():
        monkeypatch.setenv(variable, str(path))

    db.reset_engines()
    yield
    db.reset_engines()