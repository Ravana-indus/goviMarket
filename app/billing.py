"""The Govi service plan: Rs 799 a month for every seller and buyer.

Each farmer or buyer account has one plan record: when it started, what is paid up to, and the
payments. It is due from the day they join; the console marks a month paid (cash, bank transfer,
mobile money) and that adds 30 days. No payment gateway yet, and trading is not blocked while a
plan is unpaid: the app, the chat and the console show what is due. Sinhala and Tamil need a
native speaker's read."""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import accounts, store

router = APIRouter()
KIND = "subscriptions"
PRICE_LKR = int(os.getenv("SUBSCRIPTION_LKR", "799"))
PERIOD_DAYS = 30
GRACE_DAYS = 7  # "due" for a week after the due date, then "overdue"
ROLES = ("farmer", "buyer")
SAY = {
    "active": {"en": "Govi plan: Rs {price}/month, paid until {until} ✅",
               "si": "Govi සැලැස්ම: මසකට රු. {price}, {until} දක්වා ගෙවා ඇත ✅",
               "ta": "Govi திட்டம்: மாதம் ரூ. {price}, {until} வரை செலுத்தப்பட்டது ✅"},
    "due": {"en": "Govi plan: Rs {price}/month, due {due}. Pay your Govi agent or by bank transfer, quoting {phone}.",
            "si": "Govi සැලැස්ම: මසකට රු. {price}, ගෙවිය යුතු දිනය {due}. {phone} සඳහන් කර Govi නියෝජිතයාට හෝ බැංකු මාරුවකින් ගෙවන්න.",
            "ta": "Govi திட்டம்: மாதம் ரூ. {price}, செலுத்த வேண்டிய நாள் {due}. {phone} குறிப்பிட்டு Govi முகவரிடம் அல்லது வங்கி மாற்றம் மூலம் செலுத்தவும்."},
    "overdue": {"en": "Govi plan: Rs {price}/month, overdue since {due}. Please pay your Govi agent or by bank transfer, quoting {phone}.",
                "si": "Govi සැලැස්ම: මසකට රු. {price}, {due} සිට ප්‍රමාදයි. {phone} සඳහන් කර Govi නියෝජිතයාට හෝ බැංකු මාරුවකින් ගෙවන්න.",
                "ta": "Govi திட்டம்: மாதம் ரூ. {price}, {due} முதல் நிலுவையில் உள்ளது. {phone} குறிப்பிட்டு Govi முகவரிடம் அல்லது வங்கி மாற்றம் மூலம் செலுத்தவும்."},
    "none": {"en": "The Govi plan (Rs {price}/month) starts with your first harvest or order.",
             "si": "Govi සැලැස්ම (මසකට රු. {price}) ඔබේ පළමු අස්වැන්න හෝ ඇණවුම සමඟ ආරම්භ වේ.",
             "ta": "Govi திட்டம் (மாதம் ரூ. {price}) உங்கள் முதல் அறுவடை அல்லது ஆர்டருடன் தொடங்கும்."},
}
WORDS = {"plan", "my plan", "subscription", "bill", "billing", "fee", "සැලැස්ම", "ගාස්තුව මාසික", "திட்டம்", "சந்தா"}


def _today() -> date:
    return date.today()


def _pretty(phone: str) -> str:
    return "0" + phone[2:] if phone.startswith("94") and len(phone) == 11 else phone


def record(phone: str | None) -> dict | None:
    """This account's plan, started the first time we see them as a farmer or buyer."""
    if not phone or not phone.isdigit():
        return None
    doc = store.DB.one(KIND, phone)
    if doc:
        return doc
    u = accounts.user(phone) or {}
    if u.get("role") not in ROLES:
        return None
    started = (u.get("created") or "")[:10] or _today().isoformat()
    doc = {"phone": phone, "plan": "Govi service", "amount_lkr": PRICE_LKR, "period_days": PERIOD_DAYS,
           "started": started, "paid_until": None, "payments": []}
    store.DB.put(KIND, phone, doc)
    return doc


def view(doc: dict, today: Optional[date] = None) -> dict:
    """Status: active (paid up), due (unpaid, within a week of the due date) or overdue."""
    today = today or _today()
    until = date.fromisoformat(doc["paid_until"]) if doc.get("paid_until") else None
    due = until or date.fromisoformat(doc["started"])
    status = "active" if until and until >= today else "due" if today <= due + timedelta(days=GRACE_DAYS) else "overdue"
    u = accounts.user(doc["phone"]) or {}
    return {**doc, "status": status, "paid": status == "active", "due_on": due.isoformat(),
            "name": u.get("business") or u.get("name") or "", "role": u.get("role") or "",
            "owed_lkr": 0 if status == "active" else doc.get("amount_lkr", PRICE_LKR)}


def line(phone: str, lang: str) -> str:
    """One line for chat (STATUS, PLAN)."""
    doc = record(phone)
    if not doc:
        return SAY["none"][lang].format(price=PRICE_LKR)
    v = view(doc)
    return SAY[v["status"]][lang].format(price=v["amount_lkr"], until=v.get("paid_until") or "", due=v["due_on"],
                                         phone=_pretty(phone))


def mark_paid(phone: str, *, method: str = "cash", ref: str = "", by: str = "console",
              today: Optional[date] = None) -> dict:
    """One month paid: 30 more days from the paid-up date, or from today if it had lapsed."""
    today = today or _today()
    doc = record(phone)
    if not doc:
        raise KeyError(phone)
    until = date.fromisoformat(doc["paid_until"]) if doc.get("paid_until") else None
    start = until if until and until >= today else today
    new_until = start + timedelta(days=doc.get("period_days", PERIOD_DAYS))
    pay = {"at": datetime.now(timezone.utc).isoformat(), "amount_lkr": doc.get("amount_lkr", PRICE_LKR),
           "method": method, "ref": ref, "by": by, "covers": [start.isoformat(), new_until.isoformat()],
           "previous_paid_until": doc.get("paid_until")}
    doc = {**doc, "paid_until": new_until.isoformat(), "payments": [*doc.get("payments", []), pay]}
    store.DB.put(KIND, phone, doc)
    return view(doc, today)


def undo_last(phone: str) -> dict:
    doc = record(phone)
    if not doc or not doc.get("payments"):
        raise KeyError(phone)
    last = doc["payments"][-1]
    doc = {**doc, "paid_until": last.get("previous_paid_until"), "payments": doc["payments"][:-1]}
    store.DB.put(KIND, phone, doc)
    return view(doc)


def everyone() -> list[dict]:
    """Every seller and buyer account with its plan, unpaid first."""
    out = [view(d) for d in (record(u["phone"]) for u in store.DB.all("users") if u.get("role") in ROLES) if d]
    order = {"overdue": 0, "due": 1, "active": 2}
    return sorted(out, key=lambda v: (order[v["status"]], v["due_on"], v["name"]))


# ---- API

@router.get("/api/me/subscription")
def my_plan(request: Request):
    u = accounts.require(request)
    doc = record(u["phone"])
    return view(doc) if doc else {"status": "none", "amount_lkr": PRICE_LKR, "period_days": PERIOD_DAYS}


@router.get("/api/subscriptions")
def all_plans():
    rows = everyone()
    return {"price_lkr": PRICE_LKR, "rows": rows,
            "summary": {"accounts": len(rows), "active": sum(r["status"] == "active" for r in rows),
                        "unpaid": sum(r["status"] != "active" for r in rows),
                        "owed_lkr": sum(r["owed_lkr"] for r in rows),
                        "monthly_lkr": sum(r["amount_lkr"] for r in rows if r["status"] == "active")}}


class PaidIn(BaseModel):
    method: str = Field("cash", max_length=30)
    ref: str = Field("", max_length=60)


@router.post("/api/subscriptions/{phone}/paid")
def paid(phone: str, x: PaidIn | None = None):
    try:
        return mark_paid(phone, method=(x or PaidIn()).method, ref=(x or PaidIn()).ref)
    except KeyError:
        raise HTTPException(404, "No seller or buyer account with that number.")


@router.post("/api/subscriptions/{phone}/undo")
def undo(phone: str):
    try:
        return undo_last(phone)
    except KeyError:
        raise HTTPException(404, "No payment to undo.")
