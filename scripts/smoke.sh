#!/usr/bin/env bash
# Quick check of a deployed URL: ./scripts/smoke.sh https://govi-market-xxxx.a.run.app
set -euo pipefail
URL="${1:?deployed URL}"
ok() { printf '  %-28s %s\n' "$1" "$2"; }
H="$(curl -fsS "$URL/healthz")"; ok healthz "$H"
echo "$H" | grep -q '"gemini":true' || echo "  WARNING: Gemini key not loaded"
echo "$H" | grep -q '"admin_locked":true' || echo "  WARNING: console is open (ADMIN_TOKEN missing)"
for p in / /business /agent /sim /login /api/prices; do
  ok "$p" "$(curl -s -o /dev/null -w '%{http_code}' "$URL$p")"
done
ok "/state without token" "$(curl -s -o /dev/null -w '%{http_code}' "$URL/state") (want 401)"
ok "sim text message" "$(curl -s -o /dev/null -w '%{http_code}' -F text='This is Sunil, carrot 50kg ready tomorrow, Nuwara Eliya' -F sender=94770000099 -F via=sim "$URL/intake")"
