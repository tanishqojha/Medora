"""F8 append-only, S12 audit chain + tamper, F9 sign-off rules. Runs against real Postgres."""
from datetime import UTC, datetime

import psycopg
import pytest

from medora import audit, pathways, seed
from medora.dates import IST
from medora.db import tx
from medora.events import EventRejected, NewEvent, append, correct

pytestmark = pytest.mark.db


def _patient(conn, hid):
    return str(conn.execute("INSERT INTO patients (hospital_id, display_name) VALUES (%s,'Test Patient') RETURNING id",
                            (hid,)).fetchone()["id"])


def _event(hid, pid, **kw):
    return NewEvent(hospital_id=hid, type=kw.get("type", "tb_decision_recorded"), patient_id=pid,
                    occurred_at=kw.get("at", datetime(2026, 10, 1, tzinfo=UTC)), source_ref={"kind": "test", "row": 1},
                    confidence=1.0, actor="test")


def test_events_reject_update_and_delete(hospital, admin_conn):
    with tx() as conn:
        pid = _patient(conn, hospital)
        eid = append(conn, _event(hospital, pid))
    with tx() as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("UPDATE events SET confidence = 0.5 WHERE id = %s", (eid,))
    with tx() as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("DELETE FROM events WHERE id = %s", (eid,))
    # Even the owner hits the trigger.
    with pytest.raises(psycopg.errors.RaiseException):
        admin_conn.execute("UPDATE events SET confidence = 0.5 WHERE id = %s", (eid,))
    with pytest.raises(psycopg.errors.RaiseException):
        admin_conn.execute("DELETE FROM audit_log WHERE hospital_id = %s", (hospital,))


def test_event_needs_provenance_and_whitelist(hospital):
    with tx() as conn:
        pid = _patient(conn, hospital)
        bad = _event(hospital, pid)
        bad.source_ref = {}
        with pytest.raises(EventRejected):
            append(conn, bad)
        bad2 = _event(hospital, pid)
        bad2.payload = {"diagnosis": "x"}
        with pytest.raises(EventRejected):
            append(conn, bad2)


def test_dedupe_is_idempotent(hospital):
    with tx() as conn:
        pid = _patient(conn, hospital)
        assert append(conn, _event(hospital, pid)) is not None
        assert append(conn, _event(hospital, pid)) is None


def test_correction_is_new_event_and_live_view_applies(hospital):
    with tx() as conn:
        pid = _patient(conn, hospital)
        eid = append(conn, _event(hospital, pid))
        correct(conn, hospital, eid, "steward", "occurred_at", "2026-10-03T00:00:00+05:30", datetime.now(UTC))
        live = conn.execute("SELECT effective_at FROM live_events WHERE id = %s", (eid,)).fetchone()
        orig = conn.execute("SELECT occurred_at FROM events WHERE id = %s", (eid,)).fetchone()
        assert live["effective_at"].astimezone(IST).date().isoformat() == "2026-10-03"
        assert orig["occurred_at"] == datetime(2026, 10, 1, tzinfo=UTC)
        correct(conn, hospital, eid, "steward", "void", "duplicate", datetime.now(UTC))
        assert conn.execute("SELECT 1 FROM live_events WHERE id = %s", (eid,)).fetchone() is None


def test_audit_chain_verifies_and_detects_tamper(hospital, admin_conn):
    with tx() as conn:
        for i in range(5):
            audit.append(conn, hospital, "tester", "test.action", "thing", str(i), {"n": i})
        assert audit.verify_chain(conn, hospital)["valid"]
    admin_conn.execute("ALTER TABLE audit_log DISABLE TRIGGER audit_append_only")
    try:
        admin_conn.execute("""UPDATE audit_log SET actor = 'mallory' WHERE seq = (
                                SELECT seq FROM audit_log WHERE hospital_id = %s AND action = 'test.action'
                                ORDER BY seq LIMIT 1 OFFSET 2)""", (hospital,))
    finally:
        admin_conn.execute("ALTER TABLE audit_log ENABLE TRIGGER audit_append_only")
    with tx() as conn:
        res = audit.verify_chain(conn, hospital)
    assert res["valid"] is False and res["broken_at"] is not None


def test_unsigned_pathway_cannot_activate(hospital, admin_conn):
    with tx() as conn:
        v = seed.register_pathways(conn, hospital)["gi_cancer_handover.v1"]
        with pytest.raises(pathways.PathwayError):
            pathways.activate(conn, hospital, v["id"], "someone")
    # The database refuses too, even for the owner.
    with pytest.raises(psycopg.errors.CheckViolation):
        admin_conn.execute("UPDATE pathway_versions SET active = true WHERE id = %s", (v["id"],))


def test_only_clinical_lead_signs_and_versions_are_immutable(hospital, admin_conn):
    with tx() as conn:
        v = seed.register_pathways(conn, hospital)["gi_cancer_handover.v1"]
        with pytest.raises(pathways.PathwayError):
            pathways.sign(conn, hospital, v["id"], "Coordinator", "coordinator")
        pathways.sign(conn, hospital, v["id"], "Dr Lead", "clinical_lead")
        pathways.activate(conn, hospital, v["id"], "Dr Lead")
    with pytest.raises(psycopg.errors.RaiseException):
        admin_conn.execute("UPDATE pathway_versions SET yaml = yaml || ' ' WHERE id = %s", (v["id"],))
    with tx() as conn:
        text = conn.execute("SELECT yaml FROM pathway_versions WHERE id = %s", (v["id"],)).fetchone()["yaml"]
        with pytest.raises(pathways.PathwayError):
            pathways.register(conn, hospital, text.replace("max_gap_days: 7 ", "max_gap_days: 9 "), "x")


def test_same_batch_duplicates_link_one_way_and_stay_visible(hospital):
    """Two records of one person in one chunk: one link, new into older, and both stay in the live timeline."""
    from medora.identity import Record
    from medora.ingest import _resolve_identities

    a = Record(name="Kavita Iyer", phone="9820144521", hospital_number="PT-10001", sex="F", birth_year=1970)
    b = Record(name="Kavita Iyre", phone="9820144521", hospital_number="PT-10001", sex="F", birth_year=1970)
    with tx() as conn:
        ids = _resolve_identities(conn, hospital, {a.exact_key(): a, b.exact_key(): b},
                                  {a.exact_key(): {"kind": "test"}, b.exact_key(): {"kind": "test"}})
        merges = conn.execute("SELECT from_patient::text f, into_patient::text t FROM patient_merges WHERE hospital_id = %s",
                              (hospital,)).fetchall()
        assert merges == [{"f": ids[b.exact_key()], "t": ids[a.exact_key()]}]
        canon = conn.execute("SELECT patient_id::text p, canonical_id::text c FROM patient_canonical WHERE patient_id = ANY(%s::uuid[])",
                             (list(ids.values()),)).fetchall()
        assert {r["c"] for r in canon} == {ids[a.exact_key()]} and len(canon) == 2
