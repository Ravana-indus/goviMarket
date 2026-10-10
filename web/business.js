const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const rs = (n) => "Rs " + Math.round(n).toLocaleString("en-LK");
const kg = (n) => Math.round(n).toLocaleString("en-LK") + " kg";
const STEPS = ["booked", "loaded", "in_transit", "arrived", "delivered"];
const STEP_NAME = { booked: "Booked", loaded: "Loaded", in_transit: "On the way", arrived: "Arrived", delivered: "Delivered" };
const TREND = { rising: "↑ rising", falling: "↓ easing", steady: "→ steady" };
const cname = (c) => GOVI.name(c, "en");
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};
let me = store.get("biz", null);
let cart = store.get("cart", {});
let catalogue = [];

async function api(path, opts) {
  const r = await fetch(path, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || r.statusText);
  return body;
}

function showSignin(show) {
  $("signin").hidden = !show;
  document.querySelectorAll(".pane").forEach((p) => (p.style.display = show ? "none" : ""));
  $("tabs").style.visibility = show ? "hidden" : "";
}
function signIn(b) {
  me = b; store.set("biz", b); showSignin(false); renderWho(); loadAll();
}
$("si-go").onclick = () => {
  const name = $("si-name").value.trim(), phone = $("si-phone").value.replace(/\D/g, "");
  if (!name || !phone) return;
  signIn({ name, phone, location: $("si-loc").value.trim() || "Colombo" });
};
$("pitch-ics").innerHTML = ["carrot", "tomato", "beans", "leeks", "red onion", "green chilli"].map((c) => GOVI.icon(c, 40)).join("");
$("si-demo").onclick = () => signIn({ name: "Mango Tree Cafe", phone: "94770000014", location: "Colombo" });
function renderWho() {
  $("who").innerHTML = me ? `<b>${esc(me.name)}</b>${esc(me.location)} · <a href="#" id="out">switch</a>` : "";
  if (me) $("out").onclick = (e) => { e.preventDefault(); store.set("biz", null); me = null; showSignin(true); };
}

document.querySelectorAll("#tabs button").forEach((b) => (b.onclick = () => {
  document.querySelectorAll("#tabs button").forEach((x) => x.classList.toggle("on", x === b));
  document.querySelectorAll(".pane").forEach((p) => p.classList.toggle("on", p.id === b.dataset.tab));
  if (b.dataset.tab === "orders") loadOrders();
  if (b.dataset.tab === "standing") loadStanding();
}));

function setQty(crop, v) {
  v = Math.max(0, Math.round(v));
  if (v) cart[crop] = v; else delete cart[crop];
  store.set("cart", cart); renderCatalogue(); renderCart();
}

function renderCatalogue() {
  $("catalogue").innerHTML = catalogue.map((p) => {
    const q = cart[p.crop] || 0, out = p.available_kg <= 0;
    const trend = p.signal ? `<span class="trend ${p.signal}" title="${esc(p.advice || "")}">${TREND[p.signal].split(" ")[0]} ${rs(p.next_week_price)} next week</span>` : "";
    return `<div class="card prod ${out ? "soldout" : ""} ${q ? "in" : ""}">
      <div class="head">${GOVI.icon(p.crop, 48)}<span class="name">${esc(cname(p.crop))}</span></div>
      <div class="pr"><div class="price num">${rs(p.price)}<small> /kg</small></div>${trend}</div>
      <div class="meta"><span class="up">Save ${p.saving_pct}% vs retail ${rs(p.retail)}</span>
        <span>${out ? "No stock right now; order and we'll find a farmer" : `${kg(p.available_kg)} from ${p.farmers} farmer${p.farmers > 1 ? "s" : ""} · ${esc(p.origins.join(", "))}`}</span></div>
      <div class="qty"><button data-c="${esc(p.crop)}" data-d="-10" aria-label="less">−</button>
        <input type="number" min="0" step="5" value="${q}" data-c="${esc(p.crop)}" aria-label="kg of ${esc(p.crop)}"><span class="unit">kg</span>
        <button data-c="${esc(p.crop)}" data-d="10" aria-label="more">+</button></div>
      <div class="adds">${[5, 10, 25].map((n) => `<button data-c="${esc(p.crop)}" data-d="${n}">+${n} kg</button>`).join("")}</div>
    </div>`;
  }).join("");
  document.querySelectorAll(".qty button, .adds button").forEach((b) => (b.onclick = () => setQty(b.dataset.c, (cart[b.dataset.c] || 0) + +b.dataset.d)));
  document.querySelectorAll(".qty input").forEach((i) => (i.onchange = () => setQty(i.dataset.c, +i.value || 0)));
}

function renderCart() {
  const lines = Object.entries(cart).map(([crop, q]) => ({ crop, q, p: catalogue.find((c) => c.crop === crop) })).filter((l) => l.p);
  const total = lines.reduce((s, l) => s + l.q * l.p.price, 0);
  const retail = lines.reduce((s, l) => s + l.q * l.p.retail, 0);
  $("lines").innerHTML = lines.length ? lines.map((l) => `<div class="line"><span>${esc(cname(l.crop))} · ${kg(l.q)}</span><span class="num">${rs(l.q * l.p.price)}</span></div>`).join("")
    : `<div class="muted small">Add produce from the list.</div>`;
  $("cart-n").textContent = lines.length ? `${lines.length} item${lines.length > 1 ? "s" : ""}` : "";
  $("total").textContent = rs(total);
  $("save").textContent = total ? `You save ${rs(retail - total)} vs retail` : "";
  $("place").disabled = !lines.length;
  $("mobilebar").classList.toggle("hidden", !lines.length);
  $("mb-text").textContent = `${lines.length} item${lines.length > 1 ? "s" : ""} · ${rs(total)}`;
  const d = $("needed").value ? new Date($("needed").value + "T00:00") : null;
  $("weekday").textContent = d ? `on ${d.toLocaleDateString("en-GB", { weekday: "long" })}s` : "";
}
$("needed").onchange = renderCart;
$("mobilebar").onclick = () => $("cart").scrollIntoView({ behavior: "smooth" });

$("place").onclick = async () => {
  const items = Object.entries(cart).map(([crop, qty_kg]) => ({ crop, qty_kg }));
  $("place").disabled = true;
  try {
    const out = await api("/api/orders", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone: me.phone, business: me.name, location: me.location, needed_by: $("needed").value,
        items, repeat_weekly: $("weekly").checked }) });
    const farmers = new Set(out.matches.map((m) => m.farmer)).size;
    $("placed").innerHTML = `<div class="card done"><b>Order placed.</b><div class="small">${kg(out.matched_kg)} of ${kg(out.ordered_kg)} matched with ${farmers} farmer${farmers === 1 ? "" : "s"} so far.
      We've asked them to confirm on WhatsApp; you'll get a message from us when it's booked.${$("weekly").checked ? " Saved as a weekly order." : ""}</div></div>`;
    cart = {}; store.set("cart", cart); $("weekly").checked = false;
    await loadCatalogue();
  } catch (e) { $("placed").innerHTML = `<div class="card done" style="border-color:var(--clay)">${esc(e.message)}</div>`; }
  finally { renderCart(); }
};

async function loadCatalogue() { catalogue = await api("/api/catalogue"); renderCatalogue(); renderCart(); }
async function loadOutlook() {
  const f = await api("/api/forecast");
  const rising = f.crops.filter((c) => c.signal === "rising").map((c) => c.crop);
  const cls = { rising: "trend rising", falling: "trend falling", steady: "trend steady" };
  $("outlook-chips").innerHTML = f.crops.filter((c) => c.signal && c.signal !== "steady").map((c) =>
    `<span class="${cls[c.signal]}">${TREND[c.signal].split(" ")[0]} ${esc(cname(c.crop))} ${c.change_pct > 0 ? "+" : ""}${Math.round(c.change_pct)}%</span>`).join("");
  $("outlook-text").textContent = rising.length ? `Rising crops cost more next week. A weekly order locks in today's supply.` : "Prices look steady next week.";
  $("outlook-src").textContent = /synthetic/i.test(f.summary || "") ? "Forecast from demo price history until HARTI data is loaded." : "";
}

async function loadOrders() {
  const d = await api("/api/track?phone=" + encodeURIComponent(me.phone));
  const rows = [...d.orders].sort((a, b) => b.needed_by.localeCompare(a.needed_by));
  $("order-list").innerHTML = rows.length ? rows.map((o) => {
    const ms = o.matches;
    const status = !ms.length ? "Finding farmers" : ms.every((m) => m.status === "confirmed") ? "Confirmed" : "Waiting for farmer YES";
    const ships = ms.filter((m) => m.shipment).map((m) => {
      const at = STEPS.indexOf(m.shipment.status);
      return `<div class="small muted">${kg(m.qty_kg)} from ${esc(m.farmer)} (${esc(m.shipment.origin)}) · ${esc(m.shipment.ref || "not booked yet")}</div>
        <div class="track">${STEPS.map((s, i) => `<span class="${i <= at ? "on" : ""}">${STEP_NAME[s]}</span>`).join("")}</div>`;
    }).join("");
    return `<div class="card ord"><div class="row"><span class="title" style="display:flex;gap:10px;align-items:center">${GOVI.icon(o.crop, 36)}${esc(cname(o.crop))} · ${kg(o.qty_kg)}</span>
      <span class="chip ${status === "Confirmed" ? "farmer" : "reporter"}">${status}</span></div>
      <div class="small muted">Deliver by ${new Date(o.needed_by + "T00:00").toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })} · ${kg(o.matched_kg)} matched · ${rs(ms[0]?.buyer_pays_lkr_per_kg || 0)}/kg</div>
      ${ships}<div><button class="btn small" data-re="${esc(o.crop)}" data-q="${o.qty_kg}">Reorder</button></div></div>`;
  }).join("") : `<div class="empty card">No orders yet.</div>`;
  document.querySelectorAll("[data-re]").forEach((b) => (b.onclick = () => {
    setQty(b.dataset.re, (cart[b.dataset.re] || 0) + +b.dataset.q);
    document.querySelector('[data-tab="shop"]').click();
  }));
}

async function loadStanding() {
  const rows = await api("/api/standing?phone=" + encodeURIComponent(me.phone));
  $("standing-list").innerHTML = rows.length ? rows.map((s) => `<div class="card ord">
      <div class="row"><span class="title">Every ${esc(s.weekday)}</span><button class="btn small primary" data-run="${s.id}">Create next week's order</button></div>
      <div class="small muted">${s.items.map((i) => `${esc(i.crop)} ${kg(i.qty_kg)}`).join(" · ")} · to ${esc(s.location)}</div>
      <div class="small muted">In production this runs automatically each week and messages you to confirm.</div></div>`).join("")
    : `<div class="empty card">No weekly orders. Tick "Repeat every week" when you place an order.</div>`;
  document.querySelectorAll("[data-run]").forEach((b) => (b.onclick = async () => {
    b.disabled = true; await api(`/api/standing/${b.dataset.run}/run`, { method: "POST" });
    document.querySelector('[data-tab="orders"]').click();
  }));
}

function loadAll() { loadCatalogue(); loadOutlook(); }

const d = new Date(); d.setDate(d.getDate() + 2);
$("needed").value = d.toISOString().slice(0, 10);
renderWho();
if (me) loadAll(); else showSignin(true);
