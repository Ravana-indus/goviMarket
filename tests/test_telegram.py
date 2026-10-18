from fastapi.testclient import TestClient

from app import accounts, store, telegram
from app.main import app
from tests.test_core import FARMER_JSON, _fake_gemini

PHONE = "94771234567"


def _update(uid, **message):
    return {"update_id": uid, "message": {"chat": {"id": 555, "type": "private"}, "from": {"id": 9}, **message}}


def _setup(monkeypatch):
    store.reset()
    for kind, key in (("telegram", "555"), ("telegram_phone", PHONE), ("users", PHONE)):
        store.DB.delete(kind, key)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    sent = []
    monkeypatch.setattr(telegram, "send_text", lambda chat, body, ask_phone=False, keyboard=None:
                        sent.append({"body": body, "ask_phone": ask_phone, "keyboard": keyboard}))
    monkeypatch.setattr(telegram, "fetch_media", lambda fid: b"ogg")
    c = TestClient(app)
    h = {"X-Telegram-Bot-Api-Secret-Token": telegram.webhook_secret()}
    n = iter(range(100, 1000))
    return sent, (lambda **m: c.post("/webhook/telegram", json=_update(next(n), **m), headers=h)), c


def test_telegram_registers_then_reads_the_held_order_in_the_chosen_language(monkeypatch):
    sent, post, c = _setup(monkeypatch)
    _fake_gemini(monkeypatch, FARMER_JSON)
    assert c.post("/webhook/telegram", json=_update(1, text="hi")).status_code == 403  # no secret header
    post(voice={"file_id": "v1", "mime_type": "audio/ogg"})
    assert sent[-1]["ask_phone"]  # asked to share the phone number first

    post(contact={"phone_number": "0771111111", "user_id": 42})
    assert telegram.phone_for("555") is None  # a forwarded contact card does not link

    post(contact={"phone_number": "+94771234567", "user_id": 9})
    assert telegram.phone_for("555") == PHONE
    assert sent[-1]["keyboard"] == [["සිංහල", "தமிழ்", "English"]]
    post(text="සිංහල")
    assert accounts.chosen_lang(PHONE) == "si" and "විකුණනවාද" in sent[-1]["body"]
    post(text="hmm")
    assert "බොත්තමක්" in sent[-2]["body"]  # not a button: asked again
    post(text="🌾 මම විකුණනවා (ගොවි)")
    post(text="Dambulla")
    post(text="Sunil")
    u = accounts.user(PHONE)
    assert (u["role"], u["location"], u["name"]) == ("farmer", "Dambulla", "Sunil")
    done = [m for m in sent if "සූදානම්" in m["body"]]
    assert done and done[0]["keyboard"][0] == ["📦 මගේ ඇණවුම්"]
    assert "YES" in sent[-1]["body"]  # the held voice note was read after registration
    assert store.listings() == []

    post(text="YES")
    assert len(store.listings()) == 1 and "✅" in sent[-1]["body"]
    assert telegram.send_to_phone(PHONE, "offer") and sent[-1]["body"] == "offer"


def test_telegram_language_and_restart(monkeypatch):
    sent, post, _ = _setup(monkeypatch)
    store.DB.put("users", PHONE, {"phone": PHONE, "name": "Kamal", "role": "buyer", "location": "Colombo", "lang": "en"})
    post(contact={"phone_number": PHONE, "user_id": 9})
    assert sent[-1]["body"].startswith("Linked")  # already registered: nothing asked
    post(text="/language")
    post(text="தமிழ்")
    assert accounts.chosen_lang(PHONE) == "ta" and "தமிழில்" in sent[-1]["body"]
    assert sent[-1]["keyboard"][0] == ["📦 என் ஆர்டர்கள்"]
    post(text="🔄 மீண்டும் பதிவு")
    post(text="English")
    assert "sell or buy" in sent[-1]["body"]  # restart asks every step again
    post(text="🌾 I sell (farmer)")
    post(text="Nuwara Eliya")
    post(text="Kamal Farms")
    u = accounts.user(PHONE)
    assert (u["role"], u["location"], u["name"], u["lang"]) == ("farmer", "Nuwara Eliya", "Kamal Farms", "en")
    assert "All set" in sent[-1]["body"]
    post(text="/status")
    assert "nothing open" in sent[-1]["body"]


def test_telegram_off_without_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    c = TestClient(app)
    assert c.post("/webhook/telegram", json=_update(1, text="hi"),
                  headers={"X-Telegram-Bot-Api-Secret-Token": "x"}).status_code == 403
    assert c.get("/api/health").json()["telegram"] is False
