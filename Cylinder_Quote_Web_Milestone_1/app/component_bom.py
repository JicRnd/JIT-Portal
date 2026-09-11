from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select

from .db import get_pricing_engine, get_session
from .models_db import CatalogPart


_SEAL_PARTS = {
    "B": ("PB", "BB"),
    "P": ("PP", "BB"),
    "V": ("PV", "BV"),
    "L": ("PL", "BB"),
    "C": ("PC", "BB"),
    "H": ("PV", "BV"),
}


def _dimension_key(value: Any, multiplier: int) -> str:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return ""
    return str(int(number * multiplier))


def _catalog() -> dict[str, CatalogPart]:
    get_pricing_engine()
    with get_session() as session:
        rows = session.execute(select(CatalogPart)).scalars().all()
        return {row.part_number: row for row in rows if row.part_number}


def generated_cylinder_parts(inputs: dict[str, Any]) -> list[dict[str, str]]:
    series = str(inputs.get("series") or "").strip().upper()
    bore = _dimension_key(inputs.get("bore"), 10)
    rod = _dimension_key(inputs.get("rod_diameter"), 100)
    if not series or not bore or not rod:
        return []

    seal = _SEAL_PARTS.get(str(inputs.get("seal_code") or "").strip().upper())
    if not seal:
        return []

    candidates = [
        f"TR{bore.zfill(3)}",
        f"R{rod}",
        f"{series}{bore}B",
        f"TRN{bore.zfill(3)}",
        f"{series}{bore}{seal[0]}",
        f"{series}{bore}{seal[1]}",
        f"{rod}RWP",
        f"{rod}GP" if seal[0] == "PP" else f"{rod}G{seal[0][-1]}",
        f"PIB{rod}",
        f"GBO{rod}",
        f"G{rod}",
        f"{series}{bore}P{rod}",
    ]

    mount = str(inputs.get("mount") or "").strip().upper()
    if mount:
        candidates.append(f"{series}{bore}{mount}")
    if mount not in {"MX0", "MX1", "MX2", "MX3"}:
        candidates.extend((f"{series}{bore}REH{rod}", f"{series}{bore}CEH"))

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
            "on_hand": "0",
            "allocated": "1",
        })
    return parts