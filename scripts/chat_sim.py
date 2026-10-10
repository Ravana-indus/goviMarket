"""Play scripted WhatsApp conversations against a running Govi and print the transcripts.

    python scripts/chat_sim.py https://<cloud-run-url>     # live site, real Gemini
    python scripts/chat_sim.py                             # in-process, keyword parser, no key

Each conversation uses its own fresh simulator number, so it never touches real users. Read the
replies: language, items, dates, and that nothing is placed before YES."""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CONVERSATIONS = {
    "Tamil order, then YES (the bug)": [
        "நாளைக்கு 5 கிலோ வெங்காயம், 10 கிலோ தக்காளி, 2 கிலோ கேரட், 5 கிலோ லீக்ஸ் மற்றும் 2 கிலோ கோவா தேவை",
        "YES", "YES", "STATUS"],
    "English order with corrections": [
        "need tomato 10kg and carrot 5kg tomorrow", "make tomato 15kg", "remove carrot, add 3kg beans",
        "deliver to Kandy", "ok"],
    "Sinhala farmer without a town": ["කැරට් කිලෝ 200 හෙට", "YES", "දඹුල්ල", "ඔව්"],
    "Singlish farmer": ["thakkali kilo 150 heta dambulla", "hari"],
    "Changed mind": ["need leeks 20kg friday", "NO", "NO"],
    "New order replaces the unplaced one": ["need beans 20kg", "actually I need leeks 8kg on Friday instead", "YES"],
    "Small talk": ["hi", "வணக்கம்", "need tomato 5kg", "thanks", "YES", "cancel"],
    "Unknown crop": ["need durian 5kg", "need durian 5kg and tomato 2kg", "yes"],
}


def run(base: str | None) -> None:
    if base:
        import httpx
        client = httpx.Client(base_url=base.rstrip("/"), timeout=90)
    else:
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
    for title, lines in CONVERSATIONS.items():
        phone = "9477" + str(random.randint(1000000, 9999999))
        print(f"\n=== {title}  (+{phone})")
        for text in lines:
            r = client.post("/intake", data={"text": text, "sender": phone, "via": "sim"})
            reply = r.json().get("reply") if r.status_code == 200 else f"[HTTP {r.status_code}] {r.text[:200]}"
            print(f"> {text}\n" + "\n".join("  " + l for l in (reply or "").splitlines()))
            time.sleep(0.2 if base else 0)
        thread = client.get("/api/sim/thread", params={"phone": phone}).json()
        offers = [m["text"] for m in thread if m["dir"] == "out"][len(lines):]
        for o in offers:
            print("  [also sent] " + o.replace("\n", "\n              "))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
