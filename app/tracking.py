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


def freight_rate(lane: Lane, lkr: float, kg: float) -> float | None:
    """The Rs/kg freight a seller's COST implies, for the lane's rate. What the seller paid covers
    the freight and the loading at their end (handling), never the city pickup, so handling comes
    off first. A load on the minimum charge says nothing about the per-kg rate (None). One report
    can move the rate at most to half or double what Govi has now, so a typo cannot close a route."""
    freight = lkr - lane.handling_lkr
    if freight <= lane.min_charge_lkr:
        return None
    agent, _ = _since_agent(_rows().get(_key(lane), []))  # an agent's number, else the estimate
    base = agent["per_kg"] if agent else _BASE.get(_key(lane), {}).get("lkr_per_kg", lane.lkr_per_kg)
    return round(min(max(freight / kg, base * 0.5), base * 2), 2)


def report(m: Match, lkr: float, *, phone: str = "") -> tuple[Match, Lane]:
    """Store what the seller paid to send this deal's load and refresh that lane's rate."""
    if not m.lane or not (0 < lkr <= MAX_LKR) or m.qty_kg <= 0:
        raise ValueError("cost out of range")
    now = datetime.now(timezone.utc).isoformat()
    m.shipping_paid_lkr, m.shipping_reported_at = lkr, now
    store.put_match(m)
    lane = next((l for l in load_lanes() if _key(l) == _key(m.lane)), m.lane)
    store.DB.put(KIND, uuid.uuid4().hex[:10], {"lane": _key(m.lane), "origin": m.lane.origin, "dest": m.lane.dest,
                                               "mode": m.lane.mode, "departs": m.lane.departs, "kg": m.qty_kg,
                                               "lkr": lkr, "per_kg": freight_rate(lane, lkr, m.qty_kg),
                                               "paid_per_kg": round(lkr / m.qty_kg, 2), "match_id": m.id,
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
        rates = ([agent["per_kg"]] if agent else []) + [r["per_kg"] for r in after if r.get("per_kg") is not None]
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


# ---- chat steps after the dispatch slip: the seller hands the load over, the buyer gets it

STEP_SAY = {
    "dropped": {"en": "Thanks, noted: {crop} {kg} kg handed over at {pickup} ({code}). {buyer} is told it is on its way.",
                "si": "ස්තූතියි, සටහන් කළා: {crop} කිලෝ {kg} {pickup} හිදී භාර දුන්නා ({code}). {buyer} ට එය එමින් පවතින බව දන්වා ඇත.",
                "ta": "நன்றி, பதிவு செய்தோம்: {crop} {kg} கிலோ {pickup} இல் ஒப்படைக்கப்பட்டது ({code}). {buyer} க்கு அது வருவதாக தெரிவிக்கப்பட்டது."},
    "cost_next": {"en": "Now reply COST and what you paid to send it (for example: COST 1200).",
                  "si": "දැන් යැවීමට ගෙවූ මුදල COST ලෙස එවන්න (උදා: COST 1200).",
                  "ta": "இப்போது அனுப்ப செலுத்திய தொகையை COST என அனுப்பவும் (உதா: COST 1200)."},
    "to_buyer": {"en": "{farmer} has handed over your {kg} kg {crop} at {pickup} ({code}). It goes by {mode} at {departs}. Reply RECEIVED when it reaches you.",
                 "si": "{farmer} ඔබේ {crop} කිලෝ {kg} {pickup} හිදී භාර දුන්නා ({code}). {departs} ට {mode} මගින් යයි. ලැබුණු විට RECEIVED ලෙස පිළිතුරු දෙන්න.",
                 "ta": "{farmer} உங்கள் {crop} {kg} கிலோவை {pickup} இல் ஒப்படைத்தார் ({code}). {departs} மணிக்கு {mode} மூலம் செல்கிறது. வந்ததும் RECEIVED என பதில் அனுப்பவும்."},
    "received": {"en": "Thanks, {crop} {kg} kg from {farmer} marked received ✅ ({code}).",
                 "si": "ස්තූතියි, {farmer} ගෙන් {crop} කිලෝ {kg} ලැබුණු ලෙස සටහන් කළා ✅ ({code}).",
                 "ta": "நன்றி, {farmer} இடமிருந்து {crop} {kg} கிலோ பெறப்பட்டதாக பதிவு செய்தோம் ✅ ({code})."},
    "to_seller": {"en": "{buyer} received your {kg} kg {crop} ✅ ({code}).",
                  "si": "{buyer} ඔබේ {crop} කිලෝ {kg} ලබා ගත්තා ✅ ({code}).",
                  "ta": "{buyer} உங்கள் {crop} {kg} கிலோவைப் பெற்றார் ✅ ({code})."},
}
DROP_RE = re.compile(r"\b(drop+ed|drop+ed off|dropped it|handed( it)? over|handed|loaded|put (it )?on|sent off|dispatched|gave it)\b"
                     # romanised Tamil and Sinhala: koduthuten / kuduthachu (gave), anuppiten (sent),
                     # ethiten (loaded), bara dunna (handed over), damma (put), yawwa (sent)
                     r"|\bk[ou]d+u?th+[ua]?(?:t+[ea]n|en|aa?chu|i?t+en)\b|\banup+i(?:t+en|nen|yachu)\b"
                     r"|\be?th+it+en\b|\byeth+it+en\b|\bb[a]+ra dun+a\b|\bdam+a+\b|\bdem+a+\b|\by[ae]w+a\b"
                     r"|දැම්මා|භාර දුන්නා|දුන්නා|පැටෙව්වා|යැව්වා|ஒப்படைத்தேன்|ஒப்படைத்துவிட்டேன்|ஏற்றினேன்|ஏற்றிவிட்டேன்"
                     r"|கொடுத்தேன்|கொடுத்துட்டேன்|கொடுத்துவிட்டேன்|கொடுத்தாச்சு|அனுப்பினேன்|அனுப்பிட்டேன்|அனுப்பிவிட்டேன்", re.I)
RECV_RE = re.compile(r"\b(received|recieved|got it|got the|arrived|it came|delivered)\b"
                     r"|\bkidai?ch+(?:athu|uthu|udhu|iduchu|idichu|ithu)\b|\bvan+[dt]?h?(?:uchu|iruchu|iduchu)\b|\blab+una+\b"
                     r"|ලැබුණා|ලැබුනා|கிடைத்தது|கிடைச்சுது|பெற்றேன்|வந்தது|வந்துச்சு|வந்துவிட்டது", re.I)
# Words that tie a message to a booked load rather than to new harvest: the train, bus, station, parcel office.
HAUL_RE = re.compile(r"\b(train|trian|bus|station|parcel|lorry|post office|rail|coach)\b|ரயில்|பேருந்து|பஸ்|நிலைய"
                     r"|දුම්රිය|කෝච්චි|බස්|ස්ටේෂන්|පාර්සල්", re.I)


def _facts(m: Match, lang: str) -> dict:
    return dict(crop=vocab.crop_name(m.crop, lang), kg=f"{m.qty_kg:.0f}", code=dispatch.code(m), farmer=m.farmer,
                buyer=m.buyer, pickup=(m.lane.pickup or m.lane.origin) if m.lane else "",
                mode=dispatch.MODE.get(m.lane.mode, {}).get(lang, m.lane.mode) if m.lane else "",
                departs=m.lane.departs if m.lane else "")


def awaiting_drop(phone: str) -> list[Match]:
    return [m for m, side in _mine(phone) if side == "farmer" and m.lane and not m.dropped_at
            and step_of(m) in ("planned", "booked", "loaded")]


def awaiting_receipt(phone: str) -> list[Match]:
    return [m for m, side in _mine(phone) if side == "buyer" and not m.received_at
            and (m.dropped_at or step_of(m) in ("loaded", "in_transit", "arrived", "local"))]


def waiting(phone: str) -> tuple[str, list[Match]] | None:
    """What Govi is waiting on this number for: ("drop", loads to hand over) or ("recv", loads to receive)."""
    ms = awaiting_drop(phone)
    if ms:
        return "drop", ms
    ms = awaiting_receipt(phone)
    return ("recv", ms) if ms else None


def _move_to(sid: str | None, target: str, send) -> None:
    """Advance a shipment step by step (each step tells everyone on it) until it reaches `target`."""
    from . import shipping
    for _ in range(6):
        x = next((s for s in store.shipments() if s.id == sid), None)
        if not x or x.status in ("missed", "delivered") or shipping.STEPS.index(x.status) >= shipping.STEPS.index(target):
            return
        try:
            shipping.advance(sid, send)
        except ValueError:  # someone on the bundle has not said YES yet
            return


def dropped(phone: str, lang: str, send) -> str | None:
    """The seller handed over every load still waiting: tell the buyers, and once everyone on a
    bundle has handed over, the shipment moves to loaded."""
    ms = awaiting_drop(phone)
    if not ms:
        return None
    now = datetime.now(timezone.utc).isoformat()
    lines = []
    for m in ms:
        m.dropped_at = now
        store.put_match(m)
        lines.append(STEP_SAY["dropped"][lang].format(**_facts(m, lang)))
        o = store.get("orders", m.order_id) or {}
        if o.get("phone"):
            bl = accounts.reply_lang(o["phone"], o.get("lang"))
            send(o["phone"], STEP_SAY["to_buyer"][bl].format(**_facts(m, bl)), m.id, buttons=[["📦 RECEIVED", "TRACK"]])
        mates = [y for y in store.matches() if y.shipment_id and y.shipment_id == m.shipment_id]
        if mates and all(y.dropped_at for y in mates):
            _move_to(m.shipment_id, "loaded", send)
    if not any(m.shipping_paid_lkr for m in ms):
        lines.append(STEP_SAY["cost_next"][lang])
    return "\n".join(lines)


def received(phone: str, lang: str, send) -> str | None:
    """The buyer has it: the seller is told, and a bundle everyone has received is delivered."""
    ms = awaiting_receipt(phone)
    if not ms:
        return None
    now = datetime.now(timezone.utc).isoformat()
    lines = []
    for m in ms:
        m.received_at = now
        store.put_match(m)
        lines.append(STEP_SAY["received"][lang].format(**_facts(m, lang)))
        l = store.get("listings", m.listing_id) or {}
        if l.get("phone"):
            fl = accounts.reply_lang(l["phone"], l.get("lang"))
            send(l["phone"], STEP_SAY["to_seller"][fl].format(**_facts(m, fl)), m.id)
        mates = [y for y in store.matches() if y.shipment_id and y.shipment_id == m.shipment_id]
        if mates and all(y.received_at for y in mates):
            _move_to(m.shipment_id, "delivered", send)
    return "\n".join(lines)


def chat_step(phone: str, text: str, lang: str, send) -> str | None:
    """'dropped', 'both loaded on the train', 'RECEIVED', 'got it' from someone with a load waiting."""
    if DROP_RE.search(text or "") and awaiting_drop(phone):
        return dropped(phone, lang, send)
    if RECV_RE.search(text or "") and awaiting_receipt(phone):
        return received(phone, lang, send)
    return None


def yes(phone: str, lang: str, send) -> str | None:
    """A YES with nothing else waiting, right after a dispatch slip, means handed over (or received)."""
    return dropped(phone, lang, send) or received(phone, lang, send)
