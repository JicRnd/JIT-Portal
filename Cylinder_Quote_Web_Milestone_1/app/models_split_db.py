"""SQLAlchemy models for the split (post-migration) SQLite databases.

These models intentionally mirror the current persistence layer in
``app/models_db.py`` but are bound to separate database files:

* Employee_Contacts.db  -> contacts
* Quote.db              -> quotes, quote_line_items, quote_documents
* Order.db              -> orders

No existing code paths are wired to these models yet; this file exists so the
migration script can create the new schemas deterministically.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, declarative_base, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


EmployeeContactsBase = declarative_base()
QuoteBase = declarative_base()
OrderBase = declarative_base()


class SplitContact(EmployeeContactsBase):
    """Migrated customer directory, now living in Employee_Contacts.db."""

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city_state_zip: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )


class SplitQuote(QuoteBase):
    """Immutable historical quote snapshot, living in Quote.db."""

    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_number: Mapped[str] = mapped_column(
        String(60), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), default="draft", nullable=False
    )

    # Presentation/business fields.
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_contact: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    special_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pricing/engine snapshot fields.
    pricing_version: Mapped[str] = mapped_column(
        String(20), default="v1.2", nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    discount: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    model_code: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Serialized snapshots (intentionally JSON; immutable pricing-engine output).
    cylinder_inputs_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    price_breakdown_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_by_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    edited_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    emailed_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    approved_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    assigned_employee_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    customer_update_pending: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Denormalized employee identifying info (Quote.db has no users table).
    created_by_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    edited_by_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    edited_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_by_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    approved_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)


class SplitQuoteLineItem(QuoteBase):
    """User-entered manual/special-order line item on a saved quote."""

    __tablename__ = "quote_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(
        ForeignKey("quotes.id"), nullable=False
    )
    reference_part_number: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    extended_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    show_on_customer_quote: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class SplitQuoteDocument(QuoteBase):
    """Generated customer-facing document for a specific quote revision."""

    __tablename__ = "quote_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(
        ForeignKey("quotes.id"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    created_by_user_id: Mapped[int] = mapped_column(Integer, nullable=False)


class SplitOrder(OrderBase):
    """Flattened order-form snapshot extracted from a saved quote."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    order_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    order_created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    order_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_tagline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_contact: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    customer_state: Mapped[str | None] = mapped_column(String(60), nullable=True)
    customer_zip: Mapped[str | None] = mapped_column(String(20), nullable=True)

    salesperson: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shipping_terms: Mapped[str | None] = mapped_column(String(255), nullable=True)

    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    lead_time: Mapped[str | None] = mapped_column(String(255), nullable=True)
    list_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    discount_percent: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    net_each: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    extended_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    expedited_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    emergency_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    series: Mapped[str | None] = mapped_column(String(60), nullable=True)
    mount: Mapped[str | None] = mapped_column(String(60), nullable=True)
    bore: Mapped[str | None] = mapped_column(String(60), nullable=True)
    stroke: Mapped[str | None] = mapped_column(String(60), nullable=True)
    rod: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ports: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cushions: Mapped[str | None] = mapped_column(String(120), nullable=True)
    seals: Mapped[str | None] = mapped_column(String(120), nullable=True)
    options: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight: Mapped[str | None] = mapped_column(String(60), nullable=True)
    push_force: Mapped[str | None] = mapped_column(String(60), nullable=True)
    pull_force: Mapped[str | None] = mapped_column(String(60), nullable=True)
    closed_dimension: Mapped[str | None] = mapped_column(String(60), nullable=True)
    open_dimension: Mapped[str | None] = mapped_column(String(60), nullable=True)

    special_order_parts: Mapped[str | None] = mapped_column(Text, nullable=True)

    repair_1_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    repair_1_part: Mapped[str | None] = mapped_column(String(120), nullable=True)
    repair_1_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    repair_1_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    repair_2_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    repair_2_part: Mapped[str | None] = mapped_column(String(120), nullable=True)
    repair_2_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    repair_2_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    repair_3_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    repair_3_part: Mapped[str | None] = mapped_column(String(120), nullable=True)
    repair_3_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    repair_3_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    terms_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    footer_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    prepared_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    order_status: Mapped[str | None] = mapped_column(String(60), nullable=True)
    approved_by_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    approved_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Additional order-form snapshot fields surfaced from the source JSON.
    assembled_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bill_to_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bill_to_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bill_to_3: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bill_to_4: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cushion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_passed_test: Mapped[str | None] = mapped_column(String(255), nullable=True)
    discount: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    includes: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    parts: Mapped[str | None] = mapped_column(Text, nullable=True)
    parts_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    pivot_pin: Mapped[str | None] = mapped_column(String(60), nullable=True)
    po_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rod_clevis: Mapped[str | None] = mapped_column(String(60), nullable=True)
    rod_diameter: Mapped[str | None] = mapped_column(String(60), nullable=True)
    rod_thread: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ship_date: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ship_method: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ship_to_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ship_to_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ship_to_3: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ship_to_4: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    terms: Mapped[str | None] = mapped_column(String(255), nullable=True)
    testing: Mapped[str | None] = mapped_column(Text, nullable=True)
