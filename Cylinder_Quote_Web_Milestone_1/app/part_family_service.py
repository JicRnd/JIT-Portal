"""Admin-defined part families for the Pricing Catalog.

A family holds one representative image plus one reusable description template
(for example ``GV`` = Viton/FKM Rod Seal) so an admin does not have to type a
description for every part. Nothing here touches pricing values.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import func, select
from werkzeug.utils import secure_filename

from .db import get_session
from .models_db import CatalogPart, PartFamily


FAMILY_IMAGE_DIRECTORY = Path(__file__).resolve().parent / "static" / "family_images"
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_IMAGE_BYTES = 2 * 1024 * 1024

TEMPLATE_VARIABLES = ("part_number", "size", "family", "material", "part_type")
_PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")
_LEADING_DIGITS_RE = re.compile(r"^(\d+)")

# Size-decoding rules the admin can pick per family. Nothing is decoded until a
# rule is configured for that family.
SIZE_RULES = {
    "none": "No automatic size",
    "prefix_hundredths": "Leading digits / 100 (062 -> 0.625, 100 -> 1.000)",
    "prefix_thousandths": "Leading digits / 1000 (0625 -> 0.625)",
    "prefix_sixteenths": "Leading digits / 16 (10 -> 0.625)",
    "regex": "Custom: regex:<pattern>:<divisor>",
}
# Tolerance used when snapping a truncated decimal (062 -> 0.62) back to the
# exact fractional inch size it abbreviates (0.625).
_SNAP_TOLERANCE = 0.01


class FamilyError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _clean(value) -> str | None:
    value = (str(value) if value is not None else "").strip()
    return value or None


def _truthy(value) -> bool:
    return value in (True, "true", "True", "on", "yes", "YES", "1", 1)


# --- Size decoding -------------------------------------------------------

def _snap_to_fraction(value: float) -> float | None:
    """Snap a truncated decimal to the sixteenth-inch size it abbreviates."""
    candidate = round(value * 16) / 16
    if abs(candidate - value) <= _SNAP_TOLERANCE:
        return candidate
    return None


def decode_size(part_number: str, size_rule: str | None) -> float | None:
    """Return the decoded size for a part, or None when it cannot be decoded."""
    rule = (size_rule or "").strip()
    part_number = (part_number or "").strip()
    if not rule or rule == "none" or not part_number:
        return None

    if rule.startswith("regex:"):
        _, _, remainder = rule.partition("regex:")
        pattern, _, divisor_text = remainder.rpartition(":")
        if not pattern:
            pattern, divisor_text = remainder, "1"
        try:
            match = re.search(pattern, part_number)
            divisor = float(divisor_text or 1)
        except (re.error, ValueError):
            return None
        if not match or divisor == 0:
            return None
        raw = match.groupdict().get("size") or (match.group(1) if match.groups() else None)
        try:
            return float(raw) / divisor if raw is not None else None
        except (TypeError, ValueError):
            return None

    digits = _LEADING_DIGITS_RE.match(part_number)
    if not digits:
        return None
    number = float(digits.group(1))
    if rule == "prefix_thousandths":
        return number / 1000
    if rule == "prefix_sixteenths":
        return number / 16
    if rule == "prefix_hundredths":
        return _snap_to_fraction(number / 100)
    return None


def format_size(size: float | None) -> str | None:
    return None if size is None else f"{size:.3f}"


# --- Description templates ----------------------------------------------

def _field(family, name, default=None):
    """Read a family field from either an ORM row or a serialized dict."""
    if family is None:
        return default
    if isinstance(family, dict):
        return family.get(name, default)
    return getattr(family, name, default)


def render_description(family, part, size: float | None) -> str | None:
    """Render the family's template for one part, or None when unresolvable."""
    template = (_field(family, "description_template") or "").strip()
    if not template:
        return None
    values = {
        "part_number": part.part_number or "",
        "size": format_size(size),
        "family": _field(family, "display_name") or _field(family, "family_code"),
        "material": _field(family, "material") or "",
        "part_type": _field(family, "part_type") or "",
    }
    used = _PLACEHOLDER_RE.findall(template)
    for name in used:
        if name not in TEMPLATE_VARIABLES:
            raise FamilyError(f"Unknown template variable '{{{name}}}'.")
        if values.get(name) in (None, ""):
            # Never guess a missing value - leave the part for admin review.
            return None
    return _PLACEHOLDER_RE.sub(lambda match: values[match.group(1)], template)


def family_headline(family) -> str:
    """Short family-level line for the catalog band (never part specific)."""
    template = (_field(family, "description_template") or "").strip()
    if template and not any(f"{{{name}}}" in template for name in ("part_number", "size")):
        values = {
            "family": _field(family, "display_name") or _field(family, "family_code"),
            "material": _field(family, "material") or "",
            "part_type": _field(family, "part_type") or "",
        }
        if all(values.get(name) for name in _PLACEHOLDER_RE.findall(template)):
            return _PLACEHOLDER_RE.sub(lambda match: values[match.group(1)], template)
    parts = [_field(family, "material"), _field(family, "part_type")]
    return " \u00b7 ".join(part for part in parts if part)


def describe_part(family, part) -> dict:
    """Display metadata for one part under its family (no data is written)."""
    size_rule = _field(family, "size_rule") or "none"
    size = decode_size(part.part_number, size_rule)
    generated = None
    if family is not None and _field(family, "auto_description_enabled"):
        try:
            generated = render_description(family, part, size)
        except FamilyError:
            generated = None
    return {
        "size": size,
        "size_display": f"{format_size(size)} in" if size is not None else None,
        "size_unresolved": size is None and size_rule != "none",
        "generated_description": generated,
        "display_description": generated or part.description or "",
    }


# --- Persistence ---------------------------------------------------------

def _validate_family_payload(data: dict) -> dict:
    family_code = _clean(data.get("family_code"))
    if not family_code:
        raise FamilyError("Family code is required.")
    if not re.fullmatch(r"[A-Za-z0-9_\-]{1,40}", family_code):
        raise FamilyError("Family code may only contain letters, numbers, dashes and underscores.")
    display_name = _clean(data.get("display_name"))
    if not display_name:
        raise FamilyError("Display name is required.")

    size_rule = _clean(data.get("size_rule")) or "none"
    if size_rule not in SIZE_RULES and not size_rule.startswith("regex:"):
        raise FamilyError("Choose a supported size-decoding rule.")

    template = _clean(data.get("description_template"))
    if template:
        for name in _PLACEHOLDER_RE.findall(template):
            if name not in TEMPLATE_VARIABLES:
                raise FamilyError(f"Unknown template variable '{{{name}}}'.")

    auto_enabled = _truthy(data.get("auto_description_enabled"))
    if auto_enabled and not template:
        raise FamilyError("Enter a description template before enabling automatic descriptions.")
    if auto_enabled and template and "{size}" in template and size_rule == "none":
        raise FamilyError("Configure a size-decoding rule before using {size} automatically.")

    return {
        "family_code": family_code.upper(),
        "display_name": display_name,
        "material": _clean(data.get("material")),
        "part_type": _clean(data.get("part_type")),
        "description_template": template,
        "size_rule": size_rule,
        "auto_description_enabled": auto_enabled,
    }


def _family_json(family) -> dict:
    return {
        "id": family.id,
        "family_code": family.family_code,
        "display_name": family.display_name,
        "material": family.material or "",
        "part_type": family.part_type or "",
        "image_path": family.image_path or "",
        "description_template": family.description_template or "",
        "size_rule": family.size_rule or "none",
        "auto_description_enabled": bool(family.auto_description_enabled),
    }


def list_families() -> list[dict]:
    with get_session() as session:
        rows = session.execute(
            select(PartFamily).order_by(PartFamily.display_name)
        ).scalars().all()
        counts = dict(
            session.execute(
                select(CatalogPart.family_code, func.count())
                .where(CatalogPart.family_code.is_not(None))
                .group_by(CatalogPart.family_code)
            ).all()
        )
        return [
            {**_family_json(row), "part_count": counts.get(row.family_code, 0)}
            for row in rows
        ]


def create_family(data: dict) -> dict:
    values = _validate_family_payload(data)
    with get_session() as session:
        existing = session.execute(
            select(PartFamily).filter_by(family_code=values["family_code"])
        ).scalar_one_or_none()
        if existing is not None:
            raise FamilyError(f"Family '{values['family_code']}' already exists.")
        family = PartFamily(**values)
        session.add(family)
        session.commit()
        return _family_json(family)


def update_family(family_id, data: dict) -> dict:
    values = _validate_family_payload(data)
    with get_session() as session:
        family = session.get(PartFamily, int(family_id))
        if family is None:
            raise FamilyError("Family not found.", 404)
        if values["family_code"] != family.family_code:
            clash = session.execute(
                select(PartFamily).filter_by(family_code=values["family_code"])
            ).scalar_one_or_none()
            if clash is not None:
                raise FamilyError(f"Family '{values['family_code']}' already exists.")
            session.execute(
                CatalogPart.__table__.update()
                .where(CatalogPart.family_code == family.family_code)
                .values(family_code=values["family_code"])
            )
        for field, value in values.items():
            setattr(family, field, value)
        session.commit()
        return _family_json(family)


def assign_parts(family_code, part_ids) -> dict:
    """Attach (or with an empty code, detach) catalog parts to a family."""
    code = _clean(family_code)
    ids = []
    for raw in part_ids or []:
        try:
            ids.append(int(raw))
        except (TypeError, ValueError) as exc:
            raise FamilyError("Invalid part selection.") from exc
    if not ids:
        raise FamilyError("Select at least one part.")

    with get_session() as session:
        if code:
            code = code.upper()
            family = session.execute(
                select(PartFamily).filter_by(family_code=code)
            ).scalar_one_or_none()
            if family is None:
                raise FamilyError(f"Family '{code}' does not exist.", 404)
        session.execute(
            CatalogPart.__table__.update()
            .where(CatalogPart.id.in_(ids))
            .values(family_code=code)
        )
        session.commit()
        return {"family_code": code, "assigned": len(ids)}


def preview_family(family_id, limit: int = 25) -> dict:
    """Show decoded sizes/descriptions so an admin can approve the rule."""
    with get_session() as session:
        family = session.get(PartFamily, int(family_id))
        if family is None:
            raise FamilyError("Family not found.", 404)
        parts = session.execute(
            select(CatalogPart)
            .where(CatalogPart.family_code == family.family_code)
            .order_by(CatalogPart.part_number)
            .limit(limit)
        ).scalars().all()
        rows = []
        unresolved = 0
        for part in parts:
            info = describe_part(family, part)
            if info["size"] is None:
                unresolved += 1
            rows.append({
                "part_number": part.part_number,
                "size_display": info["size_display"] or "Unresolved - needs review",
                "description": info["generated_description"] or (part.description or ""),
                "generated": info["generated_description"] is not None,
            })
        return {"family": _family_json(family), "rows": rows, "unresolved": unresolved}


def save_family_image(family_id, storage) -> dict:
    """Store one representative image locally under app/static/family_images."""
    if storage is None or not getattr(storage, "filename", ""):
        raise FamilyError("Choose an image file.")
    extension = Path(secure_filename(storage.filename)).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise FamilyError("Image must be a PNG, JPG, GIF or WEBP file.")
    data = storage.read()
    if not data:
        raise FamilyError("The uploaded image is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise FamilyError("Image must be 2 MB or smaller.")

    with get_session() as session:
        family = session.get(PartFamily, int(family_id))
        if family is None:
            raise FamilyError("Family not found.", 404)
        # Filename is derived from the family code only - never from the upload.
        filename = f"{family.family_code.lower()}{extension}"
        FAMILY_IMAGE_DIRECTORY.mkdir(parents=True, exist_ok=True)
        (FAMILY_IMAGE_DIRECTORY / filename).write_bytes(data)
        family.image_path = filename
        session.commit()
        return _family_json(family)
