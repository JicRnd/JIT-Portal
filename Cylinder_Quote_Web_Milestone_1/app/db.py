from __future__ import annotations

import os
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

# Non-business application telemetry is isolated from the five business
# databases. The runtime never uses the legacy instance database.
DEFAULT_DATABASE_PATH = str(
    Path(__file__).resolve().parents[1] / "Databases" / "Application.db"
)

# All employee/customer account and login records live in their own dedicated
# SQLite file, separate from quotes/customers, so account data stays isolated.
DEFAULT_ACCOUNTS_DATABASE_PATH = str(
    Path(__file__).resolve().parents[1] / "Databases" / "User_accounts.db"
)

DEFAULT_CONTACTS_DATABASE_PATH = str(
    Path(__file__).resolve().parents[1] / "Databases" / "Employee_Contacts.db"
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

# Imported pricing-catalog data is intentionally isolated from quote snapshots,
# orders, accounts, and the protected calculator's normalized source files.
DEFAULT_PRICING_DATABASE_PATH = str(
    Path(__file__).resolve().parents[1] / "Databases" / "Pricing.db"
)

DEFAULT_INVENTORY_DATABASE_PATH = str(
    Path(__file__).resolve().parents[1] / "Databases" / "Inventory.db"
)

_engine = None
_accounts_engine = None
_contacts_engine = None
_quotes_engine = None
_orders_engine = None
_pricing_engine = None
_inventory_engine = None
_Session = None


def reset_engines() -> None:
    """Dispose cached engines and clear the session factory.

    This is primarily useful for tests that switch database paths between
    application instances.
    """
    global _engine, _accounts_engine, _contacts_engine, _quotes_engine, _orders_engine, _pricing_engine, _inventory_engine, _Session

    for engine in (_engine, _accounts_engine, _contacts_engine, _quotes_engine, _orders_engine, _pricing_engine, _inventory_engine):
        if engine is not None:
            engine.dispose()
    _engine = None
    _accounts_engine = None
    _contacts_engine = None
    _quotes_engine = None
    _orders_engine = None
    _pricing_engine = None
    _inventory_engine = None
    _Session = None


def _resolve_database_path() -> str:
    """Resolve the database path from the environment each time."""
    return os.environ.get("DATABASE_PATH", DEFAULT_DATABASE_PATH)


def _resolve_accounts_database_path() -> str:
    """Resolve the user-accounts database path from the environment each time."""
    return os.environ.get("ACCOUNTS_DATABASE_PATH", DEFAULT_ACCOUNTS_DATABASE_PATH)


def _resolve_contacts_database_path() -> str:
    """Resolve the employee/customer contacts database path."""
    return os.environ.get("CONTACTS_DATABASE_PATH", DEFAULT_CONTACTS_DATABASE_PATH)


def _resolve_quotes_database_path() -> str:
    """Resolve the quotes database path from the environment each time."""
    return os.environ.get("QUOTES_DATABASE_PATH", DEFAULT_QUOTES_DATABASE_PATH)


def _resolve_orders_database_path() -> str:
    """Resolve the orders database path from the environment each time."""
    return os.environ.get("ORDERS_DATABASE_PATH", DEFAULT_ORDERS_DATABASE_PATH)


def _resolve_pricing_database_path() -> str:
    """Resolve the pricing-catalog database path from the environment each time."""
    return os.environ.get("PRICING_DATABASE_PATH", DEFAULT_PRICING_DATABASE_PATH)


def _resolve_inventory_database_path() -> str:
    """Resolve the dedicated inventory database path."""
    return os.environ.get("INVENTORY_DATABASE_PATH", DEFAULT_INVENTORY_DATABASE_PATH)


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
        dbapi_conn.execute("PRAGMA busy_timeout = 30000")

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


def get_contacts_engine():
    """Return the singleton engine for Employee_Contacts.db."""
    global _contacts_engine
    if _contacts_engine is None:
        _contacts_engine = _build_sqlite_engine(Path(_resolve_contacts_database_path()))
    return _contacts_engine


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


def get_pricing_engine():
    """Return the singleton engine for the dedicated Pricing.db file."""
    global _pricing_engine
    if _pricing_engine is None:
        _pricing_engine = _build_sqlite_engine(Path(_resolve_pricing_database_path()))
    return _pricing_engine


def get_inventory_engine():
    """Return the singleton engine for the dedicated Inventory.db file."""
    global _inventory_engine
    if _inventory_engine is None:
        _inventory_engine = _build_sqlite_engine(Path(_resolve_inventory_database_path()))
    return _inventory_engine


def get_session_factory():
    """Return the singleton sessionmaker, creating it on first call."""
    global _Session
    if _Session is None:
        from . import models_db
        from . import quote_numbering

        quotes_engine = get_quotes_engine()
        inventory_engine = get_inventory_engine()
        quote_binds = {
            models_db.Quote: quotes_engine,
            models_db.QuoteLineItem: quotes_engine,
            models_db.QuoteDocument: quotes_engine,
            models_db.EmailLog: quotes_engine,
            models_db.ApprovalSubmission: quotes_engine,
            quote_numbering.QuoteNumberSequence: quotes_engine,
            models_db.Order: get_orders_engine(),
            models_db.CatalogPart: get_pricing_engine(),
            models_db.OrderFormInventoryRule: get_pricing_engine(),
            models_db.TieRodRule: get_pricing_engine(),
            models_db.OrderFormWorkbookCell: get_pricing_engine(),
            models_db.OrderFormDependencyCell: get_pricing_engine(),
            models_db.OrderFormDependencyEdge: get_pricing_engine(),
            models_db.PartFamily: get_pricing_engine(),
            models_db.BaseAssemblyPrice: get_pricing_engine(),
            models_db.CommonModificationPrice: get_pricing_engine(),
            models_db.PhVaPrice: get_pricing_engine(),
            models_db.PriceChangeLog: get_pricing_engine(),
            models_db.InventoryPart: inventory_engine,
        }

        _Session = sessionmaker(
            bind=get_engine(),
            binds={
                models_db.User: get_accounts_engine(),
                models_db.Customer: get_contacts_engine(),
                **quote_binds,
            },
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
    contacts_engine = get_contacts_engine()
    quotes_engine = get_quotes_engine()
    orders_engine = get_orders_engine()
    pricing_engine = get_pricing_engine()
    inventory_engine = get_inventory_engine()

    user_tables = [models_db.User.__table__]
    contact_tables = [models_db.Customer.__table__]
    quote_tables = [
        models_db.Quote.__table__,
        models_db.QuoteLineItem.__table__,
        models_db.QuoteDocument.__table__,
        models_db.EmailLog.__table__,
        models_db.ApprovalSubmission.__table__,
        quote_numbering.QuoteNumberSequence.__table__,
    ]
    order_tables = [models_db.Order.__table__]
    pricing_tables = [
        models_db.CatalogPart.__table__,
        models_db.OrderFormInventoryRule.__table__,
        models_db.TieRodRule.__table__,
        models_db.OrderFormWorkbookCell.__table__,
        models_db.OrderFormDependencyCell.__table__,
        models_db.OrderFormDependencyEdge.__table__,
        models_db.PartFamily.__table__,
        models_db.BaseAssemblyPrice.__table__,
        models_db.CommonModificationPrice.__table__,
        models_db.PhVaPrice.__table__,
        models_db.PriceChangeLog.__table__,
    ]
    inventory_tables = [models_db.InventoryPart.__table__]
    other_tables = [
        table
        for table in Base.metadata.sorted_tables
        if table not in user_tables and table not in contact_tables and table not in quote_tables and table not in order_tables and table not in pricing_tables and table not in inventory_tables
    ]

    Base.metadata.create_all(bind=accounts_engine, tables=user_tables)
    Base.metadata.create_all(bind=contacts_engine, tables=contact_tables)
    Base.metadata.create_all(bind=quotes_engine, tables=quote_tables)
    Base.metadata.create_all(bind=orders_engine, tables=order_tables)
    Base.metadata.create_all(bind=pricing_engine, tables=pricing_tables)
    _migrate_inventory_schema(inventory_engine)
    Base.metadata.create_all(bind=inventory_engine, tables=inventory_tables)
    Base.metadata.create_all(bind=engine, tables=other_tables)

    # Lightweight migration for customer directory presentation and notes.
    with contacts_engine.begin() as connection:
        customer_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(customers)")
        }
        required_customer_columns = {
            "company_name": "VARCHAR(255)",
            "poc": "VARCHAR(255)",
            "shipping_address": "TEXT",
            "notes": "TEXT",
        }
        for column_name, column_type in required_customer_columns.items():
            if column_name not in customer_columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE customers ADD COLUMN {column_name} {column_type}"
                )

    # Lightweight SQLite migration for accounts created before the current schema.
    with accounts_engine.begin() as connection:
        user_columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(users)")}
        required_user_columns = {
            "role": "VARCHAR(20) NOT NULL DEFAULT 'employee'",
            "access_level": "VARCHAR(20) NOT NULL DEFAULT 'standard'",
            "company_name": "VARCHAR(255)",
            "phone": "VARCHAR(60)",
            "phone_extension": "VARCHAR(20)",
            "shipping_name": "VARCHAR(255)",
            "shipping_address": "TEXT",
            "billing_address": "TEXT",
            "shipping_same_as_billing": "BOOLEAN",
            "assigned_promo_code": "VARCHAR(40)",
            "assigned_discount_percent": "INTEGER",
            "approval_status": "VARCHAR(20) DEFAULT 'approved'",
            "approval_decided_at": "DATETIME",
            "approval_decided_by_user_id": "INTEGER",
        }
        for column_name, column_type in required_user_columns.items():
            if column_name not in user_columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"
                )
        connection.exec_driver_sql(
            """
            UPDATE users
            SET approval_status = 'pending'
            WHERE is_active = 0
              AND (approval_status IS NULL OR approval_status = 'approved')
            """
        )

    # Lightweight SQLite migration for projects created before Special Instructions.
    with quotes_engine.begin() as connection:
        quote_columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(quotes)")}
        if "special_instructions" not in quote_columns:
            connection.exec_driver_sql("ALTER TABLE quotes ADD COLUMN special_instructions TEXT")
        required_quote_columns = {
            "customer_address": "TEXT",
            "person_of_contact": "TEXT",
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
            "deleted_by_user_id": "INTEGER",
            "deleted_at": "DATETIME",
            "deleted_status": "VARCHAR(30)",
        }
        for column_name, column_type in required_quote_columns.items():
            if column_name not in quote_columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE quotes ADD COLUMN {column_name} {column_type}"
                )

    # Lightweight SQLite migration for recoverable employee order history.
    with orders_engine.begin() as connection:
        order_columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(orders)")}
        required_order_columns = {
            "deleted_status": "VARCHAR(30)",
            "deleted_by_user_id": "INTEGER",
            "deleted_at": "DATETIME",
        }
        for column_name, column_type in required_order_columns.items():
            if column_name not in order_columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE orders ADD COLUMN {column_name} {column_type}"
                )

    # Lightweight SQLite migration for catalog parts created before the
    # dedicated category column existed.
    with pricing_engine.begin() as connection:
        catalog_part_columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(catalog_parts)")}
        if "category" not in catalog_part_columns:
            connection.exec_driver_sql("ALTER TABLE catalog_parts ADD COLUMN category VARCHAR(80)")
        if "family_code" not in catalog_part_columns:
            connection.exec_driver_sql("ALTER TABLE catalog_parts ADD COLUMN family_code VARCHAR(40)")
        if "vendors" not in catalog_part_columns:
            connection.exec_driver_sql("ALTER TABLE catalog_parts ADD COLUMN vendors TEXT")
        if "inventory" not in catalog_part_columns:
            connection.exec_driver_sql("ALTER TABLE catalog_parts ADD COLUMN inventory INTEGER")

        price_log_columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(price_change_log)")}
        if price_log_columns and "old_text" not in price_log_columns:
            connection.exec_driver_sql("ALTER TABLE price_change_log ADD COLUMN old_text TEXT")
            connection.exec_driver_sql("ALTER TABLE price_change_log ADD COLUMN new_text TEXT")

    # Order status is kept separately from the quote status so Order.db can be
    # queried independently for approval and fulfillment workflows.
    with orders_engine.begin() as connection:
        order_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(orders)")
        }
        if "status" not in order_columns:
            connection.exec_driver_sql(
                "ALTER TABLE orders ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'pending_approval'"
            )

    # Customer directory column rename: contact -> phone, plus email.
    with contacts_engine.begin() as connection:
        customer_columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(customers)")}
        if "contact" in customer_columns and "phone" not in customer_columns:
            connection.exec_driver_sql("ALTER TABLE customers RENAME COLUMN contact TO phone")
        if "email" not in customer_columns:
            connection.exec_driver_sql("ALTER TABLE customers ADD COLUMN email VARCHAR(255)")
        if "city_state_zip" not in customer_columns:
            connection.exec_driver_sql("ALTER TABLE customers ADD COLUMN city_state_zip VARCHAR(255)")


def _migrate_inventory_schema(inventory_engine) -> None:
    """Rebuild the legacy inventory table into the current minimal schema."""
    with inventory_engine.begin() as connection:
        columns = [row[1] for row in connection.exec_driver_sql("PRAGMA table_info(inventory_parts)")]
        legacy_current = [
            "part_number", "product_description", "inventory", "allocated",
            "start_2025", "on_order", "updated_by", "updated_at",
        ]
        current = [*legacy_current[:6], "source_name", *legacy_current[6:]]
        if not columns or set(columns) == set(current):
            return
        if set(columns) == set(legacy_current):
            with inventory_engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE inventory_parts ADD COLUMN source_name VARCHAR(255)")
            return
        rows = connection.exec_driver_sql(
            "SELECT part_number, product_description, inventory, on_hand, allocated, start_2025, on_order, updated_at "
            "FROM inventory_parts"
        ).fetchall()
        connection.exec_driver_sql("DROP TABLE IF EXISTS inventory_parts_new")
        connection.exec_driver_sql(
            "CREATE TABLE inventory_parts_new ("
            "part_number VARCHAR(120) PRIMARY KEY NOT NULL, product_description TEXT, "
            "inventory INTEGER NOT NULL DEFAULT 0, allocated NUMERIC(14, 4), "
            "start_2025 NUMERIC(14, 4), on_order NUMERIC(14, 4), source_name VARCHAR(255), "
            "updated_by VARCHAR(255), updated_at DATETIME NOT NULL)"
        )
        for part_number, description, inventory, on_hand, allocated, start_2025, on_order, updated_at in rows:
            quantity = inventory if inventory is not None else on_hand
            quantity = int(Decimal(str(quantity or 0)).to_integral_value(rounding=ROUND_CEILING))
            connection.exec_driver_sql(
                "INSERT INTO inventory_parts_new "
                "(part_number, product_description, inventory, allocated, start_2025, on_order, source_name, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (part_number, description, quantity, allocated, start_2025, on_order, None, updated_at),
            )
        connection.exec_driver_sql("DROP TABLE inventory_parts")
        connection.exec_driver_sql("ALTER TABLE inventory_parts_new RENAME TO inventory_parts")

