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
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

function statusChip(m) {
  if (m.status === "confirmed") return `<span class="chip farmer">confirmed</span>`;
  const waiting = [!m.farmer_ok && "farmer", !m.buyer_ok && "buyer"].filter(Boolean).join(" + ");
  return `<span class="chip reporter" title="waiting for YES">waiting: ${waiting}</span>`;
}

function empty(cols, text) { return `<tr><td colspan="${cols}" class="empty">${text}</td></tr>`; }

function renderPlan(plan) {
  const i = plan.impact || {};
  $("k-kg").textContent = kg(i.kg_matched || 0);
  $("k-matches").textContent = `${plan.matches.length} matches`;
  $("k-farmer").textContent = rs(i.farmer_extra_lkr || 0);
  $("k-buyer").textContent = rs(i.buyer_saved_lkr || 0);
  $("k-surplus").textContent = kg(i.surplus_kg || 0);
  $("k-transport").textContent = rs(i.transport_saved_lkr || 0);
  const ships = plan.shipments || [];
  $("ship-count").textContent = ships.length ? `${ships.filter((x) => x.status === "delivered").length}/${ships.length} delivered` : "";
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
    const action = x.status === "delivered" ? `<span class="chip farmer">delivered</span>`
      : x.status === "planned" && waiting.length
        ? `<span class="chip reporter" title="${esc(waiting.map((m) => m.farmer + " / " + m.buyer).join(", "))}">waiting for YES (${waiting.length})</span>`
        : `<button class="btn small" data-advance="${x.id}">${x.status === "planned" ? "Book" : "Next: " + STEP_NAME[STEPS[at + 1]]} →</button>`;
    return `<div class="ship">
      <div class="row"><span class="mode">${MODE[x.lane.mode] || x.lane.mode}</span>
        <span>${esc(x.origin)} → ${esc(x.dest)} · ${fmtDate(x.ship_on)} ${x.lane.departs}</span>
        <span class="chip">${kg(x.total_kg)} · ${x.farmers.length} farmer${x.farmers.length > 1 ? "s" : ""} → ${x.buyers.length} buyer${x.buyers.length > 1 ? "s" : ""}</span>
        ${x.ref ? `<span class="chip" title="carrier booking reference (demo)">${esc(x.ref)}</span>` : ""}
        <span style="margin-left:auto">${action}</span></div>
      <ol class="steps">${steps}</ol>
      <div class="loads">${bars}</div>
      <div class="cost"><span>Drop-off: <b>${esc(x.lane.pickup || x.origin)}</b></span>
        <span>Cost: <b>${rs(x.cost_lkr)}</b> (avg Rs ${x.lkr_per_kg}/kg, est.)</span>
        ${x.saved_lkr > 0 ? `<span class="up">Bundling saved ${rs(x.saved_lkr)} vs ${rs(x.solo_cost_lkr)} separately</span>` : ""}
        ${x.lane.door_delivery ? "<span>Door delivery, no Colombo pickup</span>" : ""}</div></div>`;
  }).join("") : `<div class="empty">Run matching to plan shipments.</div>`;
  document.querySelectorAll("[data-advance]").forEach((b) => (b.onclick = () => busy(b, async () => {
    await api(`/shipments/${b.dataset.advance}/advance`, { method: "POST" }); await refresh();
  })));
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
    ? plan.surplus.map((l) => `<tr><td>${esc(l.farmer)}<div class="small muted">${esc(l.location)}</div></td><td>${esc(l.crop)}</td><td class="num">${kg(l.remaining_kg)}</td></tr>`).join("")
    : empty(3, "Nothing left over.");
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

async function refresh() {
  const [s, plan] = await Promise.all([api("/state"), api("/api/plan")]);
  renderState(s, plan); renderPlan(plan); loadReports();
  $("plan-note").textContent = plan.matches.length ? "from last matching run" : "";
}

async function busy(btn, fn) { btn.disabled = true; try { await fn(); } catch (e) { alert(e.message); } finally { btn.disabled = false; } }

$("run").onclick = (e) => busy(e.target, async () => { await api("/plan", { method: "POST" }); await refresh(); });
$("advance-all").onclick = (e) => busy(e.target, async () => { await api("/demo/advance-all", { method: "POST" }); await refresh(); });
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

api("/healthz").then((h) => {
  $("mode").textContent = h.gemini ? "Gemini live" : "Demo mode · no Gemini key";
  $("mode").className = "badge" + (h.gemini ? " live" : "");
  $("sent-note").textContent = h.gemini ? "written by the Gemini agent" : "templates (demo mode)";
  $("inbox-note").textContent = h.gemini ? "what Gemini understood" : "keyword parser (demo mode)";
});
refresh();
loadForecast();
setInterval(refresh, 5000);
setInterval(loadForecast, 30000);
