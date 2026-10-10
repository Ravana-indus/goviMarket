"""Match lifecycle: propose, notify both sides, confirm on YES from each."""
from __future__ import annotations

import logging
import os
import uuid

from . import agent, messages, shipping, store, vocab, whatsapp
from .lanes import load_lanes
from .matcher import bundle, impact, match
from .pricing import split

log = logging.getLogger("govi")
LANES = load_lanes()
YES = vocab.YES
NO = vocab.NO | vocab.CANCEL
SAY = {  # Sinhala and Tamil need a native speaker's read before the demo video.
    "both": {"en": "Confirmed by both sides. {kg} kg {crop}.", "si": "දෙපාර්ශවයම තහවුරු කළා. {crop} කිලෝ {kg}.",
             "ta": "இரு தரப்பும் உறுதிசெய்தனர். {crop} {kg} கிலோ."},
    "wait": {"en": "Thanks. Waiting for the other side. {kg} kg {crop}.",
             "si": "ස්තූතියි. අනෙක් පාර්ශවයේ පිළිතුර බලාපොරොත්තුවෙන්. {crop} කිලෝ {kg}.",
             "ta": "நன்றி. மறுதரப்பின் பதிலுக்காக காத்திருக்கிறோம். {crop} {kg} கிலோ."},
    "declined": {"en": "Declined: {kg} kg {crop}. We will look for another match.",
                 "si": "ප්‍රතික්ෂේප කළා: {crop} කිලෝ {kg}. වෙනත් ගැළපීමක් සොයනවා.",
                 "ta": "நிராகரிக்கப்பட்டது: {crop} {kg} கிலோ. வேறு பொருத்தம் தேடுவோம்."},
    "agreed": {"en": "Confirmed: {kg} kg {crop}, {farmer} → {buyer}.", "si": "තහවුරුයි: {crop} කිලෝ {kg}, {farmer} → {buyer}.",
               "ta": "உறுதி: {crop} {kg} கிலோ, {farmer} → {buyer}."},
    "off": {"en": "The offer for {kg} kg {crop} is off: the other side withdrew. We will look for another match.",
            "si": "{crop} කිලෝ {kg} සඳහා වූ ගැළපීම අවලංගුයි: අනෙක් පාර්ශවය ඉවත් විය. වෙනත් ගැළපීමක් සොයනවා.",
            "ta": "{crop} {kg} கிலோ பொருத்தம் ரத்து: மறுதரப்பு விலகியது. வேறு பொருத்தம் தேடுவோம்."},
    "many": {"en": "Reply YES to accept all {n}, or NO to decline all.",
             "si": "සියල්ල ({n}) පිළිගැනීමට YES, සියල්ල ප්‍රතික්ෂේප කිරීමට NO ලෙස පිළිතුරු දෙන්න.",
             "ta": "அனைத்தையும் ({n}) ஏற்க YES, அனைத்தையும் நிராகரிக்க NO என பதில் அனுப்பவும்."},
}


def _say(key: str, lang: str | None, m=None, **kw) -> str:
    lang = lang if lang in ("si", "ta", "en") else "en"
    if m is not None:
        kw = {"kg": f"{m.qty_kg:.0f}", "crop": vocab.crop_name(m.crop, lang), "farmer": m.farmer, "buyer": m.buyer, **kw}
    return SAY[key][lang].format(**kw)


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
    # One message per person per run: a buyer whose five-item order found five farmers gets one
    # list and one YES, not five messages that each want their own YES.
    todo: dict[tuple, list] = {}
    for m in live:
        if m.id in fresh_ids:
            l, o = by_id[m.listing_id], by_id[m.order_id]
            todo.setdefault((l.phone, "farmer", l.lang), []).append(m)
            todo.setdefault((o.phone, "buyer", o.lang), []).append(m)
    for (phone, party, lang), ms in todo.items():
        if len(ms) == 1 or not phone:
            for m in ms:
                _send(phone, agent.explain(m, party=party, lang=lang, prices=prices,
                                           shared_with=sizes.get(m.shipment_id, 1) - 1 if party == "farmer" else 0), m.id)
        else:
            _send(phone, _several(ms, party, lang), ",".join(m.id for m in ms))
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


def _several(ms: list, party: str, lang: str) -> str:
    """Several matches for one person in one message, numbers from code."""
    rows = []
    for m in ms:
        lane = f"{m.lane.mode.replace('_', ' ')} {m.lane.departs}" if m.lane else "local pickup"
        crop = vocab.crop_name(m.crop, "en")
        rows.append(f"• {crop} {m.qty_kg:.0f} kg to {m.buyer}: you get Rs {m.farmer_gets_lkr_per_kg:.0f}/kg, send by {lane}"
                    if party == "farmer" else
                    f"• {crop} {m.qty_kg:.0f} kg from {m.farmer}: Rs {m.buyer_pays_lkr_per_kg:.0f}/kg "
                    f"(retail Rs {m.market_retail_lkr_per_kg:.0f}), comes by {lane}")
    head = f"{'Buyers' if party == 'farmer' else 'Farmers'} found for {len(ms)} of your items:"
    fallback = "\n".join([head, *rows, _say("many", "en", n=len(ms))])
    if lang == "en":
        return fallback
    return messages.write("several match offers for one person; list each one, then say how to accept or decline all",
                          {"party": party, "offers": rows, "reply": _say("many", lang, n=len(ms))}, lang, fallback,
                          extra="Keep every number exactly as given. End with the reply line as given, word for word.")


def _mine(phone: str) -> list[tuple]:
    """Matches still waiting for this number's YES, with which side it is on."""
    out = []
    for m in store.matches():
        if m.status != "proposed":
            continue
        l, o = store.get("listings", m.listing_id), store.get("orders", m.order_id)
        if l and l.get("phone") == phone and not m.farmer_ok:
            out.append((m, "farmer", l.get("lang")))
        elif o and o.get("phone") == phone and not m.buyer_ok:
            out.append((m, "buyer", o.get("lang")))
    return out


def asked_at(phone: str) -> str | None:
    """When this number was last sent a match offer it has not answered, if any."""
    mine = {m.id for m, _, _ in _mine(phone)}
    if not mine:
        return None
    ats = [o["at"] for o in store.sent() if o["to"] == phone and set((o.get("match_id") or "").split(",")) & mine]
    return max(ats) if ats else "0"  # an offer we never managed to send still counts, just as the oldest


def answer(phone: str, text: str, lang: str | None = None) -> str | None:
    """YES or NO to every match offer waiting on this number (one message offered them together).
    Returns the reply, or None if this is not a YES/NO or nothing is waiting."""
    word = vocab.norm(text)
    if word not in YES | NO:
        return None
    pending = _mine(phone)
    if not pending:
        return None
    lines = []
    for m, side, own_lang in pending:
        lang_ = lang or own_lang
        if word in NO:
            m.status = "declined"
            store.put_match(m)
            lines.append(_say("declined", lang_, m))
            continue
        setattr(m, f"{side}_ok", True)
        if m.farmer_ok and m.buyer_ok:
            confirm(m)
            other = store.get("orders" if side == "farmer" else "listings",
                              m.order_id if side == "farmer" else m.listing_id)
            _send(other.get("phone"), _say("agreed", other.get("lang"), m), m.id)
        store.put_match(m)
        lines.append(_say("both" if m.status == "confirmed" else "wait", lang_, m))
    return "\n".join(lines)


def withdraw(ids: set[str]) -> int:
    """A listing or order was withdrawn: call off its open offers and tell the other side."""
    n = 0
    for m in store.matches():
        if m.status != "proposed" or not ({m.listing_id, m.order_id} & ids):
            continue
        m.status = "cancelled"
        store.put_match(m)
        other = store.get("orders", m.order_id) if m.listing_id in ids else store.get("listings", m.listing_id)
        if other:
            _send(other.get("phone"), _say("off", other.get("lang"), m), m.id)
        n += 1
    return n


def advance_shipment(sid: str):
    return shipping.advance(sid, _send)
