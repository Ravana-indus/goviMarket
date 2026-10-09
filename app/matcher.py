"""Greedy allocation of harvest listings to buyer orders.

Deterministic on purpose: Gemini explains the plan, it does not decide who gets paid."""
from __future__ import annotations

from datetime import timedelta

from .lanes import lane_cost, pick_lane
from .pricing import split
from .schemas import Lane, Listing, Match, Order


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
                farmer_gets_lkr_per_kg=money["farmer_gets"],
                buyer_pays_lkr_per_kg=money["buyer_pays"],
                collector_pays_lkr_per_kg=money["collector"],
                market_retail_lkr_per_kg=money["retail"],
            ))
    surplus = [l for l in listings if l.remaining_kg > 0]
    return matches, surplus


def impact(matches: list[Match]) -> dict:
    """Totals for the ops screen and the pitch."""
    kg = sum(m.qty_kg for m in matches)
    farmer_extra = sum((m.farmer_gets_lkr_per_kg - m.collector_pays_lkr_per_kg) * m.qty_kg for m in matches)
    buyer_saved = sum((m.market_retail_lkr_per_kg - m.buyer_pays_lkr_per_kg) * m.qty_kg for m in matches)
    return {"kg_matched": kg, "farmer_extra_lkr": round(farmer_extra), "buyer_saved_lkr": round(buyer_saved)}
