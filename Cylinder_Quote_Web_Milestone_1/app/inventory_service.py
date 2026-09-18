from __future__ import annotations

from decimal import ROUND_CEILING, Decimal, InvalidOperation
from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd
import openpyxl
from sqlalchemy import select

from .db import get_session, init_db
from .models_db import CatalogPart, InventoryPart, OrderFormInventoryRule, PartFamily, utc_now


class InventoryImportError(ValueError):
    pass


_INVENTORY_HEADERS = {
    "part_number": ("part number", "part no", "part #", "partnumber", "part", "item", "item number"),
    "product_description": ("product description", "description", "part name", "name"),
    "unit_price": ("unit price", "price", "unit cost"),
    "on_hand": ("on hand", "onhand", "qty on hand", "quantity on hand"),
    "allocated": ("allocated", "allocation"),
    "start_2025": ("start 2025", "start2025", "beginning inventory"),
    "on_order": ("on order", "onorder", "ordered"),
    "inventory": ("inventory", "in stock", "stock", "available", "available quantity"),
}


def _header_text(value) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _find_column(columns, candidates):
    normalized = {_header_text(column): column for column in columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None


def _number(value, field: str, row_number: int) -> Decimal | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError) as exc:
        raise InventoryImportError(
            f"Row {row_number}: {field} must be numeric."
        ) from exc


def _whole_inventory(value, field: str, row_number: int) -> int | None:
    number = _number(value, field, row_number)
    if number is None:
        return None
    return int(number.to_integral_value(rounding=ROUND_CEILING))


def _read_frame(source, filename: str):
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".csv":
        if hasattr(source, "read"):
            content = source.read()
            if isinstance(content, bytes):
                content = content.decode("utf-8-sig")
            return pd.read_csv(StringIO(content))
        return pd.read_csv(source)
    if suffix in {".xlsm", ".xlsx", ".xls"}:
        if suffix == ".xls":
            return pd.read_excel(source, sheet_name="Inventory")
        workbook = openpyxl.load_workbook(source, read_only=True, data_only=True, keep_vba=suffix == ".xlsm")
        if "Inventory" not in workbook.sheetnames:
            raise InventoryImportError("The workbook must contain an Inventory sheet.")
        worksheet = workbook["Inventory"]
        values = worksheet.values
        headers = next(values, None)
        if headers is None:
            raise InventoryImportError("The Inventory sheet is empty.")
        return pd.DataFrame(values, columns=headers).dropna(how="all")
    raise InventoryImportError("Inventory file must be a CSV, XLSX, or XLSM file.")


def parse_inventory_source(source, filename: str) -> list[dict]:
    """Read cached workbook values or CSV rows into normalized inventory records."""
    try:
        frame = _read_frame(source, filename)
    except ValueError as exc:
        raise InventoryImportError("The workbook must contain an Inventory sheet.") from exc
    except (OSError, ImportError) as exc:
        raise InventoryImportError(f"Unable to read inventory file: {exc}") from exc

    part_column = _find_column(frame.columns, _INVENTORY_HEADERS["part_number"])
    if part_column is None:
        raise InventoryImportError("Inventory file must contain a Part Number column.")

    columns = {
        field: _find_column(frame.columns, candidates)
        for field, candidates in _INVENTORY_HEADERS.items()
    }
    rows = []
    for index, record in frame.iterrows():
        row_number = int(index) + 2
        part_number = str(record[part_column]).strip() if not pd.isna(record[part_column]) else ""
        if not part_number or part_number.lower() == "nan":
            continue
        values = {
            field: _number(record[column], field, row_number) if column else None
            for field, column in columns.items()
            if field not in {"part_number", "product_description"}
        }
        if columns["product_description"]:
            description_value = record[columns["product_description"]]
            description = None if pd.isna(description_value) else str(description_value).strip() or None
        else:
            description = None
        if values["inventory"] is None and values["on_hand"] is not None:
            values["inventory"] = values["on_hand"] - (values["allocated"] or Decimal("0"))
        if values["inventory"] is None:
            raise InventoryImportError(
                f"Row {row_number}: Inventory or On Hand is required for {part_number}."
            )
        values["inventory"] = _whole_inventory(values["inventory"], "inventory", row_number)
        rows.append({"part_number": part_number, "product_description": description, **values})
    return rows


def inventory_rows_json(rows: list[dict]) -> list[dict]:
    return [
        {
            key: (
                str(value)
                if isinstance(value, Decimal)
                else value
            )
            for key, value in row.items()
        }
        for row in rows
    ]


def upsert_inventory_rows(rows: list[dict], source_name: str = "", updated_by: str | None = None) -> dict[str, int]:
    """Persist normalized inventory rows in Inventory.db."""
    init_db()
    created = 0
    updated = 0
    with get_session() as session:
        for values in rows:
            part_number = values["part_number"]
            row = session.execute(
                select(InventoryPart).where(InventoryPart.part_number == part_number)
            ).scalar_one_or_none()
            if row is None:
                row = InventoryPart(part_number=part_number, inventory=0)
                session.add(row)
                created += 1
            else:
                updated += 1
            for field in (
                "product_description",
                "allocated",
                "start_2025",
                "on_order",
                "inventory",
            ):
                setattr(row, field, values.get(field))
            if source_name:
                row.source_name = source_name
            if updated_by:
                row.updated_by = updated_by
            row.updated_at = utc_now()
            catalog_part = session.execute(
                select(CatalogPart).where(CatalogPart.part_number == part_number)
            ).scalar_one_or_none()
            if catalog_part is None:
                session.add(
                    CatalogPart(
                        part_number=part_number,
                        description=values.get("product_description"),
                        active="YES",
                    )
                )
        session.commit()
    return {"created": created, "updated": updated, "total": len(rows)}


def sync_catalog_parts_to_inventory() -> int:
    """Create zero-quantity inventory rows for catalog parts not yet imported."""
    init_db()
    with get_session() as session:
        catalog_numbers = set(session.execute(select(CatalogPart.part_number)).scalars())
        inventory_numbers = set(session.execute(select(InventoryPart.part_number)).scalars())
        missing = sorted(catalog_numbers - inventory_numbers)
        for part_number in missing:
            session.add(InventoryPart(part_number=part_number, inventory=0))
        if missing:
            session.commit()
        return len(missing)


def _format_allocated(value, allocation_category: str = "") -> str:
    if value is None:
        return ""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    if allocation_category == "length_based":
        return f"{number:.3f}".rstrip("0").rstrip(".")
    return f"{number:.0f}"


def _inventory_dict(row: InventoryPart, catalog_part=None, family=None, allocation_category: str = "") -> dict:
    if not allocation_category and (row.product_description or "").strip().casefold() in {"rod", "barrel", "tie rod"}:
        allocation_category = "length_based"
    return {
        "part_number": row.part_number,
        "product_description": catalog_part.description if catalog_part is not None else "",
        "family_code": (catalog_part.family_code if catalog_part is not None else None) or "",
        "family_name": (family.display_name if family is not None else None) or "",
        "allocated": _format_allocated(row.allocated, allocation_category),
        "allocation_category": allocation_category,
        "start_2025": str(row.start_2025) if row.start_2025 is not None else "",
        "on_order": str(row.on_order) if row.on_order is not None else "",
        "source_name": row.source_name or "",
        "inventory": str(row.inventory) if row.inventory is not None else "",
        "updated_by": row.updated_by or "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }


def search_inventory(query: str = "", limit: int = 10000) -> list[dict]:
    sync_catalog_parts_to_inventory()
    init_db()
    text = (query or "").strip()
    with get_session() as session:
        rows = session.execute(
            select(InventoryPart).order_by(InventoryPart.part_number)
        ).scalars().all()
        part_numbers = [row.part_number for row in rows]
        catalog_parts = {
            part.part_number: part
            for part in session.execute(
                select(CatalogPart).where(CatalogPart.part_number.in_(part_numbers))
            ).scalars()
        }
        family_codes = {part.family_code for part in catalog_parts.values() if part.family_code}
        families = {
            family.family_code: family
            for family in session.execute(
                select(PartFamily).where(PartFamily.family_code.in_(family_codes))
            ).scalars()
        } if family_codes else {}
        allocation_categories = {
            rule.part_number: rule.category or ""
            for rule in session.execute(select(OrderFormInventoryRule)).scalars()
        }
        result = [
            _inventory_dict(
                row,
                catalog_parts.get(row.part_number),
                families.get(catalog_parts.get(row.part_number).family_code)
                if catalog_parts.get(row.part_number) and catalog_parts.get(row.part_number).family_code
                else None,
                allocation_categories.get(row.part_number, ""),
            )
            for row in rows
        ]
        result.sort(key=lambda item: (item["family_name"].casefold(), item["family_code"].casefold(), item["part_number"].casefold()))
        if text:
            folded = text.casefold()
            result = [
                item for item in result
                if folded in item["part_number"].casefold()
                or folded in item["product_description"].casefold()
                or folded in item["family_code"].casefold()
                or folded in item["family_name"].casefold()
            ]
        return result[:max(1, min(limit, 10000))]


def update_inventory_quantity(part_number: str, value, updated_by: str | None = None) -> dict:
    text = (part_number or "").strip()
    if not text:
        raise InventoryImportError("Part Number is required.")
    quantity = _whole_inventory(value, "inventory", 0)
    if quantity is None or quantity < 0:
        raise InventoryImportError("Inventory must be a non-negative number.")
    init_db()
    with get_session() as session:
        row = session.execute(
            select(InventoryPart).where(InventoryPart.part_number == text)
        ).scalar_one_or_none()
        if row is None:
            raise InventoryImportError(f"Part number '{text}' was not found.")
        row.inventory = quantity
        if updated_by:
            row.updated_by = updated_by
        row.updated_at = utc_now()
        session.commit()
        return _inventory_dict(row)
