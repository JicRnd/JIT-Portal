from __future__ import annotations

from types import SimpleNamespace

from app.pricing_catalog_service import build_category_sections, part_subgroup


def _part(part_number: str, description: str):
    return SimpleNamespace(
        id=part_number,
        part_number=part_number,
        description=description,
        all_descriptions=description,
        category=None,
        family_code=None,
    )


def test_part_subgroup_strips_trailing_size_text():
    assert part_subgroup(_part("062RWP", "Polyurethane Rod Wiper")) == "Polyurethane Rod Wipers"
    assert part_subgroup(_part("JN0716", "Jam Nut 7/16-20")) == "Jam Nuts"
    assert part_subgroup(_part("AC250", "Alignment Coupler 2 1/2")) == "Alignment Couplers"


def test_wipers_split_into_alphabetical_subgroups_sorted_by_size():
    parts = [
        _part("200RWV", "Viton Rod Wiper"),
        _part("062RWV", "Viton Rod Wiper"),
        _part("138RWP", "Polyurethane Rod Wiper"),
        _part("062RWP", "Polyurethane Rod Wiper"),
        _part("RWSPECIAL", "Polyurethane Rod Wiper"),
    ]
    section = next(s for s in build_category_sections(parts) if s["name"] == "Wipers")
    names = [group["name"] for group in section["groups"]]
    assert names == ["Polyurethane Rod Wipers", "Viton Rod Wipers"]
    assert [row.part_number for row in section["groups"][0]["rows"]] == [
        "062RWP",
        "138RWP",
        "RWSPECIAL",
    ]
    assert [row.part_number for row in section["groups"][1]["rows"]] == ["062RWV", "200RWV"]
