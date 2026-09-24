"""Shipment fee: courier price API first, documented formula as fallback.

Per shipment (one tracking number = one parcel):
  1. Build a parcel from the products in it (gross weight, packed carton size).
  2. AusPost/StarTrack -> ask the courier price API for a quote.
  3. If the quote is unavailable -> formula estimate from shipping_rates.json.
  4. TNT -> A$0.00 (integration not implemented, as the brief allows).
"""
import math
from decimal import ROUND_CEILING, Decimal
from typing import Optional

from app.couriers.auspost import AusPostClient
from app.models import Address, Carrier, Fee, FeeSource, Parcel
from app.services.pricing import ZERO, money
from app.services.products import Product

TENTH = Decimal("0.1")


def build_parcel(items: list[tuple[Product, int]], rates: dict) -> tuple[Optional[Parcel], list[str]]:
    notes: list[str] = []
    if not items:
        return None, notes
    carton = rates["carton"]

    weight = Decimal(str(carton["tare_kg"]))
    volume_mm3 = ZERO
    for product, qty in items:
        if product.shipping_weight_kg is None:
            notes.append(f"{product.sku}: no weight data, counted as 0 kg")
        else:
            weight += product.shipping_weight_kg * qty
        if product.item_volume_mm3 is None:
            notes.append(f"{product.sku}: no size data, not counted in carton volume")
        else:
            volume_mm3 += product.item_volume_mm3 * qty

    # One carton: at least the minimum box, scaled up evenly if the goods need more room.
    min_dims = [Decimal(str(carton[k])) for k in ("min_length_cm", "min_width_cm", "min_height_cm")]
    min_volume_cm3 = min_dims[0] * min_dims[1] * min_dims[2]
    needed_cm3 = volume_mm3 / 1000 * Decimal(str(carton["fill_factor"]))
    scale = max(1.0, (float(needed_cm3) / float(min_volume_cm3)) ** (1 / 3))
    dims = [(d * Decimal(str(scale))).quantize(TENTH, rounding=ROUND_CEILING) for d in min_dims]

    cubic_kg = dims[0] * dims[1] * dims[2] / Decimal(1_000_000) * Decimal(str(rates["cubic_factor_kg_per_m3"]))
    parcel = Parcel(
        weight_kg=weight.quantize(Decimal("0.001")),
        length_cm=dims[0], width_cm=dims[1], height_cm=dims[2],
        cubic_kg=cubic_kg.quantize(Decimal("0.001")),
        item_count=sum(qty for _, qty in items),
    )
    return parcel, notes


def _in_ranges(postcode: str, ranges: list[list[int]]) -> bool:
    try:
        pc = int(postcode)
    except (TypeError, ValueError):
        return False
    return any(lo <= pc <= hi for lo, hi in ranges)


def zone_for(dest: Address, rates: dict) -> str:
    state = dest.state.strip().upper()
    if state in rates.get("remote_states", []):
        return "REMOTE"
    metro = _in_ranges(dest.postcode, rates["metro_postcodes"].get(state, []))
    same_state = state == rates["origin"]["state"]
    if same_state:
        return "SAME_STATE_METRO" if metro else "SAME_STATE_REGIONAL"
    return "INTERSTATE_METRO" if metro else "INTERSTATE_REGIONAL"


def chargeable_kg(parcel: Parcel, rates: dict) -> Decimal:
    step = Decimal(str(rates["round_up_to_kg"]))
    raw = max(parcel.weight_kg, parcel.cubic_kg, Decimal(str(rates["minimum_chargeable_kg"])))
    return Decimal(math.ceil(raw / step)) * step


def formula_fee(parcel: Parcel, dest: Address, rates: dict) -> Fee:
    zone = zone_for(dest, rates)
    zone_rates = rates["zones"][zone]
    kg = chargeable_kg(parcel, rates)
    amount = money(Decimal(zone_rates["base"]) + Decimal(zone_rates["per_kg"]) * kg)
    return Fee(
        amount=amount, source=FeeSource.FORMULA_ESTIMATE, zone=zone_rates["label"],
        chargeable_kg=kg, parcel=parcel,
        note=f"{zone_rates['label']}: A${zone_rates['base']} + A${zone_rates['per_kg']}/kg × {kg} kg (assumed rates).",
    )


async def quote_shipment(
    carrier: Optional[Carrier], parcel: Optional[Parcel], dest: Address, rates: dict, auspost: AusPostClient,
) -> Fee:
    if parcel is None:
        return Fee(amount=ZERO, source=FeeSource.NO_ITEMS, note="No valid items in this parcel.")
    if carrier is None:
        return Fee(amount=ZERO, source=FeeSource.NOT_AVAILABLE, parcel=parcel,
                   note="Unknown tracking reference, so the courier is unknown.")
    if carrier == Carrier.TNT:
        return Fee(amount=ZERO, source=FeeSource.NOT_AVAILABLE, parcel=parcel,
                   note="TNT integration not implemented; fee shown as A$0.00 as the brief requires.")

    origin = rates["origin"]["postcode"]
    quote = await auspost.quote(carrier, origin, dest.postcode, parcel)
    if quote.amount is not None:
        return Fee(amount=money(quote.amount), source=FeeSource.COURIER_QUOTE, parcel=parcel,
                   chargeable_kg=chargeable_kg(parcel, rates), note=quote.note)

    fee = formula_fee(parcel, dest, rates)
    fee.note = f"Courier quote unavailable ({quote.note}) Using formula. {fee.note}"
    return fee
