from decimal import Decimal
from pathlib import Path

import pytest

from cylinder_quote_engine.data import PricingData


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "data_dir",
    [ROOT / "data", ROOT / "tests" / "data"],
)
def test_modification_rate_matrix_files_are_separated(data_dir):
    pricing_data = PricingData(data_dir)

    assert len(pricing_data.mod_rates) == 667
    assert {row["unit_system"] for row in pricing_data.mod_rates} == {"mm"}
    assert {row["series_group"] for row in pricing_data.mod_rates} == {"IH|IHM|IMH"}

    standard_rates = pricing_data.find_mod_rates("H", Decimal("1.5"), Decimal("0.625"), "rod_extension")
    metric_rates = pricing_data.find_mod_rates("IH", Decimal("25"), Decimal("12"), "rod_extension")

    assert standard_rates["per_length"] == Decimal("14")
    assert metric_rates["per_length"] > Decimal("0")


def test_standard_modification_rates_use_standard_series_columns():
    pricing_data = PricingData(ROOT / "data")
    for row in pricing_data.mod_rates:
        if row["unit_system"] == "inch" and row["rule_id"] == "rod_extension":
            row["rate_value"] = "999999"

    rates = pricing_data.find_mod_rates("H", Decimal("1.5"), Decimal("0.625"), "rod_extension")

    assert rates["per_length"] == Decimal("14")


def test_standard_modification_rate_missing_series_value_raises():
    pricing_data = PricingData(ROOT / "data")
    source = next(
        row for row in pricing_data.standard_series_pricing
        if row["series_family"] == "H"
        and row["bore"] == "1.5"
        and row["rod_diameter"] == "0.625"
    )
    source["Rod_Extension_per_inch"] = ""

    with pytest.raises(LookupError, match="Rod_Extension_per_inch"):
        pricing_data.find_mod_rates("H", Decimal("1.5"), Decimal("0.625"), "rod_extension")