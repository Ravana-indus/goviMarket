"""Ordering portal for business buyers: catalogue, orders, standing weekly orders."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import deals, forecast, store, vocab
from .pricing import split
from .schemas import Order

router = APIRouter()
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class Line(BaseModel):
    crop: str
    qty_kg: float = Field(gt=0, le=5000)


class OrderIn(BaseModel):
    phone: str
    business: str = Field(min_length=1, max_length=80)
    location: str = Field("Colombo", max_length=60)
    needed_by: date
    items: list[Line] = Field(max_length=20)
    repeat_weekly: bool = False


@router.get("/api/catalogue")
def catalogue():
    """What can be ordered now: open supply per crop, Govi price vs retail, and the price outlook."""
    held = {}
    for m in store.matches():
        if m.status == "proposed":
            held[m.listing_id] = held.get(m.listing_id, 0) + m.qty_kg
    fc = {r["crop"]: r for r in forecast.outlook()}
    rows = []
    for crop, p in sorted(store.prices().items()):
        open_ = [l for l in store.listings() if l.crop == crop and l.remaining_kg - held.get(l.id, 0) > 0]
        kg = sum(l.remaining_kg - held.get(l.id, 0) for l in open_)
        price = split(p, 0)["buyer_pays"]
        f = fc.get(crop, {})
        rows.append({
            "crop": crop, "available_kg": round(kg), "origins": sorted({l.location for l in open_}),
            "farmers": len({l.farmer for l in open_}),
            "ready_on": min((l.ready_on for l in open_), default=None),
            "price": price, "retail": p["retail"], "saving_pct": round((p["retail"] - price) / p["retail"] * 100),
            "signal": f.get("signal"), "next_week_price": f.get("buyer_price_next_week"),
            "advice": f.get("buyer_advice"),
        })
    return rows


def _create(o: OrderIn) -> list[str]:
    ids = []
    for line in o.items:
        rid = uuid.uuid4().hex[:8]
        store.put("orders", Order(id=rid, phone=o.phone, lang="en", buyer=o.business, location=o.location,
                                  crop=line.crop, qty_kg=line.qty_kg, needed_by=o.needed_by,
                                  remaining_kg=line.qty_kg).model_dump(mode="json"))
        ids.append(rid)
    return ids


@router.post("/api/orders")
def place_order(o: OrderIn):
    """Place an order from the portal. Matching runs at once, so the buyer sees suppliers."""
    if not o.items:
        raise HTTPException(400, "Add at least one item.")
    phone = vocab.phone(o.phone)
    if not phone:
        raise HTTPException(400, "Enter a valid WhatsApp number.")
    if not date.today() <= o.needed_by <= date.today() + timedelta(days=60):
        raise HTTPException(400, "Delivery date must be between today and 60 days ahead.")
    o = o.model_copy(update={"phone": phone, "location": vocab.town(o.location) or "Colombo",
                             "items": [Line(crop=vocab.crop(l.crop), qty_kg=l.qty_kg) for l in o.items]})
    known = store.prices()
    bad = [l.crop for l in o.items if l.crop not in known]
    if bad:
        raise HTTPException(400, f"unknown crop: {', '.join(bad)}")
    ids = _create(o)
    if o.repeat_weekly:
        sid = uuid.uuid4().hex[:8]
        store.DB.put("standing", sid, {"id": sid, **o.model_dump(mode="json", exclude={"repeat_weekly"}),
                                        "weekday": o.needed_by.strftime("%A"),
                                        "created": datetime.now(timezone.utc).isoformat()})
    deals.plan()
    mine = [m.model_dump(mode="json") for m in store.matches() if m.order_id in ids]
    return {"order_ids": ids, "matches": mine,
            "matched_kg": sum(m["qty_kg"] for m in mine), "ordered_kg": sum(l.qty_kg for l in o.items)}


@router.get("/api/standing")
def standing(phone: str):
    return [s for s in store.DB.all("standing") if s["phone"] == phone]


@router.post("/api/standing/{sid}/run")
def run_standing(sid: str, today: Optional[date] = None):
    """Create next week's order from a standing order (a weekly job in production)."""
    s = next((x for x in store.DB.all("standing") if x["id"] == sid), None)
    if s is None:
        raise HTTPException(404)
    today = today or date.today()
    target = WEEKDAYS.index(s["weekday"])
    days = (target - today.weekday()) % 7 or 7
    o = OrderIn(phone=s["phone"], business=s["business"], location=s["location"],
                needed_by=today + timedelta(days=days), items=[Line(**i) for i in s["items"]])
    return place_order(o)


_FC: dict = {}
FC_TTL = 3600  # Gemini writes the summary at most once an hour


@router.get("/api/forecast")
def get_forecast():
    import time
    rows = forecast.outlook()
    key = date.today().isoformat()
    hit = _FC.get(key)
    if not hit or time.time() - hit[0] > FC_TTL:
        try:
            summary = forecast.explain(rows)
        except Exception:
            summary = forecast.template(rows)
        _FC.clear(); _FC[key] = hit = (time.time(), summary)
    return {"summary": hit[1], "crops": rows}
