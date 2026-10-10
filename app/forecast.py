"""Next-week price and supply/demand outlook per crop.

The numbers come from code: a linear trend over the last two weeks of prices, nudged by how
much open demand there is against open supply. Gemini only writes the explanation.

Until real HARTI history is loaded, the price history is a SYNTHETIC series built around the
seed price, plus any prices reporters actually sent. Every response says which it is."""
from __future__ import annotations

import hashlib
import math
import os
from datetime import date, timedelta

from . import ai

from . import store
from .pricing import split

DAYS = 56


def _phase(crop: str) -> float:
    return int(hashlib.md5(crop.encode()).hexdigest(), 16) % 628 / 100


def history(crop: str, base: dict, today: date) -> list[dict]:
    """Daily collector and retail prices for the last DAYS days (synthetic unless reported)."""
    reported = {p["date"]: p for p in store.DB.all("prices") if p["crop"] == crop}
    out = []
    for i in range(DAYS, 0, -1):
        d = today - timedelta(days=i - 1)
        # Seasonal wave + a slow drift, ending at today's seed price.
        f = 1 + 0.12 * math.sin(2 * math.pi * (DAYS - i) / 30 + _phase(crop)) \
            - 0.12 * math.sin(2 * math.pi * (DAYS - 1) / 30 + _phase(crop)) + 0.002 * (i - 1) * (-1 if _phase(crop) > 3 else 1)
        row = {"date": d.isoformat(), "collector": round(base["collector"] * f, 1),
               "retail": round(base["retail"] * f, 1), "source": "synthetic"}
        r = reported.get(d.isoformat())
        if r and r["kind"] in ("collector", "retail"):
            row[r["kind"]] = r["lkr_per_kg"]
            row["source"] = "reported"
        out.append(row)
    return out


def _trend(ys: list[float]) -> tuple[float, float]:
    """Least-squares slope per day and residual standard deviation."""
    n = len(ys)
    xs = range(n)
    mx, my = (n - 1) / 2, sum(ys) / n
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    resid = [y - (my + slope * (x - mx)) for x, y in zip(xs, ys)]
    return slope, (sum(r * r for r in resid) / n) ** 0.5


def outlook(today: date | None = None) -> list[dict]:
    today = today or date.today()
    horizon = today + timedelta(days=7)
    supply, demand = {}, {}
    for l in store.listings():
        if l.remaining_kg > 0 and l.ready_on <= horizon:
            supply[l.crop] = supply.get(l.crop, 0) + l.remaining_kg
    for o in store.orders():
        if o.remaining_kg > 0 and o.needed_by <= horizon:
            demand[o.crop] = demand.get(o.crop, 0) + o.remaining_kg
    for s in store.DB.all("standing"):
        for it in s["items"]:
            demand[it["crop"]] = demand.get(it["crop"], 0) + it["qty_kg"]
    rows = []
    for crop, base in sorted(store.prices().items()):
        hist = history(crop, base, today)
        recent = [h["collector"] for h in hist[-14:]]
        slope, sd = _trend(recent)
        s, d = supply.get(crop, 0), demand.get(crop, 0)
        ratio = d / s if s else (2.0 if d else 1.0)
        pressure = max(-0.08, min(0.08, (ratio - 1) * 0.05))
        now = recent[-1]
        mid = now + slope * 7
        mid *= 1 + pressure
        band = max(sd * 1.5, now * 0.03)
        change = (mid - now) / now
        signal = "rising" if change > 0.03 else "falling" if change < -0.03 else "steady"
        future = {"collector": mid, "retail": base["retail"] * mid / base["collector"]}
        rows.append({
            "crop": crop, "history": hist[-28:], "source": "reported" if any(h["source"] == "reported" for h in hist) else "synthetic",
            "collector_now": round(now), "collector_next_week": round(mid),
            "low": round(mid - band), "high": round(mid + band), "change_pct": round(change * 100, 1),
            "buyer_price_now": split(base, 0)["buyer_pays"], "buyer_price_next_week": split(future, 0)["buyer_pays"],
            "supply_kg": round(s), "demand_kg": round(d), "demand_supply_ratio": round(ratio, 2),
            "signal": signal,
            "farmer_advice": ("Hold a few days if storage allows; prices are climbing." if signal == "rising"
                              else "Sell this week; prices are expected to ease." if signal == "falling"
                              else "Sell as normal."),
            "buyer_advice": ("Lock in a standing order now before prices rise." if signal == "rising"
                             else "Order as needed; prices are expected to ease." if signal == "falling"
                             else "Order as needed."),
        })
    return rows


def template(rows: list[dict]) -> str:
    movers = sorted(rows, key=lambda r: -abs(r["change_pct"]))[:3]
    parts = [f"{r['crop']} {r['signal']} ({r['change_pct']:+.0f}%, Rs {r['low']}-{r['high']} to farmers)" for r in movers]
    return "Next week: " + "; ".join(parts) + ". Synthetic history until HARTI data is loaded."


def explain(rows: list[dict], client=None) -> str:
    """Two or three plain sentences for the ops team. Gemini when a key is set, else a template."""
    from . import ai
    if client is None and not ai.enabled():
        return template(rows)
    from google import genai
    from google.genai import types
    try:
        return _explain(rows, client or ai.client(), types)
    except Exception as e:
        ai.failed("forecast", e)
        return template(rows)


def _explain(rows, client, types) -> str:
    slim = [{k: r[k] for k in ("crop", "collector_now", "collector_next_week", "low", "high", "change_pct",
                               "supply_kg", "demand_kg", "signal", "source")} for r in rows]
    resp = client.models.generate_content(
        model=ai.MODEL,
        contents=f"Forecast table (Rs/kg, collector price; JSON): {slim}",
        config=types.GenerateContentConfig(
            system_instruction=("You brief a Sri Lankan produce marketplace's ops team. In at most 3 short "
                                "sentences, say which crops to watch next week and what farmers and buyers "
                                "should do. Use only numbers from the table. If source is 'synthetic', say "
                                "the history is a demo series."),
            temperature=0.2),
    )
    return (resp.text or "").strip() or template(rows)
