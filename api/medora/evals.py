"""eval_runs / eval_results writer and reader (F16, S16). The Trust screen reads only from here."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any

from psycopg.types.json import Jsonb

from medora.config import ROOT
from medora.db import Conn, one


@dataclass
class Metric:
    metric: str
    value: float
    bar: float | None = None
    higher_is_better: bool = True
    detail: dict[str, Any] | None = None

    @property
    def passed(self) -> bool:
        if self.bar is None:
            return True
        return self.value >= self.bar if self.higher_is_better else self.value <= self.bar


def git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              timeout=5, check=True).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def record(conn: Conn, kind: str, metrics: list[Metric], summary: dict[str, Any] | None = None,
           hospital_id: str | None = None, synthetic: bool = True) -> str:
    passed = all(m.passed for m in metrics)
    run = one(conn, """INSERT INTO eval_runs (hospital_id, kind, finished_at, git_sha, synthetic, passed, summary)
                       VALUES (%s,%s,now(),%s,%s,%s,%s) RETURNING id""",
              (hospital_id, kind, git_sha(), synthetic, passed, Jsonb(summary or {})))
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO eval_results (hospital_id, run_id, metric, value, bar, higher_is_better, passed, detail)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            [(hospital_id, run["id"], m.metric, m.value, m.bar, m.higher_is_better, m.passed, Jsonb(m.detail or {}))
             for m in metrics])
    return str(run["id"])


def latest(conn: Conn, kinds: list[str], hospital_id: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in kinds:
        run = conn.execute(
            """SELECT * FROM eval_runs WHERE kind = %s AND (hospital_id IS NULL OR hospital_id = %s)
               ORDER BY started_at DESC LIMIT 1""", (k, hospital_id)).fetchone()
        if not run:
            out[k] = None
            continue
        results = conn.execute("SELECT metric, value, bar, higher_is_better, passed, detail FROM eval_results "
                               "WHERE run_id = %s ORDER BY metric", (run["id"],)).fetchall()
        out[k] = {**run, "id": str(run["id"]), "results": [{**r, "value": float(r["value"]),
                                                             "bar": float(r["bar"]) if r["bar"] is not None else None}
                                                            for r in results]}
    return out
