from decimal import Decimal

from app.services import pricing
from app.services.products import (
    LENGTH_TO_MM, VOLUME_TO_MM3, WEIGHT_TO_KG, index_products, parse_measure, parse_product,
)
from conftest import product_row


def test_parse_measure_units():
    assert parse_measure("10.0mm", LENGTH_TO_MM) == Decimal("10.0")
    assert parse_measure("2cm", LENGTH_TO_MM) == Decimal("20")
    assert parse_measure("0.2g", WEIGHT_TO_KG) == Decimal("0.0002")
    assert parse_measure("0.2kg", WEIGHT_TO_KG) == Decimal("0.2")
    assert parse_measure("1000.0mm³", VOLUME_TO_MM3) == Decimal("1000.0")
    assert parse_measure("15", LENGTH_TO_MM, default_unit="mm") == Decimal("15")


def test_parse_measure_bad_values_are_none():
    for raw in (None, "", "abc", "10 furlongs", "nullmm"):
        assert parse_measure(raw, LENGTH_TO_MM) is None


def test_parse_product_cleans_text_and_flags_bad_fields():
    p = parse_product(product_row(" tbamet10 ", rrp="n/a", gross="heavy"))
    assert p.sku == "TBAMET10"
    assert p.name == "Name tbamet10"
    assert p.rrp is None
    assert p.gross_weight_kg is None
    assert p.shipping_weight_kg == Decimal("0.100")  # falls back to net weight
    assert any("RRP" in w for w in p.warnings)


def test_shipping_weight_uses_heavier_of_gross_and_net():
    # Real data: HALGEO15 has Volumetric_GrossWeight 0.02kg but weight 68.0g.
    p = parse_product(product_row("HALGEO15", gross="0.02kg", weight="68.0g"))
    assert p.shipping_weight_kg == Decimal("0.0680")
    p = parse_product(product_row("TBAMET28", gross="0.4kg", weight="93.0g"))
    assert p.shipping_weight_kg == Decimal("0.4")


def test_index_products_first_file_wins():
    products, _ = index_products([{"rows": [product_row("A", rrp="11")]}, {"rows": [product_row("a", rrp="22")]}])
    assert products["A"].rrp == Decimal("11")


def test_rrp_includes_gst_so_price_is_backed_out():
    assert pricing.money(pricing.unit_price_ex_gst(Decimal("22.00"))) == Decimal("20.00")
    assert pricing.money(pricing.unit_price_ex_gst(Decimal("199.00"))) == Decimal("180.91")
    assert pricing.money(pricing.line_subtotal_ex_gst(Decimal("149.00"), 4)) == Decimal("541.82")
    assert pricing.money(Decimal("0.055")) == Decimal("0.06")  # half-up at the cent


def test_order_totals_match_brief_example():
    # Brief mock-up: RRP A$22 x2 + A$33 x1, fee A$10 -> 70.00 / 7.00 / 10.00 / 87.00
    lines = [pricing.line_subtotal_ex_gst(Decimal("22"), 2), pricing.line_subtotal_ex_gst(Decimal("33"), 1)]
    t = pricing.order_totals(lines, Decimal("10"))
    assert (t.subtotal_ex_gst, t.gst, t.shipment_fee, t.total) == (
        Decimal("70.00"), Decimal("7.00"), Decimal("10.00"), Decimal("87.00"))


def test_subtotal_plus_gst_equals_rrp_total_for_real_orders():
    # Order 1 and order 2 line items (RRP incl. GST, quantity) from the supplied data.
    order1 = [("99.00", 3), ("199.00", 1), ("199.00", 1), ("149.00", 4), ("140.00", 6)]
    order2 = [("99.00", 10), ("110.00", 1), ("129.00", 2), ("99.00", 3)]
    for lines, rrp_total, subtotal, gst in ((order1, "2131.00", "1937.27", "193.73"),
                                             (order2, "1655.00", "1504.55", "150.45")):
        t = pricing.order_totals([pricing.line_subtotal_ex_gst(Decimal(r), q) for r, q in lines], Decimal("0"))
        assert (t.subtotal_ex_gst, t.gst) == (Decimal(subtotal), Decimal(gst))
        assert t.total == Decimal(rrp_total)  # no GST double-counting, no 1-cent drift


def test_order_totals_serialise_as_strings():
    t = pricing.order_totals([Decimal("1.00")], Decimal("0"))
    assert t.model_dump(mode="json")["total"] == "1.10"
