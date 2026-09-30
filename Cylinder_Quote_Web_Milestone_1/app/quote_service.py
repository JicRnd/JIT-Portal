from __future__ import annotations

import logging
import time
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, select

from cylinder_quote_engine import QuotePricingEngine

from .component_bom import (
    apply_allocated_costs,
    apply_dynamic_allocations,
    apply_fixed_allocations,
    enrich_parts_with_inventory,
    generated_cylinder_parts,
    sort_order_form_parts,
)
from .models_db import Customer, Order, Quote, QuoteLineItem, utc_now
from .quote_numbering import generate_quote_number
from .service import (
    calculate_metric_assembly_price,
    calculate_metric_rod_seal_price,
    calculate_payload,
    decimal_to_json,
    quote_inputs_from_payload,
)

PRICING_VERSION = "v1.2"
_ACCESSORY_ENGINE = QuotePricingEngine(Path(__file__).resolve().parents[1] / "data")
logger = logging.getLogger(__name__)

_CONTACT_BUSINESS_TERMS = {
    "associates", "company", "construction", "consulting", "corp", "corporation",
    "design", "enterprises", "group", "holdings", "inc", "incorporated", "industries",
    "llc", "llp", "lp", "ltd", "manufacturing", "partners", "plc", "services",
    "solutions", "supply", "systems", "the", "&",
}
_CONTACT_PERSON_FIRST_NAMES = {
    "alex", "anna", "bob", "charles", "chris", "daniel", "david", "dr", "james",
    "jane", "jennifer", "john", "jordan", "joseph", "joshua", "kane", "laura",
    "lisa", "maria", "mary", "michael", "mike", "pat", "patrick", "paul", "robert",
    "sarah", "stephanie", "susan", "thomas", "william",
}


def classify_contact_name(value: str | None) -> tuple[str | None, str | None]:
    """Split a single imported contact label into company and optional POC fields."""
    name = (value or "").strip()
    if not name:
        return None, None

    words = name.lower().replace(",", " ").split()
    if any(word in _CONTACT_BUSINESS_TERMS for word in words) or "&" in name:
        return name, None

    person_shape = 2 <= len(words) <= 4 and words[0].rstrip(".") in _CONTACT_PERSON_FIRST_NAMES
    if person_shape:
        return None, name

    return name, None


def sync_order_status(session: Session, quote_id: int, status: str) -> None:
    order = session.execute(
        select(Order).where(Order.quote_id == quote_id)
    ).scalar_one_or_none()
    if order is not None:
        order.status = status
        session.add(order)


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


def upsert_customer(
    session: Session,
    name: str | None,
    address: str | None,
    phone: str | None,
    email: str | None = None,
    city_state_zip: str | None = None,
    company_name: str | None = None,
    poc: str | None = None,
) -> None:
    """Keep the saved customer directory current from a quote's presentation fields."""
    name = (name or "").strip()
    address = (address or "").strip() or None
    phone = (phone or "").strip() or None
    email = (email or "").strip() or None
    city_state_zip = (city_state_zip or "").strip() or None
    company_name = (company_name or "").strip() or None
    poc = (poc or "").strip() or None
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
        if company_name is not None:
            existing.company_name = company_name
        if poc is not None:
            existing.poc = poc
    else:
        session.add(
            Customer(
                name=name,
                company_name=company_name,
                poc=poc,
                address=address,
                phone=phone,
                email=email,
                city_state_zip=city_state_zip,
            )
        )


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
    person_of_contact = _optional_str(payload.get("person_of_contact"))
    customer_contact = _optional_str(payload.get("customer_contact"))
    customer_reference = _optional_str(payload.get("reference_notes"))
    comments = _optional_str(payload.get("comments"))
    special_instructions = _optional_str(payload.get("special_instructions"))
    quantity = max(1, int(payload.get("quantity", 1) or 1))
    inputs_snapshot = decimal_to_json(asdict(inputs))
    quote_form_edits = payload.get("quote_form_edits")
    order_form_snapshot = (
        {"quote_form_edits": quote_form_edits}
        if isinstance(quote_form_edits, dict)
        else None
    )

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
                    status="new",
                    pricing_version=PRICING_VERSION,
                    quantity=quantity,
                    discount=inputs.discount,
                    model_code=breakdown["model_code"],
                    cylinder_inputs_snapshot=inputs_snapshot,
                    price_breakdown_snapshot=breakdown,
                    customer_name=customer_name,
                    customer_address=customer_address,
                    person_of_contact=person_of_contact,
                    customer_contact=customer_contact,
                    customer_reference=customer_reference,
                    comments=comments,
                    special_instructions=special_instructions,
                    order_form_snapshot=order_form_snapshot,
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



def _manual_items_snapshot(quote: Quote) -> list[tuple[Any, ...]]:
    return [
        (
            item.reference_part_number,
            item.description,
            decimal_to_json(item.quantity),
            decimal_to_json(item.unit_price),
        )
        for item in quote.line_items
    ]


def _warm_order_form_snapshot(quote: Quote) -> list[dict[str, Any]]:
    parts = _order_form_parts(quote, apply_workbook_allocations=True)
    snapshot = dict(quote.order_form_snapshot or {})
    snapshot["order_form_parts"] = parts
    quote.order_form_snapshot = snapshot
    return parts


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

    previous_inputs = quote.cylinder_inputs_snapshot
    previous_quantity = quote.quantity
    previous_manual_items = _manual_items_snapshot(quote)

    if "customer_name" in payload:
        quote.customer_name = _optional_str(payload["customer_name"])
    if "customer_address" in payload:
        quote.customer_address = _optional_str(payload["customer_address"])
    if "person_of_contact" in payload:
        quote.person_of_contact = _optional_str(payload["person_of_contact"])
    if "customer_contact" in payload:
        quote.customer_contact = _optional_str(payload["customer_contact"])
    if "reference_notes" in payload:
        quote.customer_reference = _optional_str(payload["reference_notes"])
    if "comments" in payload:
        quote.comments = _optional_str(payload["comments"])
    if "special_instructions" in payload:
        quote.special_instructions = _optional_str(payload["special_instructions"])

    if "quote_form_edits" in payload and isinstance(payload["quote_form_edits"], dict):
        snapshot = dict(quote.order_form_snapshot or {})
        snapshot["quote_form_edits"] = payload["quote_form_edits"]
        quote.order_form_snapshot = snapshot

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
    current_manual_items = _manual_items_snapshot(quote)
    cache_missing = not isinstance((quote.order_form_snapshot or {}).get("order_form_parts"), list)
    parts_changed = (
        previous_inputs != quote.cylinder_inputs_snapshot
        or previous_quantity != quote.quantity
        or previous_manual_items != current_manual_items
    )
    if cache_missing or parts_changed:
        _warm_order_form_snapshot(quote)
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
                    status="new",
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


def _order_form_parts(quote: Quote, *, apply_workbook_allocations: bool) -> list[dict[str, Any]]:
    inputs = quote.cylinder_inputs_snapshot or {}
    started = time.perf_counter()
    generated_parts = generated_cylinder_parts(inputs)
    generated_elapsed = time.perf_counter() - started
    generated_parts = apply_fixed_allocations(
        generated_parts,
        quantity=max(1, int(quote.quantity or 1)),
    )
    special_parts = [
        {
            "part_number": part_number,
            "description": f"Quoted special part (Qty {quantity})",
            "cost": "0",
            "on_hand": "0",
            "allocated": decimal_to_json(quantity),
            "allocation_category": "quantity_or_option_based",
        }
        for part_number, quantity in (inputs.get("special_parts") or {}).items()
    ]
    manual_parts = [
        {
            "part_number": item.reference_part_number or "",
            "description": item.description or "",
            "cost": decimal_to_json(item.unit_price),
            "on_hand": "0",
            "allocated": decimal_to_json(item.quantity),
            "allocation_category": "quantity_or_option_based",
        }
        for item in quote.line_items
    ]
    order_form_parts = enrich_parts_with_inventory(
        generated_parts + special_parts + manual_parts
    )
    initial_inventory_elapsed = time.perf_counter() - started - generated_elapsed
    dynamic_started = time.perf_counter()
    if apply_workbook_allocations:
        order_form_parts = apply_dynamic_allocations(
            order_form_parts,
            inputs,
            quantity=max(1, int(quote.quantity or 1)),
        )
    dynamic_elapsed = time.perf_counter() - dynamic_started
    final_started = time.perf_counter()
    order_form_parts = enrich_parts_with_inventory(order_form_parts, preserve_allocated=True)
    order_form_parts = apply_allocated_costs(order_form_parts)
    result = sort_order_form_parts(order_form_parts)
    logger.info(
        "Order Form parts timing quote=%s workbook_allocations=%s generated=%.3fs initial_inventory=%.3fs dynamic_allocations=%.3fs finalization=%.3fs total=%.3fs rows=%s",
        quote.id,
        apply_workbook_allocations,
        generated_elapsed,
        initial_inventory_elapsed,
        dynamic_elapsed,
        time.perf_counter() - final_started,
        time.perf_counter() - started,
        len(result),
    )
    return result


def quote_to_json(quote: Quote, *, include_order_form_parts: bool = True) -> dict[str, Any]:
    """Serialize a Quote and its line items for general API responses."""
    inputs = quote.cylinder_inputs_snapshot or {}
    breakdown = dict(quote.price_breakdown_snapshot or {})
    if (
        str(inputs.get("series") or "").upper() in {"IH", "IHM", "IMH"}
        and "recommended_assembly_price" not in breakdown
    ):
        try:
            breakdown["recommended_assembly_price"] = decimal_to_json(
                calculate_metric_assembly_price(quote_inputs_from_payload(inputs))
            )
        except (ValueError, LookupError, KeyError):
            breakdown["recommended_assembly_price"] = None
    if (
        str(inputs.get("series") or "").upper() in {"IH", "IHM", "IMH"}
        and "recommended_rod_seal_price" not in breakdown
    ):
        try:
            breakdown["recommended_rod_seal_price"] = decimal_to_json(
                calculate_metric_rod_seal_price(quote_inputs_from_payload(inputs))
            )
        except (ValueError, LookupError, KeyError):
            breakdown["recommended_rod_seal_price"] = None
    try:
        accessory_parts = breakdown.get("accessory_parts")
        if not isinstance(accessory_parts, list):
            accessory_parts = _ACCESSORY_ENGINE.accessory_parts(
                quote_inputs_from_payload(inputs)
            )
        breakdown["accessory_parts"] = enrich_parts_with_inventory(
            [
                {
                    **part,
                    "description": part.get("label") or "",
                    "on_hand": part.get("on_hand") or "0",
                    "allocated": part.get("quantity") or "0",
                }
                for part in accessory_parts
            ]
        )
        for part, enriched in zip(accessory_parts, breakdown["accessory_parts"]):
            part["on_hand"] = enriched.get("on_hand", "0")
        breakdown["accessory_parts"] = accessory_parts
    except (KeyError, LookupError, ValueError):
        breakdown["accessory_parts"] = []
    generated_parts = generated_cylinder_parts(inputs)
    generated_parts = apply_fixed_allocations(
        generated_parts,
        quantity=max(1, int(quote.quantity or 1)),
    )
    order_form_parts = (
        _order_form_parts(quote, apply_workbook_allocations=False)
        if include_order_form_parts
        else []
    )
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
        "person_of_contact": quote.person_of_contact,
        "customer_contact": quote.customer_contact,
        "reference_notes": quote.customer_reference,
        "comments": quote.comments,
        "special_instructions": quote.special_instructions,
        "order_form_snapshot": quote.order_form_snapshot,
        "cylinder_inputs_snapshot": quote.cylinder_inputs_snapshot,
        "generated_parts": generated_parts,
        "order_form_parts": order_form_parts,
        "price_breakdown_snapshot": breakdown,
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


def quote_to_order_form_json(quote: Quote) -> dict[str, Any]:
    """Serialize a Quote for the Order Form workflow."""
    started = time.perf_counter()
    result = quote_to_json(quote)
    cached_parts = (quote.order_form_snapshot or {}).get("order_form_parts")
    cache_hit = isinstance(cached_parts, list)
    result["order_form_parts"] = (
        cached_parts
        if cache_hit
        else _order_form_parts(quote, apply_workbook_allocations=True)
    )
    logger.info(
        "Order Form serialization timing quote=%s cache_hit=%s total=%.3fs",
        quote.id,
        cache_hit,
        time.perf_counter() - started,
    )
    return result
