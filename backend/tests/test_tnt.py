import asyncio

import httpx
import respx

from app.couriers.tnt import TRACK_URL, TntClient, parse_history, to_iso
from app.models import TrackingStatus

# Trimmed from the real pages returned for consignment 305506914.
FORM_PAGE = """<form method="post" action="./trackntrace.aspx" id="form1">
<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="vs1" />
<input type="hidden" name="__VIEWSTATEGENERATOR" id="__VIEWSTATEGENERATOR" value="7AD588C4" />
<input type="hidden" name="__EVENTVALIDATION" id="__EVENTVALIDATION" value="ev1" />
<textarea name="ctl00$bodycontent$TextArea" id="TextArea"></textarea></form>"""

RESULT_PAGE = """<form method="post" action="./trackntraceResult.aspx?con=ENC&amp;type=T" id="form1">
<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="vs2" />
<input type="hidden" name="ctl00$bodycontent$hdnSingleDs" id="bodycontent_hdnSingleDs" value="D" />
<a id="bodycontent_A1" href="javascript:__doPostBack(&#39;ctl00$bodycontent$A1&#39;,&#39;&#39;)">View Details</a>
</form>"""

HISTORY_PAGE = """<h1>CONSIGNMENT HISTORY RESULTS</h1>
<div>Consignment: 305506914</div><div>Delivered: </div><div>Signed by: Norton</div>
<table><tr><th>Status</th><th>Date &amp; Time</th><th>Depot</th></tr>
<tr><td>Your shipment data is lodged</td><td>03/12/2025 10:21</td><td>Sydney - Enfield</td></tr>
<tr><td>We&#39;ve collected your shipment</td><td>03/12/2025 15:27</td><td>Sydney - Enfield</td></tr>
<tr><td>Your shipment&#39;s with a driver</td><td>04/12/2025 09:16</td><td>Melbourne - Airport</td></tr>
<tr><td>We&#39;ve delivered your shipment</td><td>04/12/2025 13:00</td><td>Melbourne - Airport</td></tr>
</table>"""


def test_to_iso_uses_depot_timezone():
    assert to_iso("04/12/2025 13:00", "Melbourne - Airport") == "2025-12-04T13:00:00+11:00"  # AEDT
    assert to_iso("04/07/2025 13:00", "Sydney - Enfield") == "2025-07-04T13:00:00+10:00"     # AEST
    assert to_iso("04/12/2025 13:00", "Perth - Kewdale") == "2025-12-04T13:00:00+08:00"
    assert to_iso("04/12/2025 13:00", "Brisbane - Eagle Farm") == "2025-12-04T13:00:00+10:00"  # no DST
    assert to_iso("not a date", "Sydney") is None


def test_parse_history():
    res = parse_history(HISTORY_PAGE, "305506914")
    assert res.status == TrackingStatus.OK
    assert res.current_status == "We've delivered your shipment (signed by Norton)"
    assert res.last_update == "2025-12-04T13:00:00+11:00"
    assert [e.location for e in res.events][:2] == ["Melbourne - Airport", "Melbourne - Airport"]
    assert res.events[-1].description == "Your shipment data is lodged"  # oldest last


def test_parse_history_without_events_is_no_data():
    res = parse_history("<table><tr><th>Status</th><th>Date &amp; Time</th><th>Depot</th></tr></table>", "X")
    assert res.status == TrackingStatus.NO_DATA


@respx.mock
def test_full_flow_posts_search_then_view_details():
    respx.get(TRACK_URL).mock(return_value=httpx.Response(200, text=FORM_PAGE))
    search = respx.post(TRACK_URL).mock(return_value=httpx.Response(200, text=RESULT_PAGE))
    details = respx.post(url__regex=r".*/trackntraceResult\.aspx.*").mock(
        return_value=httpx.Response(200, text=HISTORY_PAGE))

    res = asyncio.run(TntClient().track_many(["305506914"]))["305506914"]

    assert res.status == TrackingStatus.OK
    assert len(res.events) == 4
    sent = dict(httpx.QueryParams(search.calls.last.request.content.decode()))
    assert sent["method"] == "CON" and sent["TextArea"] == "305506914"
    assert sent["__VIEWSTATE"] == "vs1" and sent["__EVENTTARGET"] == "ctl00$bodycontent$btnSubmit"
    sent2 = dict(httpx.QueryParams(details.calls.last.request.content.decode()))
    assert sent2["__EVENTTARGET"] == "ctl00$bodycontent$A1" and sent2["__VIEWSTATE"] == "vs2"


@respx.mock
def test_layout_change_or_errors_are_unavailable():
    client = TntClient()
    respx.get(TRACK_URL).mock(return_value=httpx.Response(200, text="<html>redesigned</html>"))
    assert asyncio.run(client.track_many(["A"]))["A"].status == TrackingStatus.UNAVAILABLE

    respx.get(TRACK_URL).mock(return_value=httpx.Response(503))
    assert asyncio.run(client.track_many(["B"]))["B"].status == TrackingStatus.UNAVAILABLE

    respx.get(TRACK_URL).mock(side_effect=httpx.TimeoutException("slow"))
    res = asyncio.run(client.track_many(["C"]))["C"]
    assert res.status == TrackingStatus.UNAVAILABLE and "timed out" in res.message

    respx.get(TRACK_URL).mock(return_value=httpx.Response(200, text=FORM_PAGE))
    respx.post(TRACK_URL).mock(return_value=httpx.Response(200, text="<p>no result</p>"))
    assert asyncio.run(client.track_many(["D"]))["D"].status == TrackingStatus.UNAVAILABLE


def test_disabled_makes_no_request():
    with respx.mock(assert_all_called=False) as router:
        res = asyncio.run(TntClient(enabled=False).track_many(["X"]))["X"]
        assert router.calls.call_count == 0
    assert res.status == TrackingStatus.NOT_CONFIGURED
