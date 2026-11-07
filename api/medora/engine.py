"""Runs compiled pathway SQL, decides each candidate with rules.check, keeps the ledger and flags (F9-F12)."""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from psycopg.types.json import Jsonb

from medora import audit
from medora.db import Conn, one
from medora.pathways import rule_version
from medora.rules import Decision, Ev, check, gaps_from_spec

log = logging.getLogger("medora.engine")


def _load_events(conn: Conn, hospital_id: str, patients: list[str],
                 as_of: datetime) -> dict[str, list[Ev]]:
    rows = conn.execute(
        """SELECT id::text, canonical_id::text AS pid, type, effective_at, payload->>'outcome' AS outcome
           FROM live_events WHERE hospital_id = %s AND canonical_id = ANY(%s::uuid[]) AND effective_at <= %s""",
        (hospital_id, patients, as_of),
    ).fetchall()
    out: dict[str, list[Ev]] = defaultdict(list)
    for r in rows:
        out[r["pid"]].append(Ev(r["id"], r["type"], r["effective_at"], r["outcome"]))
    return out


def decide(conn: Conn, hospital_id: str, version: dict[str, Any], as_of: datetime,
           patients: list[str] | None = None) -> list[tuple[str, Decision]]:
    """Pure read: returns (patient_id, decision) for every candidate. Used by evaluate and preview."""
    spec = version["spec"]
    rows = conn.execute(version["compiled_sql"],
                        {"hospital_id": hospital_id, "as_of": as_of, "patients": patients}).fetchall()
    if not rows:
        return []
    gaps = {(g.from_step, g.expected_step): g for g in gaps_from_spec(spec)}
    evs = _load_events(conn, hospital_id, sorted({str(r["patient_id"]) for r in rows}), as_of)
    rv = rule_version(version)
    out = []
    for r in rows:
        pid = str(r["patient_id"])
        from_ev = next(e for e in evs[pid] if e.id == str(r["from_event_id"]))
        d = check(rv, gaps[(r["from_step"], r["expected_step"])], from_ev, evs[pid], as_of,
                  spec["unreachable_after_attempts"])
        sql_ev = str(r["evidence_event_id"]) if r["evidence_event_id"] else None
        if sql_ev != d.evidence_event_id:
            # Compiled SQL and the rule function disagree. Never pick one silently.
            log.error("engine mismatch", extra={"from_event": d.from_event_id, "sql": sql_ev,
                                                "rule": d.evidence_event_id})
            audit.append(conn, hospital_id, "system", "engine.mismatch", "event", d.from_event_id,
                         {"sql_evidence": sql_ev, "rule_evidence": d.evidence_event_id, "rule_version": rv})
            continue
        out.append((pid, d))
    return out


def evaluate(conn: Conn, hospital_id: str, version: dict[str, Any],
             as_of: datetime | None = None, patients: list[str] | None = None, actor: str = "system") -> dict[str, int]:
    """Write obligations, flags and explanations. Incremental when `patients` is given."""
    as_of = as_of or datetime.now(UTC)
    stats = {"candidates": 0, "open": 0, "closed": 0, "flags": 0, "resolved": 0}
    for pid, d in decide(conn, hospital_id, version, as_of, patients):
        stats["candidates"] += 1
        ob = conn.execute(
            """INSERT INTO obligations (hospital_id, pathway_version_id, patient_id, from_step, expected_step,
                                        from_event_id, due_by, state, closed_by_event, closed_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (pathway_version_id, from_event_id, expected_step) DO UPDATE
                 SET patient_id = EXCLUDED.patient_id, due_by = EXCLUDED.due_by, state = EXCLUDED.state,
                     closed_by_event = EXCLUDED.closed_by_event, closed_at = EXCLUDED.closed_at
                 WHERE obligations.state <> 'closed_reason'
               RETURNING id, state""",
            (hospital_id, version["id"], pid, d.from_step, d.expected_step, d.from_event_id, d.due_by, d.state,
             d.evidence_event_id, as_of if d.evidence_event_id else None),
        ).fetchone()
        if ob is None:  # closed by a coded reason; a person decided, the engine leaves it alone
            stats["closed"] += 1
            continue
        stats["open" if ob["state"] == "open" else "closed"] += 1
        if d.flag_kind and ob["state"] == "open":
            fl = one(conn, 
                """INSERT INTO flags (hospital_id, obligation_id, patient_id, pathway_version_id, kind,
                                      rank_inputs, reason_line, state)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,'open')
                   ON CONFLICT (obligation_id) DO UPDATE SET kind = EXCLUDED.kind, patient_id = EXCLUDED.patient_id,
                     rank_inputs = EXCLUDED.rank_inputs, reason_line = EXCLUDED.reason_line, state = 'open',
                     resolved_at = NULL
                   RETURNING id""",
                (hospital_id, ob["id"], pid, version["id"], d.flag_kind, Jsonb(d.rank_inputs(pid)), d.reason_line),
            )
            conn.execute(
                """INSERT INTO flag_explanations (flag_id, hospital_id, rule_version, source_event_ids, steps,
                                                  result_hash, computed_at)
                   VALUES (%s,%s,%s,%s::uuid[],%s,%s,%s)
                   ON CONFLICT (flag_id) DO UPDATE SET rule_version = EXCLUDED.rule_version,
                     source_event_ids = EXCLUDED.source_event_ids, steps = EXCLUDED.steps,
                     result_hash = EXCLUDED.result_hash, computed_at = EXCLUDED.computed_at""",
                (fl["id"], hospital_id, rule_version(version), d.source_event_ids,
                 Jsonb({"as_of": as_of.isoformat(), "lines": d.steps, "from_step": d.from_step,
                        "expected_step": d.expected_step, "from_event_id": d.from_event_id}),
                 d.result_hash, as_of),
            )
            stats["flags"] += 1
        else:
            cur = conn.execute(
                "UPDATE flags SET state = 'resolved', resolved_at = %s WHERE obligation_id = %s AND state = 'open'",
                (as_of, ob["id"]))
            stats["resolved"] += cur.rowcount
    audit.append(conn, hospital_id, actor, "engine.evaluate", "pathway_version", version["id"],
                 {**stats, "as_of": as_of.isoformat(), "incremental": patients is not None})
    return stats


def evaluate_active(conn: Conn, hospital_id: str, patients: list[str] | None = None,
                    actor: str = "system", as_of: datetime | None = None) -> dict[str, dict[str, int]]:
    versions = conn.execute(
        "SELECT * FROM pathway_versions WHERE hospital_id = %s AND active", (hospital_id,)).fetchall()
    return {str(v["id"]): evaluate(conn, hospital_id, v, as_of, patients, actor) for v in versions}


def replay(conn: Conn, hospital_id: str, flag_id: str) -> dict[str, Any]:
    """F12: recompute a flag from stored events. A mismatch is logged and audited as an alert."""
    row = conn.execute(
        """SELECT f.*, x.rule_version, x.steps, x.result_hash, x.source_event_ids, v.id AS vid
           FROM flags f JOIN flag_explanations x ON x.flag_id = f.id
           JOIN pathway_versions v ON v.id = f.pathway_version_id
           WHERE f.id = %s AND f.hospital_id = %s""", (flag_id, hospital_id)).fetchone()
    if not row:
        raise LookupError("flag not found")
    version = one(conn, "SELECT * FROM pathway_versions WHERE id = %s", (row["vid"],))
    steps = row["steps"]
    as_of = datetime.fromisoformat(steps["as_of"])
    gap = next(g for g in gaps_from_spec(version["spec"])
               if g.from_step == steps["from_step"] and g.expected_step == steps["expected_step"])
    pid = str(row["patient_id"])
    evs = _load_events(conn, hospital_id, [pid], as_of)[pid]
    from_ev = next((e for e in evs if e.id == steps["from_event_id"]), None)
    if from_ev is None:
        result = {"match": False, "reason": "source event no longer live (voided or merged away)"}
    else:
        d = check(rule_version(version), gap, from_ev, evs, as_of, version["spec"]["unreachable_after_attempts"])
        result = {"match": d.result_hash == row["result_hash"], "recomputed_hash": d.result_hash,
                  "recomputed_steps": d.steps, "recomputed_kind": d.flag_kind}
    result.update({"flag_id": flag_id, "stored_hash": row["result_hash"], "rule_version": row["rule_version"],
                   "as_of": steps["as_of"], "stored_steps": steps["lines"],
                   "source_event_ids": [str(s) for s in row["source_event_ids"]]})
    if not result["match"]:
        log.error("replay mismatch", extra={"flag_id": flag_id})
        audit.append(conn, hospital_id, "system", "replay.mismatch", "flag", flag_id,
                     {"stored": row["result_hash"], "recomputed": result.get("recomputed_hash")})
    return result
