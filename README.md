# Govi Market

Sri Lankan farmers sell straight to restaurants, hotels and exporters. Anyone can send an order or a harvest update in any form: a photo of a handwritten order, a Sinhala voice note, or a WhatsApp text. Gemini reads it. Govi matches supply to demand, ships it on night buses, trains or Sri Lanka Post, and shows how much more the farmer earns than the village collector pays.

Built for the AI Builder Cup 2026 (Sustainability & Social Impact).

## How it works
1. `POST /webhook/whatsapp` (WhatsApp Cloud API) or `POST /intake` (web) takes text and/or a photo or voice note. Farmers, buyers and market price reporters all use the same pipeline. Gemini returns structured JSON (`app/parser.py`, schema in `app/schemas.py`).
2. The message becomes a harvest listing (farmer) or an order (buyer) (`app/store.py`).
3. `POST /plan` runs the matcher, then bundles loads leaving the same town on the same day into one consignment (cheapest bus, train or lorry for the combined weight; fixed loading and Colombo pickup paid once; each farmer's share cut by the same ratio, so nobody pays more than shipping alone) (`app/matcher.py`). It fills the earliest deadlines first, from the farm that nets the farmer the most after transport. The lane picker (`app/lanes.py`) uses the cheapest public transport that lands by 08:00 on the needed-by day.
4. Leftover stock comes back as `surplus`, ready to route to processors or exporters.

## Pages
| URL | Who | Notes |
|---|---|---|
| `/` | Farmers | Main input: harvest form (crop, kg, ready day, town). Matching runs at once. |
| `/business` | Restaurants, hotels | Orders, weekly standing orders, forecast. |
| `/agent` | Market agents | Phone-first price entry; needs `AGENT_PIN`. |
| `/admin` | Operations | Console and analytics; needs `ADMIN_TOKEN` (sign in at `/login`). |
| `/sim` (also `/smul`) | Demo and testing | WhatsApp simulator: text, photos and voice notes go through the same pipeline as the real webhook, and every reply Govi sends to that number shows up in the chat. |

## Run locally (no keys needed)
```bash
pip install -r requirements-dev.txt
uvicorn app.main:app --port 8000
pytest -q
```
Open http://localhost:8000/admin, click **Load demo morning**, then try http://localhost:8000/sim. Without `GEMINI_API_KEY` a keyword demo parser reads simple English text; photos and voice notes need the key. Copy `.env.example` to `.env` to set keys and logins.

## Deploy (Cloud Run + Firestore)
```bash
gcloud auth login
PROJECT_ID=<your-project-id> ./scripts/deploy.sh
./scripts/smoke.sh https://<cloud-run-url>
```
The script enables the APIs, creates Firestore, asks for the Gemini key (hidden input) and stores it in Secret Manager, generates the console token and agent PIN (printed once), deploys with `--max-instances=1 --min-instances=0` and request-based billing (add `WHATSAPP=1` for the real WhatsApp webhook, which needs CPU kept on after it replies), and schedules `POST /jobs/daily` at 06:00 Colombo time for standing orders and unsold-produce alerts.

- One instance only: the Firestore store keeps a write-through cache in memory.
- `ALLOW_RESET=1` keeps the demo reset button working. Deploy with `ALLOW_RESET=0` before real users arrive.
- Real WhatsApp (optional): add `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN` and `WHATSAPP_APP_SECRET`, then set the Meta webhook to `https://<cloud-run-url>/webhook/whatsapp` and subscribe to `messages`.

## Data status
`data/lanes.json` and `data/prices.json` are **placeholders** until the field-checked transport rates and HARTI daily prices are filled in.
