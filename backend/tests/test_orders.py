import asyncio
from decimal import Decimal

import pytest

from app.couriers.auspost import AusPostClient
from app.couriers.tnt import TntClient
from app.models import FeeSource, LineStatus, TrackingStatus
from app.services.loader import load_dataset
from app.services.orders import build_order, parse_quantity
from conftest import order, product_row, write_dataset


@pytest.mark.parametrize("raw,expected", [
    (3, 3), ("4", 4), (2.0, 2), (0, None), (-1, None), (1.5, None), ("abc", None), (None, None), (True, None),
])
def test_parse_quantity(raw, expected):
    assert parse_quantity(raw) == expected


def _build(tmp_path, settings, lines, shipments, rows, orders=None):
    ds = load_dataset(write_dataset(tmp_path, orders or [order("PO-1")], lines, shipments, rows))
    detail = asyncio.run(build_order(ds.orders[0], ds, AusPostClient(settings), TntClient()))
    return ds, detail


def test_bad_lines_are_shown_but_excluded_from_totals(tmp_path, unconfigured):
    lines = [
        {"sku": "A", "quantity": 2, "tracking_ref": "T1", "order_no": "PO-1"},
        {"sku": "MISSING", "quantity": 1, "tracking_ref": "T1", "order_no": "PO-1"},
        {"sku": "A", "quantity": 0, "tracking_ref": "T1", "order_no": "PO-1"},
        {"sku": "BADPRICE", "quantity": 1, "tracking_ref": "T1", "order_no": "PO-1"},
    ]
    shipments = [{"tracking_ref": "T1", "tracking_no": "X1", "carrier": "AUSPOST"}]
    rows = [product_row("A", rrp="110.00"), product_row("BADPRICE", rrp="")]
    _, d = _build(tmp_path, unconfigured, lines, shipments, rows)

    statuses = [l.status for l in d.shipments[0].lines]
    assert statuses == [LineStatus.OK, LineStatus.SKU_NOT_FOUND, LineStatus.INVALID_QTY, LineStatus.BAD_PRODUCT_DATA]
    assert d.shipments[0].lines[0].unit_price == Decimal("110.00")
    assert d.shipments[0].lines[0].line_total == Decimal("220.00")
    assert d.totals.subtotal == Decimal("220.00")
    assert d.totals.gst == Decimal("22.00")
    assert len(d.warnings) == 3


def test_lines_grouped_into_shipments_per_tracking_ref(tmp_path, unconfigured):
    lines = [
        {"sku": "A", "quantity": 1, "tracking_ref": "T2", "order_no": "PO-1"},
        {"sku": "A", "quantity": 1, "tracking_ref": "T3", "order_no": "PO-1"},
        {"sku": "A", "quantity": 1, "tracking_ref": "T2", "order_no": "PO-1"},
    ]
    shipments = [{"tracking_ref": "T2", "tracking_no": "S2", "carrier": "STARTRACK"},
                 {"tracking_ref": "T3", "tracking_no": "S3", "carrier": "TNT"}]
    _, d = _build(tmp_path, unconfigured, lines, shipments, [product_row("A")])

    assert [s.tracking_ref for s in d.shipments] == ["T2", "T3"]
    assert [len(s.lines) for s in d.shipments] == [2, 1]
    assert d.shipments[0].tracking.status == TrackingStatus.NOT_CONFIGURED
    assert d.shipments[1].tracking.status == TrackingStatus.NOT_IMPLEMENTED
    # TNT fee is always 0.00; StarTrack falls back to the formula when not configured.
    assert d.shipments[1].fee.amount == Decimal("0.00")
    assert d.shipments[1].fee.source == FeeSource.NOT_AVAILABLE
    assert d.shipments[0].fee.source == FeeSource.FORMULA_ESTIMATE
    assert d.totals.shipment_fee == d.shipments[0].fee.amount


def test_orders_are_independent(tmp_path, unconfigured):
    lines = [{"sku": "A", "quantity": 1, "tracking_ref": "T1", "order_no": "PO-1"},
             {"sku": "A", "quantity": 5, "tracking_ref": "T1", "order_no": "PO-2"}]
    shipments = [{"tracking_ref": "T1", "tracking_no": "S1", "carrier": "AUSPOST"}]
    ds, d = _build(tmp_path, unconfigured, lines, shipments, [product_row("A")], orders=[order("PO-1"), order("PO-2")])
    assert sum(len(s.lines) for s in d.shipments) == 1


def test_orphan_lines_and_unknown_tracking_ref_are_reported(tmp_path, unconfigured):
    lines = [{"sku": "A", "quantity": 1, "tracking_ref": "NOPE", "order_no": "PO-1"},
             {"sku": "A", "quantity": 1, "tracking_ref": "T1", "order_no": "PO-20251202-00046"}]
    ds, d = _build(tmp_path, unconfigured, lines, [], [product_row("A")])
    assert any("PO-20251202-00046" in w for w in ds.warnings)
    assert not any("did you mean" in w for w in ds.warnings)  # PO-1 is not a near match
    assert any("NOPE" in w for w in d.warnings)
    assert d.shipments[0].tracking.status == TrackingStatus.NO_DATA
    assert d.shipments[0].fee.amount == Decimal("0.00")


def test_pdf_order_number_typo_is_flagged_not_merged(tmp_path, unconfigured):
    # PDF: header says PO-20251202-00046, its SKU lines say PO-20251203-00046.
    lines = [{"sku": "A", "quantity": 1, "tracking_ref": "T1", "order_no": "PO-20251203-00046"}]
    ds, d = _build(tmp_path, unconfigured, lines, [], [product_row("A")], orders=[order("PO-20251202-00046")])
    assert any("did you mean PO-20251202-00046" in w for w in ds.warnings)
    assert d.shipments == []
    assert d.totals.total == Decimal("0.00")
    assert "looks like a typo" in d.warnings[0]
