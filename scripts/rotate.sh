#!/usr/bin/env bash
# Replace the console token and agent PIN, roll Cloud Run onto them, and update the daily job.
#   PROJECT_ID=my-project ./scripts/rotate.sh
# The new values print once here. Keep them out of chats.
set -euo pipefail
PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"; REGION="${REGION:-asia-south1}"; SERVICE="${SERVICE:-govi-market}"
gc() { gcloud --project "$PROJECT_ID" "$@"; }
TOKEN="$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)"
PIN="$(printf '%06d' $(( $(od -An -N4 -tu4 /dev/urandom) % 1000000 )))"
printf '%s' "$TOKEN" | gc secrets versions add ADMIN_TOKEN --data-file=- >/dev/null
printf '%s' "$PIN" | gc secrets versions add AGENT_PIN --data-file=- >/dev/null
# A new revision makes Cloud Run read the latest secret versions.
gc run services update "$SERVICE" --region "$REGION" \
  --update-secrets "ADMIN_TOKEN=ADMIN_TOKEN:latest,AGENT_PIN=AGENT_PIN:latest" \
  --update-labels "rotated=$(date +%Y%m%d%H%M)" >/dev/null
gc scheduler jobs update http govi-daily --location "$REGION" --update-headers "X-Admin-Token=$TOKEN" >/dev/null
echo "New console token: $TOKEN"
echo "New market agent PIN: $PIN"
