"""Australia Post / StarTrack Shipping & Tracking API client.

- Track:  GET  {base}/track?tracking_ids=a,b   (max 10 ids per call)
- Price:  POST {base}/prices/items
- Auth:   HTTP Basic (API key : password) + `Account-Number` header.

Credentials only ever live on the server. Every public method returns a
result object and never raises, so a courier outage cannot break an order.
"""
from decimal import Decimal, InvalidOperation
from typing import Optional

import httpx

from app.config import Settings
from app.couriers.base import TTLCache
from app.models import Carrier, Parcel, TrackingEvent, TrackingResult, TrackingStatus

TRACK_BATCH_SIZE = 10
_track_cache = TTLCache(ttl_seconds=300)
_price_cache = TTLCache(ttl_seconds=600)


class QuoteResult:
    def __init__(self, amount: Optional[Decimal], note: str):
        self.amount = amount
        self.note = note


def clear_caches() -> None:
    _track_cache.clear()
    _price_cache.clear()


class AusPostClient:
    def __init__(self, settings: Settings):
        self.s = settings

    # ---------- configuration ----------

    def account_for(self, carrier: Carrier) -> str:
        if carrier == Carrier.STARTRACK:
            return self.s.startrack_account
        account = self.s.auspost_account.strip()
        return account.zfill(10) if account.isdigit() else account

    def product_id_for(self, carrier: Carrier) -> str:
        return self.s.startrack_product_id if carrier == Carrier.STARTRACK else self.s.auspost_product_id

    def missing_config(self, carrier: Carrier) -> list[str]:
        needed = {
            "AUSPOST_BASE_URL": self.s.auspost_base_url,
            "AUSPOST_API_KEY": self.s.auspost_api_key,
            "AUSPOST_PASSWORD": self.s.auspost_password,
            ("STARTRACK_ACCOUNT" if carrier == Carrier.STARTRACK else "AUSPOST_ACCOUNT"): self.account_for(carrier),
        }
        return [name for name, value in needed.items() if not value.strip()]

    def account_number_problem(self, carrier: Carrier) -> Optional[str]:
        """Format rules from the official "REST and authentication" page."""
        account = self.account_for(carrier).strip()
        if not account:
            return None
        if carrier == Carrier.STARTRACK:
            if not (len(account) == 8 and account.isdigit() and account[0] != "0"):
                return (f"StarTrack account numbers are 8 digits and never start with 0; "
                        f"got {len(account)} digits starting with {account[0]!r}.")
        elif not (account.isdigit() and len(account) <= 10):
            return "Australia Post account numbers are up to 10 digits (left-padded with zeros)."
        return None

    def _client(self, carrier: Carrier) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.s.auspost_base_url.rstrip("/") + "/",
            auth=(self.s.auspost_api_key, self.s.auspost_password),
            # Header set as listed on the official "REST and authentication" page.
            headers={"Account-Number": self.account_for(carrier), "Accept": "application/json",
                     "Content-Type": "application/json"},
            timeout=self.s.courier_timeout_seconds,
        )

    # ---------- tracking ----------

    async def track_many(self, tracking_nos: list[str], carrier: Carrier) -> dict[str, TrackingResult]:
        carrier_name = carrier.value
        missing = self.missing_config(carrier)
        if missing:
            return {
                no: TrackingResult(
                    status=TrackingStatus.NOT_CONFIGURED, carrier=carrier_name, tracking_no=no,
                    message=f"Tracking API not configured (missing {', '.join(missing)}).",
                )
                for no in tracking_nos
            }

        results: dict[str, TrackingResult] = {}
        pending = []
        for no in tracking_nos:
            cached = _track_cache.get((carrier_name, no))
            if cached is not None:
                results[no] = cached
            else:
                pending.append(no)

        for i in range(0, len(pending), TRACK_BATCH_SIZE):
            batch = pending[i:i + TRACK_BATCH_SIZE]
            batch_results = await self._track_batch(batch, carrier)
            for no, result in batch_results.items():
                if result.status in (TrackingStatus.OK, TrackingStatus.NO_DATA):
                    _track_cache.set((carrier_name, no), result)
                results[no] = result
        return results

    async def _track_batch(self, batch: list[str], carrier: Carrier) -> dict[str, TrackingResult]:
        def unavailable(message: str) -> dict[str, TrackingResult]:
            return {
                no: TrackingResult(status=TrackingStatus.UNAVAILABLE, carrier=carrier.value, tracking_no=no, message=message)
                for no in batch
            }

        try:
            async with self._client(carrier) as client:
                resp = await client.get("track", params={"tracking_ids": ",".join(batch)})
        except httpx.TimeoutException:
            return unavailable("Tracking API timed out.")
        except httpx.HTTPError as e:
            return unavailable(f"Tracking API request failed: {type(e).__name__}.")

        if resp.status_code != 200:
            return unavailable(describe_http_failure("Tracking", resp))
        try:
            payload = resp.json()
        except ValueError:
            return unavailable("Tracking API returned a response that is not JSON.")

        parsed = parse_track_response(payload, carrier.value)
        for no in batch:
            parsed.setdefault(no, TrackingResult(
                status=TrackingStatus.NO_DATA, carrier=carrier.value, tracking_no=no,
                message="Tracking number not included in the API response.",
            ))
        return parsed

    # ---------- price quote ----------

    async def quote(self, carrier: Carrier, from_postcode: str, to_postcode: str, parcel: Parcel) -> QuoteResult:
        missing = self.missing_config(carrier)
        if missing:
            return QuoteResult(None, f"price API not configured, missing {', '.join(missing)}")
        product_id = self.product_id_for(carrier)
        if not product_id:
            var = "STARTRACK_PRODUCT_ID" if carrier == Carrier.STARTRACK else "AUSPOST_PRODUCT_ID"
            return QuoteResult(None, f"no {var} set; the product ID comes from GET /accounts "
                                     "(scripts/probe_auspost.py) once the API credentials are accepted")

        body = {
            "from": {"postcode": from_postcode},
            "to": {"postcode": to_postcode},
            "items": [{
                "product_ids": [product_id],
                "length": float(parcel.length_cm),
                "width": float(parcel.width_cm),
                "height": float(parcel.height_cm),
                "weight": float(parcel.weight_kg),
            }],
        }
        cache_key = (carrier.value, from_postcode, to_postcode, product_id,
                     parcel.length_cm, parcel.width_cm, parcel.height_cm, parcel.weight_kg)
        cached = _price_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            async with self._client(carrier) as client:
                resp = await client.post("prices/items", json=body)
        except httpx.TimeoutException:
            return QuoteResult(None, "Courier price API timed out.")
        except httpx.HTTPError as e:
            return QuoteResult(None, f"Courier price API request failed: {type(e).__name__}.")

        if resp.status_code != 200:
            return QuoteResult(None, describe_http_failure("Price", resp))
        try:
            amount = parse_price_response(resp.json(), product_id)
        except ValueError:
            return QuoteResult(None, "Courier price API returned a response that is not JSON.")
        if amount is None:
            return QuoteResult(None, "Courier price API response had no price for the product.")

        result = QuoteResult(amount, f"{carrier.value} product {product_id}, {from_postcode} → {to_postcode}.")
        _price_cache.set(cache_key, result)
        return result


# ---------- response parsing (pure functions, unit-tested) ----------

def _describe_error(e: dict) -> str:
    # The live API uses error_code/error_name/message; older docs show code/name.
    code = e.get("error_code") or e.get("code") or ""
    text = e.get("message") or e.get("error_name") or e.get("name") or ""
    return f"{code} {text}".strip()


def describe_http_failure(api: str, resp: httpx.Response) -> str:
    """Turn an HTTP failure into a specific, actionable reason (internal / debug use)."""
    code, hint = resp.status_code, _error_hint(resp)
    if code == 401:
        reason = "rejected the API key and password (authentication failed)"
    elif code == 403:
        reason = "refused access for this account number"
    elif code == 429:
        reason = "rate limit reached (10 requests per minute); try again shortly"
    elif code == 400:
        reason = "rejected the request as invalid"
    elif code == 404:
        reason = "endpoint not found (check AUSPOST_BASE_URL)"
    elif code >= 500:
        reason = "service error on the carrier side"
    else:
        reason = "unexpected response"
    return f"{api} API {reason}: HTTP {code}{hint}."


def _error_hint(resp: httpx.Response) -> str:
    try:
        errors = resp.json().get("errors") or []
        if errors:
            return f" ({_describe_error(errors[0])})"
    except (ValueError, AttributeError):
        pass
    return ""


def parse_track_response(payload: dict, carrier: str) -> dict[str, TrackingResult]:
    results: dict[str, TrackingResult] = {}
    for entry in (payload or {}).get("tracking_results", []) or []:
        no = entry.get("tracking_id")
        if not no:
            continue
        errors = entry.get("errors") or []
        if errors:
            results[no] = TrackingResult(
                status=TrackingStatus.NO_DATA, carrier=carrier, tracking_no=no,
                message=_describe_error(errors[0]) or "No tracking data",
            )
            continue

        status, raw_events = _status_and_events(entry)
        events, seen = [], set()
        for ev in raw_events:
            key = (ev.get("date"), ev.get("description"), ev.get("location"))
            if key in seen:  # documented responses repeat some events
                continue
            seen.add(key)
            events.append(TrackingEvent(
                date=ev.get("date"), description=ev.get("description", ""), location=ev.get("location") or None,
            ))
        events.sort(key=lambda ev: ev.date or "", reverse=True)

        results[no] = TrackingResult(
            status=TrackingStatus.OK if (status or events) else TrackingStatus.NO_DATA,
            carrier=carrier, tracking_no=no,
            current_status=status,
            last_update=events[0].date if events else None,
            events=events,
            message="" if (status or events) else "API returned no status or events.",
        )
    return results


def _status_and_events(entry: dict) -> tuple[Optional[str], list[dict]]:
    """Handle every documented Track Items response shape.

    - StarTrack consignments (Aug 2024 format): top-level `consignment` with
      its own status and events; this is the consignment-level summary.
    - Australia Post articles: `trackable_items[].events`.
    - Australia Post consignments: `trackable_items[].items[].events`.
    """
    consignment = entry.get("consignment") or {}
    if isinstance(consignment, dict) and (consignment.get("status") or consignment.get("events")):
        return consignment.get("status") or entry.get("status"), list(consignment.get("events") or [])

    statuses, events = [], []
    for item in entry.get("trackable_items", []) or []:
        for leaf in (item.get("items") or [item]):
            events += leaf.get("events") or []
            if leaf.get("status"):
                statuses.append(leaf["status"])
    return entry.get("status") or (statuses[0] if statuses else None), events


def parse_price_response(payload: dict, product_id: str) -> Optional[Decimal]:
    for item in (payload or {}).get("items", []) or []:
        for price in item.get("prices", []) or []:
            if price.get("product_id") not in (None, product_id):
                continue
            raw = price.get("calculated_price")
            if raw is None:
                continue
            try:
                return Decimal(str(raw))
            except InvalidOperation:
                return None
    return None
