"""After both sides say YES the seller gets a dispatch slip with the buyer's address and a tracking code."""
from datetime import timedelta

from app import dispatch, store
from tests.test_conversations import TODAY, TOMORROW, P, Phone, g  # noqa: F401


def _deal(g, farmer="94771200001", buyer="94771200002", address=None):
    store.DB.put("users", buyer, {"phone": buyer, "name": "Lotus Kitchen", "role": "buyer", "lang": "",
                                  **({"address": address} if address else {})})
    f, b = Phone(farmer, g), Phone(buyer, g)
    f.say("carrot 100kg ready tomorrow Nuwara Eliya", P(role="farmer", items={"carrot": 100}, loc="Nuwara Eliya", when=TOMORROW, name="Sunil"))
    f.say("yes")
    b.say("need carrot 100kg", P(items={"carrot": 100}, loc="Colombo", when=TOMORROW + timedelta(days=1), name="Lotus Kitchen"))
    b.say("yes")
    f.say("yes")
    assert "Confirmed by both sides" in b.say("yes")
    return f, b, next(m for m in store.matches() if m.status == "confirmed")


def test_seller_gets_slip_with_address_and_code(g):
    f, b, m = _deal(g, address="No. 7, Flower Road, Colombo 07")
    slip = next(x for x in f.inbox() if "Dispatch slip" in x)
    assert dispatch.code(m) in slip and "No. 7, Flower Road, Colombo 07" in slip and "0771200002" in slip
    assert "Hand over at:" in slip and "COST" in slip
    assert any(dispatch.code(m) in x for x in b.inbox())
    assert dispatch.find(dispatch.code(m).lower()).id == m.id


def test_slip_falls_back_to_the_town_and_follows_the_seller_language(g):
    store.DB.put("users", "94771200003", {"phone": "94771200003", "name": "Sunil", "role": "farmer", "lang": "si"})
    f, b, m = _deal(g, farmer="94771200003", buyer="94771200004")
    slip = next(x for x in f.inbox() if dispatch.code(m) in x and "📦" in x)
    assert "යැවීමේ පත්‍රිකාව" in slip and "Lotus Kitchen, Colombo" in slip
