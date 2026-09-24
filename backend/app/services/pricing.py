"""Money rules, following the original test PDF literally:

    Line Total = SKU price (RRP) × quantity
    Subtotal   = sum of all line totals
    GST        = 10% of Subtotal
    Total      = Subtotal + GST + Shipment Fee

Note: the PDF also says the SKU price already includes GST, so this
formula adds GST on top of a GST-inclusive price (see README).
"""
from decimal import ROUND_HALF_UP, Decimal

from app.models import Totals

GST_RATE = Decimal("0.10")
CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def line_total(price: Decimal, quantity: int) -> Decimal:
    return money(price * quantity)


def order_totals(line_totals: list[Decimal], shipment_fee: Decimal) -> Totals:
    subtotal = money(sum(line_totals, ZERO))
    gst = money(subtotal * GST_RATE)
    fee = money(shipment_fee)
    return Totals(
        subtotal=subtotal,
        gst=gst,
        shipment_fee=fee,
        total=money(subtotal + gst + fee),
    )
