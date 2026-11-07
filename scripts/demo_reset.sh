#!/usr/bin/env bash
# S22: fresh SYNTHETIC demo tenant, harness and evals rerun so the Trust screen is current.
# Usage: scripts/demo_reset.sh "Dr. Name" [--bench]
set -euo pipefail
cd "$(dirname "$0")/.."
[ $# -ge 1 ] || { echo 'Usage: scripts/demo_reset.sh "Clinical Lead name" [--bench]'; exit 1; }
name="$1"; shift
uv run --project api python scripts/demo_reset.py --signed-by "$name" "$@"
