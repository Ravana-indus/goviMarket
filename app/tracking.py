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
from .lanes import _norm, load_lanes
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


_BASE: dict[str, tuple[float, str]] = {}


def apply() -> None:
    """Every lane's Rs/kg: the median of its latest seller reports, else the original estimate."""
    by_lane: dict[str, list[dict]] = {}
    for r in store.DB.all(KIND):
        by_lane.setdefault(r["lane"], []).append(r)
    for lane in load_lanes():
        k = _key(lane)
        _BASE.setdefault(k, (lane.lkr_per_kg, lane.source))
        rows = sorted(by_lane.get(k, []), key=lambda r: r["at"])[-RECENT:]
        if rows:
            lane.lkr_per_kg = round(statistics.median(r["per_kg"] for r in rows), 2)
            lane.source = f"REPORTED by sellers ({len(by_lane[k])} reports, latest {rows[-1]['at'][:10]})"
        else:
            lane.lkr_per_kg, lane.source = _BASE[k]


def costs() -> list[dict]:
    """For the console: each lane's estimate next to what sellers report."""
    by_lane: dict[str, list[dict]] = {}
    for r in store.DB.all(KIND):
        by_lane.setdefault(r["lane"], []).append(r)
    out = []
    for lane in load_lanes():
        k = _key(lane)
        rows = sorted(by_lane.get(k, []), key=lambda r: r["at"])
        out.append({"origin": lane.origin, "dest": lane.dest, "mode": lane.mode, "departs": lane.departs,
                    "estimate_lkr_per_kg": _BASE.get(k, (lane.lkr_per_kg, ""))[0], "now_lkr_per_kg": lane.lkr_per_kg,
                    "reports": len(rows), "latest": rows[-1] if rows else None, "source": lane.source})
    return sorted(out, key=lambda r: (-r["reports"], r["origin"]))


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
