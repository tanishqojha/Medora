"""Safety harness runner (F15). Exit 1 if any case is not routed to a person. Run in CI.

Usage: uv run --project api python safety_harness/run.py [--record]
--record writes an eval_run (kind 'harness') for the Trust screen. Needs DATABASE_URL.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

from medora import tripwire

CASES = Path(__file__).parent / "cases"


def load() -> list[dict]:
    out = []
    for f in sorted(CASES.glob("*.yaml")):
        doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        out += [{**c, "file": f.name, "status": doc.get("status")} for c in doc["cases"]]
    return out


def run() -> dict:
    results = []
    for c in load():
        r = tripwire.check(c["text"])
        results.append({"id": c["id"], "routed": r.routed, "route": r.route, "expected": c["expected_route"],
                        "categories": r.categories})
    routed = sum(r["routed"] for r in results)
    exact = sum(r["route"] == r["expected"] for r in results)
    return {"cases": len(results), "routed": routed, "route_match": exact, "results": results,
            "failures": [r for r in results if not r["routed"]]}


def main() -> int:
    res = run()
    for f in res["failures"]:
        print(f"NOT ROUTED: {f['id']}")
    print(f"harness: {res['routed']}/{res['cases']} routed to a person, {res['route_match']} to the expected role")
    if "--record" in sys.argv:
        from medora import evals
        from medora.db import tx

        with tx() as conn:
            run_id = evals.record(conn, "harness", [
                evals.Metric("routed_to_human_rate", res["routed"] / res["cases"], 1.0),
                evals.Metric("expected_route_rate", res["route_match"] / res["cases"]),
                evals.Metric("cases", float(res["cases"]))], summary={"failures": res["failures"], "draft": True})
        print(f"recorded eval run {run_id}")
    return 0 if not res["failures"] else 1


if __name__ == "__main__":
    sys.exit(main())
