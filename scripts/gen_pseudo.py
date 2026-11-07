"""Write a SYNTHETIC pseudo dataset for manual testing into data/pseudo (git-ignored).

Run: uv run --project api python scripts/gen_pseudo.py [--patients 300] [--seed 7]
Covers every pathway scenario (on time, late, missed, silent, not yet due) with corrupted
registers (typos, dd/mm swaps, Devanagari, duplicates) plus three register photos.
"""
import argparse
import json
from pathlib import Path

from medora.synth import build

ap = argparse.ArgumentParser()
ap.add_argument("--patients", type=int, default=300)
ap.add_argument("--seed", type=int, default=7)
a = ap.parse_args()
out = Path(__file__).resolve().parent.parent / "data" / "pseudo"
out.mkdir(parents=True, exist_ok=True)
ds = build(out, n_patients=a.patients, seed=a.seed)
print(json.dumps({"synthetic": True, "rows": len(ds.rows), "out": str(out)}))
