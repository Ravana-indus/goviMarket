"""The WhatsApp conversation: one state per phone number.

    idle ──order or harvest──▶ asking (one fact missing) ──answer──▶ confirming
         └──────────────────complete─────────────────────────────▶ confirming
    confirming ──YES──▶ placed: stored and matched, back to idle
    confirming ──NO / cancel──▶ cancelled, nothing stored
    confirming ──a change ("tomato 15kg", "remove carrot")──▶ confirming, whole order shown again
    asking or confirming, no reply for PENDING_HOURS ──▶ expired, nothing stored

Nothing becomes an order or a harvest listing until the sender has seen all of it, in their own
language, and said YES. A YES or NO goes to whatever this number was asked most recently: its own
pending order, a match offer, or a route change. Every line the sender sees is built here from
code templates, so a number in a reply is always one the code decided."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from . import accounts, ai, deals, demo_parser, parser, replies, reroute, store, surplus, vocab
from .schemas import Item, ParsedMessage

log = logging.getLogger("govi.convo")
KIND = "convo"
PENDING_HOURS = 24
DONE_GRACE = timedelta(hours=6)  # a second YES this soon after placing gets "already done"
MAX_KG = 20000
MODE = {"train_parcel": {"en": "train", "si": "දුම්රියෙන්", "ta": "ரயிலில்"},
        "night_bus": {"en": "night bus", "si": "රාත්‍රී බසයෙන්", "ta": "இரவு பேருந்தில்"},
        "lorry": {"en": "lorry", "si": "ලොරියෙන්", "ta": "லாரியில்"},
        "sl_post": {"en": "post", "si": "තැපෑලෙන්", "ta": "தபாலில்"}}
WEEKDAY = {"en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
           "si": ["සඳුදා", "අඟහරුවාදා", "බදාදා", "බ්‍රහස්පතින්දා", "සිකුරාදා", "සෙනසුරාදා", "ඉරිදා"],
           "ta": ["திங்கள்", "செவ்வாய்", "புதன்", "வியாழன்", "வெள்ளி", "சனி", "ஞாயிறு"]}

# Sinhala and Tamil need a native speaker's read before the demo video.
T = {
    "head_buyer": {"en": "Please check your order:", "si": "ඔබේ ඇණවුම පරීක්ෂා කරන්න:",
                   "ta": "உங்கள் ஆர்டரை சரிபார்க்கவும்:"},
    "head_farmer": {"en": "Please check your harvest:", "si": "ඔබේ අස්වැන්න පරීක්ෂා කරන්න:",
                    "ta": "உங்கள் அறுவடையை சரிபார்க்கவும்:"},
    "item": {"en": "• {crop} {kg} kg", "si": "• {crop} කිලෝ {kg}", "ta": "• {crop} {kg} கிலோ"},
    "when_buyer": {"en": "Needed by {day} · Deliver to {town}", "si": "අවශ්‍ය දිනය {day} · ලබා දෙන්නේ {town}",
                   "ta": "தேவைப்படும் நாள் {day} · வழங்கும் இடம் {town}"},
    "when_farmer": {"en": "Ready {day} · From {town}", "si": "සූදානම් දිනය {day} · නගරය {town}",
                    "ta": "தயாராகும் நாள் {day} · ஊர் {town}"},
    "item_sell": {"en": "• {crop} {kg} kg · about Rs {per}/kg (collector Rs {base})",
                  "si": "• {crop} කිලෝ {kg} · කිලෝවට රු. {per} පමණ (එකතු කරන්නා රු. {base})",
                  "ta": "• {crop} {kg} கிலோ · கிலோவுக்கு சுமார் ரூ. {per} (சேகரிப்பாளர் ரூ. {base})"},
    "item_local": {"en": "• {crop} {kg} kg · collectors pay more today (Rs {base}/kg): better sold locally",
                   "si": "• {crop} කිලෝ {kg} · අද එකතු කරන්නන් වැඩියෙන් ගෙවයි (කිලෝවට රු. {base}): ප්‍රදේශයේම විකුණන්න",
                   "ta": "• {crop} {kg} கிலோ · இன்று சேகரிப்பாளர்கள் அதிகம் தருகிறார்கள் (கிலோவுக்கு ரூ. {base}): உள்ளூரில் விற்பது நல்லது"},
    "item_buy": {"en": "• {crop} {kg} kg · about Rs {per}/kg", "si": "• {crop} කිලෝ {kg} · කිලෝවට රු. {per} පමණ",
                 "ta": "• {crop} {kg} கிலோ · கிலோவுக்கு சுமார் ரூ. {per}"},
    "transport": {"en": "Transport to Colombo for all {kg} kg together: about Rs {per}/kg by {mode} at {departs}. Less if neighbours send with you.",
                  "si": "කිලෝ {kg}ම එකට කොළඹට ප්‍රවාහනය: කිලෝවට රු. {per} පමණ, {departs} {mode}. අසල්වැසියන් සමඟ යැවුවොත් අඩුයි.",
                  "ta": "மொத்த {kg} கிலோவும் சேர்ந்து கொழும்புக்கு போக்குவரத்து: கிலோவுக்கு சுமார் ரூ. {per}, {departs} {mode}. அயலவர்களுடன் அனுப்பினால் குறையும்."},
    "no_lane": {"en": "We have no transport from {town} yet, so these prices are before transport.",
                "si": "{town} සිට අපට තවම ප්‍රවාහන මාර්ගයක් නැහැ, ඒ නිසා මේ මිල ප්‍රවාහනයට පෙර.",
                "ta": "{town} இலிருந்து இன்னும் போக்குவரத்து இல்லை, எனவே இவை போக்குவரத்துக்கு முந்தைய விலைகள்."},
    "total_farmer": {"en": "You get about Rs {total} in total (collectors: about Rs {base}).",
                     "si": "ඔබට මුළු රු. {total} පමණ ලැබේ (එකතු කරන්නන්ගෙන්: රු. {base} පමණ).",
                     "ta": "உங்களுக்கு மொத்தம் சுமார் ரூ. {total} கிடைக்கும் (சேகரிப்பாளர்களிடம்: சுமார் ரூ. {base})."},
    "total_buyer": {"en": "About Rs {total} in total (market about Rs {base}).",
                    "si": "මුළු රු. {total} පමණ (වෙළඳපොළේ රු. {base} පමණ).",
                    "ta": "மொத்தம் சுமார் ரூ. {total} (சந்தையில் சுமார் ரூ. {base})."},
    "ask_buyer": {"en": "Reply YES to place this order, NO to cancel, or send a change (for example: tomato 15kg).",
                  "si": "මෙම ඇණවුම දැමීමට YES (ඔව්) ලෙස පිළිතුරු දෙන්න, අවලංගු කිරීමට NO (එපා), නැත්නම් වෙනසක් එවන්න (උදා: තක්කාලි කිලෝ 15).",
                  "ta": "இந்த ஆர்டரை உறுதிசெய்ய YES (ஆம்), ரத்து செய்ய NO (வேண்டாம்) என பதில் அனுப்பவும், அல்லது மாற்றத்தை அனுப்பவும் (உதா: தக்காளி 15 கிலோ)."},
    "ask_farmer": {"en": "Reply YES to put this up for sale, NO to cancel, or send a change (for example: carrot 250kg).",
                   "si": "විකිණීමට දැමීමට YES (ඔව්) ලෙස පිළිතුරු දෙන්න, අවලංගු කිරීමට NO (එපා), නැත්නම් වෙනසක් එවන්න (උදා: කැරට් කිලෝ 250).",
                   "ta": "விற்பனைக்கு வைக்க YES (ஆம்), ரத்து செய்ய NO (வேண்டாம்) என பதில் அனுப்பவும், அல்லது மாற்றத்தை அனுப்பவும் (உதா: கேரட் 250 கிலோ)."},
    "placed_buyer": {"en": "Order placed ✅ Ref {ref}.\nWe are finding farmers now. Each one we find comes to you with the price and arrival time; reply YES to accept. Send STATUS any time.",
                     "si": "ඇණවුම දැම්මා ✅ අංකය {ref}.\nඅපි දැන් ගොවීන් සොයනවා. හමු වන සෑම ගොවියෙක් ගැනම මිල සහ පැමිණෙන වේලාව සමඟ පණිවිඩයක් එවනවා; පිළිගන්න YES එවන්න. ඕනෑම වේලාවක STATUS එවන්න.",
                     "ta": "ஆர்டர் பதிவு செய்யப்பட்டது ✅ எண் {ref}.\nஇப்போது விவசாயிகளைத் தேடுகிறோம். ஒவ்வொருவரும் கிடைத்ததும் விலையும் வரும் நேரமும் அனுப்புவோம்; ஏற்க YES அனுப்பவும். எப்போது வேண்டுமானாலும் STATUS அனுப்பவும்."},
    "placed_farmer": {"en": "Your harvest is up for sale ✅ Ref {ref}.\nWhen a buyer is found we send you the price and which bus or train to load, and when; reply YES to accept. Send STATUS any time.",
                      "si": "ඔබේ අස්වැන්න විකිණීමට දැම්මා ✅ අංකය {ref}.\nගැනුම්කරුවෙක් හමු වූ විට මිලත්, පටවන්න ඕන බස් එක හෝ දුම්රියත්, වේලාවත් අපි එවනවා; පිළිගන්න YES එවන්න. ඕනෑම වේලාවක STATUS එවන්න.",
                      "ta": "உங்கள் அறுவடை விற்பனைக்கு வைக்கப்பட்டது ✅ எண் {ref}.\nவாங்குபவர் கிடைத்ததும் விலையையும், ஏற்ற வேண்டிய பேருந்து அல்லது ரயிலையும், நேரத்தையும் அனுப்புவோம்; ஏற்க YES அனுப்பவும். எப்போது வேண்டுமானாலும் STATUS அனுப்பவும்."},
    "cancelled": {"en": "Cancelled. Nothing was placed.", "si": "අවලංගු කළා. කිසිවක් දැම්මේ නැහැ.",
                  "ta": "ரத்து செய்யப்பட்டது. எதுவும் பதிவு செய்யப்படவில்லை."},
    "cancelled_placed": {"en": "Cancelled ref {ref}. It is no longer open.", "si": "අංකය {ref} අවලංගු කළා.",
                         "ta": "எண் {ref} ரத்து செய்யப்பட்டது."},
    "cant_cancel": {"en": "Ref {ref} is already agreed with the other side, so it cannot be cancelled here. Please call Govi.",
                    "si": "අංකය {ref} අනෙක් පාර්ශවය සමඟ දැනටමත් එකඟ වී ඇති නිසා මෙතැනින් අවලංගු කළ නොහැක. කරුණාකර Govi අමතන්න.",
                    "ta": "எண் {ref} ஏற்கனவே மறுதரப்புடன் ஒப்புக்கொள்ளப்பட்டதால் இங்கே ரத்து செய்ய முடியாது. Govi-ஐ அழைக்கவும்."},
    "nothing": {"en": "Nothing is waiting for your answer right now. To buy or sell, send the crop and kg (for example: tomato 10kg tomorrow).",
                "si": "දැනට ඔබේ පිළිතුර බලාපොරොත්තුවෙන් කිසිවක් නැහැ. ගන්න හෝ විකුණන්න, බෝගය සහ කිලෝ ගණන එවන්න (උදා: තක්කාලි කිලෝ 10 හෙට).",
                "ta": "இப்போது உங்கள் பதிலுக்காக எதுவும் காத்திருக்கவில்லை. வாங்க அல்லது விற்க, பயிரும் கிலோவும் அனுப்பவும் (உதா: தக்காளி 10 கிலோ நாளை)."},
    "done": {"en": "That is already done (ref {ref}). Nothing else is waiting for a YES.",
             "si": "එය දැනටමත් සිදු කර ඇත (අංකය {ref}). තවත් YES එකක් බලාපොරොත්තු වන දෙයක් නැහැ.",
             "ta": "அது ஏற்கனவே முடிந்தது (எண் {ref}). வேறு எதுவும் YES-க்காக காத்திருக்கவில்லை."},
    "expired": {"en": "Your earlier order was not placed: it waited more than {h} hours without a YES. Please send it again.",
                "si": "පැය {h}කට වඩා YES නොලැබුණු නිසා ඔබේ කලින් ඇණවුම දැම්මේ නැහැ. කරුණාකර නැවත එවන්න.",
                "ta": "{h} மணி நேரத்திற்கு மேல் YES வராததால் உங்கள் முந்தைய ஆர்டர் பதிவு செய்யப்படவில்லை. மீண்டும் அனுப்பவும்."},
    "expired_note": {"en": "(Your earlier order waited too long and was not placed. This is a new one.)",
                     "si": "(ඔබේ කලින් ඇණවුම බොහෝ වේලා රැඳී තිබූ නිසා දැම්මේ නැහැ. මෙය අලුත් එකක්.)",
                     "ta": "(உங்கள் முந்தைய ஆர்டர் நீண்ட நேரம் காத்திருந்ததால் பதிவு செய்யப்படவில்லை. இது புதியது.)"},
    "wrong_ask": {"en": "Sorry about that. What is wrong? Send the right item and kg (for example: carrot 2kg), or NO to cancel.",
                  "si": "සමාවෙන්න. වැරැද්ද කුමක්ද? නිවැරදි බෝගය සහ කිලෝ ගණන එවන්න (උදා: කැරට් කිලෝ 2), නැත්නම් අවලංගු කිරීමට NO.",
                  "ta": "மன்னிக்கவும். என்ன தவறு? சரியான பயிரையும் கிலோவையும் அனுப்பவும் (உதா: கேரட் 2 கிலோ), அல்லது ரத்து செய்ய NO."},
    "wrong_again": {"en": "Sorry. I read it again from the start. If it is still wrong, send one item per line, like: carrot 2kg",
                    "si": "සමාවෙන්න. මම මුල සිට නැවත කියෙව්වා. තවමත් වැරදි නම්, එක පේළියකට එක බෝගයක් එවන්න, උදා: කැරට් කිලෝ 2",
                    "ta": "மன்னிக்கவும். மீண்டும் முதலிலிருந்து படித்தேன். இன்னும் தவறு என்றால், ஒரு வரிக்கு ஒரு பயிர் அனுப்பவும், உதா: கேரட் 2 கிலோ"},
    "first": {"en": "First I need one thing: {q}", "si": "මුලින් එක දෙයක් අවශ්‍යයි: {q}", "ta": "முதலில் ஒரு விவரம் தேவை: {q}"},
    "replaced": {"en": "(This replaces your earlier order, which was not placed.)",
                 "si": "(මෙය නොදැමූ ඔබේ කලින් ඇණවුම වෙනුවට.)",
                 "ta": "(இது பதிவு செய்யப்படாத உங்கள் முந்தைய ஆர்டருக்குப் பதிலாக.)"},
    "not_traded": {"en": "Not on Govi yet, so left out: {crops}.", "si": "Govi හි තවම නැති නිසා ඉවත් කළා: {crops}.",
                   "ta": "Govi-யில் இன்னும் இல்லாததால் நீக்கப்பட்டது: {crops}."},
    "none_traded": {"en": "We don't trade {crops} yet. We trade: {all}.", "si": "අපි තවම {crops} වෙළඳාම් කරන්නේ නැහැ. අප සතු බෝග: {all}.",
                    "ta": "நாங்கள் இன்னும் {crops} வியாபாரம் செய்வதில்லை. எங்களிடம்: {all}."},
    "unsure": {"en": "I was not fully sure I read this right, so please check it carefully.",
               "si": "මට මෙය නිවැරදිව කියවූ බව සම්පූර්ණයෙන් විශ්වාස නැහැ, හොඳින් පරීක්ෂා කරන්න.",
               "ta": "இதைச் சரியாகப் படித்தேனா என்று முழுமையாக உறுதியில்லை, கவனமாக சரிபார்க்கவும்."},
    "hello": {"en": "Hello from Govi 👋 Send what you want to buy or sell with the kg, as text, a photo or a voice note. "
                    "For example: \"need tomato 10kg tomorrow\" or \"carrot 200kg ready Friday, Dambulla\". Send STATUS to see your orders.",
              "si": "Govi වෙතින් ආයුබෝවන් 👋 ඔබට ගන්න හෝ විකුණන්න ඕන දේ කිලෝ ගණනත් සමඟ, පණිවිඩයක්, ඡායාරූපයක් හෝ හඬ පණිවිඩයක් ලෙස එවන්න. "
                    "උදා: \"හෙට තක්කාලි කිලෝ 10 ඕන\". ඔබේ ඇණවුම් බලන්න STATUS ලෙස එවන්න.",
              "ta": "Govi-யிலிருந்து வணக்கம் 👋 நீங்கள் வாங்க அல்லது விற்க விரும்புவதை கிலோவுடன் உரை, புகைப்படம் அல்லது குரல் செய்தியாக அனுப்பவும். "
                    "உதா: \"நாளைக்கு தக்காளி 10 கிலோ தேவை\". உங்கள் ஆர்டர்களைப் பார்க்க STATUS என அனுப்பவும்."},
    "thanks": {"en": "You're welcome 🙏", "si": "ස්තූතියි 🙏", "ta": "நன்றி 🙏"},
    "still": {"en": "This is still waiting for your YES:", "si": "මෙය තවමත් ඔබේ YES එක බලාපොරොත්තුවෙන්:",
              "ta": "இது இன்னும் உங்கள் YES-க்காக காத்திருக்கிறது:"},
    "unread_image": {"en": "Sorry, I could not read that photo. Please send a clearer photo, or type the crop and kg.",
                     "si": "සමාවන්න, එම ඡායාරූපය කියවීමට නොහැකි විය. පැහැදිලි ඡායාරූපයක් එවන්න, නැත්නම් බෝගය සහ කිලෝ ගණන ටයිප් කරන්න.",
                     "ta": "மன்னிக்கவும், அந்தப் புகைப்படத்தைப் படிக்க முடியவில்லை. தெளிவான புகைப்படம் அனுப்பவும், அல்லது பயிரையும் கிலோவையும் தட்டச்சு செய்யவும்."},
    "unread_audio": {"en": "Sorry, I could not understand that voice note. Please try again slowly, or type the crop and kg.",
                     "si": "සමාවන්න, එම හඬ පණිවිඩය තේරුම් ගත නොහැකි විය. සෙමින් නැවත උත්සාහ කරන්න, නැත්නම් බෝගය සහ කිලෝ ගණන ටයිප් කරන්න.",
                     "ta": "மன்னிக்கவும், அந்தக் குரல் செய்தி புரியவில்லை. மெதுவாக மீண்டும் முயற்சிக்கவும், அல்லது பயிரையும் கிலோவையும் தட்டச்சு செய்யவும்."},
    "unsupported": {"en": "I can read text, photos and voice notes. Please send your order one of those ways.",
                    "si": "මට පණිවිඩ, ඡායාරූප සහ හඬ පණිවිඩ කියවිය හැක. කරුණාකර ඔබේ ඇණවුම ඒ ආකාරයෙන් එවන්න.",
                    "ta": "என்னால் உரை, புகைப்படம், குரல் செய்திகளைப் படிக்க முடியும். உங்கள் ஆர்டரை அவற்றில் ஒன்றாக அனுப்பவும்."},
    "q_role": {"en": "Are you selling this, or buying it?", "si": "ඔබ මෙය විකුණනවාද, මිලදී ගන්නවාද?",
               "ta": "இதை நீங்கள் விற்கிறீர்களா, வாங்குகிறீர்களா?"},
    "q_items": {"en": "Which crop, and how many kg?", "si": "කුමන බෝගය ද, කිලෝ කීයද?", "ta": "எந்தப் பயிர், எத்தனை கிலோ?"},
    "q_qty": {"en": "How many kg of {crop}?", "si": "{crop} කිලෝ කීයද?", "ta": "{crop} எத்தனை கிலோ?"},
    "q_town": {"en": "Which town are you sending it from?", "si": "ඔබ කුමන නගරයේ සිට එවනවාද?",
               "ta": "எந்த ஊரிலிருந்து அனுப்புகிறீர்கள்?"},
    "st_head": {"en": "Your orders and harvest with Govi:", "si": "Govi හි ඔබේ ඇණවුම් සහ අස්වැන්න:",
                "ta": "Govi-யில் உங்கள் ஆர்டர்களும் அறுவடையும்:"},
    "st_none": {"en": "You have nothing open with Govi right now.", "si": "දැනට Govi හි ඔබට විවෘත කිසිවක් නැහැ.",
                "ta": "இப்போது Govi-யில் உங்களுக்கு திறந்த எதுவும் இல்லை."},
    "st_pending": {"en": "not placed yet, waiting for your YES", "si": "තවම දැම්මේ නැහැ, ඔබේ YES එක බලාපොරොත්තුවෙන්",
                   "ta": "இன்னும் பதிவு செய்யப்படவில்லை, உங்கள் YES-க்காக காத்திருக்கிறது"},
    "st_offer": {"en": "match offered, waiting for your YES", "si": "ගැළපීමක් ලැබී ඇත, ඔබේ YES එක බලාපොරොත්තුවෙන්",
                 "ta": "பொருத்தம் கிடைத்துள்ளது, உங்கள் YES-க்காக காத்திருக்கிறது"},
    "st_matched": {"en": "{kg} kg agreed ✅", "si": "කිලෝ {kg} එකඟයි ✅", "ta": "{kg} கிலோ ஒப்புக்கொள்ளப்பட்டது ✅"},
    "st_looking_buyer": {"en": "looking for a buyer", "si": "ගැනුම්කරුවෙක් සොයමින්", "ta": "வாங்குபவரைத் தேடுகிறோம்"},
    "st_looking_farmer": {"en": "looking for a farmer", "si": "ගොවියෙක් සොයමින්", "ta": "விவசாயியைத் தேடுகிறோம்"},
}


def t(key: str, lang: str, **kw) -> str:
    s = T[key].get(lang) or T[key]["en"]
    return s.format(**kw) if kw else s


def _gemini() -> bool:
    return ai.enabled()


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Turn:
    reply: str
    parsed: Optional[ParsedMessage] = None
    created: list[str] = field(default_factory=list)
    needs: bool = False
    plan: bool = False  # run matching after the reply has gone out
    state: str = "idle"


# ---------------------------------------------------------------- state

def load(phone: str) -> dict:
    """This number's conversation. A pending order past PENDING_HOURS expires here, unplaced."""
    c = store.DB.one(KIND, phone) if phone.isdigit() else None
    c = dict(c or {"phone": phone, "state": "idle"})
    if c["state"] != "idle" and c.get("asked_at") and \
            datetime.fromisoformat(c["asked_at"]) < _now() - timedelta(hours=PENDING_HOURS):
        c.update(state="idle", parsed=None, question=None, qkind=None, asked_at=None,
                 last={"what": "expired", "at": _now().isoformat()})
        save(c)
    return c


def save(c: dict) -> None:
    if c["phone"].isdigit():
        store.DB.put(KIND, c["phone"], c)


def _pending(c: dict) -> Optional[ParsedMessage]:
    return ParsedMessage(**c["parsed"]) if c.get("state") != "idle" and c.get("parsed") else None


def _hold(c: dict, state: str, p: ParsedMessage, question: str | None = None, qkind: str | None = None) -> None:
    c.update(state=state, parsed=p.model_dump(mode="json"), question=question, qkind=qkind,
             asked_at=_now().isoformat(), lang=p.language)
    save(c)


# ---------------------------------------------------------------- reading the order

def context(sender: str, known: dict | None, c: dict) -> str | None:
    """What we already know about this number, so Gemini infers instead of asking."""
    bits = []
    role = _role_of(sender, known)
    if role:
        bits.append(f"About the sender: this number belongs to a {role}"
                    + (f" in {known['location']}" if known and known.get("location") else "") + ".")
    p = _pending(c)
    if p:
        bits.append("Pending order from this sender, NOT placed yet (JSON): "
                    + json.dumps(p.model_dump(mode="json", include={"role", "location", "when", "items", "sender_name"}),
                                 ensure_ascii=False)
                    + f"\nWe asked them: {c.get('question') or 'reply YES to place it, NO to cancel, or send a change'}")
    return "\n".join(bits) or None


def _role_of(sender: str, known: dict | None) -> str | None:
    role = (known or {}).get("role")
    if role in ("farmer", "buyer"):
        return role
    if not sender.isdigit():
        return None
    sold = any(x.phone == sender for x in store.listings())
    bought = any(x.phone == sender for x in store.orders())
    return "farmer" if sold and not bought else "buyer" if bought and not sold else None


_SEGMENTS = re.compile(r",|;|\n|&|\+|\band\b|\bthen\b|மற்றும்|සහ", re.I)


def merge(base: ParsedMessage, delta: ParsedMessage, text: str | None) -> ParsedMessage:
    """Apply a change to the pending order. Items not mentioned stay as they were; an item goes only
    when the sender says so ("remove carrot", qty 0 from Gemini). A crop named again gets its new kg."""
    items = {i.crop: i for i in base.items}
    removed: set[str] = set()
    for seg in _SEGMENTS.split(text or ""):
        if vocab.REMOVE.search(seg):
            removed |= vocab.crops_in(seg)
    for it in delta.items:
        if it.crop in removed or (not it.qty_kg and it.crop in items):
            removed.add(it.crop)
        else:
            items[it.crop] = it
    for crop in removed:
        items.pop(crop, None)
    out = base.model_copy(deep=True)
    out.items = list(items.values())
    out.role = base.role if base.role in ("farmer", "buyer") else delta.role
    out.location = delta.location or base.location
    out.when = delta.when or base.when
    out.sender_name = delta.sender_name or base.sender_name
    out.language = vocab.script(text) or (delta.language if text is None else base.language)
    out.confidence = min(base.confidence, delta.confidence) if delta.items else base.confidence
    return out


def _defaults(p: ParsedMessage, sender: str, known: dict | None, today: date) -> ParsedMessage:
    if p.role not in ("farmer", "buyer", "reporter"):
        p.role = _role_of(sender, known) or "unknown"
    elif (not _gemini() or demo_parser.FALLBACK in p.unclear) and _role_of(sender, known) in ("farmer", "buyer") and p.role != "reporter":
        p.role = _role_of(sender, known)  # the keyword parser only guesses the role; the account knows
    if not p.location and known and known.get("location") and p.role in ("farmer", "buyer"):
        p.location = vocab.town(known["location"])
    if p.role == "buyer" and not p.location:
        p.location = "Colombo"  # shown in the summary, so a wrong guess is one reply away from fixed
    first = today if p.role == "farmer" else today + timedelta(days=1)
    if not p.when or p.when < (today if p.role == "farmer" else first):
        p.when = first
    if not p.sender_name and known:
        p.sender_name = known.get("business") or known.get("name") or None
    return p


def _missing(p: ParsedMessage, lang: str) -> tuple[str, str] | None:
    """The one fact Govi cannot trade without, as (kind, question). Dates, towns for buyers and
    names all have defaults the sender sees before saying YES, so they are never asked."""
    if not p.items:
        return "items", t("q_items", lang)
    if p.role not in ("farmer", "buyer"):
        return "role", t("q_role", lang)
    for it in p.items:
        if not it.qty_kg or it.qty_kg <= 0 or it.qty_kg > MAX_KG:
            return "qty", t("q_qty", lang, crop=vocab.crop_name(it.crop, lang))
    if p.role == "farmer" and not p.location:
        return "town", t("q_town", lang)
    return None


def _split_traded(p: ParsedMessage) -> list[str]:
    """Drop crops Govi has no price for (nobody could be matched); return their names."""
    prices = store.prices()
    gone = [i.crop for i in p.items if i.crop not in prices]
    p.items = [i for i in p.items if i.crop in prices]
    return gone


# ---------------------------------------------------------------- what the sender reads

def _kg(x: float) -> str:
    return f"{x:.0f}" if float(x).is_integer() else f"{x:.1f}"


def _day(d: date, lang: str) -> str:
    return f"{WEEKDAY[lang][d.weekday()]} {d.day}/{d.month}"


def item_lines(p: ParsedMessage, lang: str) -> list[str]:
    return [t("item", lang, crop=vocab.crop_name(i.crop, lang).capitalize() if lang == "en" else vocab.crop_name(i.crop, lang),
              kg=_kg(i.qty_kg) if i.qty_kg else "?") for i in p.items]


def _rs(x: float) -> str:
    return f"{round(x):,}"


def summary(p: ParsedMessage, lang: str) -> list[str]:
    """The order card: header, one line per item with its price, day and town, transport, total.
    Every number comes from replies.quote, worked out once for the whole load."""
    q = replies.quote(p, store.prices())
    priced = {r["crop"]: r for r in q["items"]}
    lines = [t("head_farmer" if p.role == "farmer" else "head_buyer", lang)]
    for i in p.items:
        crop = vocab.crop_name(i.crop, lang)
        crop = crop.capitalize() if lang == "en" else crop
        r = priced.get(i.crop)
        if not r:
            lines.append(t("item", lang, crop=crop, kg=_kg(i.qty_kg) if i.qty_kg else "?"))
        elif p.role == "farmer" and not r["worth_it"]:
            lines.append(t("item_local", lang, crop=crop, kg=_kg(i.qty_kg), base=_rs(r["baseline"])))
        else:
            lines.append(t("item_sell" if p.role == "farmer" else "item_buy", lang, crop=crop, kg=_kg(i.qty_kg),
                           per=_rs(r["per_kg"]), base=_rs(r["baseline"])))
    if p.when:
        lines.append(t("when_farmer" if p.role == "farmer" else "when_buyer", lang,
                       day=_day(p.when, lang), town=vocab.town_name(p.location, lang)))
    if p.role == "farmer" and q["items"]:
        lane = q["lane"]
        lines.append(t("transport", lang, kg=_kg(q["total_kg"]), per=_rs(q["transport"]),
                       mode=MODE[lane.mode][lang], departs=lane.departs) if lane
                     else t("no_lane", lang, town=vocab.town_name(p.location, lang)))
    if q["total"]:
        lines.append(t("total_farmer" if p.role == "farmer" else "total_buyer", lang,
                       total=_rs(q["total"]), base=_rs(q["baseline"])))
    return lines


def status(sender: str, c: dict, lang: str) -> str:
    lines = []
    p = _pending(c)
    if p and c["state"] == "confirming":
        lines += [f"{l} ({t('st_pending', lang)})" for l in item_lines(p, lang)]
    ms = [m for m in store.matches() if m.status in ("proposed", "confirmed")]
    rows = [("farmer", x) for x in store.listings() if x.phone == sender] + \
           [("buyer", x) for x in store.orders() if x.phone == sender]
    rows.sort(key=lambda r: (r[1].ready_on if r[0] == "farmer" else r[1].needed_by), reverse=True)
    for side, x in rows[:8]:
        key = "listing_id" if side == "farmer" else "order_id"
        mine = [m for m in ms if getattr(m, key) == x.id]
        agreed = sum(m.qty_kg for m in mine if m.status == "confirmed")
        offered = any(m.status == "proposed" and not getattr(m, f"{side}_ok") for m in mine)
        what = (t("st_offer", lang) if offered else t("st_matched", lang, kg=_kg(agreed)) if agreed
                else t("st_looking_buyer" if side == "farmer" else "st_looking_farmer", lang))
        day = x.ready_on if side == "farmer" else x.needed_by
        lines.append(f"{t('item', lang, crop=vocab.crop_name(x.crop, lang), kg=_kg(x.qty_kg))}, {_day(day, lang)}: {what}")
    return "\n".join([t("st_head", lang), *lines]) if lines else t("st_none", lang)


# ---------------------------------------------------------------- the turn

def step(*, sender: str, text: Optional[str], media: Optional[bytes], mime_type: Optional[str],
         today: date, confirm_first: bool, via: str = "web") -> Turn:
    c = load(sender)
    known = accounts.user(sender) if sender.isdigit() else None
    lang = vocab.script(text) or c.get("lang") or (known or {}).get("lang") or "en"
    if lang not in ("si", "ta", "en"):
        lang = "en"
    if not text and not media:
        return Turn(t("unsupported", lang), state=c["state"])

    if text and not media:
        w = vocab.norm(text)
        if w in vocab.YES or w in vocab.NO or w in vocab.CANCEL:
            return _answer(c, sender, "yes" if w in vocab.YES else "cancel" if w in vocab.CANCEL else "no", lang, today)
        if w in vocab.STATUS:
            return Turn(status(sender, c, lang), state=c["state"])
        if w in vocab.HELLO or w in vocab.THANKS:
            return _chatter(c, "hello" if w in vocab.HELLO else "thanks", lang)
        if c["state"] == "asking" and c.get("qkind") == "role" and w in vocab.SELLING | vocab.BUYING:
            p = _pending(c)
            p.role = "farmer" if w in vocab.SELLING else "buyer"
            return _advance(c, sender, known, p, lang, today, confirm_first)
        if c["state"] == "asking" and c.get("qkind") == "qty" and re.fullmatch(r"\d+(\.\d+)?\s*(kg|kilo|කිලෝ|கிலோ)?", w):
            p = _pending(c)
            n = float(re.match(r"\d+(\.\d+)?", w).group())
            next(i for i in p.items if not i.qty_kg or i.qty_kg <= 0 or i.qty_kg > MAX_KG).qty_kg = n
            return _advance(c, sender, known, p, lang, today, confirm_first)
        if w.isdigit():
            r = surplus.answer(sender, w)
            if r:
                return Turn(r)

    try:
        parsed = parser.parse(text=text, media=media, mime_type=mime_type, today=today.isoformat(),
                              context=context(sender, known, c))
    except Exception:
        log.exception("could not read message from %s", sender)
        kind = "unread_audio" if (mime_type or "").startswith("audio") else "unread_image"
        return Turn(t(kind, lang), state=c["state"])
    if not vocab.script(text) and parsed.language in ("si", "ta", "en") and \
            (media or (parsed.items and c["state"] == "idle")):
        lang = parsed.language  # a voice note or a new Singlish order: Gemini heard the language

    if parsed.intent in ("confirm", "cancel"):
        return _answer(c, sender, "yes" if parsed.intent == "confirm" else "cancel", lang, today)
    if parsed.intent == "status":
        return Turn(status(sender, c, lang), state=c["state"])
    if parsed.role == "reporter" and parsed.items and not _pending(c):
        created = store.record(parsed, default_date=today, sender=sender)
        return Turn(replies.build(parsed, store.prices()), parsed=parsed, created=created)

    pending = _pending(c)
    notes = []
    guessed = demo_parser.FALLBACK in parsed.unclear
    if guessed and _gemini():
        notes.append(t("unsure", lang))  # Gemini failed and the keyword parser stood in: say it may be off
    if pending and vocab.says_wrong(text):
        if not parsed.items:
            return Turn(t("wrong_ask", lang), parsed=pending, state=c["state"])
        pending = None  # read the resent order on its own, not merged into the one they called wrong
        notes.append(t("wrong_again", lang))
    if pending and parsed.intent == "chat" and not (parsed.items or parsed.location or parsed.when):
        return _remind(c, lang)
    if not pending and (c.get("last") or {}).get("what") == "expired":
        notes.append(t("expired_note", lang))
        c["last"] = None
    if pending and parsed.intent == "order" and _gemini() and not guessed and parsed.items and c["state"] == "confirming":
        p = parsed  # Gemini says this is a separate new order: it replaces the unplaced one
        notes.append(t("replaced", lang))
    elif pending:
        p = merge(pending, parsed, text)
    else:
        if parsed.intent == "chat" or not (parsed.items or parsed.location):
            if media:
                return Turn(t("unread_audio" if (mime_type or "").startswith("audio") else "unread_image", lang))
            return _chatter(c, "hello", lang)
        p = parsed
    p.language = lang
    u = accounts.link(sender, name=parsed.sender_name, role=p.role, via=via) if sender.isdigit() else None
    p = _defaults(p, sender, u or known, today)
    gone = _split_traded(p)
    if gone and not p.items:
        names = ", ".join(vocab.crop_name(g, lang) for g in gone)
        every = ", ".join(vocab.crop_name(x, lang) for x in sorted(store.prices()))
        if pending:  # keep what they had; only the new crop is refused
            return Turn("\n".join([t("not_traded", lang, crops=names), *summary(pending, lang),
                                   t("ask_farmer" if pending.role == "farmer" else "ask_buyer", lang)]),
                        parsed=pending, state=c["state"])
        return Turn(t("none_traded", lang, crops=names, all=every), parsed=p)
    if gone:
        notes.append(t("not_traded", lang, crops=", ".join(vocab.crop_name(g, lang) for g in gone)))
    if p.confidence < 0.6 and (media or p.confidence > 0) and t("unsure", lang) not in notes:
        notes.append(t("unsure", lang))
    return _advance(c, sender, u or known, p, lang, today, confirm_first, notes)


def _advance(c, sender, known, p: ParsedMessage, lang, today, confirm_first, notes=()) -> Turn:
    """Ask the one missing fact, or show the whole order for a YES, or (web form) place it."""
    p.language = lang
    gap = _missing(p, lang)
    stateful = sender.isdigit()
    if gap:
        kind, q = gap
        p.question_in_sender_language = q
        if stateful:
            _hold(c, "asking", p, q, kind)
        return Turn("\n".join([*notes, *item_lines(p, lang), q]), parsed=p, needs=True,
                    state="asking" if stateful else "idle")
    p.question_in_sender_language = None
    if confirm_first and stateful:
        _hold(c, "confirming", p)
        return Turn("\n".join([*summary(p, lang), *notes, t("ask_farmer" if p.role == "farmer" else "ask_buyer", lang)]),
                    parsed=p, state="confirming")
    return _place(c, sender, p, lang, today, show=True, notes=notes)


def _place(c, sender, p: ParsedMessage, lang, today, show=False, notes=()) -> Turn:
    created = store.record(p, default_date=today, sender=sender)
    if sender.isdigit():
        accounts.link(sender, name=p.sender_name, role=p.role, via="chat")
    ref = created[0].upper()[:6] if created else "-"
    c.update(state="idle", parsed=None, question=None, qkind=None, asked_at=None, lang=lang,
             last={"what": "placed", "at": _now().isoformat(), "ref": ref, "ids": created, "role": p.role})
    save(c)
    placed = t("placed_farmer" if p.role == "farmer" else "placed_buyer", lang, ref=ref)
    card = summary(p, lang)
    lines = [*card[1:], *notes] if show else [l for l in card if l.startswith(("You get", "About Rs", "ඔබට මුළු", "මුළු රු", "உங்களுக்கு மொத்தம்", "மொத்தம்"))]
    return Turn("\n".join([placed, *lines]), parsed=p, created=created, plan=bool(created))


def _chatter(c: dict, key: str, lang: str) -> Turn:
    """Greetings and thanks never start a draft; a pending order gets a reminder."""
    p = _pending(c)
    lines = [t(key, lang)]
    if p and c["state"] == "confirming":
        lines += [t("still", lang), *item_lines(p, lang), t("ask_farmer" if p.role == "farmer" else "ask_buyer", lang)]
    elif p:
        lines.append(c.get("question") or "")
    return Turn("\n".join(l for l in lines if l), state=c["state"])


def _remind(c: dict, lang: str) -> Turn:
    """Small talk while an order waits: show it again rather than guess a change."""
    p = _pending(c)
    if c["state"] == "asking":
        return Turn("\n".join([*item_lines(p, lang), c.get("question") or t("q_items", lang)]), parsed=p,
                    needs=True, state="asking")
    return Turn("\n".join([t("still", lang), *summary(p, lang)[1:],
                           t("ask_farmer" if p.role == "farmer" else "ask_buyer", lang)]), parsed=p, state="confirming")


def _answer(c: dict, sender: str, word: str, lang: str, today: date) -> Turn:
    """YES, NO or cancel: goes to the newest thing this number was asked about."""
    asks = []
    if c["state"] != "idle" and c.get("asked_at"):
        asks.append((c["asked_at"], "own"))
    elif word == "cancel" and _recent_placement(c):
        return _cancel_placed(c, c["last"], lang)  # "cancel" means the order, not just one offer on it
    if (a := deals.asked_at(sender)):
        asks.append((a, "match"))
    if (a := reroute.asked_at(sender)):
        asks.append((a, "swap"))
    if not asks:
        return _nothing_waiting(c, sender, word, lang)
    _, what = max(asks)
    if what == "match":
        return Turn(deals.answer(sender, "yes" if word == "yes" else "no", lang=lang), plan=word != "yes")
    if what == "swap":
        return Turn(reroute.answer(sender, "yes" if word == "yes" else "no", deals._send))
    p = _pending(c)
    if word != "yes":
        c.update(state="idle", parsed=None, question=None, qkind=None, asked_at=None,
                 last={"what": "cancelled", "at": _now().isoformat()})
        save(c)
        return Turn(t("cancelled", lang))
    if c["state"] == "asking":
        return Turn(t("first", lang, q=c.get("question") or t("q_items", lang)), parsed=p, needs=True, state="asking")
    return _place(c, sender, p, lang, today)


def _recent_placement(c: dict) -> bool:
    last = c.get("last") or {}
    return last.get("what") == "placed" and datetime.fromisoformat(last["at"]) > _now() - DONE_GRACE


def _nothing_waiting(c: dict, sender: str, word: str, lang: str) -> Turn:
    last = c.get("last") or {}
    recent = _recent_placement(c)
    if last.get("what") == "expired" and word == "yes":
        c["last"] = None  # say it once
        save(c)
        return Turn(t("expired", lang, h=PENDING_HOURS))
    if recent and word == "yes":
        return Turn(t("done", lang, ref=last["ref"]))
    return Turn(t("nothing", lang))


def _cancel_placed(c: dict, last: dict, lang: str) -> Turn:
    """CANCEL soon after placing: withdraw it, unless a deal on it is already agreed."""
    ids = set(last.get("ids") or [])
    ms = [m for m in store.matches() if m.listing_id in ids or m.order_id in ids]
    if any(m.status == "confirmed" for m in ms):
        return Turn(t("cant_cancel", lang, ref=last["ref"]))
    deals.withdraw(ids)
    for kind in ("listings", "orders"):
        for rid in ids:
            if store.DB.one(kind, rid):
                store.DB.delete(kind, rid)
    c["last"] = {**last, "what": "withdrawn"}
    save(c)
    return Turn(t("cancelled_placed", lang, ref=last["ref"]), plan=bool(ms))
