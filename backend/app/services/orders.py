"""Assemble an order: match SKUs, validate lines, group into shipments,
fetch tracking, quote fees and compute totals. Each order is independent.
"""
import asyncio
from collections import defaultdict
from decimal import Decimal
from typing import Optional

from app.couriers.auspost import AusPostClient
from app.couriers.tnt import TntClient
from app.models import (
    Carrier, LineResult, LineStatus, OrderDetail, OrderIn, OrderSummary,
    ShipmentResult, TrackingResult, TrackingStatus,
)
from app.services import pricing
from app.services.loader import Dataset, close_order_no
from app.services.products import Product, normalise_sku
from app.services.shipping import build_parcel, quote_shipment


def parse_quantity(raw) -> Optional[int]:
    """A quantity must be a whole number >= 1. Returns None when invalid."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, float) and raw.is_integer():
        value = int(raw)
    elif isinstance(raw, str) and raw.strip().isdigit():
        value = int(raw.strip())
    else:
        return None
    return value if value >= 1 else None


def evaluate_line(position: int, line, ds: Dataset) -> tuple[LineResult, Optional[Product], Optional[int]]:
    sku = normalise_sku(line.sku)
    product = ds.products.get(sku)
    result = LineResult(
        position=position, sku=line.sku, quantity=line.quantity,
        tracking_ref=line.tracking_ref, status=LineStatus.OK,
        image_url=ds.images.get(sku),
    )
    if product is not None:
        result.name = product.name
        result.description = product.description
        result.rrp = product.rrp
        if product.rrp is not None:
            result.unit_price_ex_gst = pricing.money(pricing.unit_price_ex_gst(product.rrp))

    qty = parse_quantity(line.quantity)
    if product is None:
        result.status = LineStatus.SKU_NOT_FOUND
        result.message = "SKU not found in product data. Excluded from totals."
    elif qty is None:
        result.status = LineStatus.INVALID_QTY
        result.message = f"Invalid quantity {line.quantity!r} (must be a whole number ≥ 1). Excluded from totals."
    elif product.rrp is None:
        result.status = LineStatus.BAD_PRODUCT_DATA
        result.message = "Product has no valid RRP. Excluded from totals."
    else:
        result.line_subtotal_ex_gst = pricing.money(pricing.line_subtotal_ex_gst(product.rrp, qty))
        return result, product, qty
    return result, None, None


async def _track_all(shipments_in: list, auspost: AusPostClient, tnt: TntClient) -> dict[str, TrackingResult]:
    by_carrier: dict[Carrier, list[str]] = defaultdict(list)
    for s in shipments_in:
        if s is not None and s.tracking_no not in by_carrier[s.carrier]:
            by_carrier[s.carrier].append(s.tracking_no)

    async def run(carrier: Carrier, nos: list[str]):
        if carrier == Carrier.TNT:
            return await tnt.track_many(nos)
        return await auspost.track_many(nos, carrier)

    results: dict[str, TrackingResult] = {}
    for part in await asyncio.gather(*(run(c, nos) for c, nos in by_carrier.items())):
        results.update(part)
    return results


async def build_order(order: OrderIn, ds: Dataset, auspost: AusPostClient, tnt: TntClient,
                      include_tracking: bool = True) -> OrderDetail:
    warnings: list[str] = []
    order_lines = [l for l in ds.lines if l.order_no == order.order_no]
    if not order_lines:
        near = sorted({l.order_no for l in ds.lines if close_order_no(l.order_no, [order.order_no])})
        warnings.append(
            "Order has no SKU lines."
            + (f" SKU lines exist for {', '.join(near)}, which looks like a typo of this order number;"
               " they are not merged automatically." if near else "")
        )

    # Group lines by tracking ref, keeping first-seen order.
    groups: dict[str, list[tuple[LineResult, Optional[Product], Optional[int]]]] = {}
    for position, line in enumerate(order_lines, start=1):
        evaluated = evaluate_line(position, line, ds)
        groups.setdefault(line.tracking_ref, []).append(evaluated)
        result, product, _ = evaluated
        if result.status != LineStatus.OK:
            warnings.append(f"{result.sku}: {result.message}")
        elif product.warnings:
            warnings.append(f"{result.sku}: product data issues: {'; '.join(product.warnings)}")

    shipments_in = {ref: ds.shipments.get(ref) for ref in groups}
    for ref, s in shipments_in.items():
        if s is None:
            warnings.append(f"Tracking reference {ref!r} is not in shipments.json.")

    if include_tracking:
        tracking = await _track_all(list(shipments_in.values()), auspost, tnt)
    else:
        tracking = {}

    async def fee_for(ref: str):
        s = shipments_in[ref]
        items = [(p, q) for _, p, q in groups[ref] if p is not None]
        parcel, notes = build_parcel(items, ds.rates)
        fee = await quote_shipment(s.carrier if s else None, parcel, order.address, ds.rates, auspost)
        if notes:
            fee.note = f"{fee.note} Parcel notes: {'; '.join(notes)}."
        return fee

    fees = await asyncio.gather(*(fee_for(ref) for ref in groups))

    shipments: list[ShipmentResult] = []
    line_totals: list[Decimal] = []
    for (ref, evaluated), fee in zip(groups.items(), fees):
        s = shipments_in[ref]
        if s is None:
            track = TrackingResult(status=TrackingStatus.NO_DATA, message="No tracking number for this reference.")
        elif not include_tracking:
            track = TrackingResult(status=TrackingStatus.NOT_REQUESTED, carrier=s.carrier.value, tracking_no=s.tracking_no)
        else:
            track = tracking.get(s.tracking_no) or TrackingResult(
                status=TrackingStatus.UNAVAILABLE, carrier=s.carrier.value, tracking_no=s.tracking_no,
                message="No tracking result returned.",
            )
        line_results = [r for r, _, _ in evaluated]
        # Totals use the exact values; the rounded ones are only for display.
        line_totals += [pricing.line_subtotal_ex_gst(p.rrp, q) for _, p, q in evaluated if p is not None]
        shipments.append(ShipmentResult(
            tracking_ref=ref,
            tracking_no=s.tracking_no if s else None,
            carrier=s.carrier.value if s else None,
            logistics_company=s.logistics_company if s else None,
            lines=line_results, tracking=track, fee=fee,
        ))

    totals = pricing.order_totals(line_totals,sum((f.amount for f in fees), pricing.ZERO))
    return OrderDetail(order=order, shipments=shipments, totals=totals, warnings=warnings)


def summarise(detail: OrderDetail) -> OrderSummary:
    o = detail.order
    return OrderSummary(
        order_no=o.order_no, order_date=o.order_date, status=o.status,
        customer=o.customer, company=o.company, is_test=o.is_test,
        line_count=sum(len(s.lines) for s in detail.shipments),
        total=detail.totals.total, warning_count=len(detail.warnings),
    )
