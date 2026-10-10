"""Scripted WhatsApp conversations, start to finish, through the same pipeline as the webhook.

Each `say` gives what Gemini would return for that message (or nothing, which asserts Gemini is
never asked: YES, NO, STATUS, "hi" and bare numbers must not cost a call or depend on the model).
"""
import re
from datetime import date, datetime, timedelta, timezone

import pytest

from app import convo, main, parser, store
from app.schemas import Item, ParsedMessage

TODAY = date(2026, 10, 10)  # a Saturday
TOMORROW = TODAY + timedelta(days=1)


def P(role="buyer", lang="en", items=None, loc=None, when=None, intent="order", conf=0.9, name=None):
    return ParsedMessage(
        intent=intent, role=role, language=lang, sender_name=name, location=loc, when=when,
        items=[Item(crop=c, qty_kg=kg, grade=None, price_lkr_per_kg=None, price_kind=None)
               for c, kg in (items or {}).items()],
        unclear=[], confidence=conf, summary_in_sender_language="(Gemini's summary is never shown in chat)")


class Phone:
    """One simulated WhatsApp number."""

    def __init__(self, number, gemini):
        self.number, self.gemini = number, gemini

    def say(self, text=None, parse=None, *, media=None, mime=None, via="sim"):
        self.gemini.queue.append(parse)
        before = len(self.gemini.calls)
        out = main.handle(text=text, media=media, mime_type=mime, sender=self.number, today=TODAY, via=via)
        if parse is None:
            assert len(self.gemini.calls) == before, f"Gemini should not be asked to read {text!r}"
            self.gemini.queue.pop()
        else:
            assert len(self.gemini.calls) == before + 1, f"Gemini was not asked to read {text!r}"
        self.last = out
        return out["reply"]

    @property
    def state(self):
        return convo.load(self.number)["state"]

    def orders(self):
        return [o for o in store.orders() if o.phone == self.number]

    def listings(self):
        return [l for l in store.listings() if l.phone == self.number]

    def inbox(self):
        """Everything sent to this number by the matcher (offers, confirmations)."""
        return [o["body"] for o in store.sent() if o["to"] == self.number]


class FakeGemini:
    def __init__(self):
        self.queue, self.calls = [], []

    def parse(self, *, text=None, media=None, mime_type=None, today, client=None, context=None):
        self.calls.append({"text": text, "context": context, "media": media})
        nxt = self.queue.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return parser.normalise(nxt.model_copy(deep=True))


@pytest.fixture
def g(monkeypatch):
    store.reset()
    fake = FakeGemini()
    monkeypatch.setattr(parser, "parse", fake.parse)
    monkeypatch.setattr(convo, "_gemini", lambda: True)
    yield fake
    store.reset()


@pytest.fixture
def clock(monkeypatch):
    now = {"t": datetime(2026, 10, 10, 3, 0, tzinfo=timezone.utc)}
    monkeypatch.setattr(convo, "_now", lambda: now["t"])
    return now


TA_ORDER = "நாளைக்கு 5 கிலோ வெங்காயம், 10 கிலோ தக்காளி, 2 கிலோ கேரட், 5 கிலோ லீக்ஸ் மற்றும் 2 கிலோ கோவா தேவை"
TA_PARSE = P(lang="ta", when=TOMORROW, items={"big onion": 5, "tomato": 10, "carrot": 2, "leeks": 5, "cabbage": 2})


# ------------------------------------------------------------- the bug Patu hit

def test_tamil_order_then_yes_places_every_item(g):
    """Patu's chat: a 5-item Tamil order, then YES. It used to answer "no order items were specified"."""
    shop = Phone("94771000001", g)
    r = shop.say(TA_ORDER, TA_PARSE)
    assert shop.state == "confirming" and shop.orders() == []
    for word in ("வெங்காயம்", "தக்காளி", "கேரட்", "லீக்ஸ்", "கோவா", "YES", "ஞாயிறு 11/10", "கொழும்பு"):
        assert word in r, word
    assert "registered" not in r and "பதிவு செய்யப்பட்டுள்ளது" not in r  # nothing claims it is placed yet

    r = shop.say("YES")  # Latin YES from a Tamil speaker: no Gemini call, reply stays Tamil
    assert r.startswith("ஆர்டர் பதிவு செய்யப்பட்டது ✅")
    assert sorted((o.crop, o.qty_kg) for o in shop.orders()) == [
        ("big onion", 5), ("cabbage", 2), ("carrot", 2), ("leeks", 5), ("tomato", 10)]
    assert {o.needed_by for o in shop.orders()} == {TOMORROW} and shop.state == "idle"


def test_second_yes_does_not_order_twice(g):
    shop = Phone("94771000002", g)
    shop.say(TA_ORDER, TA_PARSE)
    shop.say("YES")
    r = shop.say("YES")
    assert "ஏற்கனவே முடிந்தது" in r and len(shop.orders()) == 5
    r = shop.say("ok")
    assert len(shop.orders()) == 5 and "YES" in r


# ------------------------------------------------------------- confirm, cancel, correct

def test_no_cancels_and_nothing_is_stored(g):
    shop = Phone("94771000003", g)
    shop.say("need tomato 10kg tomorrow", P(items={"tomato": 10}, when=TOMORROW))
    assert shop.say("NO") == "Cancelled. Nothing was placed."
    assert shop.orders() == [] and shop.state == "idle"
    assert shop.say("no").startswith("Nothing is waiting for your answer")


def test_corrections_edit_the_pending_order(g):
    shop = Phone("94771000004", g)
    shop.say("need tomato 10kg and carrot 5kg", P(items={"tomato": 10, "carrot": 5}))
    r = shop.say("make tomato 15kg", P(intent="edit", items={"tomato": 15}))
    assert "Tomato 15 kg" in r and "Carrot 5 kg" in r and shop.state == "confirming"
    r = shop.say("remove carrot", P(intent="edit", items={"carrot": 0}))
    assert "Carrot" not in r and "Tomato 15 kg" in r
    r = shop.say("deliver to Kandy on Friday", P(intent="edit", loc="Kandy", when=date(2026, 10, 16)))
    assert "Fri 16/10" in r and "Kandy" in r and "Tomato 15 kg" in r
    shop.say("yes")
    [o] = shop.orders()
    assert (o.crop, o.qty_kg, o.location, o.needed_by) == ("tomato", 15, "Kandy", date(2026, 10, 16))


def test_corrections_work_without_gemini(monkeypatch):
    """The keyword parser (no key, or Gemini down) still handles the same edits."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    store.reset()
    say = lambda t: main.handle(text=t, media=None, mime_type=None, sender="94771000005", today=TODAY, via="sim")["reply"]
    r = say("need tomato 10kg and carrot 5kg tomorrow")
    assert "Tomato 10 kg" in r and "Carrot 5 kg" in r
    r = say("make tomato 15kg")
    assert "Tomato 15 kg" in r and "Carrot 5 kg" in r
    r = say("remove carrot, add 3kg beans")
    assert "Carrot" not in r and "Beans 3 kg" in r
    say("ok")
    assert sorted((o.crop, o.qty_kg) for o in store.orders()) == [("beans", 3), ("tomato", 15)]


def test_tamil_order_works_without_gemini(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    store.reset()
    r = main.handle(text=TA_ORDER, media=None, mime_type=None, sender="94771000006", today=TODAY, via="sim")["reply"]
    assert "கோவா" in r and "YES" in r
    main.handle(text="ஆம்", media=None, mime_type=None, sender="94771000006", today=TODAY, via="sim")
    assert len(store.orders()) == 5


def test_a_separate_new_order_replaces_the_unplaced_one(g):
    shop = Phone("94771000007", g)
    shop.say("need beans 20kg", P(items={"beans": 20}))
    r = shop.say("sorry, actually I need leeks 8kg on Friday",
                 P(items={"leeks": 8}, when=date(2026, 10, 16)))
    assert "replaces your earlier order" in r and "Beans" not in r
    shop.say("YES")
    assert [(o.crop, o.qty_kg) for o in shop.orders()] == [("leeks", 8)]


def test_a_second_message_adds_to_the_pending_order(g):
    shop = Phone("94771000008", g)
    shop.say("need tomato 10kg", P(items={"tomato": 10}))
    r = shop.say("and 4kg green chilli", P(intent="edit", items={"green chilli": 4}))
    assert "Tomato 10 kg" in r and "Green chilli 4 kg" in r


# ------------------------------------------------------------- missing facts, one question at a time

def test_sinhala_farmer_is_asked_only_for_the_town(g):
    sunil = Phone("94771000009", g)
    r = sunil.say("කැරට් කිලෝ 200 හෙට", P(role="farmer", lang="si", items={"carrot": 200}, when=TOMORROW))
    assert r.endswith("ඔබ කුමන නගරයේ සිට එවනවාද?") and sunil.state == "asking"
    assert r.count("?") == 1
    ctx = g.calls[-1]["context"]
    r = sunil.say("දඹුල්ල", P(role="unknown", lang="si", intent="edit", loc="Dambulla"))
    assert "Pending order" in g.calls[-1]["context"] and ctx is None
    assert "කිලෝවට රු." in r and "දඹුල්ල" in r
    assert sunil.state == "confirming"
    sunil.say("ඔව්")
    [l] = sunil.listings()
    assert (l.crop, l.qty_kg, l.location, l.ready_on) == ("carrot", 200, "Dambulla", TOMORROW)


def test_yes_before_answering_repeats_the_question(g):
    sunil = Phone("94771000010", g)
    sunil.say("carrot 200kg", P(role="farmer", items={"carrot": 200}))
    r = sunil.say("YES")
    assert r == "First I need one thing: Which town are you sending it from?"
    assert sunil.listings() == [] and sunil.state == "asking"


def test_missing_quantity_is_answered_with_a_bare_number(g):
    shop = Phone("94771000011", g)
    r = shop.say("need some beans", P(items={"beans": 0}))
    assert r.endswith("How many kg of beans?")
    r = shop.say("20")  # no Gemini call needed
    assert "Beans 20 kg" in r and shop.state == "confirming"


def test_absurd_quantity_is_asked_again(g):
    shop = Phone("94771000012", g)
    assert shop.say("tomato 50000kg", P(items={"tomato": 50000})).endswith("How many kg of tomato?")


def test_role_is_asked_once_then_town(g):
    new = Phone("94771000013", g)
    r = new.say("tomato 100kg", P(role="unknown", items={"tomato": 100}))
    assert r.endswith("Are you selling this, or buying it?")
    r = new.say("selling")
    assert r.endswith("Which town are you sending it from?")


def test_role_comes_from_the_account(g):
    from app import accounts
    accounts.link("94771000014", name="Lotus Kitchen", role="buyer", via="web")
    shop = Phone("94771000014", g)
    shop.say("tomato 30kg", P(role="unknown", items={"tomato": 30}))
    assert "belongs to a buyer" in g.calls[-1]["context"] and shop.state == "confirming"
    shop.say("yes")
    assert shop.orders()[0].buyer == "Lotus Kitchen"


# ------------------------------------------------------------- crops we do not trade

def test_unknown_crops_are_left_out_and_said_so(g):
    shop = Phone("94771000015", g)
    r = shop.say("need durian 5kg and tomato 2kg", P(items={"durian": 5, "tomato": 2}))
    assert "Not on Govi yet, so left out: durian" in r and "Tomato 2 kg" in r
    r = Phone("94771000016", g).say("need durian 5kg", P(items={"durian": 5}))
    assert r.startswith("We don't trade durian yet")
    assert convo.load("94771000016")["state"] == "idle"


# ------------------------------------------------------------- photos and voice notes

def test_photo_order_then_voice_yes(g):
    shop = Phone("94771000017", g)
    r = shop.say(None, P(lang="si", items={"beans": 12, "leeks": 4}), media=b"\xff\xd8", mime="image/jpeg")
    assert "බෝංචි කිලෝ 12" in r and shop.state == "confirming"
    r = shop.say(None, P(lang="si", intent="confirm"), media=b"RIFF", mime="audio/wav")  # "ow, eka hari"
    assert r.startswith("ඇණවුම දැම්මා ✅") and len(shop.orders()) == 2


def test_unreadable_photo_keeps_the_pending_order(g):
    shop = Phone("94771000018", g)
    shop.say(TA_ORDER, TA_PARSE)
    r = shop.say(None, RuntimeError("500 INTERNAL"), media=b"\xff\xd8", mime="image/jpeg")
    assert r.startswith("மன்னிக்கவும், அந்தப் புகைப்படத்தைப் படிக்க முடியவில்லை")
    assert shop.state == "confirming"
    shop.say("YES")
    assert len(shop.orders()) == 5


def test_blank_photo_gets_a_photo_specific_answer(g):
    shop = Phone("94771000019", g)
    r = shop.say(None, P(role="unknown", items={}, conf=0.1), media=b"\xff\xd8", mime="image/jpeg")
    assert "could not read that photo" in r and shop.state == "idle"


def test_voice_note_in_singlish_sets_the_language(g):
    sunil = Phone("94771000020", g)
    r = sunil.say(None, P(role="farmer", lang="si", items={"tomato": 80}, loc="Dambulla"), media=b"RIFF", mime="audio/wav")
    assert "තක්කාලි කිලෝ 80" in r
    assert sunil.say("ok").startswith("ඔබේ අස්වැන්න විකිණීමට දැම්මා")


# ------------------------------------------------------------- time

def test_pending_order_expires_unplaced(g, clock):
    shop = Phone("94771000021", g)
    shop.say("need tomato 10kg", P(items={"tomato": 10}))
    clock["t"] += timedelta(hours=convo.PENDING_HOURS + 1)
    r = shop.say("YES")
    assert "was not placed" in r and shop.orders() == []
    assert shop.say("YES").startswith("Nothing is waiting")


def test_yes_long_after_placing_is_not_already_done(g, clock):
    shop = Phone("94771000022", g)
    shop.say("need tomato 10kg", P(items={"tomato": 10}))
    shop.say("YES")
    clock["t"] += timedelta(days=2)
    assert shop.say("YES").startswith("Nothing is waiting")


# ------------------------------------------------------------- small talk and status

def test_greetings_and_thanks_never_start_an_order(g):
    shop = Phone("94771000023", g)
    assert shop.say("hi").startswith("Hello from Govi")
    assert shop.say("வணக்கம்").startswith("Govi-யிலிருந்து வணக்கம்")
    assert shop.state == "idle"
    shop.say("need tomato 10kg", P(items={"tomato": 10}))
    r = shop.say("thanks")
    assert "still waiting for your YES" in r and "Tomato 10 kg" in r and shop.state == "confirming"


def test_chit_chat_goes_to_help_not_a_question(g):
    shop = Phone("94771000024", g)
    r = shop.say("how are you today?", P(role="unknown", intent="chat"))
    assert r.startswith("Hello from Govi") and shop.state == "idle"


def test_status_lists_what_is_open(g):
    shop = Phone("94771000025", g)
    assert shop.say("status") == "You have nothing open with Govi right now."
    shop.say("need tomato 10kg", P(items={"tomato": 10}))
    assert "not placed yet" in shop.say("STATUS")
    shop.say("yes")
    r = shop.say("my orders")
    assert "tomato 10 kg" in r and "looking for a farmer" in r


# ------------------------------------------------------------- YES goes to the newest question

def _farmer_with_carrot(g):
    sunil = Phone("94771000030", g)
    sunil.say("carrot 300kg", P(role="farmer", items={"carrot": 300}, loc="Nuwara Eliya", when=TOMORROW), via="web")
    assert len(sunil.listings()) == 1
    return sunil


def test_buyer_yes_places_then_second_yes_accepts_the_match(g):
    sunil = _farmer_with_carrot(g)
    shop = Phone("94771000031", g)
    shop.say("need carrot 100kg on Tuesday", P(items={"carrot": 100}, when=date(2026, 10, 13)))
    r = shop.say("YES")
    assert r.startswith("Order placed ✅")
    offers = shop.inbox()
    assert offers and "Reply YES" in offers[-1]  # the matcher offered Sunil's carrot
    r = shop.say("YES")
    assert r.startswith("Thanks. Waiting for the other side")
    assert sunil.say("YES").startswith("Confirmed by both sides")
    assert [m.status for m in store.matches()] == ["confirmed"]


def test_offers_come_after_the_placed_reply_in_the_chat(g):
    _farmer_with_carrot(g)
    shop = Phone("94771000032", g)
    shop.say("need carrot 100kg on Tuesday", P(items={"carrot": 100}, when=date(2026, 10, 13)))
    shop.say("YES")
    from fastapi.testclient import TestClient
    thread = TestClient(main.app).get("/api/sim/thread", params={"phone": shop.number}).json()
    texts = [m["text"] for m in thread if m["dir"] == "out"]
    assert texts[-2].startswith("Order placed") and "Reply YES" in texts[-1]


def test_new_order_after_an_offer_takes_the_next_yes(g):
    _farmer_with_carrot(g)
    shop = Phone("94771000033", g)
    shop.say("need carrot 100kg on Tuesday", P(items={"carrot": 100}, when=date(2026, 10, 13)))
    shop.say("YES")  # placed; an offer for Sunil's carrot is now waiting
    shop.say("also need beans 10kg", P(items={"beans": 10}))  # newer: the beans order waits for YES
    assert shop.say("YES").startswith("Order placed")
    assert {o.crop for o in shop.orders()} == {"carrot", "beans"}
    assert shop.say("YES").startswith("Thanks. Waiting for the other side")  # now the offer


def test_one_yes_answers_several_offers_sent_together(g):
    Phone("94771000034", g).say("x", P(role="farmer", items={"carrot": 300}, loc="Nuwara Eliya", when=TOMORROW), via="web")
    Phone("94771000035", g).say("x", P(role="farmer", items={"leeks": 300}, loc="Nuwara Eliya", when=TOMORROW), via="web")
    shop = Phone("94771000036", g)
    shop.say("need carrot 50kg and leeks 40kg", P(items={"carrot": 50, "leeks": 40}, when=date(2026, 10, 13)))
    shop.say("YES")
    offers = [b for b in shop.inbox() if "YES" in b]
    assert len(offers) == 1 and "accept all 2" in offers[0]
    r = shop.say("YES")
    assert r.count("Waiting for the other side") == 2


def test_no_to_an_offer_declines_it(g):
    _farmer_with_carrot(g)
    shop = Phone("94771000037", g)
    shop.say("need carrot 100kg on Tuesday", P(items={"carrot": 100}, when=date(2026, 10, 13)))
    shop.say("YES")
    assert shop.say("NO").startswith("Declined: 100 kg carrot")
    assert len(shop.orders()) == 1  # the order stays open; only that offer is off


def test_cancel_right_after_placing_withdraws_and_tells_the_farmer(g):
    sunil = _farmer_with_carrot(g)
    shop = Phone("94771000038", g)
    shop.say("need carrot 100kg on Tuesday", P(items={"carrot": 100}, when=date(2026, 10, 13)))
    shop.say("YES")
    r = shop.say("cancel")
    assert r.startswith("Cancelled ref") and shop.orders() == []
    assert "withdrew" in sunil.inbox()[-1]
    assert all(m.status == "cancelled" for m in store.matches())


def test_cancel_after_the_deal_is_agreed_is_refused(g):
    sunil = _farmer_with_carrot(g)
    shop = Phone("94771000039", g)
    shop.say("need carrot 100kg on Tuesday", P(items={"carrot": 100}, when=date(2026, 10, 13)))
    shop.say("YES")
    shop.say("YES")
    sunil.say("YES")
    assert "cannot be cancelled" in shop.say("cancel") and len(shop.orders()) == 1


# ------------------------------------------------------------- other channels

def test_web_form_places_at_once(g):
    sunil = Phone("94771000040", g)
    r = sunil.say("[harvest] carrot 100kg", P(role="farmer", items={"carrot": 100}, loc="Dambulla"), via="web")
    assert r.startswith("Your harvest is up for sale ✅") and len(sunil.listings()) == 1


def test_price_agents_report_without_a_yes(g):
    from app.schemas import Item
    kamal = Phone("94771000041", g)
    p = P(role="reporter", loc="Dambulla", items={})
    p.items = [Item(crop="carrot", qty_kg=0, grade=None, price_lkr_per_kg=150, price_kind="collector")]
    kamal.say("Dambulla carrot collector 150", p)
    assert store.prices()["carrot"]["collector"] == 150


def test_whatsapp_reaction_thumbs_up_is_a_yes():
    from app import whatsapp
    msgs = whatsapp.unpack({"entry": [{"changes": [{"value": {"messages": [
        {"from": "9477", "id": "w1", "type": "reaction", "reaction": {"message_id": "x", "emoji": "👍"}},
        {"from": "9477", "id": "w2", "type": "sticker", "sticker": {"id": "s"}}]}}]}]})
    assert msgs[0].text == "👍" and msgs[1].text is None and msgs[1].media_id is None


def test_small_talk_while_an_order_waits_shows_it_again(g):
    shop = Phone("94771000042", g)
    shop.say("need tomato 10kg", P(items={"tomato": 10}))
    r = shop.say("wait, let me check with the chef", P(role="unknown", intent="chat"))
    assert r.startswith("This is still waiting for your YES") and "Tomato 10 kg" in r
    assert shop.state == "confirming"


def test_after_an_expiry_the_next_order_says_it_is_new(g, clock):
    shop = Phone("94771000043", g)
    shop.say("need tomato 10kg", P(items={"tomato": 10}))
    clock["t"] += timedelta(hours=convo.PENDING_HOURS + 1)
    r = shop.say("need beans 5kg", P(items={"beans": 5}))
    assert "was not placed. This is a new one" in r and "Tomato" not in r


def test_unsold_offer_numbers_still_work_while_an_order_waits(g, monkeypatch):
    from app import surplus
    monkeypatch.setattr(surplus, "answer", lambda phone, w: f"Done: option {w}")
    shop = Phone("94771000044", g)
    shop.say("carrot 100kg", P(role="farmer", items={"carrot": 100}, loc="Dambulla"))
    assert shop.say("2") == "Done: option 2" and shop.state == "confirming"


def test_a_tamil_speaker_typing_an_english_edit_keeps_tamil(g):
    shop = Phone("94771000045", g)
    shop.say(TA_ORDER, TA_PARSE)
    r = shop.say("tomato 15kg", P(lang="en", intent="edit", items={"tomato": 15}))
    assert "தக்காளி 15 கிலோ" in r


def test_the_role_answer_is_remembered_on_the_account(g):
    from app import accounts
    new = Phone("94771000046", g)
    new.say("tomato 100kg", P(role="unknown", items={"tomato": 100}))
    new.say("buying")
    new.say("YES")
    assert accounts.user(new.number)["role"] == "buyer"


def test_small_lots_share_one_transport_cost_and_never_go_negative(g):
    """Patu's Jaffna test: tomato 10 kg was quoted alone (Rs 220/kg transport) and came out at Rs -41/kg."""
    from app import accounts
    rasan = Phone("94771000047", g)
    r = rasan.say("x", P(role="farmer", lang="ta", when=TOMORROW, loc="Jaffna",
                         items={"tomato": 10, "carrot": 50, "leeks": 30, "cabbage": 18}))
    assert "-" not in "".join(re.findall(r"ரூ\. ?-?[\d,]+", r))
    assert "மொத்த 108 கிலோவும் சேர்ந்து" in r  # one transport cost for the whole load
    assert r.count("அயலவர்களுடன்") == 1  # the pooling tip once, not per item
    assert "யாழ்ப்பாணம்" in r and "Jaffna" not in r
    assert "உங்களுக்கு மொத்தம் சுமார் ரூ." in r
    assert len(r.splitlines()) <= 9
    done = rasan.say("YES")
    assert "உங்களுக்கு மொத்தம்" in done and "STATUS" in done


def test_an_item_worth_less_than_the_collector_price_says_so(g):
    from app.schemas import Item
    tiny = Phone("94771000048", g)
    r = tiny.say("x", P(role="farmer", loc="Jaffna", items={"cabbage": 2}))
    assert "better sold locally" in r and "You get about" not in r
