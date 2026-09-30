from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from cylinder_quote_engine.data import PricingData, parse_dimension
from .service import ACCESSORY_NAMES


def _fmt(d: Decimal) -> str:
    s = format(d, "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


# Display order for the Standard Series dropdown.
STANDARD_SERIES_ORDER = ["H", "A", "LH", "MH", "HM", "VA", "W", "WA"]

# Display order for the Metric Series dropdown.
METRIC_SERIES_ORDER = ["IH", "IHM", "IMH"]

# Kept for callers that still build a compatibility catalog from both sources.
SERIES_ORDER = STANDARD_SERIES_ORDER + METRIC_SERIES_ORDER

# Display order for the Standard Mount dropdown.
STANDARD_MOUNT_ORDER = [
    "MF1", "MF2", "MF5", "MF6", "MP1", "MP2", "MP3", "MPU3",
    "MS2", "MS3", "MS4", "MS7", "MT1", "MT2", "MT4",
    "MX0", "MX1", "MX2", "MX3", "ME3", "ME4",
]

# Display order for the Metric Mount dropdown.
METRIC_MOUNT_ORDER = [
    "MF1", "MF2", "MF5", "MF6", "MP1", "MP2", "MP3", "MPU3",
    "MS2", "MS3", "MS4", "MS7", "MT1", "MT2", "MT4",
    "MX0", "MX1", "MX2", "MX3", "ME3", "ME4",
]

MOUNT_ORDER = STANDARD_MOUNT_ORDER


def _ordered(items, order):
    """Sort items by a preferred display order, appending any extras alphabetically."""
    items = set(items)
    return [x for x in order if x in items] + sorted(x for x in items if x not in order)


def _row_unit_system(row) -> str:
    value = str(row.get("unit_system") or row.get("system") or "").strip().lower()
    if value in {"metric", "mm"}:
        return "metric"
    if value in {"standard", "imperial", "inch", "in"}:
        return "standard"
    if str(row.get("stroke_unit", "")).strip().lower() == "mm":
        return "metric"
    return "standard"


def build_catalog(data: PricingData, series_pricing=None, unit_system=None) -> dict[str, Any]:
    if unit_system is None:
        if series_pricing is None:
            unit_system = "compatibility"
        else:
            source_units = {_row_unit_system(row) for row in series_pricing}
            unit_system = "metric" if source_units == {"metric"} else "standard"
    if series_pricing is None:
        if unit_system == "metric":
            series_pricing = data.metric_series_pricing
        elif unit_system == "standard":
            series_pricing = data.standard_series_pricing
        else:
            series_pricing = data.series_pricing

    is_metric = unit_system == "metric"
    series_order = METRIC_SERIES_ORDER if is_metric else SERIES_ORDER if unit_system == "compatibility" else STANDARD_SERIES_ORDER
    mount_order = METRIC_MOUNT_ORDER if is_metric else STANDARD_MOUNT_ORDER
    combos: dict[str, dict[str, dict[str, set[str]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))

    for row in series_pricing if series_pricing is not None else data.series_pricing:
        aliases = [x.strip().upper() for x in row.get("series_aliases", "").split("|") if x.strip()]
        bore = _fmt(parse_dimension(row["bore"]))
        rod = _fmt(parse_dimension(row["rod_diameter"]))
        mounts = [x.strip().upper() for x in row.get("mount_codes", "").split("|") if x.strip()]
        for series in aliases:
            combos[series][bore][rod].update(mounts)

    if not is_metric:
        for row in data.va_base:
            bore = _fmt(parse_dimension(row["bore"]))
            rod = _fmt(parse_dimension(row["rod_diameter"]))
            combos["VA"][bore][rod].update({"MX0", "MP1", "MP2", "MP3", "MPU3"})

    catalog = {}
    series_mounts = {}
    ordered_series = _ordered(combos.keys(), series_order)
    for series in ordered_series:
        catalog[series] = {}
        mount_union = set()
        for bore in sorted(combos[series], key=lambda x: Decimal(x)):
            catalog[series][bore] = {}
            for rod in sorted(combos[series][bore], key=lambda x: Decimal(x)):
                row_mounts = _ordered(combos[series][bore][rod], mount_order)
                catalog[series][bore][rod] = row_mounts
                mount_union.update(row_mounts)
        series_mounts[series] = _ordered(mount_union, mount_order)

    special_rows = [row for row in data.special_parts if _row_unit_system(row) == ("metric" if is_metric else "standard")]
    special_parts = sorted({r["part_number"].strip() for r in special_rows if r.get("part_number", "").strip()})
    special_part_details = {}
    for row in special_rows:
        part = row.get("part_number", "").strip()
        if not part:
            continue
        special_part_details[part] = {
            "description": row.get("description", "").strip(),
            "price": row.get("price", "").strip(),
        }

    return {
        "unit_system": unit_system,
        "stroke_unit": "mm" if is_metric else "in",
        "series": catalog,
        "series_mounts": series_mounts,
        "accessories": [] if is_metric else list(ACCESSORY_NAMES),
        "special_parts": special_parts,
        "special_part_details": special_part_details,
        "cushions": ["NC", "RE", "CE", "BE"] if is_metric else ["NC", "RE", "CE", "BE", "ARE", "ACE", "ABE"],
        "port_codes": ["N", "S", "F"],
        "seal_codes": ["B", "V", "L", "C", "H"] if is_metric else ["P", "B", "V", "L", "C", "H"],
        "rod_styles": [
            {"value": 1, "label": "1 - Standard"},
            {"value": 3, "label": "3 - Alternate standard"},
            {"value": 4, "label": "4 - Safety Coupler"},
            {"value": 5, "label": "5 - Special Threads"},
        ] if is_metric else [
            {"value": 1, "label": "1 - Standard"},
            {"value": 2, "label": "2 - Oversize"},
            {"value": 3, "label": "3 - Alternate standard"},
            {"value": 4, "label": "4 - Safety Coupler"},
            {"value": 5, "label": "5 - Special Threads"},
        ],
    }
