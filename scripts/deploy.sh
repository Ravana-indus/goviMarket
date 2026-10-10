#!/usr/bin/env bash
# Deploy Govi Market to Cloud Run with Firestore and Secret Manager.
#   PROJECT_ID=my-project ./scripts/deploy.sh
# Safe to re-run: existing secrets, database and scheduler job are kept.
# It asks for the Gemini key without echoing it. The console token and agent PIN are
# generated on first run and printed once; read them later with:
#   gcloud secrets versions access latest --secret=ADMIN_TOKEN
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-asia-south1}"
SERVICE="${SERVICE:-govi-market}"
ALLOW_RESET="${ALLOW_RESET:-1}"   # 1 keeps the demo reset button; set 0 once real users arrive
# Request-based billing (cheapest, fits the free tier). Real WhatsApp replies run after the webhook
# returns, so they need CPU kept on: WHATSAPP=1 ./scripts/deploy.sh
CPU_FLAG="--cpu-throttling"; [ "${WHATSAPP:-0}" = "1" ] && CPU_FLAG="--no-cpu-throttling"
gc() { gcloud --project "$PROJECT_ID" "$@"; }

echo "== APIs"
gc services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  firestore.googleapis.com secretmanager.googleapis.com cloudscheduler.googleapis.com

echo "== Firestore"
gc firestore databases describe --database="(default)" >/dev/null 2>&1 \
  || gc firestore databases create --location="$REGION" --type=firestore-native

secret() {  # secret NAME VALUE: create once, never overwrite
  if gc secrets describe "$1" >/dev/null 2>&1; then return 1; fi
  printf '%s' "$2" | gc secrets create "$1" --replication-policy=automatic --data-file=-
}

echo "== Secrets"
if ! gc secrets describe GEMINI_API_KEY >/dev/null 2>&1; then
  read -rsp "Gemini API key (input hidden): " KEY; echo
  [ -n "$KEY" ] || { echo "no key given"; exit 1; }
  secret GEMINI_API_KEY "$KEY"; unset KEY
fi
NEW_TOKEN="$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)"
NEW_PIN="$(printf '%06d' $(( $(od -An -N4 -tu4 /dev/urandom) % 1000000 )))"
secret ADMIN_TOKEN "$NEW_TOKEN" && echo "Console token (keep it safe): $NEW_TOKEN" || true
secret AGENT_PIN "$NEW_PIN" && echo "Market agent PIN: $NEW_PIN" || true

PROJECT_NUMBER="$(gc projects describe "$PROJECT_ID" --format='value(projectNumber)')"
RUN_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
for s in GEMINI_API_KEY ADMIN_TOKEN AGENT_PIN; do
  gc secrets add-iam-policy-binding "$s" --member="serviceAccount:$RUN_SA" \
    --role=roles/secretmanager.secretAccessor >/dev/null
done
gc projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$RUN_SA" \
  --role=roles/datastore.user --condition=None >/dev/null

echo "== Firebase phone sign-in"
# The Firebase web config (apiKey) is public by design: it ships to every browser. Not a secret.
# Read it from the project's first Firebase web app, or pass FIREBASE_API_KEY yourself.
fb_api() { curl -fsS -H "Authorization: Bearer $(gcloud auth print-access-token)" -H "x-goog-user-project: $PROJECT_ID" "$@"; }
FIREBASE_API_KEY="${FIREBASE_API_KEY:-}"
if [ -z "$FIREBASE_API_KEY" ]; then
  APP_ID="$(fb_api "https://firebase.googleapis.com/v1beta1/projects/$PROJECT_ID/webApps" 2>/dev/null \
    | python3 -c 'import sys,json; a=json.load(sys.stdin).get("apps",[]); print(a[0]["appId"] if a else "")' || true)"
  [ -n "$APP_ID" ] && FIREBASE_API_KEY="$(fb_api "https://firebase.googleapis.com/v1beta1/projects/$PROJECT_ID/webApps/$APP_ID/config" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin).get("apiKey",""))' || true)"
fi
if [ -n "$FIREBASE_API_KEY" ]; then echo "Firebase web app found: SMS sign-in on"
else echo "No Firebase web app yet: sign-in uses demo numbers and console codes. Add a web app in the Firebase console and re-run."; fi

echo "== Cloud Run"
# max-instances=1: the store caches Firestore in memory, so a second instance would read stale data.
gc run deploy "$SERVICE" --source . --region "$REGION" --allow-unauthenticated \
  --max-instances=1 --min-instances=0 "$CPU_FLAG" --memory=512Mi --timeout=120 \
  --set-env-vars "STORE=firestore,ALLOW_RESET=$ALLOW_RESET,GEMINI_MODEL=${GEMINI_MODEL:-gemini-2.5-flash},GOOGLE_CLOUD_PROJECT=$PROJECT_ID,FIREBASE_PROJECT_ID=$PROJECT_ID,FIREBASE_API_KEY=$FIREBASE_API_KEY,ADMIN_PHONES=${ADMIN_PHONES:-}" \
  --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest,ADMIN_TOKEN=ADMIN_TOKEN:latest,AGENT_PIN=AGENT_PIN:latest"
URL="$(gc run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"

if [ -n "$FIREBASE_API_KEY" ]; then
  echo "== Firebase authorized domain for $URL"
  HOST="${URL#https://}"
  CFG="https://identitytoolkit.googleapis.com/admin/v2/projects/$PROJECT_ID/config"
  DOMAINS="$(fb_api "$CFG" | HOST="$HOST" python3 -c 'import sys,json,os; d=json.load(sys.stdin).get("authorizedDomains",[]); h=os.environ["HOST"]; print(json.dumps({"authorizedDomains": d if h in d else d+[h]}))' || true)"
  if [ -n "$DOMAINS" ] && fb_api -X PATCH -H "Content-Type: application/json" "$CFG?updateMask=authorizedDomains" -d "$DOMAINS" >/dev/null; then
    echo "$HOST can use Firebase sign-in"
  else
    echo "Could not add $HOST automatically: add it in Firebase console > Authentication > Settings > Authorized domains"
  fi
fi

echo "== Daily job (06:00 Colombo): standing orders and unsold-produce alerts"
TOKEN="$(gc secrets versions access latest --secret=ADMIN_TOKEN)"
JOB=(--location "$REGION" --schedule "0 6 * * *" --time-zone "Asia/Colombo" --uri "$URL/jobs/daily"
     --http-method POST)
gc scheduler jobs update http govi-daily "${JOB[@]}" --update-headers "X-Admin-Token=$TOKEN" >/dev/null 2>&1 \
  || gc scheduler jobs create http govi-daily "${JOB[@]}" --headers "X-Admin-Token=$TOKEN" >/dev/null
unset TOKEN

echo "== Done: $URL"
curl -fsS "$URL/healthz"; echo
echo "Console: $URL/admin   Simulator: $URL/sim   Agents: $URL/agent   Buyers: $URL/business"
