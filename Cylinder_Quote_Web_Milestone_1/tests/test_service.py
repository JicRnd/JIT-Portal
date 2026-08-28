from decimal import Decimal
from pathlib import Path

import pytest

from app.catalog import build_catalog
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
    c = build_catalog(engine.data)
    for series in ["H", "A", "MH", "IH", "IMH", "VA"]:
        assert series in c["series"]


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
