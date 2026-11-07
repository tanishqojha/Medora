#!/usr/bin/env bash
# Migrate the database and load the SYNTHETIC demo tenant.
# Usage: scripts/seed.sh "Dr. Name"   (the clinical lead who signs the demo pathway)
set -euo pipefail
cd "$(dirname "$0")/.."
[ $# -ge 1 ] || { echo 'Usage: scripts/seed.sh "Clinical Lead name"'; exit 1; }
(cd api && uv run alembic upgrade head)
uv run --project api python scripts/demo_reset.py --signed-by "$1"
