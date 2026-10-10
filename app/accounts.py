"""Accounts: the mobile number is the identity. Sign in, a profile with a role, sign out.

Two ways to prove you own the number:
- Firebase Authentication phone OTP (FIREBASE_API_KEY set): the browser gets the SMS code from
  Firebase and sends us the Firebase ID token; we verify it and take the number from it.
- Govi's own 6-digit code (no Firebase config): sent on WhatsApp when that is configured.
  Without WhatsApp it only reaches the console outbox, so staff can read it out in a demo.
  It never shows in the public /sim page: anyone can type any number there.
Demo numbers (AUTH_DEMO_NUMBERS; on by default when ALLOW_RESET=1) take a fixed code, no SMS.

A session is a random token in an httponly cookie. The server stores only its hash, so signing
out really ends it. WhatsApp, SMS and the simulator use the same number, so everything a person
sent before they signed in is already theirs."""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from . import store, vocab

log = logging.getLogger("govi.accounts")
router = APIRouter()

COOKIE = "govi_session"
SESSION_DAYS = 30
CODE_TTL = 300          # seconds a sign-in code stays valid
CODE_TRIES = 5          # wrong guesses before the code is burnt
SENDS_PER_10_MIN = 3    # codes sent to one number per 10 minutes
ROLES = ("farmer", "buyer", "agent")
LANGS = ("si", "ta", "en")
# Who the demo numbers are the first time they sign in (same people as the demo morning and /sim).
DEMO_PEOPLE = {
    "94770000002": {"name": "Sunil", "role": "farmer", "location": "Nuwara Eliya", "lang": "si"},
    "94770000014": {"name": "Mango Tree Cafe", "role": "buyer", "business": "Mango Tree Cafe",
                    "location": "Colombo", "lang": "en"},
    "94770000001": {"name": "Kamal", "role": "agent", "market": "Dambulla", "lang": "si"},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _secure() -> bool:
    return os.getenv("COOKIE_SECURE", "1") == "1"


# ---- configuration

def firebase_config() -> dict | None:
    key = os.getenv("FIREBASE_API_KEY", "")
    project = os.getenv("FIREBASE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT", "")
    if not key or not project:
        return None
    return {"apiKey": key, "projectId": project,
            "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN") or f"{project}.firebaseapp.com"}


def provider() -> str:
    return "firebase" if firebase_config() else "govi"


def demo_code() -> str:
    return os.getenv("AUTH_DEMO_CODE", "123456")


def demo_numbers() -> list[str]:
    raw = os.getenv("AUTH_DEMO_NUMBERS")
    if raw is None:  # unset: on for a demo deployment, off for real users
        raw = ",".join(DEMO_PEOPLE) if os.getenv("ALLOW_RESET") == "1" else ""
    return [p for p in (vocab.phone(x) for x in raw.split(",")) if p]


def admin_phones() -> set[str]:
    raw = os.getenv("ADMIN_PHONES", "").replace(";", ",")  # deploy.sh joins with ; (gcloud splits on ,)
    return {p for p in (vocab.phone(x) for x in raw.split(",")) if p}


# ---- users

def user(phone: str | None) -> dict | None:
    return store.DB.one("users", phone) if phone else None


def _complete(u: dict) -> bool:
    return bool(u.get("name") and u.get("role"))


def public(u: dict) -> dict:
    keys = ("phone", "name", "role", "lang", "location", "business", "market", "created", "last_login")
    return {k: u.get(k) for k in keys} | {"complete": _complete(u), "admin": u["phone"] in admin_phones()}


def link(phone: str, *, name: str | None, role: str | None, via: str) -> dict | None:
    """A message came in from this number (WhatsApp, SMS, simulator): remember who they are, so
    signing in on the web later finds their name and role already filled in. Returns the user."""
    if not phone.isdigit():
        return None
    u = user(phone)
    if u is None:
        u = {"phone": phone, "name": name or "", "role": role if role in ("farmer", "buyer") else "",
             "lang": "", "created": _now().isoformat(), "channel": via}
        store.DB.put("users", phone, u)
    elif (not u.get("name") and name) or (not u.get("role") and role in ("farmer", "buyer")):
        u = {**u, "name": u.get("name") or name or "", "role": u.get("role") or role}
        store.DB.put("users", phone, u)
    return u


# ---- sessions

def _session_doc(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE, "")
    if not token:
        return None
    key = _hash(token)
    s = store.DB.one("sessions", key)
    if s and s["expires"] < _now().isoformat():
        store.DB.delete("sessions", key)
        return None
    return s


def current(request: Request) -> dict | None:
    """The signed-in user for this request, or None."""
    if not hasattr(request.state, "user"):
        s = _session_doc(request)
        request.state.user = user(s["phone"]) if s else None
    return request.state.user


def require(request: Request) -> dict:
    u = current(request)
    if u is None:
        raise HTTPException(401, "Please sign in with your mobile number.")
    return u


def _start_session(resp: Response, phone: str, request: Request) -> None:
    token = secrets.token_urlsafe(32)
    now = _now()
    store.DB.put("sessions", _hash(token), {
        "id": _hash(token), "phone": phone, "created": now.isoformat(),
        "expires": (now + timedelta(days=SESSION_DAYS)).isoformat(),
        "agent": (request.headers.get("user-agent") or "")[:120]})
    resp.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax", secure=_secure())


def _end_sessions(phone: str) -> int:
    mine = [s for s in store.DB.all("sessions") if s["phone"] == phone]
    for s in mine:
        store.DB.delete("sessions", s["id"])
    return len(mine)


# ---- proving the number

def _firebase_phone(id_token: str) -> str:
    """Verify a Firebase ID token (signature, expiry, audience) and return its phone number."""
    from google.auth.transport import requests as greq
    from google.oauth2 import id_token as gid
    cfg = firebase_config()
    if not cfg:
        raise HTTPException(400, "Phone sign-in through Firebase is not set up.")
    try:
        claims = gid.verify_firebase_token(id_token, greq.Request(), audience=cfg["projectId"])
    except Exception as e:
        log.warning("firebase token rejected: %s", e)
        raise HTTPException(401, "That sign-in has expired. Please try again.")
    phone = vocab.phone(claims.get("phone_number"))
    if not phone:
        raise HTTPException(401, "That sign-in has no phone number.")
    return phone


def _send_code(phone: str, code: str) -> str:
    from . import whatsapp
    text = f"Your Govi sign-in code is {code}. It works for 5 minutes. Never share it."
    if os.getenv("WHATSAPP_TOKEN"):
        try:
            whatsapp.send_text(phone, text)
            store.outbox(phone, "Sign-in code sent on WhatsApp.", kind="otp")
            return "whatsapp"
        except Exception:
            log.exception("sign-in code over WhatsApp failed")
    store.outbox(phone, text, kind="otp")  # console only; kept out of the public simulator
    return "console"


def _check_code(phone: str, code: str) -> None:
    if phone in demo_numbers():
        if hmac.compare_digest(code, demo_code()):
            return
        raise HTTPException(401, "That code is not right.")
    row = store.DB.one("otp", phone)
    if not row or row.get("used") or row["expires"] < time.time():
        raise HTTPException(401, "That code has expired. Ask for a new one.")
    if row["tries"] >= CODE_TRIES:
        raise HTTPException(429, "Too many wrong codes. Ask for a new one.")
    if not hmac.compare_digest(_hash(phone + ":" + code), row["hash"]):
        store.DB.put("otp", phone, {**row, "tries": row["tries"] + 1})
        raise HTTPException(401, "That code is not right.")
    store.DB.put("otp", phone, {**row, "used": True})


class StartIn(BaseModel):
    phone: str


class VerifyIn(BaseModel):
    phone: Optional[str] = None
    code: Optional[str] = Field(None, max_length=10)
    id_token: Optional[str] = Field(None, max_length=4096)


class ProfileIn(BaseModel):
    name: Optional[str] = Field(None, max_length=80)
    role: Optional[Literal["farmer", "buyer", "agent"]] = None
    lang: Optional[Literal["si", "ta", "en"]] = None
    location: Optional[str] = Field(None, max_length=60)
    business: Optional[str] = Field(None, max_length=80)
    market: Optional[str] = Field(None, max_length=60)
    agent_pin: Optional[str] = Field(None, max_length=20)


@router.get("/api/auth/config")
def config():
    """What the sign-in screen needs: which provider, Firebase web config, and the demo logins."""
    demo = [{"phone": p, "code": demo_code(), **{k: v for k, v in DEMO_PEOPLE.get(p, {}).items()
                                                 if k in ("name", "role")}} for p in demo_numbers()]
    return {"provider": provider(), "firebase": firebase_config(), "demo": demo}


@router.post("/api/auth/start")
def start(x: StartIn):
    """Send a sign-in code (Govi's own codes). With Firebase the browser asks Firebase instead."""
    phone = vocab.phone(x.phone)
    if not phone:
        raise HTTPException(400, "Enter a valid mobile number.")
    if phone in demo_numbers():
        return {"phone": phone, "sent": False, "demo": True}
    if provider() == "firebase":
        raise HTTPException(400, "Codes come from Firebase on this site; reload the page.")
    row = store.DB.one("otp", phone) or {}
    recent = [t for t in row.get("sent", []) if time.time() - t < 600]
    if len(recent) >= SENDS_PER_10_MIN:
        raise HTTPException(429, "We already sent a few codes. Please wait 10 minutes.")
    code = f"{secrets.randbelow(10**6):06d}"
    store.DB.put("otp", phone, {"phone": phone, "hash": _hash(phone + ":" + code), "tries": 0,
                                "expires": time.time() + CODE_TTL, "sent": recent + [time.time()]})
    return {"phone": phone, "sent": True, "channel": _send_code(phone, code)}


@router.post("/api/auth/verify")
def verify(x: VerifyIn, request: Request, response: Response):
    """Prove the number (Firebase ID token, or phone + code), then open a session.
    `new` is true when the profile still needs a name and role (registration)."""
    if x.id_token:
        phone = _firebase_phone(x.id_token)
    else:
        phone = vocab.phone(x.phone)
        if not phone or not x.code:
            raise HTTPException(400, "Enter your mobile number and the code.")
        if provider() == "firebase" and phone not in demo_numbers():
            raise HTTPException(400, "Codes come from Firebase on this site; reload the page.")
        _check_code(phone, x.code.strip())
    now = _now().isoformat()
    u = user(phone) or {"phone": phone, "name": "", "role": "", "lang": "", "created": now, "channel": "web"}
    if phone in demo_numbers():  # demo people arrive with their profile filled in
        u = {**DEMO_PEOPLE.get(phone, {}), **{k: v for k, v in u.items() if v}}
    u = {**u, "verified": True, "last_login": now}
    store.DB.put("users", phone, u)
    _start_session(response, phone, request)
    return {"user": public(u), "new": not _complete(u)}


@router.post("/api/auth/logout")
def logout(request: Request, response: Response):
    s = _session_doc(request)
    if s:
        store.DB.delete("sessions", s["id"])
    response.delete_cookie(COOKIE)
    return {"ok": True}


@router.post("/api/auth/logout-all")
def logout_all(request: Request, response: Response):
    """Sign out on every phone and computer (lost phone, shared device)."""
    u = require(request)
    n = _end_sessions(u["phone"])
    response.delete_cookie(COOKIE)
    return {"ok": True, "ended": n}


@router.get("/api/me")
def me(request: Request):
    return public(require(request))


@router.put("/api/me")
def update_me(x: ProfileIn, request: Request):
    """Fill in or change the profile. Becoming a market agent needs the agent PIN once."""
    from . import security
    u = require(request)
    data = x.model_dump(exclude_none=True, exclude={"agent_pin"})
    data = {k: v.strip() if isinstance(v, str) else v for k, v in data.items()}
    if "name" in data and not data["name"]:
        raise HTTPException(400, "Please enter your name.")
    if data.get("role") == "agent" and u.get("role") != "agent":
        pin = security.agent_pin()
        if pin and not security._same(x.agent_pin or "", pin) and not security.is_admin(request):
            raise HTTPException(403, "Market agents need the agent PIN from Govi.")
    if data.get("location"):
        data["location"] = vocab.town(data["location"])
    u = {**u, **data}
    store.DB.put("users", u["phone"], u)
    request.state.user = u
    return public(u)
