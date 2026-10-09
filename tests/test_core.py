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
"when":"2026-10-15","items":[{"crop":"carrot","qty_kg":280,"grade":null,"price_lkr_per_kg":null}],
"unclear":[],"confidence":0.92,"summary_in_sender_language":"..."}"""
BUYER_JSON = """{"role":"buyer","language":"en","sender_name":"Cafe","location":"Colombo",
"when":"2026-10-16","items":[{"crop":"carrot","qty_kg":200,"grade":null,"price_lkr_per_kg":null}],
"unclear":[],"confidence":0.88,"summary_in_sender_language":"..."}"""


def test_parser_sends_image_and_schema():
    fake = SimpleNamespace(models=FakeModels(FARMER_JSON))
    out = parser.parse(media=b"\xff\xd8", mime_type="image/jpeg", today="2026-10-13", client=fake)
    call = fake.models.calls[0]
    assert call["config"].response_json_schema["title"] == "ParsedMessage"
    assert out.items[0].qty_kg == 280


def test_api_end_to_end(monkeypatch):
    store.reset()
    replies = iter([FARMER_JSON, BUYER_JSON])
    monkeypatch.setattr(parser, "_client", lambda: SimpleNamespace(
        models=SimpleNamespace(generate_content=lambda **kw: SimpleNamespace(text=next(replies)))))
    c = TestClient(app)
    assert c.post("/intake", data={"text": "කැරට් කිලෝ 280 බ්‍රහස්පතින්දා"}).status_code == 200
    assert c.post("/intake", files={"file": ("order.jpg", b"\xff\xd8", "image/jpeg")}).status_code == 200
    plan = c.post("/plan").json()
    assert plan["impact"]["kg_matched"] == 200
    assert plan["surplus"][0]["remaining_kg"] == 80
