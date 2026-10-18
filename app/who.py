"""What one side of a deal calls the other: a name, never a phone number.

A chat user is never asked for a name, so a listing or order made from chat carries the sender's
number as its farmer or buyer. Messages show the person's or business's name when Govi knows
one (the listing or order, else the account), and otherwise a neutral label such as "a farmer in
Nuwara Eliya". The only number a message shows is a contact the other side needs, like the
buyer's delivery phone on the seller's dispatch slip."""
from __future__ import annotations

import re

from . import accounts, store, vocab
from .schemas import Match

LABEL = {
    "farmer": {"en": "a farmer in {town}", "si": "{town} ගොවියෙක්", "ta": "{town} விவசாயி"},
    "buyer": {"en": "a buyer in {town}", "si": "{town} ගැනුම්කරුවෙක්", "ta": "{town} வாங்குபவர்"},
    "farmer_any": {"en": "a farmer", "si": "ගොවියෙක්", "ta": "ஒரு விவசாயி"},
    "buyer_any": {"en": "a buyer", "si": "ගැනුම්කරුවෙක්", "ta": "ஒரு வாங்குபவர்"},
}
PHONEISH = re.compile(r"[+\d][\d\s()+-]{5,}")


def is_phone(name: str | None) -> bool:
    return not name or name.strip().lower() == "unknown" or bool(PHONEISH.fullmatch(name.strip()))


def name_of(name: str | None, phone: str | None, side: str, town: str | None, lang: str = "en") -> str:
    """`name` if it is a real name, else the account's business or name, else a neutral label."""
    if not is_phone(name):
        return name.strip()
    u = accounts.user(phone) if phone and phone.isdigit() else None
    for k in ("business", "name"):
        if u and not is_phone(u.get(k)):
            return u[k].strip()
    lang = lang if lang in ("si", "ta", "en") else "en"
    if town:
        return LABEL[side][lang].format(town=vocab.town(town) or town)
    return LABEL[f"{side}_any"][lang]


def farmer(m: Match, lang: str = "en") -> str:
    l = store.get("listings", m.listing_id) or {}
    return name_of(l.get("farmer") or m.farmer, l.get("phone"), "farmer", l.get("location"), lang)


def buyer(m: Match, lang: str = "en") -> str:
    o = store.get("orders", m.order_id) or {}
    return name_of(o.get("buyer") or m.buyer, o.get("phone"), "buyer", o.get("location"), lang)


def both(m: Match, lang: str = "en") -> dict:
    return {"farmer": farmer(m, lang), "buyer": buyer(m, lang)}


def shown(m: Match, lang: str = "en") -> Match:
    """A copy of the match with display names, for Gemini and templates that read m.farmer/m.buyer."""
    return m.model_copy(update=both(m, lang))


_START = re.compile(r"(^|[.!?]\s+|\n)(a|an) (farmer|buyer)\b")


def tidy(text: str) -> str:
    """'a farmer in Badulla has handed over...' at the start of a sentence gets its capital."""
    return _START.sub(lambda h: f"{h.group(1)}{h.group(2).capitalize()} {h.group(3)}", text or "")
