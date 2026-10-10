"""Keyword parser: used with no GEMINI_API_KEY, and as the fallback whenever a Gemini call fails.

It understands simple text like "carrot 200kg ready Thursday, Nuwara Eliya", "two kilo carrot",
typos like "onlon", and Sinhala or Tamil crop names. Photos and voice notes need Gemini.
Everything it returns carries FALLBACK in `unclear`, so the chat knows it was only a guess."""
from __future__ import annotations

import re
from datetime import date, timedelta

from . import vocab
from .schemas import Item, ParsedMessage

NUM = re.compile(r"(\d+(?:\.\d+)?)\s*(kgs|kg|kilos|kilo|rs)?")
BUY_WORDS = ("order", "need", "want", "buy", "ona", "oney", "thevai", "ඕන", "අවශ්‍ය", "ගන්න", "தேவை", "வேண்டும்", "வாங்க")
FALLBACK = "read by the keyword parser"
WORDS = {"half": "0.5", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
         "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "fifteen": "15", "twenty": "20",
         "thirty": "30", "forty": "40", "fifty": "50", "hundred": "100"}
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def parse(*, text: str | None, media: bytes | None, today: str) -> ParsedMessage:
    t = re.sub(r"\bcorn\b", "maize", (text or "").lower())
    t = re.sub(r"\b(" + "|".join(WORDS) + r")\b", lambda m: WORDS[m.group(1)], t)
    base = date.fromisoformat(today)
    if media and not t:
        return ParsedMessage(role="unknown", language="en", sender_name=None, location=None, when=None,
                             items=[], unclear=["photos and voice notes need a Gemini key"],
                             confidence=0, summary_in_sender_language="Demo mode: add GEMINI_API_KEY to read photos and voice.")
    role = "reporter" if "price" in t or "rs" in t.split() else "buyer" if any(w in t for w in BUY_WORDS) else "farmer"
    items = []
    # One item per comma, "and" or line: "10kg tomato, carrot 5kg" reads either way round.
    for seg in re.split(r",|;|\n|&|\+|\band\b|மற்றும்|සහ", t):
        crops = vocab.crops_in(seg)
        m = NUM.search(seg)
        if not crops and m and m.group(2) in ("kg", "kilo", "kilos") and role != "reporter":
            # "5 kg xyz": an item we cannot name. Keep it so the sender sees it, never drop it silently.
            rest = [w for w in re.findall(r"[^\W\d_]{3,}", NUM.sub(" ", seg)) if w not in BUY_WORDS and w not in vocab.NOT_CROPS]
            if rest:
                items.append(Item(crop=rest[0], qty_kg=float(m.group(1)), grade=None, price_lkr_per_kg=None, price_kind=None))
            continue
        if len(crops) != 1 or not m or any(i.crop in crops for i in items):
            continue
        crop, n = crops.pop(), float(m.group(1))
        if role == "reporter":
            kind = "collector" if "collector" in t or "farm gate" in t else "retail" if "retail" in t else "wholesale"
            items.append(Item(crop=crop, qty_kg=0, grade=None, price_lkr_per_kg=n, price_kind=kind))
        else:
            items.append(Item(crop=crop, qty_kg=n, grade=None, price_lkr_per_kg=None, price_kind=None))
    when = None
    if "today" in t or "අද" in t or "இன்று" in t:
        when = base
    if re.search(r"\b(day after tomorrow|anidda|nalai maru naal)\b", t) or "අනිද්දා" in t or "நாளை மறுநாள்" in t:
        when = base + timedelta(days=2)
    elif re.search(r"\b(tomorrow|heta|naalai|nalaikku)\b", t) or "හෙට" in t or "நாளை" in t:
        when = base + timedelta(days=1)
    for i, d in enumerate(DAYS):
        if d in t:
            when = base + timedelta(days=(i - base.weekday()) % 7 or 7)
    place = vocab.towns_in(t)
    name = re.search(r"(?:from|this is|i am)\s+([a-z][a-z ]{1,30}?)(?:[,.:]|$)", t)
    what = ", ".join(f"{i.crop} {int(i.qty_kg)}kg" if role != "reporter" else f"{i.crop} Rs {int(i.price_lkr_per_kg)}" for i in items)
    return ParsedMessage(
        role=role if items else "unknown", language=vocab.script(text) or "en",
        sender_name=name.group(1).strip().title() if name else None,
        location=place, when=when, items=items,
        unclear=[FALLBACK] + ([] if items else ["no crop or quantity found"]),
        confidence=0.75 if items else 0.2,
        summary_in_sender_language=f"Got it: {role} - {what}." if items else "Sorry, I could not find a crop and quantity.",
    )
