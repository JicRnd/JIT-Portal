from decimal import Decimal as D
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cylinder_quote_engine import QuoteInputs, QuotePricingEngine, excel_roundup

DATA = Path(__file__).resolve().parents[1] / 'data'
E = QuotePricingEngine(DATA)

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
