"""Match lifecycle: propose, notify both sides, confirm on YES from each."""
from __future__ import annotations

import logging
import os
import uuid

from . import agent, store, whatsapp
from .lanes import load_lanes
from .matcher import impact, match

log = logging.getLogger("govi")
LANES = load_lanes()
YES = {"yes", "y", "ok", "okay", "ow", "owu", "ඔව්", "ඔව්.", "ஆம்", "aam", "sari", "சரி"}
NO = {"no", "n", "epa", "naha", "නැහැ", "එපා", "இல்லை", "venam", "வேண்டாம்"}


def _send(to: str | None, body: str, match_id: str) -> None:
    if not to:
        return
    store.outbox(to, body, match_id)
    if os.getenv("WHATSAPP_TOKEN") and to.isdigit():
        try:
            whatsapp.send_text(to, body)
        except Exception:
            log.exception("whatsapp send failed")


def plan() -> dict:
    """Propose matches for stock not already held by a pending or confirmed match, and notify."""
    held = [m for m in store.matches() if m.status == "proposed"]
    listings, orders = store.listings(), store.orders()
    for m in held:  # confirmed matches already reduced remaining_kg when they were confirmed
        for x in listings:
            if x.id == m.listing_id:
                x.remaining_kg -= m.qty_kg
        for x in orders:
            if x.id == m.order_id:
                x.remaining_kg -= m.qty_kg
    prices = store.prices()
    blocked = {(m.listing_id, m.order_id) for m in store.matches() if m.status == "declined"}
    fresh, surplus = match(listings, orders, LANES, prices, blocked)
    by_id = {x.id: x for x in listings} | {x.id: x for x in orders}
    for m in fresh:
        m.id = uuid.uuid4().hex[:8]
        store.put_match(m)
        l, o = by_id[m.listing_id], by_id[m.order_id]
        _send(l.phone, agent.explain(m, party="farmer", lang=l.lang, prices=prices), m.id)
        _send(o.phone, agent.explain(m, party="buyer", lang=o.lang, prices=prices), m.id)
    live = [m for m in store.matches() if m.status != "declined"]
    out = {"matches": [m.model_dump(mode="json") for m in live],
           "surplus": [l.model_dump(mode="json") for l in surplus],
           "impact": {**impact(live), "surplus_kg": sum(l.remaining_kg for l in surplus),
                      "confirmed": sum(m.status == "confirmed" for m in live)}}
    store.save_plan(out)
    return out


def answer(phone: str, text: str) -> str | None:
    """Handle a YES/NO reply. Returns the reply text, or None if this is not a confirmation."""
    word = text.strip().lower().rstrip("!.")
    if word not in YES | NO:
        return None
    pending = []
    for m in store.matches():
        if m.status != "proposed":
            continue
        l, o = store.get("listings", m.listing_id), store.get("orders", m.order_id)
        if l and l.get("phone") == phone and not m.farmer_ok:
            pending.append((m, "farmer"))
        elif o and o.get("phone") == phone and not m.buyer_ok:
            pending.append((m, "buyer"))
    if not pending:
        return None
    m, side = pending[0]
    if word in NO:
        m.status = "declined"
        store.put_match(m)
        return f"Declined: {m.qty_kg:.0f} kg {m.crop}. We will look for another match."
    setattr(m, f"{side}_ok", True)
    if m.farmer_ok and m.buyer_ok:
        m.status = "confirmed"
        for kind in ("listings", "orders"):
            doc = store.get(kind, m.listing_id if kind == "listings" else m.order_id)
            doc["remaining_kg"] -= m.qty_kg
            store.put(kind, doc)
        other = store.get("orders" if side == "farmer" else "listings",
                          m.order_id if side == "farmer" else m.listing_id)
        _send(other.get("phone"), f"Confirmed: {m.qty_kg:.0f} kg {m.crop}, {m.farmer} → {m.buyer}.", m.id)
    store.put_match(m)
    done = "Confirmed by both sides." if m.status == "confirmed" else "Thanks. Waiting for the other side."
    return f"{done} {m.qty_kg:.0f} kg {m.crop}."
