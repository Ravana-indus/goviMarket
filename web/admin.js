const $ = (id) => document.getElementById(id);
const rs = (n) => "Rs " + Math.round(n).toLocaleString("en-LK");
const kg = (n) => Math.round(n).toLocaleString("en-LK") + " kg";
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const MODE = { night_bus: "🚌 Night bus", train_parcel: "🚆 Train parcel", sl_post: "📮 SL Post", lorry: "🚚 Shared lorry" };
const STEPS = ["planned", "booked", "loaded", "in_transit", "arrived", "delivered"];
const STEP_NAME = { planned: "Planned", booked: "Booked", loaded: "Loaded", in_transit: "In transit", arrived: "Arrived", delivered: "Delivered" };
const hm = (iso) => new Date(iso).toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit" });
const fmtDate = (d) => new Date(d + "T00:00").toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (r.status === 401) { location.href = "/login?next=/admin" + location.hash; throw new Error("signed out"); }
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `${r.status} ${r.statusText || "error"} on ${path}`);
  }
  return r.json();
}

function statusChip(m) {
  const note = m.note ? ` <span class="chip warn" title="${esc(m.note)}">${esc(m.note.replace("rescue: ", "rescue · "))}</span>` : "";
  if (m.status === "confirmed") return `<span class="chip farmer">confirmed</span>${note}`;
  const waiting = [!m.farmer_ok && "farmer", !m.buyer_ok && "buyer"].filter(Boolean).join(" + ");
  return `<span class="chip reporter" title="waiting for YES">waiting: ${waiting}</span>${note}`;
}

function empty(cols, text) { return `<tr><td colspan="${cols}" class="empty">${text}</td></tr>`; }

function renderPlan(plan) {
  const i = plan.impact || {};
  $("k-kg").textContent = kg(i.kg_matched || 0);
  $("k-matches").textContent = `${plan.matches.length} matches`;
  $("k-farmer").textContent = rs(i.farmer_extra_lkr || 0);
  $("k-buyer").textContent = rs(i.buyer_saved_lkr || 0);
  $("k-surplus").textContent = kg(i.surplus_kg || 0);
  $("rescued").textContent = i.surplus_rescued_kg ? `${kg(i.surplus_rescued_kg)} sent to processors` : "";
  $("k-transport").textContent = rs(i.transport_saved_lkr || 0);
  const ships = plan.shipments || [];
  const resc = ships.filter((x) => x.status === "missed");
  $("ship-count").textContent = (ships.length ? `${ships.filter((x) => x.status === "delivered").length}/${ships.length - resc.length} delivered` : "")
    + (resc.length ? ` · ${resc.length} missed, all rescued · Govi covered ${rs(i.rescue_cost_lkr || 0)}` : "");
  $("shipments").innerHTML = ships.length ? ships.map((x) => {
    const loads = plan.matches.filter((m) => x.match_ids.includes(m.id));
    const bars = loads.map((m) => `<span style="flex:${m.qty_kg}" title="${esc(m.farmer)} → ${esc(m.buyer)}: ${kg(m.qty_kg)} ${esc(m.crop)}">${esc(m.farmer)} ${Math.round(m.qty_kg)}</span>`).join("");
    const waiting = loads.filter((m) => m.status !== "confirmed");
    const at = STEPS.indexOf(x.status);
    const steps = STEPS.slice(1).map((st, i) => {
      const done = at >= i + 1, now = at === i + 1;
      const ev = (x.events || []).find((e) => e.status === st);
      const when = (x.schedule || {})[st];
      return `<li class="${done ? "done" : ""} ${now ? "now" : ""}"><span class="dot"></span><b>${STEP_NAME[st]}</b>
        <small>${when ? hm(when) : ""}${ev ? " ✓" : ""}</small></li>`;
    }).join("");
    const canMiss = x.status === "booked" || x.status === "loaded";
    const backup = "backup" in x ? (x.backup ? `<span class="chip" title="if this departure is missed">backup: ${esc(x.backup)}</span>`
      : `<span class="chip warn" title="no later transport arrives in time; a miss means other farmers or a wholesale backup buy">no later transport</span>`) : "";
    const miss = canMiss ? `<button class="btn small miss" data-miss="${x.id}" title="Demo: the load did not make this departure">Missed ✕</button>` : "";
    const action = x.status === "missed" ? `<span class="chip warn">missed · ${esc(x.rescue.action || "")}</span>`
      : x.status === "delivered" ? `<span class="chip farmer">delivered</span>`
      : x.status === "planned" && waiting.length
        ? `<span class="chip reporter" title="${esc(waiting.map((m) => m.farmer + " / " + m.buyer).join(", "))}">waiting for YES (${waiting.length})</span>`
        : `<button class="btn small" data-advance="${x.id}">${x.status === "planned" ? "Book" : "Next: " + STEP_NAME[STEPS[at + 1]]} →</button>`;
    return `<div class="ship">
      <div class="row"><span class="mode">${MODE[x.lane.mode] || x.lane.mode}</span>
        <span>${esc(x.origin)} → ${esc(x.dest)} · ${fmtDate(x.ship_on)} ${x.lane.departs}</span>
        <span class="chip">${kg(x.total_kg)} · ${x.farmers.length} farmer${x.farmers.length > 1 ? "s" : ""} → ${x.buyers.length} buyer${x.buyers.length > 1 ? "s" : ""}</span>
        ${x.ref ? `<span class="chip" title="carrier booking reference (demo)">${esc(x.ref)}</span>` : ""}
        ${backup}<span style="margin-left:auto;display:flex;gap:6px">${miss}${action}</span></div>
      ${x.status === "missed" ? `<div class="rescue"><b>Missed the ${esc(x.rescue.missed)}.</b> ${esc(x.rescue.summary)}</div>` : ""}
      <ol class="steps">${steps}</ol>
      <div class="loads">${bars}</div>
      <div class="cost"><span>Drop-off: <b>${esc(x.lane.pickup || x.origin)}</b></span>
        <span>Cost: <b>${rs(x.cost_lkr)}</b> (avg Rs ${x.lkr_per_kg}/kg, est.)</span>
        ${x.saved_lkr > 0 ? `<span class="up">Bundling saved ${rs(x.saved_lkr)} vs ${rs(x.solo_cost_lkr)} separately</span>` : ""}
        ${x.lane.door_delivery ? "<span>Door delivery, no Colombo pickup</span>" : ""}</div></div>`;
  }).join("") : `<div class="empty">Run matching to plan shipments.</div>`;
  document.querySelectorAll("[data-miss]").forEach((b) => (b.onclick = () => busy(b, async () => {
    await api(`/shipments/${b.dataset.miss}/missed`, { method: "POST" }); await refresh();
  })));
  document.querySelectorAll("[data-advance]").forEach((b) => (b.onclick = () => busy(b, async () => {
    await api(`/shipments/${b.dataset.advance}/advance`, { method: "POST" }); await refresh();
  })));
  renderSwaps(plan.swaps || []);
  $("matches").innerHTML = plan.matches.length ? plan.matches.map((m) => {
    const shared = m.transport_lkr_per_kg < m.solo_transport_lkr_per_kg;
    const lane = m.lane
      ? `<div class="lane">${MODE[m.lane.mode] || m.lane.mode} · ${esc(m.lane.origin)} ${m.lane.departs} · Rs ${m.transport_lkr_per_kg}/kg${shared ? ` <span class="up">bundled</span> <s>${m.solo_transport_lkr_per_kg}</s>` : ""}${m.lane.source.startsWith("ESTIMATE") ? " · est." : ""}</div>`
      : `<div class="lane">Same town · no transport</div>`;
    const up = m.farmer_gets_lkr_per_kg - m.collector_pays_lkr_per_kg;
    const down = m.market_retail_lkr_per_kg - m.buyer_pays_lkr_per_kg;
    return `<tr>
      <td><div class="route">${esc(m.farmer)} <span class="arrow">→</span> ${esc(m.buyer)} ${statusChip(m)}</div>${lane}</td>
      <td>${esc(m.crop)}</td><td class="num">${kg(m.qty_kg)}</td>
      <td class="num">${rs(m.farmer_gets_lkr_per_kg)}<div class="delta up">+${rs(up)} vs collector</div></td>
      <td class="num">${rs(m.buyer_pays_lkr_per_kg)}<div class="delta muted">−${rs(down)} vs retail</div></td></tr>`;
  }).join("") : empty(5, "No matches yet. Load the demo morning or send messages, then run matching.");
  $("surplus").innerHTML = plan.surplus.length
    ? plan.surplus.map((l) => {
      const o = l.offer;
      const st = !o ? `<span class="muted small">not yet</span>`
        : o.status === "open" ? `<div class="small">${o.options.map((q) => `<button class="btn small" data-offer="${o.id}" data-n="${q.n}" title="Simulate the farmer replying ${q.n}: ${esc(q.text)}">${q.n} · ${q.kind === "processor" ? "Processor Rs " + q.net_lkr_per_kg : q.kind === "cold_store" ? "Cold store" : "Keep"}</button>`).join(" ")}<div class="muted">sent, waiting for the farmer's reply</div></div>`
        : `<span class="chip farmer" title="${esc(o.choice.text)}">${esc(o.choice.kind.replace("_", " "))}</span>`;
      return `<tr><td>${esc(l.farmer)}<div class="small muted">${esc(l.location)}</div></td><td>${esc(l.crop)}</td><td class="num">${kg(l.remaining_kg)}</td><td>${st}</td></tr>`;
    }).join("")
    : empty(4, "Nothing left over.");
  document.querySelectorAll("[data-offer]").forEach((b) => (b.onclick = () => busy(b, async () => {
    await api(`/api/offers/${b.dataset.offer}/accept/${b.dataset.n}`, { method: "POST" }); await refresh();
  })));
}

function renderState(s, plan) {
  const matchedBy = {};
  for (const m of plan.matches) matchedBy[m.listing_id] = (matchedBy[m.listing_id] || 0) + m.qty_kg;
  $("supply-n").textContent = s.listings.length;
  $("demand-n").textContent = s.orders.length;
  $("supply").innerHTML = s.listings.length ? s.listings.map((l) => {
    const pct = Math.round(((matchedBy[l.id] || 0) / l.qty_kg) * 100);
    return `<tr><td>${esc(l.farmer)}<div class="small muted">${esc(l.location)}</div></td><td>${esc(l.crop)}</td>
      <td class="num">${kg(l.qty_kg)}<div class="bar" title="${pct}% matched"><span style="width:${pct}%"></span></div></td><td class="small">${fmtDate(l.ready_on)}</td></tr>`;
  }).join("") : empty(4, "No harvest listed yet.");
  $("demand").innerHTML = s.orders.length ? s.orders.map((o) =>
    `<tr><td>${esc(o.buyer)}<div class="small muted">${esc(o.location)}</div></td><td>${esc(o.crop)}</td><td class="num">${kg(o.qty_kg)}</td><td class="small">${fmtDate(o.needed_by)}</td></tr>`
  ).join("") : empty(4, "No orders yet.");
  const prices = Object.values(s.prices);
  $("prices").innerHTML = prices.length ? prices.map((p) =>
    `<tr><td>${esc(p.crop)}<div class="small muted" title="${esc(p.source)}">${p.source?.startsWith("PLACEHOLDER") ? "placeholder" : "reported"}</div></td>
     <td class="num">${rs(p.collector)}</td><td class="num">${rs(p.retail)}</td><td class="num up">${rs(fair(p))}</td></tr>`
  ).join("") : empty(4, "No prices.");
  $("inbox").innerHTML = s.inbox.length ? [...s.inbox].reverse().map((m) => {
    const p = m.parsed;
    const items = p.items.map((it) => `<span class="chip">${esc(it.crop)} ${it.price_lkr_per_kg ? "Rs " + it.price_lkr_per_kg + " " + (it.price_kind || "") : kg(it.qty_kg)}</span>`).join("");
    const unclear = p.unclear.map((u) => `<span class="chip warn">? ${esc(u)}</span>`).join("");
    return `<div class="msg">
      <div class="meta"><span class="chip ${p.role}">${p.role}</span><span>${esc(p.sender_name || m.sender)}</span>
        ${p.location ? `<span>· ${esc(p.location)}</span>` : ""}<span>· ${p.language}</span>
        <span style="margin-left:auto" title="confidence ${p.confidence}"><span class="conf"><span style="width:${p.confidence * 100}%"></span></span></span></div>
      <div>${esc(p.summary_in_sender_language)}</div>
      <div class="items">${items}${unclear}</div></div>`;
  }).join("") : `<div class="empty">Messages from WhatsApp and the web app appear here.</div>`;
  $("outbox").innerHTML = s.outbox.length ? [...s.outbox].reverse().map((o) =>
    `<div class="msg"><div class="meta"><span class="chip">to ${esc(o.to)}</span></div><div style="white-space:pre-line">${esc(o.body)}</div></div>`
  ).join("") : `<div class="empty">Match messages to farmers and buyers appear here.</div>`;
}

// Mirrors app/pricing.py split() with zero transport, for display only.
const BUYER_DISCOUNT_SHARE = 0.25, GOVI_FEE = 0.05;
function fair(p) { const buyer = p.retail - BUYER_DISCOUNT_SHARE * (p.retail - p.collector); return buyer * (1 - GOVI_FEE); }

function spark(r) {
  const W = 180, H = 44, pts = r.history.map((h) => h.collector);
  const all = [...pts, r.low, r.high], min = Math.min(...all), max = Math.max(...all);
  const n = pts.length + 7, x = (i) => (i / (n - 1)) * W, y = (v) => H - 4 - ((v - min) / (max - min || 1)) * (H - 8);
  const hist = pts.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const last = pts.length - 1, end = n - 1;
  const band = `M${x(last)},${y(pts[last])} L${x(end)},${y(r.high)} L${x(end)},${y(r.low)} Z`;
  return `<svg class="spark ${r.signal}" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(r.crop)} price trend">
    <path class="band" d="${band}"/><path class="hist" d="${hist}"/>
    <path class="fut" d="M${x(last)},${y(pts[last])} L${x(end)},${y(r.collector_next_week)}"/></svg>`;
}

async function loadForecast() {
  const f = await api("/api/forecast");
  $("fc-summary").textContent = f.summary;
  $("fc-note").textContent = f.crops.some((c) => c.source === "synthetic") ? "next 7 days · demo price history" : "next 7 days";
  $("forecast").innerHTML = f.crops.map((r) => {
    const tot = r.supply_kg + r.demand_kg || 1;
    return `<tr><td style="text-transform:capitalize">${esc(r.crop)}<div><span class="chip ${r.signal === "rising" ? "warn" : r.signal === "falling" ? "farmer" : ""}">${r.signal} ${r.change_pct > 0 ? "+" : ""}${r.change_pct}%</span></div></td>
      <td>${spark(r)}</td>
      <td class="num">${rs(r.collector_next_week)}<div class="small muted">range ${rs(r.low)}–${rs(r.high)} · now ${rs(r.collector_now)}</div></td>
      <td class="small">${kg(r.supply_kg)} supply · ${kg(r.demand_kg)} demand<div class="sd"><span class="s" style="flex:${r.supply_kg}"></span><span class="d" style="flex:${r.demand_kg}"></span></div></td>
      <td class="small">${esc(r.farmer_advice)}</td></tr>`;
  }).join("");
}

async function loadReports() {
  const rows = await api("/api/agent/reports?limit=15");
  const waiting = rows.filter((r) => r.flagged).length;
  flagged = waiting;
  $("rep-wait").textContent = waiting ? `${waiting} to check` : "all live";
  $("reports").innerHTML = rows.length ? rows.map((r) => `<tr>
    <td>${esc(r.crop)}</td><td class="small">${esc(r.kind)}</td><td class="num">${rs(r.lkr_per_kg)}</td>
    <td class="small">${esc(r.market)}</td><td class="small">${esc(r.reporter)}</td>
    <td class="small muted">${new Date(r.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</td>
    <td>${r.flagged ? `<span class="chip warn">big jump</span> <button class="btn small" data-rep="${r.id}" data-v="approve">Approve</button> <button class="btn small" data-rep="${r.id}" data-v="reject">Reject</button>` : `<span class="chip farmer">live</span>`}</td>
  </tr>`).join("") : empty(7, "No agent reports yet. Open the agent app to send today's prices.");
  $("reports").querySelectorAll("[data-rep]").forEach((b) => (b.onclick = () =>
    busy(b, async () => { await api(`/api/agent/reports/${b.dataset.rep}/${b.dataset.v}`, { method: "POST" }); refresh(); })));
}

const SWAP_STATE = { proposed: ["reporter", "waiting for YES"], done: ["farmer", "switched"],
  declined: ["", "kept as agreed (someone said NO)"], expired: ["warn", "too late, kept as agreed"] };
function renderSwaps(swaps) {
  $("swaps-card").hidden = !swaps.length;
  $("swaps").innerHTML = swaps.map((s) => {
    const [cls, label] = SWAP_STATE[s.status] || ["", s.status];
    const people = s.parties.map((p) => p.ok || s.status !== "proposed"
      ? `<span class="chip ${p.ok ? "farmer" : ""}">${p.ok ? "✓" : "·"} ${esc(p.name)}</span>`
      : `<button class="btn small" data-swap="${s.id}" data-phone="${esc(p.phone)}" title="Demo: ${esc(p.name)} replies YES on WhatsApp">YES as ${esc(p.name)}</button>`).join(" ");
    return `<div class="ship">
      <div class="row"><b>${kg(s.kg)} ${esc(s.crop)}</b><span class="chip ${cls}">${label}</span>
        <span class="up">${esc(s.why)}</span>${s.farmer_gain_lkr_per_kg > 0 ? `<span class="chip farmer">farmer +Rs ${s.farmer_gain_lkr_per_kg}/kg</span>` : ""}</div>
      <div class="cost"><span>Now: ${s.before.map(esc).join("<br>")}</span><span class="arrow">→</span>
        <span>Better: <b>${s.after.map(esc).join("<br>")}</b></span></div>
      <div class="cost"><span>Transport ${rs(s.transport_before_lkr)} → ${rs(s.transport_after_lkr)}</span><span style="margin-left:auto">${people}</span></div>
    </div>`;
  }).join("");
  document.querySelectorAll("[data-swap]").forEach((b) => (b.onclick = () => busy(b, async () => {
    await api(`/api/swaps/${b.dataset.swap}/answer?phone=${encodeURIComponent(b.dataset.phone)}`, { method: "POST" }); await refresh();
  })));
}

// ---- console navigation
const PANES = ["overview", "matches", "shipments", "unsold", "market", "prices", "forecast", "analytics", "messages"];
function show(p) {
  if (!PANES.includes(p)) p = "overview";
  document.querySelectorAll(".pane").forEach((el) => el.classList.toggle("on", el.id === "p-" + p));
  document.querySelectorAll("#side a").forEach((a) => a.classList.toggle("on", a.dataset.p === p));
  window.scrollTo({ top: 0 });
}
window.addEventListener("hashchange", () => show(location.hash.slice(1)));
show(location.hash.slice(1));

let flagged = 0;
function renderAttention(s, plan) {
  const waiting = plan.matches.filter((m) => m.status === "proposed").length;
  const openOffers = plan.surplus.filter((l) => l.offer && l.offer.status === "open").length;
  const notAlerted = plan.surplus.filter((l) => !l.offer).length;
  const noBackup = (plan.shipments || []).filter((x) => x.backup === "").length;
  const unsure = s.inbox.filter((m) => m.parsed.confidence < 0.7).length;
  const swaps = (plan.swaps || []).filter((s) => s.status === "proposed").length;
  const items = [
    [swaps, "better routes found", "a cheaper farmer-to-buyer route; switches once everyone says YES", "matches"],
    [waiting, "matches waiting for a YES", "farmers or buyers still have to confirm on WhatsApp", "matches"],
    [notAlerted, "unsold loads not yet alerted", "send the farmer a processor or cold-store offer", "unsold"],
    [openOffers, "unsold offers waiting for a reply", "farmers reply 1, 2 or 3", "unsold"],
    [noBackup, "shipments with no later transport", "a miss means re-sourcing or a wholesale backup buy", "shipments"],
    [flagged, "agent prices to check", "big jumps stay off the board until approved", "prices"],
    [unsure, "messages the parser was unsure about", "check what was understood", "messages"],
  ].filter((x) => x[0] > 0);
  $("attn").innerHTML = items.length ? items.map(([n, what, why, p]) =>
    `<a href="#${p}"><span class="k" style="color:var(--clay)">${n}</span><span><b>${what}</b><div class="small muted">${why}</div></span><span class="go">→</span></a>`).join("")
    : `<div class="empty">Nothing needs you right now.</div>`;
  $("n-attn").textContent = items.length || "";
  $("n-wait").textContent = waiting || "";
  $("n-unsold").textContent = notAlerted + openOffers || "";
  $("n-flag").textContent = flagged || "";
  $("inbox-mini").innerHTML = $("inbox").innerHTML;
}

async function refresh() {
  const [s, plan] = await Promise.all([api("/state"), api("/api/plan")]);
  renderState(s, plan); renderPlan(plan); await loadReports(); renderAttention(s, plan);
  window.renderAnalytics?.(s, plan);
  $("plan-note").textContent = plan.matches.length ? "from last matching run" : "";
}

async function busy(btn, fn) { btn.disabled = true; try { await fn(); } catch (e) { alert(e.message); } finally { btn.disabled = false; } }

$("run").onclick = (e) => busy(e.target, async () => { await api("/plan", { method: "POST" }); await refresh(); });
$("sweep").onclick = (e) => busy(e.target, async () => { await api("/surplus/sweep", { method: "POST" }); await refresh(); });
$("advance-all").onclick = (e) => busy(e.target, async () => { await api("/demo/advance-all", { method: "POST" }); await refresh(); });
$("clear").onclick = (e) => {
  if (!confirm("Delete every listing, order, deal, shipment and chat? Accounts stay.")) return;
  busy(e.target, async () => { await api("/demo/clear", { method: "POST" }); await refresh(); });
};
$("seed").onclick = (e) => busy(e.target, async () => { await api("/demo/seed", { method: "POST" }); await refresh(); await loadForecast(); });
$("sim-send").onclick = (e) => busy(e.target, async () => {
  const fd = new FormData();
  const text = $("sim-text").value.trim(), file = $("sim-file").files[0];
  if (!text && !file) return;
  if (text) fd.append("text", text);
  if (file) fd.append("file", file);
  fd.append("sender", $("sim-phone").value.trim() || "admin");
  const out = await api("/intake", { method: "POST", body: fd });
  $("sim-out").innerHTML = `Reply sent: <b>${esc(out.reply).replace(/\n/g, "<br>")}</b>`;
  $("sim-text").value = ""; $("sim-file").value = "";
  await refresh();
});

api("/api/health").then((h) => {
  $("logout").hidden = !h.admin_locked;
  $("mode").textContent = h.gemini ? "Gemini live" : "Demo mode · no Gemini key";
  $("mode").className = "badge" + (h.gemini ? " live" : "");
  $("sent-note").textContent = h.gemini ? "written by the Gemini agent" : "templates (demo mode)";
  $("inbox-note").textContent = h.gemini ? "what Gemini understood" : "keyword parser (demo mode)";
});
refresh();
loadForecast();
setInterval(refresh, 5000);
setInterval(loadForecast, 30000);
