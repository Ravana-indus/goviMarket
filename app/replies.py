"""Short confirmations sent back to the sender, in their language.

Numbers come from code, never from Gemini, so a price in a reply is always one we can trace."""
from __future__ import annotations

from .pricing import split
from .schemas import ParsedMessage

# Sinhala and Tamil strings need a native speaker's check before the demo.
FAIR = {
    "en": "Today's fair price for {crop}: Rs {fair}/kg (collectors pay about Rs {collector}).",
    "si": "අද {crop} සඳහා සාධාරණ මිල: කිලෝවට රු. {fair} (එකතු කරන්නන් ගෙවන්නේ රු. {collector} පමණ).",
    "ta": "இன்று {crop} நியாய விலை: கிலோவுக்கு ரூ. {fair} (சேகரிப்பாளர்கள் சுமார் ரூ. {collector} தருகிறார்கள்).",
}
UNCLEAR = {
    "en": "Please check: {fields}",
    "si": "කරුණාකර තහවුරු කරන්න: {fields}",
    "ta": "தயவுசெய்து உறுதிப்படுத்தவும்: {fields}",
}


def build(parsed: ParsedMessage, prices: dict[str, dict]) -> str:
    lines = [parsed.summary_in_sender_language]
    lang = parsed.language
    if parsed.role == "farmer":
        for item in parsed.items:
            p = prices.get(item.crop)
            if p:
                money = split(p, transport_lkr_per_kg=0)
                lines.append(FAIR[lang].format(crop=item.crop, fair=round(money["farmer_gets"]),
                                               collector=round(p["collector"])))
    if parsed.unclear:
        lines.append(UNCLEAR[lang].format(fields=", ".join(parsed.unclear)))
    return "\n".join(lines)
