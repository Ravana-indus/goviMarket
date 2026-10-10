// Market agent price entry. Built for one thumb on a phone in a busy market.
// Sinhala and Tamil strings need a native speaker's review before the demo.
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const CHECK = 0.35; // same threshold as the server
const T = {
  en: {
    agent: "Market agent", pin: "Agent PIN", bad_pin: "That PIN is not right. Ask Govi for the agent PIN.", si_title: "Today's market prices", si_sub: "Tell us who you are and which market you cover. You only do this once.",
    name: "Your name", phone: "WhatsApp number", market: "Market", start: "Start", demo: "Use demo agent (Dambulla)", switch: "change",
    k_collector: "Farm gate", k_collector_s: "collector pays", k_wholesale: "Wholesale", k_wholesale_s: "economic centre", k_retail: "Retail", k_retail_s: "shop price",
    tap: "Tap to enter", board: "Board", last: "you sent", skip: "Skip", next: "Next ›", done_btn: "Done",
    send: (n) => `Send ${n} price${n === 1 ? "" : "s"}`, nothing: "Tap a crop to enter its price",
    big: (b) => `Big change from Rs ${b}. Check before sending.`, flagged: "Big change, will be checked before it goes live",
    sent_ok: (n) => `${n} price${n === 1 ? "" : "s"} sent. Farmers and buyers see them now.`, sent_today: "What you sent", none: "Nothing sent yet.",
    same: "Same", sending: "Sending…", live: "live", wait: "checking", phone_in: "Sign in with mobile number",
  },
  si: {
    agent: "වෙළඳපොළ නියෝජිත", pin: "නියෝජිත PIN අංකය", bad_pin: "PIN අංකය වැරදියි. Govi වෙතින් අසන්න.", si_title: "අද වෙළඳපොළ මිල", si_sub: "ඔබ කවුද සහ ඔබ ආවරණය කරන වෙළඳපොළ කුමක්ද කියන්න. මෙය එක් වරක් පමණි.",
    name: "ඔබේ නම", phone: "WhatsApp අංකය", market: "වෙළඳපොළ", start: "අරඹන්න", demo: "ආදර්ශ නියෝජිත (දඹුල්ල)", switch: "වෙනස් කරන්න",
    k_collector: "ගොවිපල මිල", k_collector_s: "එකතු කරන්නා ගෙවන", k_wholesale: "තොග මිල", k_wholesale_s: "ආර්ථික මධ්‍යස්ථානය", k_retail: "සිල්ලර මිල", k_retail_s: "කඩේ මිල",
    tap: "මිල ඇතුළත් කරන්න", board: "පුවරුව", last: "ඔබ එවූ", skip: "මඟ හරින්න", next: "ඊළඟ ›", done_btn: "හරි",
    send: (n) => `මිල ${n}ක් යවන්න`, nothing: "මිල ඇතුළත් කිරීමට බෝගයක් ඔබන්න",
    big: (b) => `රු ${b} සිට විශාල වෙනසක්. යැවීමට පෙර පරීක්ෂා කරන්න.`, flagged: "විශාල වෙනසක්, ප්‍රසිද්ධ කිරීමට පෙර පරීක්ෂා කෙරේ",
    sent_ok: (n) => `මිල ${n}ක් යැව්වා. ගොවීන්ට සහ ගැනුම්කරුවන්ට දැන් පෙනේ.`, sent_today: "ඔබ එවූ මිල", none: "තවම කිසිවක් එවා නැත.",
    same: "එසේම", sending: "යවමින්…", live: "සජීවී", wait: "පරීක්ෂාවට", phone_in: "ජංගම අංකයෙන් පිවිසෙන්න",
  },
  ta: {
    agent: "சந்தை முகவர்", pin: "முகவர் PIN", bad_pin: "PIN தவறு. Govi இடம் கேளுங்கள்.", si_title: "இன்றைய சந்தை விலை", si_sub: "நீங்கள் யார், எந்தச் சந்தையைக் கவனிக்கிறீர்கள் என்று சொல்லுங்கள். ஒருமுறை மட்டுமே.",
    name: "உங்கள் பெயர்", phone: "WhatsApp எண்", market: "சந்தை", start: "தொடங்கு", demo: "மாதிரி முகவர் (தம்புள்ளை)", switch: "மாற்று",
    k_collector: "பண்ணை விலை", k_collector_s: "சேகரிப்பாளர் தருவது", k_wholesale: "மொத்த விலை", k_wholesale_s: "பொருளாதார மையம்", k_retail: "சில்லறை விலை", k_retail_s: "கடை விலை",
    tap: "விலையை உள்ளிடவும்", board: "பலகை", last: "நீங்கள் அனுப்பியது", skip: "தவிர்", next: "அடுத்து ›", done_btn: "சரி",
    send: (n) => `${n} விலைகளை அனுப்பு`, nothing: "விலையை உள்ளிட ஒரு பயிரைத் தட்டவும்",
    big: (b) => `ரூ ${b} இலிருந்து பெரிய மாற்றம். அனுப்பும் முன் சரிபார்க்கவும்.`, flagged: "பெரிய மாற்றம், வெளியிடும் முன் சரிபார்க்கப்படும்",
    sent_ok: (n) => `${n} விலைகள் அனுப்பப்பட்டன. விவசாயிகளும் வாங்குபவர்களும் இப்போது பார்க்கலாம்.`, sent_today: "நீங்கள் அனுப்பியவை", none: "இன்னும் எதுவும் அனுப்பவில்லை.",
    same: "அதே", sending: "அனுப்புகிறது…", live: "நேரலை", wait: "சரிபார்ப்பில்", phone_in: "மொபைல் எண்ணுடன் உள்நுழை",
  },
};
const KIND = ["collector", "wholesale", "retail"];
const ls = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};
let lang = ls.get("agent_lang", "si");
let me = ls.get("agent", null);
let kind = ls.get("agent_kind", "wholesale");
let entries = { collector: {}, wholesale: {}, retail: {} };
let board = [], markets = [], pick = null;
let pad = { crop: null, val: "" };
let locked = false;
fetch("/api/health").then((r) => r.json()).then((h) => { locked = h.agent_locked; $("pin-row").hidden = !locked; });

const t = (k, ...a) => { const v = (T[lang] || T.en)[k] ?? T.en[k]; return typeof v === "function" ? v(...a) : v; };
const cname = (c) => GOVI.name(c, lang);
const rs = (n) => Math.round(n).toLocaleString("en-LK");
const ref = (r) => r.last_here ?? r.current;
const big = (r, v) => r.current && Math.abs(v - r.current) / r.current > CHECK;

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: { ...(opts.headers || {}), "X-Agent-Pin": me?.pin || "" } });
  const body = await r.json().catch(() => ({}));
  if (r.status === 401 && me) {  // wrong or changed PIN: back to sign-in
    me = null; ls.set("agent", null); show();
    $("si-err").hidden = false; $("si-err").textContent = t("bad_pin");
  }
  if (!r.ok) throw new Error(typeof body.detail === "string" ? body.detail : r.statusText);
  return body;
}

function applyLang() {
  document.documentElement.lang = lang;
  document.querySelectorAll("#langs button").forEach((b) => b.classList.toggle("on", b.dataset.l === lang));
  document.querySelectorAll("[data-t]").forEach((el) => { el.textContent = t(el.dataset.t); });
  render();
}
document.querySelectorAll("#langs button").forEach((b) => (b.onclick = () => { lang = b.dataset.l; ls.set("agent_lang", lang); applyLang(); loadHist(); }));

// ---- sign in
function renderMarkets() {
  $("markets").innerHTML = markets.map((m) => `<button data-m="${esc(m)}" class="${m === pick ? "on" : ""}">${esc(m)}</button>`).join("");
  $("markets").querySelectorAll("button").forEach((b) => (b.onclick = () => { pick = b.dataset.m; renderMarkets(); }));
}
function signIn(a) { me = a; ls.set("agent", a); show(); }
let account = null; // phone sign-in with the agent role: no PIN needed on this device
async function useAccount(u) {
  if (!u) return;
  if (u.role !== "agent") u = await GOVI.auth.profile(u, { role: "agent", lang });  // asks for the PIN once
  if (!u || u.role !== "agent") return;
  account = u;
  $("si-name").value = u.name; $("si-phone").value = "0" + u.phone.slice(2);
  $("pin-row").hidden = true; $("si-phone-go").hidden = true;
  if (u.market && markets.includes(u.market)) { pick = u.market; renderMarkets(); signIn({ name: u.name, phone: u.phone, market: u.market, pin: "" }); }
}
$("si-phone-go").onclick = async () => useAccount(await GOVI.auth.open({ role: "agent", lang }));
$("si-go").onclick = () => {
  const name = $("si-name").value.trim();
  let phone = $("si-phone").value.replace(/\D/g, "");
  if (phone.length === 10 && phone.startsWith("0")) phone = "94" + phone.slice(1);
  const err = !name ? t("name") : phone.length < 9 ? t("phone") : !pick ? t("market") : locked && !account && !$("si-pin").value ? t("pin") : "";
  $("si-err").hidden = !err; $("si-err").textContent = err ? "⚠ " + err : "";
  if (err) return;
  if (account) {  // remember the market on the account
    fetch("/api/me", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ market: pick }) });
    return signIn({ name: account.name, phone: account.phone, market: pick, pin: "" });
  }
  signIn({ name, phone, market: pick, pin: $("si-pin").value });
};
$("si-demo").onclick = () => {
  if (locked && !$("si-pin").value) { $("si-err").hidden = false; $("si-err").textContent = "⚠ " + t("pin"); return; }
  signIn({ name: "Kumari", phone: "94770000099", market: "Dambulla", pin: $("si-pin").value });
};
$("switch").onclick = async (e) => {
  e.preventDefault(); me = null; ls.set("agent", null);
  if (account) { await GOVI.auth.logout(); account = null; $("pin-row").hidden = !locked; $("si-phone-go").hidden = false; }
  show();
};

function show() {
  $("signin").hidden = !!me;
  $("main").hidden = !me;
  $("sendbar").hidden = !me;
  if (me) { $("w-market").textContent = me.market; $("w-who").textContent = `${me.name} · ${me.phone}`; loadBoard(); loadHist(); }
}

// ---- price kind
document.querySelectorAll("#kinds button").forEach((b) => (b.onclick = () => { kind = b.dataset.k; ls.set("agent_kind", kind); loadBoard(); }));

async function loadBoard() {
  document.querySelectorAll("#kinds button").forEach((b) => b.classList.toggle("on", b.dataset.k === kind));
  const d = await api(`/api/agent/board?kind=${kind}&market=${encodeURIComponent(me.market)}`);
  board = d.crops; markets = d.markets;
  render();
}

function render() {
  if (!me) return;
  const mine = entries[kind];
  $("rows").innerHTML = board.map((r) => {
    const v = mine[r.crop];
    const cls = v == null ? "" : big(r, v) ? "check" : "set";
    const hint = [r.current ? `${t("board")} Rs ${rs(r.current)}` : "", r.last_here ? `${t("last")} Rs ${rs(r.last_here)}` : ""].filter(Boolean).join(" · ");
    return `<div class="card row ${cls}" data-c="${esc(r.crop)}" role="button" tabindex="0">
      ${GOVI.icon(r.crop, 44)}<div><div class="nm">${esc(cname(r.crop))}</div><div class="hint">${hint}</div>${cls === "check" ? `<div class="flag">⚠ ${esc(t("flagged"))}</div>` : ""}</div>
      <div class="val ${v == null ? "ghost" : ""}" aria-label="${esc(t("tap"))}">${v == null ? "Rs —" : "Rs " + rs(v)}</div>
    </div>`;
  }).join("");
  $("rows").querySelectorAll(".row").forEach((el) => (el.onclick = () => openPad(el.dataset.c)));
  const n = KIND.reduce((s, k) => s + Object.keys(entries[k]).length, 0);
  $("send").textContent = n ? t("send", n) : t("nothing");
  $("send").disabled = !n;
}

// ---- number pad
const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "00", "0", "⌫"];
$("keys").innerHTML = KEYS.map((k) => `<button data-k="${k}">${k}</button>`).join("");
$("keys").querySelectorAll("button").forEach((b) => (b.onclick = () => {
  const k = b.dataset.k;
  pad.val = k === "⌫" ? pad.val.slice(0, -1) : (pad.val + k).replace(/^0+/, "").slice(0, 4);
  drawPad();
}));
function row(c) { return board.find((r) => r.crop === c); }
function openPad(crop) {
  pad = { crop, val: entries[kind][crop] != null ? String(entries[kind][crop]) : "" };
  $("pad").hidden = false; drawPad();
}
function drawPad() {
  const r = row(pad.crop), base = ref(r), v = Number(pad.val || 0);
  $("p-crop").textContent = cname(pad.crop);
  $("p-ref").textContent = [r.current ? `${t("board")} Rs ${rs(r.current)}` : "", r.last_here ? `${t("last")} Rs ${rs(r.last_here)}` : ""].filter(Boolean).join(" · ");
  $("p-val").textContent = pad.val ? rs(v) : "—";
  $("p-warn").textContent = pad.val && big(r, v) ? t("big", rs(r.current)) : "";
  const q = base ? [[`${t("same")} ${rs(base)}`, () => String(Math.round(base))], ["−10", () => String(Math.max(0, (v || base) - 10))], ["+10", () => String((v || base) + 10)], ["+50", () => String((v || base) + 50)]] : [];
  $("quick").innerHTML = q.map(([l], i) => `<button data-i="${i}">${l}</button>`).join("");
  $("quick").querySelectorAll("button").forEach((b) => (b.onclick = () => { pad.val = q[b.dataset.i][1](); drawPad(); }));
  const last = !board.some((x) => x.crop !== pad.crop && entries[kind][x.crop] == null);
  $("p-next").textContent = last ? t("done_btn") : t("next");
}
function closePad() { $("pad").hidden = true; render(); }
function advance() {
  const i = board.findIndex((r) => r.crop === pad.crop);
  const nxt = board.slice(i + 1).concat(board.slice(0, i)).find((r) => entries[kind][r.crop] == null);
  if (nxt) openPad(nxt.crop); else closePad();
  render();
}
$("p-next").onclick = () => {
  const v = Number(pad.val || 0);
  if (v > 0) entries[kind][pad.crop] = v; else delete entries[kind][pad.crop];
  advance();
};
$("p-skip").onclick = () => { delete entries[kind][pad.crop]; advance(); };
$("scrim").onclick = closePad;

// ---- send
$("send").onclick = async () => {
  const b = $("send"); b.disabled = true; b.textContent = t("sending");
  let count = 0, flagged = 0;
  try {
    for (const k of KIND) {
      const prices = Object.entries(entries[k]).map(([crop, lkr_per_kg]) => ({ crop, lkr_per_kg }));
      if (!prices.length) continue;
      const r = await api("/api/agent/prices", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reporter: me.name, phone: me.phone, market: me.market, kind: k, prices }) });
      count += r.count; flagged += r.saved.filter((s) => s.flagged).length;
      entries[k] = {};
    }
    $("done").innerHTML = `<div class="card done"><b>✓ ${esc(t("sent_ok", count - flagged))}</b>${flagged ? `<span class="small" style="color:var(--sun)">⚠ ${flagged}: ${esc(t("flagged"))}</span>` : ""}</div>`;
    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (e) {
    $("done").innerHTML = `<div class="card done" style="border-left-color:var(--clay)">${esc(e.message)}</div>`;
  }
  await loadBoard(); loadHist();
};

async function loadHist() {
  if (!me) return;
  const rows = await api(`/api/agent/reports?phone=${me.phone}&limit=20`);
  $("hist").innerHTML = rows.length ? rows.map((p) => `<div class="item">
      <span><b>${esc(cname(p.crop))}</b> <span class="muted small">${esc(t("k_" + p.kind))} · ${new Date(p.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span></span>
      <span class="num">Rs ${rs(p.lkr_per_kg)} <span class="chip ${p.flagged ? "warn" : "farmer"}">${esc(p.flagged ? t("wait") : t("live"))}</span></span>
    </div>`).join("") : `<div class="empty">${esc(t("none"))}</div>`;
}

(async () => {
  const d = await api("/api/agent/board").catch(() => ({ markets: [] }));
  markets = d.markets; renderMarkets();
  applyLang(); show();
  const u = await GOVI.auth.me();
  if (u && u.role === "agent") useAccount(u);
})();
