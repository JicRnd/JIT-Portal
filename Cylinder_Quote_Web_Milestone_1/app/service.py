from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from cylinder_quote_engine import QuoteInputs, QuotePricingEngine
from cylinder_quote_engine.data import parse_dimension
from cylinder_quote_engine.engine import excel_roundup

from dimensions.cylinder_dimension_tables import get_cylinder_dimensions

D = Decimal


def compute_profit(working_net_each: Decimal) -> Decimal:
    """Data!D7: =ROUNDUP(D6-(IF(D6<1000,D6*0.4,D6*0.27)+Inventory!E1),0)

    D6 is working_net_each (already computed by the pricing engine).
    TODO: Inventory!E1 is a large per-quote allocated component cost lookup
    (~130 accessory/rod-hardware/seal categories keyed off accessory
    quantities, special parts, rod diameter, series, and Y/N options) that
    has not been reverse-engineered/wired in yet, so it is treated as $0.
    """
    margin_rate = D('0.4') if working_net_each < D('1000') else D('0.27')
    inventory_cost = D('0')
    return excel_roundup(working_net_each - (working_net_each * margin_rate) - inventory_cost, 0)

ACCESSORY_NAMES = [
    "Rod Clevis",
    "Rod Eye",
    "Self-Aligning Male Eye",
    "SA - Clevis Bracket",
    "Alignment Coupler",
    "Male Rod Eye",
    "Eye Bracket",
    "Pivot Pin",
    "Safety Coupler",
    "Rod Stud",
    "Jam Nut",
    "Clevis Bracket",
    "SA - Pivot Pin",
    "Weld Plate",
]

BOOLEAN_FIELDS = {
    "dre",
    "stainless_rod",
    "chrome_bore",
    "rod_gland_drain",
    "brass_wiper",
    "ultraox",
    "transducer",
    "prepped_for_transducer",
    "sensor_cover",
    "valve_manifold",
}

DECIMAL_FIELDS = {
    "bore",
    "rod_diameter",
    "stroke",
    "discount",
    "rod_extension",
    "stop_tube",
    "extra_thread",
    "air_bleed_qty",
    "prox_switch_qty",
    "extra_port_qty",
    "extra_tie_rod_qty",
    "thick_head_qty",
    "standard_rod_boot_qty",
    "legacy_post_discount_add",
    "legacy_reserved_add",
}


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _decimal(value: Any, field_name: str) -> Decimal:
    if value in (None, ""):
        return D("0")
    try:
        return parse_dimension(value)
    except (InvalidOperation, ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc


def _mapping_decimals(value: Any, field_name: str) -> dict[str, Decimal]:
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    out: dict[str, Decimal] = {}
    for key, raw in value.items():
        qty = _decimal(raw, f"{field_name}.{key}")
        if qty != 0:
            out[str(key)] = qty
    return out


def quote_inputs_from_payload(payload: dict[str, Any]) -> QuoteInputs:
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")

    required = ["series", "bore", "rod_diameter", "mount", "stroke"]
    missing = [name for name in required if payload.get(name) in (None, "")]
    if missing:
        raise ValueError("missing required fields: " + ", ".join(missing))

    kwargs: dict[str, Any] = {
        "series": str(payload["series"]).strip().upper(),
        "bore": _decimal(payload["bore"], "bore"),
        "rod_diameter": _decimal(payload["rod_diameter"], "rod_diameter"),
        "mount": str(payload["mount"]).strip().upper(),
        "stroke": _decimal(payload["stroke"], "stroke"),
        "cushion": str(payload.get("cushion", "NC")).strip().upper() or "NC",
        "port_code": str(payload.get("port_code", "")).strip().upper(),
        "seal_code": str(payload.get("seal_code", "")).strip().upper(),
        "rod_style": int(payload.get("rod_style", 1) or 1),
        "accessory_quantities": _mapping_decimals(payload.get("accessory_quantities", {}), "accessory_quantities"),
        "special_parts": _mapping_decimals(payload.get("special_parts", {}), "special_parts"),
    }

    for name in BOOLEAN_FIELDS:
        kwargs[name] = _bool(payload.get(name, False))
    for name in DECIMAL_FIELDS:
        if name in {"bore", "rod_diameter", "stroke"}:
            continue
        kwargs[name] = _decimal(payload.get(name, 0), name)

    return QuoteInputs(**kwargs)


def decimal_to_json(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        return {k: decimal_to_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decimal_to_json(v) for v in value]
    return value


def _calculate_dimensions(series: str, bore: Decimal, stroke: Decimal) -> dict[str, Any]:
    """Return cylinder dimensions from the authoritative Python lookup table."""
    missing = {
        "e": None, "g": None, "j": None, "lb": None,
        "tf": None, "r": None, "fb": None, "f": None,
        "warning": "No dimension data for this series/bore",
    }
    try:
        dims = get_cylinder_dimensions(series, bore, stroke)
    except ValueError:
        return missing

    return {k: decimal_to_json(v) for k, v in dims.items()}


def calculate_payload(engine: QuotePricingEngine, payload: dict[str, Any]) -> dict[str, Any]:
    inputs = quote_inputs_from_payload(payload)
    result = engine.calculate(inputs)
    out = {k: decimal_to_json(v) for k, v in asdict(result).items()}
    out["profit"] = decimal_to_json(compute_profit(result.working_net_each))
    out["dimensions"] = _calculate_dimensions(inputs.series, inputs.bore, inputs.stroke)
    return out


CYLINDER_INPUT_FIELDS = {
    "series",
    "bore",
    "rod_diameter",
    "mount",
    "stroke",
    "cushion",
    "port_code",
    "seal_code",
    "rod_style",
    "accessory_quantities",
    "special_parts",
    "dre",
    "stainless_rod",
    "chrome_bore",
    "rod_gland_drain",
    "brass_wiper",
    "ultraox",
    "transducer",
    "prepped_for_transducer",
    "sensor_cover",
    "valve_manifold",
    "discount",
    "rod_extension",
    "stop_tube",
    "extra_thread",
    "air_bleed_qty",
    "prox_switch_qty",
    "extra_port_qty",
    "extra_tie_rod_qty",
    "thick_head_qty",
    "standard_rod_boot_qty",
    "legacy_post_discount_add",
    "legacy_reserved_add",
}


def _sanitize_presentation_field(value: Any, max_length: int = 500) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text[:max_length]


def _validate_manual_items(raw_items: Any) -> list[dict[str, Any]]:
    if raw_items in (None, ""):
        return []
    if not isinstance(raw_items, list):
        raise ValueError("manual_items must be an array")

    validated: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_items):
        if not isinstance(item, dict):
            raise ValueError(f"manual_items[{idx}] must be an object")

        description = str(item.get("description", "")).strip()
        if not description:
            raise ValueError(f"manual_items[{idx}]: description is required")

        quantity = _decimal(item.get("quantity", 0), f"manual_items[{idx}].quantity")
        if quantity <= 0:
            raise ValueError(f"manual_items[{idx}]: quantity must be greater than 0")

        unit_price = _decimal(item.get("unit_price", 0), f"manual_items[{idx}].unit_price")
        if unit_price < 0:
            raise ValueError(f"manual_items[{idx}]: unit_price must be non-negative")

        part_number = str(item.get("part_number", "")).strip() or None
        note = str(item.get("note", "")).strip() or None
        extended_price = quantity * unit_price

        validated.append(
            {
                "part_number": part_number,
                "description": description,
                "quantity": decimal_to_json(quantity),
                "unit_price": decimal_to_json(unit_price),
                "extended_price": decimal_to_json(extended_price),
                "note": note,
            }
        )
    return validated


def build_quote_draft(engine: QuotePricingEngine, payload: dict[str, Any]) -> dict[str, Any]:
    """Build a non-persistent quote draft using authoritative server-side pricing.

    Validates manual line items and presentation fields, reuses the same pricing
    calculation as /api/calculate, and returns a snapshot suitable for the Quote
    Form page.  No database or filesystem writes are performed.
    """
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")

    price_breakdown = calculate_payload(engine, payload)
    manual_items = _validate_manual_items(payload.get("manual_items"))

    presentation = {
        "customer_name": _sanitize_presentation_field(payload.get("customer_name")),
        "customer_contact": _sanitize_presentation_field(payload.get("customer_contact")),
        "customer_reference": _sanitize_presentation_field(payload.get("customer_reference")),
        "comments": _sanitize_presentation_field(payload.get("comments")),
    }

    cylinder_inputs = {k: payload[k] for k in CYLINDER_INPUT_FIELDS if k in payload}

    return {
        "cylinder_inputs": cylinder_inputs,
        "model_code": price_breakdown["model_code"],
        "price_breakdown": price_breakdown,
        "manual_items": manual_items,
        "presentation": presentation,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pricing_engine_version": "Pricing Engine v1.2",
    }


def make_engine(project_root: Path) -> QuotePricingEngine:
    return QuotePricingEngine(project_root / "data")
