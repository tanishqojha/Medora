"""The only way events get written (F8, S7). Append-only, whitelisted, provenance required."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from psycopg.types.json import Jsonb

from medora import whitelist
from medora.db import Conn
from medora.hashing import hash_obj


class EventRejected(ValueError):
    pass


@dataclass
class NewEvent:
    hospital_id: str
    type: str
    occurred_at: datetime
    source_ref: dict[str, Any]
    confidence: float
    actor: str
    patient_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    supersedes_id: str | None = None
    dedupe_key: str | None = None
    synthetic: bool = True

    def validate(self) -> None:
        if self.type not in whitelist.event_types():
            raise EventRejected(f"event type not whitelisted: {self.type}")
        extra = set(self.payload) - whitelist.payload_fields()
        if extra:
            raise EventRejected(f"payload fields not whitelisted: {sorted(extra)}")
        if not self.source_ref or "kind" not in self.source_ref:
            raise EventRejected("event has no source_ref")
        if not 0 <= self.confidence <= 1:
            raise EventRejected("confidence must be within 0..1")
        if self.occurred_at.tzinfo is None:
            raise EventRejected("occurred_at must be timezone aware")

    def key(self) -> str:
        """Dedupe key = content hash plus source position, so identical visits on different rows stay apart."""
        if self.dedupe_key:
            return self.dedupe_key
        return hash_obj({"t": self.type, "p": self.patient_id, "at": self.occurred_at.isoformat(),
                         "pl": self.payload, "src": self.source_ref, "sup": self.supersedes_id})


def append(conn: Conn, ev: NewEvent) -> str | None:
    """Insert one event. Returns its id, or None if the same event already exists (idempotent)."""
    ev.validate()
    row = conn.execute(
        """INSERT INTO events (hospital_id, type, patient_id, occurred_at, source_ref, confidence, payload,
                               supersedes_id, dedupe_key, actor, synthetic)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (hospital_id, dedupe_key) DO NOTHING RETURNING id""",
        (ev.hospital_id, ev.type, ev.patient_id, ev.occurred_at, Jsonb(ev.source_ref), ev.confidence,
         Jsonb(ev.payload), ev.supersedes_id, ev.key(), ev.actor, ev.synthetic),
    ).fetchone()
    return str(row["id"]) if row else None


COPY_COLS = ("hospital_id", "type", "patient_id", "occurred_at", "source_ref", "confidence", "payload",
             "supersedes_id", "dedupe_key", "actor", "synthetic")


def bulk_append(conn: Conn, evs: list[NewEvent]) -> int:
    """COPY into a temp table, then insert with dedupe. Returns rows actually inserted."""
    if not evs:
        return 0
    for ev in evs:
        ev.validate()
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS _ev_stage (LIKE events INCLUDING DEFAULTS) ON COMMIT DROP")
    conn.execute("TRUNCATE _ev_stage")
    with conn.cursor().copy(f"COPY _ev_stage ({', '.join(COPY_COLS)}) FROM STDIN") as cp:
        for ev in evs:
            cp.write_row((ev.hospital_id, ev.type, ev.patient_id, ev.occurred_at, Jsonb(ev.source_ref),
                          ev.confidence, Jsonb(ev.payload), ev.supersedes_id, ev.key(), ev.actor, ev.synthetic))
    cur = conn.execute(
        f"""INSERT INTO events ({', '.join(COPY_COLS)})
            SELECT {', '.join(COPY_COLS)} FROM _ev_stage
            ON CONFLICT (hospital_id, dedupe_key) DO NOTHING"""
    )
    return cur.rowcount


def correct(conn: Conn, hospital_id: str, old_event_id: str, actor: str, field_name: str,
            value: str, occurred_at: datetime) -> str | None:
    """Corrections are new events pointing at the old one. The original stays untouched."""
    old = conn.execute("SELECT patient_id FROM events WHERE id = %s AND hospital_id = %s",
                       (old_event_id, hospital_id)).fetchone()
    if not old:
        raise EventRejected("event to correct not found in this hospital")
    return append(conn, NewEvent(
        hospital_id=hospital_id, type="correction", occurred_at=occurred_at, actor=actor, confidence=1.0,
        patient_id=str(old["patient_id"]) if old["patient_id"] else None,
        source_ref={"kind": "human_correction", "by": actor}, supersedes_id=old_event_id,
        payload={"corrected_field": field_name, "corrected_value": value},
    ))
