from __future__ import annotations

import csv
import io

import pytest

try:
    import openpyxl
except ModuleNotFoundError:  # pragma: no cover
    openpyxl = None

from app import create_app
from app.db import get_session, init_db
from app.models_db import Customer


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the app at a temporary SQLite database and create tables."""
    db_path = tmp_path / "test_customer_bulk_import.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("ACCOUNTS_DATABASE_PATH", str(tmp_path / "test_customer_bulk_import_accounts.db"))
    monkeypatch.setenv("CONTACTS_DATABASE_PATH", str(tmp_path / "test_customer_bulk_import_contacts.db"))

    import app.db as db_mod

    db_mod._engine = None
    db_mod._accounts_engine = None
    db_mod._contacts_engine = None
    db_mod._Session = None
    init_db()

    app = create_app()
    app.testing = True
    yield app

    db_mod._engine = None
    db_mod._accounts_engine = None
    db_mod._contacts_engine = None
    db_mod._Session = None


def _headers(user: str = "test-user"):
    return {"X-User-Name": user}


def _csv_bytes(rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _xlsx_bytes(rows: list[list[str]]) -> bytes:
    if openpyxl is None:  # pragma: no cover
        pytest.skip("openpyxl is not installed")
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    for row in rows:
        worksheet.append(row)
    stream = io.BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return stream.read()


def _build_rows():
    return [
        ["Company or Contact", "Address", "City, State, Zip", "Phone", "Email"],
        ["Acme Cylinders", "123 Main St", "Springfield, IL 62701", "555-0100", "acme@example.com"],
        ["Beta LLC", "456 Oak Ave", "Madison, WI 53703", "", "beta@example.com"],
        ["", "789 Pine Rd", "Denver, CO 80202", "555-0200", ""],
        ["", "", "", "", ""],
    ]


def _assert_imported_customers():
    with get_session() as session:
        customers = session.query(Customer).order_by(Customer.id).all()
    assert len(customers) == 3

    acme = customers[0]
    assert acme.name == "Acme Cylinders"
    assert acme.address == "123 Main St"
    assert acme.city_state_zip == "Springfield, IL 62701"
    assert acme.phone == "555-0100"
    assert acme.email == "acme@example.com"

    beta = customers[1]
    assert beta.name == "Beta LLC"
    assert beta.address == "456 Oak Ave"
    assert beta.city_state_zip == "Madison, WI 53703"
    assert beta.phone is None
    assert beta.email == "beta@example.com"

    nameless = customers[2]
    assert nameless.name == ""
    assert nameless.address == "789 Pine Rd"
    assert nameless.city_state_zip == "Denver, CO 80202"
    assert nameless.phone == "555-0200"
    assert nameless.email is None


def test_bulk_import_csv(temp_db):
    client = temp_db.test_client()
    rows = _build_rows()
    resp = client.post(
        "/api/customers/bulk-import",
        data={"file": (io.BytesIO(_csv_bytes(rows)), "contacts.csv")},
        headers=_headers(),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["imported"] == 3
    assert data["skipped"] == 0
    _assert_imported_customers()


@pytest.mark.skipif(openpyxl is None, reason="openpyxl is not installed")
def test_bulk_import_xlsx(temp_db):
    client = temp_db.test_client()
    rows = _build_rows()
    resp = client.post(
        "/api/customers/bulk-import",
        data={"file": (io.BytesIO(_xlsx_bytes(rows)), "contacts.xlsx")},
        headers=_headers(),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["imported"] == 3
    assert data["skipped"] == 0
    _assert_imported_customers()


def test_bulk_import_requires_file(temp_db):
    client = temp_db.test_client()
    resp = client.post("/api/customers/bulk-import", data={}, headers=_headers())
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["ok"] is False
    assert "file" in data["error"].lower()


def test_bulk_import_rejects_unsupported_extension(temp_db):
    client = temp_db.test_client()
    resp = client.post(
        "/api/customers/bulk-import",
        data={"file": (io.BytesIO(b"not a spreadsheet"), "contacts.txt")},
        headers=_headers(),
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["ok"] is False
    assert "unsupported" in data["error"].lower()
