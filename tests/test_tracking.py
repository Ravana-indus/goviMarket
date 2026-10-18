"""Tracking for both sides (code page, TRACK in chat) and sellers keeping shipping costs current."""
import pytest

from app import dispatch, main, store, tracking
from app.lanes import load_lanes
from fastapi.testclient import TestClient
from tests.test_conversations import g  # noqa: F401
from tests.test_dispatch import _deal


@pytest.fixture
def clean_costs():
    for r in store.DB.all(tracking.KIND):
        store.DB.data[tracking.KIND].clear()
        break
    tracking.apply()
    yield
    store.DB.data.get(tracking.KIND, {}).clear()
    tracking.apply()


def test_track_in_chat_for_both_sides(g, clean_costs):
    f, b, m = _deal(g, farmer="94771300001", buyer="94771300002")
    for who in (f, b):
        r = who.say("TRACK")
        assert dispatch.code(m) in r and "waiting to be booked" in r
    assert dispatch.code(m) in b.say(f"track {dispatch.code(m).lower()}")
    main.deals.advance_shipment(m.shipment_id)
    assert "booked" in b.say("track")


def test_seller_cost_updates_the_lane_rate(g, clean_costs):
    f, b, m = _deal(g, farmer="94771300003", buyer="94771300004")
    lane = next(l for l in load_lanes() if tracking._key(l) == tracking._key(m.lane))
    before = lane.lkr_per_kg
    r = f.say("COST 1,500")
    per = round(1500 / m.qty_kg, 2)
    assert "Recorded Rs 1,500" in r and f"Rs {per:g}/kg" in r
    assert lane.lkr_per_kg == per and lane.source.startswith("REPORTED") and per != before
    assert next(x for x in store.matches() if x.id == m.id).shipping_paid_lkr == 1500
    assert "no agreed shipment" in b.say("COST 900")  # buyers do not report the seller's cost
    assert "amount in rupees" in f.say("cost")
    store.DB.data[tracking.KIND].clear()
    tracking.apply()
    assert lane.lkr_per_kg == before  # back to the estimate when there are no reports


def test_public_page_shows_no_phone_or_address(g, clean_costs):
    f, b, m = _deal(g, farmer="94771300005", buyer="94771300006", address="No. 9, Hidden Lane")
    c = TestClient(main.app)
    d = c.get(f"/api/t/{dispatch.code(m)}").json()
    assert d["code"] == dispatch.code(m) and d["status"] == "planned"
    assert "Hidden Lane" not in str(d) and "94771300006" not in str(d)
    assert c.get("/api/t/GV-NOPE").status_code == 404
    assert c.get(f"/t/{dispatch.code(m)}").status_code == 200
    assert c.post("/api/shipping-cost", json={"code": dispatch.code(m), "lkr": 900}).status_code == 403
