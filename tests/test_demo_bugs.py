"""The four bugs the Oct 18 live run found (govi-plan/test-run.md): phone numbers shown as names,
bursts of shipment messages, a YES accepting an offer nobody saw, and "selling" cancelling a draft."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app import main, parser, store
from app.schemas import ParsedMessage

FARMER, BUYER = "940009911111", "940009922222"
TODAY = datetime.now(ZoneInfo("Asia/Colombo")).date()


@pytest.fixture
def chat():
    store.reset()

    def say(sender, text):
        return main.handle(text=text, media=None, mime_type=None, sender=sender, today=TODAY, via="sim")["reply"]
    yield say
    store.reset()


def inbox(phone, since=0):
    rows = [o["body"] for o in store.sent() if o["to"] == phone]
    return rows[since:]


def deal(say, buyer_yes="YES"):
    say(FARMER, "carrot 150kg ready tomorrow, Nuwara Eliya"); say(FARMER, "YES")
    say(BUYER, "need carrot 150kg on Wednesday, deliver to Colombo"); say(BUYER, "YES")
    return say(BUYER, buyer_yes)


def test_offers_slip_handover_and_track_never_show_the_other_sides_number(chat):
    deal(chat)
    chat(FARMER, "YES")
    chat(FARMER, "DROPPED")
    chat(BUYER, "RECEIVED")
    seen = {"farmer": "\n".join(inbox(FARMER)) + chat(FARMER, "TRACK"),
            "buyer": "\n".join(inbox(BUYER)) + chat(BUYER, "TRACK")}
    assert BUYER not in seen["farmer"].replace("· " + BUYER, "")  # only the delivery contact
    assert FARMER not in seen["buyer"] and "0" + FARMER[2:] not in seen["buyer"]
    assert "a farmer in Nuwara Eliya" in seen["buyer"] and "a buyer in Colombo" in seen["farmer"]
    code = next(x for x in store.matches() if x.status == "confirmed").id
    from app import tracking
    assert FARMER not in str(tracking.public(code)) and BUYER not in str(tracking.public(code))
    slip = next(m for m in inbox(FARMER) if "Dispatch slip" in m)
    assert slip.count(BUYER) == 1  # the buyer's phone once, as who to call on delivery


def test_a_known_name_is_used(chat):
    from app import accounts
    accounts.link(BUYER, name="Cinnamon Cafe", role="buyer", via="sim")
    deal(chat)
    assert any("Cinnamon Cafe" in m for m in inbox(FARMER))


def test_handover_and_receipt_send_one_message_per_side(chat):
    deal(chat)
    chat(FARMER, "YES")
    f, b = len(inbox(FARMER)), len(inbox(BUYER))
    reply = chat(FARMER, "DROPPED")
    assert "handed over" in reply
    assert inbox(FARMER, f) == []  # no "Booked: bring your carrot..." after it is handed over
    assert len(inbox(BUYER, b)) == 1 and "handed over" in inbox(BUYER, b)[0]
    f, b = len(inbox(FARMER)), len(inbox(BUYER))
    reply = chat(BUYER, "RECEIVED")
    assert "received" in reply and inbox(BUYER, b) == []
    assert len(inbox(FARMER, f)) == 1 and "will be paid" in inbox(FARMER, f)[0]
    assert next(x for x in store.shipments()).status == "delivered"


def test_confirming_sends_the_other_side_one_message(chat):
    deal(chat)
    b = len(inbox(BUYER))
    chat(FARMER, "YES")
    new = inbox(BUYER, b)
    assert len(new) == 1 and "Confirmed by both" in new[0] and "GV-" in new[0]


def test_yes_after_a_part_accept_takes_only_what_the_farmer_saw(chat):
    deal(chat, buyer_yes="YES 100kg")
    assert not any(re.search(r"\b50 kg", m) for m in inbox(BUYER) + inbox(FARMER))  # the rest is not re-offered to them
    reply = chat(FARMER, "YES")
    assert "100 kg" in reply and not re.search(r"\b50 kg", reply)
    assert [m.qty_kg for m in store.matches() if m.status == "confirmed"] == [100]


def test_bare_yes_to_offers_sent_one_by_one_lists_them_first(chat):
    from app import deals
    from app.schemas import Match
    store.put("listings", {"id": "L1", "phone": FARMER, "farmer": FARMER, "location": "Nuwara Eliya", "lang": "en"})
    store.put("orders", {"id": "O1", "phone": BUYER, "buyer": BUYER, "location": "Colombo", "lang": "en"})
    store.put("orders", {"id": "O2", "phone": "940009933333", "buyer": "Hotel", "location": "Colombo", "lang": "en"})
    for mid, oid in (("M1", "O1"), ("M2", "O2")):
        store.put_match(Match(id=mid, listing_id="L1", order_id=oid, farmer=FARMER, buyer="x", crop="carrot",
                              qty_kg=50, lane=None, transport_lkr_per_kg=0, farmer_gets_lkr_per_kg=120,
                              buyer_pays_lkr_per_kg=150, collector_pays_lkr_per_kg=100, market_retail_lkr_per_kg=180))
        store.outbox(FARMER, f"offer {mid}", mid)
    reply = deals.answer(FARMER, "YES")
    assert "1." in reply and "2." in reply and not any(m.farmer_ok for m in store.matches())
    deals.answer(FARMER, "YES")
    assert all(m.farmer_ok for m in store.matches())


def test_yes_never_accepts_an_offer_that_was_not_sent(chat):
    from app import deals
    from app.schemas import Match
    store.put("listings", {"id": "L1", "phone": FARMER, "farmer": "Sunil", "lang": "en"})
    store.put("orders", {"id": "O1", "phone": BUYER, "buyer": "Cafe", "lang": "en"})
    store.put_match(Match(id="M1", listing_id="L1", order_id="O1", farmer="Sunil", buyer="Cafe", crop="carrot",
                          qty_kg=50, lane=None, transport_lkr_per_kg=0, farmer_gets_lkr_per_kg=120,
                          buyer_pays_lkr_per_kg=150, collector_pays_lkr_per_kg=100, market_retail_lkr_per_kg=180))
    assert deals.answer(FARMER, "YES") is None
    assert not store.matches()[0].farmer_ok


def test_selling_flips_a_guessed_order_to_a_harvest(monkeypatch):
    store.reset()
    item = {"crop": "tomato", "qty_kg": 100, "grade": None, "price_lkr_per_kg": None, "price_kind": None}
    guessed = ParsedMessage(role="buyer", language="en", sender_name=None, location=None, when=None, items=[item],
                            unclear=[], confidence=0.9, summary_in_sender_language="ok", question_in_sender_language=None)
    monkeypatch.setattr(parser, "parse", lambda **kw: guessed.model_copy(deep=True))
    monkeypatch.setattr("app.convo._gemini", lambda: True)
    say = lambda t: main.handle(text=t, media=None, mime_type=None, sender="940009944444", today=TODAY, via="sim")["reply"]  # noqa: E731
    assert "check your order" in say("tomato 100kg tomorrow")
    r = say("selling")
    assert "Cancelled" not in r and "town" in r.lower()
    assert store.DB.one("convo", "940009944444")["state"] == "asking"
    store.reset()
