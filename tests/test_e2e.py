"""One run through every role with the console and agent gates locked, as in production."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import security, store
from app.main import app

TOKEN, PIN = "test-token", "4321"
FARMER, BUYER, SPARE = "94771110001", "94771110002", "94771110003"


@pytest.fixture
def c(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("AGENT_PIN", PIN)
    monkeypatch.setenv("COOKIE_SECURE", "0")
    store.reset()
    security.reset_limits()
    return TestClient(app)


def sim(c, phone, text):
    r = c.post("/intake", data={"text": text, "sender": phone, "via": "sim"})
    assert r.status_code == 200, r.text
    return r.json()["reply"]


def test_gates_are_closed_without_credentials(c):
    assert c.get("/healthz").json()["admin_locked"] is True
    assert c.get("/admin", follow_redirects=False).headers["location"] == "/login?next=/admin"
    for path in ("/state", "/api/plan", "/api/offers", "/api/agent/reports"):
        assert c.get(path).status_code == 401, path
    for path in ("/plan", "/demo/seed", "/surplus/sweep", "/jobs/daily"):
        assert c.post(path).status_code == 401, path
    bad = c.post("/api/agent/prices", json={"reporter": "A", "phone": "94770000001", "market": "Dambulla",
                                            "kind": "collector", "prices": [{"crop": "carrot", "lkr_per_kg": 120}]})
    assert bad.status_code == 401
    # Wrong token keeps the user on the sign-in page and remembers where they were going.
    r = c.post("/login", data={"token": "nope", "next": "/admin"}, follow_redirects=False)
    assert r.headers["location"].startswith("/login?bad=1")
    assert "govi_admin" not in r.cookies


def test_every_role_end_to_end(c):
    today = date.today()
    admin = {"X-Admin-Token": TOKEN}

    # 1. Market agent posts today's farm-gate price with the PIN.
    r = c.post("/api/agent/prices", headers={"X-Agent-Pin": PIN},
               json={"reporter": "Kamal", "phone": "94770000001", "market": "Dambulla", "kind": "collector",
                     "prices": [{"crop": "carrot", "lkr_per_kg": 120}]})
    assert r.status_code == 200 and r.json()["count"] == 1
    assert c.post("/api/agent/prices", headers={"X-Agent-Pin": PIN},
                  json={"reporter": "K", "phone": "1", "market": "Mars", "kind": "collector",
                        "prices": [{"crop": "carrot", "lkr_per_kg": 120}]}).status_code == 400

    # 2. Farmer posts a harvest from the portal form (the main input).
    r = c.post("/api/listings", json={"farmer": "Sunil", "phone": "0771110001", "location": "nuwara eliya",
                                      "crop": "Carrots", "qty_kg": 200, "ready_on": (today + timedelta(days=1)).isoformat(),
                                      "lang": "en"})
    assert r.status_code == 200, r.text
    assert r.json()["matched_kg"] == 0  # no buyer yet
    assert c.post("/api/listings", json={"farmer": "X", "phone": "12", "location": "Dambulla", "crop": "carrot",
                                         "qty_kg": 10, "ready_on": today.isoformat()}).status_code == 400

    # 3. Business places an order in the portal; matching runs straight away.
    r = c.post("/api/orders", json={"business": "Lotus Kitchen", "phone": "0771110002", "location": "Colombo 03",
                                    "needed_by": (today + timedelta(days=3)).isoformat(),
                                    "items": [{"crop": "carrot", "qty_kg": 150}]})
    assert r.status_code == 200, r.text
    assert r.json()["matched_kg"] == 150

    # 4. Both sides answer YES through the WhatsApp simulator.
    assert "Waiting for the other side" in sim(c, FARMER, "yes")
    assert "Confirmed by both sides" in sim(c, BUYER, "YES")
    thread = c.get(f"/api/sim/thread?phone={BUYER}").json()
    assert [m["dir"] for m in thread][-2:] == ["in", "out"]

    # 5. A simulator text from a new farmer is parsed (demo parser without a key) and stored.
    reply = sim(c, SPARE, "This is Rasan, red onion 100kg ready today, Jaffna")
    assert "red onion" in reply.lower() and "YES" in reply
    assert "up for sale" in sim(c, SPARE, "yes")

    # 6. Ops console: sign in, move the shipment, then mark one as missed.
    r = c.post("/login", data={"token": TOKEN, "next": "/admin"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/admin"
    assert c.get("/admin").status_code == 200
    ships = c.get("/api/plan").json()["shipments"]
    assert ships, "confirmed deal should have a shipment"
    sid = ships[0]["id"]
    assert c.post(f"/shipments/{sid}/advance").status_code == 200
    r = c.post(f"/shipments/{sid}/missed")
    assert r.status_code == 200, r.text
    assert c.post("/shipments/nope/missed").status_code == 404

    # 7. Daily job (Cloud Scheduler, header token): unsold onion gets numbered options; farmer replies 1.
    c.cookies.clear()
    r = c.post("/jobs/daily", headers=admin)
    assert r.status_code == 200 and r.json()["unsold_offers"] >= 1
    assert "1." in c.get(f"/api/sim/thread?phone={SPARE}").json()[-1]["text"]
    reply = sim(c, SPARE, "1")
    offer = next(o for o in c.get("/api/offers", headers=admin).json() if o["phone"] == SPARE)
    assert offer["status"] == "accepted" and reply

    # 8. Public pages all load.
    for path in ("/", "/business", "/agent", "/sim", "/smul", "/login", "/healthz", "/api/health", "/api/prices"):
        assert c.get(path).status_code == 200, path


def test_intake_validation_and_rate_limit(c, monkeypatch):
    assert c.post("/intake", data={"text": "", "sender": FARMER}).status_code == 400
    assert c.post("/intake", data={"text": "x" * 5000, "sender": FARMER}).status_code == 400
    assert c.post("/intake", data={"text": "hi", "via": "sim"}).status_code == 400  # sim needs a number
    r = c.post("/intake", data={"sender": FARMER}, files={"file": ("a.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 400
    monkeypatch.setattr(security, "RATE", 3)
    security.reset_limits()
    codes = [c.post("/login", data={"token": "x"}, follow_redirects=False).status_code for _ in range(5)]
    assert codes[-1] == 429
