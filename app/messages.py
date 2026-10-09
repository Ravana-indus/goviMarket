"""Gemini writes short WhatsApp messages from facts the code already decided.

The numbers, times and choices come from code; Gemini only puts them into plain words in the
person's language. Without a key, or if the call fails, the code's own template is sent."""
from __future__ import annotations

import json
import os

LANG_NAME = {"si": "Sinhala", "ta": "Tamil", "en": "English"}
SYSTEM = """You write ONE WhatsApp message (max 6 short lines) for Govi Market, a Sri Lankan
farm-to-buyer marketplace. Write in {lang}, in simple everyday words. Use only the facts given;
never invent a number, time, place or name. Be calm and direct: say what happened, what we already
did, and what (if anything) the reader must do. {extra}"""


def write(purpose: str, facts: dict, lang: str, fallback: str, *, extra: str = "", client=None) -> str:
    if client is None and not os.getenv("GEMINI_API_KEY"):
        return fallback
    try:
        from google import genai
        from google.genai import types
        client = client or genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        resp = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=f"Purpose: {purpose}\nFacts (JSON): {json.dumps(facts, default=str, ensure_ascii=False)}",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM.format(lang=LANG_NAME.get(lang, "English"), extra=extra),
                temperature=0.3),
        )
        return (resp.text or "").strip() or fallback
    except Exception:
        return fallback
