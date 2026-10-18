from fastapi.testclient import TestClient

from app import store, telegram
from app.main import app
from tests.test_core import FARMER_JSON, _fake_gemini


def _update(uid, **message):
    return {"update_id": uid, "message": {"chat": {"id": 555, "type": "private"}, "from": {"id": 9}, **message}}


def test_telegram_links_phone_then_runs_the_same_chat(monkeypatch):
    store.reset()
    store.DB.delete("telegram", "555")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    _fake_gemini(monkeypatch, FARMER_JSON)
    sent = []
    monkeypatch.setattr(telegram, "send_text", lambda chat, body, ask_phone=False: sent.append((chat, body, ask_phone)))
    monkeypatch.setattr(telegram, "fetch_media", lambda fid: b"ogg")
    c = TestClient(app)
    h = {"X-Telegram-Bot-Api-Secret-Token": telegram.webhook_secret()}

    assert c.post("/webhook/telegram", json=_update(1, text="hi")).status_code == 403  # no secret header
    voice = _update(2, voice={"file_id": "v1", "mime_type": "audio/ogg"})
    assert c.post("/webhook/telegram", json=voice, headers=h).status_code == 200
    assert sent[-1][2] is True  # asked to share the phone number first

    someone_else = _update(3, contact={"phone_number": "0771111111", "user_id": 42})
    c.post("/webhook/telegram", json=someone_else, headers=h)
    assert telegram.phone_for("555") is None  # a forwarded contact card does not link

    own = _update(4, contact={"phone_number": "+94771234567", "user_id": 9})
    c.post("/webhook/telegram", json=own, headers=h)
    assert telegram.phone_for("555") == "94771234567"
    assert "YES" in sent[-1][1]  # the held voice note was read and the order shown
    assert store.listings() == []

    c.post("/webhook/telegram", json=_update(4, contact={"phone_number": "+94771234567", "user_id": 9}), headers=h)
    n = len(sent)
    c.post("/webhook/telegram", json=_update(5, text="YES"), headers=h)
    assert len(store.listings()) == 1 and "✅" in sent[n][1]
    assert telegram.send_to_phone("94771234567", "offer") and sent[-1] == ("555", "offer", False)


def test_telegram_off_without_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    c = TestClient(app)
    assert c.post("/webhook/telegram", json=_update(1, text="hi"),
                  headers={"X-Telegram-Bot-Api-Secret-Token": "x"}).status_code == 403
    assert c.get("/api/health").json()["telegram"] is False
