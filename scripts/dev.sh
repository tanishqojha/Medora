#!/usr/bin/env bash
# Start api, worker and web natively (S1). Ctrl+C stops all three.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "Missing .env. Copy .env.example and fill DATABASE_URL (session pooler, port 5432)."; exit 1; }
trap 'kill 0' EXIT
(cd api && uv run uvicorn medora.app:app --reload --port 8000) &
(uv run --project api python worker/worker.py) &
(cd web && npm run dev) &
wait
