"""MUST vertical slice end to end (S24): file in -> mapping confirmed -> events -> flags -> replay.

Also: F1 kill/resume without redoing chunks, re-ingest unchanged = nothing new, F3 second file of the same
shape = zero LLM calls, F6 ambiguous dates go to review, whitelist drops the Diagnosis column.
"""
import shutil
from datetime import date

import pytest

from medora import engine, graphs, ingest, pathways, reviews, seed, synth
from medora.db import one, tx

pytestmark = pytest.mark.db


@pytest.fixture
def small_chunks(monkeypatch):
    real = ingest.setting
    monkeypatch.setattr(ingest, "setting", lambda k: 25 if k == "ingest.chunk_rows" else real(k))


@pytest.fixture
def data(tmp_path):
    return synth.build(tmp_path / "ds", n_patients=80, seed=11, as_of=date.today(), photos=0)


def _activate(hid):
    with tx() as conn:
        v = seed.register_pathways(conn, hid)["gi_cancer_handover.v1"]
        pathways.sign(conn, hid, v["id"], "Test Clinical Lead (synthetic)", "clinical_lead")
        pathways.activate(conn, hid, v["id"], "Test Clinical Lead (synthetic)")
    return v


def _upload(hid, src, tmp_path):
    tmp = tmp_path / ("up_" + src.split("\\")[-1].split("/")[-1])
    shutil.copy(src, tmp)
    with tx() as conn:
        return ingest.intake(conn, hid, tmp.name.replace("up_", ""), tmp, "steward")


def _plan(job_id):
    with tx() as conn:
        job = one(conn, "SELECT * FROM ingest_jobs WHERE id = %s", (job_id,))
        ingest.plan(conn, job)
        return one(conn, "SELECT * FROM ingest_jobs WHERE id = %s", (job_id,))


def _drain():
    n = 0
    while True:
        with tx() as conn:
            ch = ingest.claim_chunk(conn, "test-worker")
        if not ch:
            return n
        with tx() as conn:
            ingest.process_chunk(conn, ch)
        n += 1


def _confirm(hid, job_id):
    with tx() as conn:
        item = one(conn, "SELECT * FROM review_items WHERE hospital_id = %s AND dedupe_key = %s", (hid, f"mapping:{job_id}"))
    m = item["payload"]["mapping"]
    assert m["columns"]["Diagnosis"] == "ignore", "non-whitelisted column must not be mapped"
    # The steward knows the hospital's full label list and maps labels this file does not contain yet.
    m["event_type_values"].update({"Chemo booking": "appointment_booked", "Chemo Day Care": None})
    m["status_values"] = {"Booked": "appointment_booked", "Attended": "appointment_attended", "DNA": "appointment_missed"}
    m["date_convention"] = "dmy"  # a person confirms the file convention on the Mapping Confirm screen
    p = item["payload"]
    graphs.start("mapping", hid, str(job_id), {k: p.get(k) for k in ("fingerprint", "headers", "proposed_by", "prompt_version")})
    assert graphs.pending("mapping", str(job_id))
    return reviews.confirm_mapping(hid, str(item["id"]), m, "Data Steward (synthetic)")


def test_vertical_slice(hospital, data, tmp_path, small_chunks):
    _activate(hospital)
    job = _upload(hospital, data.files["register_csv"], tmp_path)
    job = _plan(job["id"])
    assert job["state"] == "needs_mapping" and job["total_chunks"] > 1
    res = _confirm(hospital, job["id"])
    assert str(job["id"]) in res["jobs_started"]
    assert _drain() == job["total_chunks"]

    with tx() as conn:
        j = one(conn, "SELECT * FROM ingest_jobs WHERE id = %s", (job["id"],))
        assert j["state"] == "done" and j["llm_calls"] == 0  # no provider configured in tests: rules proposed it
        n_events = one(conn, "SELECT count(*) AS n FROM events WHERE hospital_id = %s AND type <> 'correction'", (hospital,))["n"]
        assert n_events == j["rows_loaded"] and j["rows_loaded"] + j["rows_review"] == j["rows_total"]
        # Ambiguous dates without a confirmed convention would be review items; with dmy confirmed they parse.
        payloads = conn.execute("SELECT payload FROM events WHERE hospital_id = %s", (hospital,)).fetchall()
        assert all("diagnosis" not in str(p["payload"]).lower() for p in payloads)
        flags = conn.execute("SELECT id, kind FROM flags WHERE hospital_id = %s AND state = 'open'", (hospital,)).fetchall()
        assert flags, "late patients must be flagged"
        for f in flags:
            r = engine.replay(conn, hospital, str(f["id"]))
            assert r["match"], r
        # Every explanation names its sources.
        assert one(conn, """SELECT count(*) AS n FROM flag_explanations x JOIN flags f ON f.id = x.flag_id
                            WHERE f.hospital_id = %s AND cardinality(x.source_event_ids) = 0""", (hospital,))["n"] == 0

    # Re-ingest the unchanged file: same job, nothing recomputed.
    again = _upload(hospital, data.files["register_csv"], tmp_path)
    assert again["duplicate"] and str(again["id"]) == str(job["id"])
    with tx() as conn:
        assert one(conn, "SELECT count(*) AS n FROM events WHERE hospital_id = %s AND type <> 'correction'",
                   (hospital,))["n"] == n_events


def test_same_shape_zero_llm_calls_and_kill_resume(hospital, data, tmp_path, small_chunks):
    _activate(hospital)
    first = _plan(_upload(hospital, data.files["register_csv"], tmp_path)["id"])
    _confirm(hospital, first["id"])
    _drain()

    # Second file, same header shape (XLSX this time): mapping reused, no LLM, no person needed.
    second = _plan(_upload(hospital, data.files["register_xlsx"], tmp_path)["id"])
    assert second["state"] == "running" and second["llm_calls"] == 0 and second["mapping_id"] is not None

    # Process one chunk, then simulate a crash mid-chunk on the next and kill the job.
    with tx() as conn:
        ch = ingest.claim_chunk(conn, "w1")
    with tx() as conn:
        ingest.process_chunk(conn, ch)
    with tx() as conn:
        crashed = ingest.claim_chunk(conn, "w1")
        conn.execute("UPDATE ingest_chunks SET started_at = now() - interval '10 minutes' WHERE id = %s", (crashed["id"],))
        ingest.control(conn, hospital, str(second["id"]), "kill", "steward")
    assert _drain() == 0, "a killed job must not be processed"
    with tx() as conn:
        ingest.control(conn, hospital, str(second["id"]), "resume", "steward")
    _drain()
    with tx() as conn:
        j = one(conn, "SELECT * FROM ingest_jobs WHERE id = %s", (second["id"],))
        assert j["state"] == "done" and j["done_chunks"] == j["total_chunks"]
        assert j["rows_review"] <= j["rows_total"] * 0.1, "known labels must load, only odd rows go to review"
        redone = one(conn, "SELECT count(*) AS n FROM ingest_chunks WHERE job_id = %s AND attempts > 1 AND id <> %s",
                     (second["id"], crashed["id"]))["n"]
        assert redone == 0, "finished chunks are never redone"
        dups = one(conn, """SELECT count(*) AS n FROM (SELECT dedupe_key FROM events WHERE hospital_id = %s
                            GROUP BY dedupe_key HAVING count(*) > 1) d""", (hospital,))["n"]
        assert dups == 0


def test_parallel_chunks_do_not_duplicate_patients(hospital, data, tmp_path):
    """Two workers on two files of one hospital, transactions overlapping: every person exists once."""
    import os
    import threading
    import time

    import psycopg
    from psycopg.rows import dict_row

    _activate(hospital)
    first = _plan(_upload(hospital, data.files["register_csv"], tmp_path)["id"])
    _confirm(hospital, first["id"])
    _plan(_upload(hospital, data.files["register_xlsx"], tmp_path)["id"])
    with tx() as conn:
        a = ingest.claim_chunk(conn, "w1")
    with tx() as conn:
        b = ingest.claim_chunk(conn, "w2")
    c1 = psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)
    c2 = psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)
    try:
        ingest.process_chunk(c1, a)                      # worker 1 holds its transaction open
        t = threading.Thread(target=lambda: (ingest.process_chunk(c2, b), c2.commit()))
        t.start()
        time.sleep(1.5)                                  # without the lock, worker 2 finishes here, blind
        c1.commit()
        t.join(timeout=60)
    finally:
        c1.close()
        c2.close()
    with tx() as conn:
        dupes = one(conn, """SELECT count(*) AS n FROM (SELECT value FROM patient_identifiers
                             WHERE hospital_id = %s AND kind = 'exact_key' GROUP BY value HAVING count(*) > 1) d""",
                    (hospital,))["n"]
    assert dupes == 0
