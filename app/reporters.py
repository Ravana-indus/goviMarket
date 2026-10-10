"""Price entry for market agents: today's prices typed on a phone go straight onto the price board."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import accounts, security, store
from .schemas import PriceKind

router = APIRouter()

MARKETS = ["Dambulla", "Nuwara Eliya", "Keppetipola", "Meegoda", "Peliyagoda (Manning)",
           "Narahenpita", "Thambuttegama", "Jaffna"]
# A price this far from the current board value needs the agent to confirm it.
CHECK_CHANGE = 0.35


class PriceLine(BaseModel):
    crop: str
    lkr_per_kg: float = Field(gt=0, le=5000)


class PriceReport(BaseModel):
    reporter: Optional[str] = None  # signed-in agents: name and phone come from the account
    phone: Optional[str] = None
    market: str
    kind: PriceKind
    when: Optional[date] = None
    prices: list[PriceLine]


def _check(current: Optional[float], new: float) -> bool:
    return bool(current) and abs(new - current) / current > CHECK_CHANGE


@router.get("/api/agent/board")
def board(kind: PriceKind = "wholesale", market: Optional[str] = None):
    """Current price per crop for one kind, plus what this market reported last, to prefill the form."""
    cur = store.prices()
    mine = {}
    for p in sorted(store.DB.all("prices"), key=lambda d: d["at"]):
        if p["kind"] == kind and (market is None or p["market"] == market):
            mine[p["crop"]] = p
    return {"markets": MARKETS, "crops": [{
        "crop": crop, "current": row.get(kind),
        "last_here": mine.get(crop, {}).get("lkr_per_kg"), "last_here_date": mine.get(crop, {}).get("date"),
        "source": row.get("source", ""),
    } for crop, row in sorted(cur.items())]}


@router.post("/api/agent/prices")
def report(r: PriceReport, request: Request):
    """Save today's prices from one agent. Big jumps are saved but flagged for the admin to check."""
    if not security.is_agent(request):
        raise HTTPException(401, "Wrong agent PIN.")
    u = accounts.current(request)
    if u and u.get("role") == "agent":
        r = r.model_copy(update={"phone": u["phone"], "reporter": u.get("name") or r.reporter})
    if not r.reporter or not r.phone:
        raise HTTPException(400, "Enter your name and phone number.")
    if r.market not in MARKETS:
        raise HTTPException(400, "Pick a market from the list.")
    if not r.prices:
        raise HTTPException(400, "enter at least one price")
    cur = store.prices()
    bad = [p.crop for p in r.prices if p.crop not in cur]
    if bad:
        raise HTTPException(400, f"unknown crop: {', '.join(bad)}")
    when = (r.when or date.today()).isoformat()
    now = datetime.now(timezone.utc).isoformat()
    saved = []
    for p in r.prices:
        rid = uuid.uuid4().hex[:8]
        flagged = _check(cur[p.crop].get(r.kind), p.lkr_per_kg)
        store.DB.put("prices", rid, {"id": rid, "crop": p.crop, "kind": r.kind, "lkr_per_kg": p.lkr_per_kg,
                                     "market": r.market, "reporter": r.reporter, "phone": r.phone,
                                     "date": when, "at": now, "flagged": flagged, "via": "agent app"})
        saved.append({"id": rid, "crop": p.crop, "lkr_per_kg": p.lkr_per_kg, "flagged": flagged})
    return {"saved": saved, "count": len(saved)}


@router.get("/api/agent/reports")
def reports(request: Request, phone: Optional[str] = None, limit: int = 50):
    """Latest price reports, newest first. With phone, only that agent's (needs the agent PIN)."""
    if phone is not None and not security.is_agent(request):
        raise HTTPException(401, "Wrong agent PIN.")
    rows = [p for p in store.DB.all("prices") if phone is None or p.get("phone") == phone]
    return sorted(rows, key=lambda d: d["at"], reverse=True)[:limit]


@router.post("/api/agent/reports/{rid}/{verdict}")
def review(rid: str, verdict: str):
    """Admin decision on a flagged price: approve puts it on the board, reject drops it."""
    row = next((p for p in store.DB.all("prices") if p.get("id") == rid), None)
    if row is None or verdict not in ("approve", "reject"):
        raise HTTPException(404)
    if verdict == "reject":
        store.DB.delete("prices", rid)
    else:
        store.DB.put("prices", rid, {**row, "flagged": False, "approved": True})
    return {"ok": True}
