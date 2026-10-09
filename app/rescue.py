"""Missed-departure rescue: a buyer must not run out because a bus left without the load.

Three steps, cheapest first, all decided in code:
1. Re-route: a later bus, train or lorry on the same route that still arrives on time.
   Govi pays any extra freight; the farmer's price does not change.
2. Re-source: cancel the stranded loads and match the buyers to other farmers who can still
   make it (they get the usual YES/NO message).
3. Backup buy: whatever is still short is bought at the destination's wholesale market at
   today's agent-reported wholesale price. The buyer keeps the agreed price; Govi covers the gap.
Stranded farmers get their kg back on offer, so the unsold-produce check picks them up.
Gemini only words the messages (app/messages.py)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from . import deals, messages, shipping, store
from .lanes import DEST_PICKUP_LKR, _norm, lane_cost
from .schemas import Match, Shipment

BACKUP_MARKET = {"colombo": "Peliyagoda wholesale market", "kandy": "Kandy wholesale market"}
CAN_MISS = ("booked", "loaded")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mode(lane) -> str:
    return shipping.MODE_NAME.get(lane.mode, lane.mode)


def _tell(send, phone, lang, purpose, facts, fallback, mid):
    if phone:
        send(phone, messages.write(purpose, facts, lang or "en", fallback), mid)


def missed(sid: str, send=None, reason: str = "missed the departure") -> dict:
    send = send or deals._send
    x = next((s for s in store.shipments() if s.id == sid), None)
    if x is None:
        raise KeyError(sid)
    if x.status not in CAN_MISS:
        raise ValueError(f"only a booked or loaded shipment can miss its departure (this one is {x.status})")
    loads = [m for m in store.matches() if m.id in x.match_ids and m.status == "confirmed"]
    deadline = min(m.needed_by for m in loads)
    old = f"{_mode(x.lane)} at {x.lane.departs}"
    rescue = {"at": _now(), "reason": reason, "missed": old, "extra_cost_lkr": 0, "steps": []}

    later = shipping.backup_lanes(x, deals.LANES, deadline)
    if later:
        lane = later[0]
        cost = lane_cost(lane, x.total_kg)
        new = x.model_copy(update={
            "id": uuid.uuid4().hex[:8], "lane": lane, "status": "booked", "cost_lkr": round(cost),
            "lkr_per_kg": round(cost / x.total_kg, 1), "rescue": {}, "events": []})
        new.schedule = shipping.schedule(lane, x.ship_on)
        new.ref = shipping.booking_ref(new)
        new.events = [{"status": "booked", "at": _now(), "scheduled": new.schedule["booked"],
                       "note": f"re-routed after {old} was missed"}]
        store.put_shipment(new)
        for m in loads:
            m.lane, m.shipment_id = lane, new.id
            store.put_match(m)
        extra = max(round(cost - x.cost_lkr), 0)
        rescue.update(action="rerouted", new_shipment=new.id, extra_cost_lkr=extra,
                      summary=f"Moved to {_mode(lane)} at {lane.departs}, still on time. Govi pays Rs {extra:,} extra.")
        rescue["steps"].append(rescue["summary"])
        arrive = shipping._fmt(new.schedule["arrived"])
        for m in loads:
            l, o = store.get("listings", m.listing_id) or {}, store.get("orders", m.order_id) or {}
            facts = dict(crop=m.crop, kg=round(m.qty_kg), missed=old, new_transport=_mode(lane), departs=lane.departs,
                         drop_off=lane.pickup or x.origin, arrives=arrive, buyer=m.buyer, farmer=m.farmer, ref=new.ref)
            _tell(send, l.get("phone"), l.get("lang"), "Tell the farmer their load moves to a later transport; their price stays the same.",
                  facts, f"The {old} was missed. Your {facts['kg']} kg {m.crop} now goes by {facts['new_transport']} at "
                         f"{lane.departs} from {facts['drop_off']}. Your price stays the same. Ref {new.ref}.", m.id)
            _tell(send, o.get("phone"), o.get("lang"), "Tell the buyer the load changed transport but still arrives on time.",
                  facts, f"Update: your {facts['kg']} kg {m.crop} from {m.farmer} moved to {facts['new_transport']} at "
                         f"{lane.departs}. It still arrives about {arrive}.", m.id)
    else:
        rescue["action"] = "resourced"
        short: dict[str, float] = {}
        for m in loads:
            m.status, m.note, m.shipment_id = "cancelled", f"stranded: {old} missed", None
            store.put_match(m)
            for kind, rid in (("listings", m.listing_id), ("orders", m.order_id)):
                doc = store.get(kind, rid)
                doc["remaining_kg"] += m.qty_kg
                store.put(kind, doc)
            short[m.order_id] = short.get(m.order_id, 0) + m.qty_kg
            l = store.get("listings", m.listing_id) or {}
            _tell(send, l.get("phone"), l.get("lang"), "Tell the farmer their load could not travel in time and is back on offer.",
                  dict(crop=m.crop, kg=round(m.qty_kg), missed=old),
                  f"The {old} was missed and no later transport arrives in time. Your {round(m.qty_kg)} kg {m.crop} "
                  f"is back on offer. We are finding you another buyer today.", m.id)
        before = {m.id for m in store.matches()}
        # Other farmers in the same town would ride the transport that already left.
        same_town = {(l.id, oid) for l in store.listings() if _norm(l.location) == _norm(x.origin) for oid in short}
        deals.plan(extra_blocked=same_town)
        found = [m for m in store.matches() if m.id not in before and m.order_id in short and m.status == "proposed"]
        for m in found:
            m.note = "rescue: replacement farmer"
            store.put_match(m)
            short[m.order_id] -= m.qty_kg
        if found:
            rescue["steps"].append(f"Asked {len({m.farmer for m in found})} other farmer(s) for "
                                   f"{round(sum(m.qty_kg for m in found))} kg that can still arrive on time.")
        prices = store.prices()
        backups = []
        for oid, kg in short.items():
            if kg <= 0:
                continue
            o = store.get("orders", oid)
            src = next(m for m in loads if m.order_id == oid)
            p = prices.get(src.crop, {})
            wholesale = p.get("wholesale") or round(p.get("retail", src.buyer_pays_lkr_per_kg) * 0.8)
            market = BACKUP_MARKET.get(_norm(o["location"]), f"{o['location']} wholesale market")
            b = Match(id=uuid.uuid4().hex[:8], status="confirmed", farmer_ok=True, buyer_ok=True, listing_id="backup",
                      order_id=oid, farmer=market, buyer=o["buyer"], crop=src.crop, qty_kg=kg, lane=None,
                      needed_by=src.needed_by, transport_lkr_per_kg=0, farmer_gets_lkr_per_kg=wholesale,
                      buyer_pays_lkr_per_kg=src.buyer_pays_lkr_per_kg, collector_pays_lkr_per_kg=src.collector_pays_lkr_per_kg,
                      market_retail_lkr_per_kg=src.market_retail_lkr_per_kg, note="rescue: backup buy")
            store.put_match(b)
            o["remaining_kg"] -= kg
            store.put("orders", o)
            gap = max(wholesale - src.buyer_pays_lkr_per_kg, 0) * kg + DEST_PICKUP_LKR
            rescue["extra_cost_lkr"] += round(gap)
            backups.append(b)
        if backups:
            rescue["action"] = "backup" if not found else "resourced+backup"
            rescue["steps"].append(f"Bought {round(sum(b.qty_kg for b in backups))} kg at "
                                   f"{', '.join(sorted({b.farmer for b in backups}))} so buyers are covered. "
                                   f"Govi covers Rs {rescue['extra_cost_lkr']:,}.")
        rescue["summary"] = " ".join(rescue["steps"]) or "Re-planned."
        for oid in short:
            o = store.get("orders", oid) or {}
            mine = [m for m in found + backups if m.order_id == oid]
            facts = dict(missed=old, buyer=o.get("buyer"), crop=mine[0].crop if mine else "",
                         replacements=[{"from": m.farmer, "kg": round(m.qty_kg), "how": m.note} for m in mine],
                         price_unchanged=True)
            lines = "; ".join(f"{round(m.qty_kg)} kg from {m.farmer}" for m in mine)
            _tell(send, o.get("phone"), o.get("lang"),
                  "Tell the buyer the original transport was missed and how their order is still covered at the same price.",
                  facts, f"The {old} carrying your order was missed. You are still covered: {lines}. "
                         f"Same price as agreed, arriving by your deadline.", oid)
    x.status = "missed"
    x.events.append({"status": "missed", "at": _now(), "note": reason})
    x.rescue = rescue
    store.put_shipment(x)
    return rescue
