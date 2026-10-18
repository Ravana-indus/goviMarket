"""A picked language wins: replies stay in it whatever language the sender writes, speaks or photographs in."""
from app import accounts, main, store
from tests.test_conversations import TOMORROW, TODAY, P, Phone, g  # noqa: F401  (g is the fixture)


def test_picked_language_wins_over_the_message_language(g):
    shop = Phone("94771100001", g)
    main.handle(text="hi", media=None, mime_type=None, sender=shop.number, today=TODAY, via="sim", lang="si")
    r = shop.say("need tomato 10kg tomorrow", P(lang="en", items={"tomato": 10}, when=TOMORROW))
    assert "ඔබේ ඇණවුම පරීක්ෂා කරන්න" in r  # English message, Sinhala reply
    r = shop.say(None, P(lang="ta", intent="edit", items={"carrot": 2}), media=b"\xff\xd8", mime="image/jpeg")
    assert "කැරට්" in r and "கேரட்" not in r  # Tamil photo, still Sinhala


def test_language_message_switches_the_chat_and_the_account(g):
    shop = Phone("94771100002", g)
    assert shop.say("தமிழ்").startswith("சரி.")
    assert accounts.chosen_lang(shop.number) == "ta"
    r = shop.say("need beans 5kg", P(lang="en", items={"beans": 5}))
    assert "உங்கள் ஆர்டரை" in r
    assert "language you write in" in shop.say("language auto")
    assert accounts.chosen_lang(shop.number) is None


def test_switching_language_moves_open_orders_too(g):
    shop = Phone("94771100003", g)
    shop.say("need tomato 10kg", P(items={"tomato": 10}))
    shop.say("yes")
    assert shop.orders()[0].lang == "en"
    accounts.set_lang(shop.number, "si")
    assert [o.lang for o in shop.orders()] == ["si"]


def test_profile_language_from_settings_applies_to_chat(g):
    shop = Phone("94771100004", g)
    store.DB.put("users", shop.number, {"phone": shop.number, "name": "Kavi", "role": "buyer", "lang": "ta"})
    assert "உங்கள் ஆர்டரை" in shop.say("need tomato 10kg", P(lang="en", items={"tomato": 10}))
