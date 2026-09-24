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


def test_line_total_is_price_times_quantity():
    assert pricing.line_total(Decimal("175.00"), 3) == Decimal("525.00")
    assert pricing.line_total(Decimal("12.345"), 1) == Decimal("12.35")  # half-up at the cent
    assert pricing.money(Decimal("0.055")) == Decimal("0.06")


def test_order_totals_follow_pdf_formula():
    # PDF: Subtotal = Σ price × qty; GST = 10% of Subtotal; Total = Subtotal + GST + Fee
    lines = [pricing.line_total(Decimal("22"), 2), pricing.line_total(Decimal("33"), 1)]
    t = pricing.order_totals(lines, Decimal("10"))
    assert (t.subtotal, t.gst, t.shipment_fee, t.total) == (
        Decimal("77.00"), Decimal("7.70"), Decimal("10.00"), Decimal("94.70"))


def test_gst_rounds_half_up():
    t = pricing.order_totals([Decimal("0.05")], Decimal("0"))
    assert t.gst == Decimal("0.01")  # 0.005 -> 0.01


def test_order_totals_serialise_as_strings():
    t = pricing.order_totals([Decimal("1.00")], Decimal("0"))
    assert t.model_dump(mode="json")["total"] == "1.10"
