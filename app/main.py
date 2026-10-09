"""Govi Market API."""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from . import parser, store
from .lanes import load_lanes
from .matcher import impact, match
from .pricing import load_prices

app = FastAPI(title="Govi Market")
LANES = load_lanes()
PRICES = load_prices()


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/intake")
async def intake(text: Optional[str] = Form(None), file: Optional[UploadFile] = File(None),
                 today: Optional[date] = Form(None)):
    """Any message from anyone: photo, voice note or text."""
    media = await file.read() if file else None
    if not text and not media:
        raise HTTPException(400, "send text or a file")
    today = today or date.today()
    parsed = parser.parse(text=text, media=media, mime_type=file.content_type if file else None,
                          today=today.isoformat())
    created = store.record(parsed, default_date=today)
    needs_clarification = parsed.confidence < 0.7 or (parsed.role == "farmer" and not parsed.location)
    return {"parsed": parsed, "created": created, "needs_clarification": needs_clarification}


@app.post("/plan")
def plan():
    """Match open listings to open orders and pick transport."""
    matches, surplus = match(list(store.LISTINGS.values()), list(store.ORDERS.values()), LANES, PRICES)
    return {"matches": matches, "surplus": surplus, "impact": impact(matches)}


@app.get("/state")
def state():
    return {"listings": list(store.LISTINGS.values()), "orders": list(store.ORDERS.values()),
            "inbox": store.INBOX}
