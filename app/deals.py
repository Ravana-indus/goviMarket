"""Match lifecycle: propose, notify both sides, confirm on YES from each."""
from __future__ import annotations

import logging
import os
import uuid

from . import agent, shipping, store, whatsapp
from .lanes import load_lanes
from .matcher import bundle, impact, match
from .pricing import split

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


def plan(extra_blocked: set[tuple[str, str]] = frozenset()) -> dict:
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
    blocked = {(m.listing_id, m.order_id) for m in store.matches() if m.status in ("declined", "cancelled")} | set(extra_blocked)
    fresh, surplus = match(listings, orders, LANES, prices, blocked)
    by_id = {x.id: x for x in listings} | {x.id: x for x in orders}
    for m in fresh:
        m.id = uuid.uuid4().hex[:8]
        store.put_match(m)
    live = [m for m in store.matches() if m.status not in ("declined", "cancelled")]
    # Shipments already booked are locked; only loads still being planned get re-bundled.
    frozen = [x for x in store.shipments() if x.status != "planned"]
    for x in store.shipments():
        if x.status == "planned":
            store.delete_shipment(x.id)
    frozen_ids = {mid for x in frozen for mid in x.match_ids}
    movable = [m for m in live if m.id not in frozen_ids]
    for m in movable:  # every run starts from each load's own cheapest lane, then re-bundles
        m.lane = m.solo_lane or m.lane
        m.transport_lkr_per_kg = m.solo_transport_lkr_per_kg or m.transport_lkr_per_kg
        m.shipment_id = None
        m.farmer_gets_lkr_per_kg = split(prices[m.crop], m.transport_lkr_per_kg)["farmer_gets"] \
            if m.crop in prices else m.farmer_gets_lkr_per_kg
    shipments = bundle(movable, LANES, prices)
    for x in shipments:
        x.schedule = shipping.schedule(x.lane, x.ship_on)
        store.put_shipment(x)
    for m in movable:
        store.put_match(m)
    shipments = frozen + shipments
    fresh_ids = {m.id for m in fresh}
    sizes = {x.id: len(x.farmers) for x in shipments}
    for m in live:
        if m.id in fresh_ids:
            l, o = by_id[m.listing_id], by_id[m.order_id]
            _send(l.phone, agent.explain(m, party="farmer", lang=l.lang, prices=prices,
                                         shared_with=sizes.get(m.shipment_id, 1) - 1), m.id)
            _send(o.phone, agent.explain(m, party="buyer", lang=o.lang, prices=prices), m.id)
    out = {"matches": [m.model_dump(mode="json") for m in live],
           "shipments": [x.model_dump(mode="json") for x in shipments],
           "surplus": [l.model_dump(mode="json") for l in surplus],
           "impact": {**impact(live), "surplus_kg": sum(l.remaining_kg for l in surplus),
                      "confirmed": sum(m.status == "confirmed" for m in live)}}
    store.save_plan(out)
    from . import reroute
    reroute.scan(_send)  # a better route can show up after a deal is agreed
    return out


def confirm(m) -> None:
    """Both sides said yes: lock the deal and take the kg out of open stock and demand."""
    m.farmer_ok = m.buyer_ok = True
    m.status = "confirmed"
    for kind, rid in (("listings", m.listing_id), ("orders", m.order_id)):
        doc = store.get(kind, rid)
        doc["remaining_kg"] -= m.qty_kg
        store.put(kind, doc)
    store.put_match(m)


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
        confirm(m)
        other = store.get("orders" if side == "farmer" else "listings",
                          m.order_id if side == "farmer" else m.listing_id)
        _send(other.get("phone"), f"Confirmed: {m.qty_kg:.0f} kg {m.crop}, {m.farmer} → {m.buyer}.", m.id)
    store.put_match(m)
    done = "Confirmed by both sides." if m.status == "confirmed" else "Thanks. Waiting for the other side."
    return f"{done} {m.qty_kg:.0f} kg {m.crop}."


def advance_shipment(sid: str):
    return shipping.advance(sid, _send)
