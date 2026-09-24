"""Probe the Australia Post / StarTrack testbed with the credentials in .env.

Run from backend/:   python scripts/probe_auspost.py
Prints HTTP status and response bodies (never the credentials) so the
findings can be recorded in the README. Makes read-only calls only.
"""
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import env_file_path, get_settings  # noqa: E402

ORDER_NUMBERS = ["2FWZ50008569", "2FWZ50008645"]
FAQ_NUMBERS = ["RBXZ50016112", "2FWZ50020500", "2FWZ50020498", "2FWZ50020475"]


def show(title: str, resp: httpx.Response | Exception) -> None:
    print(f"\n=== {title}")
    if isinstance(resp, Exception):
        print(f"ERROR {type(resp).__name__}: {resp}")
        return
    print(f"HTTP {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False)[:3000])
    except ValueError:
        print(resp.text[:1000])


def main() -> None:
    s = get_settings()
    print(f"env file: {env_file_path()} (exists={env_file_path().exists()})")
    missing = [n for n in ("auspost_base_url", "auspost_api_key", "auspost_password") if not getattr(s, n)]
    if missing:
        sys.exit(f"Missing in .env: {', '.join(m.upper() for m in missing)}")

    accounts = {"AUSPOST": s.auspost_account, "STARTRACK": s.startrack_account}
    for label, account in accounts.items():
        if not account:
            print(f"\n(skip {label}: no account number set)")
            continue
        with httpx.Client(base_url=s.auspost_base_url.rstrip("/") + "/", auth=(s.auspost_api_key, s.auspost_password),
                          headers={"Account-Number": account, "Accept": "application/json"},
                          timeout=s.courier_timeout_seconds) as client:

            def call(title, method, path, **kw):
                try:
                    show(f"{label} {title}", client.request(method, path, **kw))
                except httpx.HTTPError as e:
                    show(f"{label} {title}", e)

            # Which products can this account quote with? -> AUSPOST_PRODUCT_ID / STARTRACK_PRODUCT_ID
            call("GET accounts", "GET", f"accounts/{account}")
            call("track order numbers", "GET", "track", params={"tracking_ids": ",".join(ORDER_NUMBERS)})
            call("track FAQ numbers", "GET", "track", params={"tracking_ids": ",".join(FAQ_NUMBERS)})

            product_id = s.startrack_product_id if label == "STARTRACK" else s.auspost_product_id
            if product_id:
                body = {"from": {"postcode": "2111"}, "to": {"postcode": "3141"},
                        "items": [{"product_ids": [product_id], "length": 22, "width": 16, "height": 7.7, "weight": 1}]}
                call(f"price {product_id} 2111->3141", "POST", "prices/items", json=body)
            else:
                print(f"\n(skip {label} price: set {label}_PRODUCT_ID from the accounts response above)")


if __name__ == "__main__":
    main()
