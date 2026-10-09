"""Greedy allocation of harvest listings to buyer orders.

Deterministic on purpose: Gemini explains the plan, it does not decide who gets paid."""
from __future__ import annotations

from datetime import datetime, timedelta

import uuid
from collections import defaultdict

from .lanes import _norm, arrival, lane_cost, pick_lane
from .pricing import split
from .schemas import Lane, Listing, Match, Order, Shipment


def match(listings: list[Listing], orders: list[Order], lanes: list[Lane],
          prices: dict[str, dict], blocked: set[tuple[str, str]] = frozenset()) -> tuple[list[Match], list[Listing]]:
    """Fill earliest-deadline orders first from the listing that pays the farmer most.

    `blocked` holds (listing_id, order_id) pairs a farmer or buyer already declined.
    Returns (matches, surplus listings with stock left over)."""
    listings = [l.model_copy() for l in listings]
    matches: list[Match] = []
    for order in sorted(orders, key=lambda o: o.needed_by):
        remaining = order.remaining_kg
        price = prices.get(order.crop)
        if price is None:
            continue
        while remaining > 0:
            best = None
            for l in listings:
                if l.crop != order.crop or l.remaining_kg <= 0 or l.ready_on > order.needed_by \
                        or (l.id, order.id) in blocked:
                    continue
                kg = min(remaining, l.remaining_kg)
                ship_on = max(l.ready_on, order.needed_by - timedelta(days=1))
                lane = None
                transport = 0.0
                if l.location.lower() != order.location.lower():
                    lane = pick_lane(lanes, origin=l.location, dest=order.location,
                                     kg=kg, ship_on=ship_on, needed_by=order.needed_by)
                    if lane is None:
                        continue
                    transport = round(lane_cost(lane, kg) / kg, 1)
                money = split(price, transport)
                if not money["farmer_better_off"]:
                    continue
                if best is None or money["farmer_gets"] > best[3]["farmer_gets"]:
                    best = (l, kg, lane, money, transport)
            if best is None:
                break
            l, kg, lane, money, transport = best
            l.remaining_kg -= kg
            remaining -= kg
            matches.append(Match(
                listing_id=l.id, order_id=order.id, farmer=l.farmer, buyer=order.buyer,
                crop=order.crop, qty_kg=kg, lane=lane, transport_lkr_per_kg=transport,
                solo_transport_lkr_per_kg=transport, solo_lane=lane, needed_by=order.needed_by,
                ship_on=max(l.ready_on, order.needed_by - timedelta(days=1)),
                farmer_gets_lkr_per_kg=money["farmer_gets"],
                buyer_pays_lkr_per_kg=money["buyer_pays"],
                collector_pays_lkr_per_kg=money["collector"],
                market_retail_lkr_per_kg=money["retail"],
            ))
    surplus = [l for l in listings if l.remaining_kg > 0]
    return matches, surplus


def bundle(matches: list[Match], lanes: list[Lane], prices: dict[str, dict]) -> list[Shipment]:
    """Put loads leaving the same town for the same city on the same day into one consignment.

    For each group, try every lane on the route with the combined weight, keep the cheapest one
    that still meets every buyer's deadline and fits the load, and split its cost by kg. A bigger
    load can switch mode (for example to a shared lorry), and the fixed handling and pickup costs
    are paid once instead of once per farmer. Updates each match's transport and farmer price."""
    groups: dict[tuple, list[Match]] = defaultdict(list)
    for m in matches:
        if m.lane and m.ship_on:
            groups[(_norm(m.lane.origin), _norm(m.lane.dest), m.ship_on)].append(m)
    shipments = []
    for (_, _, ship_on), group in groups.items():
        for m in group:
            m.solo_transport_lkr_per_kg = m.solo_transport_lkr_per_kg or m.transport_lkr_per_kg
        total = sum(m.qty_kg for m in group)
        solo = sum(m.solo_transport_lkr_per_kg * m.qty_kg for m in group)
        deadline = min(m.needed_by for m in group)
        cutoff = datetime(deadline.year, deadline.month, deadline.day, 8, 0)
        origin, dest = group[0].lane.origin, group[0].lane.dest
        options = [l for l in lanes if _norm(l.origin) == _norm(origin) and _norm(l.dest) == _norm(dest)
                   and l.max_kg >= total and arrival(l, ship_on) <= cutoff]
        if not options:
            continue  # too heavy for any single lane; loads travel separately
        lane = min(options, key=lambda l: lane_cost(l, total))
        cost = lane_cost(lane, total)
        if cost > solo and len(group) > 1:
            continue
        per_kg = round(cost / total, 1)
        ratio = cost / solo if solo else 1.0
        sid = uuid.uuid4().hex[:8]
        for m in group:
            # Everyone's share falls by the same ratio, so no farmer pays more than shipping alone.
            m.lane, m.shipment_id = lane, sid
            m.transport_lkr_per_kg = round(m.solo_transport_lkr_per_kg * ratio, 1)
            m.farmer_gets_lkr_per_kg = split(prices[m.crop], m.transport_lkr_per_kg)["farmer_gets"]
        shipments.append(Shipment(
            id=sid, origin=origin, dest=dest, ship_on=ship_on, lane=lane,
            match_ids=[m.id for m in group], farmers=sorted({m.farmer for m in group}),
            buyers=sorted({m.buyer for m in group}), total_kg=total, cost_lkr=round(cost),
            lkr_per_kg=per_kg, solo_cost_lkr=round(solo), saved_lkr=round(max(solo - cost, 0))))
    return shipments


def impact(matches: list[Match]) -> dict:
    """Totals for the ops screen and the pitch."""
    kg = sum(m.qty_kg for m in matches)
    transport_saved = sum((m.solo_transport_lkr_per_kg - m.transport_lkr_per_kg) * m.qty_kg for m in matches)
    farmer_extra = sum((m.farmer_gets_lkr_per_kg - m.collector_pays_lkr_per_kg) * m.qty_kg for m in matches)
    buyer_saved = sum((m.market_retail_lkr_per_kg - m.buyer_pays_lkr_per_kg) * m.qty_kg for m in matches)
    return {"kg_matched": kg, "farmer_extra_lkr": round(farmer_extra), "buyer_saved_lkr": round(buyer_saved),
            "transport_saved_lkr": round(transport_saved)}
