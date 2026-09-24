"""Money rules.

RRP (Recommended Retail Price) is the SKU price, in AUD, and INCLUDES GST
(brief FAQ 1 and "Confirmed tax treatment"). The PDF's line total =
price x quantity would therefore add GST twice, so prices are first
converted back to ex-GST:

    Ex-GST unit price  = RRP / 1.10
    Line subtotal      = Ex-GST unit price x quantity        (ex GST)
    Order subtotal     = sum of line subtotals               (ex GST)
    GST                = order subtotal x 10%
    Order total        = subtotal + GST + shipment fee

Values are kept at full precision and only rounded to cents for display,
so subtotal + GST always equals the sum of RRP x quantity exactly.
"""
from decimal import ROUND_HALF_UP, Decimal

from app.models import Totals

GST_RATE = Decimal("0.10")
GST_DIVISOR = 1 + GST_RATE
CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def unit_price_ex_gst(rrp: Decimal) -> Decimal:
    """Exact (unrounded) ex-GST unit price."""
    return rrp / GST_DIVISOR


def line_subtotal_ex_gst(rrp: Decimal, quantity: int) -> Decimal:
    """Exact (unrounded) ex-GST line subtotal."""
    return rrp * quantity / GST_DIVISOR


def order_totals(line_subtotals: list[Decimal], shipment_fee: Decimal) -> Totals:
    """`line_subtotals` are the exact ex-GST values; results are rounded to cents."""
    exact = sum(line_subtotals, Decimal(0))
    subtotal = money(exact)
    gst = money(exact * GST_RATE)
    fee = money(shipment_fee)
    return Totals(
        subtotal_ex_gst=subtotal,
        gst=gst,
        shipment_fee=fee,
        total=subtotal + gst + fee,
    )
