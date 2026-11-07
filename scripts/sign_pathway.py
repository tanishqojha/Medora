"""Record a clinician sign-off for a pathway version, then activate it. Run by a person, never by Claude Code.

Usage: uv run --project api python scripts/sign_pathway.py --hospital <id> --pathway gi_cancer_handover --version 1 --by "Dr. Name"
"""
from __future__ import annotations

import argparse
import sys

from _lib import ROOT  # noqa: F401  (puts api/ on sys.path)

from medora import engine, pathways
from medora.db import one, tx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hospital", required=True)
    ap.add_argument("--pathway", required=True)
    ap.add_argument("--version", type=int, required=True)
    ap.add_argument("--by", required=True, help="full name of the clinical lead signing")
    ap.add_argument("--no-activate", action="store_true")
    a = ap.parse_args()
    with tx() as conn:
        v = one(conn, """SELECT v.* FROM pathway_versions v JOIN pathways p ON p.id = v.pathway_id
                         WHERE v.hospital_id = %s AND p.key = %s AND v.version = %s""", (a.hospital, a.pathway, a.version))
        pathways.sign(conn, a.hospital, v["id"], a.by, "clinical_lead")
        if not a.no_activate:
            pathways.activate(conn, a.hospital, v["id"], a.by)
            v = one(conn, "SELECT * FROM pathway_versions WHERE id = %s", (v["id"],))
            print("evaluated:", engine.evaluate(conn, a.hospital, v, actor=a.by))
    print(f"signed {a.pathway} v{a.version} by {a.by}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
