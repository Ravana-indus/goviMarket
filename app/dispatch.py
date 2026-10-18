"""After a deal is agreed: the seller gets a dispatch slip (tracking code, delivery address, where
and when to hand the load over) and the buyer gets the same tracking code.

The tracking code goes on every bag. Anyone holding it can follow the load at /t/<code>, and
TRACK in chat shows it too. Sinhala and Tamil need a native speaker's read before the demo."""
from __future__ import annotations

import os
from datetime import datetime

from . import accounts, store, vocab, who
from .schemas import Match

MODE = {"night_bus": {"en": "night bus", "si": "රාත්‍රී බසය", "ta": "இரவு பேருந்து"},
        "train_parcel": {"en": "train", "si": "දුම්රිය", "ta": "ரயில்"},
        "lorry": {"en": "shared lorry", "si": "හවුල් ලොරිය", "ta": "பகிர்வு லாரி"},
        "sl_post": {"en": "Sri Lanka Post", "si": "ශ්‍රී ලංකා තැපෑල", "ta": "இலங்கை தபால்"}}
SAY = {
    "seller_head": {"en": "📦 Dispatch slip: {kg} kg {crop} for {buyer}",
                    "si": "📦 යැවීමේ පත්‍රිකාව: {buyer} සඳහා {crop} කිලෝ {kg}",
                    "ta": "📦 அனுப்பும் சீட்டு: {buyer} க்கு {crop} {kg} கிலோ"},
    "code": {"en": "Tracking code: {code} (write it on every bag or box)",
             "si": "ලුහුබැඳීමේ අංකය: {code} (සෑම මල්ලක්ම හෝ පෙට්ටියක්ම මත ලියන්න)",
             "ta": "கண்காணிப்பு எண்: {code} (ஒவ்வொரு பை அல்லது பெட்டியிலும் எழுதவும்)"},
    "to": {"en": "Deliver to: {address}", "si": "භාර දිය යුත්තේ: {address}", "ta": "வழங்க வேண்டிய முகவரி: {address}"},
    "hand": {"en": "Hand over at: {pickup}, by {load}. It goes by {mode} at {departs}.",
             "si": "භාර දෙන්න: {pickup}, {load} ට පෙර. {departs} ට {mode} මගින් යයි.",
             "ta": "ஒப்படைக்கும் இடம்: {pickup}, {load} க்குள். {departs} மணிக்கு {mode} மூலம் செல்லும்."},
    "local": {"en": "The buyer collects it in {town} on {day}.", "si": "ගැනුම්කරු {day} {town} හිදී රැගෙන යයි.",
              "ta": "வாங்குபவர் {day} அன்று {town} இல் பெற்றுக்கொள்வார்."},
    "link": {"en": "Track it: {url}", "si": "ලුහුබඳින්න: {url}", "ta": "கண்காணிக்க: {url}"},
    "track_cmd": {"en": "Send TRACK any time to see where it is.", "si": "එය කොහිද බලන්න ඕනෑම වේලාවක TRACK එවන්න.",
                  "ta": "அது எங்கே என்று பார்க்க எப்போது வேண்டுமானாலும் TRACK அனுப்பவும்."},
    "cost": {"en": "After you hand it over, reply COST and what you paid to send it (for example: COST 1200), so Govi's transport prices stay up to date.",
             "si": "භාර දුන් පසු, යැවීමට ගෙවූ මුදල COST ලෙස එවන්න (උදා: COST 1200), එවිට Govi ප්‍රවාහන මිල යාවත්කාලීනව තබා ගත හැක.",
             "ta": "ஒப்படைத்த பின், அனுப்ப செலுத்திய தொகையை COST என அனுப்பவும் (உதா: COST 1200), இதனால் Govi போக்குவரத்து விலைகள் புதுப்பித்த நிலையில் இருக்கும்."},
    "drop_ask": {"en": "When you have handed it over, reply DROPPED (or YES).",
                 "si": "භාර දුන් පසු DROPPED (හෝ YES) ලෙස පිළිතුරු දෙන්න.",
                 "ta": "ஒப்படைத்ததும் DROPPED (அல்லது YES) என பதில் அனுப்பவும்."},
    "recv_ask": {"en": "When it reaches you, reply RECEIVED.", "si": "ඔබට ලැබුණු විට RECEIVED ලෙස පිළිතුරු දෙන්න.",
                 "ta": "உங்களுக்கு வந்ததும் RECEIVED என பதில் அனுப்பவும்."},
    "buyer": {"en": "Your {kg} kg {crop} from {farmer} has tracking code {code}. Check it on the bags when it arrives.",
              "si": "{farmer} ගෙන් ඔබේ {crop} කිලෝ {kg} සඳහා ලුහුබැඳීමේ අංකය {code}. ලැබුණු විට මලු මත එය පරීක්ෂා කරන්න.",
              "ta": "{farmer} இடமிருந்து உங்கள் {crop} {kg} கிலோவின் கண்காணிப்பு எண் {code}. வந்ததும் பைகளில் சரிபார்க்கவும்."},
}
SITE = os.getenv("PUBLIC_URL", "").rstrip("/")  # set by deploy, or learned from the first web request


def say(key: str, lang: str, **kw) -> str:
    return SAY[key].get(lang, SAY[key]["en"]).format(**kw)


def lang_of(doc: dict) -> str:
    return accounts.reply_lang(doc.get("phone"), doc.get("lang"))


def code(m: Match) -> str:
    return "GV-" + m.id.upper()


def find(tracking: str) -> Match | None:
    want = (tracking or "").strip().upper().removeprefix("GV-").removeprefix("GV")
    return next((m for m in store.matches() if m.id.upper() == want and m.status == "confirmed"), None) if want else None


def url(m: Match) -> str:
    return f"{SITE}/t/{code(m)}" if SITE else ""


def address(o: dict) -> str:
    """Where the buyer wants it: the order's address, else the account's, else name and town, then
    the buyer's phone once, as the delivery contact (the one number the seller needs)."""
    u = accounts.user(o.get("phone")) or {}
    where = o.get("address") or u.get("address") or o.get("location") or ""
    phone = o.get("phone") or ""
    pretty = "0" + phone[2:] if phone.startswith("94") and len(phone) == 11 else phone
    name = o.get("buyer") if not who.is_phone(o.get("buyer")) else u.get("business") or u.get("name")
    name = None if who.is_phone(name) else name
    return ", ".join(x for x in [name, where] if x) + (f" · {pretty}" if pretty else "")


def slip(m: Match, lang: str) -> str:
    """The seller's message: everything needed to label and hand over the load."""
    o = store.get("orders", m.order_id) or {}
    crop = vocab.crop_name(m.crop, lang)
    lines = [say("seller_head", lang, kg=f"{m.qty_kg:.0f}", crop=crop, buyer=who.buyer(m, lang)),
             say("code", lang, code=code(m)), say("to", lang, address=address(o))]
    x = next((s for s in store.shipments() if s.id == m.shipment_id), None)
    if m.lane:
        load = datetime.fromisoformat(x.schedule["loaded"]).strftime("%a %d/%m %H:%M") if x and x.schedule.get("loaded") \
            else (m.ship_on.strftime("%a %d/%m") if m.ship_on else "")
        lines.append(say("hand", lang, pickup=m.lane.pickup or m.lane.origin, load=load,
                         mode=MODE.get(m.lane.mode, {}).get(lang, m.lane.mode), departs=m.lane.departs))
    else:
        day = (m.ship_on or m.needed_by)
        lines.append(say("local", lang, town=o.get("location") or "", day=day.strftime("%a %d/%m") if day else ""))
    lines.append(say("link", lang, url=url(m)) if url(m) else say("track_cmd", lang))
    lines += [say("drop_ask", lang), say("cost", lang)] if m.lane else []
    return "\n".join(lines)


def send_details(m: Match, send, head: dict[str, str] | None = None) -> None:
    """Both sides said YES: the seller gets the dispatch slip, the buyer the tracking code, each in
    one message. `head` (phone -> line) goes on top of that person's message, so the side that did
    not send the last YES hears "Confirmed" and the details together, not as two messages."""
    l, o = store.get("listings", m.listing_id) or {}, store.get("orders", m.order_id) or {}
    head = head or {}
    if l.get("phone"):
        body = slip(m, lang_of(l))
        send(l["phone"], "\n".join(x for x in [head.get(l["phone"]), body] if x), m.id,
             buttons=[["✅ DROPPED", "TRACK"]] if m.lane else None)
    if o.get("phone"):
        lang = lang_of(o)
        line = say("buyer", lang, kg=f"{m.qty_kg:.0f}", crop=vocab.crop_name(m.crop, lang), farmer=who.farmer(m, lang), code=code(m))
        send(o["phone"], who.tidy("\n".join(x for x in [head.get(o["phone"]), line, say("link", lang, url=url(m)) if url(m)
                                                      else say("track_cmd", lang), say("recv_ask", lang)] if x)),
             m.id, buttons=[["📦 RECEIVED", "TRACK"]])
