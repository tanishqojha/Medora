#!/usr/bin/env bash
# Migrate the database and load the SYNTHETIC demo tenant.
# Usage: scripts/seed.sh ["Dr. Name"]   (the clinical lead who signs the demo pathway; omit to leave it unsigned)
set -euo pipefail
cd "$(dirname "$0")/.."
(cd api && uv run alembic upgrade head)
uv run --project api python scripts/demo_reset.py ${1:+--signed-by "$1"}
