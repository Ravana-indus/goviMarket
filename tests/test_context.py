"""The chat remembers what it just asked: a short reply is read as the answer to Govi's last line."""
from app import convo, store
from tests.test_conversations import P, g  # noqa: F401
from tests.test_dispatch import _deal


def _dropped(g, n, lang=None):
    f, b, m = _deal(g, farmer=f"9477170{n:04d}", buyer=f"9477171{n:04d}")
    if lang:
        store.DB.put("convo", f.number, {**convo.load(f.number), "lang": lang})
    assert "COST" in f.say("dropped")
    return f, b, m


def _cost(m):
    return next(x for x in store.matches() if x.id == m.id).shipping_paid_lkr


def test_bare_amount_after_the_cost_question_is_the_cost(g):
    """Patu's chat, Oct 18: 'send the amount you paid as COST', then '2000' got 'which crop and how many kg?'."""
    f, b, m = _dropped(g, 1)
    r = f.say("2000")  # answered without asking Gemini
    assert "Recorded Rs 2,000" in r and "kg?" not in r and _cost(m) == 2000


def test_bare_amount_in_tamil_chat(g):
    f, b, m = _dropped(g, 2, lang="ta")
    assert "ரூ. 2,000" in f.say("2000") and _cost(m) == 2000


def test_amount_with_rupees(g):
    f, b, m = _dropped(g, 3)
    assert "Recorded Rs 1,500" in f.say("Rs 1,500")


def test_gemini_reads_a_worded_cost_with_the_chat_as_context(g):
    f, b, m = _dropped(g, 4)
    p = P(role="farmer", intent="cost")
    p.amount_lkr = 1800
    r = f.say("1800 koduthen bus ku", p)
    assert "Recorded Rs 1,800" in r and _cost(m) == 1800
    ctx = g.calls[-1]["context"]
    assert "Recent chat" in ctx and "Now reply COST" in ctx and "Sender: 1800 koduthen bus ku" in ctx
    assert "reply COST with the rupees" in ctx


def test_small_numbers_are_not_a_cost(g):
    f, b, m = _dropped(g, 5)
    f.say("2", P(role="farmer", intent="chat"))
    assert _cost(m) is None


def test_no_cost_owed_means_a_number_is_not_taken_as_one(g):
    f, b, m = _deal(g, farmer="94771700006", buyer="94771710006")
    f.say("2000", P(role="farmer", intent="chat"))  # not handed over yet: Gemini reads it
    assert _cost(m) is None


def test_offers_and_slips_sent_by_the_matcher_are_in_the_chat_context(g):
    f, b, m = _deal(g, farmer="94771700007", buyer="94771710007")
    assert any(x["who"] == "govi" and "Dispatch slip" in x["text"] for x in convo.recent(f.number))


def test_yes_to_the_handover_question_hands_it_over(g):
    f, b, m = _deal(g, farmer="94771700008", buyer="94771710008")
    assert "Have you handed over" in f.say("enna aachu", P(role="farmer", intent="chat"))
    assert "handed over" in f.say("yes")
