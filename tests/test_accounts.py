"""Phone-number accounts: register, sign in, profile and role, sign out, and the link to WhatsApp."""
import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import accounts, security, store, vocab
from app.main import app

TOKEN, PIN = "test-token", "4321"
NEW = "94771230001"


@pytest.fixture
def c(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("AGENT_PIN", PIN)
    monkeypatch.setenv("COOKIE_SECURE", "0")
    for k in ("FIREBASE_API_KEY", "FIREBASE_PROJECT_ID", "AUTH_DEMO_NUMBERS", "ADMIN_PHONES"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ALLOW_RESET", "1")
    store.reset()
    for kind in store.KEEP:
        store.DB.data.pop(kind, None)
    security.reset_limits()
    return TestClient(app)


def code_for(phone):
    msg = [o for o in store.sent() if o["to"] == phone][-1]["body"]
    return re.search(r"\b(\d{6})\b", msg).group(1)


def sign_in(c, phone=NEW):
    assert c.post("/api/auth/start", json={"phone": phone}).json()["sent"] is True
    r = c.post("/api/auth/verify", json={"phone": phone, "code": code_for(vocab.phone(phone))})
    assert r.status_code == 200, r.text
    return r.json()


def test_register_profile_post_track_and_sign_out(c):
    assert c.get("/api/me").status_code == 401
    assert c.get("/api/auth/config").json()["provider"] == "govi"
    c.post("/api/auth/start", json={"phone": "077 123 0001"})
    bad = c.post("/api/auth/verify", json={"phone": "0771230001", "code": "000000" if code_for(NEW) != "000000" else "111111"})
    assert bad.status_code == 401
    r = c.post("/api/auth/verify", json={"phone": "0771230001", "code": code_for(NEW)})
    assert r.status_code == 200 and r.json()["new"] is True and r.json()["user"]["phone"] == NEW
    assert "govi_session" in r.cookies
    # The same code cannot be used twice.
    assert c.post("/api/auth/verify", json={"phone": NEW, "code": code_for(NEW)}).status_code == 401

    # Registration: name and role.
    assert c.put("/api/me", json={"name": " "}).status_code == 400
    me = c.put("/api/me", json={"name": "Ravi", "role": "farmer", "location": "dambulla", "lang": "si"}).json()
    assert me["complete"] and me["location"] == "Dambulla" and c.get("/api/me").json()["name"] == "Ravi"

    # Posting as someone else's number is not possible once signed in.
    r = c.post("/api/listings", json={"phone": "0779999999", "location": "Dambulla", "crop": "tomato",
                                      "qty_kg": 50, "ready_on": (date.today() + timedelta(days=1)).isoformat()})
    assert r.status_code == 200, r.text
    mine = c.get("/api/track").json()
    assert [l["farmer"] for l in mine["listings"]] == ["Ravi"] and mine["listings"][0]["phone"] == NEW
    # Asking for another number still returns your own.
    assert c.get("/api/track", params={"phone": "94779999999"}).json()["listings"][0]["phone"] == NEW

    old = c.cookies.get("govi_session")
    assert c.post("/api/auth/logout").json()["ok"]
    assert c.get("/api/me").status_code == 401
    c.cookies.set("govi_session", old)  # a stolen copy of the old cookie is dead too
    assert c.get("/api/me").status_code == 401
    assert c.get("/api/track").status_code == 401


def test_codes_never_show_on_the_public_simulator(c):
    c.post("/intake", data={"text": "carrot 10kg ready tomorrow, Dambulla", "sender": NEW, "via": "sim"})
    c.post("/api/auth/start", json={"phone": NEW})
    code = code_for(NEW)
    assert not any(code in m["text"] for m in c.get("/api/sim/thread", params={"phone": NEW}).json())
    assert c.get("/signin").status_code == 200


def test_wrong_codes_and_resends_are_capped(c):
    c.post("/api/auth/start", json={"phone": NEW})
    good = code_for(NEW)
    wrong = "000000" if good != "000000" else "111111"
    for _ in range(accounts.CODE_TRIES):
        assert c.post("/api/auth/verify", json={"phone": NEW, "code": wrong}).status_code == 401
    assert c.post("/api/auth/verify", json={"phone": NEW, "code": good}).status_code == 429
    for _ in range(accounts.SENDS_PER_10_MIN - 1):
        assert c.post("/api/auth/start", json={"phone": NEW}).status_code == 200
    assert c.post("/api/auth/start", json={"phone": NEW}).status_code == 429
    assert c.post("/api/auth/start", json={"phone": "12"}).status_code == 400


def test_sign_out_everywhere(c):
    sign_in(c)
    other = TestClient(app)
    other.post("/api/auth/start", json={"phone": NEW})
    other.post("/api/auth/verify", json={"phone": NEW, "code": code_for(NEW)})
    assert other.get("/api/me").status_code == 200
    assert c.post("/api/auth/logout-all").json()["ended"] == 2
    assert other.get("/api/me").status_code == 401


def test_demo_logins_arrive_with_a_profile(c, monkeypatch):
    demo = c.get("/api/auth/config").json()["demo"]
    assert {d["role"] for d in demo} == {"farmer", "buyer", "agent"}
    assert c.post("/api/auth/start", json={"phone": "0770000014"}).json()["demo"] is True
    assert c.post("/api/auth/verify", json={"phone": "0770000014", "code": "999999"}).status_code == 401
    r = c.post("/api/auth/verify", json={"phone": "0770000014", "code": "123456"}).json()
    assert r["new"] is False and r["user"]["role"] == "buyer" and r["user"]["business"] == "Mango Tree Cafe"
    # The demo reset keeps accounts and sessions.
    c.post("/demo/seed", headers={"X-Admin-Token": TOKEN})
    assert c.get("/api/me").json()["phone"] == "94770000014"
    assert c.get("/api/track").json()["orders"]  # the demo morning's Mango Tree Cafe order is theirs
    # Real deployments switch the demo numbers off.
    monkeypatch.setenv("ALLOW_RESET", "0")
    assert c.get("/api/auth/config").json()["demo"] == []


def test_whatsapp_history_belongs_to_the_same_number(c):
    r = c.post("/intake", data={"text": "This is Ravi, carrot 100kg ready tomorrow, Dambulla",
                                "sender": NEW, "via": "sim"})
    assert r.status_code == 200
    assert accounts.user(NEW)["name"] == "Ravi" and accounts.user(NEW)["role"] == "farmer"
    out = sign_in(c)
    assert out["new"] is False and out["user"]["name"] == "Ravi"
    assert [l["crop"] for l in c.get("/api/track").json()["listings"]] == ["carrot"]


def test_track_needs_sign_in_but_console_can_look_anyone_up(c):
    assert c.get("/api/track", params={"phone": NEW}).status_code == 401
    assert c.get("/api/standing", params={"phone": NEW}).status_code == 401
    assert c.get("/api/track", params={"phone": NEW}, headers={"X-Admin-Token": TOKEN}).status_code == 200


def test_agent_role_needs_the_pin_once_then_no_pin(c):
    sign_in(c)
    assert c.put("/api/me", json={"name": "Kamal", "role": "agent"}).status_code == 403
    assert c.put("/api/me", json={"name": "Kamal", "role": "agent", "agent_pin": PIN, "market": "Dambulla"}).json()["role"] == "agent"
    r = c.post("/api/agent/prices", json={"market": "Dambulla", "kind": "collector",
                                          "prices": [{"crop": "carrot", "lkr_per_kg": 130}]})
    assert r.status_code == 200, r.text
    row = store.DB.one("prices", r.json()["saved"][0]["id"])
    assert row["phone"] == NEW and row["reporter"] == "Kamal"


def test_admin_phones_open_the_console(c, monkeypatch):
    sign_in(c)
    assert c.get("/state").status_code == 401
    monkeypatch.setenv("ADMIN_PHONES", "0770554201;0771230001")
    assert c.get("/state").status_code == 200 and c.get("/api/me").json()["admin"] is True


def test_firebase_phone_sign_in(c, monkeypatch):
    monkeypatch.setenv("FIREBASE_API_KEY", "web-key")
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "govimart-8407c")
    cfg = c.get("/api/auth/config").json()
    assert cfg["provider"] == "firebase" and cfg["firebase"]["authDomain"] == "govimart-8407c.firebaseapp.com"
    # Govi's own codes are off; Firebase sends the SMS. Demo numbers still work without SMS.
    assert c.post("/api/auth/start", json={"phone": NEW}).status_code == 400
    assert c.post("/api/auth/verify", json={"phone": NEW, "code": "123456"}).status_code == 400
    assert c.post("/api/auth/verify", json={"phone": "0770000002", "code": "123456"}).status_code == 200
    monkeypatch.setattr(accounts, "_firebase_phone", lambda tok: "94771230001" if tok == "good" else
                        (_ for _ in ()).throw(accounts.HTTPException(401, "expired")))
    assert c.post("/api/auth/verify", json={"id_token": "bad"}).status_code == 401
    r = c.post("/api/auth/verify", json={"id_token": "good"})
    assert r.status_code == 200 and r.json()["user"]["phone"] == NEW
    assert c.get("/api/me").json()["phone"] == NEW


def test_real_firebase_tokens_are_checked(c, monkeypatch):
    monkeypatch.setenv("FIREBASE_API_KEY", "web-key")
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "govimart-8407c")
    from google.oauth2 import id_token as gid
    monkeypatch.setattr(gid, "verify_firebase_token", lambda tok, req, audience: {"phone_number": "+94771230001", "aud": audience})
    assert accounts._firebase_phone("x") == NEW
    def boom(*a, **k):
        raise ValueError("Token expired")
    monkeypatch.setattr(gid, "verify_firebase_token", boom)
    with pytest.raises(accounts.HTTPException) as e:
        accounts._firebase_phone("x")
    assert e.value.status_code == 401
