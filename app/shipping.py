"""Shipment lifecycle: planned -> booked -> loaded -> in transit -> arrived -> delivered.

Each step messages the farmers and buyers on the shipment. In the demo, an operator (or the
"simulate next step" button) advances a shipment; in production the carrier's booking reference
and the farmer's drop-off photo would drive the same steps."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from . import store
from .schemas import Lane, Shipment

STEPS = ["planned", "booked", "loaded", "in_transit", "arrived", "delivered"]
MODE_NAME = {"night_bus": "night bus", "train_parcel": "train", "sl_post": "Sri Lanka Post", "lorry": "shared lorry"}
REF_PREFIX = {"night_bus": "BUS", "train_parcel": "SLR", "sl_post": "SLP", "lorry": "LRY"}

# Sinhala and Tamil strings need a native speaker's check before the demo.
FARMER = {
    "booked": {
        "en": "Booked: bring your {kg} kg {crop} to {pickup} by {load}. It goes by {mode} at {departs}. Ref {ref}.",
        "si": "වෙන් කළා: ඔබේ {crop} කිලෝ {kg} {load} ට පෙර {pickup} වෙත ගෙනෙන්න. {departs} ට {mode} මගින් යවනවා. අංකය {ref}.",
        "ta": "பதிவு செய்யப்பட்டது: உங்கள் {crop} {kg} கிலோவை {load} க்குள் {pickup} க்கு கொண்டு வாருங்கள். {departs} மணிக்கு {mode} மூலம் செல்கிறது. எண் {ref}.",
    },
    "in_transit": {
        "en": "Your {crop} is on the way to {buyer}.",
        "si": "ඔබේ {crop} {buyer} වෙත යමින් පවතී.",
        "ta": "உங்கள் {crop} {buyer} க்கு செல்கிறது.",
    },
    "delivered": {
        "en": "Delivered to {buyer}. Rs {amount} will be paid to you.",
        "si": "{buyer} වෙත භාර දුන්නා. ඔබට රු. {amount} ගෙවනු ලැබේ.",
        "ta": "{buyer} க்கு வழங்கப்பட்டது. உங்களுக்கு ரூ. {amount} செலுத்தப்படும்.",
    },
}
BUYER = {
    "booked": "Booked: {kg} kg {crop} from {farmer} comes by {mode}, arriving about {arrive}. Ref {ref}.",
    "loaded": "Loaded: your {crop} from {farmer} is on the {mode} leaving {origin} at {departs}.",
    "in_transit": "On the way: {kg} kg {crop}, arriving about {arrive}.",
    "arrived": "Arrived in {dest}. Delivering to you shortly.",
    "delivered": "Delivered: {kg} kg {crop} from {farmer}. Reply OK if everything is fine.",
}


def schedule(lane: Lane, ship_on) -> dict[str, str]:
    hh, mm = (int(x) for x in lane.departs.split(":"))
    depart = datetime(ship_on.year, ship_on.month, ship_on.day, hh, mm)
    arrive = depart + timedelta(hours=lane.transit_hours)
    return {
        "booked": (datetime(ship_on.year, ship_on.month, ship_on.day, 18, 0) - timedelta(days=1)).isoformat(),
        "loaded": (depart - timedelta(minutes=45)).isoformat(),
        "in_transit": depart.isoformat(),
        "arrived": arrive.isoformat(),
        "delivered": (arrive + timedelta(hours=0 if lane.door_delivery else 2)).isoformat(),
    }


def booking_ref(x: Shipment) -> str:
    n = int(hashlib.sha1(x.id.encode()).hexdigest(), 16) % 9000 + 1000
    return f"{REF_PREFIX.get(x.lane.mode, 'GOV')}-{n}"


def _fmt(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%a %H:%M")


def _notify(x: Shipment, status: str, send) -> None:
    for mid in x.match_ids:
        m = next((m for m in store.matches() if m.id == mid), None)
        if not m:
            continue
        l, o = store.get("listings", m.listing_id) or {}, store.get("orders", m.order_id) or {}
        load = (datetime.fromisoformat(x.schedule["loaded"])).strftime("%a %H:%M")
        facts = dict(kg=round(m.qty_kg), crop=m.crop, farmer=m.farmer, buyer=m.buyer, origin=x.origin,
                     dest=x.dest, mode=MODE_NAME.get(x.lane.mode, x.lane.mode), departs=x.lane.departs,
                     arrive=_fmt(x.schedule["arrived"]), pickup=x.lane.pickup or x.origin, load=load, ref=x.ref,
                     amount=f"{round(m.farmer_gets_lkr_per_kg * m.qty_kg):,}")
        if status in FARMER:
            send(l.get("phone"), FARMER[status][l.get("lang", "en")].format(**facts), mid)
        if status in BUYER:
            send(o.get("phone"), BUYER[status].format(**facts), mid)


def advance(sid: str, send) -> Shipment:
    """Move a shipment one step forward and message everyone on it."""
    x = next((s for s in store.shipments() if s.id == sid), None)
    if x is None:
        raise KeyError(sid)
    if x.status == "delivered":
        return x
    if x.status == "planned":
        waiting = [m for m in store.matches() if m.id in x.match_ids and m.status != "confirmed"]
        if waiting:
            names = ", ".join(sorted({f"{m.farmer}/{m.buyer}" for m in waiting}))
            raise ValueError(f"waiting for YES from {names}")
        x.ref = booking_ref(x)
    nxt = STEPS[STEPS.index(x.status) + 1]
    x.status = nxt
    x.events.append({"status": nxt, "at": datetime.now(timezone.utc).isoformat(),
                     "scheduled": x.schedule.get(nxt)})
    store.put_shipment(x)
    _notify(x, nxt, send)
    return x
