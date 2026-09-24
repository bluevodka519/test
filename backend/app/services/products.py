"""Parse the raw SQL-like query output into typed products.

Every value in the query output is a string, often with units attached
("175.00", "10.0mm", "0.2g", "1000.0mm³", "0.2kg") and stray newlines.
Anything that cannot be parsed becomes None plus a warning, never an error.
"""
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional

_MEASURE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*([a-zA-Z³]*)\s*$")

LENGTH_TO_MM = {"mm": Decimal(1), "cm": Decimal(10), "m": Decimal(1000)}
WEIGHT_TO_KG = {"g": Decimal("0.001"), "kg": Decimal(1)}
VOLUME_TO_MM3 = {"mm³": Decimal(1), "mm3": Decimal(1), "cm³": Decimal(1000), "cm3": Decimal(1000)}


def normalise_sku(sku: str) -> str:
    return (sku or "").strip().upper()


def parse_measure(raw, units: dict[str, Decimal], default_unit: Optional[str] = None) -> Optional[Decimal]:
    """Parse "10.0mm" style values into the base unit of `units`. None if unparseable."""
    if raw is None:
        return None
    m = _MEASURE.match(str(raw))
    if not m:
        return None
    number, unit = m.group(1), m.group(2).lower()
    if not unit:
        unit = default_unit
    if unit not in units:
        return None
    try:
        return Decimal(number) * units[unit]
    except InvalidOperation:
        return None


def parse_money(raw) -> Optional[Decimal]:
    if raw is None:
        return None
    text = str(raw).strip().replace("$", "").replace(",", "")
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def clean_text(raw) -> str:
    return " ".join(str(raw or "").split())


@dataclass
class Product:
    sku: str
    name: str
    description: str
    rrp: Optional[Decimal]
    length_mm: Optional[Decimal]
    width_mm: Optional[Decimal]
    height_mm: Optional[Decimal]
    volume_mm3: Optional[Decimal]
    net_weight_kg: Optional[Decimal]
    gross_weight_kg: Optional[Decimal]
    warnings: list[str] = field(default_factory=list)

    @property
    def shipping_weight_kg(self) -> Optional[Decimal]:
        """Heavier of gross and net weight.

        Gross (packed) weight is what couriers bill, but in the supplied data it is
        sometimes lighter than the net weight (e.g. 0.02kg vs 68g), which cannot be
        right, so the larger value is used.
        """
        known = [w for w in (self.gross_weight_kg, self.net_weight_kg) if w is not None]
        return max(known) if known else None

    @property
    def item_volume_mm3(self) -> Optional[Decimal]:
        if self.volume_mm3 is not None:
            return self.volume_mm3
        if None not in (self.length_mm, self.width_mm, self.height_mm):
            return self.length_mm * self.width_mm * self.height_mm
        return None


def parse_product(row: dict) -> Product:
    warnings = []

    def measure(key, units, default_unit=None):
        raw = row.get(key)
        value = parse_measure(raw, units, default_unit)
        if value is None and str(raw or "").strip():
            warnings.append(f"Could not parse {key}={raw!r}")
        return value

    rrp = parse_money(row.get("RRP"))
    if rrp is None:
        warnings.append(f"Could not parse RRP={row.get('RRP')!r}")
    elif rrp < 0:
        warnings.append(f"Negative RRP={row.get('RRP')!r}")
        rrp = None

    return Product(
        sku=normalise_sku(row.get("SKU", "")),
        name=clean_text(row.get("ProductName")),
        description=clean_text(row.get("Description")),
        rrp=rrp,
        length_mm=measure("length", LENGTH_TO_MM, "mm"),
        width_mm=measure("width", LENGTH_TO_MM, "mm"),
        height_mm=measure("height", LENGTH_TO_MM, "mm"),
        volume_mm3=measure("volume", VOLUME_TO_MM3, "mm³"),
        net_weight_kg=measure("weight", WEIGHT_TO_KG, "g"),
        gross_weight_kg=measure("Volumetric_GrossWeight", WEIGHT_TO_KG, "kg"),
        warnings=warnings,
    )


def index_products(query_results: list[dict]) -> tuple[dict[str, Product], list[str]]:
    """Merge one or more raw query responses ({rows: [...]}) into a SKU index."""
    products: dict[str, Product] = {}
    warnings: list[str] = []
    for result in query_results:
        for row in result.get("rows", []):
            product = parse_product(row)
            if not product.sku:
                warnings.append("Skipped a product row with no SKU")
                continue
            if product.sku in products:
                continue  # same SKU from several query files: first one wins
            products[product.sku] = product
    return products, warnings
