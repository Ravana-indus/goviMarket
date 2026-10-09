"""In-memory store. Swap for Firestore before deploy; the API only touches these functions."""
from __future__ import annotations

import uuid
from datetime import date

from .schemas import Listing, Order, ParsedMessage

LISTINGS: dict[str, Listing] = {}
ORDERS: dict[str, Order] = {}
INBOX: list[dict] = []


def reset() -> None:
    LISTINGS.clear(); ORDERS.clear(); INBOX.clear()


def record(parsed: ParsedMessage, *, default_date: date, default_buyer_location: str = "Colombo") -> list[str]:
    """Turn a parsed message into listings or orders. Returns created ids."""
    ids = []
    who = parsed.sender_name or "unknown"
    when = parsed.when or default_date
    for item in parsed.items:
        rid = uuid.uuid4().hex[:8]
        if parsed.role == "farmer":
            if not parsed.location:
                continue
            LISTINGS[rid] = Listing(id=rid, farmer=who, location=parsed.location, crop=item.crop,
                                    qty_kg=item.qty_kg, ready_on=when, remaining_kg=item.qty_kg)
        elif parsed.role == "buyer":
            ORDERS[rid] = Order(id=rid, buyer=who, location=parsed.location or default_buyer_location,
                                crop=item.crop, qty_kg=item.qty_kg, needed_by=when, remaining_kg=item.qty_kg)
        else:
            continue
        ids.append(rid)
    INBOX.append({"parsed": parsed.model_dump(mode="json"), "created": ids})
    return ids
