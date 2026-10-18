"""Fixes from the Oct 18 matching review (govi-plan/matching-review.md)."""
import threading
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app import convo, deals, main, rescue, store, tracking
from app.lanes import load_lanes
from app.schemas import Listing, Order

TODAY = datetime.now(ZoneInfo("Asia/Colombo")).date()


@pytest.fixture(autouse=True)
def clean():
    store.reset()
    store.DB.data.pop(tracking.KIND, None)
    tracking.apply()
    yield
    store.DB.data.pop(tracking.KIND, None)
    tracking.apply()


def _li(id, loc, crop, kg, ready, phone):
    store.put("listings", Listing(id=id, phone=phone, farmer="F" + id, location=loc, crop=crop, qty_kg=kg,
                                  ready_on=ready, remaining_kg=kg).model_dump(mode="json"))


def _od(id, loc, crop, kg, need, phone):
    store.put("orders", Order(id=id, phone=phone, buyer="B" + id, location=loc, crop=crop, qty_kg=kg,
                              needed_by=need, remaining_kg=kg).model_dump(mode="json"))


def _agreed(kg=100):
    _li("a", "Nuwara Eliya", "carrot", kg, TODAY, "94771500001")
    _od("x", "Colombo", "carrot", kg, TODAY + timedelta(days=2), "94771500002")
    deals.plan()
    deals.answer("94771500002", "yes")
    deals.answer("94771500001", "yes")
    return store.matches()[0]


def test_a_missed_shipment_with_no_later_transport_does_not_freeze_matching(monkeypatch):
    m = _agreed()
    sid = store.matches()[0].shipment_id
    deals.advance_shipment(sid)  # booked
    x = next(s for s in store.shipments() if s.id == sid)
    x.schedule["in_transit"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    store.put_shipment(x)
    monkeypatch.setattr(rescue.shipping, "backup_lanes", lambda *a, **k: [])
    t = threading.Thread(target=deals.plan, daemon=True)
    t.start()
    t.join(10)
    assert not t.is_alive()
    assert next(s for s in store.shipments() if s.id == sid).status == "missed"


def test_carrier_webhook_needs_the_secret(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "tok")
    monkeypatch.setenv("CARRIER_WEBHOOK_SECRET", "s3cret")
    c = TestClient(main.app)
    assert c.post("/webhook/carrier", json={"ref": "NB-1234", "status": "missed"}).status_code == 401
    assert c.post("/webhook/carrier", json={"ref": "NB-1234", "status": "missed"},
                  headers={"x-carrier-secret": "s3cret"}).status_code == 404  # past the lock, no such ref
    assert c.post("/rescue/watchdog").status_code in (401, 403)
    assert c.post("/api/lanes/reload").status_code in (401, 403)


def test_stop_withdraws_only_the_newest_order():
    for i, crop in enumerate(["carrot", "beans", "leeks"]):
        store.put("orders", {**Order(id=f"O{i}", phone="94771500003", buyer="Cafe", location="Colombo", crop=crop,
                                     qty_kg=10, needed_by=TODAY + timedelta(days=2), remaining_kg=10).model_dump(mode="json"),
                             "created_at": f"2026-10-1{i}T00:00:00"})
    convo.step(sender="94771500003", text="stop", media=None, mime_type=None, today=TODAY, confirm_first=False)
    assert {o.id for o in store.orders()} == {"O0", "O1"}


def test_yes_1_means_the_first_line_of_the_message_just_sent():
    _li("a", "Nuwara Eliya", "carrot", 100, TODAY, "94771500001")
    _od("x", "Colombo", "carrot", 100, TODAY + timedelta(days=2), "94771500002")
    deals.plan()  # an older single offer, still waiting
    _li("b", "Nuwara Eliya", "beans", 100, TODAY, "94771500001")
    _li("c", "Nuwara Eliya", "leeks", 100, TODAY, "94771500001")
    _od("y", "Colombo", "beans", 100, TODAY + timedelta(days=2), "94771500004")
    _od("z", "Colombo", "leeks", 100, TODAY + timedelta(days=2), "94771500005")
    deals.plan()  # "1. beans  2. leeks"
    deals.answer("94771500001", "yes 1")
    ok = {m.crop: m.farmer_ok for m in store.matches()}
    assert ok == {"carrot": False, "beans": True, "leeks": False}


def test_partial_yes_reprices_and_asks_the_other_side_again():
    _li("a", "Nuwara Eliya", "carrot", 100, TODAY, "94771500001")
    _od("x", "Colombo", "carrot", 100, TODAY + timedelta(days=2), "94771500002")
    deals.plan()
    deals.answer("94771500002", "yes")
    reply = deals.answer("94771500001", "yes 10kg")  # 10 kg alone costs more to ship than it earns
    m = store.matches()[0]
    assert "too small" in reply and m.status == "proposed" and m.qty_kg == 100
    reply = deals.answer("94771500001", "yes 60kg")
    m = store.matches()[0]
    assert m.status == "proposed" and m.qty_kg == 60 and m.farmer_ok and not m.buyer_ok
    assert m.farmer_gets_lkr_per_kg > m.collector_pays_lkr_per_kg
    assert m.transport_lkr_per_kg > 26  # fixed costs over fewer kg


def test_yes_after_an_offer_expired_does_not_confirm():
    _li("a", "Nuwara Eliya", "carrot", 100, TODAY, "94771500001")
    _od("x", "Colombo", "carrot", 100, TODAY + timedelta(days=2), "94771500002")
    deals.plan()
    m = store.matches()[0]
    m.expires_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    store.put_match(m)
    assert "expired" in deals.answer("94771500001", "yes")
    assert store.matches()[0].status == "expired"


def test_no_offer_for_a_bus_that_left_whoever_runs_matching():
    _li("a", "Nuwara Eliya", "carrot", 100, TODAY - timedelta(days=1), "94771500001")
    _od("x", "Colombo", "carrot", 50, TODAY, "94771500002")
    _od("y", "Colombo", "carrot", 50, TODAY - timedelta(days=3), "94771500003")
    deals.plan()  # no `today` passed, as from the portal or /plan
    assert store.matches() == []


def test_portal_refuses_delivery_today():
    c = TestClient(main.app)
    r = c.post("/api/orders", json={"business": "Cafe", "phone": "0771500006", "location": "Colombo",
                                    "needed_by": TODAY.isoformat(), "items": [{"crop": "carrot", "qty_kg": 50}]})
    assert r.status_code == 400 and "tomorrow" in r.text


def test_one_cost_reply_cannot_blow_up_a_route():
    m = _agreed()
    lane = next(l for l in load_lanes() if tracking._key(l) == tracking._key(m.lane))
    before = lane.lkr_per_kg
    tracking.report(m, 30000, phone="94771500001")  # a typo with an extra zero
    assert lane.lkr_per_kg <= before * 2


def test_agreed_deal_keeps_its_transport_when_a_bigger_load_arrives():
    m = _agreed()
    agreed = (m.lane.mode, m.lane.pickup, m.lane.departs, m.shipment_id)
    _li("b", "Nuwara Eliya", "carrot", 900, TODAY, "94771500007")
    _od("y", "Colombo", "carrot", 900, TODAY + timedelta(days=2), "94771500008")
    deals.plan()
    m = next(x for x in store.matches() if x.listing_id == "a")
    assert (m.lane.mode, m.lane.pickup, m.lane.departs, m.shipment_id) == agreed
