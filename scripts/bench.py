"""S17: MVP ingest benchmark on 10k and 100k row SYNTHETIC files. Results go to eval_runs (kind 'bench').

Measures rows, wall time, peak process memory, LLM calls, and time to finish after a kill mid-run.
These are MVP numbers on the MVP setup. Larger sizes are production scope and are not measured here.
Usage: uv run --project api python scripts/bench.py [--sizes 10000,100000]
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import psutil  # dev dependency (via pgserver); only this script uses it
from _lib import REGISTER_MAPPING, drain, plan, preconfirm, upload

from medora import evals, ingest, seed, synth
from medora.config import database_url
from medora.db import one, tx


def peak_mb() -> float:
    info = psutil.Process().memory_info()
    return getattr(info, "peak_wset", getattr(info, "rss", 0)) / 1e6


def run(n: int, out: Path) -> list[evals.Metric]:
    path = out / f"bench_{n}.csv"
    synth.stream_big_csv(path, n, seed=99, as_of=date(2026, 10, 10))
    with tx() as conn:
        hid = seed.create_hospital(conn, f"Benchmark {n} rows (synthetic)", with_users=False)
    preconfirm(hid, synth.HEADERS, REGISTER_MAPPING, "bench")
    t0 = time.monotonic()
    job = plan(upload(hid, path, "bench")["id"])
    half = max(1, job["total_chunks"] // 2)
    drain(stop_after=half)
    with tx() as conn:  # kill mid-run, then resume
        ingest.control(conn, hid, str(job["id"]), "kill", "bench")
        ingest.control(conn, hid, str(job["id"]), "resume", "bench")
    t_resume = time.monotonic()
    drain()
    # A running worker may hold the last chunks; wait for the job, never assume this process did all the work.
    deadline = time.monotonic() + 600
    while True:
        with tx() as conn:
            j = one(conn, "SELECT * FROM ingest_jobs WHERE id = %s", (job["id"],))
        if j["state"] == "done" or time.monotonic() > deadline:
            break
        time.sleep(0.5)
    t1 = time.monotonic()
    assert j["state"] == "done", j["state"]
    p = f"rows_{n // 1000}k"
    return [evals.Metric(f"{p}_seconds", round(t1 - t0, 2), higher_is_better=False),
            evals.Metric(f"{p}_rows_per_second", round(n / (t1 - t0), 1)),
            evals.Metric(f"{p}_peak_memory_mb", round(peak_mb(), 1), higher_is_better=False),
            evals.Metric(f"{p}_llm_calls", float(j["llm_calls"]), higher_is_better=False),
            evals.Metric(f"{p}_resume_seconds", round(t1 - t_resume, 2), higher_is_better=False),
            evals.Metric(f"{p}_rows_loaded", float(j["rows_loaded"])),
            evals.Metric(f"{p}_rows_review", float(j["rows_review"]))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default="10000,100000")
    args = ap.parse_args()
    out = Path(tempfile.mkdtemp(prefix="medora_bench_"))
    metrics: list[evals.Metric] = []
    for n in [int(x) for x in args.sizes.split(",")]:
        metrics += run(n, out)
        print({m.metric: m.value for m in metrics})
    with tx() as conn:
        host = urlparse(database_url()).hostname or ""
        where = ("Supabase session pooler" if "supabase" in host else
                 "local Postgres on the developer machine" if host in ("127.0.0.1", "localhost") else host)
        run_id = evals.record(conn, "bench", metrics, summary={
            "mvp": True, "database": where, "worker_running": False,
            "note": f"Synthetic files. Database: {where}. Peak memory is this process, including generating the file."})
    print("recorded bench run", run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
