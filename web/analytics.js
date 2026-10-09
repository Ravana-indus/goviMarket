// Analytics tab: impact of the current plan, computed from the same data the console shows.
// Charts are plain HTML bars; every mark has a hover tooltip and every chart a table view.
(() => {
  const $ = (id) => document.getElementById(id);
  const rs = (n) => "Rs " + Math.round(n).toLocaleString("en-LK");
  const kg = (n) => Math.round(n).toLocaleString("en-LK") + " kg";
  const pct = (n) => (n >= 0 ? "+" : "") + Math.round(n * 100) + "%";
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const MODES = [["train_parcel", "Train", "--c1"], ["night_bus", "Night bus", "--c2"], ["lorry", "Lorry", "--c3"], ["sl_post", "SL Post", "--c4"]];
  const sum = (xs, f) => xs.reduce((a, x) => a + f(x), 0);
  const group = (xs, f) => xs.reduce((m, x) => ((m[f(x)] ||= []).push(x), m), {});

  // one floating tooltip for every [data-tip]
  const tip = $("tip");
  document.addEventListener("mousemove", (e) => {
    const t = e.target.closest("[data-tip]");
    if (!t) { tip.style.display = "none"; return; }
    tip.innerHTML = t.dataset.tip;
    tip.style.display = "block";
    const x = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8);
    tip.style.left = x + "px"; tip.style.top = e.clientY + 14 + "px";
  });

  const legend = (items) => `<div class="legend">${items.map(([name, v]) => `<span><i style="background:var(${v})"></i>${name}</span>`).join("")}</div>`;
  const table = (head, rows) => `<details class="tbl"><summary>Show as table</summary><div class="scroll-x"><table>
    <thead><tr>${head.map((h) => `<th>${h}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div></details>`;
  const tile = (label, value, hint, cls = "") => `<div class="card kpi"><div class="label">${label}</div><div class="value num ${cls}">${value}</div><div class="hint">${hint}</div></div>`;

  window.renderAnalytics = (s, plan) => {
    const all = plan.matches;
    const farm = all.filter((m) => m.listing_id !== "backup");
    const ships = plan.shipments || [];
    const empty = `<div class="empty">Load the demo morning or run matching to see analytics.</div>`;
    if (!farm.length) {
      ["a-farmer", "a-split", "a-routes", "a-funnel"].forEach((id) => ($(id).innerHTML = empty));
      $("a-hero").innerHTML = ""; $("a-top").innerHTML = ""; return;
    }

    // ---- hero numbers
    const collectorRs = sum(farm, (m) => m.collector_pays_lkr_per_kg * m.qty_kg);
    const extra = sum(farm, (m) => (m.farmer_gets_lkr_per_kg - m.collector_pays_lkr_per_kg) * m.qty_kg);
    const retailRs = sum(farm, (m) => m.market_retail_lkr_per_kg * m.qty_kg);
    const saved = sum(farm, (m) => (m.market_retail_lkr_per_kg - m.buyer_pays_lkr_per_kg) * m.qty_kg);
    const moved = sum(farm, (m) => m.qty_kg);
    const backupKg = sum(all.filter((m) => m.listing_id === "backup"), (m) => m.qty_kg);
    const solo = sum(farm, (m) => (m.solo_transport_lkr_per_kg || m.transport_lkr_per_kg) * m.qty_kg);
    const paid = sum(farm, (m) => m.transport_lkr_per_kg * m.qty_kg);
    const rerouted = ships.filter((x) => (x.events?.[0]?.note || "").startsWith("re-routed")).length;
    const missed = ships.filter((x) => x.status === "missed").length;
    const departures = ships.length - rerouted;
    const i = plan.impact || {};
    $("a-hero").innerHTML = [
      tile("Farmer income uplift", pct(extra / collectorRs), `${rs(extra)} more than village collectors pay`, "up"),
      tile("Buyer saving", Math.round((saved / retailRs) * 100) + "%", `${rs(saved)} below Colombo retail`),
      tile("Produce matched", kg(moved), `${new Set(farm.map((m) => m.farmer)).size} farmers → ${new Set(all.map((m) => m.buyer)).size} buyers${backupKg ? ` · plus ${kg(backupKg)} backup buy` : ""}`),
      tile("Transport saved by bundling", solo ? Math.round(((solo - paid) / solo) * 100) + "%" : "0%", `${rs(solo - paid)} vs every farmer shipping alone`, "up"),
      tile("Departures on time", departures ? Math.round(((departures - missed) / departures) * 100) + "%" : "–",
        missed ? `${missed} missed, every buyer still covered · Govi paid ${rs(i.rescue_cost_lkr || 0)}` : "no missed departures"),
      tile("Waste avoided", kg(i.surplus_rescued_kg || 0), `sent to processors · ${kg(i.surplus_kg || 0)} still unsold`),
    ].join("");

    // ---- farmer price per kg, by crop
    const crops = Object.entries(group(farm, (m) => m.crop)).map(([crop, ms]) => {
      const k = sum(ms, (m) => m.qty_kg);
      const avg = (f) => sum(ms, (m) => f(m) * m.qty_kg) / k;
      return { crop, kg: k, collector: avg((m) => m.collector_pays_lkr_per_kg), govi: avg((m) => m.farmer_gets_lkr_per_kg),
        transport: avg((m) => m.transport_lkr_per_kg), buyer: avg((m) => m.buyer_pays_lkr_per_kg), retail: avg((m) => m.market_retail_lkr_per_kg) };
    }).sort((a, b) => b.kg - a.kg);
    const maxF = Math.max(...crops.map((c) => Math.max(c.collector, c.govi)));
    $("a-farmer").innerHTML = legend([["Village collector", "--c0"], ["Govi, after transport", "--c1"]]) + crops.map((c) => `
      <div class="hrow"><span class="lbl">${esc(c.crop)}</span>
        <div class="track2">
          <div class="hb" style="width:${(c.collector / maxF) * 100}%;background:var(--c0)" data-tip="${esc(c.crop)} · village collector<br><b>${rs(c.collector)}/kg</b>"></div>
          <div class="hb" style="width:${(c.govi / maxF) * 100}%;background:var(--c1)" data-tip="${esc(c.crop)} · Govi after transport<br><b>${rs(c.govi)}/kg</b> (${pct(c.govi / c.collector - 1)})"></div>
        </div>
        <span class="val"><b class="up">${pct(c.govi / c.collector - 1)}</b></span></div>`).join("")
      + table(["Crop", "Collector Rs/kg", "Govi Rs/kg", "Uplift"], crops.map((c) => [esc(c.crop), Math.round(c.collector), Math.round(c.govi), pct(c.govi / c.collector - 1)]));

    // ---- where the retail rupee goes
    const maxR = Math.max(...crops.map((c) => c.retail));
    const PARTS = [["Farmer", "--c1", (c) => c.govi], ["Transport", "--c3", (c) => c.transport], ["Govi fee", "--c2", (c) => c.buyer - c.govi - c.transport], ["Buyer saves", "--c4", (c) => c.retail - c.buyer]];
    $("a-split").innerHTML = legend(PARTS.map(([n, v]) => [n, v])) + crops.map((c) => `
      <div class="hrow"><span class="lbl">${esc(c.crop)}</span>
        <div class="stack" style="width:${(c.retail / maxR) * 100}%">${PARTS.map(([n, v, f]) => {
          const val = Math.max(f(c), 0);
          return `<span style="flex:${val};background:var(${v})" data-tip="${esc(c.crop)} · ${n}<br><b>${rs(val)}/kg</b> (${Math.round((val / c.retail) * 100)}% of retail)"></span>`;
        }).join("")}</div>
        <span class="val">${rs(c.retail)}</span></div>`).join("")
      + `<div class="note">Bar length is the Colombo retail price. The farmer's share is what they get after transport.</div>`
      + table(["Crop", "Farmer", "Transport", "Govi fee", "Buyer saves", "Retail"], crops.map((c) => [esc(c.crop), ...PARTS.map(([, , f]) => Math.round(f(c))), Math.round(c.retail)]));

    // ---- kg by route and mode
    const lanes = farm.filter((m) => m.lane);
    const routes = Object.entries(group(lanes, (m) => `${m.lane.origin} → ${m.lane.dest}`))
      .map(([r, ms]) => ({ r, kg: sum(ms, (m) => m.qty_kg), by: group(ms, (m) => m.lane.mode) })).sort((a, b) => b.kg - a.kg);
    const maxK = Math.max(...routes.map((r) => r.kg));
    const used = MODES.filter(([m]) => lanes.some((x) => x.lane.mode === m));
    $("a-routes").innerHTML = legend(used.map(([, n, v]) => [n, v])) + routes.map((r) => `
      <div class="hrow"><span class="lbl" title="${esc(r.r)}">${esc(r.r)}</span>
        <div class="stack" style="width:${(r.kg / maxK) * 100}%">${used.filter(([m]) => r.by[m]).map(([m, n, v]) => {
          const k = sum(r.by[m], (x) => x.qty_kg);
          return `<span style="flex:${k};background:var(${v})" data-tip="${esc(r.r)} · ${n}<br><b>${kg(k)}</b>"></span>`;
        }).join("")}</div>
        <span class="val"><b>${kg(r.kg)}</b></span></div>`).join("")
      + table(["Route", ...used.map(([, n]) => n), "Total"], routes.map((r) => [esc(r.r), ...used.map(([m]) => Math.round(sum(r.by[m] || [], (x) => x.qty_kg))), Math.round(r.kg)]));

    // ---- harvest to delivery funnel
    const shipOf = Object.fromEntries(ships.map((x) => [x.id, x]));
    const onShip = (m, sts) => m.shipment_id && sts.includes(shipOf[m.shipment_id]?.status);
    const stages = [
      ["Harvest listed", sum(s.listings, (l) => l.qty_kg)],
      ["Matched to a buyer", sum(farm, (m) => m.qty_kg)],
      ["Confirmed by both", sum(farm.filter((m) => m.status === "confirmed"), (m) => m.qty_kg)],
      ["Booked on transport", sum(farm.filter((m) => onShip(m, ["booked", "loaded", "in_transit", "arrived", "delivered"])), (m) => m.qty_kg)],
      ["Delivered", sum(farm.filter((m) => onShip(m, ["delivered"])), (m) => m.qty_kg)],
    ];
    const top = stages[0][1] || 1;
    $("a-funnel").innerHTML = stages.map(([n, k]) => `
      <div class="hrow"><span class="lbl" style="text-transform:none">${n}</span>
        <div><div class="hb" style="width:${(k / top) * 100}%;background:var(--c1);height:18px" data-tip="${n}<br><b>${kg(k)}</b> (${Math.round((k / top) * 100)}% of listed)"></div></div>
        <span class="val"><b>${kg(k)}</b></span></div>`).join("")
      + `<div class="note">Listed kg left unmatched is the unsold produce offered to processors and cold stores.</div>`
      + table(["Stage", "Kg", "% of listed"], stages.map(([n, k]) => [n, Math.round(k), Math.round((k / top) * 100) + "%"]));

    // ---- top farmers
    const towns = Object.fromEntries(s.listings.map((l) => [l.farmer, l.location]));
    const farmers = Object.entries(group(farm, (m) => m.farmer)).map(([f, ms]) => {
      const e = sum(ms, (m) => (m.farmer_gets_lkr_per_kg - m.collector_pays_lkr_per_kg) * m.qty_kg);
      return { f, kg: sum(ms, (m) => m.qty_kg), extra: e, up: e / sum(ms, (m) => m.collector_pays_lkr_per_kg * m.qty_kg) };
    }).sort((a, b) => b.extra - a.extra).slice(0, 8);
    $("a-top").innerHTML = farmers.map((x) => `<tr><td>${esc(x.f)}</td><td class="small muted">${esc(towns[x.f] || "")}</td>
      <td class="num">${kg(x.kg)}</td><td class="num up">${rs(x.extra)}</td><td class="num">${pct(x.up)}</td></tr>`).join("");
  };
})();
