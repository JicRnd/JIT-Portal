"""Cylinder dimension reference tables for the H and A series families.

Values are stored as decimal.Decimal objects constructed from string literals
to avoid float rounding.  Unreadable values from the source screenshot are
left as ``None`` with a ``# TODO`` marker indicating the affected field/row.
"""

from decimal import Decimal


def _d(value):
    """Helper to build Decimal from a string literal."""
    return Decimal(value)


#: Dimension tables keyed by lowercase series family.
#: Each family maps bore (Decimal) -> row dict containing all required fields.
CYLINDER_DIMENSION_TABLES = {
    "h": {
        _d("1.5"): {
            "bore": _d("1.5"),
            "e": _d("2.5"),
            "g": _d("1.75"),
            "j": _d("1.5"),
            "lb_base": _d("4.63"),
            "f": _d("0.38"),
            "r": _d("1.63"),
            "fb": _d("0.44"),
            "tf": _d("3.44"),
        },
        _d("2"): {
            "bore": _d("2"),
            "e": _d("3"),
            "g": _d("1.75"),
            "j": _d("1.5"),
            "lb_base": _d("4.63"),
            "f": _d("0.63"),
            "r": _d("2.05"),
            "fb": _d("0.56"),
            "tf": _d("4.13"),
        },
        _d("2.5"): {
            "bore": _d("2.5"),
            "e": _d("3.5"),
            "g": _d("1.75"),
            "j": _d("1.5"),
            "lb_base": _d("4.75"),
            "f": _d("0.63"),
            "r": _d("2.55"),
            "fb": _d("0.56"),
            "tf": _d("4.63"),
        },
        _d("3.25"): {
            "bore": _d("3.25"),
            "e": _d("4.5"),
            "g": _d("2"),
            "j": _d("1.75"),
            "lb_base": _d("5.5"),
            "f": _d("0.75"),
            "r": _d("3.25"),
            "fb": _d("0.69"),
            "tf": _d("5.88"),
        },
        _d("4"): {
            "bore": _d("4"),
            "e": _d("5"),
            "g": _d("2"),
            "j": _d("1.75"),
            "lb_base": _d("5.75"),
            "f": _d("0.88"),
            "r": _d("3.82"),
            "fb": _d("0.69"),
            "tf": _d("6.38"),
        },
        _d("5"): {
            "bore": _d("5"),
            "e": _d("6.5"),
            "g": _d("2"),
            "j": _d("1.75"),
            "lb_base": _d("6.25"),
            "f": _d("0.88"),
            "r": _d("4.95"),
            "fb": _d("0.94"),
            "tf": _d("8.19"),
        },
        _d("6"): {
            "bore": _d("6"),
            "e": _d("7.5"),
            "g": _d("2.25"),
            "j": _d("2.25"),
            "lb_base": _d("7.38"),
            "f": _d("1.00"),
            "r": _d("5.73"),
            "fb": _d("1.06"),
            "tf": _d("9.44"),
        },
        _d("7"): {
            "bore": _d("7"),
            "e": _d("8.5"),
            "g": _d("2.75"),
            "j": _d("2.75"),
            "lb_base": _d("8.5"),
            "f": _d("1.00"),
            "r": _d("6.58"),
            "fb": _d("1.19"),
            "tf": _d("10.63"),
        },
        _d("8"): {
            "bore": _d("8"),
            "e": _d("9.5"),
            "g": _d("3"),
            "j": _d("3"),
            "lb_base": _d("9.5"),
            "f": None,  # TODO: f unreadable in screenshot for H family bore 8
            "r": _d("7.50"),
            "fb": _d("1.31"),
            "tf": _d("11.8125"),
        },
        _d("10"): {
            "bore": _d("10"),
            "e": _d("12.625"),
            "g": _d("3.688"),
            "j": _d("3.688"),
            "lb_base": _d("12.1"),
            "f": None,  # TODO: f unreadable in screenshot for H family bore 10
            "r": _d("9.89"),
            "fb": _d("1.3125"),
            "tf": _d("14.13"),
        },
        _d("12"): {
            "bore": _d("12"),
            "e": _d("14.875"),
            "g": _d("4.438"),
            "j": _d("4.438"),
            "lb_base": _d("14.5"),
            "f": None,  # TODO: f unreadable in screenshot for H family bore 12
            "r": _d("11.75"),
            "fb": _d("1.5625"),
            "tf": _d("16.79"),
        },
        _d("14"): {
            "bore": _d("14"),
            "e": _d("17.125"),
            "g": _d("4.875"),
            "j": _d("4.875"),
            "lb_base": _d("15.6"),
            "f": None,  # TODO: f unreadable in screenshot for H family bore 14
            "r": _d("12.9"),
            "fb": _d("1.8"),
            "tf": _d("18.43"),
        },
        _d("16"): {
            "bore": _d("16"),
            "e": _d("19.25"),
            "g": _d("5.875"),
            "j": _d("5.875"),
            "lb_base": _d("18.1"),
            "f": None,  # TODO: f unreadable in screenshot for H family bore 16
            "r": _d("15.28"),
            "fb": _d("1.8125"),
            "tf": _d("21.03"),
        },
        _d("18"): {
            "bore": _d("18"),
            "e": _d("22"),
            "g": _d("6.875"),
            "j": _d("6.875"),
            "lb_base": _d("21.1"),
            "f": None,  # TODO: f unreadable in screenshot for H family bore 18
            "r": _d("16.45"),
            "fb": _d("2.0625"),
            "tf": _d("22.65"),
        },
        _d("20"): {
            "bore": _d("20"),
            "e": _d("23.625"),
            "g": _d("7.875"),
            "j": _d("7.875"),
            "lb_base": _d("23.6"),
            "f": None,  # TODO: f unreadable in screenshot for H family bore 20
            "r": _d("18.07"),
            "fb": _d("2.0625"),
            "tf": _d("24.87"),
        },
    },
    "a": {
        _d("1.5"): {
            "bore": _d("1.5"),
            "e": _d("2"),
            "g": _d("1.5"),
            "j": _d("1"),
            "lb_base": _d("3.63"),
            "f": _d("0.375"),
            "r": _d("1.43"),
            "fb": _d("0.562"),
            "tf": _d("2.75"),
        },
        _d("2"): {
            "bore": _d("2"),
            "e": _d("2.5"),
            "g": _d("1.5"),
            "j": _d("1"),
            "lb_base": _d("3.63"),
            "f": _d("0.375"),
            "r": _d("1.84"),
            "fb": _d("0.375"),
            "tf": _d("3.375"),
        },
        _d("2.5"): {
            "bore": _d("2.5"),
            "e": _d("3"),
            "g": _d("1.75"),
            "j": _d("1.25"),
            "lb_base": _d("4.25"),
            "f": _d("0.375"),
            "r": _d("2.19"),
            "fb": _d("0.437"),
            "tf": _d("3.875"),
        },
        _d("3.25"): {
            "bore": _d("3.25"),
            "e": _d("3.75"),
            "g": _d("1.75"),
            "j": _d("1.25"),
            "lb_base": _d("4.25"),
            "f": _d("0.625"),
            "r": _d("2.76"),
            "fb": _d("0.437"),
            "tf": _d("4.688"),
        },
        _d("4"): {
            "bore": _d("4"),
            "e": _d("4.5"),
            "g": _d("1.75"),
            "j": _d("1.25"),
            "lb_base": _d("4.5"),
            "f": _d("0.625"),
            "r": _d("3.32"),
            "fb": _d("0.437"),
            "tf": _d("5.437"),
        },
        _d("5"): {
            "bore": _d("5"),
            "e": _d("5.5"),
            "g": _d("1.75"),
            "j": _d("1.25"),
            "lb_base": _d("4.5"),
            "f": _d("0.625"),
            "r": _d("4.1"),
            "fb": _d("0.562"),
            "tf": _d("6.625"),
        },
        _d("6"): {
            "bore": _d("6"),
            "e": _d("6.5"),
            "g": _d("1.5"),
            "j": _d("1.5"),
            "lb_base": _d("5"),
            "f": _d("0.75"),
            "r": _d("4.88"),
            "fb": None,  # TODO: fb unreadable in screenshot for A family bore 6
            "tf": None,  # TODO: tf unreadable in screenshot for A family bore 6
        },
        _d("7"): {
            "bore": _d("7"),
            "e": _d("7.5"),
            "g": _d("1.5"),
            "j": _d("1.5"),
            "lb_base": _d("5.13"),
            "f": _d("0.75"),
            "r": _d("5.73"),
            "fb": None,  # TODO: fb unreadable in screenshot for A family bore 7
            "tf": None,  # TODO: tf unreadable in screenshot for A family bore 7
        },
        _d("8"): {
            "bore": _d("8"),
            "e": _d("8.5"),
            "g": _d("1.5"),
            "j": _d("1.5"),
            "lb_base": _d("5.13"),
            "f": _d("0.75"),
            "r": _d("6.44"),
            "fb": None,  # TODO: fb unreadable in screenshot for A family bore 8
            "tf": None,  # TODO: tf unreadable in screenshot for A family bore 8
        },
        _d("10"): {
            "bore": _d("10"),
            "e": _d("10.625"),
            "g": _d("2.25"),
            "j": _d("2"),
            "lb_base": _d("6.38"),
            "f": None,  # TODO: f unreadable in screenshot for A family bore 10
            "r": _d("7.92"),
            "fb": None,  # TODO: fb unreadable in screenshot for A family bore 10
            "tf": None,  # TODO: tf unreadable in screenshot for A family bore 10
        },
        _d("12"): {
            "bore": _d("12"),
            "e": _d("12.75"),
            "g": _d("2.25"),
            "j": _d("2"),
            "lb_base": _d("6.88"),
            "f": None,  # TODO: f unreadable in screenshot for A family bore 12
            "r": _d("9.4"),
            "fb": None,  # TODO: fb unreadable in screenshot for A family bore 12
            "tf": None,  # TODO: tf unreadable in screenshot for A family bore 12
        },
        _d("14"): {
            "bore": _d("14"),
            "e": _d("14.75"),
            "g": _d("2.75"),
            "j": _d("2.25"),
            "lb_base": _d("8.13"),
            "f": None,  # TODO: f unreadable in screenshot for A family bore 14
            "r": _d("10.9"),
            "fb": None,  # TODO: fb unreadable in screenshot for A family bore 14
            "tf": None,  # TODO: tf unreadable in screenshot for A family bore 14
        },
    },
}


def _to_decimal(value):
    """Convert int/float/str/Decimal to Decimal safely."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def get_cylinder_dimensions(series_family, bore, stroke):
    """Return cylinder dimensions for a given series family, bore, and stroke.

    Args:
        series_family (str): Series family identifier (e.g. "H" or "A").
        bore (int/float/str/Decimal): Exact bore size to look up.
        stroke (int/float/str/Decimal): Cylinder stroke used to compute ``lb``.

    Returns:
        dict: Keys are ``e``, ``g``, ``j``, ``lb``, ``f``, ``r``, ``fb``,
        ``tf``. Values are Decimal or None for fields still awaiting data.

    Raises:
        ValueError: If the series family is unknown or the bore is not found.
    """
    family_key = str(series_family).strip().lower()
    table = CYLINDER_DIMENSION_TABLES.get(family_key)
    if table is None:
        raise ValueError(
            f"Unknown series family {series_family!r}. "
            f"Known families: {list(CYLINDER_DIMENSION_TABLES.keys())}"
        )

    bore_decimal = _to_decimal(bore)
    row = None
    for key, candidate in table.items():
        if key == bore_decimal:
            row = candidate
            break
    if row is None:
        raise ValueError(
            f"Bore {bore!r} not found for series family {series_family!r}."
        )

    stroke_decimal = _to_decimal(stroke)
    lb = row["lb_base"] + stroke_decimal

    return {
        "e": row["e"],
        "g": row["g"],
        "j": row["j"],
        "lb": lb,
        "f": row["f"],
        "r": row["r"],
        "fb": row["fb"],
        "tf": row["tf"],
    }
