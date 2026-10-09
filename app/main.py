"""Govi Market API."""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from . import deals, parser, replies, store, whatsapp
from .pricing import split

log = logging.getLogger("govi")
app = FastAPI(title="Govi Market")
WEB = Path(__file__).resolve().parent.parent / "web"
app.mount("/static", StaticFiles(directory=WEB), name="static")


def handle(*, text: Optional[str], media: Optional[bytes], mime_type: Optional[str],
           sender: str, today: date) -> dict:
    """One pipeline for every channel: parse, store, build a reply."""
    if text and not media:
        confirmed = deals.answer(sender, text)
        if confirmed:
            return {"parsed": None, "created": [], "needs_clarification": False, "reply": confirmed}
    parsed = parser.parse(text=text, media=media, mime_type=mime_type, today=today.isoformat())
    created = store.record(parsed, default_date=today, sender=sender)
    needs_clarification = parsed.confidence < 0.7 or (parsed.role == "farmer" and not parsed.location)
    return {"parsed": parsed, "created": created, "needs_clarification": needs_clarification,
            "reply": replies.build(parsed, store.prices())}


@app.get("/healthz")
def healthz():
    return {"ok": True, "gemini": bool(os.getenv("GEMINI_API_KEY")), "store": os.getenv("STORE", "memory"),
            "whatsapp_number": os.getenv("WHATSAPP_DISPLAY_NUMBER", "")}


@app.get("/")
def user_app():
    return FileResponse(WEB / "index.html")


@app.get("/admin")
def admin_app():
    return FileResponse(WEB / "admin.html")


@app.post("/intake")
async def intake(text: Optional[str] = Form(None), file: Optional[UploadFile] = File(None),
                 sender: str = Form("web"), today: Optional[date] = Form(None)):
    """Web upload: photo, voice note or text."""
    media = await file.read() if file else None
    if not text and not media:
        raise HTTPException(400, "send text or a file")
    return handle(text=text, media=media, mime_type=file.content_type if file else None,
                  sender=sender, today=today or date.today())


@app.get("/webhook/whatsapp")
def whatsapp_verify(mode: str = Query(alias="hub.mode"), token: str = Query(alias="hub.verify_token"),
                    challenge: str = Query(alias="hub.challenge")):
    if mode == "subscribe" and token == os.getenv("WHATSAPP_VERIFY_TOKEN"):
        return PlainTextResponse(challenge)
    raise HTTPException(403)


def _process_whatsapp(msg: whatsapp.Inbound) -> None:
    try:
        media = whatsapp.fetch_media(msg.media_id) if msg.media_id else None
        out = handle(text=msg.text, media=media, mime_type=msg.mime_type,
                     sender=msg.sender, today=date.today())
        whatsapp.send_text(msg.sender, out["reply"])
    except Exception:
        log.exception("whatsapp message failed")
        try:
            whatsapp.send_text(msg.sender, "Sorry, we could not read that. Please try again.")
        except Exception:
            log.exception("whatsapp apology failed")


@app.post("/webhook/whatsapp")
async def whatsapp_inbound(request: Request, background: BackgroundTasks):
    body = await request.body()
    if not whatsapp.verify_signature(body, request.headers.get("x-hub-signature-256")):
        raise HTTPException(403)
    for msg in whatsapp.unpack(await request.json()):
        background.add_task(_process_whatsapp, msg)  # ack Meta fast; Gemini can take seconds
    return {"ok": True}


@app.post("/plan")
def plan():
    """Match open listings to open orders, pick transport, and message both sides."""
    return deals.plan()


@app.get("/api/plan")
def latest_plan():
    """Last matching run, with each match's current confirmation status."""
    plan = store.latest_plan() or {"surplus": [], "impact": {}}
    live = [m for m in store.matches() if m.status != "declined"]
    plan["matches"] = [m.model_dump(mode="json") for m in live]
    plan["impact"] = {**plan.get("impact", {}), "confirmed": sum(m.status == "confirmed" for m in live)}
    return plan


@app.get("/api/prices")
def price_board():
    """What a farmer should get and a buyer should pay today, per crop."""
    rows = []
    for crop, p in sorted(store.prices().items()):
        money = split(p, transport_lkr_per_kg=0)
        rows.append({"crop": crop, "collector": p["collector"], "retail": p["retail"],
                     "wholesale": p.get("wholesale"), "farmer_fair": money["farmer_gets"],
                     "buyer_price": money["buyer_pays"], "source": p.get("source", "")})
    return rows


@app.get("/api/track")
def track(phone: str):
    """A sender's own listings and orders, with match status from the latest plan."""
    plan = store.latest_plan() or {"matches": []}
    def status(rid, key):
        ms = [m for m in plan["matches"] if m[key] == rid]
        return {"matched_kg": sum(m["qty_kg"] for m in ms), "matches": ms}
    return {"listings": [{**l.model_dump(mode="json"), **status(l.id, "listing_id")}
                         for l in store.listings() if l.phone == phone],
            "orders": [{**o.model_dump(mode="json"), **status(o.id, "order_id")}
                       for o in store.orders() if o.phone == phone]}


DEMO_MESSAGES = [
    ("94770000001", "Dambulla price today: carrot collector 150, beans collector 210, tomato collector 95, leeks collector 115"),
    ("94770000002", "This is Sunil, carrot 280kg ready tomorrow, Nuwara Eliya"),
    ("94770000003", "This is Kumari, leeks 150kg ready tomorrow, Nuwara Eliya"),
    ("94770000004", "This is Nimal, beans 90kg and tomato 200kg ready tomorrow, Dambulla"),
    ("94770000005", "This is Rasan, tomato 120kg ready tomorrow, Jaffna"),
    ("94770000011", "Order from Lotus Kitchen: need carrot 200kg and beans 40kg by {day}, Colombo"),
    ("94770000012", "Order from Green Spoon Hotel: need tomato 150kg and leeks 60kg by {day}, Colombo"),
    ("94770000013", "Order from Ceylon Fresh Exports: need leeks 80kg by {day}, Colombo"),
]


@app.post("/demo/seed")
def demo_seed():
    """Reset the in-memory store and replay a realistic morning of messages."""
    if os.getenv("STORE") == "firestore":
        raise HTTPException(400, "demo seed only runs on the memory store")
    store.reset()
    today = date.today()
    day = (today + timedelta(days=2)).strftime("%A")
    for phone, text in DEMO_MESSAGES:
        handle(text=text.format(day=day), media=None, mime_type=None, sender=phone, today=today)
    return plan()


@app.get("/state")
def state():
    return {"listings": store.listings(), "orders": store.orders(), "inbox": store.inbox(),
            "prices": store.prices(), "outbox": store.sent()}
