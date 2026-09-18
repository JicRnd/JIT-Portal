from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import app.db as db_mod
from app import create_app
from app.component_bom import (
    apply_dynamic_allocations,
    apply_fixed_allocations,
    generated_cylinder_parts,
    sort_order_form_parts,
)
from app.db import get_session
from app.models_db import CatalogPart, InventoryPart, OrderFormInventoryRule
from app.order_form_inventory import evaluate_formula, evaluate_inventory_rules
from scripts.import_order_form_inventory_rules import extract_dependency_audit, extract_rules
from app.models_db import TieRodRule
from app.tie_rod_engine import calculate_tie_rod_requirement


def _app_with_inventory(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("ACCOUNTS_DATABASE_PATH", str(tmp_path / "accounts.db"))
    monkeypatch.setenv("QUOTES_DATABASE_PATH", str(tmp_path / "quotes.db"))
    monkeypatch.setenv("ORDERS_DATABASE_PATH", str(tmp_path / "orders.db"))
    monkeypatch.setenv("PRICING_DATABASE_PATH", str(tmp_path / "Pricing.db"))
    monkeypatch.setenv("INVENTORY_DATABASE_PATH", str(tmp_path / "Inventory.db"))
    db_mod.reset_engines()
    app = create_app()
    app.testing = True
    return app


def test_catalog_search_adds_inventory_db_values_for_order_form(tmp_path, monkeypatch):
    app = _app_with_inventory(tmp_path, monkeypatch)
    with get_session() as session:
        session.add(CatalogPart(part_number="R200", description="Rod", active="YES"))
        session.add(
            InventoryPart(
                part_number="R200",
                product_description="Rod",
                inventory=17,
                allocated=Decimal("4"),
            )
        )
        session.commit()

    response = app.test_client().get("/api/catalog-parts/search?q=R200")

    assert response.status_code == 200
    row = response.get_json()["parts"][0]
    assert row["part_number"] == "R200"
    assert row["on_hand"] == "17"
    assert Decimal(row["allocated"]) == Decimal("4")


def test_quote_payload_contains_inventory_db_values_for_generated_parts(tmp_path, monkeypatch):
    app = _app_with_inventory(tmp_path, monkeypatch)
    with get_session() as session:
        session.add(CatalogPart(part_number="TR050", description="Tie Rod", active="YES"))
        session.add(
            InventoryPart(
            part_number="TR050",
                product_description="Tie Rod",
                inventory=23,
                allocated=Decimal("6"),
            )
        )
        session.commit()

    response = app.test_client().post(
        "/api/quotes",
        json={
            "series": "H",
            "bore": "2",
            "rod_diameter": "1",
            "mount": "MX0",
            "stroke": "12",
            "cushion": "NC",
            "port_code": "N",
            "seal_code": "P",
            "rod_style": 1,
            "discount": "0",
            "dre": False,
        },
    )

    assert response.status_code == 200
    rows = response.get_json()["quote"]["order_form_parts"]
    tie_rod = next(row for row in rows if row["part_number"] == "TR050")
    assert tie_rod["on_hand"] == "23"
    assert Decimal(tie_rod["allocated"]) == Decimal("6")


def test_quote_payload_calculates_dimensional_allocations_from_workbook_rules(
    tmp_path, monkeypatch
):
    app = _app_with_inventory(tmp_path, monkeypatch)
    parts = [
        ("TR062", "Tie Rod", 109),
        ("R200", "Rod", 1025),
        ("H40B", "Barrel", 829),
        ("TRN062", "Tie Rod Nuts", 3088),
    ]
    with get_session() as session:
        for part_number, description, on_hand in parts:
            session.add(CatalogPart(part_number=part_number, description=description, active="YES"))
            session.add(
                InventoryPart(
                    part_number=part_number,
                    product_description=description,
                    inventory=on_hand,
                    allocated=Decimal("999"),
                )
            )
        session.commit()

    create_response = app.test_client().post(
        "/api/quotes",
        json={
            "series": "H",
            "bore": "4",
            "rod_diameter": "2",
            "mount": "MF1",
            "stroke": "20",
            "cushion": "NC",
            "port_code": "N",
            "seal_code": "P",
            "rod_style": 1,
            "discount": "0",
            "dre": False,
        },
    )

    assert create_response.status_code == 200
    quote_id = create_response.get_json()["quote"]["id"]
    response = app.test_client().get(f"/api/quotes/{quote_id}")
    assert response.status_code == 200
    rows = {
        row["part_number"]: row
        for row in response.get_json()["quote"]["order_form_parts"]
    }
    assert Decimal(rows["TR062"]["allocated"]) == Decimal("109")
    assert Decimal(rows["R200"]["allocated"]) == Decimal("28.23")
    assert Decimal(rows["H40B"]["allocated"]) == Decimal("22.188")
    assert Decimal(rows["TRN062"]["allocated"]) == Decimal("8")
    assert rows["TR062"]["on_hand"] == "109"


def test_quote_payload_uses_allocated_quantity_for_order_form_cost(
    tmp_path, monkeypatch
):
    app = _app_with_inventory(tmp_path, monkeypatch)
    with get_session() as session:
        session.add(CatalogPart(
            part_number="TR087",
            description="Tie Rod",
            unit_cost=Decimal("0.2356"),
            active="YES",
        ))
        session.add(InventoryPart(
            part_number="TR087",
            product_description="Tie Rod",
            inventory=1000,
            allocated=Decimal("0"),
        ))
        session.commit()

    create_response = app.test_client().post(
        "/api/quotes",
        json={
            "series": "H",
            "bore": "5",
            "rod_diameter": "2",
            "mount": "MF1",
            "stroke": "12",
            "cushion": "NC",
            "port_code": "N",
            "seal_code": "P",
            "rod_style": 1,
            "discount": "0",
            "dre": False,
        },
    )

    assert create_response.status_code == 200
    quote_id = create_response.get_json()["quote"]["id"]
    response = app.test_client().get(f"/api/quotes/{quote_id}")
    assert response.status_code == 200
    rows = response.get_json()["quote"]["order_form_parts"]
    tie_rod = next(row for row in rows if row["part_number"] == "TR087")
    assert Decimal(tie_rod["allocated"]) == Decimal("80")
    assert Decimal(tie_rod["cost"]) == Decimal("18.8480")


def test_fixed_component_allocations_match_workbook_quantity_rules():
    rows = apply_fixed_allocations(
        [
            {"part_number": "H50PP", "description": "H Polyurethane Piston Seal"},
            {"part_number": "H50BB", "description": "H Nitrile Barrel Seal"},
            {"part_number": "H40PL", "description": "H Low Friction Piston Seal"},
            {"part_number": "H50P200", "description": "H Piston"},
        ],
        quantity=3,
    )

    allocations = {row["part_number"]: Decimal(row["allocated"]) for row in rows}
    assert allocations == {
        "H50PP": Decimal("6"),
        "H50BB": Decimal("6"),
        "H40PL": Decimal("3"),
        "H50P200": Decimal("3"),
    }


def test_order_form_parts_preserve_workbook_order_and_limit_rows():
    parts = [
        {"part_number": f"P{index:02d}", "allocated": str(index % 4)}
        for index in range(35)
    ]

    rows = sort_order_form_parts(parts)

    assert len(rows) == 31
    assert [row["part_number"] for row in rows[:4]] == ["P00", "P01", "P02", "P03"]
    assert [row["part_number"] for row in rows[-4:]] == ["P27", "P28", "P29", "P30"]


def test_generated_order_form_parts_match_workbook_sequence(tmp_path, monkeypatch):
    _app_with_inventory(tmp_path, monkeypatch)
    part_numbers = [
        "TR087", "R200", "H50B", "TRN087", "H50PP", "H50BB", "GTOB200",
        "200RWP", "200GP", "PIB200", "GBO200", "G200", "H50REH200", "H50CEH",
        "H50P200", "H50MF2",
    ]
    with get_session() as session:
        for part_number in part_numbers:
            session.add(CatalogPart(part_number=part_number, description=part_number, active="YES"))
        session.commit()

    rows = generated_cylinder_parts({
        "series": "H", "bore": "5", "rod_diameter": "2", "mount": "MF2", "seal_code": "P",
    })

    assert [row["part_number"] for row in rows] == part_numbers


def test_inventory_rule_import_preserves_complete_data_cell_references():
    workbook = Path(__file__).parents[1] / "2026 JIT Order Entry V3.xlsm"

    rules = extract_rules(workbook)

    assert len(rules) == 834
    assert len({rule["source_row"] for rule in rules}) == 834
    tr062 = next(rule for rule in rules if rule["part_number"] == "TR062")
    assert set(tr062["data_inputs"].split("|")) >= {"B2", "B3", "B4", "B8", "B16"}


def test_inventory_dependency_audit_extracts_cells_and_edges():
    audit = Path.home() / "Downloads" / "JIT_Inventory_Dependency_Audit.xlsx"
    if not audit.exists():
        return

    cells, edges = extract_dependency_audit(audit)

    assert len(cells) == 5542
    assert len(edges) == 13568
    assert any(cell["cell_key"] == "H!AE7" and cell["kind"] == "formula" for cell in cells)
    assert any(edge["from_cell"] == "H!AE7" and edge["to_reference"] == "TieRod!B2" for edge in edges)


def test_inventory_formula_evaluator_handles_selector_and_helper_formulas():
    cells = {
        "Data!B2": 2,
        "Data!B3": "H",
        "Data!B4": 4,
        "Data!B8": 20,
        "H!AE7": "=TieRod!B2+Data!B25",
        "TieRod!B2": 5,
        "Data!B25": 0.625,
    }

    result = evaluate_formula(
        '=IF(AND(Data!B3="H",OR(Data!B4=3.25,Data!B4=4)),Data!B2*(Data!B8+H!AE7)*4,0)',
        cells,
    )

    assert result == Decimal("205.000")


def test_inventory_formula_evaluator_handles_external_reference_and_sum():
    cells = {
        "Data!B3": "H",
        "Data!B4": 4,
        "I99": '=IF(AND([1]Data!B4=4,Data!B8>90),1,"")',
        "Data!B8": 100,
        "I100": 2,
        "I101": 3,
    }

    assert evaluate_formula("=SUM(I99:I101)", cells) == Decimal("6")


def test_inventory_formula_evaluator_handles_not_equal_comparison():
    assert evaluate_formula('=IF(Data!B3<>"H",1,0)', {"Data!B3": "A"}) == Decimal("1")


def test_inventory_rule_evaluator_returns_only_positive_allocations():
    rules = [
        {"part_number": "A", "allocation_formula": "=Data!B2"},
        {"part_number": "B", "allocation_formula": "=IF(Data!B3=\"H\",2,0)"},
    ]

    rows = evaluate_inventory_rules(rules, {"Data!B2": 1, "Data!B3": "H"})

    assert [(row["part_number"], row["allocated"]) for row in rows] == [("A", "1"), ("B", "2")]


def test_database_inventory_rule_overrides_fallback_allocation(tmp_path, monkeypatch):
    _app_with_inventory(tmp_path, monkeypatch)
    with get_session() as session:
        session.add(
            OrderFormInventoryRule(
                source_row=2,
                part_number="R200",
                description="Rod",
                allocation_formula='=IF(Data!B3="H",Data!B2*2,0)',
                source_workbook="test.xlsm",
                source_sheet="Inventory",
            )
        )
        session.commit()

    rows = apply_dynamic_allocations(
        [{"part_number": "R200", "description": "Rod", "allocated": "1"}],
        {"series": "H"},
        quantity=3,
    )

    assert rows[0]["allocated"] == "6"


def test_tie_rod_engine_calculates_current_quote_from_pricing_db(tmp_path, monkeypatch):
    _app_with_inventory(tmp_path, monkeypatch)
    with get_session() as session:
        session.add(
            TieRodRule(
                source_row=297,
                series_codes="H",
                bore=5,
                mount_codes="MF1|MF2|MF5|MF6|MP2",
                assembly_length=8,
                assembly_formula="=D297+F297+J297+K297+L297+M297",
                source_workbook="2026 JIT Order Entry V3.xlsm",
                source_sheet="TieRod",
            )
        )
        session.commit()

    result = calculate_tie_rod_requirement(
        {"series": "H", "bore": 5, "mount": "MF1", "stroke": 12},
    )

    assert result == {"length": Decimal("20"), "allocated": Decimal("80")}