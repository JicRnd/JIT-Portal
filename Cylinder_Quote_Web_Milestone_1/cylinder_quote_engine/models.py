from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping

D = Decimal

@dataclass(frozen=True)
class QuoteInputs:
    series: str
    bore: Decimal
    rod_diameter: Decimal
    mount: str
    stroke: Decimal
    cushion: str = "NC"
    port_code: str = ""
    seal_code: str = ""
    rod_style: int = 1
    discount: Decimal = D("0")
    dre: bool = False

    rod_extension: Decimal = D("0")
    stop_tube: Decimal = D("0")
    stainless_rod: bool = False
    chrome_bore: bool = False
    extra_thread: Decimal = D("0")
    rod_gland_drain: bool = False
    air_bleed_qty: Decimal = D("0")
    prox_switch_qty: Decimal = D("0")
    brass_wiper: bool = False
    extra_port_qty: Decimal = D("0")
    extra_tie_rod_qty: Decimal = D("0")
    ultraox: bool = False
    thick_head_qty: Decimal = D("0")

    transducer: bool = False
    prepped_for_transducer: bool = False
    sensor_cover: bool = False
    valve_manifold: bool = False

    accessory_quantities: Mapping[str, Decimal] = field(default_factory=dict)
    special_parts: Mapping[str, Decimal] = field(default_factory=dict)
    standard_rod_boot_qty: Decimal = D("0")

    # Compatibility hook for worksheet paths not yet normalized.
    legacy_post_discount_add: Decimal = D("0")  # Data!H24
    legacy_reserved_add: Decimal = D("0")       # Data!C10


@dataclass(frozen=True)
class PriceBreakdown:
    model_code: str
    base_price: Decimal
    stroke_cushion: Decimal
    modifications: Decimal
    accessories: Decimal
    special_parts: Decimal
    position_sensing: Decimal
    va_total: Decimal
    dre_surcharge: Decimal
    pre_discount_subtotal: Decimal
    discount_amount: Decimal
    working_net_each: Decimal
    list_price: Decimal
    quote_list_price: Decimal
    quote_net_each: Decimal
    expedited_price: Decimal
    emergency_price: Decimal
    warnings: tuple[str, ...] = ()
