"""Govi Market API."""
from __future__ import annotations

import logging
import os
from datetime import date
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse

from . import parser, replies, store, whatsapp
from .lanes import load_lanes
from .matcher import impact, match

log = logging.getLogger("govi")
app = FastAPI(title="Govi Market")
LANES = load_lanes()


def handle(*, text: Optional[str], media: Optional[bytes], mime_type: Optional[str],
           sender: str, today: date) -> dict:
    """One pipeline for every channel: parse, store, build a reply."""
    parsed = parser.parse(text=text, media=media, mime_type=mime_type, today=today.isoformat())
    created = store.record(parsed, default_date=today, sender=sender)
    needs_clarification = parsed.confidence < 0.7 or (parsed.role == "farmer" and not parsed.location)
    return {"parsed": parsed, "created": created, "needs_clarification": needs_clarification,
            "reply": replies.build(parsed, store.prices())}


@app.get("/healthz")
def healthz():
    return {"ok": True}


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
    """Match open listings to open orders and pick transport."""
    matches, surplus = match(store.listings(), store.orders(), LANES, store.prices())
    return {"matches": matches, "surplus": surplus, "impact": impact(matches)}


@app.get("/state")
def state():
    return {"listings": store.listings(), "orders": store.orders(), "inbox": store.inbox(),
            "prices": store.prices()}
