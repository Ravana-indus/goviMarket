"""End-to-end chat scenarios for Govi, written once and played two ways (see run.py):

    offline: in-process, no Gemini key, keyword parser (tests/test_e2e_scenarios.py runs these)
    live:    against a deployed URL with real Gemini (python scripts/e2e/run.py <url>)

A scenario is a list of steps. Each step is one message from one actor (`say`) or one HTTP call
(`api`). Checks are regexes, matched case-insensitively against the reply:

    expect  every pattern must match          absent  no pattern may match
    any     at least one pattern must match   lang    the reply is mostly in that script (si/ta/en)
    inbox   a pattern that must appear in what Govi sent this actor during the step (offers, slips)
    peer    (actor, pattern): the same, for another actor's inbox
    grab    {"name": pattern}: save the first group (or match) from reply + inbox, used as {name} later

`live_only` marks steps that need Gemini (free text the keyword parser cannot read, photos, voice).
Offline those steps are skipped; their scenario stops there. Placeholders: {crop} is a crop with no
open supply on the target (so a test deal cannot grab a real farmer's stock), {day3} the weekday
three days out, {code} whatever a previous step grabbed.
"""
from __future__ import annotations

# Reply fragments in all three languages, so a check holds whichever language Govi answers in.
CHECK_ORDER = r"check your order|ඇණවුම පරීක්ෂා|ஆர்டரை சரிபார்க்க"
CHECK_HARVEST = r"check your harvest|අස්වැන්න පරීක්ෂා|அறுவடையை சரிபார்க்க"
PLACED_BUYER = r"Order placed|ඇණවුම දැම්මා|ஆர்டர் பதிவு செய்யப்பட்டது"
PLACED_FARMER = r"up for sale|විකිණීමට දැම්මා|விற்பனைக்கு வைக்கப்பட்டது"
PLACED_ANY = PLACED_BUYER + "|" + PLACED_FARMER
NOT_PLACED = r"(?<!not )placed ✅|දැම්මා ✅|பதிவு செய்யப்பட்டது ✅|வைக்கப்பட்டது ✅"
CANCELLED = r"Cancelled|අවලංගු කළා|ரத்து செய்யப்பட்டது"
NOTHING = r"Nothing is waiting|බලාපොරොත්තුවෙන් කිසිවක් නැහැ|எதுவும் காத்திருக்கவில்லை"
HELLO = r"Hello from Govi|Govi-யிலிருந்து வணக்கம்|Govi වෙතින්|ආයුබෝවන්|வணக்கம்"
OFFER = r"\bYES\b"
WAITING_OTHER = r"Waiting for the other side|අනෙක් පාර්ශවය|மறுதரப்பு"
CONFIRMED = r"Confirmed by both|දෙපාර්ශවයම|இரு தரப்பும்|GV-[0-9A-Fa-f]+"
HANDED = r"handed over|භාර දුන්|ஒப்படைக்கப்பட்டது"
RECEIVED = r"marked received|ලැබුණු බව|பெறப்பட்டதாக|received"
STATUS_OPEN = r"tomato|තක්කාලි|தக்காளி"
ERROR = r"\[HTTP 5\d\d\]|Traceback|Internal Server Error"

TA_ORDER = "நாளைக்கு 5 கிலோ வெங்காயம், 10 கிலோ தக்காளி, 2 கிலோ கேரட், 5 கிலோ லீக்ஸ் மற்றும் 2 கிலோ கோவா தேவை"


def say(who, text, *, expect=(), any=(), absent=(ERROR,), lang=None, inbox=None, peer=None, grab=None,
        file=None, live_only=False, note=""):
    return {"who": who, "say": text, "expect": list(expect), "any": list(any), "absent": list(absent),
            "lang": lang, "inbox": inbox, "peer": peer, "grab": grab or {}, "file": file,
            "live_only": live_only, "note": note}


def api(method, path, *, status=200, json=None, data=None, contains=(), note="", headers=None):
    return {"api": (method, path), "status": status, "json": json, "data": data, "contains": list(contains),
            "note": note, "headers": headers or {}}


def deal_setup(farmer_text="{crop} 150kg ready tomorrow, Nuwara Eliya",
               buyer_text="need {crop} 150kg on {day3}, deliver to Colombo"):
    """A farmer lists, a buyer orders the same crop, both get the offer and say YES: one confirmed deal."""
    return [
        say("farmer", farmer_text, expect=[CHECK_HARVEST, OFFER]),
        say("farmer", "YES", expect=[PLACED_FARMER]),
        say("buyer", buyer_text, expect=[CHECK_ORDER, OFFER]),
        say("buyer", "YES", expect=[PLACED_BUYER], inbox=OFFER, peer=("farmer", OFFER),
            note="placing the order runs the matcher; both sides should get a YES/NO offer"),
        say("buyer", "YES", expect=[WAITING_OTHER]),
        say("farmer", "YES", any=[CONFIRMED], inbox=r"Dispatch slip|DROPPED", peer=("buyer", r"GV-[0-9A-Fa-f]+"),
            grab={"code": r"(GV-[0-9A-Fa-f]+)"}),
    ]


SCENARIOS: list[dict] = [
    # ------------------------------------------------------------ buyers
    {"id": "B1", "area": "buyer", "name": "English order, YES, STATUS", "steps": [
        say("buyer", "need tomato 10kg and carrot 5kg tomorrow, Colombo", expect=[CHECK_ORDER, r"Tomato 10 kg", r"Carrot 5 kg"],
            absent=[ERROR, NOT_PLACED], lang="en"),
        say("buyer", "YES", expect=[PLACED_BUYER], lang="en"),
        say("buyer", "STATUS", expect=[r"tomato", r"carrot"]),
        say("buyer", "CANCEL", any=[CANCELLED], note="clean-up: withdraw the test order"),
    ]},
    {"id": "B2", "area": "buyer", "name": "Sinhala order, ඔව්", "steps": [
        say("buyer", "හෙට තක්කාලි කිලෝ 10ක් සහ කැරට් කිලෝ 5ක් ඕන, කොළඹ", expect=[CHECK_ORDER, r"තක්කාලි", r"කැරට්"], lang="si"),
        say("buyer", "ඔව්", expect=[PLACED_BUYER], lang="si"),
        say("buyer", "CANCEL", any=[CANCELLED]),
    ]},
    {"id": "B3", "area": "buyer", "name": "Tamil five-item order, YES, second YES", "steps": [
        say("buyer", TA_ORDER, expect=[CHECK_ORDER, "வெங்காயம்", "தக்காளி", "கேரட்", "லீக்ஸ்", "கோவா"], lang="ta"),
        say("buyer", "YES", expect=[PLACED_BUYER], lang="ta"),
        say("buyer", "YES", any=[r"ஏற்கனவே முடிந்தது", r"YES"], lang="ta", note="second YES must not order twice"),
        say("buyer", "STATUS", any=["தக்காளி", "tomato"]),
        say("buyer", "CANCEL", any=[CANCELLED]),
        say("buyer", "STATUS", absent=[ERROR, "தக்காளி", "வெங்காயம்", "கேரட்"], note="CANCEL withdraws all five lines"),
    ]},
    {"id": "B4", "area": "buyer", "name": "Singlish order, hari", "steps": [
        say("buyer", "heta thakkali kilo 10 ona colombo", expect=[CHECK_ORDER], any=[r"තක්කාලි", r"tomato"]),
        say("buyer", "hari", expect=[PLACED_BUYER]),
        say("buyer", "CANCEL", any=[CANCELLED]),
    ]},
    {"id": "B5", "area": "buyer", "name": "Tanglish order, ok", "steps": [
        say("buyer", "naalaikku 10 kilo thakkali venum colombo", expect=[CHECK_ORDER], any=[r"தக்காளி", r"tomato"]),
        say("buyer", "ok", expect=[PLACED_BUYER]),
        say("buyer", "CANCEL", any=[CANCELLED]),
    ]},
    {"id": "B6", "area": "buyer", "name": "Edits before YES", "steps": [
        say("buyer", "need tomato 10kg and carrot 5kg tomorrow, Colombo", expect=[r"Tomato 10 kg", r"Carrot 5 kg"]),
        say("buyer", "make tomato 15kg", expect=[r"Tomato 15 kg", r"Carrot 5 kg"], absent=[ERROR, NOT_PLACED]),
        say("buyer", "remove carrot, add 3kg beans", expect=[r"Tomato 15 kg", r"Beans 3 kg"], absent=[ERROR, r"Carrot"]),
        say("buyer", "YES", expect=[PLACED_BUYER]),
        say("buyer", "STATUS", expect=[r"tomato 15", r"beans 3"]),
        say("buyer", "CANCEL", any=[CANCELLED]),
    ]},
    {"id": "B7", "area": "buyer", "name": "NO cancels, nothing stored", "steps": [
        say("buyer", "need leeks 20kg friday, Colombo", expect=[CHECK_ORDER]),
        say("buyer", "NO", expect=[CANCELLED]),
        say("buyer", "no", expect=[NOTHING]),
        say("buyer", "STATUS", expect=[r"nothing open"]),
    ]},
    {"id": "B8", "area": "buyer", "name": "CANCEL right after placing", "steps": [
        say("buyer", "need beans 20kg tomorrow, Colombo", expect=[CHECK_ORDER]),
        say("buyer", "YES", expect=[PLACED_BUYER]),
        say("buyer", "CANCEL", expect=[r"Cancelled ref"]),
        say("buyer", "STATUS", expect=[r"nothing open"]),
    ]},
    {"id": "B9", "area": "buyer", "name": "EDIT after placing", "steps": [
        say("buyer", "potato 12kg tomorrow, Colombo, buying", expect=[CHECK_ORDER, r"Potato 12 kg"]),
        say("buyer", "YES", expect=[PLACED_BUYER]),
        say("buyer", "EDIT", expect=[r"withdrawn", r"12"]),
        say("buyer", "potato 20kg", expect=[r"Potato 20 kg"]),
        say("buyer", "YES", expect=[PLACED_BUYER]),
        say("buyer", "STATUS", expect=[r"potato 20"], absent=[ERROR, r"potato 12"]),
        say("buyer", "CANCEL", any=[CANCELLED]),
    ]},
    {"id": "B10", "area": "buyer", "name": "Unknown crop", "steps": [
        say("buyer", "need durian 5kg", expect=[r"durian"], absent=[ERROR, NOT_PLACED]),
        say("buyer", "need durian 5kg and tomato 2kg tomorrow, Colombo", expect=[r"durian", r"Tomato 2 kg"]),
        say("buyer", "NO", expect=[CANCELLED]),
    ]},
    {"id": "B11", "area": "buyer", "name": "Missing kg answered with a bare number", "steps": [
        say("buyer", "need some beans tomorrow for Colombo", expect=[r"How many kg"], live_only=True),
        say("buyer", "20", expect=[r"Beans 20 kg"], live_only=True),
        say("buyer", "NO", expect=[CANCELLED]),
    ]},

    # ------------------------------------------------------------ farmers
    {"id": "F1", "area": "farmer", "name": "Sinhala harvest, asked for the town", "steps": [
        say("farmer", "කැරට් කිලෝ 200 හෙට", expect=[r"\?"], lang="si"),
        say("farmer", "දඹුල්ල", expect=[CHECK_HARVEST, r"දඹුල්ල"], lang="si"),
        say("farmer", "ඔව්", expect=[PLACED_FARMER], lang="si"),
        say("farmer", "CANCEL", any=[CANCELLED]),
    ]},
    {"id": "F2", "area": "farmer", "name": "Singlish harvest", "steps": [
        say("farmer", "thakkali kilo 150 heta dambulla", expect=[CHECK_HARVEST], any=[r"තක්කාලි", r"tomato"]),
        say("farmer", "hari", expect=[PLACED_FARMER]),
        say("farmer", "CANCEL", any=[CANCELLED]),
    ]},
    {"id": "F3", "area": "farmer", "name": "Tamil harvest", "steps": [
        say("farmer", "நாளை 100 கிலோ கேரட் விற்க வேண்டும், நுவரெலியா", expect=[CHECK_HARVEST, "கேரட்"], lang="ta",
            live_only=True, note="'விற்க' (to sell) is only understood by Gemini"),
        say("farmer", "ஆம்", expect=[PLACED_FARMER], lang="ta"),
        say("farmer", "CANCEL", any=[CANCELLED]),
    ]},
    {"id": "F4", "area": "farmer", "name": "Tanglish harvest", "steps": [
        say("farmer", "naalai 100 kilo carrot ready, nuwara eliya", expect=[CHECK_HARVEST], any=[r"கேரட்", r"carrot"]),
        say("farmer", "ok", expect=[PLACED_FARMER]),
        say("farmer", "CANCEL", any=[CANCELLED]),
    ]},
    {"id": "F5", "area": "farmer", "name": "New number: role asked, then town", "steps": [
        say("new", "tomato 100kg tomorrow", any=[r"selling this, or buying", r"Which town", CHECK_ORDER, CHECK_HARVEST],
            note="no buy/sell word: Govi should ask, not guess"),
        say("new", "selling", any=[r"Which town", CHECK_HARVEST]),
        say("new", "Dambulla", any=[CHECK_HARVEST]),
        say("new", "NO", expect=[CANCELLED]),
    ]},

    # ------------------------------------------------------------ language and onboarding
    {"id": "L1", "area": "language", "name": "Switch to Sinhala, then English text", "steps": [
        say("buyer", "සිංහල", lang="si"),
        say("buyer", "need tomato 10kg tomorrow, Colombo", expect=[CHECK_ORDER], lang="si",
            note="the picked language wins over the message's language"),
        say("buyer", "English", lang="en"),
        say("buyer", "NO", expect=[CANCELLED], lang="en"),
    ]},
    {"id": "L2", "area": "language", "name": "Switch to Tamil, then auto", "steps": [
        say("buyer", "தமிழ்", lang="ta"),
        say("buyer", "need tomato 10kg tomorrow, Colombo", expect=[CHECK_ORDER], lang="ta"),
        say("buyer", "NO", expect=[CANCELLED], lang="ta"),
        say("buyer", "language auto"),
        say("buyer", "need tomato 10kg tomorrow, Colombo", expect=[CHECK_ORDER], lang="en"),
        say("buyer", "NO", expect=[CANCELLED]),
    ]},
    {"id": "O1", "area": "onboarding", "name": "Greetings and small talk", "steps": [
        say("new", "hi", expect=[HELLO], absent=[ERROR, CHECK_ORDER, CHECK_HARVEST]),
        say("new", "வணக்கம்", expect=[HELLO], lang="ta", absent=[ERROR, CHECK_ORDER, CHECK_HARVEST]),
        say("new", "ආයුබෝවන්", lang="si", absent=[ERROR, CHECK_ORDER, CHECK_HARVEST]),
        say("new", "how are you today?", absent=[ERROR, CHECK_ORDER, CHECK_HARVEST], live_only=True),
        say("new", "YES", expect=[NOTHING]),
        say("new", "STATUS", expect=[r"nothing open|කිසිවක් නැහැ|எதுவும் இல்லை"]),
    ]},
    {"id": "O2", "area": "onboarding", "name": "Small talk while an order waits", "steps": [
        say("buyer", "need tomato 10kg tomorrow, Colombo", expect=[CHECK_ORDER]),
        say("buyer", "thanks", expect=[r"still waiting for your YES", r"Tomato 10 kg"]),
        say("buyer", "wait, let me check with the chef", any=[r"still waiting for your YES", CHECK_ORDER], live_only=True),
        say("buyer", "NO", expect=[CANCELLED]),
    ]},

    # ------------------------------------------------------------ the whole deal
    {"id": "D1", "area": "deal", "name": "Match, dispatch slip, Tanglish handover, bare COST, RECEIVED, TRACK", "steps": [
        *deal_setup(),
        api("GET", "/api/t/{code}", contains=["status"], note="public tracking page data"),
        say("farmer", "koduthuten train ku", expect=[HANDED], absent=[ERROR, HELLO, CHECK_HARVEST],
            peer=("buyer", r"handed over|භාර දුන්|ஒப்படை")),
        say("farmer", "2000", any=[r"2,?000", r"cost|වියදම|செலவு"], absent=[ERROR, CHECK_ORDER, CHECK_HARVEST],
            note="a bare amount right after the COST ask is the cost"),
        say("buyer", "RECEIVED", expect=[RECEIVED], peer=("farmer", r"received|ලැබුණා|பெற்")),
        say("farmer", "TRACK", expect=[r"GV-"]),
        say("buyer", "TRACK", expect=[r"GV-"]),
    ]},
    {"id": "D2", "area": "deal", "name": "Sinhala-romanised handover and receipt", "steps": [
        *deal_setup(),
        say("farmer", "bara dunna", expect=[HANDED], absent=[ERROR, HELLO]),
        say("farmer", "COST 1500", any=[r"1,?500"]),
        say("buyer", "labuna", any=[RECEIVED], absent=[ERROR, HELLO]),
    ]},
    {"id": "D3", "area": "deal", "name": "DROPPED button word, English receipt", "steps": [
        *deal_setup(),
        say("farmer", "DROPPED", expect=[HANDED]),
        say("buyer", "got it, thanks", expect=[RECEIVED], absent=[ERROR, HELLO]),
    ]},
    {"id": "D4", "area": "deal", "name": "Buyer says NO to the offer", "steps": [
        say("farmer", "{crop} 150kg ready tomorrow, Nuwara Eliya", expect=[CHECK_HARVEST]),
        say("farmer", "YES", expect=[PLACED_FARMER]),
        say("buyer", "need {crop} 150kg on {day3}, deliver to Colombo", expect=[CHECK_ORDER]),
        say("buyer", "YES", expect=[PLACED_BUYER], inbox=OFFER),
        say("buyer", "NO", expect=[r"Declined|ප්‍රතික්ෂේප|நிராகரி"]),
        say("buyer", "CANCEL", any=[CANCELLED]),
        say("farmer", "CANCEL", any=[CANCELLED]),
    ]},
    {"id": "D5", "area": "deal", "name": "YES 1 picks the offer by number", "steps": [
        say("farmer", "{crop} 150kg ready tomorrow, Nuwara Eliya", expect=[CHECK_HARVEST]),
        say("farmer", "YES", expect=[PLACED_FARMER]),
        say("buyer", "need {crop} 150kg on {day3}, deliver to Colombo", expect=[CHECK_ORDER]),
        say("buyer", "YES", expect=[PLACED_BUYER], inbox=OFFER),
        say("buyer", "YES 1", expect=[WAITING_OTHER]),
        say("farmer", "YES 1", any=[CONFIRMED]),
    ]},
    {"id": "D6", "area": "deal", "name": "YES 100kg takes part of a 150 kg offer", "steps": [
        say("farmer", "{crop} 150kg ready tomorrow, Nuwara Eliya", expect=[CHECK_HARVEST]),
        say("farmer", "YES", expect=[PLACED_FARMER]),
        say("buyer", "need {crop} 150kg on {day3}, deliver to Colombo", expect=[CHECK_ORDER]),
        say("buyer", "YES", expect=[PLACED_BUYER], inbox=OFFER),
        say("buyer", "YES 100kg", expect=[r"100"], absent=[ERROR, CONFIRMED],
            note="a part-accept must not confirm without the farmer"),
        say("farmer", "YES", any=[CONFIRMED, WAITING_OTHER, r"100"]),
        say("buyer", "CANCEL", note="clean-up: withdraw the 50 kg still open, if the site allows it"),
        say("farmer", "CANCEL"),
    ]},
    {"id": "D7", "area": "deal", "name": "Handover phrasings only Gemini reads", "steps": [
        *deal_setup(),
        say("farmer", "I have not dropped it yet, the train is late", absent=[ERROR, r"^.*handed over ✅"], live_only=True,
            peer=None, note="must not count as a handover"),
        say("farmer", "anju manikku train la pottachu", expect=[HANDED], live_only=True),
        say("buyer", "vanthuchu", expect=[RECEIVED], live_only=True),
    ]},

    # ------------------------------------------------------------ photos and voice notes
    {"id": "M1", "area": "media", "name": "Photo of a written order, then YES", "steps": [
        say("buyer", None, file="order_en.png", expect=[CHECK_ORDER], any=[r"tomato|Tomato", r"carrot|Carrot"], live_only=True),
        say("buyer", "YES", expect=[PLACED_BUYER], live_only=True),
        say("buyer", "CANCEL", any=[CANCELLED]),
    ]},
    {"id": "M2", "area": "media", "name": "Photo offline says it needs Gemini, never crashes", "offline_only": True, "steps": [
        say("buyer", None, file="order_en.png", any=[r"photo|Gemini|read"], absent=[ERROR, NOT_PLACED]),
    ]},
    {"id": "M3", "area": "media", "name": "Silent voice note is handled", "steps": [
        say("buyer", None, file="silence.wav", absent=[ERROR, NOT_PLACED]),
    ]},

    # ------------------------------------------------------------ portal, agent, console APIs
    {"id": "A1", "area": "api", "name": "Public pages and data", "steps": [
        api("GET", "/api/health", contains=["ok"]),
        *[api("GET", p) for p in ("/", "/business", "/agent", "/sim", "/login", "/signin")],
        api("GET", "/api/prices", contains=["carrot"]),
        api("GET", "/api/catalogue", contains=["crop"]),
        api("GET", "/api/towns"),
        api("GET", "/api/forecast", contains=["crops"]),
        api("GET", "/api/t/GV-00000000", status=404),
    ]},
    {"id": "A2", "area": "api", "name": "Gates stay shut without credentials", "locked_only": True, "steps": [
        api("GET", "/state", status=401),
        api("GET", "/api/plan", status=401),
        api("GET", "/api/offers", status=401),
        api("POST", "/plan", status=401),
        api("POST", "/demo/seed", status=401),
        api("POST", "/demo/clear", status=401, note="never sent with a token by this suite"),
        api("POST", "/jobs/daily", status=401),
        api("GET", "/admin/diag", status=401),
        api("GET", "/api/lane-costs", status=401),
        api("GET", "/api/agent/lanes", status=403),
        api("POST", "/api/agent/prices", status=401, json={"reporter": "T", "phone": "940009900000", "market": "Dambulla",
                                                           "kind": "collector", "prices": [{"crop": "carrot", "lkr_per_kg": 1}]}),
        api("POST", "/webhook/carrier", status=(401, 403), json={"ref": "GV-00000000", "status": "missed"}),
        api("POST", "/rescue/watchdog", status=401),
        api("POST", "/api/lanes/reload", status=401),
        api("GET", "/api/track", status=401),
        api("POST", "/api/shipping-cost", status=(401, 403, 404), json={"code": "GV-00000000", "lkr": 100}),
    ]},
    {"id": "A3", "area": "api", "name": "Intake validation", "steps": [
        api("POST", "/intake", status=400, data={"text": "", "sender": "{buyer}"}),
        api("POST", "/intake", status=400, data={"text": "x" * 5000, "sender": "{buyer}", "via": "sim"}),
        api("POST", "/intake", status=400, data={"text": "hi", "via": "sim"}),
    ]},
    {"id": "A4", "area": "api", "name": "Portal harvest and order, then chat sees them", "steps": [
        api("POST", "/api/listings", json={"farmer": "E2E Test Farmer", "phone": "{farmer}", "location": "Nuwara Eliya",
                                           "crop": "{crop}", "qty_kg": 120, "ready_on": "{tomorrow}", "lang": "en"},
            contains=["id"]),
        api("POST", "/api/orders", json={"business": "E2E Test Shop", "phone": "{buyer}", "location": "Colombo",
                                         "needed_by": "{day3_iso}", "items": [{"crop": "{crop}", "qty_kg": 100}]},
            contains=["order_ids"]),
        api("POST", "/api/orders", status=400, json={"business": "E2E Test Shop", "phone": "{buyer}", "location": "Colombo",
                                                     "needed_by": "{today}", "items": [{"crop": "{crop}", "qty_kg": 100}]},
            note="today is too soon"),
        api("POST", "/api/orders", status=400, json={"business": "E2E Test Shop", "phone": "{buyer}", "location": "Colombo",
                                                     "needed_by": "{day3_iso}", "items": [{"crop": "durian", "qty_kg": 5}]}),
        say("buyer", "STATUS", any=[r"{crop}", r"100"]),
        say("farmer", "STATUS", any=[r"{crop}", r"120"]),
        say("buyer", "YES", any=[WAITING_OTHER, NOTHING, OFFER], note="answers the portal order's offer if one came"),
        say("farmer", "YES", any=[CONFIRMED, WAITING_OTHER, NOTHING, OFFER]),
    ]},
]
