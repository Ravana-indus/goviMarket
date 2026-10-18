// Sinhala and Tamil strings need a native speaker's review before the demo.
const T = {
  en: {
    n_prices: "Prices", n_sell: "Sell", n_track: "My orders", you_get: "You get", more: "Rs {n} more per kg", show: "Show", sell_btn: "Sell", see_orders: "See my orders", collector_s: "Collector", govi_s: "With Govi", fine: "Buyers pay {b} via Govi · shops {r} · before transport", phone_need: "Please add your phone number so we can reply.",
    h_title: "Post your harvest", h_name: "Your name", h_crop: "Crop", h_kg: "How much?", h_ready: "Ready on", h_town: "Your town",
    h_post: "Post harvest", h_or: "or send a message, photo or voice note", today: "Today", tomorrow: "Tomorrow", in2: "In 2 days",
    h_done: "Posted. We will WhatsApp you when a buyer is found.", h_matched: "Buyer found: {kg} kg to {buyer} at Rs {price}/kg after transport. Reply YES on WhatsApp to confirm.",
    h_fill: "Please fill in your name, phone and crop.", b_title: "Restaurants, hotels and shops", b_sub: "Order with fair prices, weekly standing orders and delivery tracking.", b_go: "Open the ordering portal", err: "Something went wrong. Please try again.",
    hero: "Sell your harvest direct, for a fair price.", sub: "We find the buyer and the bus. You keep the middleman's cut.",
    wa: "Message us on WhatsApp", or: "or use this page", t_prices: "Today's prices", t_send: "Sell / Order", t_track: "My orders",
    i_farmer: "I'm selling", i_buyer: "I'm buying", photo: "Photo", voice: "Voice note", phone_ph: "Your phone number",
    send: "Send", track: "Show my orders", ph_farmer: "e.g. Carrot 200kg ready Thursday, Nuwara Eliya", ph_buyer: "e.g. Need carrot 50kg and beans 20kg by Friday, Colombo 03",
    fair: "Fair price to farmer", collector: "Collector pays", retail: "Shop price", buyer: "You pay via Govi",
    waiting: "Waiting for a match", matched: "Matched", to: "to", from: "from", you_get: "You get", per_kg: "/kg",
    none: "Nothing found for this number yet.", note: "Prices update every morning from market reporters.",
    selling: "Selling", ordering: "Ordering", sent: "Sending…",
    s_booked: "Booked", s_loaded: "Loaded", s_in_transit: "On the way", s_arrived: "Arrived", s_delivered: "Delivered", ref: "Ref", dropoff: "Drop-off", eta: "Arrives", code: "Tracking code", track_it: "Track", cost_q: "Shipping cost you paid (Rs)", cost_save: "Save", cost_saved: "Shipping cost saved: Rs {n}. Thank you, this keeps transport prices up to date.",
    before_transport: "before transport", transport_off: "Transport already taken off", shared: "shared with neighbours",
    plan_active: "Govi plan · Rs {p}/month · paid until {d} ✓", plan_due: "Govi plan · Rs {p}/month · due {d}. Pay your Govi agent or by bank transfer.", plan_overdue: "Govi plan · Rs {p}/month · overdue since {d}. Pay your Govi agent or by bank transfer.",
    signin: "Sign in", signout: "Sign out", posting_as: "Posting as {n} · {p}", t_need: "Sign in with your mobile number to see your harvests and orders, including the ones you sent on WhatsApp.",
    greet_am: "Good morning", greet_pm: "Good afternoon", greet_eve: "Good evening", sell_h: "Sell your harvest", sell_sub: "We find the buyer and the bus or train.", speak: "Speak your harvest", other: "Send a photo or type it", prices_at: "prices at 06:00",
    hold: "Hold to speak", hold_sub: "Say the crop, kilos and when it's ready", example: "For example", ex_text: "\u201cCarrot, 280 kilos, ready tomorrow, Kandapola.\u201d", or1: "or", take_photo: "Take a photo of your note", type_it: "Type it instead", understands: "Govi understands Sinhala, Tamil and English.",
    listening: "Listening\u2026", let_go: "Let go to send", slide_cancel: "slide left to cancel", reading: "Reading your voice note\u2026", mic_off: "We can't use the microphone. Allow it in your browser, or type it instead.",
    t_loads: "My loads", n_home: "Home", n_loads: "My loads", pay_note: "Payment comes after delivery, usually the same day.", more_s: "+Rs {n} more", cmp_line: "Collector pays Rs {c} \u00b7 Shop Rs {r}",
  },
  si: {
    n_prices: "මිල", n_sell: "විකුණන්න", n_track: "මගේ ඇණවුම්", you_get: "ඔබට ලැබෙන්නේ", more: "කිලෝවකට රු {n}ක් වැඩියෙන්", show: "පෙන්වන්න", sell_btn: "විකුණන්න", see_orders: "මගේ ඇණවුම් බලන්න", collector_s: "එකතු කරන්නා", govi_s: "Govi සමඟ", fine: "Govi හරහා ගැනුම්කරු {b} · කඩේ {r} · ප්‍රවාහනයට පෙර", phone_need: "පිළිතුරු දීමට කරුණාකර ඔබේ දුරකථන අංකය දාන්න.",
    h_title: "ඔබේ අස්වැන්න දාන්න", h_name: "ඔබේ නම", h_crop: "බෝගය", h_kg: "කොපමණද?", h_ready: "සූදානම් දිනය", h_town: "ඔබේ නගරය",
    h_post: "අස්වැන්න දාන්න", h_or: "නැතහොත් පණිවිඩයක්, ඡායාරූපයක් හෝ හඬ පණිවිඩයක් එවන්න", today: "අද", tomorrow: "හෙට", in2: "දින 2කින්",
    h_done: "දැම්මා. ගැනුම්කරුවෙක් හමු වූ විට WhatsApp කරන්නෙමු.", h_matched: "ගැනුම්කරු හමු විය: කිලෝ {kg} {buyer} වෙත, ප්‍රවාහනයෙන් පසු රු {price}/කිලෝ. තහවුරු කිරීමට WhatsApp හි YES යවන්න.",
    h_fill: "කරුණාකර නම, දුරකථන අංකය සහ බෝගය පුරවන්න.", b_title: "අවන්හල්, හෝටල් සහ කඩ", b_sub: "සාධාරණ මිලට ඇණවුම්, සතිපතා ඇණවුම් සහ බෙදාහැරීම් ලුහුබැඳීම.", b_go: "ඇණවුම් පිටුව විවෘත කරන්න", err: "වැරැද්දක් සිදු විය. නැවත උත්සාහ කරන්න.",
    hero: "ඔබේ අස්වැන්න සාධාරණ මිලට කෙලින්ම විකුණන්න.", sub: "ගැනුම්කරු සහ බස් රථය අපි සොයා දෙන්නෙමු. අතරමැදියාගේ කොටස ඔබටම.",
    wa: "WhatsApp හරහා පණිවිඩයක් එවන්න", or: "නැතහොත් මෙම පිටුව භාවිතා කරන්න", t_prices: "අද මිල", t_send: "විකුණන්න / ඇණවුම්", t_track: "මගේ ඇණවුම්",
    i_farmer: "මම විකුණනවා", i_buyer: "මම මිලදී ගන්නවා", photo: "ඡායාරූපය", voice: "හඬ පණිවිඩය", phone_ph: "ඔබේ දුරකථන අංකය",
    send: "යවන්න", track: "මගේ ඇණවුම් පෙන්වන්න", ph_farmer: "උදා: කැරට් කිලෝ 200 බ්‍රහස්පතින්දා, නුවරඑළිය", ph_buyer: "උදා: කැරට් කිලෝ 50 සිකුරාදා වන විට, කොළඹ 03",
    fair: "ගොවියාට සාධාරණ මිල", collector: "එකතු කරන්නා ගෙවන්නේ", retail: "කඩේ මිල", buyer: "Govi හරහා ඔබ ගෙවන්නේ",
    waiting: "ගැළපීමක් බලාපොරොත්තුවෙන්", matched: "ගැළපුණා", to: "වෙත", from: "වෙතින්", you_get: "ඔබට ලැබෙන්නේ", per_kg: "/කිලෝ",
    none: "මෙම අංකයට තවම කිසිවක් නැත.", note: "වෙළඳපොළ වාර්තාකරුවන්ගෙන් සෑම උදෑසනකම මිල යාවත්කාලීන වේ.",
    selling: "විකිණීම", ordering: "ඇණවුම", sent: "යවමින්…",
    s_booked: "වෙන් කළා", s_loaded: "පැටෙව්වා", s_in_transit: "යමින්", s_arrived: "ළඟා විය", s_delivered: "භාර දුන්නා", ref: "අංකය", dropoff: "භාර දෙන තැන", eta: "ලැබෙන වේලාව", code: "ලුහුබැඳීමේ අංකය", track_it: "ලුහුබඳින්න", cost_q: "ඔබ ගෙවූ ප්‍රවාහන ගාස්තුව (රු.)", cost_save: "සුරකින්න", cost_saved: "ප්‍රවාහන ගාස්තුව සුරැකුණා: රු. {n}. ස්තූතියි, මෙයින් ප්‍රවාහන මිල යාවත්කාලීන වේ.",
    before_transport: "ප්‍රවාහනයට පෙර", transport_off: "ප්‍රවාහන වියදම දැනටමත් අඩු කර ඇත", shared: "අසල්වැසියන් සමඟ බෙදාගත්",
    plan_active: "Govi සැලැස්ම · මසකට රු. {p} · {d} දක්වා ගෙවා ඇත ✓", plan_due: "Govi සැලැස්ම · මසකට රු. {p} · ගෙවිය යුත්තේ {d}. Govi නියෝජිතයාට හෝ බැංකු මාරුවකින් ගෙවන්න.", plan_overdue: "Govi සැලැස්ම · මසකට රු. {p} · {d} සිට ප්‍රමාදයි. Govi නියෝජිතයාට හෝ බැංකු මාරුවකින් ගෙවන්න.",
    signin: "පිවිසෙන්න", signout: "ඉවත් වන්න", posting_as: "{n} ලෙස දමයි · {p}", t_need: "ඔබේ අස්වැන්න සහ ඇණවුම් බැලීමට, WhatsApp හරහා එවූ ඒවා ද ඇතුළුව, ඔබේ ජංගම අංකයෙන් පිවිසෙන්න.",
    greet_am: "සුබ උදෑසනක්", greet_pm: "සුබ දහවලක්", greet_eve: "සුභ සන්ධ්‍යාවක්", sell_h: "ඔබේ අස්වැන්න විකුණන්න", sell_sub: "ගැනුම්කරුත් බස් හෝ දුම්රියත් අපි සොයා දෙන්නෙමු.", speak: "කතා කරලා කියන්න", other: "ඡායාරූපයක් එවන්න, නැතහොත් ටයිප් කරන්න", prices_at: "උදේ 06:00 මිල",
    hold: "කතා කිරීමට අල්ලාගෙන සිටින්න", hold_sub: "බෝගය, කිලෝ ගණන සහ සූදානම් වන දිනය කියන්න", example: "උදාහරණයක්", ex_text: "\u201cකැරට් කිලෝ 280ක්, හෙට සූදානම්, කඳපොල.\u201d", or1: "හෝ", take_photo: "සටහනේ ඡායාරූපයක් ගන්න", type_it: "ටයිප් කරන්න", understands: "Govi සිංහල, දෙමළ සහ ඉංග්‍රීසි තේරුම් ගනී.",
    listening: "අහගෙන ඉන්නවා\u2026", let_go: "යැවීමට අත ඇරලන්න", slide_cancel: "අවලංගු කිරීමට වමට ඇදින්න", reading: "ඔබේ හඬ පණිවිඩය කියවමින්\u2026", mic_off: "මයික්‍රෆෝනය භාවිතා කළ නොහැක. බ්‍රවුසරයේ අවසර දෙන්න, නැතහොත් ටයිප් කරන්න.",
    t_loads: "මගේ බඩු", n_home: "මුල් පිටුව", n_loads: "මගේ බඩු", pay_note: "ගෙවීම බඩු භාර දුන්නාට පසු, සාමාන්‍යයෙන් එදිනම.", more_s: "+රු {n}ක් වැඩි", cmp_line: "එකතු කරන්නා රු {c} \u00b7 කඩේ රු {r}",
  },
  ta: {
    n_prices: "விலை", n_sell: "விற்க", n_track: "என் ஆர்டர்கள்", you_get: "உங்களுக்குக் கிடைப்பது", more: "கிலோவுக்கு ரூ {n} அதிகம்", show: "காட்டு", sell_btn: "விற்க", see_orders: "என் ஆர்டர்களைப் பார்", collector_s: "சேகரிப்பாளர்", govi_s: "Govi மூலம்", fine: "Govi மூலம் வாங்குபவர் {b} · கடை {r} · போக்குவரத்துக்கு முன்", phone_need: "பதில் அனுப்ப உங்கள் தொலைபேசி எண்ணைச் சேர்க்கவும்.",
    h_title: "உங்கள் அறுவடையைப் பதிவிடுங்கள்", h_name: "உங்கள் பெயர்", h_crop: "பயிர்", h_kg: "எவ்வளவு?", h_ready: "தயாராகும் நாள்", h_town: "உங்கள் ஊர்",
    h_post: "அறுவடையைப் பதிவிடு", h_or: "அல்லது செய்தி, புகைப்படம் அல்லது குரல் செய்தி அனுப்புங்கள்", today: "இன்று", tomorrow: "நாளை", in2: "2 நாளில்",
    h_done: "பதிவிடப்பட்டது. வாங்குபவர் கிடைத்ததும் WhatsApp செய்வோம்.", h_matched: "வாங்குபவர் கிடைத்தார்: {kg} கிலோ {buyer} க்கு, போக்குவரத்துக்குப் பின் ரூ {price}/கிலோ. உறுதிப்படுத்த WhatsApp இல் YES அனுப்புங்கள்.",
    h_fill: "பெயர், தொலைபேசி எண் மற்றும் பயிரை நிரப்புங்கள்.", b_title: "உணவகங்கள், ஹோட்டல்கள், கடைகள்", b_sub: "நியாய விலையில் ஆர்டர், வாராந்திர ஆர்டர்கள், விநியோகக் கண்காணிப்பு.", b_go: "ஆர்டர் பக்கத்தைத் திற", err: "ஏதோ தவறு. மீண்டும் முயற்சிக்கவும்.",
    hero: "உங்கள் அறுவடையை நியாய விலையில் நேரடியாக விற்கவும்.", sub: "வாங்குபவரையும் பேருந்தையும் நாங்கள் கண்டுபிடிப்போம். இடைத்தரகரின் பங்கு உங்களுக்கே.",
    wa: "WhatsApp இல் செய்தி அனுப்புங்கள்", or: "அல்லது இந்தப் பக்கத்தைப் பயன்படுத்துங்கள்", t_prices: "இன்றைய விலை", t_send: "விற்க / ஆர்டர்", t_track: "என் ஆர்டர்கள்",
    i_farmer: "நான் விற்கிறேன்", i_buyer: "நான் வாங்குகிறேன்", photo: "புகைப்படம்", voice: "குரல் செய்தி", phone_ph: "உங்கள் தொலைபேசி எண்",
    send: "அனுப்பு", track: "என் ஆர்டர்களைக் காட்டு", ph_farmer: "உதா: கேரட் 200 கிலோ வியாழன், நுவரெலியா", ph_buyer: "உதா: கேரட் 50 கிலோ வெள்ளிக்குள், கொழும்பு 03",
    fair: "விவசாயிக்கு நியாய விலை", collector: "சேகரிப்பாளர் தருவது", retail: "கடை விலை", buyer: "Govi மூலம் நீங்கள் செலுத்துவது",
    waiting: "பொருத்தத்திற்காகக் காத்திருக்கிறது", matched: "பொருந்தியது", to: "க்கு", from: "இடமிருந்து", you_get: "உங்களுக்குக் கிடைப்பது", per_kg: "/கிலோ",
    none: "இந்த எண்ணுக்கு இன்னும் எதுவும் இல்லை.", note: "சந்தை நிருபர்களிடமிருந்து ஒவ்வொரு காலையும் விலை புதுப்பிக்கப்படுகிறது.",
    selling: "விற்பனை", ordering: "ஆர்டர்", sent: "அனுப்புகிறது…",
    s_booked: "பதிவு", s_loaded: "ஏற்றப்பட்டது", s_in_transit: "வழியில்", s_arrived: "வந்தடைந்தது", s_delivered: "வழங்கப்பட்டது", ref: "எண்", dropoff: "ஒப்படைக்கும் இடம்", eta: "வந்தடையும் நேரம்", code: "கண்காணிப்பு எண்", track_it: "கண்காணி", cost_q: "நீங்கள் செலுத்திய போக்குவரத்து கட்டணம் (ரூ.)", cost_save: "சேமி", cost_saved: "போக்குவரத்து கட்டணம் சேமிக்கப்பட்டது: ரூ. {n}. நன்றி, இது போக்குவரத்து விலைகளை புதுப்பிக்கிறது.",
    before_transport: "போக்குவரத்துக்கு முன்", transport_off: "போக்குவரத்து செலவு ஏற்கனவே கழிக்கப்பட்டது", shared: "அயலவர்களுடன் பகிர்ந்தது",
    plan_active: "Govi திட்டம் · மாதம் ரூ. {p} · {d} வரை செலுத்தப்பட்டது ✓", plan_due: "Govi திட்டம் · மாதம் ரூ. {p} · செலுத்த வேண்டிய நாள் {d}. Govi முகவரிடம் அல்லது வங்கி மாற்றம் மூலம் செலுத்தவும்.", plan_overdue: "Govi திட்டம் · மாதம் ரூ. {p} · {d} முதல் நிலுவையில். Govi முகவரிடம் அல்லது வங்கி மாற்றம் மூலம் செலுத்தவும்.",
    signin: "உள்நுழை", signout: "வெளியேறு", posting_as: "{n} ஆகப் பதிவிடுகிறது · {p}", t_need: "உங்கள் அறுவடைகளையும் ஆர்டர்களையும் (WhatsApp இல் அனுப்பியவை உட்பட) பார்க்க உங்கள் மொபைல் எண்ணுடன் உள்நுழையுங்கள்.",
    greet_am: "காலை வணக்கம்", greet_pm: "மதிய வணக்கம்", greet_eve: "மாலை வணக்கம்", sell_h: "உங்கள் அறுவடையை விற்கவும்", sell_sub: "வாங்குபவரையும் பேருந்து அல்லது ரயிலையும் நாங்கள் கண்டுபிடிப்போம்.", speak: "பேசிச் சொல்லுங்கள்", other: "புகைப்படம் அனுப்புங்கள் அல்லது தட்டச்சு செய்யுங்கள்", prices_at: "காலை 06:00 விலை",
    hold: "பேச அழுத்திப் பிடிக்கவும்", hold_sub: "பயிர், கிலோ, தயாராகும் நாளைச் சொல்லுங்கள்", example: "உதாரணம்", ex_text: "\u201cகேரட், 280 கிலோ, நாளை தயார், கந்தபொல.\u201d", or1: "அல்லது", take_photo: "குறிப்பின் புகைப்படம் எடுங்கள்", type_it: "தட்டச்சு செய்யுங்கள்", understands: "Govi சிங்களம், தமிழ், ஆங்கிலம் புரிந்துகொள்ளும்.",
    listening: "கேட்டுக்கொண்டிருக்கிறது\u2026", let_go: "அனுப்ப விடுங்கள்", slide_cancel: "ரத்து செய்ய இடப்புறம் இழுக்கவும்", reading: "உங்கள் குரல் செய்தியைப் படிக்கிறது\u2026", mic_off: "மைக்ரோஃபோனைப் பயன்படுத்த முடியவில்லை. உலாவியில் அனுமதியுங்கள் அல்லது தட்டச்சு செய்யுங்கள்.",
    t_loads: "என் சுமைகள்", n_home: "முகப்பு", n_loads: "என் சுமைகள்", pay_note: "பொருள் ஒப்படைத்த பின் பணம் கிடைக்கும், வழக்கமாக அதே நாளில்.", more_s: "+ரூ {n} அதிகம்", cmp_line: "சேகரிப்பாளர் ரூ {c} \u00b7 கடை ரூ {r}",
  },
};
const MODE = { night_bus: "🚌", train_parcel: "🚆", sl_post: "📮", lorry: "🚚" };
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const rs = (n) => "Rs " + Math.round(n).toLocaleString("en-LK");
const ls = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};
let lang = (() => { try { return localStorage.getItem("lang") || "si"; } catch { return "si"; } })();
const t = (k) => T[lang][k] ?? T.en[k];
const cname = (c) => GOVI.name(c, lang);
const locale = () => (lang === "en" ? "en-GB" : lang + "-LK");
const day = (d) => d ? new Date(d + "T00:00").toLocaleDateString(locale(), { weekday: "short", day: "numeric", month: "short" }) : "";
const fill = (s, o) => s.replace(/\{(\w+)\}/g, (_, k) => o[k]);
const n0 = (n) => Math.round(n).toLocaleString("en-LK");
// Name and phone are remembered so a returning farmer only picks crop, amount and day.
let you = ls.get("you", { name: "", phone: "" });
let account = null; // the signed-in user (phone sign-in), or null

function applyLang() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-t]").forEach((el) => (el.textContent = t(el.dataset.t)));
  document.querySelectorAll("#langs button").forEach((b) => b.classList.toggle("on", b.dataset.l === lang));
  $("text").placeholder = t("ph_farmer");
  ["ring", "ring2"].forEach((id) => $(id).setAttribute("aria-label", t("hold")));
  $("pdate").textContent = new Date().toLocaleDateString(locale(), { day: "numeric", month: "short" });
  renderPrices(); renderForm(); renderAccount();
  if ($("mine").dataset.loaded) loadTrack();
}

// ---- 1.01 first visit: pick a language
function welcome() {
  let seen = false;
  try { seen = !!localStorage.getItem("lang"); } catch {}
  $("welcome").hidden = seen;
}
document.querySelectorAll("[data-pick]").forEach((b) => (b.onclick = () => {
  lang = b.dataset.pick; try { localStorage.setItem("lang", lang); } catch {}
  $("welcome").hidden = true; applyLang(); saveLang();
}));

// ---- tabs and the sell screen's own steps
const VIEWS = ["start", "rec", "read", "type", "out"];
let view = "start";
function sellView(v) {
  view = v;
  VIEWS.forEach((x) => ($("s-" + x).hidden = x !== v));
  $("send-title").hidden = v === "rec" || v === "read";
}
function tab(name) {
  document.querySelectorAll(".tabs button").forEach((x) => x.classList.toggle("on", x.dataset.tab === name));
  document.querySelectorAll(".pane").forEach((p) => p.classList.toggle("on", p.id === name));
  window.scrollTo({ top: 0 });
  if (name === "track") loadTrack();
  if (name === "send" && view !== "rec" && view !== "read") sellView("start");
}
document.querySelectorAll(".tabs button").forEach((b) => (b.onclick = () => tab(b.dataset.tab)));
$("back").onclick = () => {
  if (view === "rec" && rec) { rec.cancel = true; return rec.mr.stop(); }
  if (view === "read") return;
  view === "start" ? tab("prices") : sellView("start");
};
$("to-type").onclick = () => sellView("type");
document.addEventListener("click", (e) => { const b = e.target.closest("[data-go]"); if (b) tab(b.dataset.go); });

// ---- type it instead: the form
let form = { crop: null, ready: 1, crops: [], towns: [] };
Object.assign(form, ls.get("hform", {}), { crops: [], towns: [] });
const iso = (d) => { const x = new Date(); x.setDate(x.getDate() + d); return x.toISOString().slice(0, 10); };
function renderForm() {
  $("h-crops").innerHTML = form.crops.map((c) => `<button type="button" data-c="${esc(c)}" class="${c === form.crop ? "on" : ""}" aria-pressed="${c === form.crop}">${GOVI.icon(c, 44)}<span>${esc(cname(c))}</span></button>`).join("");
  $("h-crops").querySelectorAll("button").forEach((b) => (b.onclick = () => { form.crop = b.dataset.c; renderForm(); }));
  $("h-ready").innerHTML = [[0, "today"], [1, "tomorrow"], [2, "in2"]].map(([d, k]) => `<button type="button" data-d="${d}" class="${d === form.ready ? "on" : ""}">${t(k)}</button>`).join("");
  $("h-ready").querySelectorAll("button").forEach((b) => (b.onclick = () => { form.ready = +b.dataset.d; renderForm(); }));
  const cur = $("h-town").value || form.town;
  $("h-town").innerHTML = form.towns.map((x) => `<option ${x === cur ? "selected" : ""}>${esc(x)}</option>`).join("");
}
document.querySelectorAll(".qty button").forEach((b) => (b.onclick = () => { $("h-kg").value = Math.max(1, (+$("h-kg").value || 0) + +b.dataset.d); }));
document.querySelectorAll("#presets button").forEach((b) => (b.onclick = () => { $("h-kg").value = b.textContent; }));
fetch("/api/towns").then((r) => r.json()).then((d) => { form.crops = d.crops; form.towns = d.origins; renderForm(); });

const phone = () => account ? account.phone : $("h-phone").value.trim();
function remember(name, ph) {
  you = { name: name || you.name, phone: ph || you.phone }; ls.set("you", you);
  if (!account) $("h-phone").value = you.phone;
  renderAccount();
}

// ---- account: sign in with the mobile number; WhatsApp messages from it are already yours
function renderAccount() {
  $("acct-name").textContent = account ? account.name || GOVI.auth.pretty(account.phone) : t("signin");
  $("acct").setAttribute("aria-label", account ? account.name : t("signin"));
  $("h-who").hidden = !!account; $("h-as").hidden = !account;
  if (account) $("h-as").textContent = fill(t("posting_as"), { n: account.name, p: GOVI.auth.pretty(account.phone) });
  $("am-name").textContent = account?.name || ""; $("am-phone").textContent = account ? GOVI.auth.pretty(account.phone) : "";
  const h = new Date().getHours(), who = (account?.name || you.name || "").trim().split(/\s+/)[0];
  $("greet").textContent = t(h < 12 ? "greet_am" : h < 18 ? "greet_pm" : "greet_eve") + (who ? ", " + who : "");
  $("greet-sub").textContent = [form.town, new Date().toLocaleDateString(locale(), { weekday: "short", day: "numeric", month: "short" }), t("prices_at")].filter(Boolean).join(" · ");
}
async function signIn() {
  const u = await GOVI.auth.open({ lang, role: "farmer" });
  if (u) { account = u; useAccountLang(u); renderAccount(); if ($("track").classList.contains("on")) loadTrack(); }
  return u;
}
$("acct").onclick = (e) => { e.stopPropagation(); if (account) { $("acct-menu").hidden = !$("acct-menu").hidden; loadPlan(); } else signIn(); };
document.addEventListener("click", (e) => { if (!e.target.closest(".acct-wrap")) $("acct-menu").hidden = true; });
$("am-out").onclick = async () => {
  await GOVI.auth.logout(); account = null; $("acct-menu").hidden = true; renderAccount();
  $("mine").innerHTML = ""; delete $("mine").dataset.loaded; if ($("track").classList.contains("on")) loadTrack();
};
function result(ok, text, withTrack) {
  return `<div class="result ${ok ? "ok" : "bad"}"><div class="h"><span class="tick">${ok ? "✓" : "!"}</span><span>${esc(text)}</span></div>
    ${withTrack ? `<button class="cta primary" data-go="track">${t("see_orders")} →</button>` : ""}</div>`;
}
const finish = (html) => { $("s-out").innerHTML = html; sellView("out"); };

$("h-go").onclick = async () => {
  const body = { farmer: account ? account.name : $("h-name").value.trim(), phone: phone(), crop: form.crop, qty_kg: +$("h-kg").value,
    ready_on: iso(form.ready), location: $("h-town").value, lang };
  if (!body.farmer || !body.phone || !body.crop || !(body.qty_kg > 0)) {
    $("h-out").innerHTML = result(false, t("h_fill"));
    (!body.crop || account ? $("h-crops") : !body.farmer ? $("h-name") : $("h-phone")).scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }
  $("h-out").innerHTML = "";
  $("h-go").disabled = true; $("h-go").textContent = t("sent");
  try {
    const r = await fetch("/api/listings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof d.detail === "string" ? d.detail : t("err"));
    ls.set("hform", { town: body.location, ready: form.ready });
    if (!account) remember(body.farmer, body.phone);
    const m = d.matches[0];
    finish(result(true, m ? fill(t("h_matched"), { kg: Math.round(d.matched_kg), buyer: m.buyer, price: Math.round(m.farmer_gets_lkr_per_kg) }) : t("h_done"), true));
  } catch (e) { $("h-out").innerHTML = result(false, e.message); }
  finally { $("h-go").disabled = false; $("h-go").textContent = t("h_post"); }
};

// ---- 1.02 prices: lead with what the farmer gets and how much more than the collector pays
let prices = [];
async function loadPrices() { prices = await (await fetch("/api/prices")).json(); renderPrices(); }
function renderPrices() {
  $("plist").innerHTML = prices.map((p) => {
    const gain = p.farmer_fair - p.collector;
    return `<article class="price" role="button" tabindex="0" data-sell="${esc(p.crop)}">
      <div class="t"><div class="c">${GOVI.icon(p.crop, 32)}${esc(cname(p.crop))}</div>${gain > 0 ? `<span class="d">${esc(fill(t("more_s"), { n: n0(gain) }))}</span>` : ""}</div>
      <div class="p"><b class="num">${rs(p.farmer_fair)}</b><span>${t("per_kg")}</span></div>
      <div class="l">${esc(fill(t("cmp_line"), { c: n0(p.collector), r: n0(p.retail) }))}</div>
    </article>`;
  }).join("");
  $("plist").querySelectorAll("[data-sell]").forEach((b) => {
    const go = () => { form.crop = b.dataset.sell; renderForm(); tab("send"); sellView("type"); };
    b.onclick = go;
    b.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } };
  });
}

// The picked language is also the chat language: replies to a photo, voice note or message in
// any other language still come back in this one (saved on the account when signed in).
function saveLang() {
  if (account && account.lang !== lang) {
    fetch("/api/me", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lang }) })
      .then((r) => r.ok && r.json()).then((u) => { if (u) account = u; }).catch(() => {});
  }
}
document.querySelectorAll("#langs button").forEach((b) => (b.onclick = () => {
  lang = b.dataset.l; try { localStorage.setItem("lang", lang); } catch {}
  applyLang(); saveLang();
}));

// ---- send a note, photo or voice note: same pipeline as WhatsApp
async function sendIntake(text, file) {
  sellView("read");
  const fd = new FormData();
  // A hint for the parser; Gemini still decides from the content.
  if (text) fd.append("text", "[harvest] " + text);
  if (file) fd.append("file", file, file.name || "voice." + (file.type.includes("mp4") ? "m4a" : file.type.includes("ogg") ? "ogg" : "webm"));
  fd.append("sender", phone());
  fd.append("lang", lang);
  try {
    const r = await fetch("/intake", { method: "POST", body: fd });
    const out = await r.json().catch(() => ({}));
    if (!r.ok) return finish(result(false, typeof out.detail === "string" ? out.detail : t("err")));
    $("text").value = ""; $("picked").hidden = true;
    if (!account) remember("", phone());
    finish(result(true, out.reply, true));
  } catch { finish(result(false, t("err"))); }
}
$("go").onclick = () => {
  const text = $("text").value.trim();
  if (!text) return $("text").focus();
  if (!phone()) { $("reply").innerHTML = result(false, t("phone_need")); $("h-phone").focus(); return; }
  $("reply").innerHTML = "";
  sendIntake(text, null);
};
$("photo").onchange = async () => {
  const f = $("photo").files[0];
  if (!f) return;
  if (!phone()) { await signIn(); if (!phone()) { $("photo").value = ""; return; } }
  await sendIntake(null, f);
  $("photo").value = "";
};

// ---- 1.03 to 1.05: hold to speak, then it goes the same way as a WhatsApp voice note
let rec = null, holding = false, startX = 0;
const wave = document.querySelector("#s-rec .wave");
wave.innerHTML = Array.from({ length: 28 }, (_, i) => `<i style="animation-delay:-${(i * 0.13).toFixed(2)}s;animation-duration:${(0.7 + ((i * 7) % 5) / 10).toFixed(1)}s"></i>`).join("");
async function startRec() {
  if (rec) return;
  if (!phone()) { holding = false; signIn(); return; }
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch { holding = false; return finish(result(false, t("mic_off"))); }
  // The finger may have lifted while the permission prompt was open.
  if (!holding) { stream.getTracks().forEach((s) => s.stop()); return; }
  const mr = new MediaRecorder(stream), chunks = [];
  mr.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  rec = { mr, stream, chunks, t0: Date.now(), cancel: false };
  const tick = () => { const s = Math.floor((Date.now() - rec.t0) / 1000); $("clock").textContent = Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };
  tick(); rec.timer = setInterval(tick, 250);
  mr.onstop = () => {
    const r = rec; rec = null; clearInterval(r.timer); r.stream.getTracks().forEach((s) => s.stop());
    // A tap is not a note: under a second, or slid away, goes back to the start.
    if (r.cancel || Date.now() - r.t0 < 1000 || !r.chunks.length) return sellView("start");
    sendIntake(null, new Blob(r.chunks, { type: mr.mimeType || "audio/webm" }));
  };
  mr.start(); sellView("rec"); $("ring2").focus();
}
const stopRec = () => { holding = false; if (rec && rec.mr.state === "recording") rec.mr.stop(); };
$("ring").onpointerdown = (e) => { holding = true; startX = e.clientX; startRec(); };
document.addEventListener("pointerup", stopRec);
document.addEventListener("pointercancel", stopRec);
document.addEventListener("pointermove", (e) => { if (rec && startX - e.clientX > 80) rec.cancel = true; });
["ring", "ring2"].forEach((id) => {
  $(id).oncontextmenu = (e) => e.preventDefault();
  // keyboard: press once to start, once to send
  $(id).onkeydown = (e) => {
    if (e.repeat || (e.key !== " " && e.key !== "Enter")) return;
    e.preventDefault();
    if (rec) stopRec(); else { holding = true; startRec(); }
  };
});

// ---- 1.10 my loads
const STEPS = ["booked", "loaded", "in_transit", "arrived", "delivered"];
function stepsHtml(x, kind) {
  const at = STEPS.indexOf(x.status);
  const sub = (i) => i !== at || !x.ref ? "" : `<small>${t("ref")} ${esc(x.ref)} · ${kind === "listing"
    ? `${t("dropoff")}: ${esc(x.lane.pickup || x.origin)}`
    : `${t("eta")}: ${new Date(x.schedule.delivered).toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit" })}`}</small>`;
  return `<div class="steps">${STEPS.map((st, i) => {
    const done = i < at || (i === at && st === "delivered");
    return `<div class="step ${done ? "done" : i === at ? "now" : "up"}"><div class="rail"><span class="dot">${done ? '<i class="ic i-check"></i>' : ""}</span><span class="line"></span></div>
      <div class="tx"><b>${t("s_" + st)}</b>${sub(i)}</div></div>`;
  }).join("")}</div>`;
}
// The Rs 799/month service plan: paid until, or due / overdue since.
async function loadPlan() {
  $("plan").hidden = true; $("am-plan").textContent = "";
  if (!account) return;
  const r = await fetch("/api/me/subscription").catch(() => null);
  const p = r && r.ok ? await r.json() : null;
  if (!p || p.status === "none") return;
  const txt = fill(t("plan_" + p.status), { p: n0(p.amount_lkr), d: day(p.status === "active" ? p.paid_until : p.due_on) });
  $("am-plan").textContent = txt;
  $("plan").textContent = txt; $("plan").className = "plan " + p.status; $("plan").hidden = false;
}
async function loadTrack() {
  $("t-signin").hidden = !!account;
  loadPlan();
  if (!account) { $("mine").innerHTML = ""; return; }
  $("mine").dataset.loaded = "1";
  const r = await fetch("/api/track");
  if (r.status === 401) { account = null; renderAccount(); return loadTrack(); }
  const d = await r.json();
  const card = (x, kind) => {
    const title = `${esc(cname(x.crop))} · ${Math.round(x.qty_kg)} kg`;
    if (!(x.matched_kg > 0)) {
      return `<div class="load slim"><div><span class="ttl">${title}</span><p class="sub">${kind === "listing" ? t("selling") : t("ordering")} · ${esc(x.location)} · ${day(x.ready_on || x.needed_by)}</p></div><span class="chip">${t("waiting")}</span></div>`;
    }
    const first = x.matches.find((m) => m.shipment);
    const lines = x.matches.map((m) => `${m.shipment ? stepsHtml(m.shipment, kind) : ""}<p class="sub">${m.lane ? MODE[m.lane.mode] || "🚚" : "📍"} <b>${Math.round(m.qty_kg)} kg</b> ${kind === "listing" ? t("to") + " " + esc(m.buyer) : t("from") + " " + esc(m.farmer)}${m.lane ? ` · ${esc(m.lane.origin)} ${m.lane.departs}` : ""}</p>
      <p class="sub">${kind === "listing" ? t("you_get") + " <b>" + rs(m.farmer_gets_lkr_per_kg) : "<b>" + rs(m.buyer_pays_lkr_per_kg)}${t("per_kg")}</b>${kind === "listing" ? ` · ${t("transport_off")}: ${rs(m.transport_lkr_per_kg)}${t("per_kg")}${m.transport_lkr_per_kg < m.solo_transport_lkr_per_kg ? " · " + t("shared") : ""}` : ""}</p>
      ${m.code ? `<p class="sub">${t("code")}: <b>${esc(m.code)}</b> · <a href="/t/${encodeURIComponent(m.code)}" target="_blank" rel="noopener">${t("track_it")} →</a></p>` : ""}
      ${m.code && m.lane && kind === "listing" ? (m.shipping_paid_lkr
        ? `<p class="sub">${esc(fill(t("cost_saved"), { n: n0(m.shipping_paid_lkr) }))}</p>`
        : `<form class="costf" data-code="${esc(m.code)}"><label class="sub">${t("cost_q")}<input type="number" min="1" step="1" inputmode="numeric" required></label><button class="cta outline">${t("cost_save")}</button></form>`) : ""}`).join("");
    return `<div class="load"><div class="top"><span class="ttl">${title}</span><span class="chip info">${first ? t("s_" + first.shipment.status) : t("matched")}</span></div>
      <p class="sub">${kind === "listing" ? t("selling") : t("ordering")} · ${esc(x.location)} · ${day(x.ready_on || x.needed_by)}</p>
      ${lines}${kind === "listing" ? `<div class="paynote"><span class="ic i-wallet"></span><span>${t("pay_note")}</span></div>` : ""}</div>`;
  };
  const html = d.listings.map((x) => card(x, "listing")).join("") + d.orders.map((x) => card(x, "order")).join("");
  $("mine").innerHTML = html || `<div class="empty">${t("none")}</div>`;
  // After a shipment, the seller types what it really cost: Govi's lane price follows.
  $("mine").querySelectorAll(".costf").forEach((f) => (f.onsubmit = async (e) => {
    e.preventDefault();
    const lkr = +f.querySelector("input").value;
    if (!(lkr > 0)) return;
    f.querySelector("button").disabled = true;
    const r = await fetch("/api/shipping-cost", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code: f.dataset.code, lkr }) });
    if (r.ok) loadTrack(); else { f.querySelector("button").disabled = false; f.insertAdjacentHTML("beforeend", `<p class="sub">${t("err")}</p>`); }
  }));
}
$("tgo").onclick = signIn;

fetch("/api/health").then((r) => r.json()).then((h) => {
  const n = (h.whatsapp_number || "").replace(/\D/g, "");
  // No number configured means no button: a dead link on the first screen looks broken.
  if (n) { $("wa").href = `https://wa.me/${n}`; $("wa").hidden = false; }
});
$("h-name").value = you.name; $("h-phone").value = you.phone;
welcome();
sellView("start");
applyLang();
loadPrices();
// A signed-in account brings its own language (it may have been changed from WhatsApp).
const useAccountLang = (u) => { if (u && ["si", "ta", "en"].includes(u.lang) && u.lang !== lang) { lang = u.lang; try { localStorage.setItem("lang", lang); } catch {} applyLang(); } };
GOVI.auth.me().then((u) => { account = u; useAccountLang(u); renderAccount(); if ($("track").classList.contains("on")) loadTrack(); });
