"""Short confirmations sent back to the sender, in their language.

Numbers come from code, never from Gemini, so a price in a reply is always one we can trace."""
from __future__ import annotations

from . import vocab
from .lanes import cheapest_to, lane_cost, load_lanes
from .pricing import split
from .schemas import ParsedMessage

# Sinhala and Tamil strings need a native speaker's check before the demo.
FAIR = {
    "en": "Today's fair price for {crop}: Rs {fair}/kg (collectors pay about Rs {collector}).",
    "si": "අද {crop} සඳහා සාධාරණ මිල: කිලෝවට රු. {fair} (එකතු කරන්නන් ගෙවන්නේ රු. {collector} පමණ).",
    "ta": "இன்று {crop} நியாய விலை: கிலோவுக்கு ரூ. {fair} (சேகரிப்பாளர்கள் சுமார் ரூ. {collector} தருகிறார்கள்).",
}
FAIR_AFTER_TRANSPORT = {
    "en": "Today's fair price for {crop}: about Rs {fair}/kg after transport to Colombo (transport about Rs {transport}/kg; collectors pay about Rs {collector}). Less transport if neighbours ship with you.",
    "si": "අද {crop} සඳහා සාධාරණ මිල: කොළඹට ප්‍රවාහන වියදම අඩු කළ පසු කිලෝවට රු. {fair} පමණ (ප්‍රවාහනය කිලෝවට රු. {transport} පමණ; එකතු කරන්නන් ගෙවන්නේ රු. {collector} පමණ). අසල්වැසියන් සමඟ එකට යැවුවොත් ප්‍රවාහන වියදම අඩුයි.",
    "ta": "இன்று {crop} நியாய விலை: கொழும்புக்கு போக்குவரத்து கழித்த பின் கிலோவுக்கு சுமார் ரூ. {fair} (போக்குவரத்து கிலோவுக்கு சுமார் ரூ. {transport}; சேகரிப்பாளர்கள் சுமார் ரூ. {collector} தருகிறார்கள்). அயலவர்களுடன் சேர்ந்து அனுப்பினால் போக்குவரத்து செலவு குறையும்.",
}
LANES = load_lanes()


def price_lines(parsed: ParsedMessage, prices: dict[str, dict], lang: str | None = None) -> list[str]:
    """What a farmer should get for each crop, after transport from their town when we know it."""
    lang = lang or parsed.language
    lines = []
    for item in parsed.items:
        p = prices.get(item.crop)
        if not p:
            continue
        crop = vocab.crop_name(item.crop, lang)
        lane = cheapest_to(LANES, origin=parsed.location, dest="Colombo", kg=item.qty_kg) \
            if parsed.location and item.qty_kg else None
        if lane:
            transport = lane_cost(lane, item.qty_kg) / item.qty_kg
            money = split(p, transport_lkr_per_kg=transport)
            lines.append(FAIR_AFTER_TRANSPORT[lang].format(
                crop=crop, fair=round(money["farmer_gets"]), transport=round(transport),
                collector=round(p["collector"])))
        else:
            money = split(p, transport_lkr_per_kg=0)
            lines.append(FAIR[lang].format(crop=crop, fair=round(money["farmer_gets"]),
                                           collector=round(p["collector"])))
    return lines


def build(parsed: ParsedMessage, prices: dict[str, dict]) -> str:
    lines = [parsed.summary_in_sender_language]
    if parsed.role == "farmer":
        lines += price_lines(parsed, prices)
    # `unclear` holds internal English notes for the console; the sender only ever gets one question.
    if parsed.question_in_sender_language:
        lines.append(parsed.question_in_sender_language)
    return "\n".join(lines)


def quote(parsed: ParsedMessage, prices: dict[str, dict]) -> dict:
    """Money for a whole harvest or order, worked out once for all its items.

    A farmer's items ride together, so transport is costed on the total kg (one minimum charge,
    one handling fee, one Colombo pickup) and shared per kg. Quoting each item alone spread those
    fixed costs over 10 kg and showed a negative tomato price."""
    rows = [(i, prices[i.crop]) for i in parsed.items if i.crop in prices and i.qty_kg]
    total_kg = sum(i.qty_kg for i, _ in rows)
    out = {"total_kg": total_kg, "lane": None, "transport": 0.0, "items": [], "total": 0, "baseline": 0}
    if parsed.role == "farmer" and parsed.location and total_kg:
        lane = cheapest_to(LANES, origin=parsed.location, dest="Colombo", kg=total_kg) \
            or cheapest_to(LANES, origin=parsed.location, dest="Colombo", kg=0)
        if lane:
            out["lane"], out["transport"] = lane, lane_cost(lane, total_kg) / total_kg
    for item, p in rows:
        money = split(p, transport_lkr_per_kg=out["transport"])
        if parsed.role == "farmer":
            per, base = money["farmer_gets"], p["collector"]
        else:
            per, base = money["buyer_pays"], p["retail"]
        worth = per > 0 and (parsed.role != "farmer" or per > base)
        out["items"].append({"crop": item.crop, "kg": item.qty_kg, "per_kg": round(per), "baseline": round(base),
                             "worth_it": worth})
        if worth:
            out["total"] += round(per * item.qty_kg)
            out["baseline"] += round(base * item.qty_kg)
    return out
