"""Govi Market API."""
from __future__ import annotations

import base64
import logging
import shutil
import os
from urllib.parse import quote
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from pydantic import BaseModel, Field

from . import accounts, ai, deals, parser, portal, replies, reporters, reroute, rescue, security, shipping, store, surplus, vocab, whatsapp
from .pricing import split
from .schemas import Listing

log = logging.getLogger("govi")
app = FastAPI(title="Govi Market")
WEB = Path(__file__).resolve().parent.parent / "web"
app.mount("/static", StaticFiles(directory=WEB), name="static")
app.include_router(portal.router)
app.include_router(reporters.router)
app.include_router(accounts.router)
app.middleware("http")(security.middleware)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

MAX_UPLOAD = 10 * 1024 * 1024  # WhatsApp media is at most ~16 MB; photos and voice notes are far smaller
MAX_TEXT = 2000
MEDIA_TYPES = ("image/", "audio/")


normalise_phone = vocab.phone


def _chat(phone: str, direction: str, text: str, via: str, media: str | None = None) -> None:
    store.DB.put("chat", uuid.uuid4().hex[:10], {"phone": phone, "dir": direction, "text": text, "media": media,
                                                 "via": via, "at": datetime.now(timezone.utc).isoformat()})


def handle(*, text: Optional[str], media: Optional[bytes], mime_type: Optional[str],
           sender: str, today: date, via: str = "web", auto_plan: bool = True) -> dict:
    """One pipeline for every channel: parse, store, match, build a reply."""
    if sender.isdigit():
        _chat(sender, "in", text or "", via, (mime_type or "").split("/")[0] or None)
    reply_to = None
    if text and not media:
        reply_to = reroute.answer(sender, text, deals._send) or deals.answer(sender, text) or surplus.answer(sender, text)
    if reply_to:
        out = {"parsed": None, "created": [], "needs_clarification": False, "reply": reply_to}
    else:
        parsed = parser.parse(text=text, media=media, mime_type=mime_type, today=today.isoformat())
        # Same number, same person: the account on the web and the WhatsApp chat are one.
        u = accounts.link(sender, name=parsed.sender_name, role=parsed.role, via=via)
        if u and u.get("name") and not parsed.sender_name:
            parsed.sender_name = u.get("business") or u["name"]
        created = store.record(parsed, default_date=today, sender=sender)
        needs = parsed.confidence < 0.7 or (parsed.role == "farmer" and not parsed.location)
        out = {"parsed": parsed, "created": created, "needs_clarification": needs,
               "reply": replies.build(parsed, store.prices())}
        if created and auto_plan and parsed.role in ("farmer", "buyer"):
            deals.plan()  # match straight away; both sides get their YES/NO message
    if sender.isdigit():
        _chat(sender, "out", out["reply"], via)
    return out


@app.get("/api/health")
@app.get("/healthz")  # local and tests only: Cloud Run blocks paths ending in "z" on run.app
def healthz():
    return {"ok": True, "gemini": bool(os.getenv("GEMINI_API_KEY")), "store": os.getenv("STORE", "memory"),
            "admin_locked": bool(security.admin_token()), "agent_locked": bool(security.agent_pin()),
            "auth": accounts.provider(), "demo_logins": len(accounts.demo_numbers()),
            "whatsapp": bool(os.getenv("WHATSAPP_TOKEN")),
            "whatsapp_number": os.getenv("WHATSAPP_DISPLAY_NUMBER", ""),
            "gemini_last_error": ai.last_error or None}


@app.get("/favicon.ico")
def favicon():
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" '
           'fill="#2f7d4a"/><text x="16" y="23" font-size="20" font-family="sans-serif" font-weight="700" '
           'fill="#fff" text-anchor="middle">G</text></svg>')
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


# 1x1 white PNG for the self-test photo call.
_DIAG_PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC")


@app.get("/admin/diag")
def diag():
    """Console-only self-test: one Firestore round trip and one tiny Gemini call, with the real errors."""
    out: dict = {"store": os.getenv("STORE", "memory"), "gemini_key": bool(os.getenv("GEMINI_API_KEY")),
                 "model": parser.MODEL}
    try:
        store.DB.put("diag", "ping", {"at": datetime.now(timezone.utc).isoformat()})
        store.DB.delete("diag", "ping")
        out["store_ok"] = True
    except Exception as e:
        out["store_ok"], out["store_error"] = False, f"{type(e).__name__}: {e}"[:400]
    if os.getenv("GEMINI_API_KEY"):
        try:
            p = parser.parse(text="carrot 10kg ready tomorrow, Dambulla", today=date.today().isoformat(),
                             client=parser._client())
            out["gemini_ok"], out["gemini_sample"] = True, p.model_dump(mode="json")
        except Exception as e:
            out["gemini_ok"], out["gemini_error"] = False, f"{type(e).__name__}: {e}"[:400]
        try:  # photos take a different path through Gemini than text, so test one too
            parser.parse(media=_DIAG_PNG, mime_type="image/png", today=date.today().isoformat(),
                         client=parser._client())
            out["gemini_photo_ok"] = True
        except Exception as e:
            out["gemini_photo_ok"], out["gemini_photo_error"] = False, f"{type(e).__name__}: {e}"[:400]
    out["ffmpeg"] = bool(shutil.which("ffmpeg"))
    out["gemini_last_error"] = ai.last_error or None
    return out


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


@app.get("/sim")
@app.get("/smul")
def simulator():
    """WhatsApp simulator: the same pipeline as the real webhook, for demos and testing."""
    return FileResponse(WEB / "sim.html")


@app.get("/signin")
def signin_page():
    """Phone sign-in for everyone (farmers, buyers, agents, and staff listed in ADMIN_PHONES)."""
    return FileResponse(WEB / "signin.html")


@app.get("/login")
def login_page():
    return FileResponse(WEB / "login.html")


@app.post("/login")
def login(token: str = Form(...), next: str = Form("/admin")):
    dest = next if next.startswith("/") and not next.startswith("//") else "/admin"
    if not security.admin_token() or not security._same(token, security.admin_token()):
        return RedirectResponse("/login?bad=1&next=" + quote(dest), status_code=303)
    resp = RedirectResponse(dest, status_code=303)
    resp.set_cookie(security.COOKIE, token, max_age=7 * 86400, httponly=True, samesite="lax",
                    secure=os.getenv("COOKIE_SECURE", "1") == "1")
    return resp


@app.post("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(security.COOKIE)
    return resp


@app.get("/api/towns")
def towns():
    """Towns with transport to the cities, for the harvest form."""
    origins = sorted({l.origin for l in deals.LANES})
    return {"origins": origins, "cities": sorted({l.dest for l in deals.LANES}),
            "crops": sorted(store.prices())}


class ListingIn(BaseModel):
    farmer: Optional[str] = Field(None, max_length=60)  # signed in: name and phone come from the account
    phone: Optional[str] = None
    location: str = Field(min_length=2, max_length=60)
    crop: str
    qty_kg: float = Field(gt=0, le=20000)
    ready_on: date
    lang: str = "si"


@app.post("/api/listings")
def add_listing(x: ListingIn, request: Request):
    """Harvest posted from the farmer portal. Matching runs at once.
    A signed-in farmer always posts as their own number."""
    u = accounts.current(request)
    phone = u["phone"] if u else normalise_phone(x.phone)
    farmer = (x.farmer or "").strip() or (u or {}).get("name", "")
    if not phone:
        raise HTTPException(400, "Enter a valid phone number.")
    if not farmer:
        raise HTTPException(400, "Enter your name.")
    crop = vocab.crop(x.crop)
    if crop not in store.prices():
        raise HTTPException(400, f"We don't trade {x.crop} yet.")
    if not date.today() - timedelta(days=1) <= x.ready_on <= date.today() + timedelta(days=30):
        raise HTTPException(400, "Ready date must be within the next 30 days.")
    rid = uuid.uuid4().hex[:8]
    store.put("listings", Listing(id=rid, phone=phone, lang=x.lang if x.lang in ("si", "ta", "en") else "si",
                                  farmer=farmer, location=vocab.town(x.location), crop=crop,
                                  qty_kg=x.qty_kg, ready_on=x.ready_on, remaining_kg=x.qty_kg).model_dump(mode="json"))
    deals.plan()
    mine = [m.model_dump(mode="json") for m in store.matches() if m.listing_id == rid]
    return {"id": rid, "matches": mine, "matched_kg": sum(m["qty_kg"] for m in mine)}


@app.get("/api/sim/thread")
def sim_thread(phone: str):
    """Everything sent to and from one simulator phone, oldest first."""
    p = normalise_phone(phone)
    chat = [c for c in store.DB.all("chat") if c["phone"] == p]
    if not p or not any(c["via"] == "sim" for c in chat):
        return []
    out = [{"dir": c["dir"], "text": c["text"], "media": c.get("media"), "at": c["at"]} for c in chat]
    out += [{"dir": "out", "text": o["body"], "media": None, "at": o["at"]} for o in store.sent()
            if o["to"] == p and o.get("kind") != "otp"]  # sign-in codes never show on the public simulator
    return sorted(out, key=lambda m: m["at"])


@app.post("/jobs/daily")
def daily_job(today: Optional[date] = None):
    """Run by Cloud Scheduler each morning: next week's standing orders, then unsold-produce alerts."""
    today = today or date.today()
    ran = []
    for s_ in store.DB.all("standing"):
        if s_.get("last_run") != today.isoformat() and s_["weekday"] == (today + timedelta(days=2)).strftime("%A"):
            portal.run_standing(s_["id"], today)
            store.DB.put("standing", s_["id"], {**s_, "last_run": today.isoformat()})
            ran.append(s_["id"])
    offers = surplus.sweep(today)
    return {"standing_orders_run": ran, "unsold_offers": len(offers)}


@app.post("/intake")
async def intake(text: Optional[str] = Form(None), file: Optional[UploadFile] = File(None),
                 sender: str = Form("web"), via: str = Form("web"), today: Optional[date] = Form(None)):
    """Web portal and WhatsApp simulator: photo, voice note or text."""
    text = (text or "").strip() or None
    if text and len(text) > MAX_TEXT:
        raise HTTPException(400, f"Message is too long (max {MAX_TEXT} characters).")
    media, mime = None, None
    if file and file.filename:
        mime = (file.content_type or "").split(";")[0].strip()
        if not mime.startswith(MEDIA_TYPES):
            raise HTTPException(400, "Send a photo or a voice note.")
        media = await file.read(MAX_UPLOAD + 1)
        if len(media) > MAX_UPLOAD:
            raise HTTPException(400, "That file is too big (max 10 MB).")
    if not text and not media:
        raise HTTPException(400, "Type a message or attach a photo or voice note.")
    phone = normalise_phone(sender) or "web"
    if via == "sim" and phone == "web":
        raise HTTPException(400, "Pick a phone number for the simulator.")
    try:
        return handle(text=text, media=media, mime_type=mime, sender=phone,
                      today=today or date.today(), via="sim" if via == "sim" else "web")
    except Exception:
        log.exception("intake failed")
        raise HTTPException(502, "We could not read that message just now. Please try again.")


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
                     sender=msg.sender, today=date.today(), via="whatsapp")
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
    plan["swaps"] = reroute.swaps()[:10]
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


@app.get("/api/swaps")
def swaps():
    """Better routes found after deals were agreed, newest first, with who has said YES."""
    return reroute.swaps()


@app.post("/api/swaps/{sid}/answer")
def swap_answer(sid: str, phone: str, yes: bool = True):
    """Console demo: reply YES or NO to a route change on behalf of one person in it."""
    s = next((x for x in reroute.swaps() if x["id"] == sid), None)
    if s is None:
        raise HTTPException(404, "no such route change")
    reply = reroute.answer(phone, "yes" if yes else "no", deals._send)
    if reply is None:
        raise HTTPException(409, "this person has nothing waiting on that route change")
    return {"reply": reply, "swap": next(x for x in reroute.swaps() if x["id"] == sid)}


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
def track(request: Request, phone: Optional[str] = None):
    """Your own listings and orders, with match status from the latest plan.
    Needs a phone sign-in; the console can look up any number with ?phone=."""
    phone = portal.whose(request, phone)
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
# A deal agreed earlier, then a better route shows up: Ampara corn should stay in Ampara, and
# Kurunegala corn (no route to Ampara) should go to Colombo instead of going unsold.
REROUTE_AGREED = [
    ("94770000016", "This is Ranjith, corn 50kg ready tomorrow, Ampara"),
    ("94770000017", "Order from Spice Route: need corn 50kg by {day}, Colombo"),
]
REROUTE_LATER = [
    ("94770000018", "This is Bandara, corn 50kg ready tomorrow, Kurunegala"),
    ("94770000019", "Order from Ampara Rest House: need corn 50kg by {day}, Ampara"),
]


@app.post("/demo/seed")
def demo_seed():
    """Reset the in-memory store and replay a realistic morning of messages."""
    try:
        store.reset()
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    try:
        with ai.offline():  # canned messages: built-in parser and templates, no Gemini quota spent
            return _seed()
    except Exception as e:
        log.exception("demo seed failed")
        raise HTTPException(500, f"Demo load failed: {type(e).__name__}: {e}"[:300])


def _seed():
    today = date.today()
    day = (today + timedelta(days=2)).strftime("%A")
    def send_all(messages):
        for phone, text in messages:
            handle(text=text.format(day=day), media=None, mime_type=None, sender=phone, today=today,
                   via="sim", auto_plan=False)

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
    send_all(REROUTE_AGREED)
    deals.plan()
    for m in store.matches():
        if m.status == "proposed":
            deals.confirm(m)
    # Just now: a new order waits for both sides to say YES, and new corn makes a better route.
    send_all(DEMO_MESSAGES[-1:] + REROUTE_LATER)
    deals.plan()
    return latest_plan()


@app.get("/state")
def state():
    return {"listings": store.listings(), "orders": store.orders(), "inbox": store.inbox(),
            "prices": store.prices(), "outbox": store.sent()}
