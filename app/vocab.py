"""Canonical crop and town names, so whatever Gemini or a person writes lands on the price board
and the transport table. Unknown names pass through unchanged (and simply won't match)."""
from __future__ import annotations

import difflib
import re

CROPS = {
    "carrot": ["carrots", "karat", "kerat", "කැරට්", "கேரட்"],
    "leeks": ["leek", "ලීක්ස්", "ලීක්", "லீக்ஸ்"],
    "beans": ["bean", "bonchi", "boonchi", "bonji", "green bean", "green beans", "බෝංචි", "பீன்ஸ்", "agarawatte beans"],
    "tomato": ["tomatoes", "thakkali", "thakkaali", "takkali", "තක්කාලි", "தக்காளி"],
    "red onion": ["red onions", "rathu lunu", "rathulunu", "chinna vengayam", "small onion", "shallot", "shallots", "රතු ළූණු", "சின்ன வெங்காயம்", "சிவப்பு வெங்காயம்"],
    "maize": ["corn", "iringu", "badairingu", "bada iringu", "solam", "sweet corn", "බඩ ඉරිඟු", "ඉරිඟු", "சோளம்", "மக்காச்சோளம்"],
    "green chilli": ["green chillies", "amu miris", "amumiris", "miris", "milagai", "green chili", "green chilies", "chilli", "chillies", "chili", "අමු මිරිස්", "මිරිස්", "பச்சை மிளகாய்", "மிளகாய்"],
    # Plain "onion" (lunu, வெங்காயம்) in a Sri Lankan kitchen order means big onion.
    "big onion": ["onion", "vengayam", "periya vengayam", "onions", "big onions", "b onion", "lunu", "loku lunu", "ලොකු ළූණු", "ළූණු",
                  "வெங்காயம்", "பெரிய வெங்காயம்"],
    "cabbage": ["cabbages", "gova", "gowa", "kova", "ගෝවා", "கோவா", "முட்டைக்கோஸ்", "முட்டைகோஸ்"],
    "potato": ["potatoes", "ala", "අල", "உருளைக்கிழங்கு", "உருளை"],
    "beetroot": ["beet", "beets", "beetroots", "බීට්", "බීට්රූට්", "பீட்ரூட்"],
    "pumpkin": ["pumpkins", "wattakka", "watakka", "poosani", "වට්ටක්කා", "பூசணிக்காய்", "பூசணி"],
    "brinjal": ["brinjals", "eggplant", "aubergine", "wambatu", "batu", "kathirikai", "වම්බටු", "கத்தரிக்காய்", "கத்தரி"],
}
# What the sender sees: crop names in their own script.
CROP_NAME = {
    "carrot": {"si": "කැරට්", "ta": "கேரட்"},
    "leeks": {"si": "ලීක්ස්", "ta": "லீக்ஸ்"},
    "beans": {"si": "බෝංචි", "ta": "பீன்ஸ்"},
    "tomato": {"si": "තක්කාලි", "ta": "தக்காளி"},
    "red onion": {"si": "රතු ළූණු", "ta": "சின்ன வெங்காயம்"},
    "maize": {"si": "බඩ ඉරිඟු", "ta": "சோளம்"},
    "green chilli": {"si": "අමු මිරිස්", "ta": "பச்சை மிளகாய்"},
    "big onion": {"si": "ලොකු ළූණු", "ta": "வெங்காயம்"},
    "cabbage": {"si": "ගෝවා", "ta": "கோவா"},
    "potato": {"si": "අල", "ta": "உருளைக்கிழங்கு"},
    "beetroot": {"si": "බීට්", "ta": "பீட்ரூட்"},
    "pumpkin": {"si": "වට්ටක්කා", "ta": "பூசணிக்காய்"},
    "brinjal": {"si": "වම්බටු", "ta": "கத்தரிக்காய்"},
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


TOWN_NAME = {
    "Nuwara Eliya": {"si": "නුවරඑළිය", "ta": "நுவரெலியா"}, "Dambulla": {"si": "දඹුල්ල", "ta": "தம்புள்ளை"},
    "Jaffna": {"si": "යාපනය", "ta": "யாழ்ப்பாணம்"}, "Badulla": {"si": "බදුල්ල", "ta": "பதுளை"},
    "Ampara": {"si": "අම්පාර", "ta": "அம்பாறை"}, "Kurunegala": {"si": "කුරුණෑගල", "ta": "குருநாகல்"},
    "Kandy": {"si": "මහනුවර", "ta": "கண்டி"}, "Colombo": {"si": "කොළඹ", "ta": "கொழும்பு"},
}


def town_name(town: str | None, lang: str) -> str:
    return TOWN_NAME.get(town or "", {}).get(lang) or town or "?"


def crop_name(crop: str, lang: str) -> str:
    return CROP_NAME.get(crop, {}).get(lang) or crop


def crops_in(text: str | None) -> set[str]:
    """Every crop named anywhere in a message, in any language ("remove the carrot", "கேரட் வேண்டாம்")."""
    t = " " + re.sub(r"[,.;:!?()\"'/+&-]+", " ", (text or "").lower()) + " "
    found = set()
    for alias, canon in sorted(_CROP.items(), key=lambda kv: -len(kv[0])):
        # Latin words need word edges ("ala" is not in "salad"); Sinhala and Tamil take suffixes
        # ("கேரட்டை", "තක්කාලිත්"), so a plain substring is right there.
        pat = (r"(?<![a-z])" + re.escape(alias) + r"(?:s|es)?(?![a-z])") if alias.isascii() else re.escape(alias)
        if re.search(pat, t):
            found.add(canon)
            t = re.sub(pat, " ", t)  # "red onion" must not also count as "onion"
    # Typos on a phone keyboard ("onlon", "tomatoe", "carot"): a close match on a single word.
    for word in re.findall(r"[a-z]{4,}", t):
        if word in NOT_CROPS:
            continue
        hit = difflib.get_close_matches(word, _LATIN_CROP, n=1, cutoff=0.8)
        if hit:
            found.add(_CROP[hit[0]])
    return found


# Words that look like crop names to a fuzzy matcher but never are.
NOT_CROPS = {"need", "needed", "kilo", "kilos", "after", "tomorrow", "ready", "order", "from", "this", "that",
             "today", "please", "with", "send", "beans", "make", "more", "less", "only", "also", "deliver",
             "delivery", "colombo", "kandy", "wrong", "change", "remove", "week", "next", "heta", "anidda"}


def script(text: str | None) -> str | None:
    """'si' or 'ta' when the text is written in that script, else None (Latin letters say nothing)."""
    for ch in text or "":
        if "\u0d80" <= ch <= "\u0dff":
            return "si"
        if "\u0b80" <= ch <= "\u0bff":
            return "ta"
    return None


# Short replies people actually send on WhatsApp. Matched against the whole message only.
YES = {"yes", "y", "yeah", "yep", "yup", "ya", "ok", "okay", "k", "kk", "ok ok", "sure", "confirm", "confirmed",
       "done", "go", "go ahead", "correct", "right", "yes please", "ok confirm", "yes confirm", "agreed", "fine",
       "ow", "ow ow", "owu", "ou", "hari", "hari hari", "ehenam", "ow hari", "ok hari",
       "ඔව්", "ඔව්ව", "හරි", "හරි හරි", "ඔව් හරි", "එහෙනම්", "ඕනෙ", "ඕන",
       "ஆம்", "ஆமா", "ஆமாம்", "சரி", "ஓகே", "ஓக்கே", "சரி சரி", "aam", "aama", "aamam", "sari", "seri",
       "👍", "👌", "✅", "🙏👍"}
NO = {"no", "n", "nope", "nah", "no thanks", "don't", "dont", "not now",
      "epa", "naha", "nehe", "na", "නැහැ", "නෑ", "එපා", "නැහැ එපා",
      "இல்லை", "இல்ல", "வேண்டாம்", "venam", "vendam", "illa", "illai", "👎", "❌"}
CANCEL = {"cancel", "cancel it", "cancel order", "stop", "delete", "අවලංගු", "අවලංගු කරන්න", "කැන්සල්",
          "ரத்து", "ரத்து செய்", "ரத்து செய்யவும்", "கேன்சல்"}
STATUS = {"status", "my orders", "orders", "my order", "order status", "where is my order", "track",
          "තත්ත්වය", "මගේ ඇණවුම්", "ඇණවුම්", "நிலை", "என் ஆர்டர்", "என் ஆர்டர்கள்", "ஆர்டர் நிலை"}
HELLO = {"hi", "hello", "hey", "helo", "hii", "help", "menu", "start", "ayubowan", "vanakkam", "good morning",
         "ආයුබෝවන්", "හලෝ", "හායි", "උදව්", "வணக்கம்", "ஹலோ", "உதவி"}
THANKS = {"thanks", "thank you", "thx", "ty", "thank u", "stuti", "istuti", "isthuthi", "nandri",
          "ස්තූතියි", "බොහොම ස්තූතියි", "நன்றி", "மிக்க நன்றி", "🙏"}
SELLING = {"selling", "sell", "i am selling", "farmer", "seller", "vikunanawa", "විකුණනවා", "විකිණීමට", "ගොවියා",
           "விற்கிறேன்", "விற்பனை", "விவசாயி"}
BUYING = {"buying", "buy", "i am buying", "buyer", "order", "ganna", "gannawa", "ගන්නවා", "මිලදී ගන්නවා", "ගැනුම්කරු",
          "வாங்குகிறேன்", "வாங்க", "வாங்குபவர்"}
# "That's wrong" about the order we showed: read the message again from scratch, or ask what to fix.
WRONG = {"wrong", "wrng", "worng", "incorrect", "not correct", "not right", "mistake", "thats wrong", "that's wrong",
         "වැරදියි", "වැරදි", "වැරැද්දක්", "தவறு", "பிழை", "சரியில்லை"}


def says_wrong(text: str | None) -> bool:
    t = norm(text)
    if any(w in t for w in WRONG if not w.isascii()) or any(re.search(rf"\b{re.escape(w)}\b", t) for w in WRONG if w.isascii()):
        return True
    first = t.split(" ", 1)[0] if t else ""
    return len(first) >= 4 and bool(difflib.get_close_matches(first, ["wrong"], cutoff=0.6))


# Words that turn "carrot" in an edit into "take the carrot out".
REMOVE = re.compile(r"\b(remove|delete|drop|without|no more|cancel|take out|don'?t need|dont need)\b|"
                    r"ඉවත්|එපා|අයින්|வேண்டாம்|நீக்கு|நீக்கவும்|இல்லாமல்|ரத்து", re.I)


def norm(text: str | None) -> str:
    """Lowercase, no punctuation or extra spaces, for matching whole short replies."""
    return re.sub(r"\s+", " ", re.sub(r"[!.?,;:'\"()\-]+", " ", (text or "").lower())).strip()


def _index(table: dict[str, list[str]]) -> dict[str, str]:
    out = {}
    for name, aliases in table.items():
        for a in [name, *aliases]:
            out[re.sub(r"\s+", " ", a.lower().strip())] = name
    return out


_CROP, _TOWN = _index(CROPS), _index(TOWNS)
_LATIN_CROP = [a for a in _CROP if a.isascii() and len(a) >= 4]


def crop(name: str) -> str:
    key = re.sub(r"\s+", " ", (name or "").lower().strip())
    return _CROP.get(key, key)


def towns_in(text: str | None) -> str | None:
    """The first known town named anywhere in a message, in any script."""
    t = " " + (text or "").lower() + " "
    for alias, canon in sorted(_TOWN.items(), key=lambda kv: -len(kv[0])):
        if (re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", t) if alias.isascii() else alias in t):
            return canon
    return None


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
