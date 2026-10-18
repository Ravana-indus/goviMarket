#!/usr/bin/env bash
# Live test run against the deployed app, with real Gemini. Run it from Cloud Shell (or any machine
# that can reach the URL):
#   bash scripts/e2e/live.sh https://govi-market-703957013605.asia-south1.run.app
# Writes e2e-live-*.md (every conversation) and parse-score-live-*.md (Gemini accuracy) here.
# Uses fresh 9400099xxxxx test numbers, never resets data, never sends an admin token.
set -uo pipefail
URL="${1:-https://govi-market-703957013605.asia-south1.run.app}"
cd "$(dirname "$0")/../.."
python3 -c "import httpx" 2>/dev/null || python3 -m pip install --user -q httpx
echo "== health"; curl -sS "$URL/api/health"; echo
echo "== conversations (about 10 minutes)"
python3 scripts/e2e/run.py "$URL" --out "e2e-live-$(date +%Y%m%d-%H%M).md"
echo "== Gemini parsing score (about 2 minutes)"
python3 scripts/e2e/score_parse.py "$URL" --out "parse-score-live-$(date +%Y%m%d-%H%M).md"
echo "Done. Share the two .md files (or paste them into the project)."
