"""S15: fetch Synthea once and generate base patients (sex, birth date). Prints the patients.csv path.

Usage: uv run --project api python scripts/get_synthea.py [--patients 400] [--seed 42]
Needs Java 11+. The jar (~200 MB) goes to tools/ (git-ignored). Names and phones are replaced by synth.py.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
JAR_URL = "https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patients", type=int, default=400)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    if not shutil.which("java"):
        print("Java 11+ is required to run Synthea.")
        return 1
    TOOLS.mkdir(exist_ok=True)
    jar = TOOLS / "synthea-with-dependencies.jar"
    if not jar.exists():
        print("downloading Synthea (~200 MB) ...")
        part = jar.with_suffix(".part")
        urllib.request.urlretrieve(JAR_URL, part)
        part.replace(jar)
    out = TOOLS / f"synthea_{a.patients}_{a.seed}"
    csv = out / "csv" / "patients.csv"
    if not csv.exists():
        subprocess.run(["java", "-jar", str(jar), "-p", str(a.patients), "-s", str(a.seed), "-cs", str(a.seed),
                        "--exporter.baseDirectory", str(out), "--exporter.csv.export", "true",
                        "--exporter.fhir.export", "false", "--exporter.hospital.fhir.export", "false",
                        "--exporter.practitioner.fhir.export", "false"], check=True, cwd=TOOLS)
    print(csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
