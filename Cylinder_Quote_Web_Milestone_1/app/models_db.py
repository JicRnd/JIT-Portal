from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from .db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """Lightweight user record.

    No authentication is enforced yet, but the schema reserves nullable columns
    (email, username, password_hash) so a real auth system can be added later
    without a migration.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)

    # Reserved for future real authentication; nullable and unused for now.
    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )
    username: Mapped[str | None] = mapped_column(
        String(120), unique=True, nullable=True
    )
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # JIT portal account/profile fields.
    role: Mapped[str] = mapped_column(String(20), default="employee", nullable=False)
    access_level: Mapped[str] = mapped_column(
        String(20), default="standard", nullable=False
    )
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    phone_extension: Mapped[str | None] = mapped_column(String(20), nullable=True)
    shipping_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shipping_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    shipping_same_as_billing: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    assigned_promo_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    assigned_discount_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)

    approval_status: Mapped[str | None] = mapped_column(
        String(20), default="approved", nullable=True
    )
    # Set when an employee approves/holds/denies the account request.
    approval_decided_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    approval_decided_by_user_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    __table_args__ = (
        Index(
            "ix_users_display_name_lower",
            func.lower(display_name),
            unique=True,
        ),
    )


class Order(Base):
    """Order-form snapshot saved by the Order Now action, living in Order.db."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    quote_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="pending_approval", nullable=False
    )
    order_form_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )


class Customer(Base):
    """Saved customer directory used for Quote Entry autocomplete."""
    __tablename__ = "customers"

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


class PartFamily(Base):
    """Admin-defined part family: one image plus one reusable description template."""

    __tablename__ = "part_families"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    material: Mapped[str | None] = mapped_column(String(80), nullable=True)
    part_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Filename only, relative to app/static/family_images (never a caller-supplied path).
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_rule: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auto_description_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )


class CatalogPart(Base):
    """Imported master part row, stored only in Pricing.db."""

    __tablename__ = "catalog_parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_number: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Links a part to PartFamily.family_code (same database, no DB-level FK
    # so legacy imported rows stay valid while unassigned).
    family_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Explicit category for the traditional catalog index/sections; legacy rows
    # without one are categorized on the fly from their description.
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    sell_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    inventory: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sell_price_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    inventory_cost_values: Mapped[str | None] = mapped_column(Text, nullable=True)
    shipvia_sell_values: Mapped[str | None] = mapped_column(Text, nullable=True)
    acc_sell_values: Mapped[str | None] = mapped_column(Text, nullable=True)
    all_descriptions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Where the part came from in the source workbook (displayed as "Workbook Location").
    source_locations: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Free-text list of vendors that sell this part, one per line.
    vendors: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_needed: Mapped[str | None] = mapped_column(String(20), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[str | None] = mapped_column(String(20), nullable=True)


class BaseAssemblyPrice(Base):
    """Imported base-cylinder and piston/rod assembly price row."""

    __tablename__ = "base_assembly_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pricing_type: Mapped[str] = mapped_column(String(80), nullable=False)
    series: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bore: Mapped[str | None] = mapped_column(String(60), nullable=True)
    rod: Mapped[str | None] = mapped_column(String(60), nullable=True)
    mount_group: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    base_price_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    cushion_base: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    cushion_base_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    per_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    per_unit_price_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    cushion_per_end: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    cushion_per_end_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    rod_thread_std: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rod_thread_oversize: Mapped[str | None] = mapped_column(String(120), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_sheet: Mapped[str] = mapped_column(String(60), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_import_index: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)


class CommonModificationPrice(Base):
    """Imported common-modification price row."""

    __tablename__ = "common_modification_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    series: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bore: Mapped[str | None] = mapped_column(String(60), nullable=True)
    rod: Mapped[str | None] = mapped_column(String(60), nullable=True)
    option_name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    base_price_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    per_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    per_unit_price_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_sheet: Mapped[str] = mapped_column(String(60), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_import_index: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)


class PhVaPrice(Base):
    """Imported PH and VA price row."""

    __tablename__ = "ph_va_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pricing_group: Mapped[str] = mapped_column(String(80), nullable=False)
    series: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bore: Mapped[str | None] = mapped_column(String(60), nullable=True)
    rod: Mapped[str | None] = mapped_column(String(60), nullable=True)
    option_name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    base_price_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    per_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    per_unit_price_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_sheet: Mapped[str] = mapped_column(String(60), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_import_index: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)


class PriceChangeLog(Base):
    """Audit trail for admin pricing-catalog edits, stored in Pricing.db."""

    __tablename__ = "price_change_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_name: Mapped[str] = mapped_column(String(60), nullable=False)
    row_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field_name: Mapped[str] = mapped_column(String(60), nullable=False)
    record_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    record_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    old_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    new_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    # Used instead of old_value/new_value when a non-price field is edited.
    old_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_type: Mapped[str] = mapped_column(String(20), nullable=False, default="individual")
    # Groups every row touched by one bulk operation.
    batch_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    batch_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    changed_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    changed_by_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )


class Quote(Base):
    """Immutable historical quote snapshot.

    Stores the full cylinder configuration, calculated price breakdown, and
    presentation/business fields at the moment the quote was issued. Future
    pricing changes must not alter saved rows.
    """

    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_number: Mapped[str] = mapped_column(
        String(60), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), default="new", nullable=False
    )

    # Business/presentation snapshot fields. These are free-text because they
    # record what was printed on the quote, not a normalized customer master.
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    person_of_contact: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_contact: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    special_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_form_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Pricing/engine snapshot fields.
    pricing_version: Mapped[str] = mapped_column(
        String(20), default="v1.2", nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    discount: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    model_code: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Full serialized snapshots. JSON is intentionally used for immutability;
    # the engine is the authority on shape, not the schema.
    cylinder_inputs_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    price_breakdown_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # No DB-level ForeignKey: users live in their own database file
    # (Databases/User_accounts.db), so these are plain, app-enforced ids.
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

    # Set when a customer edits a quote/order that an employee already accepted.
    customer_update_pending: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    created_by = relationship(
        "User",
        primaryjoin="foreign(Quote.created_by_user_id) == User.id",
        viewonly=True,
    )
    edited_by = relationship(
        "User",
        primaryjoin="foreign(Quote.edited_by_user_id) == User.id",
        viewonly=True,
    )
    emailed_by = relationship(
        "User",
        primaryjoin="foreign(Quote.emailed_by_user_id) == User.id",
        viewonly=True,
    )
    approved_by = relationship(
        "User",
        primaryjoin="foreign(Quote.approved_by_user_id) == User.id",
        viewonly=True,
    )
    assigned_employee = relationship(
        "User",
        primaryjoin="foreign(Quote.assigned_employee_user_id) == User.id",
        viewonly=True,
    )

    line_items = relationship(
        "QuoteLineItem",
        back_populates="quote",
        cascade="all, delete-orphan",
        order_by="QuoteLineItem.sort_order",
    )

    documents = relationship(
        "QuoteDocument",
        back_populates="quote",
        cascade="all, delete-orphan",
        order_by="QuoteDocument.created_at.desc()",
    )

    emails = relationship(
        "EmailLog",
        back_populates="quote",
        cascade="all, delete-orphan",
        order_by="EmailLog.sent_at.desc()",
    )


class QuoteLineItem(Base):
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

    quote = relationship("Quote", back_populates="line_items")


class QuoteDocument(Base):
    """Generated customer-facing PDF for a specific quote revision."""

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
    # No DB-level ForeignKey: users live in Databases/User_accounts.db.
    created_by_user_id: Mapped[int] = mapped_column(Integer, nullable=False)

    quote = relationship("Quote", back_populates="documents")
    created_by = relationship(
        "User",
        primaryjoin="foreign(QuoteDocument.created_by_user_id) == User.id",
        viewonly=True,
    )


class EmailLog(Base):
    """Record of an attempt to email a quote revision to a customer."""

    __tablename__ = "email_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(
        ForeignKey("quotes.id"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    recipients: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    # No DB-level ForeignKey: users live in Databases/User_accounts.db.
    sent_by_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("quote_documents.id"), nullable=True
    )

    quote = relationship("Quote", back_populates="emails")
    sent_by = relationship(
        "User",
        primaryjoin="foreign(EmailLog.sent_by_user_id) == User.id",
        viewonly=True,
    )


class ApprovalSubmission(Base):
    """Record of an attempt to submit an approved quote to Data1."""

    __tablename__ = "approval_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(
        ForeignKey("quotes.id"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    request_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    request_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    response_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # No DB-level ForeignKey: users live in Databases/User_accounts.db.
    created_by_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    quote = relationship("Quote")
    created_by = relationship(
        "User",
        primaryjoin="foreign(ApprovalSubmission.created_by_user_id) == User.id",
        viewonly=True,
    )

    __table_args__ = (
        Index("ix_approval_submissions_quote_id", quote_id),
    )


class AiUsageCreditEntry(Base):
    """Admin-entered snapshot of AI orchestration credit usage on a given date."""

    __tablename__ = "ai_usage_credit_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    credits_used: Mapped[int] = mapped_column(Integer, nullable=False)
    credits_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )


class AiUsageDailySnapshot(Base):
    """Immutable per-day record comparing the live estimator to measured usage.

    ``estimated_*``/``task_count``/``breakdown_json`` are frozen the first time a
    day is finalized (the estimator's live prediction at the time). The
    ``actual_*`` columns are filled in later once a real GitHub credit entry
    exists for that date and, once set, are never recomputed - preserving an
    honest historical record of estimate vs. reality.
    """

    __tablename__ = "ai_usage_daily_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, unique=True)

    task_count: Mapped[int] = mapped_column(Integer, nullable=False)
    local_task_count: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_savings_credits: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_credits_estimate: Mapped[float] = mapped_column(Float, nullable=False)
    breakdown_json: Mapped[str] = mapped_column(Text, nullable=False)

    actual_credits_used_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_savings_credits: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimation_error: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    actuals_recorded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AiUsageClassCalibration(Base):
    """Rolling, per (task_type, worker, model) calibrated avoided-cost estimate.

    Updated only from finalized ``AiUsageDailySnapshot`` rows once real usage
    data arrives, so a single noisy class never distorts every other class.
    """

    __tablename__ = "ai_usage_class_calibrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_type: Mapped[str] = mapped_column(String(120), nullable=False)
    worker: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)

    sample_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    calibrated_cost_per_task: Mapped[float] = mapped_column(Float, nullable=False)
    last_recalibrated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index(
            "ix_ai_usage_class_calibrations_key",
            "task_type",
            "worker",
            "model",
            unique=True,
        ),
    )


class AiUsageGithubCreditSnapshot(Base):
    """Immutable intra-day snapshot of GitHub's cumulative AI-credit total.

    A row is only appended when ``cumulative_credits_used`` differs from the
    previous snapshot, so this is a sparse, append-only log of real
    GitHub-reported changes (Actual), never edited or recomputed afterward.
    """

    __tablename__ = "ai_usage_github_credit_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cumulative_credits_used: Mapped[float] = mapped_column(Float, nullable=False)
    model_breakdown_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_ai_usage_github_credit_snapshots_captured_at", "captured_at"),
    )
