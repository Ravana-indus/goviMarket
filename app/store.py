"""Persistence. Memory for tests and local runs, Firestore on Cloud Run (STORE=firestore)."""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone
from typing import Protocol

from .pricing import load_prices
from .schemas import Listing, Match, Order, ParsedMessage


class Backend(Protocol):
    def put(self, kind: str, key: str, doc: dict) -> None: ...
    def all(self, kind: str) -> list[dict]: ...
    def clear(self) -> None: ...


class Memory:
    def __init__(self):
        self.data: dict[str, dict[str, dict]] = {}

    def put(self, kind, key, doc):
        self.data.setdefault(kind, {})[key] = doc

    def all(self, kind):
        return list(self.data.get(kind, {}).values())

    def clear(self):
        self.data.clear()


class Firestore:
    def __init__(self):
        from google.cloud import firestore
        self.db = firestore.Client()

    def put(self, kind, key, doc):
        self.db.collection(kind).document(key).set(doc)

    def all(self, kind):
        return [d.to_dict() for d in self.db.collection(kind).stream()]

    def clear(self):
        raise RuntimeError("refusing to clear Firestore")


DB: Backend = Firestore() if os.getenv("STORE") == "firestore" else Memory()


def reset() -> None:
    DB.clear()


def listings() -> list[Listing]:
    return [Listing(**d) for d in DB.all("listings")]


def orders() -> list[Order]:
    return [Order(**d) for d in DB.all("orders")]


def inbox() -> list[dict]:
    return sorted(DB.all("inbox"), key=lambda d: d["at"])


def prices() -> dict[str, dict]:
    """Seed prices overlaid with whatever reporters sent most recently."""
    out = load_prices()
    for p in sorted(DB.all("prices"), key=lambda d: d["at"]):
        row = out.setdefault(p["crop"], {"crop": p["crop"]})
        row[p["kind"]] = p["lkr_per_kg"]
        row["source"] = f"reporter {p['reporter']} ({p['market']}) {p['date']}"
    return {c: r for c, r in out.items() if "collector" in r and "retail" in r}


def record(parsed: ParsedMessage, *, default_date: date, sender: str = "",
           default_buyer_location: str = "Colombo") -> list[str]:
    """Turn a parsed message into listings, orders or price reports. Returns created ids."""
    ids = []
    who = parsed.sender_name or sender or "unknown"
    when = parsed.when or default_date
    now = datetime.now(timezone.utc).isoformat()
    for item in parsed.items:
        rid = uuid.uuid4().hex[:8]
        if parsed.role == "farmer" and parsed.location:
            doc = Listing(id=rid, phone=sender or None, lang=parsed.language, farmer=who, location=parsed.location, crop=item.crop,
                          qty_kg=item.qty_kg, ready_on=when, remaining_kg=item.qty_kg)
            DB.put("listings", rid, doc.model_dump(mode="json"))
        elif parsed.role == "buyer":
            doc = Order(id=rid, phone=sender or None, lang=parsed.language, buyer=who, location=parsed.location or default_buyer_location,
                        crop=item.crop, qty_kg=item.qty_kg, needed_by=when, remaining_kg=item.qty_kg)
            DB.put("orders", rid, doc.model_dump(mode="json"))
        elif parsed.role == "reporter" and item.price_lkr_per_kg and item.price_kind:
            DB.put("prices", rid, {"crop": item.crop, "kind": item.price_kind,
                                   "lkr_per_kg": item.price_lkr_per_kg, "market": parsed.location or "?",
                                   "reporter": who, "date": when.isoformat(), "at": now})
        else:
            continue
        ids.append(rid)
    DB.put("inbox", uuid.uuid4().hex[:8], {"at": now, "sender": sender,
                                           "parsed": parsed.model_dump(mode="json"), "created": ids})
    return ids


def save_plan(plan: dict) -> None:
    DB.put("plans", "latest", plan)


def latest_plan() -> dict | None:
    rows = DB.all("plans")
    return rows[0] if rows else None


def matches() -> list[Match]:
    return [Match(**d) for d in DB.all("matches")]


def put_match(m: Match) -> None:
    DB.put("matches", m.id, m.model_dump(mode="json"))


def get(kind: str, rid: str) -> dict | None:
    return next((d for d in DB.all(kind) if d["id"] == rid), None)


def put(kind: str, doc: dict) -> None:
    DB.put(kind, doc["id"], doc)


def outbox(to: str, body: str, match_id: str = "") -> None:
    DB.put("outbox", uuid.uuid4().hex[:8], {"at": datetime.now(timezone.utc).isoformat(),
                                            "to": to, "body": body, "match_id": match_id})


def sent() -> list[dict]:
    return sorted(DB.all("outbox"), key=lambda d: d["at"])
