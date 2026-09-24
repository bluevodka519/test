"""TNT (now FedEx Express Australia) consignment tracking.

TNT has no working tracking API for this integration: the legacy Rated
Transit Times endpoint (/Rtt/inputRequest.asp) returns 404 on both the
production and UAT hosts, and the old weblink URL (track.aspx?con=) now
redirects to a 404. The supplied TNT credentials are for those legacy
systems and are not used here.

Tracking is read from TNT's *public* domestic Track & Trace page, the same
page anyone can use without logging in:
  1. GET  trackntrace.aspx                  (ASP.NET form + hidden state)
  2. POST trackntrace.aspx  method=CON      (search by consignment number)
  3. POST result page, target "View Details" (consignment history)
  4. Parse the Status / Date & Time / Depot table.

The page markup can change at any time, so every failure returns
UNAVAILABLE and nothing is ever guessed.
"""
import asyncio
import html
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import httpx

from app.couriers.base import TTLCache
from app.models import TrackingEvent, TrackingResult, TrackingStatus

TRACK_URL = "https://www.tntexpress.com.au/interaction/trackntrace.aspx"
SOURCE_NOTE = "Source: TNT public Track & Trace page (no TNT tracking API is available)."
_cache = TTLCache(ttl_seconds=600)

# Depot names look like "Sydney - Enfield"; times on the page are depot-local.
_DEPOT_TIMEZONES = {
    "perth": "Australia/Perth", "adelaide": "Australia/Adelaide", "darwin": "Australia/Darwin",
    "brisbane": "Australia/Brisbane", "gold coast": "Australia/Brisbane", "townsville": "Australia/Brisbane",
    "cairns": "Australia/Brisbane", "hobart": "Australia/Hobart", "launceston": "Australia/Hobart",
}
_DEFAULT_TZ = "Australia/Sydney"  # Sydney, Melbourne, Canberra and anything unrecognised


def clear_cache() -> None:
    _cache.clear()


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def _hidden_fields(page: str) -> dict[str, str]:
    fields = {}
    for tag in re.findall(r"(?is)<input\b[^>]*>", page):
        if not re.search(r'type="hidden"', tag, re.I):
            continue
        name = re.search(r'name="([^"]+)"', tag)
        value = re.search(r'value="([^"]*)"', tag)
        if name:
            fields[name.group(1)] = html.unescape(value.group(1)) if value else ""
    return fields


def _form_action(page: str, base_url: str) -> str:
    m = re.search(r'(?is)<form\b[^>]*method="post"[^>]*action="([^"]+)"', page)
    return urljoin(base_url, html.unescape(m.group(1))) if m else base_url


def to_iso(local: str, depot: str) -> Optional[str]:
    """'04/12/2025 13:00' at 'Melbourne - Airport' -> '2025-12-04T13:00:00+11:00'."""
    try:
        dt = datetime.strptime(local.strip(), "%d/%m/%Y %H:%M")
    except ValueError:
        return None
    city = depot.split("-")[0].strip().lower()
    tz = next((z for key, z in _DEPOT_TIMEZONES.items() if city.startswith(key)), _DEFAULT_TZ)
    return dt.replace(tzinfo=ZoneInfo(tz)).isoformat()


def parse_history(page: str, tracking_no: str) -> TrackingResult:
    """Parse the ConsignmentHistory page into a TrackingResult."""
    events = []
    for row in re.findall(r"(?is)<tr\b[^>]*>(.*?)</tr>", page):
        cells = [_text(c) for c in re.findall(r"(?is)<t[dh]\b[^>]*>(.*?)</t[dh]>", row)]
        if len(cells) < 3 or cells[0].lower() == "status" or not cells[0]:
            continue
        iso = to_iso(cells[1], cells[2])
        events.append(TrackingEvent(date=iso or cells[1], description=cells[0], location=cells[2] or None))
    events.sort(key=lambda e: e.date or "", reverse=True)

    signed_by = re.search(r"Signed by:\s*(.*?)\s*(?:Status\b|$)", _text(page))
    signed = signed_by.group(1).strip() if signed_by and signed_by.group(1).strip() else None
    if not events:
        return TrackingResult(status=TrackingStatus.NO_DATA, carrier="TNT", tracking_no=tracking_no,
                              message=f"TNT has no tracking events for this consignment. {SOURCE_NOTE}")
    current = events[0].description
    return TrackingResult(
        status=TrackingStatus.OK, carrier="TNT", tracking_no=tracking_no,
        current_status=f"{current} (signed by {signed})" if signed and "deliver" in current.lower() else current,
        last_update=events[0].date, events=events, message=SOURCE_NOTE,
    )


class TntClient:
    def __init__(self, enabled: bool = True, timeout: float = 10.0):
        self.enabled = enabled
        self.timeout = timeout

    async def track_many(self, tracking_nos: list[str]) -> dict[str, TrackingResult]:
        if not self.enabled:
            return {no: TrackingResult(status=TrackingStatus.NOT_CONFIGURED, carrier="TNT", tracking_no=no,
                                       message="TNT tracking is switched off (TNT_PUBLIC_TRACKING=false).")
                    for no in tracking_nos}
        results = await asyncio.gather(*(self._track_one(no) for no in tracking_nos))
        return dict(zip(tracking_nos, results))

    async def _track_one(self, tracking_no: str) -> TrackingResult:
        cached = _cache.get(tracking_no)
        if cached is not None:
            return cached

        def unavailable(message: str) -> TrackingResult:
            return TrackingResult(status=TrackingStatus.UNAVAILABLE, carrier="TNT", tracking_no=tracking_no,
                                  message=f"{message} {SOURCE_NOTE}")

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=self.timeout,
                                         headers={"User-Agent": "Mozilla/5.0 (order-tracking demo)"}) as client:
                form = await client.get(TRACK_URL)
                form.raise_for_status()
                search = _hidden_fields(form.text)
                if "__VIEWSTATE" not in search:
                    return unavailable("TNT tracking page layout has changed (no form state).")
                search.update({
                    "__EVENTTARGET": "ctl00$bodycontent$btnSubmit", "__EVENTARGUMENT": "",
                    "method": "CON", "TextArea": tracking_no, "ctl00$bodycontent$hdninpTextArea": "",
                })
                result = await client.post(_form_action(form.text, TRACK_URL), data=search)
                result.raise_for_status()
                if "ctl00$bodycontent$A1" not in result.text:
                    return unavailable("TNT returned no consignment result.")

                details = _hidden_fields(result.text)
                details.update({"__EVENTTARGET": "ctl00$bodycontent$A1", "__EVENTARGUMENT": ""})
                history = await client.post(_form_action(result.text, str(result.url)), data=details)
                history.raise_for_status()
        except httpx.TimeoutException:
            return unavailable("TNT tracking page timed out.")
        except httpx.HTTPError as e:
            return unavailable(f"TNT tracking page request failed: {type(e).__name__}.")

        parsed = parse_history(history.text, tracking_no)
        if parsed.status in (TrackingStatus.OK, TrackingStatus.NO_DATA):
            _cache.set(tracking_no, parsed)
        return parsed
