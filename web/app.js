// Sinhala and Tamil strings need a native speaker's review before the demo.
const T = {
  en: {
    hero: "Sell your harvest direct. Buy fresh from the farm.", sub: "No middlemen. Send a voice note, a photo or a message, and we find the buyer and the bus.",
    wa: "Message us on WhatsApp", or: "or use this page", t_prices: "Today's prices", t_send: "Sell / Order", t_track: "My orders",
    i_farmer: "I'm selling", i_buyer: "I'm buying", photo: "Photo", voice: "Voice note", phone_ph: "Your phone number",
    send: "Send", track: "Show my orders", ph_farmer: "e.g. Carrot 200kg ready Thursday, Nuwara Eliya", ph_buyer: "e.g. Need carrot 50kg and beans 20kg by Friday, Colombo 03",
    fair: "Fair price to farmer", collector: "Collector pays", retail: "Shop price", buyer: "You pay via Govi",
    waiting: "Waiting for a match", matched: "Matched", to: "to", from: "from", you_get: "You get", per_kg: "/kg",
    none: "Nothing found for this number yet.", note: "Prices update every morning from market reporters.",
    selling: "Selling", ordering: "Ordering", sent: "Sending…",
    s_booked: "Booked", s_loaded: "Loaded", s_in_transit: "On the way", s_arrived: "Arrived", s_delivered: "Delivered", ref: "Ref", dropoff: "Drop-off", eta: "Arrives",
    before_transport: "before transport", transport_off: "Transport already taken off", shared: "shared with neighbours",
  },
  si: {
    hero: "ඔබේ අස්වැන්න කෙලින්ම විකුණන්න. ගොවිපලෙන් අලුත් එළවළු.", sub: "අතරමැදියන් නැත. හඬ පණිවිඩයක්, ඡායාරූපයක් හෝ පණිවිඩයක් එවන්න. ගැනුම්කරු සහ බස් රථය අපි සොයා දෙන්නෙමු.",
    wa: "WhatsApp හරහා පණිවිඩයක් එවන්න", or: "නැතහොත් මෙම පිටුව භාවිතා කරන්න", t_prices: "අද මිල", t_send: "විකුණන්න / ඇණවුම්", t_track: "මගේ ඇණවුම්",
    i_farmer: "මම විකුණනවා", i_buyer: "මම මිලදී ගන්නවා", photo: "ඡායාරූපය", voice: "හඬ පණිවිඩය", phone_ph: "ඔබේ දුරකථන අංකය",
    send: "යවන්න", track: "මගේ ඇණවුම් පෙන්වන්න", ph_farmer: "උදා: කැරට් කිලෝ 200 බ්‍රහස්පතින්දා, නුවරඑළිය", ph_buyer: "උදා: කැරට් කිලෝ 50 සිකුරාදා වන විට, කොළඹ 03",
    fair: "ගොවියාට සාධාරණ මිල", collector: "එකතු කරන්නා ගෙවන්නේ", retail: "කඩේ මිල", buyer: "Govi හරහා ඔබ ගෙවන්නේ",
    waiting: "ගැළපීමක් බලාපොරොත්තුවෙන්", matched: "ගැළපුණා", to: "වෙත", from: "වෙතින්", you_get: "ඔබට ලැබෙන්නේ", per_kg: "/කිලෝ",
    none: "මෙම අංකයට තවම කිසිවක් නැත.", note: "වෙළඳපොළ වාර්තාකරුවන්ගෙන් සෑම උදෑසනකම මිල යාවත්කාලීන වේ.",
    selling: "විකිණීම", ordering: "ඇණවුම", sent: "යවමින්…",
    s_booked: "වෙන් කළා", s_loaded: "පැටෙව්වා", s_in_transit: "යමින්", s_arrived: "ළඟා විය", s_delivered: "භාර දුන්නා", ref: "අංකය", dropoff: "භාර දෙන තැන", eta: "ලැබෙන වේලාව",
    before_transport: "ප්‍රවාහනයට පෙර", transport_off: "ප්‍රවාහන වියදම දැනටමත් අඩු කර ඇත", shared: "අසල්වැසියන් සමඟ බෙදාගත්",
  },
  ta: {
    hero: "உங்கள் அறுவடையை நேரடியாக விற்கவும். பண்ணையிலிருந்து புதிதாக வாங்கவும்.", sub: "இடைத்தரகர்கள் இல்லை. குரல் செய்தி, புகைப்படம் அல்லது செய்தி அனுப்புங்கள். வாங்குபவரையும் பேருந்தையும் நாங்கள் கண்டுபிடிப்போம்.",
    wa: "WhatsApp இல் செய்தி அனுப்புங்கள்", or: "அல்லது இந்தப் பக்கத்தைப் பயன்படுத்துங்கள்", t_prices: "இன்றைய விலை", t_send: "விற்க / ஆர்டர்", t_track: "என் ஆர்டர்கள்",
    i_farmer: "நான் விற்கிறேன்", i_buyer: "நான் வாங்குகிறேன்", photo: "புகைப்படம்", voice: "குரல் செய்தி", phone_ph: "உங்கள் தொலைபேசி எண்",
    send: "அனுப்பு", track: "என் ஆர்டர்களைக் காட்டு", ph_farmer: "உதா: கேரட் 200 கிலோ வியாழன், நுவரெலியா", ph_buyer: "உதா: கேரட் 50 கிலோ வெள்ளிக்குள், கொழும்பு 03",
    fair: "விவசாயிக்கு நியாய விலை", collector: "சேகரிப்பாளர் தருவது", retail: "கடை விலை", buyer: "Govi மூலம் நீங்கள் செலுத்துவது",
    waiting: "பொருத்தத்திற்காகக் காத்திருக்கிறது", matched: "பொருந்தியது", to: "க்கு", from: "இடமிருந்து", you_get: "உங்களுக்குக் கிடைப்பது", per_kg: "/கிலோ",
    none: "இந்த எண்ணுக்கு இன்னும் எதுவும் இல்லை.", note: "சந்தை நிருபர்களிடமிருந்து ஒவ்வொரு காலையும் விலை புதுப்பிக்கப்படுகிறது.",
    selling: "விற்பனை", ordering: "ஆர்டர்", sent: "அனுப்புகிறது…",
    s_booked: "பதிவு", s_loaded: "ஏற்றப்பட்டது", s_in_transit: "வழியில்", s_arrived: "வந்தடைந்தது", s_delivered: "வழங்கப்பட்டது", ref: "எண்", dropoff: "ஒப்படைக்கும் இடம்", eta: "வந்தடையும் நேரம்",
    before_transport: "போக்குவரத்துக்கு முன்", transport_off: "போக்குவரத்து செலவு ஏற்கனவே கழிக்கப்பட்டது", shared: "அயலவர்களுடன் பகிர்ந்தது",
  },
};
const MODE = { night_bus: "🚌", train_parcel: "🚆", sl_post: "📮", lorry: "🚚" };
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const rs = (n) => "Rs " + Math.round(n).toLocaleString("en-LK");
let lang = (() => { try { return localStorage.getItem("lang") || "si"; } catch { return "si"; } })();
let role = "farmer";
const t = (k) => T[lang][k] ?? T.en[k];

function applyLang() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-t]").forEach((el) => (el.textContent = t(el.dataset.t)));
  document.querySelectorAll("[data-tp]").forEach((el) => (el.placeholder = t(el.dataset.tp)));
  document.querySelectorAll("#langs button").forEach((b) => b.classList.toggle("on", b.dataset.l === lang));
  $("text").placeholder = t(role === "farmer" ? "ph_farmer" : "ph_buyer");
  loadPrices();
}

async function loadPrices() {
  const rows = await (await fetch("/api/prices")).json();
  $("prices").innerHTML = rows.map((p) => `<div class="card price">
    <div class="head"><span class="crop">${esc(p.crop)}</span><span class="big num">${rs(p.farmer_fair)}<span class="sub">${t("per_kg")}</span></span></div>
    <div class="sub">${t("fair")} · ${t("before_transport")}</div>
    <div class="stats">
      <div><div class="sub">${t("collector")}</div><div class="num down">${rs(p.collector)}</div></div>
      <div><div class="sub">${t("buyer")}</div><div class="num">${rs(p.buyer_price)}</div></div>
      <div><div class="sub">${t("retail")}</div><div class="num muted">${rs(p.retail)}</div></div>
    </div>
  </div>`).join("");
}

document.querySelectorAll(".tabs button").forEach((b) => (b.onclick = () => {
  document.querySelectorAll(".tabs button").forEach((x) => x.classList.toggle("on", x === b));
  document.querySelectorAll(".pane").forEach((p) => p.classList.toggle("on", p.id === b.dataset.tab));
}));
document.querySelectorAll("#langs button").forEach((b) => (b.onclick = () => {
  lang = b.dataset.l; try { localStorage.setItem("lang", lang); } catch {}
  applyLang();
}));
document.querySelectorAll("#who button").forEach((b) => (b.onclick = () => {
  role = b.dataset.r;
  document.querySelectorAll("#who button").forEach((x) => x.classList.toggle("on", x === b));
  $("text").placeholder = t(role === "farmer" ? "ph_farmer" : "ph_buyer");
}));
["photo", "voice"].forEach((id) => ($(id).onchange = () => {
  const f = $("photo").files[0] || $("voice").files[0];
  $("picked").textContent = f ? "📎 " + f.name : "";
}));

$("go").onclick = async () => {
  const text = $("text").value.trim(), file = $("photo").files[0] || $("voice").files[0];
  if (!text && !file) return $("text").focus();
  const fd = new FormData();
  // A hint for the parser; Gemini still decides from the content.
  fd.append("text", (role === "buyer" ? "[order] " : "[harvest] ") + text);
  if (file) fd.append("file", file);
  fd.append("sender", $("phone").value.trim() || "web");
  $("go").disabled = true; $("go").textContent = t("sent");
  try {
    const out = await (await fetch("/intake", { method: "POST", body: fd })).json();
    $("reply").innerHTML = `<div class="card reply">${esc(out.reply)}</div>`;
    $("text").value = ""; $("photo").value = ""; $("voice").value = ""; $("picked").textContent = "";
    if ($("phone").value.trim()) $("tphone").value = $("phone").value.trim();
  } finally { $("go").disabled = false; $("go").textContent = t("send"); }
};

const STEPS = ["booked", "loaded", "in_transit", "arrived", "delivered"];
function shipSteps(x, kind) {
  const at = STEPS.indexOf(x.status);
  return `<div class="track">${STEPS.map((st, i) => `<span class="${i <= at ? "on" : ""}">${t("s_" + st)}</span>`).join("")}</div>
    ${x.ref ? `<div class="ship">${t("ref")} ${esc(x.ref)} · ${kind === "listing"
      ? `${t("dropoff")}: ${esc(x.lane.pickup || x.origin)}`
      : `${t("eta")}: ${new Date(x.schedule.delivered).toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit" })}`}</div>` : ""}`;
}

$("tgo").onclick = async () => {
  const phone = $("tphone").value.trim();
  if (!phone) return $("tphone").focus();
  const d = await (await fetch("/api/track?phone=" + encodeURIComponent(phone))).json();
  const card = (x, kind) => {
    const total = x.qty_kg, done = x.matched_kg, matched = done > 0;
    const ships = x.matches.map((m) => `${m.shipment ? shipSteps(m.shipment, kind) : ""}<div class="ship">${m.lane ? MODE[m.lane.mode] || "🚚" : "📍"} ${Math.round(m.qty_kg)} kg ${kind === "listing" ? t("to") + " " + esc(m.buyer) : t("from") + " " + esc(m.farmer)}
      ${m.lane ? `· ${esc(m.lane.origin)} ${m.lane.departs}` : ""} · ${kind === "listing" ? t("you_get") + " " + rs(m.farmer_gets_lkr_per_kg) : rs(m.buyer_pays_lkr_per_kg)}${t("per_kg")}
      ${kind === "listing" ? `<br>${t("transport_off")}: ${rs(m.transport_lkr_per_kg)}${t("per_kg")}${m.transport_lkr_per_kg < m.solo_transport_lkr_per_kg ? " · " + t("shared") : ""}` : ""}</div>`).join("");
    return `<div class="card item">
      <div class="row"><span class="title"><span style="text-transform:capitalize">${esc(x.crop)}</span> · ${Math.round(total)} kg</span>
      <span class="chip ${matched ? "farmer" : ""}">${matched ? t("matched") : t("waiting")}</span></div>
      <div class="small muted">${kind === "listing" ? t("selling") : t("ordering")} · ${esc(x.location)} · ${esc(x.ready_on || x.needed_by)}</div>
      ${ships}</div>`;
  };
  const html = d.listings.map((x) => card(x, "listing")).join("") + d.orders.map((x) => card(x, "order")).join("");
  $("mine").innerHTML = html || `<div class="empty">${t("none")}</div>`;
};

fetch("/healthz").then((r) => r.json()).then((h) => {
  const n = (h.whatsapp_number || "").replace(/\D/g, "");
  $("wa").href = n ? `https://wa.me/${n}` : "#";
});
applyLang();
