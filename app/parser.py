"""Gemini turns photos, voice notes and text into ParsedMessage."""
from __future__ import annotations

import os
from typing import Optional

from .schemas import ParsedMessage

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM = """You read messages sent to Govi Market, a marketplace that connects Sri Lankan
farmers directly with restaurants, hotels, retailers and exporters.
Messages arrive as photos of handwritten orders, voice notes, or text, in Sinhala, Tamil,
English or a mix (including Singlish/Tanglish written in Latin letters).
Farmers offer harvest ("carrots 200kg ready Thursday"). Buyers place orders.
Messages typed in the Govi web app start with a hint tag: [order] or [harvest].
Rules:
- Convert every quantity to kilograms. State any unit assumption in `unclear`.
- Use lowercase singular English crop names.
- Resolve relative dates ("Thursday", "heta" = tomorrow) against today's date given below.
- Never invent items, quantities or prices. If you cannot read something, list it in `unclear`
  and lower `confidence`.
"""


def _client():
    from google import genai
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def parse(*, text: Optional[str] = None, media: Optional[bytes] = None,
          mime_type: Optional[str] = None, today: str, client=None) -> ParsedMessage:
    """Parse one inbound message. Pass `client` in tests to avoid the network."""
    if not text and not media:
        raise ValueError("need text or media")
    if client is None and not os.getenv("GEMINI_API_KEY"):
        from . import demo_parser
        return demo_parser.parse(text=text, media=media, today=today)

    from google.genai import types
    parts: list = []
    if media:
        parts.append(types.Part.from_bytes(data=media, mime_type=mime_type or "image/jpeg"))
    parts.append(f"Today is {today}.\n\nMessage text (may be empty):\n{text or ''}")

    resp = (client or _client()).models.generate_content(
        model=MODEL,
        contents=parts,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            response_mime_type="application/json",
            response_json_schema=ParsedMessage.model_json_schema(),
            temperature=0,
        ),
    )
    return ParsedMessage.model_validate_json(resp.text)
