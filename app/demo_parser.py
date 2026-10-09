"""Keyword parser used only when no GEMINI_API_KEY is set, so the app runs offline for previews.

It understands simple English text like "carrot 200kg ready Thursday, Nuwara Eliya".
Photos and voice notes need the real Gemini parser."""
from __future__ import annotations

import re
from datetime import date, timedelta

from .schemas import Item, ParsedMessage

CROPS = ["carrot", "leeks", "beans", "tomato"]
PLACES = ["Nuwara Eliya", "Dambulla", "Jaffna", "Badulla", "Colombo"]
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def parse(*, text: str | None, media: bytes | None, today: str) -> ParsedMessage:
    t = (text or "").lower()
    base = date.fromisoformat(today)
    if media and not t:
        return ParsedMessage(role="unknown", language="en", sender_name=None, location=None, when=None,
                             items=[], unclear=["photos and voice notes need a Gemini key"],
                             confidence=0, summary_in_sender_language="Demo mode: add GEMINI_API_KEY to read photos and voice.")
    role = "reporter" if "price" in t or "rs" in t.split() else "buyer" if any(w in t for w in ("order", "need", "want")) else "farmer"
    items = []
    for crop in CROPS:
        m = re.search(crop + r"s?\D{0,12}?(\d+(?:\.\d+)?)\s*(kg|rs)?", t)
        if not m:
            continue
        n = float(m.group(1))
        if role == "reporter":
            kind = "collector" if "collector" in t or "farm gate" in t else "retail" if "retail" in t else "wholesale"
            items.append(Item(crop=crop, qty_kg=0, grade=None, price_lkr_per_kg=n, price_kind=kind))
        else:
            items.append(Item(crop=crop, qty_kg=n, grade=None, price_lkr_per_kg=None, price_kind=None))
    when = None
    if "tomorrow" in t:
        when = base + timedelta(days=1)
    for i, d in enumerate(DAYS):
        if d in t:
            when = base + timedelta(days=(i - base.weekday()) % 7 or 7)
    place = next((p for p in PLACES if p.lower() in t), None)
    name = re.search(r"(?:from|this is|i am)\s+([a-z][a-z ]{1,30}?)(?:[,.:]|$)", t)
    what = ", ".join(f"{i.crop} {int(i.qty_kg)}kg" if role != "reporter" else f"{i.crop} Rs {int(i.price_lkr_per_kg)}" for i in items)
    return ParsedMessage(
        role=role if items else "unknown", language="en",
        sender_name=name.group(1).strip().title() if name else None,
        location=place, when=when, items=items,
        unclear=[] if items else ["no crop or quantity found"],
        confidence=0.75 if items else 0.2,
        summary_in_sender_language=f"Got it: {role} - {what}." if items else "Sorry, I could not find a crop and quantity.",
    )
