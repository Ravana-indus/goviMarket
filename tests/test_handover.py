"""After the dispatch slip: the seller says DROPPED (or YES), the buyer says RECEIVED, the shipment moves."""
from app import convo, dispatch, store
from tests.test_conversations import g  # noqa: F401
from tests.test_dispatch import _deal


def test_free_text_drop_then_received(g):
    f, b, m = _deal(g, farmer="94771500001", buyer="94771500002")
    slip = next(x for x in f.inbox() if "Dispatch slip" in x)
    assert "reply DROPPED" in slip
    r = f.say("both shippment droped in train")
    assert "handed over" in r and dispatch.code(m) in r and "COST" in r
    assert any("has handed over your" in x for x in b.inbox())
    assert next(x for x in store.shipments() if m.id in x.match_ids).status == "loaded"
    r = b.say("RECEIVED")
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
