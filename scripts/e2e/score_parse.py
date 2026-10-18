"""Score how well Govi reads first messages: each sample in parse_set.json goes to /intake from a
fresh test number, and the `parsed` result is compared with the expected answer.

    python scripts/e2e/score_parse.py https://<cloud-run-url>   # real Gemini
    python scripts/e2e/score_parse.py                           # offline keyword parser (the fallback)
    options: --out parse-score.md

Fields: intent, role, language, items (every crop with the right kg, nothing extra), when (date),
location. A sample is fully right when every field it states is right. A field set to null in
parse_set.json is not scored for that sample (romanised text has no single "right" language, chat
has no role, and a buyer who names no town gets Colombo by design). A message the chat answers from its word lists before Gemini ("hi", "where is my order?") is
scored on the intent its reply shows (status or chat), with language not scored.
Nothing is placed: no sample is ever followed by YES.
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run  # noqa: E402

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
FIELDS = ["intent", "role", "lang", "items", "when", "location"]


def expected_date(spec: str | None, today: date) -> str | None:
    if spec is None:
        return None
    if spec.startswith("+"):
        return (today + timedelta(days=int(spec[1:]))).isoformat()
    i = DAYS.index(spec)
    return (today + timedelta(days=(i - today.weekday()) % 7 or 7)).isoformat()


def _status_reply(reply: str) -> bool:
    from app import convo  # the STATUS answer's own opening lines, in every language
    return any(reply.startswith(v) for k in ("st_head", "st_none") for v in convo.T[k].values())


def score(sample: dict, parsed: dict | None, today: date, reply: str = "") -> dict:
    if parsed is None:
        # Answered by the chat's own word lists before Gemini ("hi", "where is my order?"): judge the
        # intent by the reply it got, and leave language unscored, since nothing was parsed.
        intent = "status" if _status_reply(reply) else "chat"
        p = {"intent": intent, "role": None, "language": sample["lang"], "items": [], "when": None, "location": None}
    else:
        p = parsed
    got_items = {i["crop"]: float(i["qty_kg"] or 0) for i in p.get("items") or []}
    if sample["role"] == "reporter":  # a price report: the crops matter, qty is always 0
        got_items = {c: 0.0 for c in got_items}
    out = {}
    checks = {
        "intent": (sample["intent"], p.get("intent")),
        "role": (sample["role"], p.get("role")),
        "lang": (sample["lang"], p.get("language")),
        "items": ({k: float(v) for k, v in sample["items"].items()}, got_items),
        "when": (expected_date(sample["when"], today), p.get("when")),
        "location": (sample["location"], p.get("location")),
    }
    for f, (want, got) in checks.items():
        if want is None and f != "items":
            continue  # not scored for this sample
        if f == "location" and isinstance(got, str):
            got = got.split(",")[0].strip()
            got = "Colombo" if got.lower().startswith("colombo") else got
        if f == "items":
            ok = set(want) == set(got) and all(abs(want[c] - got[c]) < 0.01 for c in want)
        else:
            ok = want == got
        out[f] = {"ok": ok, "want": want, "got": got}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?")
    ap.add_argument("--out", default="")
    ap.add_argument("--gap", type=float, default=2.0)
    a = ap.parse_args(argv)
    logging.disable(logging.WARNING)
    run.ensure_fixtures()
    t = run.Target(a.url, a.gap)
    if not t.live:
        run.fresh_offline()
    samples = json.loads((HERE / "parse_set.json").read_text(encoding="utf-8"))
    today = datetime.now(run.SL).date()
    rows, per_field, per_form = [], defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    numbers = []
    for s in samples:
        phone = run.TEST_PREFIX + f"{random.randint(0, 99999):05d}"
        numbers.append(phone)
        data = {"sender": phone, "via": "sim", "today": today.isoformat()}
        files = None
        if s.get("text"):
            data["text"] = s["text"]
        if s.get("file"):
            fp = run.FIXTURES / s["file"]
            files = {"file": (fp.name, fp.read_bytes(), "image/png" if fp.suffix == ".png" else "audio/wav")}
        try:
            r = t.http.post("/intake", data=data, files=files)
            parsed = r.json().get("parsed") if r.status_code == 200 else None
            reply = r.json().get("reply") or "" if r.status_code == 200 else ""
            err = None if r.status_code == 200 else f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            parsed, reply, err = None, "", f"{type(e).__name__}: {e}"
        if t.live:
            import time
            time.sleep(a.gap)
        res = score(s, parsed, today, reply) if not err else {f: {"ok": False, "want": "?", "got": err} for f in FIELDS}
        for f, v in res.items():
            per_field[f][0] += v["ok"]; per_field[f][1] += 1
        whole = all(v["ok"] for v in res.values())
        per_form[s["form"]][0] += whole; per_form[s["form"]][1] += 1
        rows.append((s, res, whole))
        print(("OK   " if whole else "MISS ") + s["id"] + ("" if whole else "  " + ", ".join(
            f"{f}: got {v['got']!r} want {v['want']!r}" for f, v in res.items() if not v["ok"])), flush=True)
        if not t.live:
            run.fresh_offline()
    fields_ok = sum(v[0] for v in per_field.values()); fields_n = sum(v[1] for v in per_field.values())
    whole_ok = sum(1 for _, _, w in rows if w)
    pct = lambda a_, b_: f"{100 * a_ / b_:.0f}%" if b_ else "-"
    mode = "live Gemini" if t.live else "offline keyword parser (no Gemini)"
    md = [f"# Govi parsing accuracy: {mode}", "",
          f"Run {datetime.now(run.SL):%Y-%m-%d %H:%M} against {getattr(t.http, 'base_url', 'in-process')}, "
          f"{len(rows)} samples ({sum(1 for s in samples if s.get('file'))} photos, no voice notes).", "",
          f"**Whole message right: {whole_ok}/{len(rows)} ({pct(whole_ok, len(rows))}). "
          f"Fields right: {fields_ok}/{fields_n} ({pct(fields_ok, fields_n)}).**", "",
          "| field | right | accuracy |", "|---|---|---|"]
    md += [f"| {f} | {per_field[f][0]}/{per_field[f][1]} | {pct(*per_field[f])} |" for f in FIELDS]
    md += ["", "| form | whole message right |", "|---|---|"]
    md += [f"| {k} | {v[0]}/{v[1]} ({pct(*v)}) |" for k, v in per_form.items()]
    md += ["", "## Misses", ""]
    for s, res, whole in rows:
        if not whole:
            md.append(f"- **{s['id']}** `{s.get('text') or s.get('file')}`: " + "; ".join(
                f"{f} got `{v['got']}` want `{v['want']}`" for f, v in res.items() if not v["ok"]))
    md += ["", f"Test numbers used (nothing placed): {', '.join(numbers)}"]
    out = Path(a.out or f"parse-score-{'live' if t.live else 'offline'}-{datetime.now(run.SL):%Y%m%d-%H%M}.md")
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"\nwhole message {pct(whole_ok, len(rows))}, fields {pct(fields_ok, fields_n)}\nreport: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
