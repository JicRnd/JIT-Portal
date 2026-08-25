"""Standalone migration: split cylinder_quote.db into three new SQLite files.

Reads the existing ``instance/cylinder_quote.db`` in read-only mode and creates:

* instance/Employee_Contacts.db
* instance/Quote.db
* instance/Order.db

The original database is never modified.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.models_split_db import (
    OrderBase,
    QuoteBase,
    EmployeeContactsBase,
    SplitContact,
    SplitOrder,
    SplitQuote,
    SplitQuoteDocument,
    SplitQuoteLineItem,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value: Any) -> datetime | None:
    """Parse an ISO-format datetime stored as SQLite text."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def instance_path() -> Path:
    return project_root() / "instance"


def source_db_path() -> Path:
    return instance_path() / "cylinder_quote.db"


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def backup_source_db() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = instance_path() / f"cylinder_quote.PREMIGRATION_BACKUP_{timestamp}.db"
    shutil.copy2(source_db_path(), backup_path)
    return backup_path


def create_engine_for_db(db_path: Path, base):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"timeout": 30, "isolation_level": "IMMEDIATE"},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        dbapi_conn.execute("PRAGMA foreign_keys = ON")
        dbapi_conn.execute("PRAGMA journal_mode = WAL")

    base.metadata.create_all(bind=engine)
    return engine


def open_readonly_source() -> sqlite3.Connection:
    uri = f"file:{source_db_path()}?mode=ro"
    return sqlite3.connect(uri, uri=True, detect_types=sqlite3.PARSE_DECLTYPES)


def load_users(conn: sqlite3.Connection) -> dict[int, dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, display_name, email FROM users"
    ).fetchall()
    return {
        row[0]: {"display_name": row[1], "email": row[2]}
        for row in rows
    }


def safe_json_loads(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (str, bytes, bytearray)):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def as_decimal(value: Any) -> Any:
    from decimal import Decimal, InvalidOperation

    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


ORDER_COLUMN_MAP = {
    "id": "id",
    "quote_id": "quote_id",
    "quote_number": "quote_number",
    "order_number": "order_number",
    "order_created_at": "order_created_at",
    "order_date": "order_date",
    "company_name": "company_name",
    "company_tagline": "company_tagline",
    "company_address": "company_address",
    "company_contact": "company_contact",
    "customer_name": "customer_name",
    "customer_address": "customer_address",
    "customer_reference": "customer_reference",
    "customer_city": "customer_city",
    "customer_state": "customer_state",
    "customer_zip": "customer_zip",
    "salesperson": "salesperson",
    "contact_name": "contact_name",
    "contact_phone": "contact_phone",
    "contact_email": "contact_email",
    "payment_terms": "payment_terms",
    "shipping_terms": "shipping_terms",
    "quantity": "quantity",
    "model_code": "model_code",
    "description": "description",
    "lead_time": "lead_time",
    "list_price": "list_price",
    "discount_percent": "discount_percent",
    "net_each": "net_each",
    "extended_price": "extended_price",
    "expedited_price": "expedited_price",
    "emergency_price": "emergency_price",
    "series": "series",
    "mount": "mount",
    "bore": "bore",
    "stroke": "stroke",
    "rod": "rod",
    "ports": "ports",
    "cushions": "cushions",
    "seals": "seals",
    "options": "options",
    "weight": "weight",
    "push_force": "push_force",
    "pull_force": "pull_force",
    "closed_dimension": "closed_dimension",
    "open_dimension": "open_dimension",
    "special_order_parts": "special_order_parts",
    "repair_1_name": "repair_1_name",
    "repair_1_part": "repair_1_part",
    "repair_1_qty": "repair_1_qty",
    "repair_1_price": "repair_1_price",
    "repair_2_name": "repair_2_name",
    "repair_2_part": "repair_2_part",
    "repair_2_qty": "repair_2_qty",
    "repair_2_price": "repair_2_price",
    "repair_3_name": "repair_3_name",
    "repair_3_part": "repair_3_part",
    "repair_3_qty": "repair_3_qty",
    "repair_3_price": "repair_3_price",
    "comments": "comments",
    "terms_conditions": "terms_conditions",
    "footer_message": "footer_message",
    "prepared_by": "prepared_by",
    "order_status": "order_status",
    "approved_by_name": "approved_by_name",
    "approved_by_email": "approved_by_email",
    "approved_at": "approved_at",
    "assembled_by": "assembled_by",
    "bill_to_1": "bill_to_1",
    "bill_to_2": "bill_to_2",
    "bill_to_3": "bill_to_3",
    "bill_to_4": "bill_to_4",
    "contact": "contact",
    "cushion": "cushion",
    "date_passed_test": "date_passed_test",
    "discount": "discount",
    "includes": "includes",
    "order_total": "order_total",
    "parts": "parts",
    "parts_total": "parts_total",
    "pivot_pin": "pivot_pin",
    "po_number": "po_number",
    "rod_clevis": "rod_clevis",
    "rod_diameter": "rod_diameter",
    "rod_thread": "rod_thread",
    "ship_date": "ship_date",
    "ship_method": "ship_method",
    "ship_to_1": "ship_to_1",
    "ship_to_2": "ship_to_2",
    "ship_to_3": "ship_to_3",
    "ship_to_4": "ship_to_4",
    "tag": "tag",
    "terms": "terms",
    "testing": "testing",
}

ORDER_NUMERIC_COLUMNS = {
    "list_price",
    "discount_percent",
    "net_each",
    "extended_price",
    "expedited_price",
    "emergency_price",
    "repair_1_price",
    "repair_2_price",
    "repair_3_price",
    "discount",
    "order_total",
    "parts_total",
}

ORDER_INT_COLUMNS = {
    "id",
    "quote_id",
    "quantity",
    "repair_1_qty",
    "repair_2_qty",
    "repair_3_qty",
}

ORDER_DATETIME_COLUMNS = {
    "order_created_at",
    "order_date",
    "approved_at",
}

ORDER_JSON_TEXT_COLUMNS = {
    "parts",
    "testing",
}


def migrate() -> dict[str, Any]:
    report: dict[str, Any] = {
        "backup_path": None,
        "source_hash_before": None,
        "source_hash_after": None,
        "source_mtime_before": None,
        "source_mtime_after": None,
        "counts": {},
        "unknown_order_keys": {},
    }

    source = source_db_path()
    report["source_hash_before"] = file_hash(source)
    report["source_mtime_before"] = source.stat().st_mtime

    backup_path = backup_source_db()
    report["backup_path"] = str(backup_path)

    # Verify backup didn't touch source.
    report["source_hash_during"] = file_hash(source)

    src = open_readonly_source()
    src.row_factory = sqlite3.Row
    users = load_users(src)

    # Counts from source.
    def count(table: str) -> int:
        return src.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    src_customers = count("customers")
    src_quotes = count("quotes")
    src_line_items = count("quote_line_items")
    src_documents = count("quote_documents")
    src_orders = src.execute(
        "SELECT COUNT(*) FROM quotes WHERE order_form_snapshot IS NOT NULL"
    ).fetchone()[0]

    report["counts"]["source"] = {
        "customers": src_customers,
        "quotes": src_quotes,
        "quote_line_items": src_line_items,
        "quote_documents": src_documents,
        "quotes_with_order_snapshot": src_orders,
    }

    # Create new databases.
    contacts_engine = create_engine_for_db(
        instance_path() / "Employee_Contacts.db", EmployeeContactsBase
    )
    quote_engine = create_engine_for_db(instance_path() / "Quote.db", QuoteBase)
    order_engine = create_engine_for_db(instance_path() / "Order.db", OrderBase)

    ContactsSession = sessionmaker(bind=contacts_engine)
    QuoteSession = sessionmaker(bind=quote_engine)
    OrderSession = sessionmaker(bind=order_engine)

    contacts_session = ContactsSession()
    quote_session = QuoteSession()
    order_session = OrderSession()

    try:
        # --- Migrate customers -> contacts ---
        for row in src.execute(
            "SELECT id, name, address, city_state_zip, phone, email, created_at, updated_at "
            "FROM customers ORDER BY id"
        ):
            contacts_session.add(
                SplitContact(
                    id=row["id"],
                    name=row["name"],
                    address=row["address"],
                    city_state_zip=row["city_state_zip"],
                    phone=row["phone"],
                    email=row["email"],
                    created_at=parse_dt(row["created_at"]),
                    updated_at=parse_dt(row["updated_at"]),
                )
            )

        # --- Migrate quotes -> Quote.db ---
        quote_cols = [r[1] for r in src.execute("PRAGMA table_info(quotes)")]

        # Determine actual columns present (future-proofing).
        def get(row, col: str, default=None):
            return row[col] if col in row.keys() else default

        for row in src.execute("SELECT * FROM quotes ORDER BY id"):
            def user_name(uid: int | None) -> str | None:
                return users[uid]["display_name"] if uid in users else None

            def user_email(uid: int | None) -> str | None:
                return users[uid]["email"] if uid in users else None

            q = SplitQuote(
                id=row["id"],
                quote_number=row["quote_number"],
                status=row["status"],
                customer_name=get(row, "customer_name"),
                customer_address=get(row, "customer_address"),
                customer_contact=get(row, "customer_contact"),
                customer_reference=get(row, "customer_reference"),
                comments=get(row, "comments"),
                special_instructions=get(row, "special_instructions"),
                pricing_version=get(row, "pricing_version", "v1.2"),
                revision=get(row, "revision", 1),
                quantity=get(row, "quantity", 1),
                discount=as_decimal(get(row, "discount")),
                model_code=get(row, "model_code"),
                cylinder_inputs_snapshot=safe_json_loads(
                    get(row, "cylinder_inputs_snapshot")
                ),
                price_breakdown_snapshot=safe_json_loads(
                    get(row, "price_breakdown_snapshot")
                ),
                created_by_user_id=row["created_by_user_id"],
                created_at=parse_dt(row["created_at"]),
                edited_by_user_id=get(row, "edited_by_user_id"),
                edited_at=parse_dt(get(row, "edited_at")),
                emailed_by_user_id=get(row, "emailed_by_user_id"),
                emailed_at=parse_dt(get(row, "emailed_at")),
                approved_by_user_id=get(row, "approved_by_user_id"),
                approved_at=parse_dt(get(row, "approved_at")),
                assigned_employee_user_id=get(row, "assigned_employee_user_id"),
                assigned_at=parse_dt(get(row, "assigned_at")),
                customer_update_pending=bool(get(row, "customer_update_pending", False)),
                created_by_name=user_name(row["created_by_user_id"]),
                created_by_email=user_email(row["created_by_user_id"]),
                edited_by_name=user_name(get(row, "edited_by_user_id")),
                edited_by_email=user_email(get(row, "edited_by_user_id")),
                approved_by_name=user_name(get(row, "approved_by_user_id")),
                approved_by_email=user_email(get(row, "approved_by_user_id")),
            )
            quote_session.add(q)

        # --- Migrate line items and documents ---
        for row in src.execute("SELECT * FROM quote_line_items ORDER BY id"):
            quote_session.add(
                SplitQuoteLineItem(
                    id=row["id"],
                    quote_id=row["quote_id"],
                    reference_part_number=get(row, "reference_part_number"),
                    description=row["description"],
                    quantity=as_decimal(row["quantity"]),
                    unit_price=as_decimal(row["unit_price"]),
                    extended_price=as_decimal(row["extended_price"]),
                    internal_note=get(row, "internal_note"),
                    show_on_customer_quote=bool(get(row, "show_on_customer_quote", True)),
                    sort_order=get(row, "sort_order", 0),
                )
            )

        for row in src.execute("SELECT * FROM quote_documents ORDER BY id"):
            quote_session.add(
                SplitQuoteDocument(
                    id=row["id"],
                    quote_id=row["quote_id"],
                    revision=row["revision"],
                    file_path=row["file_path"],
                    created_at=parse_dt(row["created_at"]),
                    created_by_user_id=row["created_by_user_id"],
                )
            )

        # --- Flatten order_form_snapshot -> Order.db ---
        unknown_keys_by_quote: dict[int, set[str]] = {}
        for row in src.execute(
            "SELECT id, quote_number, order_form_snapshot FROM quotes "
            "WHERE order_form_snapshot IS NOT NULL ORDER BY id"
        ):
            snapshot = safe_json_loads(row["order_form_snapshot"])
            if not isinstance(snapshot, dict):
                snapshot = {}

            mapped: dict[str, Any] = {
                "quote_id": row["id"],
                "quote_number": row["quote_number"],
            }
            unmapped: set[str] = set()

            for key, value in snapshot.items():
                if key in ORDER_COLUMN_MAP:
                    col = ORDER_COLUMN_MAP[key]
                    if col in ORDER_NUMERIC_COLUMNS:
                        mapped[col] = as_decimal(value)
                    elif col in ORDER_INT_COLUMNS:
                        mapped[col] = as_int(value)
                    elif col in ORDER_DATETIME_COLUMNS:
                        mapped[col] = parse_dt(value)
                    elif col in ORDER_JSON_TEXT_COLUMNS:
                        mapped[col] = json.dumps(value) if value is not None else None
                    else:
                        mapped[col] = value
                else:
                    unmapped.add(key)

            if unmapped:
                unknown_keys_by_quote[row["id"]] = unmapped

            order = SplitOrder(**mapped)
            order_session.add(order)

        contacts_session.commit()
        quote_session.commit()
        order_session.commit()

        report["counts"]["target"] = {
            "contacts": contacts_session.query(SplitContact).count(),
            "quotes": quote_session.query(SplitQuote).count(),
            "quote_line_items": quote_session.query(SplitQuoteLineItem).count(),
            "quote_documents": quote_session.query(SplitQuoteDocument).count(),
            "orders": order_session.query(SplitOrder).count(),
        }
        report["unknown_order_keys"] = {
            str(quote_id): sorted(keys)
            for quote_id, keys in unknown_keys_by_quote.items()
        }

    finally:
        contacts_session.close()
        quote_session.close()
        order_session.close()
        src.close()

    report["source_hash_after"] = file_hash(source)
    report["source_mtime_after"] = source.stat().st_mtime
    report["source_untouched"] = (
        report["source_hash_before"] == report["source_hash_after"]
    )

    return report


def main() -> None:
    os.chdir(project_root())
    report = migrate()

    print("=" * 60)
    print("Split-database migration complete")
    print("=" * 60)
    print(f"Backup: {report['backup_path']}")
    print(f"Source hash before: {report['source_hash_before']}")
    print(f"Source hash after:  {report['source_hash_after']}")
    print(f"Source untouched:   {report['source_untouched']}")
    print()
    print("Row counts:")
    for db_name, counts in report["counts"].items():
        print(f"  {db_name}:")
        for table, count in counts.items():
            print(f"    {table}: {count}")
    print()
    if report["unknown_order_keys"]:
        print("Order-form snapshot keys that did not map cleanly:")
        for quote_id, keys in report["unknown_order_keys"].items():
            print(f"  quote_id={quote_id}: {keys}")
    else:
        print("All order-form snapshot keys mapped cleanly.")


if __name__ == "__main__":
    main()
