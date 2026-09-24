"""Read the local JSON data files.

Files are re-read on every request so replacing a data file (e.g. a fresh
product query) takes effect without restarting the server.
"""
import difflib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from app.models import OrderIn, OrderLineIn, ShipmentIn
from app.services.products import Product, index_products


@dataclass
class Dataset:
    orders: list[OrderIn]
    lines: list[OrderLineIn]
    shipments: dict[str, ShipmentIn]
    products: dict[str, Product]
    images: dict[str, str]
    rates: dict
    warnings: list[str] = field(default_factory=list)


def _read_json(path: Path, default=None):
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"Missing data file: {path.name}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _parse_list(raw: list, model, label: str, warnings: list[str]):
    items = []
    for i, entry in enumerate(raw):
        try:
            items.append(model.model_validate(entry))
        except ValidationError as e:
            warnings.append(f"{label} #{i + 1} skipped: {e.errors()[0]['msg']}")
    return items


def load_dataset(data_dir: Path) -> Dataset:
    warnings: list[str] = []

    orders = _parse_list(_read_json(data_dir / "orders.json"), OrderIn, "Order", warnings)
    lines = _parse_list(_read_json(data_dir / "order_lines.json"), OrderLineIn, "Order line", warnings)
    shipment_list = _parse_list(_read_json(data_dir / "shipments.json"), ShipmentIn, "Shipment", warnings)
    shipments = {s.tracking_ref: s for s in shipment_list}

    # Every product_*.json file is a raw query response; they are merged.
    query_results = [_read_json(p) for p in sorted(data_dir.glob("product_*.json")) if p.name != "product_images.json"]
    products, product_warnings = index_products(query_results)
    warnings += product_warnings

    images_raw = _read_json(data_dir / "product_images.json", default={})
    images = {k.strip().upper(): v for k, v in images_raw.get("images", {}).items() if v}
    rates = _read_json(data_dir / "shipping_rates.json")

    # Data-quality checks across files. Lines are never re-assigned automatically;
    # a near-identical order number is only suggested as a probable typo.
    order_nos = [o.order_no for o in orders]
    for line in lines:
        if line.order_no not in order_nos:
            hint = close_order_no(line.order_no, order_nos)
            warnings.append(
                f"Line {line.sku} refers to unknown order {line.order_no} (not shown in any order)"
                + (f"; did you mean {hint}?" if hint else "")
            )

    return Dataset(orders, lines, shipments, products, images, rates, warnings)


def close_order_no(order_no: str, candidates: list[str]) -> Optional[str]:
    matches = difflib.get_close_matches(order_no, candidates, n=1, cutoff=0.9)
    return matches[0] if matches else None
