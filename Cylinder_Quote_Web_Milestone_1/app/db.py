from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

DEFAULT_DATABASE_PATH = str(
    Path(__file__).resolve().parents[1] / "instance" / "cylinder_quote.db"
)

# All employee/customer account and login records live in their own dedicated
# SQLite file, separate from quotes/customers, so account data stays isolated.
DEFAULT_ACCOUNTS_DATABASE_PATH = str(
    Path(__file__).resolve().parents[1] / "Databases" / "User_accounts.db"
)

# Saved quotes/orders and everything tied to them live in their own dedicated
# SQLite file, separate from accounts/customers.
DEFAULT_QUOTES_DATABASE_PATH = str(
    Path(__file__).resolve().parents[1] / "Databases" / "Quote.db"
)

# Order-form snapshots saved by the Order Now action live in their own
# dedicated SQLite file.
DEFAULT_ORDERS_DATABASE_PATH = str(
    Path(__file__).resolve().parents[1] / "Databases" / "Order.db"
)

_engine = None
_accounts_engine = None
_quotes_engine = None
_orders_engine = None
_Session = None


def _resolve_database_path() -> str:
    """Resolve the database path from the environment each time."""
    return os.environ.get("DATABASE_PATH", DEFAULT_DATABASE_PATH)


def _resolve_accounts_database_path() -> str:
    """Resolve the user-accounts database path from the environment each time."""
    return os.environ.get("ACCOUNTS_DATABASE_PATH", DEFAULT_ACCOUNTS_DATABASE_PATH)


def _resolve_quotes_database_path() -> str:
    """Resolve the quotes database path from the environment each time."""
    return os.environ.get("QUOTES_DATABASE_PATH", DEFAULT_QUOTES_DATABASE_PATH)


def _resolve_orders_database_path() -> str:
    """Resolve the orders database path from the environment each time."""
    return os.environ.get("ORDERS_DATABASE_PATH", DEFAULT_ORDERS_DATABASE_PATH)


def _build_sqlite_engine(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={
            "timeout": 30,
            # Hold the writer lock for the whole transaction so concurrent
            # quote-number generation serializes at the database level.
            "isolation_level": "IMMEDIATE",
        },
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        dbapi_conn.execute("PRAGMA foreign_keys = ON")
        dbapi_conn.execute("PRAGMA journal_mode = DELETE")

    return engine


def get_engine():
    """Return the singleton SQLAlchemy engine, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = _build_sqlite_engine(Path(_resolve_database_path()))
    return _engine


def get_accounts_engine():
    """Return the singleton engine for the User_accounts.db file."""
    global _accounts_engine
    if _accounts_engine is None:
        _accounts_engine = _build_sqlite_engine(Path(_resolve_accounts_database_path()))
    return _accounts_engine


def get_quotes_engine():
    """Return the singleton engine for the Quote.db file."""
    global _quotes_engine
    if _quotes_engine is None:
        _quotes_engine = _build_sqlite_engine(Path(_resolve_quotes_database_path()))
    return _quotes_engine


def get_orders_engine():
    """Return the singleton engine for the Order.db file."""
    global _orders_engine
    if _orders_engine is None:
        _orders_engine = _build_sqlite_engine(Path(_resolve_orders_database_path()))
    return _orders_engine


def get_session_factory():
    """Return the singleton sessionmaker, creating it on first call."""
    global _Session
    if _Session is None:
        from . import models_db
        from . import quote_numbering

        quotes_engine = get_quotes_engine()
        quote_binds = {
            models_db.Quote: quotes_engine,
            models_db.QuoteLineItem: quotes_engine,
            models_db.QuoteDocument: quotes_engine,
            models_db.EmailLog: quotes_engine,
            models_db.ApprovalSubmission: quotes_engine,
            quote_numbering.QuoteNumberSequence: quotes_engine,
            models_db.Order: get_orders_engine(),
        }

        _Session = sessionmaker(
            bind=get_engine(),
            binds={models_db.User: get_accounts_engine(), **quote_binds},
            expire_on_commit=False,
        )
    return _Session


def get_session():
    """Return a new SQLAlchemy Session bound to the project engine."""
    return get_session_factory()()


def init_db():
    """Create all tables defined in the persistence modules.

    Import modules here so that their tables are registered on ``Base``.
    """
    # noqa: F401 - imported for side effects (table registration)
    from . import models_db  # noqa: F401
    from . import quote_numbering  # noqa: F401

    engine = get_engine()
    accounts_engine = get_accounts_engine()
    quotes_engine = get_quotes_engine()
    orders_engine = get_orders_engine()

    user_tables = [models_db.User.__table__]
    quote_tables = [
        models_db.Quote.__table__,
        models_db.QuoteLineItem.__table__,
        models_db.QuoteDocument.__table__,
        models_db.EmailLog.__table__,
        models_db.ApprovalSubmission.__table__,
        quote_numbering.QuoteNumberSequence.__table__,
    ]
    order_tables = [models_db.Order.__table__]
    other_tables = [
        table
        for table in Base.metadata.sorted_tables
        if table not in user_tables and table not in quote_tables and table not in order_tables
    ]

    Base.metadata.create_all(bind=accounts_engine, tables=user_tables)
    Base.metadata.create_all(bind=quotes_engine, tables=quote_tables)
    Base.metadata.create_all(bind=orders_engine, tables=order_tables)
    Base.metadata.create_all(bind=engine, tables=other_tables)

    # Lightweight SQLite migration for accounts created before the current schema.
    with accounts_engine.begin() as connection:
        user_columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(users)")}
        required_user_columns = {
            "role": "VARCHAR(20) NOT NULL DEFAULT 'employee'",
            "company_name": "VARCHAR(255)",
            "phone": "VARCHAR(60)",
            "phone_extension": "VARCHAR(20)",
            "shipping_name": "VARCHAR(255)",
            "shipping_address": "TEXT",
            "billing_address": "TEXT",
            "shipping_same_as_billing": "BOOLEAN",
            "assigned_promo_code": "VARCHAR(40)",
            "assigned_discount_percent": "INTEGER",
        }
        for column_name, column_type in required_user_columns.items():
            if column_name not in user_columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"
                )

    # Lightweight SQLite migration for projects created before Special Instructions.
    with quotes_engine.begin() as connection:
        quote_columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(quotes)")}
        if "special_instructions" not in quote_columns:
            connection.exec_driver_sql("ALTER TABLE quotes ADD COLUMN special_instructions TEXT")
        required_quote_columns = {
            "customer_address": "TEXT",
            "customer_contact": "TEXT",
            "comments": "TEXT",
            "revision": "INTEGER NOT NULL DEFAULT 1",
            "quantity": "INTEGER NOT NULL DEFAULT 1",
            "discount": "NUMERIC",
            "model_code": "VARCHAR(120)",
            "cylinder_inputs_snapshot": "JSON",
            "price_breakdown_snapshot": "JSON",
        }
        for column_name, column_type in required_quote_columns.items():
            if column_name not in quote_columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE quotes ADD COLUMN {column_name} {column_type}"
                )
        if "order_form_snapshot" not in quote_columns:
            connection.exec_driver_sql("ALTER TABLE quotes ADD COLUMN order_form_snapshot JSON")

        # Employee claim/assignment columns for the shared pending-approval queue.
        # No DB-level FK here: users now live in a separate database file.
        required_quote_columns = {
            "assigned_employee_user_id": "INTEGER",
            "assigned_at": "DATETIME",
            "customer_update_pending": "BOOLEAN NOT NULL DEFAULT 0",
        }
        for column_name, column_type in required_quote_columns.items():
            if column_name not in quote_columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE quotes ADD COLUMN {column_name} {column_type}"
                )

    # Customer directory column rename: contact -> phone, plus email.
    with engine.begin() as connection:
        customer_columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(customers)")}
        if "contact" in customer_columns and "phone" not in customer_columns:
            connection.exec_driver_sql("ALTER TABLE customers RENAME COLUMN contact TO phone")
        if "email" not in customer_columns:
            connection.exec_driver_sql("ALTER TABLE customers ADD COLUMN email VARCHAR(255)")
        if "city_state_zip" not in customer_columns:
            connection.exec_driver_sql("ALTER TABLE customers ADD COLUMN city_state_zip VARCHAR(255)")

