"""Canonical crop and town names, so whatever Gemini or a person writes lands on the price board
and the transport table. Unknown names pass through unchanged (and simply won't match)."""
from __future__ import annotations

import re

CROPS = {
    "carrot": ["carrots", "කැරට්", "கேரட்"],
    "leeks": ["leek", "ලීක්ස්", "ලීක්", "லீக்ஸ்"],
    "beans": ["bean", "green bean", "green beans", "බෝංචි", "பீன்ஸ்", "agarawatte beans"],
    "tomato": ["tomatoes", "තක්කාලි", "தக்காளி"],
    "red onion": ["red onions", "small onion", "shallot", "shallots", "රතු ළූණු", "சின்ன வெங்காயம்", "சிவப்பு வெங்காயம்"],
    "maize": ["corn", "sweet corn", "බඩ ඉරිඟු", "ඉරිඟු", "சோளம்", "மக்காச்சோளம்"],
    "green chilli": ["green chillies", "green chili", "green chilies", "chilli", "chillies", "chili", "අමු මිරිස්", "මිරිස්", "பச்சை மிளகாய்", "மிளகாய்"],
}
TOWNS = {
    "Nuwara Eliya": ["nuwaraeliya", "nuwara-eliya", "n'eliya", "නුවරඑළිය", "நுவரெலியா"],
    "Dambulla": ["දඹුල්ල", "தம்புள்ளை"],
    "Jaffna": ["යාපනය", "யாழ்ப்பாணம்"],
    "Badulla": ["බදුල්ල", "பதுளை"],
    "Ampara": ["අම්පාර", "அம்பாறை"],
    "Kurunegala": ["kurunagala", "කුරුණෑගල", "குருநாகல்"],
    "Kandy": ["මහනුවර", "கண்டி"],
    "Colombo": ["කොළඹ", "கொழும்பு"],
}


def _index(table: dict[str, list[str]]) -> dict[str, str]:
    out = {}
    for name, aliases in table.items():
        for a in [name, *aliases]:
            out[re.sub(r"\s+", " ", a.lower().strip())] = name
    return out


_CROP, _TOWN = _index(CROPS), _index(TOWNS)


def crop(name: str) -> str:
    key = re.sub(r"\s+", " ", (name or "").lower().strip())
    return _CROP.get(key, key)


def town(name: str | None) -> str | None:
    if not name:
        return name
    head = name.split(",")[0]
    key = re.sub(r"\s+", " ", head.lower().strip())
    if key in _TOWN:
        return _TOWN[key]
    for alias, canon in _TOWN.items():  # "Colombo 03", "Dambulla Economic Centre"
        if key.startswith(alias):
            return canon
    return name.strip()


def phone(raw: str | None) -> str | None:
    """Digits only, Sri Lankan local numbers to 94…; None if it is not a phone number."""
    d = re.sub(r"\D", "", raw or "")
    if len(d) == 10 and d.startswith("0"):
        d = "94" + d[1:]
    return d if 9 <= len(d) <= 15 else None
