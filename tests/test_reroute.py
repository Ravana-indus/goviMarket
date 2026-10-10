"""Better route found after a deal is agreed: proposed, needs everyone's YES, never touches booked loads."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import deals, reroute, security, store
from app.main import app
from app.schemas import Lane

RANJITH, SPICE, BANDARA, REST_HOUSE = "94770000016", "94770000017", "94770000018", "94770000019"


@pytest.fixture
def c():
    store.reset()
    security.reset_limits()
    return TestClient(app)


def yes(c, phone, word="YES"):
    return c.post("/intake", data={"text": word, "sender": phone, "via": "sim"}).json()["reply"]


def maize():
    return {(m.farmer, m.buyer): m for m in store.matches() if m.crop == "maize"}


def test_demo_swap_needs_everyone_then_switches(c):
    c.post("/demo/seed")
    [s] = c.get("/api/swaps").json()
    assert s["status"] == "proposed" and s["extra_kg"] == 50
    assert s["after"] == ["Ranjith (Ampara) → Ampara Rest House (Ampara)", "Bandara (Kurunegala) → Spice Route (Colombo)"]
    for phone in (RANJITH, SPICE, BANDARA):
        assert "until then your current deal stands" in yes(c, phone)
        assert maize()[("Ranjith", "Spice Route")].status == "confirmed"  # nothing moves before the last YES
    assert "Switched" in yes(c, REST_HOUSE)
    m = maize()
    assert m[("Ranjith", "Spice Route")].status == "cancelled"
    assert m[("Ranjith", "Ampara Rest House")].status == "confirmed"
    assert m[("Bandara", "Spice Route")].status == "confirmed"
    assert all(x.remaining_kg == 0 for x in store.listings() + store.orders() if x.crop == "maize")
    assert c.get("/api/swaps").json()[0]["status"] == "done"


def test_one_no_keeps_the_agreed_deal(c):
    c.post("/demo/seed")
    yes(c, RANJITH)
    assert "nothing changes" in yes(c, SPICE, "NO")
    assert maize()[("Ranjith", "Spice Route")].status == "confirmed"
    deals.plan()  # the same swap is not offered again
    assert [s["status"] for s in reroute.swaps()] == ["declined"]


def test_booked_load_is_too_late(c):
    c.post("/demo/seed")
    sid = maize()[("Ranjith", "Spice Route")].shipment_id
    c.post(f"/shipments/{sid}/advance")  # booked on the bus
    for phone in (RANJITH, SPICE, BANDARA):
        yes(c, phone)
    assert "Too late" in yes(c, REST_HOUSE)
    assert maize()[("Ranjith", "Spice Route")].status == "confirmed"


def test_two_deals_swap_partly_when_transport_drops(c, monkeypatch):
    lane = dict(mode="lorry", min_charge_lkr=0, departs="20:00", transit_hours=4, max_kg=1000,
                handling_lkr=0, door_delivery=True, source="TEST")
    monkeypatch.setattr(deals, "LANES", [
        Lane(origin="Hilltown", dest="Westport", lkr_per_kg=20, **lane),
        Lane(origin="Hilltown", dest="Eastport", lkr_per_kg=5, **lane),
        Lane(origin="Riverside", dest="Westport", lkr_per_kg=5, **lane),
        Lane(origin="Riverside", dest="Eastport", lkr_per_kg=20, **lane)])
    day = date.today() + timedelta(days=1)
    store.DB.put("listings", "L1", dict(id="L1", phone="1", farmer="Asha", location="Hilltown", crop="carrot",
                                        qty_kg=100, ready_on=day.isoformat(), remaining_kg=100))
    store.DB.put("orders", "O1", dict(id="O1", phone="2", buyer="West Cafe", location="Westport", crop="carrot",
                                      qty_kg=100, needed_by=(day + timedelta(days=1)).isoformat(), remaining_kg=100))
    deals.plan()
    for m in store.matches():
        deals.confirm(m)
    store.DB.put("listings", "L2", dict(id="L2", phone="3", farmer="Bala", location="Riverside", crop="carrot",
                                        qty_kg=100, ready_on=day.isoformat(), remaining_kg=100))
    store.DB.put("orders", "O2", dict(id="O2", phone="4", buyer="East Hotel", location="Eastport", crop="carrot",
                                      qty_kg=60, needed_by=(day + timedelta(days=1)).isoformat(), remaining_kg=60))
    deals.plan()
    [s] = reroute.swaps()
    assert s["kg"] == 60 and s["saved_lkr"] == 60 * 30
    for phone in "1234":
        reroute.answer(phone, "yes", deals._send)
    live = {(m.listing_id, m.order_id): m.qty_kg for m in store.matches() if m.status == "confirmed"}
    assert live == {("L1", "O1"): 40, ("L1", "O2"): 60, ("L2", "O1"): 60}
