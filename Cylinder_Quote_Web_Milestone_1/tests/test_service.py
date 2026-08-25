from decimal import Decimal
from pathlib import Path

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
