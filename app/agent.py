"""Gemini agent that writes the match message each side receives.

It calls tools for every number it quotes, so prices and times in a message trace back to code."""
from __future__ import annotations

import os

from . import ai
from .lanes import load_lanes
from .pricing import split
from .schemas import Lang, Match

MODEL = os.getenv("GEMINI_AGENT_MODEL", ai.MODEL)
LANG_NAME = {"si": "Sinhala", "ta": "Tamil", "en": "English"}
_PRICES: dict[str, dict] = {}


def get_price_board(crop: str) -> dict:
    """Today's Rs/kg for a crop: what the village collector pays, Colombo retail, and the fair Govi price."""
    p = _PRICES.get(crop.lower())
    if not p:
        return {"error": f"no price for {crop}"}
    m = split(p, transport_lkr_per_kg=0)
    return {"crop": crop, "collector": p["collector"], "retail": p["retail"],
            "farmer_fair_before_transport": m["farmer_gets"], "buyer_price": m["buyer_pays"]}


def get_lane_options(origin: str, dest: str) -> list[dict]:
    """All public-transport options (night bus, train parcel, SL Post, lorry) between two towns."""
    return [l.model_dump() for l in load_lanes()
            if l.origin.lower() == origin.lower() and l.dest.lower() == dest.lower()]


SYSTEM = """You are Govi Market's WhatsApp assistant. You write ONE short message (max 6 lines) to
a farmer or a buyer about a proposed match. Write it in {lang}, in simple everyday words a
farmer with little schooling understands. Use the given match facts and your tools; never
invent a number. For a farmer: who buys, how many kg, Rs/kg they get AFTER transport versus the collector
price, that transport (Rs/kg) is already taken off, whether the load is shared with
neighbours to cut the cost, and which bus, train or lorry to load and when. For a buyer: who grows it, kg, Rs/kg versus the retail price,
and when it arrives. If a transport source is "ESTIMATE", say the time is approximate.
End with: reply YES to confirm or NO to decline (in {lang}, keep the words YES and NO in English too)."""


def _template(m: Match, party: str, lang: Lang, shared_with: int = 0) -> str:
    lane = f"{m.lane.mode.replace('_', ' ')} from {m.lane.origin} at {m.lane.departs}" if m.lane else "local pickup"
    if party == "farmer":
        shared = f", shared with {shared_with} other farmer{'s' if shared_with > 1 else ''}" if shared_with else ""
        body = (f"Buyer found: {m.buyer} wants {m.qty_kg:.0f} kg {m.crop}.\n"
                f"You get Rs {m.farmer_gets_lkr_per_kg:.0f}/kg after transport (collector pays Rs {m.collector_pays_lkr_per_kg:.0f}).\n"
                f"Transport Rs {m.transport_lkr_per_kg:.0f}/kg is already taken off{shared}.\n"
                f"Send by {lane}.")
    else:
        body = (f"Supplier found: {m.farmer} has {m.qty_kg:.0f} kg {m.crop} for you.\n"
                f"You pay Rs {m.buyer_pays_lkr_per_kg:.0f}/kg (retail Rs {m.market_retail_lkr_per_kg:.0f}).\n"
                f"Comes by {lane}.")
    return body + "\nReply YES to confirm or NO to decline."


def explain(m: Match, *, party: str, lang: Lang, prices: dict[str, dict], client=None,
            shared_with: int = 0) -> str:
    """Message for `party` ('farmer' or 'buyer') about match `m`.

    `shared_with` is how many other farmers' loads ride in the same shipment."""
    from . import ai
    if client is None and not ai.enabled():
        return _template(m, party, lang, shared_with)
    from google import genai
    from google.genai import types

    _PRICES.clear(); _PRICES.update(prices)
    client = client or ai.client()
    facts = m.model_dump_json(exclude={"status", "farmer_ok", "buyer_ok", "solo_lane"})
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=(f"Write the message for the {party}.\nMatch facts (JSON): {facts}\n"
                      f"Other farmers sharing this shipment: {shared_with}."),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM.format(lang=LANG_NAME[lang]),
                tools=[get_price_board, get_lane_options],
                temperature=0.3,
            ),
        )
        return (resp.text or "").strip() or _template(m, party, lang, shared_with)
    except Exception as e:
        ai.failed("match message", e)
        return _template(m, party, lang, shared_with)
