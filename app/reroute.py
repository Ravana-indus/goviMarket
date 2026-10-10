"""Better route found: swap who supplies whom after a deal is agreed, before the loads leave.

Example: an Ampara farmer agreed to send corn to a Colombo restaurant. Later a Kurunegala farmer
lists the same corn and an Ampara restaurant asks for it. Ampara to Ampara and Kurunegala to
Colombo is cheaper, and nobody is left unsold. Govi proposes the swap; it happens only if every
person whose deal changes replies YES. One NO and the agreed deals stand as they are.

Rules: loads already booked on a bus, train or lorry never move, nothing moves on or after its
shipping day, a rerouted deal is not rerouted again, no farmer already in a deal earns less, and
buyers pay the same price per kg. Numbers come from the matcher; Gemini only writes the messages."""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone

from . import agent, store
from .matcher import match
from .schemas import Listing, Match, Order

MIN_SAVING_LKR = float(os.getenv("REROUTE_MIN_SAVING_LKR", "500"))
MIN_SAVING_SHARE = float(os.getenv("REROUTE_MIN_SAVING_SHARE", "0.15"))
KIND = "swaps"


def swaps() -> list[dict]:
    return sorted(store.DB.all(KIND), key=lambda s: s["at"], reverse=True)


def _leg(l: Listing, o: Order, kg: float, prices: dict) -> Match | None:
    """What the matcher would offer for `kg` from this farmer to this buyer, or None if it can't."""
    from .deals import LANES
    if kg <= 0:
        return None
    ms, _ = match([l.model_copy(update={"remaining_kg": kg})], [o.model_copy(update={"remaining_kg": kg})],
                  LANES, prices)
    return ms[0] if ms and ms[0].qty_kg >= kg - 1e-6 else None


def _pending() -> list[dict]:
    return [s for s in store.DB.all(KIND) if s["status"] == "proposed"]


def _movable(today: date) -> list[Match]:
    booked = {mid for x in store.shipments() if x.status != "planned" for mid in x.match_ids}
    busy = {mid for s in _pending() for mid in s["old"]}
    return [m for m in store.matches() if m.status in ("proposed", "confirmed") and not m.note
            and m.id not in booked and m.id not in busy and m.ship_on and m.ship_on > today]


def _open() -> tuple[list[Listing], list[Order]]:
    """Stock and demand nobody holds yet (confirmed deals already came off remaining_kg)."""
    held: dict[str, float] = {}
    for m in store.matches():
        if m.status == "proposed":
            held[m.listing_id] = held.get(m.listing_id, 0) + m.qty_kg
            held[m.order_id] = held.get(m.order_id, 0) + m.qty_kg
    for s in _pending():
        for rid in (s.get("open_listing"), s.get("open_order")):
            if rid:
                held[rid] = held.get(rid, 0) + s["kg"]
    ls = [l.model_copy(update={"remaining_kg": l.remaining_kg - held.get(l.id, 0)}) for l in store.listings()]
    os_ = [o.model_copy(update={"remaining_kg": o.remaining_kg - held.get(o.id, 0)}) for o in store.orders()]
    return [l for l in ls if l.remaining_kg > 0], [o for o in os_ if o.remaining_kg > 0]


def _income(m: Match) -> float:
    return m.farmer_gets_lkr_per_kg * m.qty_kg


def _evaluate(a, b, L1, O1, L2, O2, kg, prices) -> dict | None:
    """Swap `kg` so L1 supplies O2 and L2 supplies O1. `b` is L2's current deal with O2, or None when
    L2 is unsold and O2 unfilled because the two cannot trade directly."""
    x, y = _leg(L1, O2, kg, prices), _leg(L2, O1, kg, prices)
    if not x or not y:
        return None
    rest = []  # what stays of each old deal when only part of it moves
    for old, l, o in ((a, L1, O1), (b, L2, O2)):
        if old is None or old.qty_kg - kg <= 1e-6:
            rest.append(None)
            continue
        r = _leg(l, o, old.qty_kg - kg, prices)
        if r is None:
            return None
        rest.append(r)
    # No farmer already in a deal earns less in total than what they agreed.
    if x.farmer_gets_lkr_per_kg * kg + (_income(rest[0]) if rest[0] else 0) < _income(a) - 1:
        return None
    if b and y.farmer_gets_lkr_per_kg * kg + (_income(rest[1]) if rest[1] else 0) < _income(b) - 1:
        return None
    before = a.transport_lkr_per_kg * kg + (b.transport_lkr_per_kg * kg if b else 0)
    after = (x.transport_lkr_per_kg + y.transport_lkr_per_kg) * kg
    saved = before - after
    if b and (saved < MIN_SAVING_LKR or saved < MIN_SAVING_SHARE * before):
        return None
    return {"x": x, "y": y, "rest": rest, "saved": round(saved), "extra_kg": 0 if b else kg,
            "before": round(before), "after": round(after)}


def find(today: date | None = None) -> list[dict]:
    """Look for swaps worth proposing. Each match, unsold load and open order joins at most one."""
    today = today or date.today()
    prices = store.prices()
    L = {l.id: l for l in store.listings()}
    O = {o.id: o for o in store.orders()}
    moves = [m for m in _movable(today) if m.listing_id in L and m.order_id in O and m.crop in prices]
    open_l, open_o = _open()
    tried = {s["key"] for s in store.DB.all(KIND)}
    used: set[str] = set()
    found = []
    for a in moves:
        if a.id in used:
            continue
        L1, O1 = L[a.listing_id], O[a.order_id]
        cands = []
        for b in moves:
            if b.id != a.id and b.id not in used and b.crop == a.crop \
                    and b.listing_id != a.listing_id and b.order_id != a.order_id:
                cands.append((b, L[b.listing_id], O[b.order_id], min(a.qty_kg, b.qty_kg)))
        for l2 in open_l:
            for o2 in open_o:
                if l2.crop == o2.crop == a.crop and l2.id != L1.id and o2.id != O1.id \
                        and not {l2.id, o2.id} & used:
                    kg = min(a.qty_kg, l2.remaining_kg, o2.remaining_kg)
                    if _leg(l2, o2, kg, prices) is None:  # if they can trade directly, matching does it
                        cands.append((None, l2, o2, kg))
        best = None
        for b, l2, o2, kg in cands:
            key = "|".join(sorted([a.id, b.id if b else f"{l2.id}+{o2.id}"]))
            if key in tried:
                continue  # someone already said NO to this one, or it already happened
            ev = _evaluate(a, b, L1, O1, l2, o2, kg, prices)
            if ev and (best is None or (ev["extra_kg"], ev["saved"]) > (best[1]["extra_kg"], best[1]["saved"])):
                best = ((b, l2, o2, kg, key), ev)
        if best:
            (b, l2, o2, kg, key), ev = best
            used |= {a.id} | ({b.id} if b else {l2.id, o2.id})
            found.append(_record(a, b, L1, O1, l2, o2, kg, key, ev))
    return found


def _record(a, b, L1, O1, L2, O2, kg, key, ev) -> dict:
    x, y = ev["x"], ev["y"]
    parties = [{"role": "farmer", "name": L1.farmer, "phone": L1.phone, "lang": L1.lang, "ok": False},
               {"role": "buyer", "name": O1.buyer, "phone": O1.phone, "lang": O1.lang, "ok": False},
               {"role": "farmer", "name": L2.farmer, "phone": L2.phone, "lang": L2.lang, "ok": False},
               {"role": "buyer", "name": O2.buyer, "phone": O2.phone, "lang": O2.lang, "ok": False}]
    why = (f"saves Rs {ev['saved']:,} in transport" if b else
           f"sells {kg:.0f} kg that had no buyer and fills an order that had no supplier")
    return {
        "id": uuid.uuid4().hex[:8], "key": key, "status": "proposed", "crop": a.crop, "kg": kg,
        "old": [a.id] + ([b.id] if b else []),
        "open_listing": None if b else L2.id, "open_order": None if b else O2.id,
        "before": [f"{L1.farmer} ({L1.location}) → {O1.buyer} ({O1.location})"]
                  + ([f"{L2.farmer} ({L2.location}) → {O2.buyer} ({O2.location})"] if b
                     else [f"{L2.farmer} ({L2.location}): unsold · {O2.buyer} ({O2.location}): no supplier"]),
        "after": [f"{L1.farmer} ({L1.location}) → {O2.buyer} ({O2.location})",
                  f"{L2.farmer} ({L2.location}) → {O1.buyer} ({O1.location})"],
        "new": [{"listing_id": L1.id, "order_id": O2.id}, {"listing_id": L2.id, "order_id": O1.id}],
        "transport_before_lkr": ev["before"], "transport_after_lkr": ev["after"],
        "saved_lkr": ev["saved"], "extra_kg": ev["extra_kg"], "why": why,
        "farmer_gain_lkr_per_kg": round(x.farmer_gets_lkr_per_kg - a.farmer_gets_lkr_per_kg, 1),
        "parties": parties, "at": datetime.now(timezone.utc).isoformat(),
    }


def _messages(s: dict, prices: dict) -> list[tuple[dict, str]]:
    """What each person hears. People switching deals get the change spelled out; a farmer or buyer
    who had nothing gets the normal match message from the Gemini agent."""
    L = {l.id: l for l in store.listings()}
    O = {o.id: o for o in store.orders()}
    old = {m.id: m for m in store.matches()}
    a = old[s["old"][0]]
    (n1, n2) = s["new"]
    x = _leg(L[n1["listing_id"]], O[n1["order_id"]], s["kg"], prices)
    y = _leg(L[n2["listing_id"]], O[n2["order_id"]], s["kg"], prices)
    f1, b1, f2, b2 = s["parties"]
    tail = "\nReply YES to switch or NO to keep your current deal. Nothing changes unless everyone agrees."
    out = [
        (f1, f"Better route found for {s['kg']:.0f} kg {s['crop']}.\n"
             f"Sell to {b2['name']} instead of {b1['name']}: Rs {x.farmer_gets_lkr_per_kg:.0f}/kg after transport "
             f"(now Rs {a.farmer_gets_lkr_per_kg:.0f}/kg)." + tail),
        (b1, f"Better route found for your {s['kg']:.0f} kg {s['crop']}.\n"
             f"It will come from {f2['name']} instead of {f1['name']}. Same price, Rs {y.buyer_pays_lkr_per_kg:.0f}/kg." + tail),
    ]
    if len(s["old"]) > 1:
        b = old[s["old"][1]]
        out += [(f2, f"Better route found for {s['kg']:.0f} kg {s['crop']}.\n"
                     f"Sell to {b1['name']} instead of {b2['name']}: Rs {y.farmer_gets_lkr_per_kg:.0f}/kg after "
                     f"transport (now Rs {b.farmer_gets_lkr_per_kg:.0f}/kg)." + tail),
                (b2, f"Better route found for your {s['kg']:.0f} kg {s['crop']}.\n"
                     f"It will come from {f1['name']} instead of {f2['name']}. Same price, Rs {x.buyer_pays_lkr_per_kg:.0f}/kg." + tail)]
    else:
        out += [(f2, agent.explain(y, party="farmer", lang=f2["lang"], prices=prices)),
                (b2, agent.explain(x, party="buyer", lang=b2["lang"], prices=prices))]
    return out


def scan(send, today: date | None = None) -> list[dict]:
    """Find swaps, save them, and message everyone involved. Called after every matching run."""
    prices = store.prices()
    made = find(today)
    for s in made:
        store.DB.put(KIND, s["id"], s)
        for p, body in _messages(s, prices):
            send(p["phone"], body, s["id"])
    return made


def _still_ok(s: dict, today: date) -> bool:
    live = {m.id: m for m in store.matches()}
    if any(mid not in live or live[mid].status not in ("proposed", "confirmed") for mid in s["old"]):
        return False
    booked = {mid for x in store.shipments() if x.status != "planned" for mid in x.match_ids}
    if any(mid in booked or not live[mid].ship_on or live[mid].ship_on <= today for mid in s["old"]):
        return False
    return True


def answer(phone: str, text: str, send, today: date | None = None) -> str | None:
    """YES or NO to a proposed swap. Returns the reply, or None if this phone has no swap waiting."""
    from .deals import NO, YES
    word = text.strip().lower().rstrip("!.")
    if word not in YES | NO or not phone:
        return None
    for s in sorted(_pending(), key=lambda s: s["at"]):
        mine = [p for p in s["parties"] if p["phone"] == phone and not p["ok"]]
        if not mine:
            continue
        others = [p for p in s["parties"] if p["phone"] != phone]
        if word in NO:
            s["status"] = "declined"
            store.DB.put(KIND, s["id"], s)
            for p in others:
                send(p["phone"], f"The route change for {s['kg']:.0f} kg {s['crop']} is off. "
                                 "Your current deal stays exactly as agreed.", s["id"])
            return "OK, nothing changes. Your current deal stays as agreed."
        for p in mine:
            p["ok"] = True
        store.DB.put(KIND, s["id"], s)
        if not all(p["ok"] for p in s["parties"]):
            return "Thanks. We switch once everyone involved says YES; until then your current deal stands."
        if not execute(s, send, today):
            return "Too late to switch: the load is already booked or leaving. Your current deal stays as agreed."
        return "Everyone agreed. Switched."
    return None


def execute(s: dict, send, today: date | None = None) -> bool:
    """Everyone said YES: shrink or cancel the old deals and confirm the new ones, then re-plan."""
    from . import deals
    today = today or date.today()
    prices = store.prices()
    L = {l.id: l for l in store.listings()}
    O = {o.id: o for o in store.orders()}
    old = [m for m in store.matches() if m.id in s["old"]]
    if not _still_ok(s, today):
        s["status"] = "expired"
        store.DB.put(KIND, s["id"], s)
        return False
    if s.get("open_listing"):
        open_l, open_o = _open()
        free_l = next((l.remaining_kg for l in open_l if l.id == s["open_listing"]), 0) + s["kg"]
        free_o = next((o.remaining_kg for o in open_o if o.id == s["open_order"]), 0) + s["kg"]
        if min(free_l, free_o) < s["kg"] - 1e-6:  # sold to someone else in the meantime
            s["status"] = "expired"
            store.DB.put(KIND, s["id"], s)
            return False
    legs = [_leg(L[n["listing_id"]], O[n["order_id"]], s["kg"], prices) for n in s["new"]]
    if not all(legs):
        s["status"] = "expired"
        store.DB.put(KIND, s["id"], s)
        return False
    for m in old:
        if m.status == "confirmed":  # give the kg back; the new deals take them again
            for kind, rid in (("listings", m.listing_id), ("orders", m.order_id)):
                doc = store.get(kind, rid)
                doc["remaining_kg"] += s["kg"]
                store.put(kind, doc)
        left = m.qty_kg - s["kg"]
        if left <= 1e-6:
            m.status, m.note, m.shipment_id = "cancelled", "rerouted", None
        else:
            r = _leg(L[m.listing_id], O[m.order_id], left, prices)
            keep = m.model_dump(include={"id", "status", "farmer_ok", "buyer_ok", "note"})
            m = r.model_copy(update=keep)  # the rest of the deal, priced for its new size
        store.put_match(m)
    for leg in legs:
        leg.id, leg.note = uuid.uuid4().hex[:8], "rerouted"
        deals.confirm(leg)
    s["status"], s["done_at"] = "done", datetime.now(timezone.utc).isoformat()
    store.DB.put(KIND, s["id"], s)
    deals.plan()  # re-bundle shipments around the new routes
    f1, b1, f2, b2 = s["parties"]
    for p, body in ((f1, f"you now sell to {b2['name']}"), (f2, f"you now sell to {b1['name']}"),
                    (b1, f"yours now comes from {f2['name']}"), (b2, f"yours now comes from {f1['name']}")):
        send(p["phone"], f"Route changed for {s['kg']:.0f} kg {s['crop']}: {body}. Everyone agreed.", s["id"])
    return True
