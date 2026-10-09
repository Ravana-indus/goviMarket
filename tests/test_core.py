import os
from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import parser, store
from app.lanes import load_lanes, pick_lane
from app.main import app
from app.matcher import impact, match
from app.pricing import load_prices, split
from app.schemas import Listing, Order

LANES = load_lanes()
PRICES = load_prices()
THU, FRI = date(2026, 10, 15), date(2026, 10, 16)


def test_pick_lane_cheapest_that_arrives_in_time():
    lane = pick_lane(LANES, origin="Nuwara Eliya", dest="Colombo", kg=200, ship_on=THU, needed_by=FRI)
    # Train parcel (Rs 8/kg) leaves 09:30 Thu, lands 19:30 Thu: cheaper than the night bus and on time.
    assert lane.mode == "train_parcel"


def test_pick_lane_none_when_too_late():
    assert pick_lane(LANES, origin="Badulla", dest="Colombo", kg=20, ship_on=FRI, needed_by=FRI) is None


def test_split_gives_farmer_more_than_collector():
    m = split(PRICES["carrot"], transport_lkr_per_kg=12)
    assert m["farmer_gets"] > m["collector"] and m["buyer_pays"] < m["retail"]


def test_match_fills_order_and_reports_surplus():
    listings = [Listing(id="L1", farmer="Sunil", location="Nuwara Eliya", crop="carrot",
                        qty_kg=280, ready_on=THU, remaining_kg=280)]
    orders = [Order(id="O1", buyer="Cafe", location="Colombo", crop="carrot",
                    qty_kg=200, needed_by=FRI, remaining_kg=200)]
    matches, surplus = match(listings, orders, LANES, PRICES)
    assert len(matches) == 1 and matches[0].qty_kg == 200
    assert surplus[0].remaining_kg == 80
    assert impact(matches)["farmer_extra_lkr"] > 0


def test_match_skips_unknown_crop_and_late_harvest():
    listings = [Listing(id="L1", farmer="A", location="Dambulla", crop="carrot",
                        qty_kg=50, ready_on=FRI, remaining_kg=50)]
    orders = [Order(id="O1", buyer="B", location="Colombo", crop="carrot", qty_kg=50,
                    needed_by=THU, remaining_kg=50),
              Order(id="O2", buyer="B", location="Colombo", crop="durian", qty_kg=5,
                    needed_by=FRI, remaining_kg=5)]
    matches, _ = match(listings, orders, LANES, PRICES)
    assert matches == []


class FakeModels:
    def __init__(self, payload): self.payload, self.calls = payload, []
    def generate_content(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(text=self.payload)


FARMER_JSON = """{"role":"farmer","language":"si","sender_name":"Sunil","location":"Nuwara Eliya",
"when":"2026-10-15","items":[{"crop":"carrot","qty_kg":280,"grade":null,"price_lkr_per_kg":null,"price_kind":null}],
"unclear":[],"confidence":0.92,"summary_in_sender_language":"..."}"""
BUYER_JSON = """{"role":"buyer","language":"en","sender_name":"Cafe","location":"Colombo",
"when":"2026-10-16","items":[{"crop":"carrot","qty_kg":200,"grade":null,"price_lkr_per_kg":null,"price_kind":null}],
"unclear":[],"confidence":0.88,"summary_in_sender_language":"..."}"""


def test_parser_sends_image_and_schema():
    fake = SimpleNamespace(models=FakeModels(FARMER_JSON))
    out = parser.parse(media=b"\xff\xd8", mime_type="image/jpeg", today="2026-10-13", client=fake)
    call = fake.models.calls[0]
    assert call["config"].response_json_schema["title"] == "ParsedMessage"
    assert out.items[0].qty_kg == 280


def test_api_end_to_end(monkeypatch):
    store.reset()
    _fake_gemini(monkeypatch, FARMER_JSON, BUYER_JSON)
    c = TestClient(app)
    assert c.post("/intake", data={"text": "කැරට් කිලෝ 280 බ්‍රහස්පතින්දා"}).status_code == 200
    assert c.post("/intake", files={"file": ("order.jpg", b"\xff\xd8", "image/jpeg")}).status_code == 200
    plan = c.post("/plan").json()
    assert plan["impact"]["kg_matched"] == 200
    assert plan["surplus"][0]["remaining_kg"] == 80


REPORTER_JSON = """{"role":"reporter","language":"si","sender_name":"Kamal","location":"Dambulla",
"when":"2026-10-13","items":[{"crop":"carrot","qty_kg":0,"grade":null,"price_lkr_per_kg":150,"price_kind":"collector"}],
"unclear":[],"confidence":0.9,"summary_in_sender_language":"..."}"""


def _fake_gemini(monkeypatch, *payloads):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    it = iter(payloads)
    monkeypatch.setattr(parser, "_client", lambda: SimpleNamespace(
        models=SimpleNamespace(generate_content=lambda **kw: SimpleNamespace(text=next(it)))))


def test_reporter_price_overrides_seed_and_farmer_gets_fair_price_reply(monkeypatch):
    store.reset()
    _fake_gemini(monkeypatch, REPORTER_JSON, FARMER_JSON)
    c = TestClient(app)
    c.post("/intake", data={"text": "carrot collector 150"})
    assert store.prices()["carrot"]["collector"] == 150
    reply = c.post("/intake", data={"text": "කැරට් 280"}).json()["reply"]
    assert "රු. 150" in reply  # Sinhala fair-price line quotes the reported collector price


def test_whatsapp_webhook_parses_and_replies(monkeypatch):
    from app import whatsapp
    store.reset()
    _fake_gemini(monkeypatch, FARMER_JSON)
    sent = []
    monkeypatch.setattr(whatsapp, "fetch_media", lambda mid: b"ogg")
    monkeypatch.setattr(whatsapp, "send_text", lambda to, body: sent.append((to, body)))
    payload = {"entry": [{"changes": [{"value": {"messages": [
        {"from": "94771234567", "type": "audio", "audio": {"id": "m1", "mime_type": "audio/ogg"}}]}}]}]}
    assert TestClient(app).post("/webhook/whatsapp", json=payload).status_code == 200
    assert sent and sent[0][0] == "94771234567"
    assert len(store.listings()) == 1


def test_whatsapp_signature(monkeypatch):
    from app import whatsapp
    import hashlib, hmac
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "s")
    sig = "sha256=" + hmac.new(b"s", b"{}", hashlib.sha256).hexdigest()
    assert whatsapp.verify_signature(b"{}", sig)
    assert not whatsapp.verify_signature(b"{}", "sha256=bad")


def test_demo_seed_runs_offline_and_pages_serve(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    c = TestClient(app)
    plan = c.post("/demo/seed").json()
    assert plan["impact"]["kg_matched"] > 0 and plan["surplus"]
    assert c.get("/api/prices").json()[0]["farmer_fair"] > 0
    sunil = c.get("/api/track", params={"phone": "94770000002"}).json()
    assert sunil["listings"][0]["matched_kg"] >= 200
    assert c.get("/").status_code == 200 and c.get("/admin").status_code == 200


def test_both_sides_confirm_and_stock_is_held(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    c = TestClient(app)
    plan = c.post("/demo/seed").json()
    m = next(x for x in plan["matches"] if x["status"] == "proposed" and x["buyer"] == "Mango Tree Cafe")
    farmer = store.get("listings", m["listing_id"])
    before = farmer["remaining_kg"]
    sent = c.get("/state").json()["outbox"]
    assert any(o["to"] == farmer["phone"] and "YES" in o["body"] for o in sent)  # farmer notified
    assert c.post("/intake", data={"text": "ඔව්", "sender": farmer["phone"]}).json()["reply"].startswith("Thanks")
    # the buyer may have several pending loads; keep saying yes until this one is confirmed
    for _ in range(4):
        c.post("/intake", data={"text": "yes", "sender": "94770000014"})
    assert next(x for x in store.matches() if x.id == m["id"]).status == "confirmed"
    assert store.get("listings", m["listing_id"])["remaining_kg"] == before - m["qty_kg"]
    again = c.post("/plan").json()
    assert sum(x["qty_kg"] for x in again["matches"] if x["listing_id"] == m["listing_id"]) <= farmer["qty_kg"]


def test_decline_frees_the_match(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    c = TestClient(app)
    c.post("/demo/seed")
    pending = next(x for x in store.matches() if x.status == "proposed")
    phone = store.get("listings", pending.listing_id)["phone"]
    assert c.post("/intake", data={"text": "no", "sender": phone}).json()["reply"].startswith("Declined")
    live = c.post("/plan").json()["matches"]
    declined = [m for m in __import__("app.store", fromlist=["x"]).matches() if m.status == "declined"]
    assert declined and declined[0].id == pending.id
    assert declined[0].id not in {x["id"] for x in live}
    assert not any(x["listing_id"] == declined[0].listing_id and x["order_id"] == declined[0].order_id for x in live)


def test_agent_passes_tools_and_language():
    from app import agent
    from app.schemas import Match
    calls = []
    fake = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kw: calls.append(kw) or SimpleNamespace(text="ok")))
    m = Match(id="x", listing_id="L", order_id="O", farmer="Sunil", buyer="Cafe", crop="carrot", qty_kg=200,
              lane=None, transport_lkr_per_kg=0, farmer_gets_lkr_per_kg=250, buyer_pays_lkr_per_kg=280,
              collector_pays_lkr_per_kg=150, market_retail_lkr_per_kg=320)
    assert agent.explain(m, party="farmer", lang="si", prices=PRICES, client=fake) == "ok"
    cfg = calls[0]["config"]
    assert "Sinhala" in cfg.system_instruction and agent.get_price_board in cfg.tools
    assert agent.get_price_board("carrot")["collector"] == PRICES["carrot"]["collector"]


def test_bundling_shares_one_consignment_and_nobody_pays_more():
    from app.matcher import bundle
    listings = [Listing(id=f"L{i}", farmer=f"F{i}", location="Nuwara Eliya", crop="carrot",
                        qty_kg=kg, ready_on=THU, remaining_kg=kg) for i, kg in enumerate([200, 60, 40])]
    orders = [Order(id="O1", buyer="Cafe", location="Colombo", crop="carrot", qty_kg=300,
                    needed_by=FRI, remaining_kg=300)]
    matches, _ = match(listings, orders, LANES, PRICES)
    for i, m in enumerate(matches):
        m.id = f"m{i}"
    solo = {m.id: m.transport_lkr_per_kg for m in matches}
    shipments = bundle(matches, LANES, PRICES)
    assert len(shipments) == 1 and shipments[0].total_kg == 300
    assert shipments[0].saved_lkr > 0
    assert all(m.transport_lkr_per_kg < solo[m.id] for m in matches)
    assert all(m.shipment_id == shipments[0].id for m in matches)


def test_farmer_reply_quotes_price_after_transport(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    store.reset()
    out = TestClient(app).post("/intake", data={"text": "This is Sunil, carrot 100kg ready tomorrow, Nuwara Eliya"}).json()
    assert "after transport" in out["reply"]



def test_shipment_moves_through_every_step_and_messages_both_sides(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    c = TestClient(app)
    plan = c.post("/demo/seed").json()
    statuses = {x["status"] for x in plan["shipments"]}
    assert {"planned", "booked", "loaded", "in_transit", "delivered"} <= statuses
    assert {x["lane"]["mode"] for x in plan["shipments"]} >= {"train_parcel", "sl_post", "lorry"}
    waiting = next(x for x in plan["shipments"] if x["status"] == "planned")
    assert c.post(f"/shipments/{waiting['id']}/advance").status_code == 409  # nobody said YES yet
    booked = next(x for x in plan["shipments"] if x["status"] == "booked")
    n_sent = len(c.get("/state").json()["outbox"])
    for want in ["loaded", "in_transit", "arrived", "delivered"]:
        assert c.post(f"/shipments/{booked['id']}/advance").json()["status"] == want
    sent = c.get("/state").json()["outbox"][n_sent:]
    assert any("Delivered" in o["body"] or "භාර" in o["body"] for o in sent)
    track = c.get("/api/track", params={"phone": "94770000011"}).json()
    assert any(m["shipment"] for o in track["orders"] for m in o["matches"])


def test_business_order_matches_and_standing_order_repeats(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    c = TestClient(app)
    c.post("/demo/seed")
    cat = {r["crop"]: r for r in c.get("/api/catalogue").json()}
    assert cat["carrot"]["price"] < cat["carrot"]["retail"] and cat["carrot"]["signal"]
    need = (date.today() + __import__("datetime").timedelta(days=2)).isoformat()
    body = {"phone": "94779999999", "business": "Test Bistro", "needed_by": need,
            "items": [{"crop": "tomato", "qty_kg": 40}], "repeat_weekly": True}
    out = c.post("/api/orders", json=body).json()
    assert out["ordered_kg"] == 40 and out["matched_kg"] > 0
    st = c.get("/api/standing", params={"phone": "94779999999"}).json()
    assert len(st) == 1
    again = c.post(f"/api/standing/{st[0]['id']}/run").json()
    assert again["ordered_kg"] == 40
    assert c.post("/api/orders", json={**body, "items": [{"crop": "durian", "qty_kg": 5}]}).status_code == 400
    assert c.get("/business").status_code == 200


def test_forecast_numbers_are_consistent():
    from app import forecast
    store.reset()
    rows = forecast.outlook()
    assert rows and all(r["low"] <= r["collector_next_week"] <= r["high"] for r in rows)
    assert all(r["source"] == "synthetic" for r in rows)
    assert "Synthetic" in forecast.explain(rows) or os.getenv("GEMINI_API_KEY")


def test_agent_prices_go_live_and_big_jumps_wait_for_check(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    c = TestClient(app)
    c.post("/demo/seed")
    b = {r["crop"]: r for r in c.get("/api/agent/board", params={"kind": "collector"}).json()["crops"]}
    carrot, beans = b["carrot"]["current"], b["beans"]["current"]
    body = {"reporter": "Kumari", "phone": "94770000099", "market": "Dambulla", "kind": "collector",
            "prices": [{"crop": "carrot", "lkr_per_kg": carrot + 10}, {"crop": "beans", "lkr_per_kg": beans * 3}]}
    out = c.post("/api/agent/prices", json=body).json()
    flags = {s["crop"]: s["flagged"] for s in out["saved"]}
    assert flags == {"carrot": False, "beans": True}
    live = c.get("/api/prices").json()
    live = {p["crop"]: p for p in (live if isinstance(live, list) else live.values())}
    # same day as the seed reporter, so the board shows the median of the two agents
    assert live["carrot"]["collector"] == carrot + 5 and live["beans"]["collector"] == beans
    rid = next(s["id"] for s in out["saved"] if s["flagged"])
    assert c.post(f"/api/agent/reports/{rid}/approve").status_code == 200
    b2 = {r["crop"]: r for r in c.get("/api/agent/board", params={"kind": "collector", "market": "Dambulla"}).json()["crops"]}
    assert b2["beans"]["current"] == beans * 2 and b2["carrot"]["last_here"] == carrot + 10
    assert c.post("/api/agent/prices", json={**body, "prices": [{"crop": "durian", "lkr_per_kg": 100}]}).status_code == 400
    assert len(c.get("/api/agent/reports", params={"phone": "94770000099"}).json()) == 2
    assert c.get("/agent").status_code == 200


def _seeded(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    c = TestClient(app)
    c.post("/demo/seed")
    return c, c.get("/api/plan").json()


def test_kandy_order_is_filled_from_the_nearest_town(monkeypatch):
    c, plan = _seeded(monkeypatch)
    kandy = [m for m in plan["matches"] if m["buyer"] == "Hill View Hotel"]
    assert kandy and all(m["lane"]["origin"] == "Dambulla" and m["lane"]["dest"] == "Kandy" for m in kandy)


def test_missed_departure_reroutes_when_a_later_one_is_on_time(monkeypatch):
    c, plan = _seeded(monkeypatch)
    x = next(s for s in plan["shipments"] if s["status"] in ("booked", "loaded") and s.get("backup"))
    r = c.post(f"/shipments/{x['id']}/missed").json()
    assert r["action"] == "rerouted"
    after = c.get("/api/plan").json()
    new = next(s for s in after["shipments"] if s["id"] == r["new_shipment"])
    assert new["status"] == "booked" and new["lane"]["departs"] > x["lane"]["departs"]
    moved = [m for m in after["matches"] if m["id"] in x["match_ids"]]
    assert moved and all(m["shipment_id"] == new["id"] and m["status"] == "confirmed" for m in moved)
    # farmer's price did not change; the extra freight is Govi's
    before = {m["id"]: m["farmer_gets_lkr_per_kg"] for m in plan["matches"]}
    assert all(m["farmer_gets_lkr_per_kg"] == before[m["id"]] for m in moved)
    assert c.post(f"/shipments/{x['id']}/missed").status_code == 409


def test_missed_last_departure_covers_every_buyer(monkeypatch):
    c, plan = _seeded(monkeypatch)
    x = next(s for s in plan["shipments"] if s["status"] in ("booked", "loaded") and s.get("backup") == "")
    need = {}
    for m in plan["matches"]:
        if m["id"] in x["match_ids"]:
            need[m["order_id"]] = need.get(m["order_id"], 0) + m["qty_kg"]
    r = c.post(f"/shipments/{x['id']}/missed").json()
    assert r["action"] in ("resourced", "backup", "resourced+backup")
    after = c.get("/api/plan").json()
    origin = x["origin"]
    for oid, kg_ in need.items():
        cover = [m for m in after["matches"] if m["order_id"] == oid and m.get("note", "").startswith("rescue")]
        assert sum(m["qty_kg"] for m in cover) >= kg_
        assert all(m["lane"] is None or m["lane"]["origin"] != origin for m in cover)
    stranded = {m["listing_id"] for m in plan["matches"] if m["id"] in x["match_ids"]}
    assert stranded & {s["id"] for s in after["surplus"]}


def test_unsold_produce_gets_numbered_offers_and_a_reply_settles_it(monkeypatch):
    c, plan = _seeded(monkeypatch)
    offers = c.post("/surplus/sweep").json()
    assert offers and c.post("/surplus/sweep").json() == []  # one offer per load
    o = next(x for x in offers if x["options"][0]["kind"] == "processor" and x["phone"])
    assert o["options"][-1]["kind"] == "keep" and "1." in o["message"]
    r = c.post("/intake", data={"text": "1", "sender": o["phone"]}).json()
    assert "Done" in r["reply"]
    after = c.get("/api/plan").json()
    assert after["impact"]["surplus_rescued_kg"] >= o["kg"]
    assert o["listing_id"] not in {s["id"] for s in after["surplus"]}


def test_gemini_outage_still_answers_text_and_seed_stays_offline(monkeypatch):
    from app import ai, security
    calls = []
    def broken():
        calls.append(1)
        raise RuntimeError("429 RESOURCE_EXHAUSTED")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(parser, "_client", broken)
    security.reset_limits()
    c = TestClient(app)
    assert c.post("/demo/seed").status_code == 200
    assert calls == []  # demo seed never spends Gemini quota
    r = c.post("/intake", data={"text": "This is Nimal, tomato 150kg ready tomorrow, Dambulla",
                                "sender": "94770000004", "via": "sim"})
    assert r.status_code == 200 and "tomato" in r.json()["reply"].lower()
    assert calls and "RESOURCE_EXHAUSTED" in ai.last_error["error"]
    photo = c.post("/intake", data={"sender": "94770000004", "via": "sim"},
                   files={"file": ("p.jpg", b"\xff\xd8", "image/jpeg")})
    assert photo.status_code == 502
    assert c.get("/favicon.ico").status_code == 200


def test_one_shared_gemini_client(monkeypatch):
    from app import ai
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(ai, "_client", None)
    assert parser._client() is parser._client()  # an inline throwaway client closes mid-call
    monkeypatch.setattr(ai, "_client", None)
