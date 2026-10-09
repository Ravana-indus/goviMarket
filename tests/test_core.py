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
    assert sunil["listings"][0]["matched_kg"] == 200
    assert c.get("/").status_code == 200 and c.get("/admin").status_code == 200


def test_both_sides_confirm_and_stock_is_held(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    c = TestClient(app)
    plan = c.post("/demo/seed").json()
    m = next(x for x in plan["matches"] if x["farmer"] == "Sunil")
    sent = c.get("/state").json()["outbox"]
    assert any(o["to"] == "94770000002" and "YES" in o["body"] for o in sent)  # farmer notified
    assert c.post("/intake", data={"text": "ඔව්", "sender": "94770000002"}).json()["reply"].startswith("Thanks")
    assert c.post("/intake", data={"text": "yes", "sender": "94770000011"}).json()["reply"].startswith("Confirmed")
    s = c.get("/state").json()
    sunil = next(l for l in s["listings"] if l["id"] == m["listing_id"])
    assert sunil["remaining_kg"] == 80
    # Re-running matching keeps confirmed and pending deals and does not double-allocate.
    again = c.post("/plan").json()
    assert sum(x["qty_kg"] for x in again["matches"] if x["listing_id"] == m["listing_id"]) <= 280
    assert again["impact"]["confirmed"] == 1


def test_decline_frees_the_match(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    c = TestClient(app)
    c.post("/demo/seed")
    assert c.post("/intake", data={"text": "no", "sender": "94770000002"}).json()["reply"].startswith("Declined")
    live = c.post("/plan").json()["matches"]
    declined = [m for m in __import__("app.store", fromlist=["x"]).matches() if m.status == "declined"]
    assert declined and declined[0].farmer == "Sunil"
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
