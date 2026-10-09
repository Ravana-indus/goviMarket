# Govi Market

Sri Lankan farmers sell straight to restaurants, hotels and exporters. Anyone can send an order or a harvest update in any form: a photo of a handwritten order, a Sinhala voice note, or a WhatsApp text. Gemini reads it. Govi matches supply to demand, ships it on night buses, trains or Sri Lanka Post, and shows how much more the farmer earns than the village collector pays.

Built for the AI Builder Cup 2026 (Sustainability & Social Impact).

## How it works
1. `POST /intake` takes text and/or a photo or voice note. Gemini returns structured JSON (`app/parser.py`, schema in `app/schemas.py`).
2. The message becomes a harvest listing (farmer) or an order (buyer) (`app/store.py`).
3. `POST /plan` runs the matcher (`app/matcher.py`). It fills the earliest deadlines first, from the farm that nets the farmer the most after transport. The lane picker (`app/lanes.py`) uses the cheapest public transport that lands by 08:00 on the needed-by day.
4. Leftover stock comes back as `surplus`, ready to route to processors or exporters.

## Run locally
```bash
pip install -r requirements.txt
cp .env.example .env   # add GEMINI_API_KEY
export $(cat .env | xargs) && uvicorn app.main:app --reload
pytest -q
```

## Deploy (Cloud Run)
```bash
gcloud run deploy govi-market --source . --region asia-south1 \
  --set-env-vars GEMINI_API_KEY=...,GEMINI_MODEL=gemini-2.5-flash --allow-unauthenticated
```

## Data status
`data/lanes.json` and `data/prices.json` are **placeholders** until the field-checked transport rates and HARTI daily prices are filled in.
