from __future__ import annotations
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from .data import PricingData, dec, parse_dimension
from .models import QuoteInputs, PriceBreakdown

D = Decimal


def excel_roundup(value: Decimal, num_digits=0) -> Decimal:
    """Excel-compatible ROUNDUP for non-negative pricing inputs."""
    # Excel coerces 0.1 passed as num_digits to integer 0 in this legacy workbook.
    digits = int(num_digits)
    quantum = D('1').scaleb(-digits)
    return value.quantize(quantum, rounding=ROUND_CEILING)


def fmt_code_number(v: Decimal) -> str:
    s = format(v, 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s


class QuotePricingEngine:
    def __init__(self, data_dir: str | Path):
        self.data = PricingData(data_dir)

    def model_code(self, q: QuoteInputs) -> str:
        mount = f'DRE/{q.mount}' if q.dre else q.mount
        return '-'.join([
            q.series,
            mount,
            f'{fmt_code_number(q.bore)}x{fmt_code_number(q.stroke)}x{fmt_code_number(q.rod_diameter)}',
            str(q.rod_style), q.cushion, q.port_code, q.seal_code, 'S'
        ])

    def calculate(self, q: QuoteInputs) -> PriceBreakdown:
        warnings = []
        series = q.series.upper()

        if not (D('0') <= q.discount < D('1')):
            raise ValueError('discount must be between 0 and 1')
        if q.stroke < 0:
            raise ValueError('stroke cannot be negative')

        if series == 'VA':
            base = D('0')
            stroke_cushion = D('0')
            va_total = self._va_total(q, warnings)
        else:
            p = self.data.find_series_price(series, q.bore, q.rod_diameter, q.mount)
            base = dec(p['base_price'])
            rr = self.data.find_series_row(series, q.bore, q.rod_diameter)
            stroke_for_price = excel_roundup(q.stroke, D('0.1'))
            cushion_multiplier = self._cushion_multiplier(series, q.cushion)
            stroke_cushion = dec(rr['stroke_rate']) * stroke_for_price + dec(rr['cushion_per_end']) * cushion_multiplier
            va_total = D('0')

        modifications = self._modification_total(q, warnings)
        accessories = self._accessory_total(q, warnings)
        special_parts = self._special_parts_total(q)
        position_sensing = self._position_sensing(q, warnings) if series != 'VA' else D('0')

        subtotal = base + stroke_cushion + modifications + accessories + special_parts + position_sensing + va_total + q.legacy_reserved_add
        dre_surcharge = (base * D('0.65')) if q.dre else D('0')
        subtotal_with_dre = subtotal + dre_surcharge
        discounted = subtotal_with_dre * (D('1') - q.discount)
        working_net = excel_roundup(discounted + q.legacy_post_discount_add, 0)
        list_price = working_net / (D('1') - q.discount) if q.discount != D('1') else D('0')
        quote_list = list_price * D('0.85') if series == 'W' else list_price
        quote_net = quote_list * (D('1') - q.discount)
        expedited = quote_net * (D('1.30') if quote_net > D('1000') else D('1.40'))
        emergency = expedited * D('1.25')

        return PriceBreakdown(
            model_code=self.model_code(q),
            base_price=base,
            stroke_cushion=stroke_cushion,
            modifications=modifications,
            accessories=accessories,
            special_parts=special_parts,
            position_sensing=position_sensing,
            va_total=va_total,
            dre_surcharge=dre_surcharge,
            pre_discount_subtotal=subtotal_with_dre,
            discount_amount=subtotal_with_dre * q.discount,
            working_net_each=working_net,
            list_price=list_price,
            quote_list_price=quote_list,
            quote_net_each=quote_net,
            expedited_price=expedited,
            emergency_price=emergency,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _cushion_multiplier(series: str, cushion: str) -> Decimal:
        c = cushion.upper()
        if series in {'MH', 'IMH'}:
            return {'BE': D('2'), 'CE': D('1'), 'RE': D('1')}.get(c, D('0'))
        return {'ABE': D('4'), 'ACE': D('2'), 'ARE': D('2'), 'BE': D('2'), 'CE': D('1'), 'RE': D('1')}.get(c, D('0'))

    def _legacy_rates(self, source_sheet: str, rule_id: str, bore: Decimal, rod: Decimal):
        """Return rate fields for a specific worksheet/rule, ignoring series routing.

        This is used only for worksheet formulas that accidentally omit a series check.
        Keeping these quirks isolated lets parity mode reproduce the legacy workbook
        without making them look like intentional business rules.
        """
        out = {}
        for r in self.data.mod_rates:
            if r['source_sheet'] != source_sheet or r['rule_id'] != rule_id:
                continue
            if parse_dimension(r['bore']) != bore or parse_dimension(r['rod_diameter']) != rod:
                continue
            out[r['rate_name']] = dec(r['rate_value'])
        return out

    def _legacy_ungated_modifications(self, q: QuoteInputs, warnings) -> Decimal:
        """Charges produced by legacy formulas that do not test Data!B3 series."""
        total = D('0')
        seal = q.seal_code.upper()

        # H3 Viton column R has no series gate.
        if seal == 'V':
            r = self._legacy_rates('H3', 'viton_seals', q.bore, q.rod_diameter)
            if r:
                total += r.get('rod', D('0')) + r.get('piston', D('0'))
                if q.series.upper() not in {'H','HM','W','MH'}:
                    warnings.append('Legacy parity: H3 Viton formula contributes outside the H family because the worksheet omits a series check.')

            # A3 Viton column O likewise has no series gate.
            r = self._legacy_rates('A3', 'viton_seals', q.bore, q.rod_diameter)
            if r:
                total += r.get('rod_related', D('0')) + r.get('piston', D('0'))
                if q.series.upper() not in {'A','LH'}:
                    warnings.append('Legacy parity: A3 Viton formula contributes outside the A family because the worksheet omits a series check.')

        # H4 Flange Port formula (M column) has no series gate.
        if q.port_code.upper() == 'F':
            r = self._legacy_rates('H4', 'flange_port', q.bore, q.rod_diameter)
            if r:
                total += r['fixed_each'] * (D('2') + q.extra_port_qty)
                if q.series.upper() not in {'H','HM','W','MH'}:
                    warnings.append('Legacy parity: H4 Flange Port formula contributes outside the H family because the worksheet omits a series check.')

        # Thick-head formulas on H4/IH4 have no series gate.
        if q.thick_head_qty != 0:
            for sheet in ('H4','IH4'):
                r = self._legacy_rates(sheet, 'thick_head', q.bore, q.rod_diameter)
                if r:
                    total += r['fixed_each'] * q.thick_head_qty
                    warnings.append(f'Legacy parity: {sheet} Thicker Head uses ungated Data!I58 input.')
        return total

    def _modification_total(self, q: QuoteInputs, warnings) -> Decimal:
        s = q.series.upper(); total = self._legacy_ungated_modifications(q, warnings)

        # VA has its own modification block, but Data!D6 still also sums the shared
        # H/A/IH totals. Only the ungated worksheet leaks above can affect VA.
        if s == 'VA':
            return total

        def rates(rule): return self.data.find_mod_rates(s, q.bore, q.rod_diameter, rule)
        def need(rule):
            r = rates(rule)
            if not r:
                raise LookupError(f'No modification rates for {rule} at {s}/{q.bore}/{q.rod_diameter}')
            return r

        if q.rod_extension > 0:
            total += need('rod_extension')['per_length'] * q.rod_extension
        if q.stop_tube > D('0.1'):
            r = need('stop_tube'); total += r['base'] + r['per_length'] * q.stop_tube
        if q.stainless_rod:
            r = need('stainless_rod'); total += r['base'] + r['per_stroke'] * q.stroke
        if q.chrome_bore and s not in {'A','LH'}:
            r = need('chrome_bore'); total += r['base'] + r['per_stroke'] * q.stroke
        if q.extra_thread > 0:
            total += need('extra_thread')['per_length'] * q.extra_thread
        if q.rod_gland_drain and s not in {'A','LH'}:
            total += need('rod_gland_drain')['fixed']
        if q.air_bleed_qty > D('0.1'):
            total += need('air_bleed')['fixed_each'] * q.air_bleed_qty
        if q.prox_switch_qty > (D('0') if s in {'A','LH'} else D('0.01')):
            total += need('prox_switch')['fixed_each'] * q.prox_switch_qty
        if q.brass_wiper and s not in {'A','LH'}:
            total += need('brass_wiper')['fixed']

        seal = q.seal_code.upper()
        # H3/A3 Viton are intentionally NOT added here: their actual worksheet
        # formulas are ungated and are handled once by _legacy_ungated_modifications.
        if s in {'IH','IHM','IMH'} and seal in {'V','H'}:
            r = need('viton_highload_metric'); v = r['rod'] + r['piston']; total += v if seal == 'V' else v * 2

        if q.extra_port_qty > D('0.1'):
            total += need('extra_port')['fixed_each'] * q.extra_port_qty
        if s == 'HM':
            total += need('light_duty_mill')['fixed']
        # H4 flange is handled by the ungated compatibility path. IH4 is properly gated.
        if q.port_code.upper() == 'F' and s in {'IH','IHM','IMH'}:
            total += need('flange_port')['fixed_each'] * (D('2') + q.extra_port_qty)
        # A4 calculations exist but Data!D6 references blank A4!O55, so A/LH
        # Extra Tie Rod and UltraOx do not reach selling price in the legacy workbook.
        if q.extra_tie_rod_qty > D('0.1') and s not in {'A','LH'}:
            total += need('extra_tie_rod')['per_length'] * D('4') * q.extra_tie_rod_qty
        if seal == 'C' and s not in {'A','LH'}:
            total += need('cipr')['fixed']
        if q.ultraox and s not in {'A','LH'}:
            r = need('ultraox'); total += r['base'] + r['per_stroke'] * q.stroke
        if seal in {'B','L'} and s not in {'A','LH'}:
            r = need('buna_highload_seals'); total += r['buna'] + r['high_load']
        # Thick Head is handled by the ungated compatibility path above.
        return total

    def _rod_thread(self, q: QuoteInputs):
        if q.series.upper() == 'VA':
            row = self.data.find_va_base(q.bore, q.rod_diameter)
        else:
            row = self.data.find_series_row(q.series, q.bore, q.rod_diameter)
        if q.rod_style in {1,3}:
            return row['standard_thread']
        if q.rod_style == 2:
            return row['oversize_thread']
        return None

    def _accessory_bucket(self, q: QuoteInputs):
        """Reproduce Acc!T5:T12 series/bore/mount bucket selection."""
        s=q.series.upper(); b=q.bore; m=q.mount.upper()
        if s == 'H':
            if b == D('1.5') and m == 'MP1': return 'T5'
            if b > D('1.51') and b < D('2.6') and m == 'MP1': return 'T6'
            if b == D('3.25') and m == 'MP1': return 'T7'
            if b == D('4') and m in {'MP1','MP2'}: return 'T8'
            if b == D('5') and m in {'MP1','MP2'}: return 'T9'
            if b == D('6') and m in {'MP1','MP2'}: return 'T10'
            if b == D('7') and m in {'MP1','MP2'}: return 'T11'
            if b == D('8') and m in {'MP1','MP2'}: return 'T12'
        if s in {'A','LH'} and m == 'MP1':
            if b < D('2.6'): return 'T5'
            if b > D('2.6') and b < D('5.1'): return 'T6'
            if b > D('5.1') and b < D('8.1'): return 'T7'
        return None

    def _accessory_total(self, q: QuoteInputs, warnings) -> Decimal:
        total = D('0')
        thread = self._rod_thread(q)
        bucket = self._accessory_bucket(q)
        thread_direct = {'Rod Clevis','Rod Eye','Self-Aligning Male Eye','SA - Clevis Bracket','Alignment Coupler','Male Rod Eye'}
        thread_group = {'Eye Bracket','Pivot Pin'}
        rod_direct = {'Safety Coupler'}
        rod_legacy = {'Rod Stud','Jam Nut'}

        for name, qty in q.accessory_quantities.items():
            qty = dec(qty)
            if qty <= 0: continue
            canonical = 'Rod Eye' if name == 'Female Rod Eye' else name
            row = None
            if canonical in thread_direct and thread:
                row = self.data.find_accessory('thread', thread, canonical)
            elif canonical in thread_group and thread:
                row = self.data.find_accessory('thread_group', thread, canonical)
            elif canonical in rod_direct:
                row = self.data.find_accessory('rod_diameter', fmt_code_number(q.rod_diameter), canonical)
            elif canonical in rod_legacy:
                row = self.data.find_accessory('rod_diameter_legacy', fmt_code_number(q.rod_diameter), canonical)
                if row:
                    warnings.append(f'Legacy parity: {canonical} is selected by rod diameter rather than rod thread.')
            elif canonical in {'Clevis Bracket','SA - Pivot Pin'} and bucket:
                row = self.data.find_accessory('bore_mount_bucket', bucket, canonical)
            elif canonical == 'Weld Plate':
                row = self.data.find_accessory('rod_diameter', fmt_code_number(q.rod_diameter), canonical)
                if row:
                    total += dec(row['price'])
                    if qty != D('1'):
                        warnings.append('Legacy parity: Weld Plate quantity acts only as an on/off trigger; price is not multiplied by quantity.')
                    continue
            else:
                warnings.append(f'Accessory {name!r} has no active legacy price for this configuration; contributes 0.')
                continue
            if row:
                total += dec(row['price']) * qty
            else:
                warnings.append(f'Accessory {name!r} has no active legacy price for this configuration; contributes 0.')

        if q.standard_rod_boot_qty > 0:
            r = self.data.find_rod_boot(q.rod_diameter)
            if r:
                # Exact Acc!D54:D68 behavior: base is charged once; only stroke component is multiplied by quantity.
                total += dec(r['base_price']) + dec(r['per_stroke_rate']) * q.stroke * q.standard_rod_boot_qty
                if q.standard_rod_boot_qty != D('1'):
                    warnings.append('Legacy parity: Standard Rod Boot base price is charged once; quantity multiplies only the stroke-dependent portion.')
            else:
                warnings.append('Standard Rod Boot has no active legacy rate for this rod diameter; contributes 0.')
        return total

    def _special_parts_total(self, q: QuoteInputs) -> Decimal:
        total = D('0')
        for part, qty in q.special_parts.items():
            if qty <= 0: continue
            r = self.data.find_special_part(part)
            total += dec(r['price']) * qty
        return total

    def _position_sensing(self, q: QuoteInputs, warnings) -> Decimal:
        if not (q.transducer or q.prepped_for_transducer or q.sensor_cover or q.valve_manifold):
            return D('0')
        metric = q.series.upper() in {'IH','IHM','IMH'}
        r = self.data.find_ph(metric, q.bore)
        total = D('0')
        if q.transducer or q.prepped_for_transducer:
            total += dec(r['gun_drill_base']) + dec(r['gun_drill_per_stroke']) * q.stroke
        if q.sensor_cover:
            # Exact legacy PH formula: certain mounts use D-column price *2, otherwise hard-coded 358.
            total += dec(r['sensor_cover']) * 2 if q.mount.upper() in {'MP1','MP2','MP3','MPU3'} else D('358')
            if metric:
                warnings.append('Metric PH sensor-cover path intentionally reproduces legacy worksheet reference behavior.')
        if q.valve_manifold:
            total += dec(r['valve_manifold_base']) + dec(r['valve_manifold_per_stroke']) * q.stroke
        if q.transducer:
            total += self._sensor_band(metric, q.stroke)
        return total

    def _sensor_band(self, metric: bool, stroke: Decimal) -> Decimal:
        rows = [r for r in self.data.ph_bands if r['system'] == ('metric' if metric else 'imperial')]
        if metric:
            for r in rows:
                if stroke < dec(r['max_stroke']) + D('0.0000001'):
                    return dec(r['price'])
            return D('0')
        bands = [(D('0'),D('13')), (D('12.9'),D('25')), (D('24.9'),D('37')), (D('36.9'),D('49')),
                 (D('48.9'),D('61')), (D('60.9'),D('73')), (D('72.9'),D('85')), (D('84.9'),D('97')), (D('96.9'),D('180'))]
        for r,(lo,hi) in zip(rows,bands):
            if stroke > lo and stroke < hi:
                return dec(r['price'])
        return D('0')

    def _va_total(self, q: QuoteInputs, warnings) -> Decimal:
        b = self.data.find_va_base(q.bore, q.rod_diameter)
        m = self.data.find_va_mod(q.bore, q.rod_diameter)
        total = dec(b['base_price']) + dec(b['stroke_rate']) * q.stroke
        if q.extra_thread > D('0.001'):
            total += dec(m['extra_thread_per_in']) * q.extra_thread
        if q.rod_extension > D('0.001'):
            total += dec(m['rod_extension_per_in']) * q.rod_extension
        if q.stainless_rod:
            total += dec(m['stainless_rod_base']) + dec(m['stainless_rod_per_in_stroke']) * q.stroke
        if q.seal_code.upper() == 'V':
            total += dec(m['viton_seals'])
        if q.extra_tie_rod_qty > D('0.001'):
            # Legacy workbook bug/quirk: trigger B25 but formula multiplies by B27 (extra thread), not B25.
            total += dec(m['extra_tie_rod_per_in']) * q.extra_thread
            warnings.append('VA Extra Tie Rod reproduces legacy B25-trigger/B27-multiplier behavior.')
        return total
