// Transport rates an agent sets or confirms after calling the bus stand, station or farmers.
// Used by the agent page and the console; `call(path, opts)` adds that page's PIN or cookie.
const LANE_MODE = { night_bus: "🚌 Night bus", train_parcel: "🚆 Train parcel", sl_post: "📮 SL Post", lorry: "🚚 Shared lorry" };

async function laneEditor(el, call, who = "") {
  const e = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const rows = (await call("/api/agent/lanes")).map((r) => ({ ...r, lkr_per_kg: r.now_lkr_per_kg }));
  const when = (iso) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  const field = (r, f, label, door = false) => door ? `<span class="lane-f lane-na" title="Delivered to the door">door</span>`
    : `<label class="lane-f"><span>${label}</span><input type="number" min="0" step="any" inputmode="decimal" data-f="${f}" value="${r[f] ?? ""}" aria-label="${e(r.origin)} to ${e(r.dest)}: ${label}"></label>`;
  const src = (r) => r.checked
    ? `<span class="chip farmer">${r.checked.confirmed ? "Confirmed" : "Set"} ${when(r.checked.at)}</span> <span>by ${e(r.checked.who)}</span>`
    : `<span class="chip warn">Estimate</span> <span>never checked</span>`;
  el.innerHTML = rows.length ? `<div class="lanes-t">
    <div class="lane-head" aria-hidden="true"><span>Route</span><span>Rs/kg</span><span>Minimum Rs</span><span>Handling Rs</span><span>City pickup Rs</span><span></span></div>
    ${rows.map((r, i) => `<div class="lane-row" data-i="${i}">
      <div class="lane-h"><b>${e(r.origin)} → ${e(r.dest)}</b><span class="lane-mode">${LANE_MODE[r.mode] || e(r.mode)} · ${e(r.departs)}</span>
        <span class="lane-src">${src(r)}${r.reports ? ` <span>· ${r.reports} seller report${r.reports === 1 ? "" : "s"}</span>` : ""} <span class="num">· 20 kg ≈ Rs ${Math.round(laneCost(r, 20) / 20)}/kg</span></span></div>
      ${field(r, "lkr_per_kg", "Rs/kg")}${field(r, "min_charge_lkr", "Minimum Rs")}${field(r, "handling_lkr", "Handling Rs")}${field(r, "pickup_lkr", "Pickup Rs", r.door_delivery)}
      <div class="lane-acts"><button class="btn small" data-a="confirm">Still right</button><button class="btn small primary" data-a="save">Save change</button><span class="small lane-msg" role="status"></span></div>
    </div>`).join("")}</div>` : `<div class="empty">No routes.</div>`;
  el.querySelectorAll(".lane-f input").forEach((inp) => (inp.oninput = () => {
    const r = rows[+inp.closest(".lane-row").dataset.i];
    inp.classList.toggle("changed", Number(inp.value) !== Number(r[inp.dataset.f]));
    inp.closest(".lane-row").classList.toggle("dirty", !!inp.closest(".lane-row").querySelector("input.changed"));
  }));
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
