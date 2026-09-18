from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import select

from .db import get_pricing_engine, get_session
from .models_db import TieRodRule


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _codes(value: str) -> set[str]:
    return {code.strip().upper() for code in value.split("|") if code.strip()}


def calculate_tie_rod_requirement(
    inputs: dict[str, Any],
    quantity: int = 1,
) -> dict[str, Decimal] | None:
    """Return the TieRod-sheet length and four-rod requirement for an order."""
    TieRodRule.__table__.create(bind=get_pricing_engine(), checkfirst=True)
    series = str(inputs.get("series") or "").strip().upper()
    mount = str(inputs.get("mount") or "").strip().upper()
    bore = _decimal(inputs.get("bore"))
    stroke = _decimal(inputs.get("stroke"))
    extra = _decimal(inputs.get("extra_tie_rod_qty")) or Decimal("0")
    if not series or not mount or bore is None or stroke is None:
        return None

    with get_session() as session:
        rules = session.execute(
            select(TieRodRule).where(TieRodRule.bore == bore)
        ).scalars().all()

    rule = next(
        (
            row
            for row in rules
            if series in _codes(row.series_codes)
            and mount in _codes(row.mount_codes)
            and row.assembly_length is not None
        ),
        None,
    )
    if rule is None:
        return None

    length = stroke + Decimal(str(rule.assembly_length)) + extra
    rods = length * Decimal(str(max(1, int(quantity or 1)))) * Decimal("4")
    return {"length": length, "allocated": rods}


def import_tie_rod_rules_from_json(path: Path) -> int:
    """Load the verified normalized TieRod sheet rows into Pricing.db."""
    data = json.loads(path.read_text(encoding="utf-8"))
    rules = [
        item for item in data["tie_rod_rules"]
        if item.get("assembly_length") is not None
    ]
    TieRodRule.__table__.create(bind=get_pricing_engine(), checkfirst=True)
    with get_session() as session:
        session.query(TieRodRule).delete()
        for item in rules:
            session.add(
                TieRodRule(
                    source_row=item["source_row"],
                    series_codes="|".join(item["series"]),
                    bore=item["bore"],
                    rod_diameter=item.get("rod"),
                    mount_codes="|".join(item["mounts"]),
                    tie_rod_diameter=item.get("tie_rod_diameter"),
                    rod_end_thread_length=item.get("rod_end_thread_length"),
                    cap_end_thread_length=item.get("cap_end_thread_length"),
                    k_rod_end=item.get("k_rod_end"),
                    k_cap_end=item.get("k_cap_end"),
                    through_rod=item.get("through_rod"),
                    through_cap=item.get("through_cap"),
                    assembly_length=item.get("assembly_length"),
                    assembly_formula=item.get("assembly_formula"),
                    source_workbook=data["source_workbook"],
                    source_sheet=data["source_sheet"],
                )
            )
        session.commit()
    return len(rules)