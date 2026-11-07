"""Human decisions on review items (Review Queue). Every decision is audited. Nothing here auto-approves.

Gated through LangGraph (S11): mapping confirm, identity merge, outcome reason (registered in callassist).
Row, date and extraction fixes are direct decisions on the item.
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from psycopg.types.json import Jsonb

from medora import audit, engine, graphs, mapping
from medora.dates import IST
from medora.db import Conn, one, tx
from medora.events import NewEvent, append
from medora.identity import Record
from medora.ingest import _birth_year, _canonical, _resolve_identities, _sex


class ReviewError(ValueError):
    pass


def _open_item(conn: Conn, hospital_id: str, item_id: str, kinds: set[str]) -> dict[str, Any]:
    item = conn.execute("SELECT * FROM review_items WHERE id = %s AND hospital_id = %s FOR UPDATE",
                        (item_id, hospital_id)).fetchone()
    if not item:
        raise LookupError("review item not found")
    if item["type"] not in kinds:
        raise ReviewError(f"item is a {item['type']} review")
    if item["state"] == "decided":
        raise ReviewError("this item was already decided")
    return item


def _close(conn: Conn, item_id: str, actor: str, decision: dict[str, Any]) -> None:
    conn.execute("UPDATE review_items SET state = 'decided', decided_by = %s, decision = %s, decided_at = now() WHERE id = %s",
                 (actor, Jsonb(decision), item_id))


# ---------- mapping ----------

@graphs.register("mapping")
def _apply_mapping(hospital_id: str, job_id: str, proposal: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    actor = decision["actor"]
    with tx() as conn:
        item = _open_item(conn, hospital_id, decision["review_item_id"], {"mapping"})
        mp = mapping.save_confirmed(conn, hospital_id, proposal["fingerprint"], proposal["headers"], decision["mapping"],
                                    proposal.get("proposed_by", "human"), proposal.get("prompt_version"), actor)
        # Compile once: every job waiting on this file shape starts with zero further LLM calls.
        jobs = conn.execute(
            """UPDATE ingest_jobs SET mapping_id = %s, state = 'running', updated_at = now()
               WHERE hospital_id = %s AND fingerprint = %s AND state = 'needs_mapping' RETURNING id""",
            (mp["id"], hospital_id, proposal["fingerprint"])).fetchall()
        conn.execute("""UPDATE review_items SET state = 'decided', decided_by = %s, decision = %s, decided_at = now()
                        WHERE hospital_id = %s AND type = 'mapping' AND state <> 'decided'
                          AND payload->>'fingerprint' = %s""",
                     (actor, Jsonb({"mapping_id": str(mp["id"])}), hospital_id, proposal["fingerprint"]))
        _ = item
    return {"mapping_id": str(mp["id"]), "version": mp["version"], "jobs_started": [str(j["id"]) for j in jobs]}


def confirm_mapping(hospital_id: str, item_id: str, mapping_json: dict[str, Any], actor: str) -> dict[str, Any]:
    with tx() as conn:
        item = _open_item(conn, hospital_id, item_id, {"mapping"})
        job = one(conn, "SELECT * FROM ingest_jobs WHERE id = %s", (item["job_id"],))
        mapping.validate(mapping_json, job["headers"])  # fail fast before touching the gate
    proposal = {k: item["payload"].get(k) for k in ("fingerprint", "headers", "proposed_by", "prompt_version")}
    return graphs.decide("mapping", hospital_id, str(item["job_id"]), proposal,
                         {"mapping": mapping_json, "actor": actor, "review_item_id": item_id})


# ---------- identity ----------

@graphs.register("identity")
def _apply_identity(hospital_id: str, item_id: str, proposal: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    actor = decision["actor"]
    with tx() as conn:
        item = _open_item(conn, hospital_id, item_id, {"identity"})
        a, b = item["payload"]["patient_a"], item["payload"]["patient_b"]
        result: dict[str, Any] = {"merged": False}
        if decision["merge"]:
            older = one(conn, "SELECT id::text FROM patients WHERE id = ANY(%s::uuid[]) ORDER BY created_at, id LIMIT 1",
                        ([a, b],))["id"]
            newer = b if older == a else a
            m = one(conn, """INSERT INTO patient_merges (hospital_id, from_patient, into_patient, outcome, score, features,
                                                         decided_by)
                             VALUES (%s,%s,%s,'review_merge',%s,%s,%s) RETURNING id""",
                    (hospital_id, newer, older, item["payload"]["score"], Jsonb(item["payload"]["features"]), actor))
            audit.append(conn, hospital_id, actor, "identity.merge", "patient_merge", m["id"], {"from": newer, "into": older})
            engine.evaluate_active(conn, hospital_id, patients=_canonical(conn, [a, b]), actor=actor)
            result = {"merged": True, "merge_id": str(m["id"])}
        else:
            audit.append(conn, hospital_id, actor, "identity.keep_apart", "review_item", item_id, {"a": a, "b": b})
        _close(conn, item_id, actor, {"merge": bool(decision["merge"])})
    return result


def decide_identity(hospital_id: str, item_id: str, merge: bool, actor: str) -> dict[str, Any]:
    return graphs.decide("identity", hospital_id, item_id, {}, {"merge": merge, "actor": actor})


def reverse_merge(conn: Conn, hospital_id: str, merge_id: str, actor: str) -> None:
    m = conn.execute("""UPDATE patient_merges SET reversed_at = now(), reversed_by = %s
                        WHERE id = %s AND hospital_id = %s AND reversed_at IS NULL RETURNING from_patient, into_patient""",
                     (actor, merge_id, hospital_id)).fetchone()
    if not m:
        raise ReviewError("merge not found or already reversed")
    audit.append(conn, hospital_id, actor, "identity.unmerge", "patient_merge", merge_id,
                 {"from": str(m["from_patient"]), "into": str(m["into_patient"])})
    engine.evaluate_active(conn, hospital_id, patients=_canonical(conn, [str(m["from_patient"]), str(m["into_patient"])]),
                           actor=actor)


# ---------- rows, dates, extraction ----------

def accept_row(conn: Conn, hospital_id: str, item_id: str, fields: dict[str, Any], event_type: str,
               event_date: str, actor: str) -> str | None:
    """A person fixed or confirmed the row. The event records them as the source of the correction."""
    item = _open_item(conn, hospital_id, item_id, {"row", "date", "extraction"})
    d = date.fromisoformat(event_date)
    allowed = {"patient_name", "phone", "hospital_number", "sex", "age", "birth_year", "department", "status",
               "appointment_date"}
    fields = {k: v for k, v in fields.items() if k in allowed and v not in (None, "")}
    if not any(k in fields for k in ("patient_name", "phone", "hospital_number")):
        raise ReviewError("at least one identifier is required")
    rec = Record(name=str(fields.get("patient_name") or ""), phone=fields.get("phone"),
                 hospital_number=fields.get("hospital_number"), sex=_sex(fields.get("sex")),
                 birth_year=_birth_year(fields, d.year))
    src = {**(item["source_ref"] or {"kind": "manual"}), "reviewed_by": actor, "review_item": item_id}
    k = rec.exact_key()
    pid = _resolve_identities(conn, hospital_id, {k: rec}, {k: src})[k]
    payload = {"department": fields.get("department"), "status_label": fields.get("status"),
               "appointment_date": fields.get("appointment_date")}
    ev_id = append(conn, NewEvent(
        hospital_id=hospital_id, type=event_type, occurred_at=datetime.combine(d, time(0, 0), tzinfo=IST),
        source_ref=src, confidence=1.0, actor=actor, patient_id=pid,
        payload={k2: str(v) for k2, v in payload.items() if v not in (None, "")}, dedupe_key=f"review:{item_id}"))
    _close(conn, item_id, actor, {"accepted": True, "event_id": ev_id})
    audit.append(conn, hospital_id, actor, "review.accept_row", "review_item", item_id, {"event_id": ev_id})
    engine.evaluate_active(conn, hospital_id, patients=_canonical(conn, [pid]), actor=actor)
    return ev_id


def reject_row(conn: Conn, hospital_id: str, item_id: str, reason: str, actor: str) -> None:
    _open_item(conn, hospital_id, item_id, {"row", "date", "extraction"})
    _close(conn, item_id, actor, {"accepted": False, "reason": reason})
    audit.append(conn, hospital_id, actor, "review.reject_row", "review_item", item_id, {"reason": reason})


def escalate_overdue(conn: Conn) -> int:
    """Timeout escalates (S11). It never approves."""
    rows = conn.execute(
        """UPDATE review_items SET state = 'escalated' WHERE state = 'open' AND due_at IS NOT NULL AND due_at < now()
           RETURNING id, hospital_id, type""").fetchall()
    for r in rows:
        audit.append(conn, r["hospital_id"], "system", "review.escalate", "review_item", r["id"], {"type": r["type"]})
    return len(rows)
