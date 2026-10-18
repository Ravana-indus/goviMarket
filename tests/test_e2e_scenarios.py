"""Every chat scenario in scripts/e2e/scenarios.py, played offline through /intake with no Gemini key.

Steps marked live_only (free text only Gemini reads, photos, voice) end the scenario early here; the
live run (python scripts/e2e/run.py <url>) plays them in full. KNOWN lists offline failures that are
real gaps in the keyword fallback: they run as strict xfail, so a fix shows up as XPASS."""
import sys
from pathlib import Path

import pytest

E2E = Path(__file__).resolve().parent.parent / "scripts" / "e2e"
sys.path.insert(0, str(E2E))

import run  # noqa: E402
from scenarios import SCENARIOS  # noqa: E402

KNOWN = {
    "B5": "keyword fallback does not know Tanglish 'venum' (want), so the order is read as a harvest",
}


@pytest.fixture(scope="module")
def target():
    run.ensure_fixtures()
    with pytest.MonkeyPatch.context() as mp:  # Target locks the console gates; undo that for later test files
        for k in ("ADMIN_TOKEN", "AGENT_PIN", "GEMINI_API_KEY"):
            mp.setenv(k, "")  # recorded, so the original value (or its absence) comes back afterwards
        t = run.Target(None, 0)
        yield t
    run.fresh_offline()


@pytest.mark.parametrize("sc", [s for s in SCENARIOS if not s.get("live_only")], ids=lambda s: s["id"])
def test_scenario(sc, target, monkeypatch):
    base = {"crop": "carrot", "day3": "", "day3_iso": "", "today": "", "tomorrow": ""}
    from datetime import timedelta
    today = run.datetime.now(run.SL).date()
    d3 = today + timedelta(days=3)
    base.update(day3=d3.strftime("%A"), day3_iso=d3.isoformat(), today=today.isoformat(),
                tomorrow=(today + timedelta(days=1)).isoformat())
    res = run.run_scenario(target, sc, base, {})
    if sc["id"] in KNOWN:
        if res["ok"]:
            pytest.fail(f"XPASS: {sc['id']} now passes; remove it from KNOWN")
        pytest.xfail(KNOWN[sc["id"]])
    assert res["ok"], f"{res['why']}\n\n{run.transcript(res)}"
