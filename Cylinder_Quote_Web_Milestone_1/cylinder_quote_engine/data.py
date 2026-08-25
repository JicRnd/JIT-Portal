from __future__ import annotations
import csv
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path

D = Decimal


def dec(value) -> Decimal:
    if value is None or value == "":
        return D("0")
    if isinstance(value, Decimal):
        return value
    return D(str(value).strip())


def parse_dimension(value) -> Decimal:
    """Parse numeric values and Excel-style mixed fractions such as 1 3/8\"."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return D(str(value))
    s = str(value).strip().replace('"', '')
    try:
        return D(s)
    except InvalidOperation:
        pass
    if ' ' in s:
        whole, frac = s.split(None, 1)
        f = Fraction(frac)
        return D(whole) + (D(f.numerator) / D(f.denominator))
    f = Fraction(s)
    return D(f.numerator) / D(f.denominator)


class PricingData:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.series_pricing = self._read('series_pricing.csv')
        self.series_row_rates = self._read('series_row_rates.csv')
        self.mod_rates = self._read('modification_rate_matrix.csv')
        self.special_parts = self._read('special_part_catalog.csv')
        self.ph = self._read('ph_position_sensing.csv')
        self.ph_bands = self._read('ph_sensor_bands.csv')
        self.va_base = self._read('va_base_pricing.csv')
        self.va_mods = self._read('va_modifications.csv')
        self.accessories = self._read('accessory_mountings.csv')
        self.accessory_catalog = self._read('accessory_catalog_v12.csv')
        self.rod_boot_rates = self._read('rod_boot_rates.csv')

    def _read(self, name: str):
        with (self.data_dir / name).open(encoding='utf-8-sig', newline='') as f:
            return list(csv.DictReader(f))

    @staticmethod
    def _aliases(row):
        return {x.strip().upper() for x in row.get('series_aliases', '').split('|') if x.strip()}

    def find_series_price(self, series, bore, rod, mount):
        series = series.upper(); mount = mount.upper()
        candidates = []
        for r in self.series_pricing:
            if series not in self._aliases(r):
                continue
            if parse_dimension(r['bore']) != bore or parse_dimension(r['rod_diameter']) != rod:
                continue
            codes = {x.strip().upper() for x in r['mount_codes'].split('|') if x.strip()}
            if mount in codes:
                candidates.append(r)
        if len(candidates) != 1:
            raise LookupError(f'Expected one base-price row for {series}/{bore}/{rod}/{mount}, found {len(candidates)}')
        return candidates[0]

    def find_series_row(self, series, bore, rod):
        series = series.upper()
        rows = [r for r in self.series_row_rates
                if series in self._aliases(r)
                and parse_dimension(r['bore']) == bore
                and parse_dimension(r['rod_diameter']) == rod]
        if len(rows) != 1:
            raise LookupError(f'Expected one row-rate record for {series}/{bore}/{rod}, found {len(rows)}')
        return rows[0]

    def find_mod_rates(self, series, bore, rod, rule_id):
        series = series.upper()
        out = {}
        for r in self.mod_rates:
            aliases = {x.strip().upper() for x in r['series_group'].split('|') if x.strip()}
            if series not in aliases or r['rule_id'] != rule_id:
                continue
            if parse_dimension(r['bore']) != bore or parse_dimension(r['rod_diameter']) != rod:
                continue
            out[r['rate_name']] = dec(r['rate_value'])
        return out

    def find_special_part(self, part_number):
        key = part_number.strip().upper()
        rows = [r for r in self.special_parts if r['part_number'].strip().upper() == key]
        if len(rows) != 1:
            raise LookupError(f'Special part {part_number!r}: found {len(rows)} rows')
        return rows[0]

    def find_va_base(self, bore, rod):
        rows = [r for r in self.va_base if parse_dimension(r['bore']) == bore and parse_dimension(r['rod_diameter']) == rod]
        if len(rows) != 1:
            raise LookupError(f'VA base {bore}/{rod}: found {len(rows)} rows')
        return rows[0]

    def find_va_mod(self, bore, rod):
        rows = [r for r in self.va_mods if parse_dimension(r['bore']) == bore and parse_dimension(r['rod_diameter']) == rod]
        if len(rows) != 1:
            raise LookupError(f'VA mods {bore}/{rod}: found {len(rows)} rows')
        return rows[0]

    def find_ph(self, metric, bore):
        system = 'metric' if metric else 'imperial'
        rows = [r for r in self.ph if r['system'] == system and parse_dimension(r['bore']) == bore]
        if len(rows) != 1:
            raise LookupError(f'PH {system}/{bore}: found {len(rows)} rows')
        return rows[0]

    def accessory_price_by_thread(self, thread, part_type):
        rows = [r for r in self.accessories if r['thread_size'].strip() == thread and r['part_type'] == part_type]
        if len(rows) != 1:
            raise LookupError(f'Accessory {part_type}/{thread}: found {len(rows)} rows')
        return dec(rows[0]['price'])

    def find_accessory(self, lookup_type, lookup_key, part_type):
        key = str(lookup_key).strip()
        rows = [r for r in self.accessory_catalog
                if r['lookup_type'] == lookup_type
                and r['lookup_key'].strip() == key
                and r['part_type'] == part_type]
        if len(rows) > 1:
            raise LookupError(f'Accessory {part_type}/{lookup_type}/{lookup_key}: found {len(rows)} rows')
        return rows[0] if rows else None

    def find_rod_boot(self, rod):
        rows = [r for r in self.rod_boot_rates if parse_dimension(r['rod_diameter']) == rod]
        if len(rows) > 1:
            raise LookupError(f'Rod boot {rod}: found {len(rows)} rows')
        return rows[0] if rows else None
