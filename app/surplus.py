"""Unsold-produce deadline: harvest still without a buyer the day before it is ready gets an offer.

The farmer is told in their language that the produce is not sold yet, with numbered options
worked out in code: a processor that pays a fixed share of today's collector price (minus
collection), a cold store nearby (fee per kg per day) to wait for a better week, or keeping it.
They reply 1, 2 or 3 on WhatsApp. Gemini only words the message."""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import messages, store
from .lanes import _norm

DATA = Path(__file__).resolve().parent.parent / "data"
# Days a crop keeps after harvest without cold storage (rough guide for the demo).
SHELF_DAYS = {"tomato": 4, "beans": 4, "leeks": 6, "green chilli": 5, "carrot": 10, "red onion": 30}
WARN_DAYS = 1  # alert when harvest is this close and still unsold
STORE_DAYS = 3  # how long a cold-store option assumes the farmer waits


def outlets() -> list[dict]:
    return json.loads((DATA / "outlets.json").read_text())


def _open_kg() -> dict[str, float]:
    held: dict[str, float] = {}
    for m in store.matches():
        if m.status == "proposed":
            held[m.listing_id] = held.get(m.listing_id, 0) + m.qty_kg
    return {l.id: l.remaining_kg - held.get(l.id, 0) for l in store.listings()}


def options_for(crop: str, location: str, prices: dict) -> list[dict]:
    """Numbered choices for one unsold load, best money first. The last option is always 'keep it'."""
    p = prices.get(crop, {})
    collector = p.get("collector", 0)
    here = _norm(location)
    procs, colds = [], []
    for o in outlets():
        if crop not in o["crops"] or here not in {_norm(s) for s in o["serves"]}:
            continue
        if o["kind"] == "processor" and collector:
            collect = 0 if _norm(o["location"]) == here else o["collect_lkr_per_kg"]
            pays = round(collector * o["pay_pct"])
            procs.append({"kind": "processor", "outlet": o["id"], "name": o["name"], "location": o["location"],
                          "pays_lkr_per_kg": pays, "collect_lkr_per_kg": collect, "net_lkr_per_kg": pays - collect,
                          "text": f"Sell all of it to {o['name']} ({o['location']}): Rs {pays - collect}/kg, they collect"})
        elif o["kind"] == "cold_store" and SHELF_DAYS.get(crop, 5) + o["max_days"] > STORE_DAYS:
            fee = o["fee_lkr_per_kg_day"]
            colds.append({"kind": "cold_store", "outlet": o["id"], "name": o["name"], "location": o["location"],
                          "fee_lkr_per_kg_day": fee, "days": STORE_DAYS,
                          "text": f"Keep it in {o['name']} for Rs {fee}/kg a day while we find a buyer"})
    opts = sorted(procs, key=lambda x: -x["net_lkr_per_kg"])[:1] + sorted(colds, key=lambda x: x["fee_lkr_per_kg_day"])[:1]
    opts.append({"kind": "keep", "text": "Keep it and sell it yourself"})
    for i, o in enumerate(opts, 1):
        o["n"] = i
    return opts


def sweep(today: date | None = None, send=None) -> list[dict]:
    """Find harvest that is nearly ready and still unsold, and send each farmer one offer."""
    from .deals import _send
    send = send or _send
    today = today or date.today()
    prices = store.prices()
    open_kg = _open_kg()
    already = {o["listing_id"] for o in store.DB.all("offers")}
    made = []
    for l in store.listings():
        kg = open_kg.get(l.id, 0)
        if kg <= 0 or l.id in already or l.ready_on > today + timedelta(days=WARN_DAYS):
            continue
        sell_by = l.ready_on + timedelta(days=SHELF_DAYS.get(l.crop, 5))
        opts = options_for(l.crop, l.location, prices)
        oid = uuid.uuid4().hex[:8]
        offer = {"id": oid, "listing_id": l.id, "farmer": l.farmer, "phone": l.phone, "lang": l.lang,
                 "crop": l.crop, "kg": kg, "location": l.location, "ready_on": l.ready_on.isoformat(),
                 "sell_by": sell_by.isoformat(), "options": opts, "status": "open", "choice": None,
                 "at": datetime.now(timezone.utc).isoformat()}
        lines = "\n".join(f"{o['n']}. {o['text']}" for o in opts)
        fallback = (f"Your {round(kg)} kg {l.crop} has no buyer yet, and it keeps until about "
                    f"{sell_by.strftime('%a %d %b')}. Choose one:\n{lines}\nReply with the number.")
        offer["message"] = messages.write(
            "Tell the farmer their produce has no buyer yet and list the numbered options exactly as given.",
            {"crop": l.crop, "kg": round(kg), "keeps_until": sell_by, "options": [o["text"] for o in opts]},
            l.lang, fallback, extra="Keep the option numbers exactly as given and end with: reply with the number.")
        store.DB.put("offers", oid, offer)
        send(l.phone, offer["message"], oid)
        made.append(offer)
    return made


def offers() -> list[dict]:
    return sorted(store.DB.all("offers"), key=lambda o: o["at"], reverse=True)


def accept(oid: str, n: int) -> dict:
    o = next((x for x in store.DB.all("offers") if x["id"] == oid), None)
    if o is None:
        raise KeyError(oid)
    if o["status"] != "open":
        return o
    pick = next((x for x in o["options"] if x["n"] == n), None)
    if pick is None:
        raise ValueError(f"no option {n}")
    o["status"], o["choice"] = "accepted", pick
    if pick["kind"] == "processor":  # cold storage keeps it on offer for buyers
        doc = store.get("listings", o["listing_id"])
        moved = min(o["kg"], doc["remaining_kg"])
        doc["remaining_kg"] -= moved
        store.put("listings", doc)
        o["rescued_kg"] = moved
    store.DB.put("offers", oid, o)
    return o


def answer(phone: str, text: str) -> str | None:
    """A farmer replying 1, 2 or 3 to their unsold-produce offer."""
    word = text.strip().rstrip(".")
    if not word.isdigit():
        return None
    mine = [o for o in offers() if o["phone"] == phone and o["status"] == "open"]
    if not mine:
        return None
    try:
        o = accept(mine[0]["id"], int(word))
    except ValueError:
        return f"Please reply with one of: {', '.join(str(x['n']) for x in mine[0]['options'])}."
    c = o["choice"]
    if c["kind"] == "processor":
        return f"Done. {c['name']} will collect {round(o['kg'])} kg {o['crop']} at Rs {c['net_lkr_per_kg']}/kg."
    if c["kind"] == "cold_store":
        return f"Done. Take your {o['crop']} to {c['name']}. We keep looking for a buyer."
    return "OK, you keep it. We will tell you if a buyer comes."


def rescued_kg() -> float:
    return sum(o.get("rescued_kg", 0) for o in store.DB.all("offers"))
