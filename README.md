# Govi Market

Sri Lankan farmers sell straight to restaurants, hotels and exporters. Anyone can send an order or a harvest update in any form: a photo of a handwritten order, a Sinhala voice note, or a WhatsApp text. Gemini reads it. Govi matches supply to demand, ships it on night buses, trains or Sri Lanka Post, and shows how much more the farmer earns than the village collector pays.

Built for the AI Builder Cup 2026 (Sustainability & Social Impact).

## How it works
1. `POST /webhook/whatsapp` (WhatsApp Cloud API) or `POST /intake` (web) takes text and/or a photo or voice note. Farmers, buyers and market price reporters all use the same pipeline. Gemini returns structured JSON (`app/parser.py`, schema in `app/schemas.py`).
2. The message becomes a harvest listing (farmer) or an order (buyer) (`app/store.py`).
3. `POST /plan` runs the matcher (`app/matcher.py`). It fills the earliest deadlines first, from the farm that nets the farmer the most after transport. The lane picker (`app/lanes.py`) uses the cheapest public transport that lands by 08:00 on the needed-by day.
4. Leftover stock comes back as `surplus`, ready to route to processors or exporters.

## Preview locally (no keys needed)
```bash
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```
Open http://localhost:8000/admin and click **Load demo morning**, then **Run matching**. The farmer and buyer web app is at http://localhost:8000/. Without `GEMINI_API_KEY` a keyword demo parser reads simple English text; photos and voice notes need the key.

## Run locally with Gemini
```bash
pip install -r requirements.txt
cp .env.example .env   # add GEMINI_API_KEY
export $(cat .env | xargs) && uvicorn app.main:app --reload
pytest -q
```

## Deploy (Cloud Run)
```bash
gcloud firestore databases create --location=asia-south1   # once per project
gcloud run deploy govi-market --source . --region asia-south1 --allow-unauthenticated \
  --no-cpu-throttling \
  --set-env-vars STORE=firestore,GEMINI_MODEL=gemini-2.5-flash \
  --set-env-vars GEMINI_API_KEY=...,WHATSAPP_TOKEN=...,WHATSAPP_PHONE_NUMBER_ID=...,WHATSAPP_VERIFY_TOKEN=...,WHATSAPP_APP_SECRET=...
```
`--no-cpu-throttling` keeps CPU on after the webhook acks Meta, so the Gemini call and reply can finish in the background.

Then, in the Meta app's WhatsApp settings, set the webhook URL to `https://<cloud-run-url>/webhook/whatsapp`, enter the verify token, and subscribe to `messages`.

```bash
# smoke test
curl -F text="carrots 200kg ready Thursday, Nuwara Eliya" https://<cloud-run-url>/intake
```

## Data status
`data/lanes.json` and `data/prices.json` are **placeholders** until the field-checked transport rates and HARTI daily prices are filled in.
