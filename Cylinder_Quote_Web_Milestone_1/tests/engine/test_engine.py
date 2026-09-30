from decimal import Decimal as D
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cylinder_quote_engine import QuoteInputs, QuotePricingEngine, excel_roundup
from cylinder_quote_engine.data import PricingData

DATA = Path(__file__).resolve().parents[1] / 'data'
E = QuotePricingEngine(DATA)

def test_row_rates_use_unit_specific_series_pricing_workbooks():
    pricing_data = PricingData(DATA)
    standard_source = next(
        row for row in pricing_data.standard_series_pricing
        if row['series_family'] == 'H'
        and row['bore'] == '1.5'
        and row['rod_diameter'] == '0.625'
    )
    metric_source = next(
        row for row in pricing_data.metric_series_pricing
        if row['series_family'] == 'IH'
        and row['bore'] == '25'
        and row['rod_diameter'] == '12'
    )
    pricing_data.series_row_rates = [
        dict(standard_source, stroke_rate='999', cushion_per_end='999'),
    ]

    standard_row = pricing_data.find_series_row('H', D('1.5'), D('0.625'))
    metric_row = pricing_data.find_series_row('IH', D('25'), D('12'))

    assert standard_row['stroke_unit'] == 'inch'
    assert standard_row['stroke_rate'] == standard_source['stroke_rate']
    assert standard_row['cushion_per_end'] == standard_source['cushion_per_end']
    assert metric_row['stroke_unit'] == 'mm'
    assert metric_row['stroke_rate'] == metric_source['stroke_rate']
    assert metric_row['cushion_per_end'] == metric_source['cushion_per_end']

def test_excel_roundup_legacy_stroke_behavior():
    assert excel_roundup(D('12.01'), D('0.1')) == D('13')
    assert excel_roundup(D('12.00'), D('0.1')) == D('12')

def test_h_base_stroke_cushion_and_model():
    q = QuoteInputs(series='H', bore=D('1.5'), rod_diameter=D('0.625'), mount='MX0', stroke=D('10'), cushion='BE', port_code='N', seal_code='B')
    r = E.calculate(q)
    assert r.base_price == D('642')
    assert r.stroke_cushion == D('394')  # 10*10 + 147*2
    assert r.model_code == 'H-MX0-1.5x10x0.625-1-BE-N-B-S'
    assert r.modifications == D('60')
    assert r.working_net_each == D('1096')

def test_dre_is_65_percent_of_base_only():
    q = QuoteInputs(series='H', bore=D('1.5'), rod_diameter=D('0.625'), mount='MX0', stroke=D('10'), cushion='NC', dre=True)
    r = E.calculate(q)
    assert r.base_price == D('642')
    assert r.dre_surcharge == D('417.30')
    assert r.pre_discount_subtotal == D('1159.30')  # 642 + 100 + 417.30
    assert r.working_net_each == D('1160')

def test_discount_list_backout_and_net_return():
    q = QuoteInputs(series='H', bore=D('1.5'), rod_diameter=D('0.625'), mount='MX0', stroke=D('10'), discount=D('0.20'))
    r = E.calculate(q)
    assert r.working_net_each == D('594')  # roundup((642+100)*.8)
    assert r.list_price == D('742.5')
    assert r.quote_net_each == D('594.00')

def test_w_series_quote_form_reduction():
    q = QuoteInputs(series='W', bore=D('1.5'), rod_diameter=D('0.625'), mount='MX0', stroke=D('10'))
    r = E.calculate(q)
    assert r.working_net_each == D('742')
    assert r.quote_net_each == D('630.70')

def test_common_modifications():
    q = QuoteInputs(series='H', bore=D('1.5'), rod_diameter=D('0.625'), mount='MX0', stroke=D('10'), rod_extension=D('2'), stop_tube=D('1'))
    r = E.calculate(q)
    # H2 C8=14; D8=57; E8=44 => 28 + 101
    assert r.modifications == D('129')

def test_special_part_catalog():
    q = QuoteInputs(series='H', bore=D('1.5'), rod_diameter=D('0.625'), mount='MX0', stroke=D('10'), special_parts={'AC044': D('2')})
    r = E.calculate(q)
    assert r.special_parts == D('160')

def test_va_base_and_stroke():
    q = QuoteInputs(series='VA', bore=D('2.5'), rod_diameter=D('0.625'), mount='MX0', stroke=D('10'))
    r = E.calculate(q)
    assert r.va_total == D('480')
    assert r.base_price == D('0')
    assert r.working_net_each == D('480')
