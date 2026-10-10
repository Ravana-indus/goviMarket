"""Gemini turns photos, voice notes and text into ParsedMessage."""
from __future__ import annotations

import os
from typing import Optional

from . import ai, audio, vocab
from .schemas import ParsedMessage

MODEL = ai.MODEL

_SYSTEM = """You read messages sent to Govi Market, a marketplace that connects Sri Lankan
farmers directly with restaurants, hotels, retailers and exporters.
Messages arrive as photos of handwritten orders, voice notes, or text, in Sinhala, Tamil,
English or a mix (including Singlish/Tanglish written in Latin letters).
Farmers offer harvest ("carrots 200kg ready Thursday"). Buyers place orders.
Messages typed in the Govi web app start with a hint tag: [order] or [harvest].
Rules:
- Convert every quantity to kilograms. State any unit assumption in `unclear`.
- Use these exact crop names when the crop is one of them: {crops}. Otherwise a lowercase English name.
- Use these exact town names when the place is one of them: {towns}. A Colombo suburb is "Colombo".
- Resolve relative dates ("Thursday", "heta" = tomorrow) against today's date given below.
- Never invent items, quantities or prices. If you cannot read something, list it in `unclear`
  and lower `confidence`.
"""


SYSTEM = _SYSTEM.format(crops=", ".join(vocab.CROPS), towns=", ".join(vocab.TOWNS))


def normalise(p: ParsedMessage) -> ParsedMessage:
    """Snap crop and town names to the ones the price board and transport table use."""
    for it in p.items:
        it.crop = vocab.crop(it.crop)
    p.location = vocab.town(p.location)
    return p


def _client():
    return ai.client()


def parse(*, text: Optional[str] = None, media: Optional[bytes] = None,
          mime_type: Optional[str] = None, today: str, client=None) -> ParsedMessage:
    """Parse one inbound message. Pass `client` in tests to avoid the network."""
    if not text and not media:
        raise ValueError("need text or media")
    from . import demo_parser
    if client is None and not ai.enabled():
        return normalise(demo_parser.parse(text=text, media=media, today=today))

    from google.genai import types
    parts: list = []
    if media:
        mime = (mime_type or "image/jpeg").split(";")[0].strip().lower()  # "audio/ogg; codecs=opus"
        media, mime = audio.for_gemini(media, mime)
        parts.append(types.Part.from_bytes(data=media, mime_type=mime))
    parts.append(f"Today is {today}.\n\nMessage text (may be empty):\n{text or ''}")

    try:
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
        return normalise(ParsedMessage.model_validate_json(resp.text))
    except Exception as e:
        ai.failed("parse", e)
        if media or client is not None:
            raise  # photos and voice notes need Gemini; tests want the real error
        # Text still gets an answer from the built-in parser while Gemini is down or rate-limited.
        return normalise(demo_parser.parse(text=text, media=None, today=today))
