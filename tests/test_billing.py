"""Rs 799/month plan for every seller and buyer: due from joining, the console marks months paid."""
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app import billing, main, store
from tests.test_conversations import P, Phone, g  # noqa: F401


def _user(phone, role="buyer", created="2026-10-01"):
    store.DB.put("users", phone, {"phone": phone, "name": "Cafe " + phone[-2:], "role": role, "lang": "",
                                  "created": created + "T00:00:00+00:00"})
    store.DB.delete(billing.KIND, phone)


def test_due_then_overdue_then_paid_for_thirty_days():
    _user("94771400001")
    doc = billing.record("94771400001")
    assert doc["amount_lkr"] == 799 and doc["paid_until"] is None
    assert billing.view(doc, date(2026, 10, 5))["status"] == "due"
    assert billing.view(doc, date(2026, 10, 9))["status"] == "overdue"
    v = billing.mark_paid("94771400001", method="bank transfer", today=date(2026, 10, 9))
    assert v["status"] == "active" and v["paid_until"] == "2026-11-08"
    v = billing.mark_paid("94771400001", today=date(2026, 10, 10))  # paying ahead adds to the paid-up date
    assert v["paid_until"] == "2026-12-08"
    assert billing.undo_last("94771400001")["paid_until"] == "2026-11-08"


def test_agents_have_no_plan():
    _user("94771400002", role="agent")
    assert billing.record("94771400002") is None


def test_console_lists_and_marks_paid():
    _user("94771400003", role="farmer", created=(date.today() - timedelta(days=20)).isoformat())
    c = TestClient(main.app)
    d = c.get("/api/subscriptions").json()
    row = next(r for r in d["rows"] if r["phone"] == "94771400003")
    assert row["status"] == "overdue" and row["owed_lkr"] == 799
    r = c.post("/api/subscriptions/94771400003/paid", json={"method": "cash"}).json()
    assert r["status"] == "active" and r["payments"][-1]["method"] == "cash"
    assert c.post("/api/subscriptions/94770009999/paid").status_code == 404


def test_plan_shows_in_chat(g):
    _user("94771400004")
    shop = Phone("94771400004", g)
    assert "Rs 799/month" in shop.say("PLAN")
    assert "Rs 799/month" in shop.say("status")
