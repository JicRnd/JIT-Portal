from decimal import Decimal
from pathlib import Path

import pytest

from app.Pricing.metric_catalog import build_catalog as build_metric_catalog
from app.Pricing.standard_catalog import build_catalog as build_standard_catalog
from cylinder_quote_engine.data import PricingData
from app.service import calculate_payload, make_engine, quote_inputs_from_payload

ROOT = Path(__file__).resolve().parents[1]


def sample_payload():
    return {
        "series": "H",
        "bore": "2",
        "rod_diameter": "1",
        "mount": "MX0",
        "stroke": "12",
        "cushion": "NC",
        "port_code": "N",
        "seal_code": "",
        "rod_style": 1,
        "discount": "0.10",
        "dre": False,
    }


def test_payload_conversion():
    q = quote_inputs_from_payload(sample_payload())
    assert q.series == "H"
    assert q.bore == Decimal("2")
    assert q.discount == Decimal("0.10")


def test_engine_calculation_round_trip():
    engine = make_engine(ROOT)
    result = calculate_payload(engine, sample_payload())
    assert result["model_code"].startswith("H-MX0-2x12x1-")
    assert Decimal(result["quote_net_each"]) > 0
    assert Decimal(result["quote_list_price"]) >= Decimal(result["quote_net_each"])


def test_catalog_has_primary_routes():
    engine = make_engine(ROOT)
    standard_catalog = build_standard_catalog(engine.data)
    metric_catalog = build_metric_catalog(engine.data)
    for series in ["H", "A", "MH", "VA"]:
        assert series in standard_catalog["series"]
    for series in ["IH", "IMH"]:
        assert series in metric_catalog["series"]


def test_catalog_modules_use_associated_workbook_fixtures():
    fixture_data = PricingData(ROOT / "tests" / "data")
    standard_catalog = build_standard_catalog(fixture_data)
    metric_catalog = build_metric_catalog(fixture_data)

    assert list(standard_catalog["series"]) == ["H", "A", "LH", "MH", "HM", "VA", "W"]
    assert list(metric_catalog["series"]) == ["IH", "IHM", "IMH"]
    assert standard_catalog["stroke_unit"] == "in"
    assert metric_catalog["stroke_unit"] == "mm"
    assert "IH" not in standard_catalog["series"]
    assert "H" not in metric_catalog["series"]
    assert standard_catalog["series"]["H"]["2"]["1"]
    assert metric_catalog["series"]["IH"]["25"]["12"]


def test_calculate_payload_includes_dimensions():
    """The calculation result includes authoritative cylinder dimensions."""
    engine = make_engine(ROOT)
    payload = {
        "series": "H",
        "bore": "5",
        "rod_diameter": "2",
        "mount": "MX0",
        "stroke": "12",
        "cushion": "NC",
        "port_code": "N",
        "seal_code": "",
        "rod_style": 1,
        "discount": "0",
        "dre": False,
    }
    result = calculate_payload(engine, payload)
    dims = result["dimensions"]
    assert dims is not None
    assert "warning" not in dims
    assert float(dims["e"]) == pytest.approx(6.5)
    assert float(dims["g"]) == pytest.approx(2.0)
    assert float(dims["j"]) == pytest.approx(1.75)
    assert float(dims["lb"]) == pytest.approx(18.25)
    assert float(dims["tf"]) == pytest.approx(8.19)
    assert float(dims["r"]) == pytest.approx(4.95)
    assert float(dims["fb"]) == pytest.approx(0.94)
    assert float(dims["f"]) == pytest.approx(0.88)
