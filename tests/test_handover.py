"""After the dispatch slip: the seller says DROPPED (or YES), the buyer says RECEIVED, the shipment moves."""
from app import convo, demo_parser, dispatch, store
from tests.test_conversations import P, TOMORROW, g  # noqa: F401
from tests.test_dispatch import _deal


def test_free_text_drop_then_received(g):
    f, b, m = _deal(g, farmer="94771500001", buyer="94771500002")
    slip = next(x for x in f.inbox() if "Dispatch slip" in x)
    assert "reply DROPPED" in slip
    r = f.say("both shippment droped in train", P(role="farmer", intent="dropped"))
    assert "handed over" in r and dispatch.code(m) in r and "COST" in r
    assert any("has handed over your" in x for x in b.inbox())
    assert next(x for x in store.shipments() if m.id in x.match_ids).status == "loaded"
    r = b.say("RECEIVED")  # the button word: answered without asking Gemini
    assert "marked received" in r
    assert any("received your" in x for x in f.inbox())
    assert next(x for x in store.shipments() if m.id in x.match_ids).status == "delivered"


def test_yes_after_slip_means_dropped(g):
    f, b, m = _deal(g, farmer="94771500003", buyer="94771500004")
    assert "handed over" in f.say("YES")
    assert "handed over" not in f.say("YES")  # second YES: nothing left to hand over


def test_one_language_for_the_whole_chat(g):
    f, b, m = _deal(g, farmer="94771500005", buyer="94771500006")
    store.DB.put("convo", f.number, {**convo.load(f.number), "lang": "ta"})
    for kind in ("listings",):
        for doc in store.DB.all(kind):
            if doc.get("phone") == f.number:
                store.DB.put(kind, doc["id"], {**doc, "lang": "si"})
    from app import deals
    deals.advance_shipment(next(x for x in store.shipments() if m.id in x.match_ids).id)
    booked = f.inbox()[-1]
    assert "பதிவு செய்யப்பட்டது" in booked and any(w in booked for w in ("ரயில்", "இரவு பேருந்து", "லாரி", "தபால்"))
    assert "ஒப்படைக்கப்பட்டது" in f.say("dropped")


# ---------------------------------------------------------------- Patu's Telegram chat, Oct 18
# After the booking message the seller wrote Tanglish and got the generic hello, then the same words
# with the crop and kg were read as a brand-new harvest.



def _seller(g, n):
    f, b, m = _deal(g, farmer=f"9477160{n:04d}", buyer=f"9477161{n:04d}")
    return f, b, m


def _gemini_down(text):
    p = P(role="unknown", intent="chat")
    p.unclear = [demo_parser.FALLBACK]
    return p


def test_tanglish_handover_is_understood_when_gemini_fails(g):
    f, b, m = _seller(g, 1)
    r = f.say("koduthuten train ku", _gemini_down("koduthuten train ku"))
    assert "handed over" in r and dispatch.code(m) in r and "Hello" not in r
    assert any("has handed over your" in x for x in b.inbox())


def test_tamil_crop_and_kg_with_tanglish_handover_is_not_a_new_listing(g):
    f, b, m = _seller(g, 2)
    before = len(f.listings())
    r = f.say("கேரட் 100 கிலோவை koduthuten train ku", P(role="farmer", lang="ta", intent="dropped"))
    assert "ஒப்படைக்கப்பட்டது" in r and len(f.listings()) == before and f.state == "idle"


def test_gemini_reads_a_handover_the_keywords_miss(g):
    f, b, m = _seller(g, 3)
    r = f.say("anju manikku train la pottachu", P(role="farmer", lang="en", intent="dropped"))
    assert "handed over" in r
    assert "Waiting on this sender" in g.calls[-1]["context"] and dispatch.code(m) in g.calls[-1]["context"]


def test_load_named_again_gets_a_question_not_a_new_harvest(g):
    f, b, m = _seller(g, 4)
    before = len(f.listings())
    r = f.say("carrot 100 kg train la", P(role="farmer", items={"carrot": 100}))  # Gemini misread it as harvest
    assert "Have you handed over" in r and "DROPPED" in r and dispatch.code(m) in r
    assert len(f.listings()) == before and f.state == "idle" and not m.dropped_at


def test_unclear_message_with_a_load_waiting_asks_instead_of_hello(g):
    f, b, m = _seller(g, 5)
    r = f.say("enna aachu", P(role="farmer", intent="chat"))
    assert "Have you handed over" in r and "Hello" not in r


def test_new_prefix_still_lists_more_harvest(g):
    f, b, m = _seller(g, 6)
    r = f.say("NEW carrot 100kg ready tomorrow train", P(role="farmer", items={"carrot": 100}, loc="Nuwara Eliya"))
    assert "Please check your harvest" in r and f.state == "confirming"


def test_other_crop_is_a_normal_new_harvest(g):
    f, b, m = _seller(g, 7)
    r = f.say("tomato 50kg ready tomorrow", P(role="farmer", items={"tomato": 50}, loc="Nuwara Eliya"))
    assert "Please check your harvest" in r


def test_buyer_tanglish_received(g):
    f, b, m = _seller(g, 8)
    f.say("dropped")
    r = b.say("vanthuchu", P(intent="received"))
    assert "marked received" in r


def test_buyer_same_weekly_order_is_not_held_by_a_load_in_transit(g):
    f, b, m = _seller(g, 9)
    f.say("dropped")
    r = b.say("need carrot 100kg", P(items={"carrot": 100}, loc="Colombo", when=TOMORROW))
    assert "Please check your order" in r


def test_not_yet_dropped_is_not_a_handover(g):
    f, b, m = _seller(g, 10)
    r = f.say("I have not dropped it yet, train is late", P(role="farmer", intent="chat"))
    assert "Have you handed over" in r and not any("has handed over your" in x for x in b.inbox())


def test_keywords_alone_when_there_is_no_gemini_key(g, monkeypatch):
    f, b, m = _seller(g, 11)
    monkeypatch.setattr(convo, "_gemini", lambda: False)
    assert "handed over" in f.say("koduthuten train ku")
