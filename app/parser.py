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
  Plain "onion" (lunu, ළූණු, வெங்காயம்) is "big onion"; red or small onion (rathu lunu, சின்ன வெங்காயம்) is "red onion".
  Cabbage is gova/ගෝවා/கோவா.
- Use these exact town names when the place is one of them: {towns}. A Colombo suburb is "Colombo".
- Resolve relative dates ("Thursday", "heta" = tomorrow) against today's date given below.
  "Day after tomorrow" (anidda, අනිද්දා, நாளை மறுநாள்) is today + 2 days.
  "Next week" (heta sathiya, அடுத்த வாரம்) means Monday of next week. No date at all: `when` null.
  A resolved date is not unclear.
- Role: if "About the sender" says this number is a farmer or a buyer, use that unless the message
  plainly says the opposite. Never ask the sender who they are.
- If "Pending order" is given, it is NOT placed yet; the sender is replying to it. Pick `intent`:
  "confirm" for yes/ok/go ahead/ow/hari/ஆம்/சரி (also in a voice note), "cancel" for no/cancel,
  "edit" when the message adds, removes or changes anything in it or answers our question. For "edit"
  return ONLY what changes: each added or changed item with its NEW total kg ("2 more kg tomato" on
  10 kg is 12), each removed item with qty_kg 0, and location/when/sender_name only if they change
  (else null). A message that agrees AND changes something ("yes but 15kg tomato") is "edit".
  Use "order" only for a clearly separate new order, and then return all of it.
- With no pending order: "status" for questions about their orders, "chat" for greetings, thanks or
  anything with no crop in it, else "order".
- Everything the sender sees (summary, question) is in their language only. `unclear` is internal.
- Read typos and number words generously ("onlon" is onion, "two kilo" is 2 kg, "gova" is cabbage).
  Every item the sender lists must appear in `items`; never drop one you cannot name, use your best
  lowercase English guess and say so in `unclear`.
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
          mime_type: Optional[str] = None, today: str, client=None,
          context: Optional[str] = None) -> ParsedMessage:
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
    parts.append(f"Today is {today}.\n{context or ''}\n\nMessage text (may be empty):\n{text or ''}")

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
