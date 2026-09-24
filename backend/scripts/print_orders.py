"""Console / JSON output view (supplementary to the web UI).

Run from backend/:
    python scripts/print_orders.py                 # all orders, console table
    python scripts/print_orders.py PO-20251130-00072
    python scripts/print_orders.py --json          # same data as the API
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import get_settings  # noqa: E402
from app.couriers.auspost import AusPostClient  # noqa: E402
from app.couriers.tnt import TntClient  # noqa: E402
from app.services.loader import load_dataset  # noqa: E402
from app.services.orders import build_order  # noqa: E402


def aud(value) -> str:
    return "—" if value is None else f"A${value:,.2f}"


def print_order(d) -> None:
    o = d.order
    print("=" * 96)
    print(f"Order {o.order_no}  |  {o.order_date}  |  {o.status}{'  |  TEST DATA' if o.is_test else ''}")
    print(f"{o.company} — {o.customer}  |  {o.phone}  |  {o.email}")
    a = o.address
    print(f"Ship to: {a.street}, {a.suburb} {a.state} {a.postcode}")
    for s in d.shipments:
        print("-" * 96)
        t = s.tracking
        state = t.current_status if t.status.value == "OK" else t.status.value
        print(f"{s.tracking_ref}  {s.carrier or '?'}  {s.tracking_no or '—'}  tracking: {state}"
              f"{'  last update ' + t.last_update if t.last_update else ''}")
        if t.message:
            print(f"    {t.message}")
        print(f"  {'SKU':<16}{'Name':<44}{'Qty':>5}{'Price/unit':>14}{'Line total':>14}  Image")
        for l in s.lines:
            image = l.image_url or f"placeholder: Product {l.position}"
            print(f"  {l.sku[:15]:<16}{(l.name or 'Unknown product')[:42]:<44}{str(l.quantity):>5}"
                  f"{aud(l.unit_price):>14}{aud(l.line_total):>14}  {image[:40]}")
            if l.status.value != "OK":
                print(f"    ! {l.message}")
        print(f"  Shipment Fee {aud(s.fee.amount)} ({s.fee.source.value}) {s.fee.note}")
    print("-" * 96)
    t = d.totals
    for label, value in (("Subtotal", t.subtotal), ("GST (10% of Subtotal)", t.gst),
                         ("Shipment Fee", t.shipment_fee), ("Total", t.total)):
        print(f"{label:>84}{aud(value):>16}")
    for w in d.warnings:
        print(f"  WARNING: {w}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("order_no", nargs="?", help="Show only this order")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table")
    args = parser.parse_args()

    settings = get_settings()
    ds = load_dataset(settings.data_dir)
    orders = [o for o in ds.orders if not args.order_no or o.order_no == args.order_no]
    if not orders:
        sys.exit(f"Order {args.order_no} not found")
    auspost, tnt = AusPostClient(settings), TntClient()
    details = [await build_order(o, ds, auspost, tnt) for o in orders]

    if args.json:
        print(json.dumps({"orders": [d.model_dump(mode="json") for d in details], "data_warnings": ds.warnings},
                         indent=2, ensure_ascii=False))
        return
    for d in details:
        print_order(d)
    for w in ds.warnings:
        print(f"DATA WARNING: {w}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
