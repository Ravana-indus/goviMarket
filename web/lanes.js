// Transport rates an agent sets or confirms after calling the bus stand, station or farmers.
// Used by the agent page and the console; `call(path, opts)` adds that page's PIN or cookie.
const LANE_MODE = { night_bus: "🚌 Night bus", train_parcel: "🚆 Train parcel", sl_post: "📮 SL Post", lorry: "🚚 Shared lorry" };

async function laneEditor(el, call, who = "") {
  const e = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const rows = (await call("/api/agent/lanes")).map((r) => ({ ...r, lkr_per_kg: r.now_lkr_per_kg }));
  const when = (iso) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  const field = (r, f, label) => `<label class="lane-f"><span>${label}</span><input type="number" min="0" step="any" inputmode="decimal" data-f="${f}" value="${r[f]}"></label>`;
  el.innerHTML = rows.map((r, i) => `<div class="lane-row" data-i="${i}">
      <div class="lane-h"><b>${e(r.origin)} → ${e(r.dest)}</b> <span class="small muted">${LANE_MODE[r.mode] || e(r.mode)} ${e(r.departs)}</span></div>
      <div class="lane-fs">${field(r, "lkr_per_kg", "Rs/kg")}${field(r, "min_charge_lkr", "Minimum Rs")}${field(r, "handling_lkr", "Handling Rs")}${r.door_delivery ? "" : field(r, "pickup_lkr", "City pickup Rs")}</div>
      <div class="small muted lane-src">${r.checked ? `${r.checked.confirmed ? "Confirmed" : "Set"} by ${e(r.checked.who)} on ${when(r.checked.at)}` : "Never checked: estimate"}${r.reports ? ` · ${r.reports} seller report${r.reports === 1 ? "" : "s"}` : ""} · 20 kg costs about Rs ${Math.round(laneCost(r, 20) / 20)}/kg</div>
      <div class="lane-acts"><button class="btn small" data-a="confirm">Still right</button><button class="btn small primary" data-a="save">Save change</button><span class="small lane-msg"></span></div>
    </div>`).join("") || `<div class="empty">No routes.</div>`;
  el.querySelectorAll(".lane-row").forEach((row) => row.querySelectorAll("button").forEach((b) => (b.onclick = async () => {
    const r = rows[+row.dataset.i], body = { key: r.key, confirmed: b.dataset.a === "confirm", who };
    for (const f of ["lkr_per_kg", "min_charge_lkr", "handling_lkr", "pickup_lkr"]) {
      const inp = row.querySelector(`[data-f="${f}"]`);
      body[f] = b.dataset.a === "confirm" || !inp ? r[f] : Number(inp.value);
    }
    if (r.door_delivery) body.pickup_lkr = null;
    const msg = row.querySelector(".lane-msg");
    b.disabled = true;
    try { await call("/api/agent/lanes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      await laneEditor(el, call, who); }
    catch (err) { msg.textContent = err.message; b.disabled = false; }
  })));
}

function laneCost(r, kg) {
  return Math.max(r.min_charge_lkr, r.now_lkr_per_kg * kg) + r.handling_lkr + (r.door_delivery ? 0 : r.pickup_lkr);
}
