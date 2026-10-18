"""Telegram Bot API adapter: unpack updates, fetch photos and voice notes, send replies.

Off unless TELEGRAM_BOT_TOKEN is set. Govi accounts are phone numbers, so a chat is linked to the
sender's number once, through Telegram's "share my phone number" button; after that the chat is
the same account as WhatsApp, the simulator and the web app, and match offers reach it here too."""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx

from . import store, vocab

log = logging.getLogger("govi.telegram")
API = "https://api.telegram.org"
MAX_FILE = 10 * 1024 * 1024
ASK_PHONE = ("Govi needs your phone number once, so this chat is the same account as WhatsApp and the app. "
             "Tap the button below.\n"
             "ඔබේ දුරකථන අංකය එක් වරක් බෙදාගන්න: පහත බොත්තම ඔබන්න.\n"
             "உங்கள் தொலைபேசி எண்ணை ஒருமுறை பகிருங்கள்: கீழே உள்ள பொத்தானை அழுத்தவும்.")
LINKED = "Linked to +{phone} ✅"
SHARE = {"keyboard": [[{"text": "📱 Share my phone number", "request_contact": True}]],
         "one_time_keyboard": True, "resize_keyboard": True}


@dataclass
class Inbound:
    chat_id: str
    text: Optional[str] = None
    file_id: Optional[str] = None
    mime_type: Optional[str] = None
    contact: Optional[str] = None  # the sender's own number, shared with the button
    id: str = ""


def _token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "")


def enabled() -> bool:
    return bool(_token())


def webhook_secret() -> str:
    """Telegram echoes this in X-Telegram-Bot-Api-Secret-Token; derived from the bot token so
    there is no second secret to store."""
    return hashlib.sha256(f"govi-telegram:{_token()}".encode()).hexdigest()[:48]


def verify(header: Optional[str]) -> bool:
    return enabled() and bool(header) and hmac.compare_digest(header, webhook_secret())


def unpack(update: dict) -> Optional[Inbound]:
    m = update.get("message") or {}
    chat = (m.get("chat") or {}).get("id")
    if chat is None or (m.get("chat") or {}).get("type") != "private":
        return None  # groups and channels are not orders
    msg = Inbound(str(chat), id=str(update.get("update_id", "")))
    c = m.get("contact")
    if c:
        if c.get("user_id") == (m.get("from") or {}).get("id"):  # their own number, not a forwarded card
            msg.contact = vocab.phone(c.get("phone_number"))
        return msg
    msg.text = m.get("text") or m.get("caption")
    if m.get("photo"):
        msg.file_id, msg.mime_type = m["photo"][-1]["file_id"], "image/jpeg"  # last is the largest size
    elif m.get("voice"):
        msg.file_id, msg.mime_type = m["voice"]["file_id"], m["voice"].get("mime_type") or "audio/ogg"
    elif m.get("audio"):
        msg.file_id, msg.mime_type = m["audio"]["file_id"], m["audio"].get("mime_type") or "audio/mpeg"
    elif (m.get("document") or {}).get("mime_type", "").startswith(("image/", "audio/")):
        msg.file_id, msg.mime_type = m["document"]["file_id"], m["document"]["mime_type"]
    return msg


def _call(method: str, **payload) -> dict:
    with httpx.Client(timeout=30) as c:
        r = c.post(f"{API}/bot{_token()}/{method}", json=payload)
        r.raise_for_status()
        return r.json().get("result") or {}


def fetch_media(file_id: str) -> bytes:
    f = _call("getFile", file_id=file_id)
    if f.get("file_size", 0) > MAX_FILE:
        raise ValueError("file too big")
    with httpx.Client(timeout=30) as c:
        return c.get(f"{API}/file/bot{_token()}/{f['file_path']}").raise_for_status().content


def send_text(chat_id: str, body: str, *, ask_phone: bool = False, keyboard: Optional[list] = None) -> None:
    """`keyboard` rows of button labels replace the chat's buttons ([] removes them); without it
    the buttons already showing stay."""
    payload = {"chat_id": chat_id, "text": body[:4000]}
    if ask_phone:
        payload["reply_markup"] = SHARE
    elif keyboard == []:
        payload["reply_markup"] = {"remove_keyboard": True}
    elif keyboard:
        payload["reply_markup"] = {"keyboard": [[{"text": b} for b in row] for row in keyboard],
                                   "resize_keyboard": True, "is_persistent": True}
    _call("sendMessage", **payload)


def set_webhook(url: str, commands: list[dict]) -> dict:
    _call("setMyCommands", commands=commands)
    return _call("setWebhook", url=url, secret_token=webhook_secret(),
                 allowed_updates=["message"], drop_pending_updates=True)


def phone_for(chat_id: str) -> Optional[str]:
    return (store.DB.one("telegram", chat_id) or {}).get("phone")


def link(chat_id: str, phone: str) -> None:
    store.DB.put("telegram", chat_id, {"phone": phone})
    store.DB.put("telegram_phone", phone, {"chat_id": chat_id})


def send_to_phone(phone: str, body: str, keyboard: Optional[list] = None) -> bool:
    """Deliver a Govi message to the Telegram chat linked to this number, if there is one."""
    if not enabled() or not phone:
        return False
    chat = (store.DB.one("telegram_phone", phone) or {}).get("chat_id")
    if not chat:
        return False
    try:
        send_text(chat, body, keyboard=keyboard)
        return True
    except Exception:
        log.exception("telegram send failed")
        return False
