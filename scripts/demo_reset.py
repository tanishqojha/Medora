"""S22: reset the demo. Everything created here is SYNTHETIC.

Events and the audit log are append-only, so the old demo tenant is never deleted. A fresh tenant is created
and logins resolve to the newest one.

Usage: uv run --project api python scripts/demo_reset.py --signed-by "Dr. Name" [--bench]
--signed-by is the clinical lead who signs the GI pathway version for this demo tenant. A person must pass it.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

from _lib import REGISTER_MAPPING, ROOT, drain, plan, preconfirm, upload

from medora import audit, callassist, pathways, seed, synth
from medora.db import tx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--signed-by", required=True, help="name of the clinical lead signing the demo pathway")
    ap.add_argument("--bench", action="store_true", help="also run the 10k/100k benchmark (slow)")
    ap.add_argument("--synthea", type=Path, help="patients.csv from scripts/get_synthea.py for base demographics")
    args = ap.parse_args()

    data = ROOT / "data" / "demo"
    ds = synth.build(data, n_patients=400, seed=42, as_of=date.today(), photos=3, mix=synth.DEMO_SCENARIOS,
                     synthea_csv=args.synthea)
    # A new file shape for the live mapping beat (demo beat 2): same facts, different headers.
    new_shape = data / "opd_list_new_shape.csv"
    rows = [r for r in ds.rows if r["truth_event_type"] != "tb_decision_recorded"][:300]
    new_shape.write_text("Pt Name,Contact,CR No,Visit Dt,Clinic,Attendance\n" + "".join(
        f"{r['Patient Name']},{r['Mobile No']},{r['UHID']},{r['Date']},{r['Department']},{r['Status']}\n" for r in rows),
        encoding="utf-8")

    with tx() as conn:
        hid = seed.create_hospital(conn, f"Kronex Demo Hospital (synthetic, reset {date.today().isoformat()})")
        versions = seed.register_pathways(conn, hid, ("gi_cancer_handover.v1", "breast_handover_demo.v1"))
        gi = versions["gi_cancer_handover.v1"]
        pathways.sign(conn, hid, gi["id"], args.signed_by, "clinical_lead")
        pathways.activate(conn, hid, gi["id"], args.signed_by)
        audit.append(conn, hid, "demo_reset", "demo.reset", "hospital", hid, {"signed_by": args.signed_by})

    preconfirm(hid, synth.HEADERS, REGISTER_MAPPING, "Data Steward (synthetic, demo reset)")
    for key in ("register_csv", "register_xlsx"):
        job = upload(hid, Path(ds.files[key]), "Data Steward (synthetic)")
        plan(job["id"])
    drain()

    # Contact history so every flag kind shows up: three unanswered calls make one patient unreachable.
    with tx() as conn:
        flags = conn.execute("SELECT id FROM flags WHERE hospital_id = %s AND state = 'open' ORDER BY created_at LIMIT 2",
                             (hid,)).fetchall()
    for _ in range(3):
        with tx() as conn:
            att = callassist.record_attempt(conn, hid, str(flags[0]["id"]), "Meera (Care Coordinator)")
        callassist.record_outcome(hid, att, "no_answer", "tap", "Meera (Care Coordinator)")

    from medora.app import record_replay

    with tx() as conn:
        record_replay(conn, hid)
        audit_ok = audit.verify_chain(conn, hid)
        from medora import evals
        evals.record(conn, "audit_chain", [evals.Metric("chain_valid", 1.0 if audit_ok["valid"] else 0.0, 1.0),
                                           evals.Metric("entries_checked", float(audit_ok["checked"]))],
                     summary=audit_ok, hospital_id=hid)
    py = [sys.executable]
    subprocess.run(py + [str(ROOT / "safety_harness" / "run.py"), "--record"], check=True)
    subprocess.run(py + [str(ROOT / "eval" / "run_eval.py"), "--record"], check=False)
    subprocess.run(py + [str(ROOT / "eval" / "run_llm_eval.py"), "--record"], check=False)
    if args.bench:
        subprocess.run(py + [str(ROOT / "scripts" / "bench.py")], check=False)
    with tx() as conn:
        n = conn.execute("SELECT count(*) AS n FROM flags WHERE hospital_id = %s AND state = 'open'", (hid,)).fetchone()["n"]
    print(f"\nDemo tenant ready: {hid}\nOpen flags: {n}\nLog in as meera@medora.test (password from SEED_PASSWORD, "
          f"default medora-demo).\nLive mapping beat file: {new_shape}\nPhotos: {data}/register_photo_*.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
