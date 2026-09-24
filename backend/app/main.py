"""FastAPI entry point. Run from backend/:  uvicorn app.main:app --reload"""
import asyncio

from fastapi import FastAPI, HTTPException

from app.config import REPORTED_FIELDS, env_file_path, get_settings
from app.couriers.auspost import AusPostClient
from app.couriers.tnt import TntClient
from app.models import Carrier, OrderDetail
from app.services.loader import load_dataset
from app.services.orders import build_order, summarise

app = FastAPI(title="Order Details, Tracking & Shipping Estimate", version="1.0.0")


def _context():
    settings = get_settings()
    tnt = TntClient(enabled=settings.tnt_public_tracking, timeout=settings.courier_timeout_seconds)
    return settings, load_dataset(settings.data_dir), AusPostClient(settings), tnt


@app.get("/api/health")
def health():
    settings = get_settings()
    client = AusPostClient(settings)
    env_file = env_file_path()
    return {
        "env_file_found": env_file.exists(),
        "env_vars_set": {name.upper(): bool(str(getattr(settings, name)).strip()) for name in REPORTED_FIELDS},
        "couriers": {
            "AUSPOST": {"tracking_ready": not client.missing_config(Carrier.AUSPOST),
                        "quote_ready": not client.missing_config(Carrier.AUSPOST) and bool(settings.auspost_product_id),
                        "account_number_warning": client.account_number_problem(Carrier.AUSPOST)},
            "STARTRACK": {"tracking_ready": not client.missing_config(Carrier.STARTRACK),
                          "quote_ready": not client.missing_config(Carrier.STARTRACK) and bool(settings.startrack_product_id),
                          "account_number_warning": client.account_number_problem(Carrier.STARTRACK)},
            "TNT": {"tracking_ready": settings.tnt_public_tracking, "quote_ready": False,
                    "note": "Tracking via TNT's public Track & Trace page; the RTT price service is retired (404), "
                            "so TNT fees are formula estimates with assumed TNT rates."},
        },
    }


@app.get("/api/orders")
async def list_orders():
    _, ds, auspost, tnt = _context()
    details = await asyncio.gather(*(build_order(o, ds, auspost, tnt, include_tracking=False) for o in ds.orders))
    return {"orders": [summarise(d) for d in details], "data_warnings": ds.warnings}


@app.get("/api/orders/{order_no}", response_model=OrderDetail)
async def get_order(order_no: str):
    _, ds, auspost, tnt = _context()
    order = next((o for o in ds.orders if o.order_no == order_no), None)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order {order_no} not found")
    return await build_order(order, ds, auspost, tnt)
