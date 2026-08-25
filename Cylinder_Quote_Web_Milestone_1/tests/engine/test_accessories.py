from decimal import Decimal as D
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cylinder_quote_engine import QuoteInputs, QuotePricingEngine

DATA=Path(__file__).resolve().parents[1]/'data'
E=QuotePricingEngine(DATA)

def q(**kw):
    base=dict(series='H',bore=D('1.5'),rod_diameter=D('0.625'),mount='MX0',stroke=D('8'),cushion='NC',port_code='N',seal_code='P',rod_style=1)
    base.update(kw); return QuoteInputs(**base)

def test_accessory_normalization_cases():
    cases=[
      ({'Rod Clevis':D('2')},D('120')),
      ({'Rod Eye':D('3')},D('120')),
      ({'Eye Bracket':D('2')},D('120')),
      ({'Pivot Pin':D('2')},D('40')),
      ({'Self-Aligning Male Eye':D('1')},D('125')),
      ({'SA - Clevis Bracket':D('2')},D('240')),
      ({'Alignment Coupler':D('1')},D('80')),
      ({'Male Rod Eye':D('1')},D('305')),
      ({'Safety Coupler':D('2')},D('350')),
      ({'Rod Stud':D('2')},D('40')),
      ({'Jam Nut':D('3')},D('18')),
      ({'Weld Plate':D('3')},D('194')),
    ]
    for acc, expected in cases:
        assert E.calculate(q(accessory_quantities=acc)).accessories == expected

def test_oversize_thread_rod_clevis():
    assert E.calculate(q(rod_style=2, accessory_quantities={'Rod Clevis':D('1')})).accessories == D('70')

def test_clevis_and_sa_pivot_bucket_active_and_inactive():
    assert E.calculate(q(mount='MP1',accessory_quantities={'Clevis Bracket':D('1')})).accessories == D('125')
    assert E.calculate(q(mount='MX0',accessory_quantities={'Clevis Bracket':D('1')})).accessories == D('0')
    assert E.calculate(q(mount='MP1',accessory_quantities={'SA - Pivot Pin':D('2')})).accessories == D('40')

def test_rod_boot_legacy_quantity_behavior():
    assert E.calculate(q(standard_rod_boot_qty=D('1'))).accessories == D('535')
    assert E.calculate(q(standard_rod_boot_qty=D('2'))).accessories == D('655')

def test_a_series_bucket():
    qq=QuoteInputs(series='A',bore=D('1.5'),rod_diameter=D('0.625'),mount='MP1',stroke=D('8'),cushion='NC',port_code='N',seal_code='P',rod_style=1,accessory_quantities={'Clevis Bracket':D('1'),'SA - Pivot Pin':D('1')})
    assert E.calculate(qq).accessories == D('145')
