"""Shipment tracking for both sides, and sellers reporting what each shipment really cost.

- A tracking code (GV-xxxxxxxx, one per agreed deal) opens /t/<code> for anyone holding it,
  and TRACK in chat lists every agreed deal of that number with where its load is.
- After a shipment, the seller replies COST 1200 (or types it in the app). That is stored on the
  deal, and the lane's Rs/kg becomes the median of the latest reports for it, so every new quote,
  match and bundle uses what sellers actually paid. Sinhala and Tamil need a native speaker's read."""
from __future__ import annotations

import re
import statistics
import uuid
from datetime import datetime, timezone

from . import accounts, dispatch, store, vocab
from .lanes import DEST_PICKUP_LKR, _norm, load_lanes
from .schemas import Lane, Match

KIND = "lane_costs"
RECENT = 5  # the lane rate is the median of this many latest reports
STEP = {
    "planned": {"en": "waiting to be booked", "si": "වෙන් කිරීමට බලාපොරොත්තුවෙන්", "ta": "பதிவுக்காக காத்திருக்கிறது"},
    "booked": {"en": "booked", "si": "වෙන් කළා", "ta": "பதிவு செய்யப்பட்டது"},
    "loaded": {"en": "loaded", "si": "පැටෙව්වා", "ta": "ஏற்றப்பட்டது"},
    "in_transit": {"en": "on the way", "si": "එමින් පවතී", "ta": "வழியில்"},
    "arrived": {"en": "arrived", "si": "ළඟා විය", "ta": "வந்து சேர்ந்தது"},
    "delivered": {"en": "delivered ✅", "si": "භාර දුන්නා ✅", "ta": "வழங்கப்பட்டது ✅"},
    "missed": {"en": "missed its transport, being rescued", "si": "ප්‍රවාහනය මග හැරුණා, විසඳමින්", "ta": "போக்குவரத்து தவறியது, சரிசெய்யப்படுகிறது"},
    "local": {"en": "local pickup", "si": "ප්‍රදේශයේම රැගෙන යාම", "ta": "உள்ளூர் எடுப்பு"},
}
SAY = {
    "head": {"en": "Your shipments:", "si": "ඔබේ යැවීම්:", "ta": "உங்கள் அனுப்புதல்கள்:"},
    "none": {"en": "No agreed deals to track yet. Send STATUS to see your orders.",
             "si": "ලුහුබැඳීමට තවම එකඟ වූ ගනුදෙනු නැහැ. ඔබේ ඇණවුම් බලන්න STATUS එවන්න.",
             "ta": "கண்காணிக்க இன்னும் ஒப்புக்கொண்ட ஒப்பந்தங்கள் இல்லை. உங்கள் ஆர்டர்களைப் பார்க்க STATUS அனுப்பவும்."},
    "row": {"en": "• {code} · {crop} {kg} kg, {farmer} → {buyer}: {step}{eta}",
            "si": "• {code} · {crop} කිලෝ {kg}, {farmer} → {buyer}: {step}{eta}",
            "ta": "• {code} · {crop} {kg} கிலோ, {farmer} → {buyer}: {step}{eta}"},
    "eta": {"en": ", arrives about {at}", "si": ", {at} පමණ ළඟා වේ", "ta": ", சுமார் {at} வந்து சேரும்"},
    "cost_ok": {"en": "Thanks. Recorded Rs {lkr} for sending {code} ({per}/kg). Govi's {route} price is now Rs {rate}/kg.",
                "si": "ස්තූතියි. {code} යැවීමට රු. {lkr} (කිලෝවට {per}) සටහන් කළා. Govi හි {route} මිල දැන් කිලෝවට රු. {rate}.",
                "ta": "நன்றி. {code} அனுப்ப ரூ. {lkr} (கிலோவுக்கு {per}) பதிவு செய்யப்பட்டது. Govi-யின் {route} விலை இப்போது கிலோவுக்கு ரூ. {rate}."},
    "cost_none": {"en": "There is no agreed shipment of yours to put a cost on. Send TRACK to see your codes.",
                  "si": "වියදමක් දැමීමට ඔබේ එකඟ වූ යැවීමක් නැහැ. ඔබේ අංක බලන්න TRACK එවන්න.",
                  "ta": "செலவு பதிவு செய்ய உங்கள் ஒப்புக்கொண்ட அனுப்புதல் எதுவும் இல்லை. உங்கள் எண்களைப் பார்க்க TRACK அனுப்பவும்."},
    "cost_bad": {"en": "Please send the amount in rupees, for example: COST 1200", "si": "කරුණාකර රුපියල් ගණන එවන්න, උදා: COST 1200",
                 "ta": "தொகையை ரூபாயில் அனுப்பவும், உதா: COST 1200"},
}
COST_WORDS = r"(?:cost|shipping|transport|ගාස්තුව|වියදම|கட்டணம்|செலவு)"
COST_RE = re.compile(COST_WORDS + r":?\s*(gv\s*-?\s*[0-9a-f]+)?\s*(?:rs\.?|lkr|රු\.?|ரூ\.?)?\s*([\d,]+(?:\.\d+)?)?\s*$", re.I)
TRACK_RE = re.compile(r"(?:track|tracking|ලුහුබඳින්න|கண்காணி)\s*(gv\s*-?\s*[0-9a-f]+)?\s*$", re.I)
MAX_LKR = 500_000


def say(key: str, lang: str, **kw) -> str:
    return SAY[key].get(lang, SAY[key]["en"]).format(**kw)


def _ship(m: Match):
    return next((x for x in store.shipments() if x.id == m.shipment_id), None) if m.shipment_id else None


def _mine(phone: str) -> list[tuple[Match, str]]:
    """Agreed deals of this number, newest first, with which side it is on."""
    out = []
    for m in store.matches():
        if m.status != "confirmed":
            continue
        l, o = store.get("listings", m.listing_id) or {}, store.get("orders", m.order_id) or {}
        if l.get("phone") == phone:
            out.append((m, "farmer"))
        elif o.get("phone") == phone:
            out.append((m, "buyer"))
    return sorted(out, key=lambda r: (r[0].ship_on or r[0].needed_by or datetime.min.date()), reverse=True)


def step_of(m: Match) -> str:
    x = _ship(m)
    return x.status if x else ("planned" if m.lane else "local")


def chat_track(phone: str, text: str, lang: str) -> str | None:
    """TRACK or TRACK GV-xxxx in chat. None if the message is not a track request."""
    hit = TRACK_RE.fullmatch(vocab.norm(text).replace(" - ", "-"))
    if not hit:
        return None
    rows = _mine(phone)
    if hit.group(1):
        want = dispatch.find(hit.group(1).replace(" ", ""))
        rows = [r for r in rows if want and r[0].id == want.id]
    if not rows:
        return say("none", lang)
    lines = [say("head", lang)]
    for m, _ in rows[:8]:
        x = _ship(m)
        st = step_of(m)
        eta = say("eta", lang, at=datetime.fromisoformat(x.schedule["arrived"]).strftime("%a %H:%M")) \
            if x and st in ("booked", "loaded", "in_transit") and x.schedule.get("arrived") else ""
        lines.append(say("row", lang, code=dispatch.code(m), crop=vocab.crop_name(m.crop, lang), kg=f"{m.qty_kg:.0f}",
                         farmer=m.farmer, buyer=m.buyer, step=STEP[st].get(lang, STEP[st]["en"]), eta=eta))
    return "\n".join(lines)


def chat_cost(phone: str, text: str, lang: str) -> str | None:
    """COST 1200 / COST GV-xxxx 1200 from a seller. None if the message is not a cost report."""
    hit = COST_RE.fullmatch(re.sub(r"\s+", " ", (text or "").lower()).strip().rstrip(".!"))
    if not hit:
        return None
    if not hit.group(2):
        return say("cost_bad", lang)
    lkr = float(hit.group(2).replace(",", ""))
    mine = [m for m, side in _mine(phone) if side == "farmer" and m.lane]
    if hit.group(1):
        want = dispatch.find(hit.group(1).replace(" ", ""))
        mine = [m for m in mine if want and m.id == want.id]
    else:  # the newest one that has left or is about to, still without a cost
        mine = sorted(mine, key=lambda m: (m.shipping_paid_lkr is None, step_of(m) != "planned"), reverse=True)
    if not mine:
        return say("cost_none", lang)
    try:
        m, lane = report(mine[0], lkr, phone=phone)
    except ValueError:
        return say("cost_bad", lang)
    return say("cost_ok", lang, lkr=f"{lkr:,.0f}", code=dispatch.code(m), per=f"{lkr / m.qty_kg:.1f}",
               route=f"{lane.origin} → {lane.dest}", rate=f"{lane.lkr_per_kg:g}")


def _key(lane: Lane) -> str:
    return "|".join([_norm(lane.origin), _norm(lane.dest), lane.mode, lane.departs])


def report(m: Match, lkr: float, *, phone: str = "") -> tuple[Match, Lane]:
    """Store what the seller paid to send this deal's load and refresh that lane's rate."""
    if not m.lane or not (0 < lkr <= MAX_LKR) or m.qty_kg <= 0:
        raise ValueError("cost out of range")
    now = datetime.now(timezone.utc).isoformat()
    m.shipping_paid_lkr, m.shipping_reported_at = lkr, now
    store.put_match(m)
    store.DB.put(KIND, uuid.uuid4().hex[:10], {"lane": _key(m.lane), "origin": m.lane.origin, "dest": m.lane.dest,
                                               "mode": m.lane.mode, "departs": m.lane.departs, "kg": m.qty_kg,
                                               "lkr": lkr, "per_kg": round(lkr / m.qty_kg, 2), "match_id": m.id,
                                               "code": dispatch.code(m), "phone": phone, "at": now})
    apply()
    lane = next((l for l in load_lanes() if _key(l) == _key(m.lane)), m.lane)
    return m, lane


FIXED = ("min_charge_lkr", "handling_lkr", "pickup_lkr")  # per-consignment costs an agent can set
_BASE: dict[str, dict] = {}


def _rows() -> dict[str, list[dict]]:
    by_lane: dict[str, list[dict]] = {}
    for r in store.DB.all(KIND):
        by_lane.setdefault(r["lane"], []).append(r)
    return {k: sorted(v, key=lambda r: r["at"]) for k, v in by_lane.items()}


def _since_agent(rows: list[dict]) -> tuple[dict | None, list[dict]]:
    """The latest agent check of a lane and the seller reports after it. An agent's new rate
    replaces older reports; sellers' later reports then move it again."""
    agent = next((r for r in reversed(rows) if r.get("kind") == "agent"), None)
    after = [r for r in rows if r.get("kind") != "agent" and (agent is None or r["at"] > agent["at"])]
    return agent, after


def apply() -> None:
    """Every lane's costs: the latest agent check, moved by seller reports since, else the estimate."""
    by_lane = _rows()
    for lane in load_lanes():
        k = _key(lane)
        base = _BASE.setdefault(k, {"lkr_per_kg": lane.lkr_per_kg, "source": lane.source,
                                    **{f: getattr(lane, f) for f in FIXED}})
        agent, after = _since_agent(by_lane.get(k, []))
        rates = ([agent["per_kg"]] if agent else []) + [r["per_kg"] for r in after]
        rates = rates[-RECENT:]
        lane.lkr_per_kg = round(statistics.median(rates), 2) if rates else base["lkr_per_kg"]
        for f in FIXED:
            setattr(lane, f, agent[f] if agent and f in agent else base[f])
        bits = []
        if agent:
            bits.append(f"{'CONFIRMED' if agent.get('confirmed') else 'SET'} by agent {agent['who']} {agent['at'][:10]}")
        if after:
            bits.append(f"REPORTED by sellers ({len(after)} reports, latest {after[-1]['at'][:10]})")
        lane.source = "; ".join(bits) or base["source"]


def agent_set(key: str, *, who: str, lkr_per_kg: float, min_charge_lkr: float, handling_lkr: float,
              pickup_lkr: float | None, confirmed: bool = False) -> Lane:
    """An agent called the bus stand, station or farmers and set (or confirmed) a lane's costs."""
    lane = next((l for l in load_lanes() if _key(l) == key), None)
    if lane is None:
        raise KeyError(key)
    vals = [lkr_per_kg, min_charge_lkr, handling_lkr] + ([pickup_lkr] if pickup_lkr is not None else [])
    if not all(0 <= v <= MAX_LKR for v in vals) or lkr_per_kg <= 0:
        raise ValueError("cost out of range")
    store.DB.put(KIND, uuid.uuid4().hex[:10], {
        "kind": "agent", "lane": key, "origin": lane.origin, "dest": lane.dest, "mode": lane.mode,
        "departs": lane.departs, "who": who or "agent", "confirmed": confirmed, "per_kg": lkr_per_kg,
        "min_charge_lkr": min_charge_lkr, "handling_lkr": handling_lkr, "pickup_lkr": pickup_lkr,
        "at": datetime.now(timezone.utc).isoformat()})
    apply()
    return lane


def costs() -> list[dict]:
    """Each lane's costs now, the estimate it started from, and who last checked it."""
    by_lane = _rows()
    out = []
    for lane in load_lanes():
        k = _key(lane)
        rows = by_lane.get(k, [])
        agent, after = _since_agent(rows)
        sellers = [r for r in rows if r.get("kind") != "agent"]
        out.append({"key": k, "origin": lane.origin, "dest": lane.dest, "mode": lane.mode, "departs": lane.departs,
                    "estimate_lkr_per_kg": _BASE.get(k, {}).get("lkr_per_kg", lane.lkr_per_kg),
                    "now_lkr_per_kg": lane.lkr_per_kg, "min_charge_lkr": lane.min_charge_lkr,
                    "handling_lkr": lane.handling_lkr, "door_delivery": lane.door_delivery,
                    "pickup_lkr": 0 if lane.door_delivery else DEST_PICKUP_LKR if lane.pickup_lkr is None else lane.pickup_lkr,
                    "reports": len(sellers), "latest": sellers[-1] if sellers else None, "source": lane.source,
                    "checked": {"who": agent["who"], "at": agent["at"], "confirmed": agent.get("confirmed")} if agent else None})
    return sorted(out, key=lambda r: (r["origin"], r["dest"], r["departs"]))


def public(code: str) -> dict | None:
    """What /t/<code> shows: no phone numbers or addresses, only the load and where it is."""
    m = dispatch.find(code)
    if not m:
        return None
    x = _ship(m)
    st = step_of(m)
    steps = []
    if x:
        done = {e["status"]: e["at"] for e in x.events}
        steps = [{"status": s, "planned": x.schedule.get(s), "done": done.get(s)}
                 for s in ("booked", "loaded", "in_transit", "arrived", "delivered")]
    return {"code": dispatch.code(m), "crop": m.crop, "kg": m.qty_kg, "farmer": m.farmer, "buyer": m.buyer,
            "status": st, "origin": x.origin if x else None, "dest": x.dest if x else None,
            "mode": m.lane.mode if m.lane else None, "departs": m.lane.departs if m.lane else None,
            "pickup": (m.lane.pickup or m.lane.origin) if m.lane else None, "ship_on": m.ship_on, "needed_by": m.needed_by,
            "carrier_ref": x.ref if x else "", "steps": steps, "shipping_paid_lkr": m.shipping_paid_lkr}


def can_report(phone: str, m: Match) -> bool:
    return (store.get("listings", m.listing_id) or {}).get("phone") == phone


def lang_for(phone: str, fallback: str = "en") -> str:
    return accounts.chosen_lang(phone) or fallback
