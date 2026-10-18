"""The Telegram conversation around the order chat: link the phone number, register the person
(language, seller or buyer, town, name) with buttons, and the /language, /restart and /status
commands. Orders themselves go through main.handle like every other channel."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from . import accounts, convo, store, telegram, vocab

log = logging.getLogger("govi.telegram")
LANG_BUTTONS = {"සිංහල": "si", "தமிழ்": "ta", "English": "en"}
STEPS = ("lang", "role", "town", "name")
T = {
    "ask_lang": {"en": "Choose your language. Govi will always reply in it.\nභාෂාව තෝරන්න.\nமொழியைத் தேர்ந்தெடுக்கவும்."},
    "ask_role": {"en": "Do you sell or buy on Govi?", "si": "ඔබ Govi හි විකුණනවාද, මිලදී ගන්නවාද?",
                 "ta": "நீங்கள் Govi-யில் விற்கிறீர்களா, வாங்குகிறீர்களா?"},
    "farmer": {"en": "🌾 I sell (farmer)", "si": "🌾 මම විකුණනවා (ගොවි)", "ta": "🌾 நான் விற்கிறேன் (விவசாயி)"},
    "buyer": {"en": "🛒 I buy (buyer)", "si": "🛒 මම මිලදී ගන්නවා (ගැනුම්කරු)", "ta": "🛒 நான் வாங்குகிறேன் (வாங்குபவர்)"},
    "ask_town": {"en": "Which town are you in? Type it, for example Dambulla or Colombo.",
                 "si": "ඔබ සිටින්නේ කුමන නගරයේද? ලියන්න, උදා: දඹුල්ල හෝ කොළඹ.",
                 "ta": "நீங்கள் எந்த ஊரில் இருக்கிறீர்கள்? எழுதுங்கள், உதா: தம்புள்ளை அல்லது கொழும்பு."},
    "ask_name": {"en": "What name should buyers and farmers see? Your name or your business.",
                 "si": "ගැනුම්කරුවන්ට සහ ගොවීන්ට පෙනෙන නම කුමක්ද? ඔබේ නම හෝ ව්‍යාපාරයේ නම.",
                 "ta": "வாங்குபவர்களும் விவசாயிகளும் பார்க்கும் பெயர் என்ன? உங்கள் பெயர் அல்லது வணிகப் பெயர்."},
    "done": {"en": "All set, {name} ✅ {role} in {town}.\nChange it any time with /restart, or the language with /language.",
             "si": "සියල්ල සූදානම්, {name} ✅ {town} හි {role}.\nඕනෑම වේලාවක /restart මගින් වෙනස් කරන්න, භාෂාව /language මගින්.",
             "ta": "எல்லாம் தயார், {name} ✅ {town}-இல் {role}.\nஎப்போது வேண்டுமானாலும் /restart மூலம் மாற்றவும், மொழியை /language மூலம்."},
    "role_farmer": {"en": "Seller", "si": "විකුණුම්කරු", "ta": "விற்பனையாளர்"},
    "role_buyer": {"en": "Buyer", "si": "ගැනුම්කරු", "ta": "வாங்குபவர்"},
    "pick": {"en": "Please tap one of the buttons below.", "si": "කරුණාකර පහත බොත්තමක් ඔබන්න.",
             "ta": "கீழே உள்ள பொத்தான்களில் ஒன்றை அழுத்தவும்."},
    "held": {"en": "I kept your message and will read it as soon as you finish.",
             "si": "ඔබේ පණිවිඩය තබාගත්තා; අවසන් වූ වහාම කියවනවා.",
             "ta": "உங்கள் செய்தியை வைத்திருக்கிறேன்; முடிந்தவுடன் படிப்பேன்."},
    "m_status": {"en": "📦 My orders", "si": "📦 මගේ ඇණවුම්", "ta": "📦 என் ஆர்டர்கள்"},
    "m_lang": {"en": "🌐 Language", "si": "🌐 භාෂාව", "ta": "🌐 மொழி"},
    "m_restart": {"en": "🔄 Restart registration", "si": "🔄 නැවත ලියාපදිංචි වන්න", "ta": "🔄 மீண்டும் பதிவு"},
}
COMMANDS = [{"command": "start", "description": "Start / ආරම්භය / தொடங்கு"},
            {"command": "status", "description": "My orders / මගේ ඇණවුම් / என் ஆர்டர்கள்"},
            {"command": "edit", "description": "Change my last order / වෙනස් කරන්න / மாற்று"},
            {"command": "language", "description": "Change language / භාෂාව / மொழி"},
            {"command": "restart", "description": "Register again / නැවත ලියාපදිංචිය / மீண்டும் பதிவு"},
            {"command": "help", "description": "How to use Govi / උදව් / உதவி"}]


def t(key: str, lang: str | None, **kw) -> str:
    return (T[key].get(lang or "en") or T[key]["en"]).format(**kw)


def _label_map(*keys: str) -> dict[str, str]:
    return {T[k][lang]: k for k in keys for lang in T[k]}


MENU_WORDS = _label_map("m_status", "m_lang", "m_restart")
ROLE_WORDS = _label_map("farmer", "buyer") | {"sell": "farmer", "seller": "farmer", "farmer": "farmer",
                                               "buy": "buyer", "buyer": "buyer"}


def menu(lang: str) -> list[list[str]]:
    return [[t("m_status", lang)], [t("m_lang", lang), t("m_restart", lang)]]


def _state(chat: str) -> dict:
    return store.DB.one("telegram", chat) or {}


def _set_step(chat: str, step: str | None, only: bool = False) -> None:
    store.DB.put("telegram", chat, {**_state(chat), "step": step, "only": only})


def _next_step(u: dict) -> str | None:
    have = {"lang": u.get("lang") in convo.LANGS, "role": u.get("role") in ("farmer", "buyer"),
            "town": bool(u.get("location")), "name": bool(u.get("name") or u.get("business"))}
    return next((s for s in STEPS if not have[s]), None)


def _ask(chat: str, step: str, lang: str) -> None:
    if step == "lang":
        telegram.send_text(chat, t("ask_lang", "en"), keyboard=[list(LANG_BUTTONS)])
    elif step == "role":
        telegram.send_text(chat, t("ask_role", lang), keyboard=[[t("farmer", lang)], [t("buyer", lang)]])
    else:
        telegram.send_text(chat, t("ask_" + step, lang), keyboard=[])


def _hold(chat: str, msg: telegram.Inbound) -> None:
    store.DB.put("telegram_pending", chat, {"text": msg.text, "file_id": msg.file_id, "mime_type": msg.mime_type})


def _start_or_resume(chat: str, phone: str, handle) -> None:
    """Ask the next missing registration step, or, once registered, read any held message."""
    u = accounts.user(phone) or accounts.link(phone, name=None, role=None, via="telegram")
    lang = accounts.chosen_lang(phone) or "en"
    step = _next_step(u)
    _set_step(chat, step)
    if step:
        _ask(chat, step, lang)
        return
    held = store.DB.one("telegram_pending", chat) or {}
    if held.get("text") or held.get("file_id"):
        store.DB.delete("telegram_pending", chat)
        _order(chat, phone, telegram.Inbound(chat, held.get("text"), held.get("file_id"), held.get("mime_type")), handle)


def _answer_step(chat: str, phone: str, step: str, msg: telegram.Inbound, handle) -> None:
    lang = accounts.chosen_lang(phone) or "en"
    text = (msg.text or "").strip()
    u = accounts.user(phone) or {}
    if step == "lang":
        pick = LANG_BUTTONS.get(text) or convo.lang_word(text)
        if pick not in convo.LANGS:
            return _reask(chat, phone, step, msg, lang)
        accounts.set_lang(phone, pick, via="telegram")
        if _state(chat).get("only"):
            _set_step(chat, None)
            telegram.send_text(chat, convo.t("lang_set", pick), keyboard=menu(pick))
            return
    elif step == "role":
        role = ROLE_WORDS.get(text) or ROLE_WORDS.get(text.lower()) or vocab.role_said(text)
        if not role:
            return _reask(chat, phone, step, msg, lang)
        store.DB.put("users", phone, {**u, "role": role})
    elif step in ("town", "name"):
        if not text or msg.file_id or text.startswith("/") or len(text) > 60:
            return _reask(chat, phone, step, msg, lang)
        field = "location" if step == "town" else "name"
        store.DB.put("users", phone, {**u, field: vocab.town(text) if step == "town" else text})
    u = accounts.user(phone) or {}
    if _state(chat).get("restart"):  # /restart asks every step again, then falls back to the missing ones
        rest = STEPS[STEPS.index(step) + 1:]
        if rest:
            _set_step(chat, rest[0])
            store.DB.put("telegram", chat, {**_state(chat), "restart": True})
            return _ask(chat, rest[0], accounts.chosen_lang(phone) or "en")
        store.DB.put("telegram", chat, {**_state(chat), "restart": False})
    if _next_step(u) is None:
        lang = accounts.chosen_lang(phone) or "en"
        telegram.send_text(chat, "\n\n".join([
            t("done", lang, name=u.get("business") or u.get("name"), role=t("role_" + u["role"], lang),
              town=vocab.town_name(u["location"], lang)),
            convo.t("hello", lang)]), keyboard=menu(lang))
    _start_or_resume(chat, phone, handle)


def _reask(chat: str, phone: str, step: str, msg: telegram.Inbound, lang: str) -> None:
    if msg.file_id or (step in ("lang", "role") and len((msg.text or "").split()) > 2):
        _hold(chat, msg)  # an order sent mid-registration is kept, not lost
        telegram.send_text(chat, t("held", lang))
    elif step in ("lang", "role"):
        telegram.send_text(chat, t("pick", lang))
    _ask(chat, step, lang)


def _order(chat: str, phone: str, msg: telegram.Inbound, handle) -> None:
    send = lambda body: telegram.send_text(chat, body)  # noqa: E731
    if not msg.text and not msg.file_id:
        send(convo.t("hello", accounts.chosen_lang(phone) or "en"))
        return
    try:
        media = telegram.fetch_media(msg.file_id) if msg.file_id else None
        handle(text=(msg.text or "").strip()[:2000] or None, media=media, mime_type=msg.mime_type,
               sender=phone, today=date.today(), via="telegram", deliver=send)
    except Exception:
        log.exception("telegram message failed")
        try:
            lang = accounts.chosen_lang(phone) or convo.load(phone).get("lang") or "en"
            send(convo.t("unread_audio" if (msg.mime_type or "").startswith("audio") else "unread_image", lang)
                 if msg.file_id else "Sorry, we could not read that. Please try again.")
        except Exception:
            log.exception("telegram apology failed")


def process(msg: telegram.Inbound, handle) -> None:
    if msg.id:  # Telegram re-sends an update it thinks we missed
        if store.DB.one("seen", f"tg{msg.id}"):
            return
        store.DB.put("seen", f"tg{msg.id}", {"at": datetime.now(timezone.utc).isoformat()})
    chat = msg.chat_id
    phone = telegram.phone_for(chat)
    if msg.contact:
        telegram.link(chat, msg.contact)
        telegram.send_text(chat, telegram.LINKED.format(phone=msg.contact))
        return _start_or_resume(chat, msg.contact, handle)
    if not phone:
        if (msg.text or msg.file_id) and not (msg.text or "").startswith("/"):
            _hold(chat, msg)
        telegram.send_text(chat, telegram.ASK_PHONE, ask_phone=True)
        return
    text = (msg.text or "").strip()
    cmd = MENU_WORDS.get(text) or (text.split()[0].split("@")[0].lower() if text.startswith("/") else None)
    lang = accounts.chosen_lang(phone) or "en"
    if cmd in ("/restart", "m_restart"):
        store.DB.put("telegram", chat, {**_state(chat), "step": "lang", "only": False, "restart": True})
        return _ask(chat, "lang", lang)
    if cmd in ("/language", "/lang", "m_lang"):
        _set_step(chat, "lang", only=True)
        return _ask(chat, "lang", lang)
    step = _state(chat).get("step")
    if step:
        if cmd in ("/start", "/help"):
            return _ask(chat, step, lang)
        return _answer_step(chat, phone, step, msg, handle)
    if _next_step(accounts.user(phone) or {}):  # registered on another channel without all the details
        if not cmd:
            _hold(chat, msg)
        return _start_or_resume(chat, phone, handle)
    if cmd in ("/status", "m_status", "/edit"):
        return _order(chat, phone, telegram.Inbound(chat, "EDIT" if cmd == "/edit" else "STATUS"), handle)
    if cmd:  # /start, /help and anything unknown
        telegram.send_text(chat, convo.t("hello", lang), keyboard=menu(lang))
        return
    _order(chat, phone, msg, handle)
