"""Verify P0 correctness invariants:
1. Confirmed deals are price-immutable.
2. remaining_kg never drops below zero.
3. Self-match between same phone is blocked.
4. Rescue match decline triggers automatic wholesale backup buy.
5. Inverted retail < collector price clamping.
6. Unbundled matches produce tracked shipment records.
"""
from datetime import date, datetime, timedelta, timezone
import pytest
from app import deals, matcher, pricing, rescue, store
from app.schemas import Lane, Listing, Match, Order, Shipment

THU, FRI = date(2026, 10, 15), date(2026, 10, 16)


def test_confirmed_deal_price_is_immutable():
    store.reset()
    lane = Lane(origin="Nuwara Eliya", dest="Colombo", mode="night_bus", lkr_per_kg=10,
                min_charge_lkr=200, departs="20:00", transit_hours=6, max_kg=500, handling_lkr=100, source="TEST")
    m = Match(id="M1", status="confirmed", farmer_ok=True, buyer_ok=True, listing_id="L1", order_id="O1",
              farmer="Sunil", buyer="Cafe", crop="carrot", qty_kg=100, lane=lane, solo_lane=lane,
              transport_lkr_per_kg=10, solo_transport_lkr_per_kg=10, ship_on=THU, needed_by=FRI,
              farmer_gets_lkr_per_kg=150.0, buyer_pays_lkr_per_kg=180.0,
              collector_pays_lkr_per_kg=100.0, market_retail_lkr_per_kg=200.0)
    store.put_match(m)
    # Price reports shift wildly in the market
    shifted_prices = {"carrot": {"crop": "carrot", "collector": 50, "retail": 80}}
    # Re-bundle with shifted prices
    shipments = matcher.bundle([m], [lane], shifted_prices)
    # The agreed farmer payout must NOT drop to shifted prices
    assert m.farmer_gets_lkr_per_kg == 150.0


def test_remaining_kg_never_negative():
    store.reset()
    store.put("listings", {"id": "L1", "remaining_kg": 10.0})
    store.adjust_remaining("listings", "L1", -50.0)
    assert store.get("listings", "L1")["remaining_kg"] == 0.0


def test_self_match_blocked():
    lanes = deals.LANES
    prices = store.prices()
    listings = [Listing(id="L1", phone="94771111111", farmer="Sunil", location="Nuwara Eliya",
                        crop="carrot", qty_kg=100, ready_on=THU, remaining_kg=100)]
    orders = [Order(id="O1", phone="94771111111", buyer="Sunil", location="Colombo",
                    crop="carrot", qty_kg=100, needed_by=FRI, remaining_kg=100)]
    matches, _ = matcher.match(listings, orders, lanes, prices)
    assert matches == []


def test_rescue_decline_triggers_backup_buy():
    store.reset()
    store.put("orders", {"id": "O1", "phone": "94772222222", "buyer": "Cafe", "location": "Colombo",
                         "crop": "carrot", "qty_kg": 50, "needed_by": FRI.isoformat(), "remaining_kg": 50})
    m = Match(id="RM1", status="proposed", farmer_ok=False, buyer_ok=False, listing_id="L2", order_id="O1",
              farmer="Kamal", buyer="Cafe", crop="carrot", qty_kg=50, lane=None, transport_lkr_per_kg=0,
              needed_by=FRI, ship_on=THU, farmer_gets_lkr_per_kg=120, buyer_pays_lkr_per_kg=180,
              collector_pays_lkr_per_kg=100, market_retail_lkr_per_kg=220, note="rescue: replacement farmer")
    store.put_match(m)
    # Replacement farmer Kamal declines
    sent = []
    backup = rescue.decline_rescue_match(m, send=lambda to, body, mid: sent.append((to, body)))
    assert backup.note == "rescue: backup buy"
    assert backup.status == "confirmed"
    assert backup.qty_kg == 50
    assert store.get("orders", "O1")["remaining_kg"] == 0.0


def test_price_sanity_market_inversion():
    inverted = {"collector": 200, "retail": 150}
    s = pricing.split(inverted, transport_lkr_per_kg=10)
    # Buyer pays must never exceed retail
    assert s["buyer_pays"] <= 150.0


def test_unbundled_matches_still_create_shipments():
    lane = Lane(origin="Nuwara Eliya", dest="Colombo", mode="night_bus", lkr_per_kg=10,
                min_charge_lkr=200, departs="20:00", transit_hours=6, max_kg=50, handling_lkr=100, source="TEST")
    m = Match(id="M_OVER", status="proposed", listing_id="L1", order_id="O1", farmer="Sunil", buyer="Cafe",
              crop="carrot", qty_kg=200, lane=lane, solo_lane=lane, transport_lkr_per_kg=10,
              solo_transport_lkr_per_kg=10, ship_on=THU, needed_by=FRI, farmer_gets_lkr_per_kg=150,
              buyer_pays_lkr_per_kg=180, collector_pays_lkr_per_kg=100, market_retail_lkr_per_kg=200)
    # Total is 200kg, lane max is 50kg -> bundling fails, but solo shipment must be created!
    shipments = matcher.bundle([m], [lane], {"carrot": {"collector": 100, "retail": 200}})
    assert len(shipments) == 1
    assert shipments[0].total_kg == 200
    assert m.shipment_id == shipments[0].id


def test_selective_match_acceptance():
    store.reset()
    store.put("listings", {"id": "L1", "phone": "94773333333", "farmer": "Sunil", "lang": "en"})
    store.put("listings", {"id": "L2", "phone": "94773333333", "farmer": "Sunil", "lang": "en"})
    store.put("orders", {"id": "O1", "phone": "94774444444", "buyer": "Cafe", "lang": "en"})
    store.put("orders", {"id": "O2", "phone": "94775555555", "buyer": "Hotel", "lang": "en"})
    m1 = Match(id="M1", status="proposed", listing_id="L1", order_id="O1", farmer="Sunil", buyer="Cafe",
               crop="carrot", qty_kg=50, needed_by=FRI, lane=None, transport_lkr_per_kg=0,
               farmer_gets_lkr_per_kg=120, buyer_pays_lkr_per_kg=150,
               collector_pays_lkr_per_kg=100, market_retail_lkr_per_kg=180)
    m2 = Match(id="M2", status="proposed", listing_id="L2", order_id="O2", farmer="Sunil", buyer="Hotel",
               crop="beans", qty_kg=40, needed_by=FRI, lane=None, transport_lkr_per_kg=0,
               farmer_gets_lkr_per_kg=180, buyer_pays_lkr_per_kg=220,
               collector_pays_lkr_per_kg=150, market_retail_lkr_per_kg=250)
    store.put_match(m1)
    store.put_match(m2)

    # Sunil says "YES 1 NO 2"
    reply = deals.answer("94773333333", "YES 1 NO 2")
    assert reply is not None
    m1_updated = next(m for m in store.matches() if m.id == "M1")
    m2_updated = next(m for m in store.matches() if m.id == "M2")
    assert m1_updated.farmer_ok is True
    assert m1_updated.status == "proposed"  # waiting on buyer
    assert m2_updated.status == "declined"


def test_rescue_watchdog_catches_passed_departures():
    store.reset()
    lane = Lane(origin="Dambulla", dest="Colombo", mode="night_bus", lkr_per_kg=10,
                min_charge_lkr=200, departs="22:00", transit_hours=5, max_kg=300, handling_lkr=100, source="TEST")
    m = Match(id="M_PAST", status="confirmed", farmer_ok=True, buyer_ok=True, listing_id="L1", order_id="O1",
              farmer="Nimal", buyer="Hotel", crop="beans", qty_kg=100, needed_by=FRI, lane=lane, transport_lkr_per_kg=10,
              farmer_gets_lkr_per_kg=180, buyer_pays_lkr_per_kg=220, collector_pays_lkr_per_kg=150,
              market_retail_lkr_per_kg=250)
    store.put_match(m)
    s = Shipment(id="S_PAST", origin="Dambulla", dest="Colombo", ship_on=THU, lane=lane,
                 match_ids=["M_PAST"], farmers=["Nimal"], buyers=["Hotel"], total_kg=100,
                 cost_lkr=1100, lkr_per_kg=11, solo_cost_lkr=1100, saved_lkr=0, status="booked",
                 schedule={"in_transit": "2026-10-15T22:00:00+00:00"})
    store.put_shipment(s)

    # Watchdog runs at 23:00 (departure already passed)
    now = datetime(2026, 10, 15, 23, 0, tzinfo=timezone.utc)
    rescued = rescue.watchdog(now=now, send=lambda *a, **k: None)
    assert "S_PAST" in rescued
    assert next(x for x in store.shipments() if x.id == "S_PAST").status == "missed"


def test_cancel_does_not_decline_match_offer():
    store.reset()
    from app import convo
    # Farmer Sunil has a proposed match offer
    store.put("listings", {"id": "L1", "phone": "94779999999", "farmer": "Sunil", "lang": "en"})
    store.put("orders", {"id": "O1", "phone": "94778888888", "buyer": "Hotel", "lang": "en"})
    m = Match(id="M1", status="proposed", listing_id="L1", order_id="O1", farmer="Sunil", buyer="Hotel",
              crop="carrot", qty_kg=100, needed_by=FRI, lane=None, transport_lkr_per_kg=0,
              farmer_gets_lkr_per_kg=120, buyer_pays_lkr_per_kg=150,
              collector_pays_lkr_per_kg=100, market_retail_lkr_per_kg=180)
    store.put_match(m)
    # Sunil says "cancel": withdraws his listing (cancelled), does not decline the offer (declined)
    turn = convo.step(sender="94779999999", text="cancel", media=None, mime_type=None,
                      today=THU, confirm_first=False)
    assert "Cancelled ref" in turn.reply
    assert next(x for x in store.matches() if x.id == "M1").status == "cancelled"
    assert store.DB.one("listings", "L1") is None  # listing withdrawn


def test_planned_shipment_id_stability_and_transport_tie_out():
    store.reset()
    store.put("listings", {"id": "L1", "phone": "94771111111", "farmer": "Sunil", "location": "Nuwara Eliya",
                           "crop": "carrot", "qty_kg": 100, "ready_on": THU.isoformat(), "remaining_kg": 100})
    store.put("orders", {"id": "O1", "phone": "94772222222", "buyer": "Hotel", "location": "Colombo",
                         "crop": "carrot", "qty_kg": 100, "needed_by": FRI.isoformat(), "remaining_kg": 100})
    p1 = deals.plan(today=THU)
    assert len(p1["shipments"]) == 1
    s1_id = p1["shipments"][0]["id"]
    # Run plan again without changes: shipment id must be stable
    p2 = deals.plan(today=THU)
    s2_id = p2["shipments"][0]["id"]
    assert s1_id == s2_id
    # Transport saved in impact must tie out to sum of shipment saved_lkr
    assert p2["impact"]["transport_saved_lkr"] == sum(s["saved_lkr"] for s in p2["shipments"])


def test_partial_quantity_acceptance():
    store.reset()
    store.put("listings", {"id": "L1", "phone": "94776666661", "farmer": "Sunil", "lang": "en"})
    store.put("orders", {"id": "O1", "phone": "94776666662", "buyer": "Hotel", "lang": "en"})
    m = Match(id="M_PARTIAL", status="proposed", listing_id="L1", order_id="O1", farmer="Sunil", buyer="Hotel",
              crop="carrot", qty_kg=100, needed_by=FRI, lane=None, transport_lkr_per_kg=0,
              farmer_gets_lkr_per_kg=120, buyer_pays_lkr_per_kg=150,
              collector_pays_lkr_per_kg=100, market_retail_lkr_per_kg=180)
    store.put_match(m)

    # Sunil accepts only 40kg instead of full 100kg
    reply = deals.answer("94776666661", "YES 40kg")
    assert reply is not None
    updated = next(x for x in store.matches() if x.id == "M_PARTIAL")
    assert updated.qty_kg == 40.0
    assert updated.farmer_ok is True


def test_offer_expiry_and_sla_reminder():
    store.reset()
    now = datetime.now(timezone.utc)
    store.put("listings", {"id": "L1", "phone": "94777777771", "farmer": "Sunil", "location": "Nuwara Eliya",
                           "crop": "carrot", "qty_kg": 50, "ready_on": THU.isoformat(), "remaining_kg": 50, "lang": "en"})
    store.put("orders", {"id": "O1", "phone": "94777777772", "buyer": "Hotel", "location": "Colombo",
                         "crop": "carrot", "qty_kg": 50, "needed_by": FRI.isoformat(), "remaining_kg": 50, "lang": "en"})

    # 1. Offer expiring in 40 minutes (< 1h) triggers reminder
    m = Match(id="M_EXP", status="proposed", listing_id="L1", order_id="O1", farmer="Sunil", buyer="Hotel",
              crop="carrot", qty_kg=50, needed_by=FRI, lane=None, transport_lkr_per_kg=0,
              farmer_gets_lkr_per_kg=120, buyer_pays_lkr_per_kg=150,
              collector_pays_lkr_per_kg=100, market_retail_lkr_per_kg=180,
              expires_at=(now + timedelta(minutes=40)).isoformat(), reminded=False)
    store.put_match(m)
    deals.plan(today=THU)
    assert next(x for x in store.matches() if x.id == "M_EXP").reminded is True


def test_dynamic_lanes_reload():
    lanes = deals.reload_lanes()
    assert len(lanes) > 0
    assert all(isinstance(l, Lane) for l in lanes)


def test_carrier_webhook_tracking_and_failure():
    from fastapi.testclient import TestClient
    from app import main
    store.reset()
    store.put("listings", {"id": "L1", "phone": "94778888881", "farmer": "Sunil", "location": "Nuwara Eliya",
                           "crop": "carrot", "qty_kg": 100, "ready_on": THU.isoformat(), "remaining_kg": 100, "lang": "en"})
    store.put("orders", {"id": "O1", "phone": "94778888882", "buyer": "Hotel", "location": "Colombo",
                         "crop": "carrot", "qty_kg": 100, "needed_by": FRI.isoformat(), "remaining_kg": 100, "lang": "en"})
    p = deals.plan(today=THU)
    m = next(x for x in store.matches())
    deals.confirm(m)
    sid = p["shipments"][0]["id"]
    deals.advance_shipment(sid)  # planned -> booked (generates ref)
    s = next(x for x in store.shipments() if x.id == sid)
    assert s.ref is not None

    client = TestClient(main.app)
    # Carrier webhook advances by ref to in_transit
    res = client.post("/webhook/carrier", json={"ref": s.ref, "status": "in_transit", "note": "departed terminal"})
    assert res.status_code == 200
    assert res.json()["status"] == "in_transit"

    # Carrier webhook reports breakdown / failure -> triggers rescue
    res2 = client.post("/webhook/carrier", json={"ref": s.ref, "status": "failed", "note": "lorry engine breakdown"})
    assert res2.status_code == 200
    assert next(x for x in store.shipments() if x.id == sid).status == "missed"

