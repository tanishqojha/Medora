"""Medora worker: plans uploaded files and processes chunks (SKIP LOCKED). Run: uv run --project api python worker/worker.py

Safe to kill at any time. Each chunk commits atomically; a chunk left running by a killed worker is
reclaimed after the lease expires and finished chunks are never redone.
"""
from __future__ import annotations

import logging
import os
import signal
import socket
import time

from medora import audit, callassist, evals, graphs, ingest, logs, reviews  # reviews/callassist register gate handlers
from medora.db import one, tx

log = logging.getLogger("medora.worker")
NAME = f"{socket.gethostname()}:{os.getpid()}"
running = True


def _stop(*_: object) -> None:
    global running
    running = False


def plan_next() -> bool:
    with tx() as conn:
        job = conn.execute(
            """SELECT * FROM ingest_jobs WHERE state = 'queued' AND fingerprint IS NULL
               ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1""").fetchone()
        if not job:
            return False
        try:
            with conn.transaction():
                ingest.plan(conn, job)
        except Exception as e:
            log.exception("plan failed", extra={"job_id": str(job["id"])})
            conn.execute("UPDATE ingest_jobs SET state = 'failed', error = %s, updated_at = now() WHERE id = %s",
                         (f"{type(e).__name__}: {e}"[:500], job["id"]))
            audit.append(conn, job["hospital_id"], "worker", "ingest.failed", "ingest_job", job["id"],
                         {"error": type(e).__name__})
            return True
    with tx() as conn:
        job = one(conn, "SELECT * FROM ingest_jobs WHERE id = %s", (job["id"],))
        item = conn.execute("SELECT * FROM review_items WHERE dedupe_key = %s AND hospital_id = %s",
                            (f"mapping:{job['id']}", job["hospital_id"])).fetchone()
    if job["state"] == "needs_mapping" and item:
        p = item["payload"]
        graphs.start("mapping", str(job["hospital_id"]), str(job["id"]),
                     {k: p.get(k) for k in ("fingerprint", "headers", "proposed_by", "prompt_version")})
    return True


def process_next() -> bool:
    with tx() as conn:
        chunk = ingest.claim_chunk(conn, NAME)
    if not chunk:
        return False
    started = time.monotonic()
    try:
        with tx() as conn:
            stats = ingest.process_chunk(conn, chunk)
        log.info("chunk done", extra={"job_id": str(chunk["job_id"]), "seq": chunk["seq"],
                                      "loaded": stats["loaded"], "review": stats["review"],
                                      "ms": int((time.monotonic() - started) * 1000)})
    except Exception as e:
        log.exception("chunk failed", extra={"job_id": str(chunk["job_id"]), "seq": chunk["seq"]})
        with tx() as conn:
            ingest.fail_chunk(conn, chunk["id"], f"{type(e).__name__}: {e}")
            conn.execute("UPDATE ingest_jobs SET error = %s, updated_at = now() WHERE id = %s",
                         (f"chunk {chunk['seq']} failed: {type(e).__name__}"[:500], chunk["job_id"]))
    return True


def housekeeping() -> None:
    with tx() as conn:
        n = reviews.escalate_overdue(conn)
    if n:
        log.info("review items escalated", extra={"count": n})
    purged = callassist.purge_expired_audio()
    if purged:
        log.info("expired audio deleted", extra={"count": purged})
    verify_chains_daily()


def verify_chains_daily() -> None:
    """S12: verify each hospital's audit chain once a day and record it for the Trust screen."""
    with tx() as conn:
        due = conn.execute(
            """SELECT h.id FROM hospitals h WHERE NOT EXISTS (
                 SELECT 1 FROM eval_runs r WHERE r.hospital_id = h.id AND r.kind = 'audit_chain'
                   AND r.started_at > now() - interval '24 hours')""").fetchall()
    for h in due:
        with tx() as conn:
            res = audit.verify_chain(conn, h["id"])
            evals.record(conn, "audit_chain", [evals.Metric("chain_valid", 1.0 if res["valid"] else 0.0, 1.0),
                                               evals.Metric("entries_checked", float(res["checked"]))],
                         summary={**res, "by": "worker daily check"}, hospital_id=h["id"])
        if not res["valid"]:
            log.error("audit chain broken", extra={"hospital_id": str(h["id"]), "broken_at": res["broken_at"]})


def main() -> None:
    logs.setup()
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    log.info("worker started", extra={"worker": NAME})
    last_house = 0.0
    while running:
        did = process_next() or plan_next()
        if time.monotonic() - last_house > 60:
            housekeeping()
            last_house = time.monotonic()
        if not did:
            time.sleep(1.0)
    log.info("worker stopped", extra={"worker": NAME})


if __name__ == "__main__":
    main()
