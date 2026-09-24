import asyncio
from decimal import Decimal

import httpx
import respx

from app.couriers.auspost import AusPostClient, parse_track_response
from app.models import Address, Carrier, FeeSource, TrackingStatus
from app.services.products import parse_product
from app.services.shipping import build_parcel, chargeable_kg, formula_fee, quote_shipment, rates_for, zone_for
from conftest import BASE, product_row


def addr(state, postcode):
    return Address(street="1 St", suburb="X", state=state, postcode=postcode)


# ---------- tracking ----------

@respx.mock
def test_tracking_ok_parses_status_and_latest_event(configured):
    route = respx.get(f"{BASE}/track").mock(return_value=httpx.Response(200, json={"tracking_results": [{
        "tracking_id": "2FWZ1", "status": "In transit",
        "trackable_items": [{"events": [
            {"date": "2025-12-01T09:00:00+11:00", "description": "Picked up", "location": "RYDE NSW"},
            {"date": "2025-12-02T10:00:00+11:00", "description": "In transit", "location": "SYDNEY NSW"},
        ]}],
    }]}))
    res = asyncio.run(AusPostClient(configured).track_many(["2FWZ1"], Carrier.STARTRACK))["2FWZ1"]
    assert res.status == TrackingStatus.OK
    assert res.current_status == "In transit"
    assert res.last_update == "2025-12-02T10:00:00+11:00"
    assert res.events[0].description == "In transit"
    req = route.calls.last.request
    assert req.headers["Account-Number"] == "222"  # StarTrack account
    assert req.headers["Authorization"].startswith("Basic ")


# Shapes below are trimmed from the official Track Items reference examples.

def test_parse_startrack_consignment_format():
    payload = {"tracking_results": [{
        "tracking_id": "5XXXX0XXXXXX",
        "consignment": {"status": "Awaiting Collection", "events": [
            {"location": "NEWTOWN VIC", "description": "Awaiting collection", "date": "2024-08-08T12:51:22+10:00"},
            {"location": "AVALON VIC", "description": "Onboard for delivery", "date": "2024-08-08T08:41:20+10:00"},
        ]},
        "trackable_items": [{"article_id": "5XXXX0XXXXXXFPP00001", "status": "In Transit", "events": [
            {"location": "NEWTOWN VIC", "description": "In transit", "date": "2024-08-08T12:51:21+10:00"}]}],
    }]}
    res = parse_track_response(payload, "STARTRACK")["5XXXX0XXXXXX"]
    assert res.status == TrackingStatus.OK
    assert res.current_status == "Awaiting Collection"  # consignment-level summary wins
    assert res.last_update == "2024-08-08T12:51:22+10:00"
    assert [e.description for e in res.events] == ["Awaiting collection", "Onboard for delivery"]


def test_parse_auspost_nested_consignment_items():
    payload = {"tracking_results": [{
        "tracking_id": "33XXX0123456",
        "trackable_items": [{"consignment_id": "33XXX0123456", "number_of_items": 1, "items": [{
            "article_id": "33XXX012345601000931502", "status": "Delivered", "events": [
                {"location": "LIGHTSVIEW SA", "description": "Delivered - Left in a safe place",
                 "date": "2020-12-29T11:04:08+11:00"},
                {"description": "Shipping information received by Australia Post", "date": "2020-12-15T23:59:32+11:00"},
            ]}]}],
    }]}
    res = parse_track_response(payload, "AUSPOST")["33XXX0123456"]
    assert res.current_status == "Delivered"
    assert len(res.events) == 2
    assert res.events[1].location is None


def test_parse_drops_duplicate_events():
    ev = {"location": "JOHN F. KENNEDY APT/NEW YORK (US)", "description": "Departed facility",
          "date": "2014-05-26T05:00:00+10:00"}
    payload = {"tracking_results": [{"tracking_id": "A", "status": "Delivered",
                                     "trackable_items": [{"events": [ev, dict(ev)]}]}]}
    assert len(parse_track_response(payload, "AUSPOST")["A"].events) == 1


@respx.mock
def test_tracking_rate_limited_is_unavailable(configured):
    respx.get(f"{BASE}/track").mock(return_value=httpx.Response(429, json={"errors": [
        {"message": "Too many requests", "error_code": "API_002", "error_name": "Too many requests"}]}))
    res = asyncio.run(AusPostClient(configured).track_many(["X"], Carrier.AUSPOST))["X"]
    assert res.status == TrackingStatus.UNAVAILABLE
    assert "429" in res.message and "API_002" in res.message


def test_account_number_rules(configured):
    # Made-up numbers with the same shape as the supplied ones (10-digit AusPost,
    # 8-digit StarTrack starting with 0).
    client = AusPostClient(configured.model_copy(update={"auspost_account": "2001234567",
                                                         "startrack_account": "01234567"}))
    assert client.account_number_problem(Carrier.AUSPOST) is None
    assert "never start with 0" in client.account_number_problem(Carrier.STARTRACK)
    padded = AusPostClient(configured.model_copy(update={"auspost_account": "123456"}))
    assert padded.account_for(Carrier.AUSPOST) == "0000123456"
    ok = AusPostClient(configured.model_copy(update={"startrack_account": "12345678"}))
    assert ok.account_number_problem(Carrier.STARTRACK) is None


@respx.mock
def test_tracking_per_id_error_is_no_data(configured):
    respx.get(f"{BASE}/track").mock(return_value=httpx.Response(200, json={"tracking_results": [
        {"tracking_id": "BAD", "errors": [{"code": "ESB-10001", "name": "Invalid tracking ID"}]}]}))
    res = asyncio.run(AusPostClient(configured).track_many(["BAD"], Carrier.AUSPOST))["BAD"]
    assert res.status == TrackingStatus.NO_DATA
    assert "Invalid tracking ID" in res.message


@respx.mock
def test_tracking_failures_become_unavailable(configured):
    client = AusPostClient(configured)
    # 401 body is the real testbed response observed with the supplied credentials.
    for mock in (httpx.Response(401, json={"errors": [{"message": "The request failed authentication",
                                                        "error_code": "API_001", "error_name": "Unauthenticated request"}]}),
                 httpx.Response(200, text="<html>not json</html>"),
                 httpx.TimeoutException("slow"),
                 httpx.ConnectError("down")):
        if isinstance(mock, Exception):
            respx.get(f"{BASE}/track").mock(side_effect=mock)
        else:
            respx.get(f"{BASE}/track").mock(return_value=mock)
        res = asyncio.run(client.track_many(["X"], Carrier.AUSPOST))["X"]
        assert res.status == TrackingStatus.UNAVAILABLE, mock


def test_tracking_not_configured_makes_no_call(unconfigured):
    with respx.mock(assert_all_called=False) as router:
        res = asyncio.run(AusPostClient(unconfigured).track_many(["X"], Carrier.AUSPOST))["X"]
        assert router.calls.call_count == 0
    assert res.status == TrackingStatus.NOT_CONFIGURED
    assert "AUSPOST_API_KEY" in res.message


# ---------- parcel + formula ----------

def test_parcel_uses_gross_weight_and_minimum_carton(rates):
    p = parse_product(product_row("A", gross="0.2kg", volume="1000mm³"))
    parcel, notes = build_parcel([(p, 3)], rates)
    assert parcel.weight_kg == Decimal("0.700")  # 3 x 0.2 + 0.1 tare
    assert (parcel.length_cm, parcel.width_cm, parcel.height_cm) == (Decimal("22.0"), Decimal("16.0"), Decimal("7.7"))
    assert notes == []


def test_parcel_grows_for_bulky_goods(rates):
    p = parse_product(product_row("A", gross="0.05kg", volume="1000000mm³"))  # light, 1 litre each
    parcel, _ = build_parcel([(p, 10)], rates)
    assert parcel.length_cm > Decimal("22.0")
    assert parcel.cubic_kg > parcel.weight_kg  # volumetric weight dominates


def test_zones(rates):
    assert zone_for(addr("NSW", "2000"), rates) == "SAME_STATE_METRO"
    assert zone_for(addr("NSW", "2830"), rates) == "SAME_STATE_REGIONAL"
    assert zone_for(addr("VIC", "3141"), rates) == "INTERSTATE_METRO"
    assert zone_for(addr("VIC", "3550"), rates) == "INTERSTATE_REGIONAL"
    assert zone_for(addr("NT", "0800"), rates) == "REMOTE"


def test_formula_fee(rates):
    p = parse_product(product_row("A", gross="0.2kg", volume="1000mm³"))
    parcel, _ = build_parcel([(p, 3)], rates)
    assert chargeable_kg(parcel, rates) == Decimal("1.0")  # 0.7 kg rounds up to 1.0
    fee = formula_fee(parcel, addr("VIC", "3141"), rates)
    assert fee.amount == Decimal("14.70")  # 12.50 + 2.20 x 1.0
    assert fee.source == FeeSource.FORMULA_ESTIMATE


# ---------- courier quote with fallback ----------

@respx.mock
def test_quote_uses_courier_price(configured, rates):
    route = respx.post(f"{BASE}/prices/items").mock(return_value=httpx.Response(200, json={
        "items": [{"prices": [{"product_id": "EXP", "calculated_price": 18.35, "calculated_gst": 1.67}]}]}))
    parcel, _ = build_parcel([(parse_product(product_row("A")), 1)], rates)
    fee = asyncio.run(quote_shipment(Carrier.STARTRACK, parcel, addr("VIC", "3141"), rates, AusPostClient(configured)))
    assert fee.source == FeeSource.COURIER_QUOTE
    assert fee.amount == Decimal("18.35")
    body = route.calls.last.request.content.decode()
    assert '"postcode":"2111"' in body.replace(" ", "") and '"postcode":"3141"' in body.replace(" ", "")


@respx.mock
def test_quote_falls_back_to_formula_on_api_error(configured, rates):
    respx.post(f"{BASE}/prices/items").mock(return_value=httpx.Response(500))
    parcel, _ = build_parcel([(parse_product(product_row("A", gross="0.2kg", volume="1000mm³")), 3)], rates)
    fee = asyncio.run(quote_shipment(Carrier.AUSPOST, parcel, addr("VIC", "3141"), rates, AusPostClient(configured)))
    assert fee.source == FeeSource.FORMULA_ESTIMATE
    assert fee.amount == Decimal("14.70")
    assert "HTTP 500" in fee.note


def test_tnt_fee_is_estimated_from_the_parcel_with_tnt_rates(configured, rates):
    tnt_rates = rates_for(rates, Carrier.TNT)
    parcel, _ = build_parcel([(parse_product(product_row("A")), 1)], tnt_rates)  # 0.6 kg, min carton
    with respx.mock(assert_all_called=False) as router:
        fee = asyncio.run(quote_shipment(Carrier.TNT, parcel, addr("VIC", "3065"), rates, AusPostClient(configured)))
        assert router.calls.call_count == 0  # never asks AusPost for a TNT price
    assert fee.source == FeeSource.FORMULA_ESTIMATE
    assert fee.chargeable_kg == Decimal("1.0")  # TNT minimum chargeable weight
    assert fee.amount == Decimal("15.90")       # TNT interstate metro: 13.50 + 2.40 x 1.0
    assert "TNT Road Express" in fee.note and "RTT" in fee.note


def test_carrier_rates_override_defaults(rates):
    tnt = rates_for(rates, Carrier.TNT)
    assert tnt["minimum_chargeable_kg"] == 1.0 and tnt["zones"]["INTERSTATE_METRO"]["base"] == "13.50"
    assert tnt["carton"] == rates["carton"]  # shared settings are kept
    assert rates_for(rates, Carrier.STARTRACK)["zones"] == rates["zones"]  # no override -> defaults
