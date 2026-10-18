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
          prices: dict[str, dict], blocked: set[tuple[str, str]] = frozenset(),
          today: date | None = None,
          booked_cap: dict[tuple, float] | None = None) -> tuple[list[Match], list[Listing]]:
    """Fill earliest-deadline orders first from the listing that pays the farmer most.

    `blocked` holds (listing_id, order_id) pairs a farmer or buyer already declined.
    Returns (matches, surplus listings with stock left over)."""
    listings = [l.model_copy() for l in listings if l.remaining_kg > 0]
    valid_orders = [o for o in orders if o.remaining_kg > 0 and (today is None or o.needed_by >= today)]
    matches: list[Match] = []
    # ponytail: deterministic tie-break on (needed_by, created_at, id)
    for order in sorted(valid_orders, key=lambda o: (o.needed_by, o.created_at or "", o.id)):
        remaining = max(0.0, order.remaining_kg)
        price = prices.get(order.crop)
        if price is None:
            continue
        while remaining > 0:
            best = None
            for l in listings:
                if l.crop != order.crop or l.remaining_kg <= 0 or l.ready_on > order.needed_by \
                        or (l.id, order.id) in blocked \
                        or (l.phone and order.phone and l.phone != "web" and l.phone == order.phone) \
                        or (l.farmer and order.buyer and l.farmer.strip().lower() not in ("unknown", "web", "") and l.farmer.strip().lower() == order.buyer.strip().lower()):
                    continue
                # ponytail: match grade if requested by buyer
                if order.grade and l.grade and l.grade.strip().lower() != order.grade.strip().lower():
                    continue
                kg = min(remaining, l.remaining_kg)
                ship_on = max(l.ready_on, order.needed_by - timedelta(days=1))
                if today and ship_on < today:
                    ship_on = today
                if ship_on > order.needed_by:
                    continue
                lane = None
                transport = 0.0
                if l.location.lower() != order.location.lower():
                    lane = pick_lane(lanes, origin=l.location, dest=order.location,
                                     kg=kg, ship_on=ship_on, needed_by=order.needed_by,
                                     booked_cap=booked_cap)
                    if lane is None:
                        continue
                    transport = round(lane_cost(lane, kg) / kg, 1)
                money = split(price, transport)
                if not money["farmer_better_off"]:
                    continue
                # ponytail: respect farmer's ask floor and buyer's bid cap
                if l.price_lkr_per_kg and money["farmer_gets"] < l.price_lkr_per_kg:
                    continue
                if order.price_lkr_per_kg and money["buyer_pays"] > order.price_lkr_per_kg:
                    continue
                if best is None or money["farmer_gets"] > best[3]["farmer_gets"]:
                    best = (l, kg, lane, money, transport, ship_on)
            if best is None:
                break
            l, kg, lane, money, transport, ship_on = best
            l.remaining_kg -= kg
            remaining -= kg
            matches.append(Match(
                listing_id=l.id, order_id=order.id, farmer=l.farmer, buyer=order.buyer,
                crop=order.crop, qty_kg=kg, lane=lane, transport_lkr_per_kg=transport,
                solo_transport_lkr_per_kg=transport, solo_lane=lane, needed_by=order.needed_by,
                ship_on=ship_on,
                farmer_gets_lkr_per_kg=money["farmer_gets"],
                buyer_pays_lkr_per_kg=money["buyer_pays"],
                collector_pays_lkr_per_kg=money["collector"],
                market_retail_lkr_per_kg=money["retail"],
            ))
    surplus = [l for l in listings if l.remaining_kg > 0]
    return matches, surplus


def why_unmatched(order: Order, listings: list[Listing], lanes: list[Lane], prices: dict[str, dict],
                  blocked: set[tuple[str, str]] = frozenset()) -> str:
    """Plain reason an order has kg nobody is supplying, checked in the same order `match` does."""
    price = prices.get(order.crop)
    if price is None:
        return f"No price for {order.crop} on the board, so it cannot be priced."
    same = [l for l in listings if l.crop == order.crop and l.remaining_kg > 0]
    if not same:
        return f"No open {order.crop} supply right now."
    if all((l.id, order.id) in blocked for l in same):
        return f"Every {order.crop} seller was already offered this order and it was declined or called off."
    ready = [l for l in same if l.ready_on <= order.needed_by and (l.id, order.id) not in blocked]
    if not ready:
        first = min(l.ready_on for l in same)
        return f"{order.crop.capitalize()} is only ready from {first:%a %d %b}, after it is needed."
    late, poor = [], []
    for l in ready:
        kg = min(order.remaining_kg, l.remaining_kg)
        ship_on = max(l.ready_on, order.needed_by - timedelta(days=1))
        transport = 0.0
        if l.location.lower() != order.location.lower():
            lane = pick_lane(lanes, origin=l.location, dest=order.location, kg=kg,
                             ship_on=ship_on, needed_by=order.needed_by)
            if lane is None:
                late.append(l)
                continue
            transport = round(lane_cost(lane, kg) / kg, 1)
        money = split(price, transport)
        if not money["farmer_better_off"]:
            poor.append((l, money, transport))
    if poor:
        l, money, transport = max(poor, key=lambda p: p[1]["farmer_gets"])
        return (f"{l.farmer} would get Rs {money['farmer_gets']:g}/kg after Rs {transport:g}/kg transport, "
                f"less than the Rs {money['collector']:g} collector price, so Govi does not offer it.")
    if late:
        l = late[0]
        return (f"No bus, train or lorry from {l.location} reaches {order.location} by 08:00 "
                f"{order.needed_by:%a %d %b} when the {order.crop} is ready {l.ready_on:%a %d %b}.")
    return "Waiting for the next matching run."


def bundle(matches: list[Match], lanes: list[Lane], prices: dict[str, dict],
           booked_cap: dict[tuple, float] | None = None,
           prev_ids: dict[tuple, str] | None = None) -> list[Shipment]:
    """Put loads leaving the same town for the same city on the same day into one consignment.

    For each group, try every lane on the route with the combined weight, keep the cheapest one
    that still meets every buyer's deadline and fits the load, and split its cost proportional to solo cost. A bigger
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
        options = []
        for l in lanes:
            if _norm(l.origin) != _norm(origin) or _norm(l.dest) != _norm(dest):
                continue
            used = (booked_cap or {}).get((_norm(l.origin), _norm(l.dest), l.mode, l.departs, ship_on), 0.0)
            if (l.max_kg - used) >= total and arrival(l, ship_on) <= cutoff:
                options.append(l)
        if not options:
            # ponytail: unbundled loads get solo shipments so ops board tracks them
            for m in group:
                if not m.shipment_id and m.lane and m.ship_on:
                    sid = (prev_ids or {}).get((m.id,)) or uuid.uuid4().hex[:8]
                    m.shipment_id = sid
                    s_cost = lane_cost(m.lane, m.qty_kg)
                    shipments.append(Shipment(
                        id=sid, origin=m.lane.origin, dest=m.lane.dest, ship_on=m.ship_on, lane=m.lane,
                        match_ids=[m.id], farmers=[m.farmer], buyers=[m.buyer], total_kg=m.qty_kg,
                        cost_lkr=round(s_cost), lkr_per_kg=round(s_cost / m.qty_kg, 1),
                        solo_cost_lkr=round(s_cost), saved_lkr=0))
            continue
        lane = min(options, key=lambda l: lane_cost(l, total))
        cost = lane_cost(lane, total)
        if cost > solo and len(group) > 1:
            for m in group:
                if not m.shipment_id and m.lane and m.ship_on:
                    sid = (prev_ids or {}).get((m.id,)) or uuid.uuid4().hex[:8]
                    m.shipment_id = sid
                    s_cost = lane_cost(m.lane, m.qty_kg)
                    shipments.append(Shipment(
                        id=sid, origin=m.lane.origin, dest=m.lane.dest, ship_on=m.ship_on, lane=m.lane,
                        match_ids=[m.id], farmers=[m.farmer], buyers=[m.buyer], total_kg=m.qty_kg,
                        cost_lkr=round(s_cost), lkr_per_kg=round(s_cost / m.qty_kg, 1),
                        solo_cost_lkr=round(s_cost), saved_lkr=0))
            continue
        per_kg = round(cost / total, 1)
        ratio = cost / solo if solo else 1.0
        sid = (prev_ids or {}).get(tuple(sorted(m.id for m in group))) or uuid.uuid4().hex[:8]
        if booked_cap is not None:
            k = (_norm(lane.origin), _norm(lane.dest), lane.mode, lane.departs, ship_on)
            booked_cap[k] = booked_cap.get(k, 0.0) + total
        for m in group:
            # Everyone's share falls by the same ratio, so no farmer pays more than shipping alone.
            m.lane, m.shipment_id = lane, sid
            m.transport_lkr_per_kg = round(m.solo_transport_lkr_per_kg * ratio, 1)
            # ponytail: confirmed matches are locked contracts; never silently reprice them
            if m.status != "confirmed":
                m.farmer_gets_lkr_per_kg = split(prices[m.crop], m.transport_lkr_per_kg)["farmer_gets"]
        shipments.append(Shipment(
            id=sid, origin=origin, dest=dest, ship_on=ship_on, lane=lane,
            match_ids=[m.id for m in group], farmers=sorted({m.farmer for m in group}),
            buyers=sorted({m.buyer for m in group}), total_kg=total, cost_lkr=round(cost),
            lkr_per_kg=per_kg, solo_cost_lkr=round(solo), saved_lkr=round(max(solo - cost, 0))))
    return shipments


def impact(matches: list[Match], shipments: list[Shipment] | None = None) -> dict:
    """Totals for the ops screen and the pitch."""
    # ponytail: backup wholesale market buys are platform cost centers, not farmer benefits
    real = [m for m in matches if m.listing_id != "backup" and not m.note.startswith("rescue: backup")]
    kg = sum(m.qty_kg for m in real)
    if shipments is not None:
        transport_saved = sum(s.saved_lkr for s in shipments if s.status != "cancelled")
    else:
        transport_saved = sum((m.solo_transport_lkr_per_kg - m.transport_lkr_per_kg) * m.qty_kg for m in real)
    farmer_extra = sum((m.farmer_gets_lkr_per_kg - m.collector_pays_lkr_per_kg) * m.qty_kg for m in real)
    buyer_saved = sum((m.market_retail_lkr_per_kg - m.buyer_pays_lkr_per_kg) * m.qty_kg for m in real)
    return {"kg_matched": kg, "farmer_extra_lkr": round(farmer_extra), "buyer_saved_lkr": round(buyer_saved),
            "transport_saved_lkr": round(transport_saved)}
