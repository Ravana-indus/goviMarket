"""Replies stay in the sender's language, ask at most one question, and remember a half-finished message."""
from datetime import date

import pytest

from app import main, parser, store
from app.schemas import ParsedMessage

TODAY = date(2026, 10, 10)


def _p(**kw):
    base = dict(role="buyer", language="ta", sender_name=None, location="Colombo", when=None, items=[],
                unclear=[], confidence=0.9, summary_in_sender_language="சரி.", question_in_sender_language=None)
    return ParsedMessage(**{**base, **kw})


@pytest.fixture
def fake(monkeypatch):
    store.reset()
    calls = []

    def install(*results):
        queue = list(results)

        def parse(*, text=None, media=None, mime_type=None, today, client=None, context=None):
            calls.append({"text": text, "context": context})
            return queue.pop(0)
        monkeypatch.setattr(parser, "parse", parse)
        return calls
    yield install
    store.reset()


def test_internal_notes_never_reach_the_sender(fake):
    fake(_p(items=[{"crop": "red onion", "qty_kg": 20, "grade": None, "price_lkr_per_kg": None, "price_kind": None}],
            when=date(2026, 10, 12), unclear=["Role unclear", "Exact date not specified"],
            question_in_sender_language="நீங்கள் வாங்குபவரா?"))
    out = main.handle(text="அடுத்த வாரத்திற்கு 20 கிலோ வெங்காயம்", media=None, mime_type=None,
                      sender="94771234567", today=TODAY, auto_plan=False)
    assert "unclear" not in out["reply"] and "Role" not in out["reply"]
    assert "?" not in out["reply"]  # complete order: nothing to ask
    assert out["created"] and not out["needs_clarification"]


def test_half_finished_message_is_held_then_completed(fake):
    item = {"crop": "carrot", "qty_kg": 200, "grade": None, "price_lkr_per_kg": None, "price_kind": None}
    calls = fake(_p(role="farmer", language="si", location=None, items=[item],
                    question_in_sender_language="ඔබ කුමන නගරයේ ද?"),
                 _p(role="farmer", language="si", location="Dambulla", items=[item]))
    first = main.handle(text="කැරට් කිලෝ 200", media=None, mime_type=None, sender="94771111111",
                        today=TODAY, auto_plan=False)
    assert first["created"] == [] and first["reply"].endswith("ඔබ කුමන නගරයේ ද?")
    assert any(d["phone"] == "94771111111" for d in store.DB.all("drafts"))

    second = main.handle(text="දඹුල්ල", media=None, mime_type=None, sender="94771111111",
                         today=TODAY, auto_plan=False)
    assert "Unfinished earlier message" in calls[1]["context"]
    assert second["created"] and not store.DB.all("drafts")
    assert store.listings()[0].location == "Dambulla"


def test_role_comes_from_the_numbers_history(fake):
    item = {"crop": "beans", "qty_kg": 40, "grade": None, "price_lkr_per_kg": None, "price_kind": None}
    calls = fake(_p(items=[item]), _p(items=[item]))
    main.handle(text="beans 40kg", media=None, mime_type=None, sender="94772222222", today=TODAY, auto_plan=False)
    main.handle(text="beans 40kg again", media=None, mime_type=None, sender="94772222222", today=TODAY, auto_plan=False)
    assert calls[0]["context"] is None
    assert "belongs to a buyer" in calls[1]["context"]
