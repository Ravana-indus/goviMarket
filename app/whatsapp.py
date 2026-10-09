"""WhatsApp Cloud API adapter: verify, unpack inbound messages, fetch media, send replies."""
from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Optional

import httpx

GRAPH = "https://graph.facebook.com/v21.0"


@dataclass
class Inbound:
    sender: str
    text: Optional[str]
    media_id: Optional[str]
    mime_type: Optional[str]


def _token() -> str:
    return os.environ["WHATSAPP_TOKEN"]


def verify_signature(body: bytes, header: Optional[str]) -> bool:
    secret = os.getenv("WHATSAPP_APP_SECRET")
    if not secret:  # local runs and the Meta test number without an app secret configured
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def unpack(payload: dict) -> list[Inbound]:
    out = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for m in change.get("value", {}).get("messages", []):
                kind = m.get("type")
                if kind == "text":
                    out.append(Inbound(m["from"], m["text"]["body"], None, None))
                elif kind in ("image", "audio", "document"):
                    media = m[kind]
                    out.append(Inbound(m["from"], media.get("caption"), media["id"], media.get("mime_type")))
    return out


def fetch_media(media_id: str) -> bytes:
    headers = {"Authorization": f"Bearer {_token()}"}
    with httpx.Client(timeout=30) as c:
        url = c.get(f"{GRAPH}/{media_id}", headers=headers).raise_for_status().json()["url"]
        return c.get(url, headers=headers).raise_for_status().content


def send_text(to: str, body: str) -> None:
    phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
    with httpx.Client(timeout=30) as c:
        c.post(f"{GRAPH}/{phone_id}/messages", headers={"Authorization": f"Bearer {_token()}"},
               json={"messaging_product": "whatsapp", "to": to, "type": "text",
                     "text": {"body": body[:4000]}}).raise_for_status()
