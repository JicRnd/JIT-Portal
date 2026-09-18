from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import select

from .db import get_inventory_engine, get_pricing_engine, get_session
from .models_db import CatalogPart, InventoryPart
from .order_form_inventory import evaluate_database_inventory_rules
from .tie_rod_engine import calculate_tie_rod_requirement


_SEAL_PARTS = {
    "B": ("PB", "BB"),
    "P": ("PP", "BB"),
    "V": ("PV", "BV"),
    "L": ("PL", "BB"),
    "C": ("PC", "BB"),
    "H": ("PV", "BV"),
}

_STATIC_DIR = Path(__file__).with_name("static")
with (_STATIC_DIR / "sheet_h_engineering.json").open(encoding="utf-8") as _file:
    _H_ENGINEERING = json.load(_file)
with (_STATIC_DIR / "tierod_reference.json").open(encoding="utf-8") as _file:
    _TIE_ROD_REFERENCE = json.load(_file)


def _dimension_key(value: Any, multiplier: int) -> str:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return ""
    return str(int(number * multiplier))


def _tie_rod_key(series: str, bore: Decimal | None) -> str:
    if bore is None:
        return ""
    if series in {"H", "HM"}:
        for upper, key in (
            (Decimal("1.5"), "038"),
            (Decimal("2.5"), "050"),
            (Decimal("4"), "062"),
            (Decimal("5"), "087"),
            (Decimal("6"), "100"),
            (Decimal("7"), "112"),
            (Decimal("8"), "125"),
        ):
            if bore <= upper:
                return key
    return _dimension_key(bore, 10).zfill(3)


def _catalog() -> dict[str, CatalogPart]:
    get_pricing_engine()
    with get_session() as session:
        rows = session.execute(select(CatalogPart)).scalars().all()
        return {row.part_number: row for row in rows if row.part_number}


def enrich_parts_with_inventory(
    parts: list[dict[str, Any]],
    preserve_allocated: bool = False,
) -> list[dict[str, Any]]:
    """Overlay on-hand and allocated values from the authoritative Inventory.db."""
    part_numbers = {
        str(part.get("part_number") or "").strip()
        for part in parts
        if str(part.get("part_number") or "").strip()
    }
    if not part_numbers:
        return parts

    get_inventory_engine()
    with get_session() as session:
        rows = session.execute(
            select(InventoryPart).where(InventoryPart.part_number.in_(part_numbers))
        ).scalars().all()
        inventory = {row.part_number.casefold(): row for row in rows}

    enriched = []
    for part in parts:
        item = dict(part)
        row = inventory.get(str(part.get("part_number") or "").strip().casefold())
        if row is not None:
            item["on_hand"] = str(row.inventory)
            if row.allocated is not None and not preserve_allocated:
                item["allocated"] = str(row.allocated)
        enriched.append(item)
    return enriched


def _decimal_value(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _engineering_lengths(inputs: dict[str, Any]) -> dict[str, Decimal]:
    series = str(inputs.get("series") or "").strip().upper()
    family = "A" if series == "LH" else series
    bore = _decimal_value(inputs.get("bore"))
    rod = _decimal_value(inputs.get("rod_diameter"))
    stroke = _decimal_value(inputs.get("stroke"))
    if bore is None or rod is None or stroke is None:
        return {}

    cushion = str(inputs.get("cushion") or "").strip().upper()
    rod_style = int(inputs.get("rod_style") or 1)
    rod_rule = next(
        (
            rule
            for rule in _H_ENGINEERING.get("rod_addition_rules", [])
            if family in rule.get("families", [])
            and _decimal_value(rule.get("bore")) == bore
            and _decimal_value(rule.get("rod")) == rod
            and cushion in rule.get("cushions", [])
            and rod_style in rule.get("rod_styles", [])
        ),
        None,
    )
    barrel_rule = next(
        (
            rule
            for rule in _H_ENGINEERING.get("barrel_rules", [])
            if _decimal_value(rule.get("bore")) == bore
        ),
        None,
    )
    mount = str(inputs.get("mount") or "").strip().upper()
    tie_rule = next(
        (
            rule
            for rule in _TIE_ROD_REFERENCE.get("tie_rod_rules", [])
            if series in rule.get("series", [])
            and _decimal_value(rule.get("bore")) == bore
            and mount in rule.get("mounts", [])
            and rule.get("assembly_length") is not None
        ),
        None,
    )
    lengths: dict[str, Decimal] = {}
    if rod_rule:
        lengths["rod"] = stroke + Decimal(str(rod_rule["rod_length_addition"]))
    if barrel_rule:
        addition = barrel_rule.get("families", {}).get(family)
        if addition is not None:
            lengths["barrel"] = stroke + Decimal(str(addition))
    if tie_rule:
        extra = _decimal_value(inputs.get("extra_tie_rod_qty")) or Decimal("0")
        lengths["tie_rod"] = stroke + Decimal(str(tie_rule["assembly_length"])) + extra
    return lengths


def apply_dynamic_allocations(
    parts: list[dict[str, Any]],
    inputs: dict[str, Any],
    quantity: int = 1,
) -> list[dict[str, Any]]:
    """Apply workbook-derived current-order requirements to measured parts."""
    tie_rod_requirement = calculate_tie_rod_requirement(inputs, quantity=quantity)
    workbook_rules = evaluate_database_inventory_rules(inputs, quantity=quantity)
    if workbook_rules:
        allocations = {row["part_number"]: row for row in workbook_rules}
        series = str(inputs.get("series") or "").strip().upper()
        tie_rod_key = _tie_rod_key(series, _decimal_value(inputs.get("bore")))
        tie_rod_part = f"TR{tie_rod_key}"
        if tie_rod_requirement is not None:
            tie_rod_row = allocations.setdefault(
                tie_rod_part,
                {
                    "part_number": tie_rod_part,
                    "description": "Tie Rod",
                    "unit_price": None,
                        "category": "length_based",
                },
            )
            tie_rod_row["allocated"] = format(tie_rod_requirement["allocated"], "f")
        existing_numbers = {part.get("part_number") for part in parts}
        resolved = []
        for part in parts:
            item = dict(part)
            rule = allocations.get(part.get("part_number"))
            if rule is not None:
                item["allocated"] = rule["allocated"]
                item["allocation_category"] = rule.get("category") or "quantity_or_option_based"
            resolved.append(item)
        for part_number, rule in allocations.items():
            if part_number not in existing_numbers:
                resolved.append({
                    "part_number": part_number,
                    "description": rule.get("description") or "",
                    "unit_price": rule.get("unit_price"),
                    "cost": rule.get("unit_price"),
                    "on_hand": "0",
                    "allocated": rule["allocated"],
                    "allocation_category": rule.get("category") or "quantity_or_option_based",
                })
        return resolved

    lengths = _engineering_lengths(inputs)
    if not lengths:
        return parts

    series = str(inputs.get("series") or "").strip().upper()
    bore = _dimension_key(inputs.get("bore"), 10)
    rod = _dimension_key(inputs.get("rod_diameter"), 100)
    order_quantity = Decimal(str(max(1, int(quantity or 1))))
    tie_rod_key = _tie_rod_key(series, _decimal_value(inputs.get("bore")))
    measured_allocations = {
        f"R{rod}": lengths.get("rod", Decimal("0")) * order_quantity,
        f"{series}{bore}B": lengths.get("barrel", Decimal("0")) * order_quantity,
        f"TR{tie_rod_key}": lengths.get("tie_rod", Decimal("0")) * order_quantity * 4,
        f"TRN{tie_rod_key}": order_quantity * 8,
    }
    if tie_rod_requirement is not None:
        measured_allocations[f"TR{tie_rod_key}"] = tie_rod_requirement["allocated"]
    return [
        {**part, "allocated": format(measured_allocations[part["part_number"]], "f"), "allocation_category": "length_based"}
        if part.get("part_number") in measured_allocations
        and measured_allocations[part["part_number"]] != 0
        else part
        for part in parts
    ]


def apply_fixed_allocations(
    parts: list[dict[str, Any]],
    quantity: int = 1,
) -> list[dict[str, Any]]:
    """Apply workbook quantity rules to generated non-dimensional components."""
    order_quantity = Decimal(str(max(1, int(quantity or 1))))
    allocated = []
    for part in parts:
        item = dict(part)
        part_number = str(part.get("part_number") or "").upper()
        description = str(part.get("description") or "").lower()
        multiplier = Decimal("1")
        if "piston seal" in description and part_number.endswith("PL"):
            multiplier = Decimal("1")
        elif "piston seal" in description or "barrel seal" in description:
            multiplier = Decimal("2")
        item["allocated"] = format(order_quantity * multiplier, "f")
        item["allocation_category"] = "quantity_or_option_based"
        allocated.append(item)
    return allocated


def apply_allocated_costs(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace unit cost with the extended cost for each Order Form row."""
    extended = []
    for part in parts:
        item = dict(part)
        unit_cost = _decimal_value(part.get("unit_price", part.get("cost")))
        allocated = _decimal_value(part.get("allocated"))
        if unit_cost is not None and allocated is not None:
            item["unit_price"] = format(unit_cost, "f")
            item["cost"] = format(unit_cost * allocated, "f")
        extended.append(item)
    return extended


def sort_order_form_parts(
    parts: list[dict[str, Any]],
    limit: int = 31,
) -> list[dict[str, Any]]:
    """Preserve the workbook's parts sequence for Order Form display."""
    if limit <= 0:
        return []
    return [dict(part) for part in parts[:limit]]


def generated_cylinder_parts(inputs: dict[str, Any]) -> list[dict[str, str]]:
    series = str(inputs.get("series") or "").strip().upper()
    bore = _dimension_key(inputs.get("bore"), 10)
    rod = _dimension_key(inputs.get("rod_diameter"), 100)
    if not series or not bore or not rod:
        return []

    seal = _SEAL_PARTS.get(str(inputs.get("seal_code") or "").strip().upper())
    if not seal:
        return []

    tie_rod_key = _tie_rod_key(series, _decimal_value(inputs.get("bore")))
    candidates = [
        f"TR{tie_rod_key}",
        f"R{rod}",
        f"{series}{bore}B",
        f"TRN{tie_rod_key}",
        f"{series}{bore}{seal[0]}",
        f"{series}{bore}{seal[1]}",
        f"GTOB{rod}",
        f"{rod}RWP",
        f"{rod}GP" if seal[0] == "PP" else f"{rod}G{seal[0][-1]}",
        f"PIB{rod}",
        f"GBO{rod}",
        f"G{rod}",
    ]

    mount = str(inputs.get("mount") or "").strip().upper()
    if mount not in {"MX0", "MX1", "MX2", "MX3"}:
        candidates.extend((f"{series}{bore}REH{rod}", f"{series}{bore}CEH"))
    candidates.append(f"{series}{bore}P{rod}")

    if mount:
        candidates.append(f"{series}{bore}{mount}")

    catalog = _catalog()
    parts = []
    seen = set()
    for part_number in candidates:
        row = catalog.get(part_number)
        if not row or part_number in seen:
            continue
        seen.add(part_number)
        parts.append({
            "part_number": part_number,
            "description": row.description or "",
            "cost": str(row.unit_cost or "0"),
            "unit_price": str(row.unit_cost or "0"),
            "on_hand": "0",
            "allocated": "1",
        })
    return enrich_parts_with_inventory(parts)