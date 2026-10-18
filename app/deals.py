"""Match lifecycle: propose, notify both sides, confirm on YES from each."""
from __future__ import annotations

import logging
import os
import re
import threading
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import accounts, agent, messages, shipping, store, telegram, vocab, whatsapp
from .lanes import _norm, load_lanes
from .matcher import bundle, impact, match, why_unmatched
from .pricing import split

log = logging.getLogger("govi")
LANES = load_lanes()
SL_TZ = ZoneInfo("Asia/Colombo")
YES = vocab.YES
NO = vocab.NO
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
    "expired": {"en": "That offer ({kg} kg {crop}) has expired. We will look for another match.",
                "si": "එම ගැළපීම ({crop} කිලෝ {kg}) කල් ඉකුත් විය. වෙනත් ගැළපීමක් සොයනවා.",
                "ta": "அந்த பொருத்தம் ({crop} {kg} கிலோ) காலாவதியானது. வேறு பொருத்தம் தேடுவோம்."},
    "too_much": {"en": "The offer is for {kg} kg {crop}. Reply YES, or YES and a smaller amount.",
                 "si": "ගැළපීම {crop} කිලෝ {kg} සඳහායි. YES, හෝ YES සහ අඩු ප්‍රමාණයක් එවන්න.",
                 "ta": "பொருத்தம் {crop} {kg} கிலோவுக்கு. YES, அல்லது YES உடன் குறைந்த அளவு அனுப்பவும்."},
    "too_small": {"en": "{part} kg {crop} is too small to send on its own: transport would cost more than the collector pays. Reply YES for all {kg} kg or NO.",
                  "si": "{crop} කිලෝ {part} තනිව යැවීමට ඉතා අඩුයි: ප්‍රවාහන වියදම එකතු කරන්නාගේ මිලට වඩා වැඩියි. කිලෝ {kg} ම සඳහා YES හෝ NO එවන්න.",
                  "ta": "{crop} {part} கிலோ தனியாக அனுப்ப மிகக் குறைவு: போக்குவரத்து செலவு சேகரிப்பாளர் விலையை விட அதிகம். {kg} கிலோ முழுவதற்கும் YES அல்லது NO அனுப்பவும்."},
    "many": {"en": "Reply YES to accept all {n}, NO to decline all, or e.g. YES 1 or NO 2 to pick.",
             "si": "සියල්ල ({n}) පිළිගැනීමට YES, ප්‍රතික්ෂේප කිරීමට NO, හෝ තෝරාගැනීමට YES 1 / NO 2 ලෙස පිළිතුරු දෙන්න.",
             "ta": "அனைத்தையும் ({n}) ஏற்க YES, நிராகரிக்க NO, அல்லது தெரிவுசெய்ய YES 1 / NO 2 என பதில் அனுப்பவும்."},
}


def _say(key: str, lang: str | None, m=None, **kw) -> str:
    lang = lang if lang in ("si", "ta", "en") else "en"
    if m is not None:
        kw = {"kg": f"{m.qty_kg:.0f}", "crop": vocab.crop_name(m.crop, lang), "farmer": m.farmer, "buyer": m.buyer, **kw}
    return SAY[key][lang].format(**kw)


def _send(to: str | None, body: str, match_id: str, buttons: list | None = None) -> None:
    """`buttons`: one-tap replies shown under the message on Telegram (rows of labels)."""
    if not to:
        return
    store.outbox(to, body, match_id)
    if os.getenv("WHATSAPP_TOKEN") and to.isdigit():
        try:
            whatsapp.send_text(to, body)
        except Exception:
            log.exception("whatsapp send failed")
    telegram.send_to_phone(to, body, keyboard=buttons)


_plan_lock = threading.RLock()  # re-entrant: a rescue inside plan() re-plans on the same thread


def plan(extra_blocked: set[tuple[str, str]] = frozenset(), today: date | None = None) -> dict:
    """Propose matches for stock not already held by a pending or confirmed match, and notify."""
    with _plan_lock:  # ponytail: process lock ensures no overlapping plans race on inventory
        now = datetime.now(timezone.utc)
        # Every caller gets the past-date rules, not just chat: Sri Lanka's date, not the server's UTC one.
        today = today or datetime.now(SL_TZ).date()
        from . import rescue
        rescue.watchdog(now=now, send=_send)
        # ponytail: release stale proposed matches past their TTL and send reminder/expiry notices
        for m in store.matches():
            if m.status == "proposed" and m.expires_at:
                try:
                    exp_dt = datetime.fromisoformat(m.expires_at)
                    if exp_dt <= now:
                        m.status = "expired"
                        store.put_match(m)
                        l = store.get("listings", m.listing_id) or {}
                        o = store.get("orders", m.order_id) or {}
                        if not m.farmer_ok:
                            _send(l.get("phone"), f"Offer for {m.qty_kg:.0f} kg {m.crop} expired. Produce is back on offer for other buyers.", m.id)
                        if not m.buyer_ok:
                            _send(o.get("phone"), f"Offer for {m.qty_kg:.0f} kg {m.crop} expired. Order is back on offer for other farmers.", m.id)
                    elif not m.reminded and exp_dt - now <= timedelta(hours=1):
                        m.reminded = True
                        store.put_match(m)
                        l = store.get("listings", m.listing_id) or {}
                        o = store.get("orders", m.order_id) or {}
                        if not m.farmer_ok:
                            _send(l.get("phone"), f"Reminder: offer for {m.qty_kg:.0f} kg {m.crop} expires soon. Reply YES to accept or NO to pass.", m.id)
                        if not m.buyer_ok:
                            _send(o.get("phone"), f"Reminder: offer for {m.qty_kg:.0f} kg {m.crop} expires soon. Reply YES to accept or NO to pass.", m.id)
                except Exception:
                    pass

        held = [m for m in store.matches() if m.status == "proposed"]
        listings, orders = store.listings(), store.orders()
        for m in held:  # confirmed matches already reduced remaining_kg when they were confirmed
            for x in listings:
                if x.id == m.listing_id:
                    x.remaining_kg = max(0.0, x.remaining_kg - m.qty_kg)
            for x in orders:
                if x.id == m.order_id:
                    x.remaining_kg = max(0.0, x.remaining_kg - m.qty_kg)
        prices = store.prices()
        # ponytail: rerouted matches do not permanently block the pair from ever trading again
        blocked = {(m.listing_id, m.order_id) for m in store.matches()
                   if m.status == "declined" or (m.status == "cancelled" and m.note != "rerouted")} | set(extra_blocked)

        # Track aggregate departure capacity booked by non-planned shipments
        booked_cap: dict[tuple, float] = defaultdict(float)
        for s in store.shipments():
            if s.status != "planned" and s.lane and s.ship_on:
                k = (_norm(s.lane.origin), _norm(s.lane.dest), s.lane.mode, s.lane.departs, s.ship_on)
                booked_cap[k] += s.total_kg

        match_cap = defaultdict(float, booked_cap)
        fresh, surplus = match(listings, orders, LANES, prices, blocked, today=today, booked_cap=match_cap)
        by_id = {x.id: x for x in listings} | {x.id: x for x in orders}
        ttl_hours = float(os.getenv("OFFER_TTL_HOURS", "4"))
        for m in fresh:
            m.id = uuid.uuid4().hex[:8]
            m.created_at = now.isoformat()
            m.expires_at = (now + timedelta(hours=ttl_hours)).isoformat()
            store.put_match(m)
        live = [m for m in store.matches() if m.status not in ("declined", "cancelled", "expired")]
        # Shipments already booked are locked, and so is any load someone has agreed to: its seller
        # already has a dispatch slip naming the bus, the stand and the time. Only loads still
        # waiting for a YES get re-bundled.
        status = {m.id: m.status for m in store.matches()}
        frozen = []
        for x in store.shipments():
            if x.status == "planned" and not any(status.get(i) == "confirmed" for i in x.match_ids):
                continue
            keep = [i for i in x.match_ids if status.get(i) in ("proposed", "confirmed")]
            if x.status == "planned" and keep != x.match_ids:  # drop loads that were declined or expired
                x.match_ids = keep
                x.total_kg = sum(m.qty_kg for m in live if m.id in keep)
                store.put_shipment(x)
            frozen.append(x)
        frozen_sids = {x.id for x in frozen}
        prev_ids = {tuple(sorted(x.match_ids)): x.id for x in store.shipments()
                    if x.status == "planned" and x.id not in frozen_sids}
        for x in store.shipments():
            if x.status == "planned" and x.id not in frozen_sids:
                store.delete_shipment(x.id)
        frozen_ids = {mid for x in frozen for mid in x.match_ids}
        movable = [m for m in live if m.id not in frozen_ids and m.status != "confirmed"]
        for m in movable:  # every run starts from each load's own cheapest lane, then re-bundles
            m.lane = m.solo_lane or m.lane
            m.transport_lkr_per_kg = m.solo_transport_lkr_per_kg or m.transport_lkr_per_kg
            m.shipment_id = None
            # ponytail: confirmed matches are binding contracts; never silently reprice them
            if m.status != "confirmed":
                m.farmer_gets_lkr_per_kg = split(prices[m.crop], m.transport_lkr_per_kg)["farmer_gets"] \
                    if m.crop in prices else m.farmer_gets_lkr_per_kg
        bundle_cap = defaultdict(float, booked_cap)
        shipments = bundle(movable, LANES, prices, booked_cap=bundle_cap, prev_ids=prev_ids)
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
                todo.setdefault((l.phone, "farmer", accounts.reply_lang(l.phone, l.lang)), []).append(m)
                todo.setdefault((o.phone, "buyer", accounts.reply_lang(o.phone, o.lang)), []).append(m)
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
               "impact": {**impact(live, shipments), "surplus_kg": sum(l.remaining_kg for l in surplus),
                          "confirmed": sum(m.status == "confirmed" for m in live)}}
        store.save_plan(out)
        from . import reroute
        reroute.scan(_send)  # a better route can show up after a deal is agreed
        return out


def unmatched() -> dict[str, str]:
    """Order id -> why its open kg found no seller, for the console."""
    held = [m for m in store.matches() if m.status == "proposed"]
    listings, orders = store.listings(), store.orders()
    for x in listings + orders:
        x.remaining_kg -= sum(m.qty_kg for m in held if x.id in (m.listing_id, m.order_id))
    blocked = {(m.listing_id, m.order_id) for m in store.matches() if m.status in ("declined", "cancelled")}
    prices = store.prices()
    return {o.id: why_unmatched(o, listings, LANES, prices, blocked) for o in orders if o.remaining_kg > 0}


def confirm(m, notify: bool = True) -> None:
    """Both sides said yes: lock the deal, take the kg out of open stock and demand, and send the
    seller the dispatch slip (tracking code and delivery address) and the buyer the tracking code."""
    m.farmer_ok = m.buyer_ok = True
    m.status = "confirmed"
    store.adjust_remaining("listings", m.listing_id, -m.qty_kg)
    store.adjust_remaining("orders", m.order_id, -m.qty_kg)
    store.put_match(m)
    if notify:
        from . import dispatch
        dispatch.send_details(m, _send)


def _several(ms: list, party: str, lang: str) -> str:
    """Several matches for one person in one message, numbers from code."""
    rows = []
    for idx, m in enumerate(ms, 1):
        lane = f"{m.lane.mode.replace('_', ' ')} {m.lane.departs}" if m.lane else "local pickup"
        crop = vocab.crop_name(m.crop, lang)
        rows.append(f"{idx}. {crop} {m.qty_kg:.0f} kg to {m.buyer}: you get Rs {m.farmer_gets_lkr_per_kg:.0f}/kg, send by {lane}"
                    if party == "farmer" else
                    f"{idx}. {crop} {m.qty_kg:.0f} kg from {m.farmer}: Rs {m.buyer_pays_lkr_per_kg:.0f}/kg "
                    f"(retail Rs {m.market_retail_lkr_per_kg:.0f}), comes by {lane}")
    head = f"{'Buyers' if party == 'farmer' else 'Farmers'} found for {len(ms)} of your items:"
    fallback = "\n".join([head, *rows, _say("many", lang, n=len(ms))])
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
            out.append((m, "farmer", accounts.reply_lang(phone, l.get("lang"))))
        elif o and o.get("phone") == phone and not m.buyer_ok:
            out.append((m, "buyer", accounts.reply_lang(phone, o.get("lang"))))
    return out


def asked_at(phone: str) -> str | None:
    """When this number was last sent a match offer it has not answered, if any."""
    mine = {m.id for m, _, _ in _mine(phone)}
    if not mine:
        return None
    ats = [o["at"] for o in store.sent() if o["to"] == phone and set((o.get("match_id") or "").split(",")) & mine]
    return max(ats) if ats else datetime.min.replace(tzinfo=timezone.utc).isoformat()


def _parse_selection(text: str, total: int) -> dict[int, bool] | None:
    norm_text = vocab.norm(text)
    if norm_text in YES:
        return {i: True for i in range(1, total + 1)}
    if norm_text in NO:
        return {i: False for i in range(1, total + 1)}
    actions = {}
    for part in re.finditer(r"(?:\b|^)(yes|ok|sure|confirm|ow|hari|ஆம்|சரி|no|epa|නෑ|නැහැ|இல்லை|வேண்டாம்)\b([0-9,\s#]+)", text, re.IGNORECASE):
        kw = vocab.norm(part.group(1))
        is_yes = kw in YES
        nums = [int(n) for n in re.findall(r"\b\d+\b", part.group(2))]
        for n in nums:
            if 1 <= n <= total:
                actions[n] = is_yes
    if not actions:
        for part in re.finditer(r"(?:#?\b)(\d+)\s*(yes|ok|sure|confirm|ow|hari|ஆம்|சரி|no|epa|නෑ|නැහැ|இல்லை|வேண்டாம்)\b", text, re.IGNORECASE):
            n = int(part.group(1))
            kw = vocab.norm(part.group(2))
            is_yes = kw in YES
            if 1 <= n <= total:
                actions[n] = is_yes
    return actions if actions else None


def _parse_partial_qty(text: str, total: int) -> tuple[int, float] | None:
    m = re.search(r"\b(yes|ok|sure|confirm|ow|hari)\b(?:\s*#?(\d+))?\s+(\d+(?:\.\d+)?)\s*(?:kg|kilo|kgs|kilos|කිලෝ|கிலோ)\b", text, re.I)
    if m:
        item = int(m.group(2)) if m.group(2) else (1 if total == 1 else None)
        qty = float(m.group(3))
        if item is not None and 1 <= item <= total:
            return item, qty
    return None


def _numbered(phone: str, pending: list[tuple]) -> list[tuple]:
    """Waiting offers in the order the newest numbered message showed them, so "YES 1" means that
    message's 1; offers it did not list follow after."""
    by_id = {m.id: row for row in pending for m in [row[0]]}
    for o in reversed(store.sent()):
        ids = (o.get("match_id") or "").split(",")
        if o["to"] == phone and len(ids) > 1 and set(ids) & set(by_id):
            first = [by_id[i] for i in ids if i in by_id]
            return first + [row for row in pending if row[0].id not in ids]
    return pending


def _reprice(m, kg: float) -> bool:
    """Re-cost a smaller load on its own (fixed charges weigh more per kg). False if the farmer
    would no longer beat the collector price."""
    from .lanes import lane_cost, pick_lane
    prices = store.prices()
    if m.crop not in prices:
        return False
    lane, transport = None, 0.0
    if m.lane:
        lane = pick_lane(LANES, origin=m.lane.origin, dest=m.lane.dest, kg=kg, ship_on=m.ship_on, needed_by=m.needed_by)
        if lane is None:
            return False
        transport = round(lane_cost(lane, kg) / kg, 1)
    money = split(prices[m.crop], transport)
    if not money["farmer_better_off"]:
        return False
    m.qty_kg, m.lane, m.solo_lane = kg, lane, lane
    m.transport_lkr_per_kg = m.solo_transport_lkr_per_kg = transport
    m.farmer_gets_lkr_per_kg, m.buyer_pays_lkr_per_kg = money["farmer_gets"], money["buyer_pays"]
    return True


def answer(phone: str, text: str, lang: str | None = None) -> str | None:
    """YES, NO, selective pick (e.g. YES 1, NO 2), or partial accept (e.g. YES 50kg) to match offers.
    Returns the reply, or None if this is not an answer or nothing is waiting."""
    pending = _mine(phone)
    if not pending:
        return None
    now = datetime.now(timezone.utc)
    live = []
    for m, side, own_lang in pending:  # an offer past its time is gone, even if no run has expired it yet
        if m.expires_at and datetime.fromisoformat(m.expires_at) <= now:
            m.status = "expired"
            store.put_match(m)
        else:
            live.append((m, side, own_lang))
    if not live:
        return _say("expired", lang or pending[0][2], pending[0][0])
    pending = _numbered(phone, live)
    partial = _parse_partial_qty(text, len(pending))
    if partial and partial[1] != pending[partial[0] - 1][0].qty_kg:  # "YES 100kg" on a 100 kg offer is a plain YES
        idx, partial_kg = partial
        m, side, own_lang = pending[idx - 1]
        lang_ = lang or own_lang
        if not 0 < partial_kg < m.qty_kg:
            return _say("too_much", lang_, m)
        if not _reprice(m, partial_kg):
            return _say("too_small", lang_, m, part=f"{partial_kg:.0f}")
        # The other side agreed to the full amount, not this one: ask them again.
        other_side = "buyer" if side == "farmer" else "farmer"
        setattr(m, f"{side}_ok", True)
        setattr(m, f"{other_side}_ok", False)
        store.put_match(m)
        other = store.get("orders" if side == "farmer" else "listings",
                          m.order_id if side == "farmer" else m.listing_id) or {}
        if other.get("phone"):
            olang = accounts.reply_lang(other.get("phone"), other.get("lang"))
            _send(other["phone"], agent.explain(m, party=other_side, lang=olang, prices=store.prices()), m.id)
        return _say("wait", lang_, m)
    actions = {partial[0]: True} if partial else _parse_selection(text, len(pending))
    if not actions:
        return None
    lines = []
    for idx, (m, side, own_lang) in enumerate(pending, 1):
        if idx not in actions:
            continue
        yes = actions[idx]
        lang_ = lang or own_lang
        if not yes:
            m.status = "declined"
            store.put_match(m)
            if m.note.startswith("rescue:"):
                from . import rescue
                rescue.decline_rescue_match(m)
            lines.append(_say("declined", lang_, m))
            continue
        setattr(m, f"{side}_ok", True)
        if m.farmer_ok and m.buyer_ok:
            confirm(m, notify=False)
            other = store.get("orders" if side == "farmer" else "listings",
                              m.order_id if side == "farmer" else m.listing_id)
            _send(other.get("phone"), _say("agreed", accounts.reply_lang(other.get("phone"), other.get("lang")), m), m.id)
            from . import dispatch
            dispatch.send_details(m, _send)
        store.put_match(m)
        lines.append(_say("both" if m.status == "confirmed" else "wait", lang_, m))
    return "\n".join(lines) if lines else None


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
            _send(other.get("phone"), _say("off", accounts.reply_lang(other.get("phone"), other.get("lang")), m), m.id)
        n += 1
    return n


def advance_shipment(sid: str):
    return shipping.advance(sid, _send)


def cancel_shipment(sid: str, reason: str = "operator cancelled"):
    """Operator marks a shipment cancelled, frees its matches."""
    s = next((x for x in store.shipments() if x.id == sid), None)
    if not s:
        raise KeyError(sid)
    s.status = "cancelled"
    s.events.append({"status": "cancelled", "at": datetime.now(timezone.utc).isoformat(), "note": reason})
    store.put_shipment(s)
    withdraw(set(s.match_ids))
    return s


def reload_lanes() -> list[Lane]:
    """Reload carrier lanes from disk without server restart."""
    global LANES
    LANES = load_lanes()
    return LANES
