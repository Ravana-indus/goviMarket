"""Play the scenarios in scenarios.py and write a Markdown report with every transcript.

    python scripts/e2e/run.py                         # offline: in-process, no Gemini, fresh memory store
    python scripts/e2e/run.py https://<cloud-run-url> # live: real Gemini, fresh test numbers
    options: --only D1,B3   --out report.md   --area deal

Live runs never call /demo/clear or /demo/seed and never send an admin token. Test numbers start
with 9400099 (12 digits, not a Sri Lankan mobile), so a WhatsApp send to them goes nowhere. Every
number used and every record left behind is listed at the end of the report.
"""
from __future__ import annotations

import argparse
import logging
import json as jsonlib
import os
import random
import re
import sys
import time
import wave
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scenarios import SCENARIOS  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SL = timezone(timedelta(hours=5, minutes=30))
CROP_CANDIDATES = ["pumpkin", "beetroot", "brinjal", "cabbage", "potato", "maize", "leeks", "carrot"]
TEST_PREFIX = "9400099"
# Order notes rendered as photos (Latin script only: the container has no Sinhala or Tamil font).
PHOTOS = {
    "order_en.png": ["ORDER - Green Leaf Cafe", "Tomato  10 kg", "Carrot  5 kg", "Need by tomorrow", "Deliver: Colombo 05"],
    "harvest_note.png": ["Sunil - Nuwara Eliya", "Carrot 200kg", "Leeks 100kg", "Ready tomorrow - for sale"],
    "hotel_order.png": ["Hotel Hill View, Kandy", "Purchase order", "Beans 15 kg", "Big onion 20 kg", "Green chilli 3 kg",
                        "Deliver by Friday"],
}


def script_of(text: str) -> str:
    """Mostly Sinhala, Tamil or Latin letters."""
    si = len(re.findall(r"[඀-෿]", text or ""))
    ta = len(re.findall(r"[஀-௿]", text or ""))
    la = len(re.findall(r"[A-Za-z]", re.sub(r"\b(YES|NO|STATUS|EDIT|CANCEL|COST|TRACK|DROPPED|RECEIVED|GV-[0-9A-Fa-f]+|Govi|Rs|kg)\b", "", text or "")))
    best = max(("si", si), ("ta", ta), ("en", la * 0.35), key=lambda x: x[1])
    return best[0] if best[1] else "?"


def ensure_fixtures() -> None:
    """A handwritten-style order photo and a one-second silent voice note, made on first run."""
    FIXTURES.mkdir(exist_ok=True)
    wav = FIXTURES / "silence.wav"
    if not wav.exists():
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b"\0\0" * 16000)
    for name, lines in PHOTOS.items():
        png = FIXTURES / name
        if png.exists():
            continue
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (900, 120 + 95 * len(lines)), (250, 247, 235))
        d = ImageDraw.Draw(img)
        font = ImageFont.load_default(size=44)
        for y in range(140, img.height, 95):
            d.line((40, y, 860, y), fill=(180, 200, 230), width=2)
        for i, line in enumerate(lines):
            d.text((60 + (i % 2) * 8, 60 + i * 95), line, fill=(30, 40, 120), font=font)
        img.rotate(2, expand=True, fillcolor=(90, 80, 70)).save(png)  # a slightly crooked phone photo


class Target:
    def __init__(self, base: str | None, gap: float):
        self.live = bool(base)
        self.gap = gap
        if base:
            import httpx
            self.http = httpx.Client(base_url=base.rstrip("/"), timeout=120)
        else:
            os.environ.pop("GEMINI_API_KEY", None)
            os.environ.setdefault("RATE_LIMIT_PER_MIN", "100000")
            os.environ["ADMIN_TOKEN"] = "e2e-offline-token"  # gates locked, as in production
            os.environ["AGENT_PIN"] = "e2e-pin"
            from fastapi.testclient import TestClient
            from app import store
            from app.main import app
            store.reset()
            self.http = TestClient(app)
        self.locked = None

    def health(self) -> dict:
        try:
            return self.http.get("/api/health").json()
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}

    def thread(self, phone: str) -> list[dict]:
        r = self.http.get("/api/sim/thread", params={"phone": phone})
        return r.json() if r.status_code == 200 else []

    def say(self, phone: str, text: str | None, file: str | None) -> tuple[str, list[str], float]:
        before = len(self.thread(phone))
        t0 = time.time()
        files = None
        if file:
            p = FIXTURES / file
            mime = "image/png" if p.suffix == ".png" else "audio/wav"
            files = {"file": (p.name, p.read_bytes(), mime)}
        data = {"sender": phone, "via": "sim"}
        if text is not None:
            data["text"] = text
        for attempt in range(4):
            try:
                r = self.http.post("/intake", data=data, files=files)
                reply = r.json().get("reply") or "" if r.status_code == 200 else f"[HTTP {r.status_code}] {r.text[:300]}"
            except Exception as e:  # noqa: BLE001
                reply = f"[HTTP 599] {type(e).__name__}: {e}"
            if not reply.startswith("[HTTP 429]"):
                break
            time.sleep(20)  # the site allows 30 messages a minute per address
        took = time.time() - t0
        if self.live:
            time.sleep(self.gap)
        after = self.thread(phone)
        # Messages Govi sent this number during the step, other than the reply itself.
        new = [m["text"] for m in after[before:] if m["dir"] == "out" and m["text"] != reply]
        return reply, new, took

    def inbox_since(self, phone: str, n: int) -> tuple[list[str], int]:
        t = self.thread(phone)
        return [m["text"] for m in t[n:] if m["dir"] == "out"], len(t)


def fresh_offline() -> None:
    """Empty in-memory market, including what store.reset() keeps (accounts, lane costs), and the
    shared lane rates back to data/lanes.json: a COST report moves them for the whole process."""
    from app import lanes, security, store
    from app.schemas import Lane
    store.reset()
    for kind in store.KEEP:
        store.DB.data.pop(kind, None) if hasattr(store.DB, "data") else None
    for path, shared in lanes._SHARED.items():
        rows = jsonlib.loads(path.read_text())
        for lane, row in zip(shared, rows):
            for k, val in Lane(**row).__dict__.items():
                setattr(lane, k, val)
    security.reset_limits()


def fill(s, v: dict):
    if isinstance(s, str):
        return re.sub(r"\{(\w+)\}", lambda m: str(v.get(m.group(1), m.group(0))), s)
    if isinstance(s, dict):
        return {k: fill(x, v) for k, x in s.items()}
    if isinstance(s, list):
        return [fill(x, v) for x in s]
    return s


def pick_crop(t: Target) -> str:
    if not t.live:
        return "carrot"
    try:
        cat = {r["crop"]: r for r in t.http.get("/api/catalogue").json()}
        for c in CROP_CANDIDATES:
            if c in cat and not cat[c].get("available_kg"):
                return c
    except Exception:  # noqa: BLE001
        pass
    return CROP_CANDIDATES[0]


def run_scenario(t: Target, sc: dict, base_vars: dict, ledger: dict) -> dict:
    if not t.live:  # offline every scenario starts from an empty market, so results never depend on order
        fresh_offline()
    actors: dict[str, str] = {}
    v = dict(base_vars)
    for who in ("buyer", "farmer", "new"):
        actors[who] = TEST_PREFIX + f"{random.randint(0, 99999):05d}"
        v[who] = actors[who]
    log, ok, skipped, why = [], True, False, ""
    for i, st in enumerate(sc["steps"], 1):
        if "api" in st:
            method, path = st["api"]
            path = fill(path, v)
            kw = {}
            if st.get("json") is not None:
                kw["json"] = fill(st["json"], v)
            if st.get("data") is not None:
                kw["data"] = fill(st["data"], v)
            try:
                r = t.http.request(method, path, headers=st["headers"], follow_redirects=False, **kw)
                code, body = r.status_code, r.text
            except Exception as e:  # noqa: BLE001
                code, body = 599, str(e)
            want = st["status"] if isinstance(st["status"], tuple) else (st["status"],)
            fails = [] if code in want else [f"status {code}, wanted {'/'.join(map(str, want))}"]
            fails += [f"body lacks {c!r}" for c in st["contains"] if c not in body]
            log.append({"n": i, "kind": "api", "line": f"{method} {path}", "reply": f"{code} {body[:200]}", "fails": fails,
                        "note": st.get("note", "")})
            if method == "POST" and code == 200 and path in ("/api/listings", "/api/orders"):
                ledger.setdefault("portal", []).append(f"{path} {body[:120]}")
            if fails:
                ok, why = False, fails[0]
                break
            continue
        if st["live_only"] and not t.live:
            skipped = True
            log.append({"n": i, "kind": "skip", "line": st["say"] or f"[{st['file']}]", "reply": "(needs Gemini: skipped offline)",
                        "fails": [], "who": st["who"]})
            break
        phone = actors[st["who"]]
        text = fill(st["say"], v) if st["say"] is not None else None
        peer_n = None
        if st.get("peer"):
            peer_n = len(t.thread(actors[st["peer"][0]]))
        reply, new, took = t.say(phone, text, st["file"])
        ledger.setdefault("numbers", set()).add(phone)
        hay = reply
        fails = []
        for pat in st["expect"]:
            if not re.search(fill(pat, v), reply, re.I | re.S):
                fails.append(f"reply lacks /{pat[:60]}/")
        if st["any"] and not any(re.search(fill(p, v), reply, re.I | re.S) for p in st["any"]):
            fails.append(f"reply matches none of {[p[:40] for p in st['any']]}")
        for pat in st["absent"]:
            if re.search(pat, reply, re.I | re.S):
                fails.append(f"reply has /{pat[:60]}/")
        if st["lang"] and script_of(reply) != st["lang"]:
            fails.append(f"reply is in {script_of(reply)}, wanted {st['lang']}")
        if st["inbox"] and not any(re.search(st["inbox"], m, re.I) for m in new + [reply]):
            fails.append(f"nothing sent to {st['who']} matching /{st['inbox']}/")
        peer_msgs = []
        if st.get("peer"):
            if t.live:
                time.sleep(1.0)
            peer_msgs, _ = t.inbox_since(actors[st["peer"][0]], peer_n)
            if not any(re.search(st["peer"][1], m, re.I) for m in peer_msgs):
                fails.append(f"nothing sent to {st['peer'][0]} matching /{st['peer'][1]}/")
        for name, pat in st["grab"].items():
            m = re.search(pat, "\n".join([reply] + new + peer_msgs), re.I)
            if m:
                v[name] = m.group(1) if m.groups() else m.group(0)
            else:
                fails.append(f"could not find {name}")
        if any(re.search(r"GV-[0-9A-Fa-f]+", x) for x in [reply] + new):
            ledger.setdefault("codes", set()).update(re.findall(r"GV-[0-9A-Fa-f]+", "\n".join([reply] + new)))
        log.append({"n": i, "kind": "say", "who": st["who"], "line": text if text is not None else f"[{st['file']}]",
                    "reply": reply, "also": new, "peer": (st["peer"][0], peer_msgs) if st.get("peer") else None,
                    "fails": fails, "took": took, "note": st.get("note", "")})
        if fails:
            ok, why = False, fails[0]
            break
    return {"id": sc["id"], "area": sc["area"], "name": sc["name"], "ok": ok, "skipped": skipped, "why": why,
            "log": log, "actors": actors}


def transcript(res: dict) -> str:
    out = []
    for e in res["log"]:
        if e["kind"] == "api":
            out.append(f"{e['n']}. API {e['line']}\n   -> {e['reply']}")
        elif e["kind"] == "skip":
            out.append(f"{e['n']}. {e['who']} > {e['line']}\n   {e['reply']}")
        else:
            out.append(f"{e['n']}. {e['who']} (+{res['actors'][e['who']]}) > {e['line']}")
            out += ["   " + l for l in (e["reply"] or "(empty reply)").splitlines()]
            for m in e.get("also") or []:
                out.append("   [also sent to " + e["who"] + "] " + m.replace("\n", "\n      "))
            if e.get("peer"):
                for m in e["peer"][1]:
                    out.append(f"   [sent to {e['peer'][0]}] " + m.replace("\n", "\n      "))
        for f in e["fails"]:
            out.append(f"   ✗ {f}")
        if e.get("note"):
            out.append(f"   (check: {e['note']})")
    return "\n".join(out)


def report(results: list[dict], t: Target, health: dict, base_vars: dict, ledger: dict, started: str) -> str:
    passed = [r for r in results if r["ok"] and not r["skipped"]]
    partial = [r for r in results if r["ok"] and r["skipped"]]
    failed = [r for r in results if not r["ok"]]
    mode = "live (real Gemini)" if t.live else "offline (keyword parser, no Gemini)"
    lines = [f"# Govi E2E run: {mode}", "",
             f"Started {started}. Target: {getattr(t.http, 'base_url', 'in-process')}. Test crop: {base_vars['crop']}.", "",
             f"Health: `{jsonlib.dumps({k: health.get(k) for k in ('gemini', 'store', 'admin_locked', 'agent_locked', 'telegram', 'whatsapp', 'gemini_last_error')})}`", "",
             f"**{len(passed)} passed, {len(failed)} failed, {len(partial)} passed up to a Gemini-only step** (of {len(results)}).", "",
             "| id | area | scenario | result |", "|---|---|---|---|"]
    for r in results:
        res = "✅ pass" if r["ok"] and not r["skipped"] else "◐ partial (rest needs Gemini)" if r["ok"] else f"❌ {r['why']}"
        lines.append(f"| {r['id']} | {r['area']} | {r['name']} | {res.replace('|', '/')} |")
    if failed:
        lines += ["", "## Failures", ""]
        for r in failed:
            lines += [f"### {r['id']} {r['name']}", "", "```", transcript(r), "```", ""]
    lines += ["", "## Test records left behind", "",
              f"Numbers used: {', '.join(sorted(ledger.get('numbers', [])))}", "",
              f"Tracking codes created: {', '.join(sorted(ledger.get('codes', []))) or 'none'}", "",
              "Portal records: " + ("; ".join(ledger.get("portal", [])) or "none"), "",
              "Orders and listings from passing chat scenarios were withdrawn with CANCEL where the scenario ends with it; "
              "confirmed test deals (D1-D3, D5, D6, A4) cannot be cancelled from chat and stay until removed in the console. "
              "D1 and D2 also send COST reports (Rs 2,000 and Rs 1,500 for 150 kg), which feed that lane's freight rate.",
              "", "## All transcripts", ""]
    for r in results:
        lines += [f"<details><summary>{r['id']} {r['name']}: {'pass' if r['ok'] else 'FAIL'}</summary>", "", "```", transcript(r), "```",
                  "", "</details>", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?")
    ap.add_argument("--only", default="")
    ap.add_argument("--area", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--gap", type=float, default=2.0, help="seconds between live messages (site limit: 30/min)")
    a = ap.parse_args(argv)
    logging.disable(logging.WARNING)
    ensure_fixtures()
    t = Target(a.url, a.gap)
    health = t.health()
    started = datetime.now(SL).strftime("%Y-%m-%d %H:%M %Z")
    today = datetime.now(SL).date()
    d3 = today + timedelta(days=3)
    base = {"crop": pick_crop(t), "day3": d3.strftime("%A"), "day3_iso": d3.isoformat(),
            "today": today.isoformat(), "tomorrow": (today + timedelta(days=1)).isoformat()}
    locked = bool(health.get("admin_locked"))
    chosen = [s for s in SCENARIOS
              if (not a.only or s["id"] in a.only.split(","))
              and (not a.area or s["area"] == a.area)
              and not (s.get("offline_only") and t.live)
              and not (s.get("locked_only") and not locked)]
    ledger: dict = {}
    results = []
    for sc in chosen:
        r = run_scenario(t, sc, base, ledger)
        results.append(r)
        mark = "PASS" if r["ok"] and not r["skipped"] else "part" if r["ok"] else "FAIL"
        print(f"{mark}  {r['id']:4} {r['name']}" + (f"  -- {r['why']}" if not r["ok"] else ""), flush=True)
    md = report(results, t, health, base, ledger, started)
    out = Path(a.out or f"e2e-{'live' if t.live else 'offline'}-{datetime.now(SL):%Y%m%d-%H%M}.md")
    out.write_text(md, encoding="utf-8")
    print(f"\nreport: {out}")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
