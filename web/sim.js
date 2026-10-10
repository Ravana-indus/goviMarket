// WhatsApp simulator: every message goes through /intake exactly like the real webhook,
// and everything Govi sends to this number (replies, match offers, shipment updates) shows up here.
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const PEOPLE = [
  { group: "Farmers", kind: "farmer", name: "Sunil", place: "Nuwara Eliya", phone: "94770000002",
    tries: ["This is Sunil, carrot 200kg ready tomorrow, Nuwara Eliya", "සුනිල්, කැරට් කිලෝ 200 හෙට, නුවරඑළිය"] },
  { group: "Farmers", kind: "farmer", name: "Nimal", place: "Dambulla", phone: "94770000004",
    tries: ["This is Nimal, tomato 150kg ready tomorrow, Dambulla", "නිමල්, තක්කාලි කිලෝ 150 හෙට, දඹුල්ල"] },
  { group: "Farmers", kind: "farmer", name: "Rasan", place: "Jaffna", phone: "94770000005",
    tries: ["This is Rasan, red onion 100kg ready tomorrow, Jaffna", "ரசன், சின்ன வெங்காயம் 100 கிலோ நாளை, யாழ்ப்பாணம்"] },
  { group: "Buyers", kind: "buyer", name: "Lotus Kitchen", place: "Colombo", phone: "94770000011",
    tries: ["Order from Lotus Kitchen: need carrot 50kg and beans 20kg by Friday, Colombo"] },
  { group: "Buyers", kind: "buyer", name: "Hill View Hotel", place: "Kandy", phone: "94770000015",
    tries: ["Order from Hill View Hotel: need tomato 60kg by Saturday, Kandy"] },
  { group: "Market agent", kind: "agent", name: "Dambulla agent", place: "Dambulla", phone: "94770000001",
    tries: ["Dambulla price today: tomato collector 100, beans collector 220"] },
];
const ls = { get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} } };
let people = PEOPLE.concat(ls.get("sim_extra", []));
let me = people.find((p) => p.phone === ls.get("sim_phone", "")) || people[0];
let local = {}; // phone -> [{at, url, kind}] media previews kept in this tab only
let pending = null, rec = null, waiting = false, lastCount = -1, failNote = "";

function renderPeople() {
  let html = "", group = "";
  for (const p of people) {
    if (p.group !== group) { group = p.group; html += `<h2>${esc(group)}</h2>`; }
    html += `<button class="person ${p.phone === me.phone ? "on" : ""}" data-p="${p.phone}"><span class="av ${p.kind}">${esc(p.name[0])}</span>
      <span><b>${esc(p.name)}</b><small>${esc(p.place)} · +${p.phone}</small></span></button>`;
  }
  html += `<div class="newnum"><input type="tel" id="newnum" placeholder="Another number, e.g. 0771234567"><button class="btn small" id="addnum">Add</button></div>`;
  $("people").innerHTML = html;
  document.querySelectorAll(".person").forEach((b) => (b.onclick = () => pick(b.dataset.p)));
  $("addnum").onclick = () => {
    let d = $("newnum").value.replace(/\D/g, "");
    if (d.length === 10 && d.startsWith("0")) d = "94" + d.slice(1);
    if (d.length < 9 || d.length > 15) return ($("newnum").style.borderColor = "var(--clay)");
    if (!people.some((p) => p.phone === d)) {
      const extra = { group: "Your numbers", kind: "farmer", name: "+" + d, place: "new", phone: d, tries: [] };
      people.push(extra); ls.set("sim_extra", people.filter((p) => p.group === "Your numbers"));
    }
    pick(d);
  };
}

function pick(phone) {
  me = people.find((p) => p.phone === phone) || me;
  ls.set("sim_phone", me.phone);
  $("h-av").textContent = me.name[0]; $("h-name").textContent = me.name; $("h-num").textContent = "+" + me.phone;
  $("chips").innerHTML = ["YES", "NO", "1", "2", "3", ...me.tries].map((t, i) => `<button data-i="${i}" title="${esc(t)}">${esc(t.length > 34 ? t.slice(0, 32) + "…" : t)}</button>`).join("");
  const all = ["YES", "NO", "1", "2", "3", ...me.tries];
  $("chips").querySelectorAll("button").forEach((b) => (b.onclick = () => { const t = all[b.dataset.i]; t.length <= 3 ? send(t) : ($("text").value = t, $("text").focus()); }));
  lastCount = -1; failNote = ""; renderPeople(); load(true);
}

const hm = (iso) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
function bubble(m) {
  const media = (local[me.phone] || []).find((x) => Math.abs(new Date(x.at) - new Date(m.at)) < 15000 && m.dir === "in" && m.media === x.kind);
  const body = media
    ? (media.kind === "image" ? `<img src="${media.url}" alt="photo">` : `<audio controls src="${media.url}"></audio>`)
    : m.media ? `<div class="tag">${m.media === "image" ? "📷 Photo" : "🎤 Voice note"}</div>` : "";
  return `<div class="b ${m.dir}">${body}${esc(m.text)}<time>${hm(m.at)}</time></div>`;
}

async function load(scroll) {
  if (!me) return;
  const r = await fetch("/api/sim/thread?phone=" + me.phone);
  const thread = r.ok ? await r.json() : [];
  if (thread.length === lastCount && !scroll) return;
  lastCount = thread.length;
  const box = $("msgs");
  const atEnd = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
  box.innerHTML = (thread.length ? `<div class="day">Messages go through the same Gemini pipeline as WhatsApp</div>` : `<div class="day">Say hello, or tap a sample message below</div>`)
    + thread.map(bubble).join("") + (waiting ? `<div class="typing">Govi is reading…</div>` : "")
    + (failNote ? `<div class="day err">${esc(failNote)}</div>` : "");
  if (scroll || atEnd) box.scrollTop = box.scrollHeight;
}

function showPreview() {
  if (!pending) { $("preview").hidden = true; return; }
  $("preview").hidden = false;
  $("preview").innerHTML = (pending.kind === "image" ? `<img src="${pending.url}">` : `🎤 Voice note ${pending.secs ? `(${pending.secs}s)` : ""}`)
    + ` <button class="btn small" id="unpick">Remove</button>`;
  $("unpick").onclick = () => { pending = null; $("file").value = ""; showPreview(); };
}

$("file").onchange = () => {
  const f = $("file").files[0];
  if (!f) return;
  if (f.size > 10 * 1024 * 1024) return alert("That file is too big (max 10 MB).");
  pending = { blob: f, name: f.name, kind: f.type.startsWith("audio") ? "audio" : "image", url: URL.createObjectURL(f) };
  showPreview();
};

// Voice: record, then convert to 16 kHz mono WAV, a format Gemini reads everywhere.
async function toWav(blob) {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const audio = await ctx.decodeAudioData(await blob.arrayBuffer());
  const rate = 16000, len = Math.ceil(audio.duration * rate);
  const off = new OfflineAudioContext(1, len, rate);
  const src = off.createBufferSource(); src.buffer = audio; src.connect(off.destination); src.start();
  const pcm = (await off.startRendering()).getChannelData(0);
  const buf = new DataView(new ArrayBuffer(44 + pcm.length * 2));
  const w = (o, s) => [...s].forEach((c, i) => buf.setUint8(o + i, c.charCodeAt(0)));
  w(0, "RIFF"); buf.setUint32(4, 36 + pcm.length * 2, true); w(8, "WAVE"); w(12, "fmt ");
  buf.setUint32(16, 16, true); buf.setUint16(20, 1, true); buf.setUint16(22, 1, true); buf.setUint32(24, rate, true);
  buf.setUint32(28, rate * 2, true); buf.setUint16(32, 2, true); buf.setUint16(34, 16, true); w(36, "data"); buf.setUint32(40, pcm.length * 2, true);
  pcm.forEach((v, i) => buf.setInt16(44 + i * 2, Math.max(-1, Math.min(1, v)) * 0x7fff, true));
  ctx.close();
  return { blob: new Blob([buf], { type: "audio/wav" }), secs: Math.round(audio.duration) };
}
$("mic").onclick = async () => {
  if (rec) { rec.stop(); return; }
  if (!navigator.mediaDevices?.getUserMedia) return alert("This browser cannot record. Attach an audio file instead.");
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const chunks = [];
    rec = new MediaRecorder(stream);
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      $("mic").classList.remove("rec"); $("mic").textContent = "🎤"; rec = null;
      const raw = new Blob(chunks, { type: chunks[0]?.type || "audio/webm" });
      let out = { blob: raw, secs: 0 };
      try { out = await toWav(raw); } catch {}
      pending = { blob: out.blob, name: "voice.wav", kind: "audio", url: URL.createObjectURL(out.blob), secs: out.secs };
      showPreview();
    };
    rec.start(); $("mic").classList.add("rec"); $("mic").textContent = "■";
  } catch { alert("Microphone permission was refused. Attach an audio file instead."); }
};

async function send(textArg) {
  const text = (textArg ?? $("text").value).trim();
  if (!text && !pending) return;
  const fd = new FormData();
  if (text) fd.append("text", text);
  if (pending) {
    fd.append("file", pending.blob, pending.name);
    (local[me.phone] ||= []).push({ at: new Date().toISOString(), url: pending.url, kind: pending.kind });
  }
  fd.append("sender", me.phone); fd.append("via", "sim");
  $("text").value = ""; pending = null; $("file").value = ""; showPreview();
  waiting = true; failNote = ""; $("send").disabled = true;
  setTimeout(() => load(true), 150);
  try {
    const r = await fetch("/intake", { method: "POST", body: fd });
    if (!r.ok) {
      const e = await r.json().catch(() => ({}));
      failNote = e.detail || `Could not send (error ${r.status}). Try again.`;
    }
  } catch {
    failNote = "No connection to Govi. Check your internet and try again.";
  } finally {
    waiting = false; $("send").disabled = false; lastCount = -1; await load(true);
  }
}
$("send").onclick = () => send();
$("text").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } });

fetch("/api/health").then((r) => r.json()).then((h) => {
  $("mode").textContent = h.gemini ? "Gemini live" : "Demo mode · text only";
  $("mode").className = "badge" + (h.gemini ? " live" : "");
});
renderPeople(); pick(me.phone);
setInterval(() => load(false), 3000);
