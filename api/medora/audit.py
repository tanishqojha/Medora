"""Audit log: append and verify a per-hospital hash chain (S12). Two-key file.

The only writer of audit_log. Each entry hashes the previous entry, so editing or removing a row
breaks every hash after it.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from psycopg.types.json import Jsonb

from medora.db import Conn
from medora.hashing import canonical, sha256

GENESIS = "0" * 64


def _entry_hash(prev_hash: str, hospital_id: str, at: datetime, actor: str, action: str,
                object_type: str, object_id: str, detail: dict[str, Any]) -> str:
    body = canonical({
        "hospital_id": str(hospital_id), "at": at.astimezone(UTC).isoformat(), "actor": actor,
        "action": action, "object_type": object_type, "object_id": str(object_id), "detail": detail,
    })
    return sha256(prev_hash + body)


def append(conn: Conn, hospital_id: str, actor: str, action: str, object_type: str,
           object_id: Any, detail: dict[str, Any] | None = None) -> str:
    """Append one audit entry inside the caller's transaction. Returns entry_hash."""
    detail = detail or {}
    # Serialise writers per hospital so two entries never share a prev_hash.
    conn.execute("SELECT pg_advisory_xact_lock(hashtext('audit:' || %s))", (str(hospital_id),))
    row = conn.execute(
        "SELECT entry_hash FROM audit_log WHERE hospital_id = %s ORDER BY seq DESC LIMIT 1", (hospital_id,)
    ).fetchone()
    prev = row["entry_hash"] if row else GENESIS
    at = datetime.now(UTC)
    entry = _entry_hash(prev, hospital_id, at, actor, action, object_type, str(object_id), detail)
    conn.execute(
        """INSERT INTO audit_log (hospital_id, at, actor, action, object_type, object_id, detail,
                                  prev_hash, entry_hash)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (hospital_id, at, actor, action, object_type, str(object_id),
         Jsonb(detail), prev, entry),
    )
    return entry


def verify_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure check over rows ordered by seq. Returns {valid, checked, broken_at}."""
    prev = GENESIS
    for i, r in enumerate(rows):
        expected = _entry_hash(prev, r["hospital_id"], r["at"], r["actor"], r["action"], r["object_type"],
                               r["object_id"], r["detail"])
        if r["prev_hash"] != prev or r["entry_hash"] != expected:
            return {"valid": False, "checked": i, "broken_at": r.get("seq")}
        prev = r["entry_hash"]
    return {"valid": True, "checked": len(rows), "broken_at": None}


def verify_chain(conn: Conn, hospital_id: str) -> dict[str, Any]:
    rows = conn.execute(
        """SELECT seq, hospital_id, at, actor, action, object_type, object_id, detail, prev_hash, entry_hash
           FROM audit_log WHERE hospital_id = %s ORDER BY seq""", (hospital_id,)
    ).fetchall()
    return verify_rows(rows)
