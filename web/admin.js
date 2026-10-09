const $ = (id) => document.getElementById(id);
const rs = (n) => "Rs " + Math.round(n).toLocaleString("en-LK");
const kg = (n) => Math.round(n).toLocaleString("en-LK") + " kg";
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const MODE = { night_bus: "🚌 Night bus", train_parcel: "🚆 Train parcel", sl_post: "📮 SL Post", lorry: "🚚 Shared lorry" };
const fmtDate = (d) => new Date(d + "T00:00").toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

function empty(cols, text) { return `<tr><td colspan="${cols}" class="empty">${text}</td></tr>`; }

function renderPlan(plan) {
  const i = plan.impact || {};
  $("k-kg").textContent = kg(i.kg_matched || 0);
  $("k-matches").textContent = `${plan.matches.length} matches`;
  $("k-farmer").textContent = rs(i.farmer_extra_lkr || 0);
  $("k-buyer").textContent = rs(i.buyer_saved_lkr || 0);
  $("k-surplus").textContent = kg(i.surplus_kg || 0);
  $("matches").innerHTML = plan.matches.length ? plan.matches.map((m) => {
    const lane = m.lane
      ? `<div class="lane">${MODE[m.lane.mode] || m.lane.mode} · ${esc(m.lane.origin)} ${m.lane.departs} · ${m.lane.transit_hours}h · Rs ${m.transport_lkr_per_kg}/kg${m.lane.source.startsWith("ESTIMATE") ? " · est." : ""}</div>`
      : `<div class="lane">Same town · no transport</div>`;
    const up = m.farmer_gets_lkr_per_kg - m.collector_pays_lkr_per_kg;
    const down = m.market_retail_lkr_per_kg - m.buyer_pays_lkr_per_kg;
    return `<tr>
      <td><div class="route">${esc(m.farmer)} <span class="arrow">→</span> ${esc(m.buyer)}</div>${lane}</td>
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
}

// Mirrors app/pricing.py split() with zero transport, for display only.
const BUYER_DISCOUNT_SHARE = 0.25, GOVI_FEE = 0.05;
function fair(p) { const buyer = p.retail - BUYER_DISCOUNT_SHARE * (p.retail - p.collector); return buyer * (1 - GOVI_FEE); }

async function refresh() {
  const [s, plan] = await Promise.all([api("/state"), api("/api/plan")]);
  renderState(s, plan); renderPlan(plan);
  $("plan-note").textContent = plan.matches.length ? "from last matching run" : "";
}

async function busy(btn, fn) { btn.disabled = true; try { await fn(); } catch (e) { alert(e.message); } finally { btn.disabled = false; } }

$("run").onclick = (e) => busy(e.target, async () => { await api("/plan", { method: "POST" }); await refresh(); });
$("seed").onclick = (e) => busy(e.target, async () => { await api("/demo/seed", { method: "POST" }); await refresh(); });
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
});
refresh();
setInterval(refresh, 5000);
