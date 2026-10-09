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

from . import deals, parser, portal, replies, reporters, rescue, shipping, store, surplus, whatsapp
from .pricing import split

log = logging.getLogger("govi")
app = FastAPI(title="Govi Market")
WEB = Path(__file__).resolve().parent.parent / "web"
app.mount("/static", StaticFiles(directory=WEB), name="static")
app.include_router(portal.router)
app.include_router(reporters.router)


def handle(*, text: Optional[str], media: Optional[bytes], mime_type: Optional[str],
           sender: str, today: date) -> dict:
    """One pipeline for every channel: parse, store, build a reply."""
    if text and not media:
        confirmed = deals.answer(sender, text) or surplus.answer(sender, text)
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


@app.get("/business")
def business_app():
    return FileResponse(WEB / "business.html")


@app.get("/agent")
def agent_app():
    return FileResponse(WEB / "agent.html")


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
    """Last matching run, with each match's current status, live surplus and rescue totals."""
    plan = store.latest_plan() or {"surplus": [], "impact": {}}
    live = [m for m in store.matches() if m.status not in ("declined", "cancelled")]
    plan["matches"] = [m.model_dump(mode="json") for m in live]
    ships = sorted(store.shipments(), key=lambda x: x.schedule.get("in_transit", ""))
    by_id = {m.id: m for m in live}
    out = []
    for x in ships:
        row = x.model_dump(mode="json")
        due = [by_id[i].needed_by for i in x.match_ids if i in by_id and by_id[i].needed_by]
        if x.status in rescue.CAN_MISS + ("planned",) and due:
            alt = shipping.backup_lanes(x, deals.LANES, min(due))
            row["backup"] = f"{shipping.MODE_NAME[alt[0].mode]} {alt[0].departs}" if alt else ""
        out.append(row)
    plan["shipments"] = out
    open_kg = surplus._open_kg()
    offered = {o["listing_id"]: o for o in surplus.offers()}
    plan["surplus"] = [{**l.model_dump(mode="json"), "remaining_kg": open_kg[l.id], "offer": offered.get(l.id)}
                       for l in store.listings() if open_kg.get(l.id, 0) > 0]
    missed = [x.rescue for x in ships if x.status == "missed"]
    plan["impact"] = {**plan.get("impact", {}), "confirmed": sum(m.status == "confirmed" for m in live),
                      "surplus_kg": sum(r["remaining_kg"] for r in plan["surplus"]),
                      "surplus_rescued_kg": surplus.rescued_kg(), "rescues": len(missed),
                      "rescue_cost_lkr": sum(r.get("extra_cost_lkr", 0) for r in missed)}
    return plan


@app.post("/shipments/{sid}/missed")
def shipment_missed(sid: str, reason: str = "missed the departure"):
    """The load did not make its bus, train or lorry: re-route, re-source or backup-buy."""
    try:
        return rescue.missed(sid, reason=reason)
    except KeyError:
        raise HTTPException(404, "no such shipment")
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.post("/surplus/sweep")
def surplus_sweep(today: Optional[date] = None):
    """Tell every farmer whose harvest is nearly ready and still unsold, with numbered options."""
    return surplus.sweep(today)


@app.get("/api/offers")
def surplus_offers():
    return surplus.offers()


@app.post("/api/offers/{oid}/accept/{n}")
def surplus_accept(oid: str, n: int):
    try:
        return surplus.accept(oid, n)
    except KeyError:
        raise HTTPException(404, "no such offer")
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/shipments/{sid}/advance")
def advance_shipment(sid: str):
    """Move a shipment to its next step (booked, loaded, in transit, arrived, delivered)."""
    try:
        return deals.advance_shipment(sid)
    except KeyError:
        raise HTTPException(404, "no such shipment")
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.post("/demo/advance-all")
def advance_all():
    """Demo control: push every shipment that can move one step forward."""
    moved = []
    for x in store.shipments():
        try:
            if x.status not in ("delivered", "missed"):
                moved.append(deals.advance_shipment(x.id).id)
        except ValueError:
            pass
    return {"moved": moved}


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
    ships = {x.id: x.model_dump(mode="json") for x in store.shipments()}
    live = [m.model_dump(mode="json") for m in store.matches() if m.status != "declined"]
    def status(rid, key):
        ms = [{**m, "shipment": ships.get(m["shipment_id"])} for m in live if m[key] == rid]
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
    ("94770000005", "This is Rasan, tomato 120kg and red onion 150kg ready tomorrow, Jaffna"),
    ("94770000008", "This is Kamala, tomato 250kg ready tomorrow, Dambulla"),
    ("94770000009", "This is Sita, green chilli 25kg ready tomorrow, Badulla"),
    ("94770000006", "This is Priya, carrot 60kg ready tomorrow, Nuwara Eliya"),
    ("94770000007", "This is Ajith, beans 45kg ready tomorrow, Nuwara Eliya"),
    ("94770000011", "Order from Lotus Kitchen: need carrot 200kg and beans 40kg and red onion 100kg by {day}, Colombo"),
    ("94770000012", "Order from Green Spoon Hotel: need tomato 150kg and leeks 60kg and green chilli 20kg by {day}, Colombo"),
    ("94770000013", "Order from Ceylon Fresh Exports: need leeks 80kg and tomato 200kg by {day}, Colombo"),
    ("94770000015", "Order from Hill View Hotel: need tomato 100kg and beans 30kg by {day}, Kandy"),
    ("94770000014", "Order from Mango Tree Cafe: need carrot 120kg and beans 60kg by {day}, Colombo"),
]


@app.post("/demo/seed")
def demo_seed():
    """Reset the in-memory store and replay a realistic morning of messages."""
    if os.getenv("STORE") == "firestore":
        raise HTTPException(400, "demo seed only runs on the memory store")
    store.reset()
    today = date.today()
    day = (today + timedelta(days=2)).strftime("%A")
    def send_all(messages):
        for phone, text in messages:
            handle(text=text.format(day=day), media=None, mime_type=None, sender=phone, today=today)

    # Earlier this morning: deals confirmed and shipments already moving, later departures
    # further behind, so every step shows on the board.
    send_all(DEMO_MESSAGES[:-1])
    deals.plan()
    for m in store.matches():
        if m.status == "proposed":
            deals.confirm(m)
    ships = sorted(store.shipments(), key=lambda x: x.schedule["in_transit"])
    for x, n in zip(ships, [5, 3, 2, 1, 1, 1]):
        for _ in range(n):
            deals.advance_shipment(x.id)
    # Just now: a new order comes in and waits for both sides to say YES.
    send_all(DEMO_MESSAGES[-1:])
    deals.plan()
    return latest_plan()


@app.get("/state")
def state():
    return {"listings": store.listings(), "orders": store.orders(), "inbox": store.inbox(),
            "prices": store.prices(), "outbox": store.sent()}
