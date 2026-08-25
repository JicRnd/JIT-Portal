from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, select

from cylinder_quote_engine import QuotePricingEngine

from .models_db import Customer, Quote, QuoteLineItem, utc_now
from .quote_numbering import generate_quote_number
from .service import calculate_payload, decimal_to_json, quote_inputs_from_payload

PRICING_VERSION = "v1.2"


def _optional_str(value: Any, default: str | None = None) -> str | None:
    """Coerce an optional string value, treating blank input as the default."""
    if value is None:
        return default
    cleaned = str(value).strip()
    return cleaned if cleaned else default


def _parse_non_negative_decimal(value: Any, field_name: str) -> Decimal:
    """Parse a required numeric value and reject negatives."""
    if value is None or value == "":
        raise ValueError(f"{field_name} is required")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if d < 0:
        raise ValueError(f"{field_name} cannot be negative")
    return d


def _validate_manual_line_items(items: Any) -> list[dict[str, Any]]:
    """Validate and normalize a list of manual line-item dicts."""
    if items is None:
        return []
    if not isinstance(items, list):
        raise ValueError("manual_line_items must be a list")

    out: list[dict[str, Any]] = []
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise ValueError(f"manual_line_items[{i}] must be an object")

        description = _optional_str(raw.get("description"), default="")
        if not description:
            raise ValueError(f"manual_line_items[{i}].description is required")

        quantity = _parse_non_negative_decimal(
            raw.get("quantity"), f"manual_line_items[{i}].quantity"
        )
        unit_price = _parse_non_negative_decimal(
            raw.get("unit_price"), f"manual_line_items[{i}].unit_price"
        )

        out.append(
            {
                "reference_part_number": _optional_str(raw.get("reference_part_number")),
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "internal_note": _optional_str(raw.get("internal_note")),
                "show_on_customer_quote": bool(raw.get("show_on_customer_quote", True)),
            }
        )

    return out


def upsert_customer(session: Session, name: str | None, address: str | None, phone: str | None, email: str | None = None, city_state_zip: str | None = None) -> None:
    """Keep the saved customer directory current from a quote's presentation fields."""
    name = (name or "").strip()
    address = (address or "").strip() or None
    phone = (phone or "").strip() or None
    email = (email or "").strip() or None
    city_state_zip = (city_state_zip or "").strip() or None
    existing = session.execute(
        select(Customer).where(func.lower(Customer.name) == name.lower())
    ).scalar_one_or_none()
    if existing:
        if address:
            existing.address = address
        if phone:
            existing.phone = phone
        if email:
            existing.email = email
        if city_state_zip:
            existing.city_state_zip = city_state_zip
    else:
        session.add(Customer(name=name, address=address, phone=phone, email=email, city_state_zip=city_state_zip))


def create_quote_snapshot(
    session: Session,
    payload: dict[str, Any],
    current_user,
    engine: QuotePricingEngine,
) -> Quote:
    """Persist a new immutable quote snapshot including manual line items."""
    inputs = quote_inputs_from_payload(payload)
    breakdown = calculate_payload(engine, payload)

    # Validate manual items before consuming a quote number.
    line_items = _validate_manual_line_items(payload.get("manual_line_items"))

    customer_name = _optional_str(payload.get("customer_name"))
    customer_address = _optional_str(payload.get("customer_address"))
    customer_contact = _optional_str(payload.get("customer_contact"))
    customer_reference = _optional_str(payload.get("reference_notes"))
    comments = _optional_str(payload.get("comments"))
    special_instructions = _optional_str(payload.get("special_instructions"))
    quantity = max(1, int(payload.get("quantity", 1) or 1))
    inputs_snapshot = decimal_to_json(asdict(inputs))

    # Prefer the Quote ID created when the Quote button was clicked
    # (first letter of Quote Entry name + mmddyyhhmm). Fall back to server
    # generation in the same format if one was not provided.
    provided_number = _optional_str(payload.get("quote_number"))
    quote = None
    last_error: Exception | None = None
    for _attempt in range(20):
        try:
            with session.begin_nested():
                if _attempt == 0 and provided_number and len(provided_number) == 11:
                    quote_number = provided_number.upper()
                else:
                    quote_number = generate_quote_number(session, customer_name)
                quote = Quote(
                    quote_number=quote_number,
                    status="draft",
                    pricing_version=PRICING_VERSION,
                    quantity=quantity,
                    discount=inputs.discount,
                    model_code=breakdown["model_code"],
                    cylinder_inputs_snapshot=inputs_snapshot,
                    price_breakdown_snapshot=breakdown,
                    customer_name=customer_name,
                    customer_address=customer_address,
                    customer_contact=customer_contact,
                    customer_reference=customer_reference,
                    comments=comments,
                    special_instructions=special_instructions,
                    created_by_user_id=current_user.id,
                )
                session.add(quote)
                session.flush()
            break
        except IntegrityError as exc:
            last_error = exc
            quote = None
            continue

    if quote is None:
        raise RuntimeError("Failed to create quote with a unique quote number") from last_error

    for i, item in enumerate(line_items):
        session.add(
            QuoteLineItem(
                quote=quote,
                reference_part_number=item["reference_part_number"],
                description=item["description"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                extended_price=item["quantity"] * item["unit_price"],
                internal_note=item["internal_note"],
                show_on_customer_quote=item["show_on_customer_quote"],
                sort_order=i,
            )
        )

    upsert_customer(session, quote.customer_name, quote.customer_address, phone=quote.customer_contact)
    return quote


def get_quote(session: Session, quote_id: int) -> Quote | None:
    """Retrieve a saved quote with line items eagerly loaded."""
    return session.execute(
        select(Quote)
        .where(Quote.id == quote_id)
        .options(
            selectinload(Quote.line_items),
            selectinload(Quote.created_by),
            selectinload(Quote.edited_by),
            selectinload(Quote.emailed_by),
            selectinload(Quote.approved_by),
        )
    ).scalar_one_or_none()


def update_quote_edits(
    session: Session,
    quote_id: int,
    payload: dict[str, Any],
    current_user,
    *,
    engine: QuotePricingEngine | None = None,
) -> Quote:
    """Update the existing quote in place without creating a new order."""
    quote = get_quote(session, quote_id)
    if quote is None:
        raise ValueError("Quote not found")

    if "customer_name" in payload:
        quote.customer_name = _optional_str(payload["customer_name"])
    if "customer_address" in payload:
        quote.customer_address = _optional_str(payload["customer_address"])
    if "customer_contact" in payload:
        quote.customer_contact = _optional_str(payload["customer_contact"])
    if "reference_notes" in payload:
        quote.customer_reference = _optional_str(payload["reference_notes"])
    if "comments" in payload:
        quote.comments = _optional_str(payload["comments"])
    if "special_instructions" in payload:
        quote.special_instructions = _optional_str(payload["special_instructions"])

    if "quantity" in payload:
        quote.quantity = max(1, int(payload.get("quantity", 1) or 1))

    required_pricing_fields = ("series", "bore", "rod_diameter", "mount", "stroke")
    if engine is not None and all(payload.get(name) not in (None, "") for name in required_pricing_fields):
        inputs = quote_inputs_from_payload(payload)
        breakdown = calculate_payload(engine, payload)
        quote.discount = inputs.discount
        quote.model_code = breakdown["model_code"]
        quote.cylinder_inputs_snapshot = decimal_to_json(asdict(inputs))
        quote.price_breakdown_snapshot = breakdown

    if "manual_line_items" in payload:
        # Full replacement keeps the implementation simple and still supports
        # add/edit/delete of manual items in a single call.
        quote.line_items.clear()
        line_items = _validate_manual_line_items(payload["manual_line_items"])
        for i, item in enumerate(line_items):
            quote.line_items.append(
                QuoteLineItem(
                    reference_part_number=item["reference_part_number"],
                    description=item["description"],
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],
                    extended_price=item["quantity"] * item["unit_price"],
                    internal_note=item["internal_note"],
                    show_on_customer_quote=item["show_on_customer_quote"],
                    sort_order=i,
                )
            )

    quote.revision += 1
    quote.edited_by_user_id = current_user.id
    quote.edited_at = utc_now()
    session.expire(quote, ["edited_by"])

    if getattr(current_user, "role", "employee") == "customer" and quote.assigned_employee_user_id is not None:
        quote.customer_update_pending = True

    upsert_customer(session, quote.customer_name, quote.customer_address, phone=quote.customer_contact)
    return quote


def duplicate_quote(session: Session, source: Quote, current_user) -> Quote:
    """Create a fresh draft copy of an existing quote snapshot.

    The new quote preserves the cylinder/pricing snapshots, customer fields,
    comments, and manual line items, but receives a new quote number and
    reset revision/status. Email/approval timestamps and documents are not
    copied.
    """
    new_quote = None
    last_error: Exception | None = None
    for _attempt in range(20):
        try:
            with session.begin_nested():
                new_quote = Quote(
                    quote_number=generate_quote_number(session, source.customer_name),
                    status="draft",
                    pricing_version=source.pricing_version or PRICING_VERSION,
                    revision=1,
                    quantity=max(1, int(source.quantity or 1)),
                    discount=source.discount,
                    model_code=source.model_code,
                    cylinder_inputs_snapshot=source.cylinder_inputs_snapshot,
                    price_breakdown_snapshot=source.price_breakdown_snapshot,
                    customer_name=source.customer_name,
                    customer_address=source.customer_address,
                    customer_contact=source.customer_contact,
                    customer_reference=source.customer_reference,
                    comments=source.comments,
                    special_instructions=source.special_instructions,
                    created_by_user_id=current_user.id,
                )
                for i, item in enumerate(source.line_items):
                    new_quote.line_items.append(
                        QuoteLineItem(
                            reference_part_number=item.reference_part_number,
                            description=item.description,
                            quantity=item.quantity,
                            unit_price=item.unit_price,
                            extended_price=item.extended_price,
                            internal_note=item.internal_note,
                            show_on_customer_quote=item.show_on_customer_quote,
                            sort_order=i,
                        )
                    )
                session.add(new_quote)
                session.flush()
            break
        except IntegrityError as exc:
            last_error = exc
            new_quote = None
            continue

    if new_quote is None:
        raise RuntimeError("Failed to duplicate quote with a unique quote number") from last_error
    return new_quote


def _line_item_to_json(item: QuoteLineItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "reference_part_number": item.reference_part_number,
        "description": item.description,
        "quantity": decimal_to_json(item.quantity),
        "unit_price": decimal_to_json(item.unit_price),
        "extended_price": decimal_to_json(item.extended_price),
        "internal_note": item.internal_note,
        "show_on_customer_quote": item.show_on_customer_quote,
        "sort_order": item.sort_order,
    }


def quote_to_json(quote: Quote) -> dict[str, Any]:
    """Serialize a Quote and its line items for API responses."""
    return {
        "id": quote.id,
        "quote_number": quote.quote_number,
        "status": quote.status,
        "pricing_version": quote.pricing_version,
        "revision": quote.revision,
        "quantity": max(1, int(quote.quantity or 1)),
        "model_code": quote.model_code,
        "discount": decimal_to_json(quote.discount),
        "customer_name": quote.customer_name,
        "customer_address": quote.customer_address,
        "customer_contact": quote.customer_contact,
        "reference_notes": quote.customer_reference,
        "comments": quote.comments,
        "special_instructions": quote.special_instructions,
        "order_form_snapshot": quote.order_form_snapshot,
        "cylinder_inputs_snapshot": quote.cylinder_inputs_snapshot,
        "price_breakdown_snapshot": quote.price_breakdown_snapshot,
        "manual_line_items": [_line_item_to_json(item) for item in quote.line_items],
        "created_by": quote.created_by.display_name if quote.created_by else None,
        "edited_by": quote.edited_by.display_name if quote.edited_by else None,
        "emailed_by": quote.emailed_by.display_name if quote.emailed_by else None,
        "approved_by": quote.approved_by.display_name if quote.approved_by else None,
        "created_at": quote.created_at.isoformat() if quote.created_at else None,
        "edited_at": quote.edited_at.isoformat() if quote.edited_at else None,
        "emailed_at": quote.emailed_at.isoformat() if quote.emailed_at else None,
        "approved_at": quote.approved_at.isoformat() if quote.approved_at else None,
    }
