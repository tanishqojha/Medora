"""Shared helpers for scripts. Runs the same ingest code the worker runs, inline, for seeding and benchmarks."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from medora import ingest, mapping  # noqa: E402
from medora.db import one, tx  # noqa: E402

REGISTER_MAPPING = json.loads((ROOT / "eval" / "gold" / "register_mapping.json").read_text(encoding="utf-8"))


def upload(hospital_id: str, path: Path, actor: str) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(dir=ingest.upload_dir())) / path.name
    shutil.copy(path, tmp)
    with tx() as conn:
        return ingest.intake(conn, hospital_id, path.name, tmp, actor)


def plan(job_id: str) -> dict[str, Any]:
    with tx() as conn:
        job = one(conn, "SELECT * FROM ingest_jobs WHERE id = %s", (job_id,))
        if job["fingerprint"] is None:
            ingest.plan(conn, job)
        return one(conn, "SELECT * FROM ingest_jobs WHERE id = %s", (job_id,))


def preconfirm(hospital_id: str, headers: list[str], mapping_json: dict[str, Any], actor: str) -> None:
    """S22: the demo starts with one mapping already confirmed, as if a steward did it earlier."""
    with tx() as conn:
        fp = mapping.fingerprint(headers)
        if not mapping.find_confirmed(conn, hospital_id, fp):
            mapping.save_confirmed(conn, hospital_id, fp, headers, mapping_json, "human", None, actor)


def drain(stop_after: int | None = None) -> int:
    n = 0
    while stop_after is None or n < stop_after:
        with tx() as conn:
            ch = ingest.claim_chunk(conn, "script")
        if not ch:
            break
        with tx() as conn:
            ingest.process_chunk(conn, ch)
        n += 1
    return n
