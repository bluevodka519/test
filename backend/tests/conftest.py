import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DEFAULT_DATA_DIR, Settings  # noqa: E402
from app.couriers.auspost import clear_caches  # noqa: E402
from app.couriers.tnt import clear_cache as clear_tnt_cache  # noqa: E402

BASE = "https://courier.test/shipping/v1"


@pytest.fixture(autouse=True)
def _clear_courier_caches():
    clear_caches()
    clear_tnt_cache()
    yield
    clear_caches()
    clear_tnt_cache()


@pytest.fixture
def rates():
    return json.loads((DEFAULT_DATA_DIR / "shipping_rates.json").read_text(encoding="utf-8"))


@pytest.fixture
def unconfigured():
    return Settings(_env_file=None)


@pytest.fixture
def configured():
    return Settings(
        _env_file=None,
        auspost_base_url=BASE, auspost_api_key="key", auspost_password="pw",
        auspost_account="111", startrack_account="222",
        auspost_product_id="PP", startrack_product_id="EXP",
        courier_timeout_seconds=2,
    )


def product_row(sku, rrp="110.00", gross="0.5kg", weight="100g", l="100mm", w="100mm", h="100mm", volume="1000000mm³"):
    return {"SKU": sku, "ProductName": f"Name {sku}\n", "Description": "desc\n", "RRP": rrp,
            "Volumetric_GrossWeight": gross, "weight": weight, "length": l, "width": w, "height": h, "volume": volume}


def write_dataset(tmp_path: Path, orders, lines, shipments, rows):
    for name in ("shipping_rates.json",):
        (tmp_path / name).write_text((DEFAULT_DATA_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "orders.json").write_text(json.dumps(orders), encoding="utf-8")
    (tmp_path / "order_lines.json").write_text(json.dumps(lines), encoding="utf-8")
    (tmp_path / "shipments.json").write_text(json.dumps(shipments), encoding="utf-8")
    (tmp_path / "product_list.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")
    return tmp_path


def order(no, state="VIC", postcode="3141"):
    return {"order_no": no, "order_date": "2025-11-30", "status": "Completed", "customer": "C",
            "address": {"street": "1 St", "suburb": "Sub", "state": state, "postcode": postcode}}
