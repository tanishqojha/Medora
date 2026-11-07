"""Medora API. Run: uv run uvicorn medora.app:app --reload (from /api).

Every route declares roles and filters by the caller's hospital_id. Errors come back as plain sentences.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from psycopg.types.json import Jsonb

from medora import audit, callassist, engine, evals, fhir, ingest, llm, logs, pathways, reviews, tripwire
from medora.auth import User, issue, require, verify_password
from medora.config import env
from medora.db import one, tx
from medora.history import build_history
from medora.ranking import rank
from medora.rules import gaps_from_spec

logs.setup()
log = logging.getLogger("medora.api")
app = FastAPI(title="Medora API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=[env("WEB_ORIGIN", "http://localhost:3000")], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

COORD = ("coordinator", "clinical_lead", "admin")
STEWARD = ("data_steward", "admin", "clinical_lead")
REVIEW = ("data_steward", "coordinator", "clinical_lead", "admin")
CLINICAL_QUEUE = ("nurse", "clinical_lead")
DOCTOR = ("clinical_lead", "admin")
READ_ALL = ("coordinator", "clinical_lead", "nurse", "admin", "data_steward")


@app.exception_handler(LookupError)
async def _not_found(_: Request, e: LookupError) -> JSONResponse:
    return JSONResponse({"detail": str(e) or "Not found."}, status_code=404)


@app.exception_handler(ValueError)
async def _bad(_: Request, e: ValueError) -> JSONResponse:
    return JSONResponse({"detail": str(e)}, status_code=400)


def _j(rows: Any) -> Any:
    """JSON-safe copy (UUIDs, datetimes, decimals)."""
    return json.loads(json.dumps(rows, default=str))


# ---------- auth and meta ----------

@app.get("/api/health")
def health() -> dict[str, Any]:
    with tx() as conn:
        conn.execute("SELECT 1")
    return {"ok": True}


@app.post("/api/auth/login")
def login(body: dict[str, str] = Body(...)) -> JSONResponse:
    email = (body.get("email") or "").strip().lower()
    with tx() as conn:
        u = conn.execute("SELECT * FROM users WHERE lower(email) = %s ORDER BY created_at DESC LIMIT 1", (email,)).fetchone()
        if not u or not verify_password(body.get("password") or "", u["password_hash"]):
            raise HTTPException(401, "Email or password is not right.")
        audit.append(conn, u["hospital_id"], u["display_name"], "auth.login", "user", u["id"], {"role": u["role"]})
    token = issue(u)
    resp = JSONResponse({"token": token, "user": {"name": u["display_name"], "role": u["role"]}})
    resp.set_cookie("medora_token", token, httponly=True, samesite="lax", max_age=12 * 3600)
    return resp


@app.post("/api/auth/logout")
def logout() -> JSONResponse:
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("medora_token")
    return resp


@app.get("/api/meta")
def meta(user: User = require()) -> dict[str, Any]:
    with tx() as conn:
        h = one(conn, "SELECT name, synthetic FROM hospitals WHERE id = %s", (user.hospital_id,))
        counts = one(conn, """SELECT
            (SELECT count(*) FROM flags WHERE hospital_id = %(h)s AND state = 'open') AS stuck,
            (SELECT count(*) FROM review_items WHERE hospital_id = %(h)s AND state <> 'decided') AS review,
            (SELECT count(*) FROM nurse_items WHERE hospital_id = %(h)s AND state = 'open') AS nurse,
            (SELECT count(*) FROM review_items WHERE hospital_id = %(h)s AND state <> 'decided' AND type = 'identity') AS merges,
            (SELECT count(*) FROM ingest_jobs WHERE hospital_id = %(h)s AND state IN ('queued','running','needs_mapping')) AS jobs
        """, {"h": user.hospital_id})
    return {"hospital": h["name"], "synthetic": h["synthetic"], "replay": llm.mode() == "replay",
            "user": {"name": user.name, "role": user.role}, "counts": counts}


@app.get("/api/patients")
def search_patients(q: str = Query(..., min_length=2), user: User = require(*READ_ALL)) -> list[dict[str, Any]]:
    with tx() as conn:
        rows = conn.execute(
            """SELECT DISTINCT c.canonical_id AS id, p.display_name, p.sex, p.birth_year
               FROM patient_identifiers i JOIN patient_canonical c ON c.patient_id = i.patient_id
               JOIN patients p ON p.id = c.canonical_id
               WHERE i.hospital_id = %s AND (i.value ILIKE %s OR i.value = %s) LIMIT 20""",
            (user.hospital_id, f"%{q.strip()}%", q.strip())).fetchall()
    return _j(rows)


# ---------- uploads and jobs (F1) ----------

@app.post("/api/uploads")
async def upload(files: list[UploadFile] = File(...), user: User = require(*STEWARD)) -> list[dict[str, Any]]:
    out = []
    for f in files:
        fd, name = tempfile.mkstemp(dir=ingest.upload_dir(), suffix=".part")
        os.close(fd)  # mkstemp leaves the file open; Windows cannot move an open file
        tmp = Path(name)
        with open(tmp, "wb") as w:
            while block := await f.read(1 << 20):
                w.write(block)
        with tx() as conn:
            try:
                job = ingest.intake(conn, user.hospital_id, f.filename or "upload", tmp, user.name)
            except ingest.IntakeRejected as e:
                out.append({"filename": f.filename, "error": str(e)})
                continue
        out.append({"filename": f.filename, "job_id": str(job["id"]), "duplicate": job["duplicate"], "state": job["state"]})
    return out


_JOB_SQL = """SELECT j.*, s.filename, s.kind, s.size_bytes, s.content_hash, s.synthetic, m.version AS mapping_version,
                     m.confirmed_by AS mapping_confirmed_by
              FROM ingest_jobs j JOIN source_files s ON s.id = j.source_file_id LEFT JOIN mappings m ON m.id = j.mapping_id
              WHERE j.hospital_id = %s"""


@app.get("/api/jobs")
def jobs(user: User = require(*READ_ALL)) -> list[dict[str, Any]]:
    with tx() as conn:
        rows = conn.execute(_JOB_SQL + " ORDER BY j.created_at DESC LIMIT 100", (user.hospital_id,)).fetchall()
    for r in rows:
        r.pop("profile", None)
    return _j(rows)


@app.get("/api/jobs/{job_id}")
def job(job_id: str, user: User = require(*READ_ALL)) -> dict[str, Any]:
    with tx() as conn:
        j = one(conn, _JOB_SQL + " AND j.id = %s", (user.hospital_id, job_id))
        j["chunks"] = ingest.chunk_counts(conn, job_id)
        j["failed_chunks"] = conn.execute("SELECT seq, error FROM ingest_chunks WHERE job_id = %s AND state = 'failed'",
                                          (job_id,)).fetchall()
    return _j(j)


@app.post("/api/jobs/{job_id}/{action}")
def job_control(job_id: str, action: str, user: User = require(*STEWARD)) -> dict[str, Any]:
    if action not in ("pause", "resume", "kill"):
        raise HTTPException(404, "Unknown action.")
    with tx() as conn:
        return _j(ingest.control(conn, user.hospital_id, job_id, action, user.name))


# ---------- mapping confirm (F3) ----------

@app.get("/api/jobs/{job_id}/mapping")
def job_mapping(job_id: str, user: User = require(*STEWARD)) -> dict[str, Any]:
    with tx() as conn:
        j = one(conn, _JOB_SQL + " AND j.id = %s", (user.hospital_id, job_id))
        item = conn.execute("SELECT * FROM review_items WHERE hospital_id = %s AND dedupe_key = %s",
                            (user.hospital_id, f"mapping:{job_id}")).fetchone()
        current = conn.execute("SELECT * FROM mappings WHERE id = %s", (j["mapping_id"],)).fetchone() if j["mapping_id"] else None
        others = one(conn, """SELECT count(*) AS n FROM ingest_jobs WHERE hospital_id = %s AND fingerprint = %s
                              AND state = 'needs_mapping' AND id <> %s""", (user.hospital_id, j["fingerprint"], job_id))
    from medora import whitelist
    return _j({"job": j, "review_item": item, "mapping": current, "same_shape_waiting": others["n"],
               "targets": sorted(whitelist.canonical_fields()), "event_types": sorted(whitelist.event_types())})


@app.post("/api/review/{item_id}/mapping")
def confirm_mapping(item_id: str, body: dict[str, Any] = Body(...), user: User = require(*STEWARD)) -> dict[str, Any]:
    return reviews.confirm_mapping(user.hospital_id, item_id, body["mapping"], user.name)


# ---------- review queue ----------

@app.get("/api/review")
def review_list(type: str | None = None, state: str = "open", user: User = require(*REVIEW)) -> dict[str, Any]:
    states = ["open", "escalated"] if state == "open" else [state]
    with tx() as conn:
        rows = conn.execute(
            """SELECT r.*, s.filename FROM review_items r
               LEFT JOIN ingest_jobs j ON j.id = r.job_id LEFT JOIN source_files s ON s.id = j.source_file_id
               WHERE r.hospital_id = %s AND r.state = ANY(%s) AND (%s::text IS NULL OR r.type = %s)
               ORDER BY (r.state = 'escalated') DESC, r.created_at LIMIT 200""",
            (user.hospital_id, states, type, type)).fetchall()
        counts = conn.execute("""SELECT type, count(*) AS n FROM review_items WHERE hospital_id = %s
                                 AND state <> 'decided' GROUP BY type""", (user.hospital_id,)).fetchall()
        for r in rows:
            if r["type"] == "identity":
                ids = [r["payload"]["patient_a"], r["payload"]["patient_b"]]
                r["patients"] = conn.execute(
                    """SELECT p.id, p.display_name, p.sex, p.birth_year, p.created_at,
                              array_agg(DISTINCT i.kind || ':' || i.value) FILTER (WHERE i.kind IN ('phone','hospital_number','name'))
                                AS identifiers
                       FROM patients p LEFT JOIN patient_identifiers i ON i.patient_id = p.id
                       WHERE p.id = ANY(%s::uuid[]) GROUP BY p.id""", (ids,)).fetchall()
    return _j({"items": rows, "counts": {c["type"]: c["n"] for c in counts}})


@app.post("/api/review/{item_id}/identity")
def review_identity(item_id: str, body: dict[str, Any] = Body(...), user: User = require(*STEWARD)) -> dict[str, Any]:
    return reviews.decide_identity(user.hospital_id, item_id, bool(body["merge"]), user.name)


@app.post("/api/review/{item_id}/accept")
def review_accept(item_id: str, body: dict[str, Any] = Body(...), user: User = require(*STEWARD)) -> dict[str, Any]:
    with tx() as conn:
        ev = reviews.accept_row(conn, user.hospital_id, item_id, body.get("fields", {}), body["event_type"],
                                body["event_date"], user.name)
    return {"event_id": ev}


@app.post("/api/review/{item_id}/reject")
def review_reject(item_id: str, body: dict[str, Any] = Body(...), user: User = require(*STEWARD)) -> dict[str, Any]:
    with tx() as conn:
        reviews.reject_row(conn, user.hospital_id, item_id, body.get("reason") or "not usable", user.name)
    return {"ok": True}


@app.post("/api/review/{item_id}/reason")
def review_reason(item_id: str, body: dict[str, Any] = Body(...), user: User = require(*COORD)) -> dict[str, Any]:
    return callassist.confirm_reason(user.hospital_id, item_id, body["reason_code"], user.name)


@app.post("/api/merges/{merge_id}/reverse")
def merge_reverse(merge_id: str, user: User = require(*STEWARD)) -> dict[str, Any]:
    with tx() as conn:
        reviews.reverse_merge(conn, user.hospital_id, merge_id, user.name)
    return {"ok": True}


# ---------- stuck list (F11) ----------

@app.get("/api/stuck")
def stuck(pathway: str | None = None, kind: str | None = None, user: User = require(*COORD)) -> dict[str, Any]:
    with tx() as conn:
        rows = conn.execute(
            """SELECT f.id, f.kind, f.reason_line, f.rank_inputs, f.created_at, f.patient_id, p.display_name, p.sex,
                      p.birth_year, p.synthetic, pw.key AS pathway_key, pw.name AS pathway_name, v.version AS pathway_version,
                      o.from_step, o.expected_step, o.due_by, o.id AS obligation_id, x.rule_version, x.source_event_ids,
                      (SELECT e.source_ref FROM events e WHERE e.id = o.from_event_id) AS from_source,
                      (SELECT max(a.attempted_at) FROM contact_attempts a WHERE a.patient_id = f.patient_id) AS last_attempt
               FROM flags f JOIN patients p ON p.id = f.patient_id JOIN obligations o ON o.id = f.obligation_id
               JOIN pathway_versions v ON v.id = f.pathway_version_id JOIN pathways pw ON pw.id = v.pathway_id
               JOIN flag_explanations x ON x.flag_id = f.id
               WHERE f.hospital_id = %s AND f.state = 'open' AND v.active
                 AND (%s::text IS NULL OR pw.key = %s) AND (%s::text IS NULL OR f.kind = %s)""",
            (user.hospital_id, pathway, pathway, kind, kind)).fetchall()
        by_step = conn.execute(
            """SELECT o.expected_step, count(*) AS n FROM flags f JOIN obligations o ON o.id = f.obligation_id
               JOIN pathway_versions v ON v.id = f.pathway_version_id
               WHERE f.hospital_id = %s AND f.state = 'open' AND v.active GROUP BY o.expected_step ORDER BY n DESC""",
            (user.hospital_id,)).fetchall()
        today = one(conn, """SELECT
              (SELECT count(*) FROM contact_attempts WHERE hospital_id = %(h)s AND attempted_at::date = current_date) AS calls,
              (SELECT count(*) FROM contact_outcomes WHERE hospital_id = %(h)s AND created_at::date = current_date
                 AND outcome = 'callback') AS callbacks,
              (SELECT count(*) FROM nurse_items WHERE hospital_id = %(h)s AND state = 'open') AS needs_human""",
                    {"h": user.hospital_id})
        outcomes = conn.execute(
            """SELECT outcome, count(*) AS n FROM contact_outcomes WHERE hospital_id = %s AND created_at::date = current_date
               GROUP BY outcome""", (user.hospital_id,)).fetchall()
    ranked = rank([{**r, "rank_inputs": r["rank_inputs"]} for r in rows])
    return _j({"items": ranked, "by_step": by_step, "today": today, "outcomes": outcomes})


# ---------- patient timeline and why flagged (F8, F12) ----------

@app.get("/api/patients/{patient_id}")
def patient(patient_id: str, user: User = require(*READ_ALL)) -> dict[str, Any]:
    with tx() as conn:
        canon = one(conn, "SELECT canonical_id FROM patient_canonical WHERE patient_id = %s", (patient_id,))["canonical_id"]
        p = one(conn, "SELECT * FROM patients WHERE id = %s AND hospital_id = %s", (canon, user.hospital_id))
        ids = conn.execute(
            """SELECT i.kind, i.value, i.source_ref, i.patient_id FROM patient_identifiers i
               JOIN patient_canonical c ON c.patient_id = i.patient_id
               WHERE c.canonical_id = %s AND i.kind IN ('phone','hospital_number','name')""", (canon,)).fetchall()
        events = conn.execute(
            """SELECT id, type, occurred_at, effective_at, recorded_at, source_ref, confidence, payload, actor, synthetic
               FROM live_events WHERE canonical_id = %s AND hospital_id = %s ORDER BY effective_at, id""",
            (canon, user.hospital_id)).fetchall()
        corrections = conn.execute(
            """SELECT e.* FROM events e JOIN events o ON o.id = e.supersedes_id JOIN patient_canonical c ON c.patient_id = o.patient_id
               WHERE c.canonical_id = %s AND e.type = 'correction' ORDER BY e.recorded_at""", (canon,)).fetchall()
        obligations = conn.execute(
            """SELECT o.*, pw.name AS pathway_name, v.version, f.id AS flag_id, f.kind AS flag_kind, f.state AS flag_state,
                      f.reason_line
               FROM obligations o JOIN pathway_versions v ON v.id = o.pathway_version_id JOIN pathways pw ON pw.id = v.pathway_id
               LEFT JOIN flags f ON f.obligation_id = o.id
               WHERE o.patient_id = %s AND o.hospital_id = %s ORDER BY o.created_at""", (canon, user.hospital_id)).fetchall()
        merges = conn.execute(
            """SELECT * FROM patient_merges WHERE hospital_id = %s AND (into_patient = %s OR from_patient = %s)
               ORDER BY created_at""", (user.hospital_id, canon, canon)).fetchall()
        attempts = conn.execute(
            """SELECT a.*, o.outcome, o.reason_code, o.reason_confidence, o.reason_source, o.routed_to_nurse, o.id AS outcome_id
               FROM contact_attempts a LEFT JOIN contact_outcomes o ON o.attempt_id = a.id
               JOIN patient_canonical c ON c.patient_id = a.patient_id WHERE c.canonical_id = %s ORDER BY a.attempted_at""",
            (canon,)).fetchall()
    return _j({"patient": p, "identifiers": ids, "events": events, "corrections": corrections,
               "obligations": obligations, "merges": merges, "attempts": attempts})


# ---------- doctor panel: history points, no causes (history.py) ----------

@app.get("/api/doctor/patients")
def doctor_patients(q: str = Query("", max_length=60), user: User = require(*DOCTOR)) -> list[dict[str, Any]]:
    with tx() as conn:
        rows = conn.execute(
            """SELECT e.canonical_id AS id, p.display_name, p.sex, p.birth_year, count(*) AS points,
                      max(e.effective_at) AS last_at, bool_and(e.synthetic) AS synthetic
               FROM live_events e JOIN patients p ON p.id = e.canonical_id
               WHERE e.hospital_id = %s AND p.display_name ILIKE %s
               GROUP BY e.canonical_id, p.display_name, p.sex, p.birth_year
               ORDER BY max(e.effective_at) DESC, p.display_name LIMIT 100""",
            (user.hospital_id, f"%{q.strip()}%")).fetchall()
    return _j(rows)


@app.get("/api/doctor/patients/{patient_id}/history")
def doctor_history(patient_id: str, user: User = require(*DOCTOR)) -> dict[str, Any]:
    with tx() as conn:
        canon = one(conn, "SELECT canonical_id FROM patient_canonical WHERE patient_id = %s", (patient_id,))["canonical_id"]
        p = one(conn, "SELECT id, display_name, sex, birth_year, synthetic FROM patients WHERE id = %s AND hospital_id = %s",
                (canon, user.hospital_id))
        events = conn.execute(
            """SELECT id, type, effective_at, source_ref, confidence, payload, synthetic
               FROM live_events WHERE canonical_id = %s AND hospital_id = %s""", (canon, user.hospital_id)).fetchall()
    return _j({"patient": p, "points": build_history(events),
               "note": "History points are dates and steps taken from the files. Medora does not state causes."})


@app.get("/api/patients/{patient_id}/fhir")
def patient_fhir(patient_id: str, user: User = require(*READ_ALL)) -> JSONResponse:
    data = patient(patient_id, user)
    with tx() as conn:
        audit.append(conn, user.hospital_id, user.name, "export.fhir", "patient", data["patient"]["id"], {})
    return JSONResponse(fhir.bundle(data["patient"], data["identifiers"], data["events"], data["obligations"]),
                        media_type="application/fhir+json")


@app.get("/api/jobs/{job_id}/quality")
def job_quality(job_id: str, user: User = require(*READ_ALL)) -> dict[str, Any]:
    """Data-quality radar for one file: missing phones, unclear dates, rows already loaded."""
    with tx() as conn:
        j = one(conn, "SELECT * FROM ingest_jobs WHERE id = %s AND hospital_id = %s", (job_id, user.hospital_id))
        m = conn.execute("SELECT mapping FROM mappings WHERE id = %s", (j["mapping_id"],)).fetchone() if j["mapping_id"] else None
        dates = one(conn, "SELECT count(*) AS n FROM review_items WHERE job_id = %s AND type = 'date'", (job_id,))["n"]
    rows = max(int(j["rows_total"]), 1)
    phone_col = next((h for h, f in (m["mapping"]["columns"] if m else {}).items() if f == "phone"), None)
    filled = (j["profile"] or {}).get("columns", {}).get(phone_col, {}).get("filled", 0) if phone_col else 0
    return {"rows": j["rows_total"], "missing_phone_rate": round(1 - filled / rows, 4) if phone_col else None,
            "unclear_date_rate": round(dates / rows, 4), "already_loaded_rate": round(j["rows_skipped"] / rows, 4),
            "review_rate": round(j["rows_review"] / rows, 4)}


@app.get("/api/flags/{flag_id}")
def flag(flag_id: str, user: User = require(*READ_ALL)) -> dict[str, Any]:
    with tx() as conn:
        f = one(conn, """SELECT f.*, x.rule_version, x.steps, x.source_event_ids, x.result_hash, x.computed_at,
                                v.signed_by, v.signed_at, v.version, pw.name AS pathway_name
                         FROM flags f JOIN flag_explanations x ON x.flag_id = f.id
                         JOIN pathway_versions v ON v.id = f.pathway_version_id JOIN pathways pw ON pw.id = v.pathway_id
                         WHERE f.id = %s AND f.hospital_id = %s""", (flag_id, user.hospital_id))
        f["sources"] = conn.execute(
            "SELECT id, type, occurred_at, source_ref, confidence, payload FROM events WHERE id = ANY(%s::uuid[])",
            (f["source_event_ids"],)).fetchall()
        spec = one(conn, "SELECT spec FROM pathway_versions WHERE id = %s", (f["pathway_version_id"],))["spec"]
        g = next((g for g in gaps_from_spec(spec) if g.from_step == f["steps"]["from_step"]
                  and g.expected_step == f["steps"]["expected_step"]), None)
        f["gap"] = g.__dict__ if g else None
        f["obligation"] = one(conn, "SELECT * FROM obligations WHERE id = %s", (f["obligation_id"],))
    return _j(f)


@app.get("/api/flags/{flag_id}/replay")
def flag_replay(flag_id: str, user: User = require(*READ_ALL)) -> dict[str, Any]:
    with tx() as conn:
        return _j(engine.replay(conn, user.hospital_id, flag_id))


@app.get("/api/sources/{file_id}/rows/{row_no}")
def source_row(file_id: str, row_no: int, user: User = require(*READ_ALL)) -> dict[str, Any]:
    """Open the exact source row behind a value (S7)."""
    with tx() as conn:
        sf = one(conn, "SELECT * FROM source_files WHERE id = %s AND hospital_id = %s", (file_id, user.hospital_id))
        job = one(conn, "SELECT id, headers FROM ingest_jobs WHERE source_file_id = %s ORDER BY created_at LIMIT 1", (file_id,))
        ch = one(conn, "SELECT seq FROM ingest_chunks WHERE job_id = %s AND row_start <= %s AND row_end >= %s",
                 (job["id"], row_no, row_no))
    spool = ingest.upload_dir() / "spool" / str(job["id"]) / f"{ch['seq']:06d}.jsonl"
    with open(spool, encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            if item["r"] == row_no:
                return _j({"filename": sf["filename"], "kind": sf["kind"], "synthetic": sf["synthetic"], "row": row_no,
                           "headers": job["headers"], "values": item["v"]})
    raise LookupError("row not found in the source file")


@app.get("/api/sources/crops/{stem}/{name}")
def source_crop(stem: str, name: str, user: User = require(*READ_ALL)) -> FileResponse:
    with tx() as conn:
        sf = one(conn, "SELECT storage_path FROM source_files WHERE hospital_id = %s AND storage_path LIKE %s LIMIT 1",
                 (user.hospital_id, f"%{stem}%"))
    p = Path(sf["storage_path"]).parent / "crops" / stem / name
    if not p.is_file() or ".." in name:
        raise LookupError("crop not found")
    return FileResponse(p, media_type="image/png")


# ---------- call-assist (F13) and ledger (F10) ----------

@app.get("/api/flags/{flag_id}/call-card")
def call_card(flag_id: str, language: str = "en", user: User = require(*COORD)) -> dict[str, Any]:
    with tx() as conn:
        h = one(conn, "SELECT name FROM hospitals WHERE id = %s", (user.hospital_id,))
        return _j(callassist.call_card(conn, user.hospital_id, flag_id, user.name, h["name"], language))


@app.post("/api/flags/{flag_id}/attempts")
def new_attempt(flag_id: str, user: User = require(*COORD)) -> dict[str, Any]:
    with tx() as conn:
        return {"attempt_id": callassist.record_attempt(conn, user.hospital_id, flag_id, user.name)}


@app.post("/api/attempts/{attempt_id}/outcome")
async def attempt_outcome(attempt_id: str, outcome: str = Form(...), source: str = Form(...),
                          reason_code: str | None = Form(None), note: str | None = Form(None),
                          language: str | None = Form(None), audio: UploadFile | None = File(None),
                          user: User = require(*COORD)) -> dict[str, Any]:
    data = await audio.read() if audio else None
    return _j(callassist.record_outcome(user.hospital_id, attempt_id, outcome, source, user.name, reason_code=reason_code,
                                        note=note, audio=data, audio_name=(audio.filename if audio else "memo.webm") or "memo.webm",
                                        language=language))


@app.post("/api/outcomes/{outcome_id}/override")
def outcome_override(outcome_id: str, body: dict[str, Any] = Body(...), user: User = require(*COORD)) -> dict[str, Any]:
    with tx() as conn:
        callassist.override_reason(conn, user.hospital_id, outcome_id, body["reason_code"], user.name)
    return {"ok": True}


@app.post("/api/obligations/{obligation_id}/close")
def obligation_close(obligation_id: str, body: dict[str, Any] = Body(...), user: User = require(*COORD)) -> dict[str, Any]:
    with tx() as conn:
        callassist.close_obligation(conn, user.hospital_id, obligation_id, user.name,
                                    reason_code=body.get("reason_code"), evidence_event_id=body.get("evidence_event_id"))
    return {"ok": True}


@app.get("/api/reason-codes")
def reason_codes(user: User = require(*READ_ALL)) -> list[dict[str, Any]]:
    with tx() as conn:
        return _j(conn.execute("SELECT * FROM reason_codes ORDER BY category, code").fetchall())


# ---------- nurse queue (F14) ----------

@app.get("/api/nurse")
def nurse(state: str = "open", user: User = require(*CLINICAL_QUEUE, "admin")) -> list[dict[str, Any]]:
    with tx() as conn:
        return _j(conn.execute(
            """SELECT n.*, p.display_name, p.sex, p.birth_year,
                      (SELECT value FROM patient_identifiers WHERE patient_id = n.patient_id AND kind = 'phone' LIMIT 1) AS phone
               FROM nurse_items n LEFT JOIN patients p ON p.id = n.patient_id
               WHERE n.hospital_id = %s AND n.state = %s ORDER BY n.created_at""", (user.hospital_id, state)).fetchall())


@app.post("/api/nurse/{item_id}/handle")
def nurse_handle(item_id: str, body: dict[str, Any] = Body(default={}), user: User = require(*CLINICAL_QUEUE)) -> dict[str, Any]:
    with tx() as conn:
        r = conn.execute("""UPDATE nurse_items SET state = 'handled', handled_by = %s, handled_at = now(), handled_note = %s
                            WHERE id = %s AND hospital_id = %s AND state = 'open' RETURNING id""",
                         (user.name, (body.get("note") or "")[:500] or None, item_id, user.hospital_id)).fetchone()
        if not r:
            raise LookupError("item not found or already handled")
        audit.append(conn, user.hospital_id, user.name, "nurse.handled", "nurse_item", item_id, {})
    return {"ok": True}


@app.post("/api/assist/message")
def assist_message(body: dict[str, Any] = Body(...), user: User = require(*READ_ALL)) -> dict[str, Any]:
    """A pasted patient message or a question to Medora. Medora never answers medical questions."""
    text = str(body.get("text") or "")[:2000]
    trip = tripwire.check(text)
    with tx() as conn:
        if trip.routed:
            ni = one(conn, """INSERT INTO nurse_items (hospital_id, patient_id, source, route, excerpt, matched, created_by)
                              VALUES (%s,%s,'message',%s,%s,%s,%s) RETURNING id""",
                     (user.hospital_id, body.get("patient_id"), trip.route, text, Jsonb(trip.as_dict()), user.name))
            audit.append(conn, user.hospital_id, "tripwire", "tripwire.route", "nurse_item", ni["id"],
                         {"route": trip.route, "categories": trip.categories})
            return {**trip.as_dict(), "nurse_item_id": str(ni["id"]), "reply": None}
    return {**trip.as_dict(), "reply": None}


# ---------- pathways (F9) ----------

@app.get("/api/pathways")
def pathway_list(user: User = require(*READ_ALL)) -> list[dict[str, Any]]:
    with tx() as conn:
        return _j(conn.execute(
            """SELECT v.id, v.version, v.spec, v.yaml, v.compiled_sql, v.content_hash, v.demo, v.signed_by, v.signed_role,
                      v.signed_at, v.active, v.created_at, pw.key, pw.name,
                      (SELECT count(*) FROM flags f WHERE f.pathway_version_id = v.id AND f.state = 'open') AS open_flags,
                      (SELECT count(*) FROM obligations o WHERE o.pathway_version_id = v.id AND o.state = 'open') AS open_obligations
               FROM pathway_versions v JOIN pathways pw ON pw.id = v.pathway_id
               WHERE v.hospital_id = %s ORDER BY pw.key, v.version DESC""", (user.hospital_id,)).fetchall())


@app.post("/api/pathways")
def pathway_register(body: dict[str, Any] = Body(...), user: User = require("clinical_lead", "admin", "data_steward")) -> dict[str, Any]:
    with tx() as conn:
        v = pathways.register(conn, user.hospital_id, body["yaml"], user.name)
    return _j({"id": v["id"], "version": v["version"], "signed_by": v["signed_by"]})


@app.post("/api/pathways/{version_id}/sign")
def pathway_sign(version_id: str, user: User = require("clinical_lead")) -> dict[str, Any]:
    with tx() as conn:
        pathways.sign(conn, user.hospital_id, version_id, user.name, user.role)
    return {"ok": True}


@app.post("/api/pathways/{version_id}/activate")
def pathway_activate(version_id: str, user: User = require("clinical_lead", "admin")) -> dict[str, Any]:
    with tx() as conn:
        pathways.activate(conn, user.hospital_id, version_id, user.name)
        v = one(conn, "SELECT * FROM pathway_versions WHERE id = %s", (version_id,))
        stats = engine.evaluate(conn, user.hospital_id, v, actor=user.name)
    return {"ok": True, "stats": stats}


@app.get("/api/pathways/{version_id}/preview")
def pathway_preview(version_id: str, user: User = require(*READ_ALL)) -> dict[str, Any]:
    """Unsigned versions can be previewed, never activated. Nothing is written."""
    with tx() as conn:
        v = one(conn, "SELECT * FROM pathway_versions WHERE id = %s AND hospital_id = %s", (version_id, user.hospital_id))
        decisions = engine.decide(conn, user.hospital_id, v, datetime.now(UTC))
        names = {str(r["id"]): r["display_name"] for r in conn.execute(
            "SELECT id, display_name FROM patients WHERE id = ANY(%s::uuid[])", ([pid for pid, _ in decisions],)).fetchall()}
        conn.rollback()
    items = [{"patient_id": pid, "display_name": names.get(pid), "kind": d.flag_kind, "reason_line": d.reason_line,
              "rank_inputs": d.rank_inputs(pid), "steps": d.steps} for pid, d in decisions if d.flag_kind]
    return _j({"preview": True, "signed": bool(v["signed_by"]), "demo": v["demo"], "items": rank(items)})


# ---------- trust (F16) and audit ----------

TRUST_KINDS = ["gold_extraction_structured", "gold_extraction_scan", "gold_identity", "harness", "replay", "bench",
               "audit_chain", "llm_eval_mapping", "llm_eval_reason"]


@app.get("/api/trust")
def trust(user: User = require(*READ_ALL)) -> dict[str, Any]:
    with tx() as conn:
        runs = evals.latest(conn, TRUST_KINDS, user.hospital_id)
        review = conn.execute("""SELECT type, count(*) AS n FROM review_items WHERE hospital_id = %s AND state <> 'decided'
                                 GROUP BY type""", (user.hospital_id,)).fetchall()
        versions = conn.execute("""SELECT pw.key, v.version, v.signed_by FROM pathway_versions v
                                   JOIN pathways pw ON pw.id = v.pathway_id WHERE v.hospital_id = %s AND v.active""",
                                (user.hospital_id,)).fetchall()
    return _j({"runs": runs, "review": {r["type"]: r["n"] for r in review}, "active_pathways": versions,
               "synthetic": True, "replay": llm.mode() == "replay"})


@app.post("/api/trust/verify-chain")
def trust_verify(user: User = require(*READ_ALL)) -> dict[str, Any]:
    with tx() as conn:
        res = audit.verify_chain(conn, user.hospital_id)
        run = evals.record(conn, "audit_chain", [evals.Metric("chain_valid", 1.0 if res["valid"] else 0.0, 1.0),
                                                 evals.Metric("entries_checked", float(res["checked"]))],
                           summary=res, hospital_id=user.hospital_id)
    return {**res, "run_id": run}


@app.post("/api/trust/replay")
def trust_replay(user: User = require(*READ_ALL)) -> dict[str, Any]:
    """F12 at scale: replay every open flag and record the match rate as an eval run."""
    with tx() as conn:
        return record_replay(conn, user.hospital_id)


def record_replay(conn: Any, hospital_id: str) -> dict[str, Any]:
    ids = [str(r["id"]) for r in conn.execute("SELECT id FROM flags WHERE hospital_id = %s AND state = 'open'",
                                              (hospital_id,)).fetchall()]
    matched = sum(engine.replay(conn, hospital_id, f)["match"] for f in ids)
    rate = matched / len(ids) if ids else 1.0
    run = evals.record(conn, "replay", [evals.Metric("replay_match_rate", rate, 1.0), evals.Metric("flags_replayed", float(len(ids)))],
                       summary={"mismatches": len(ids) - matched}, hospital_id=hospital_id)
    return {"run_id": run, "flags": len(ids), "matched": matched, "rate": rate}


@app.get("/api/eval-runs/{run_id}")
def eval_run(run_id: str, user: User = require(*READ_ALL)) -> dict[str, Any]:
    with tx() as conn:
        run = one(conn, "SELECT * FROM eval_runs WHERE id = %s AND (hospital_id IS NULL OR hospital_id = %s)",
                  (run_id, user.hospital_id))
        run["results"] = conn.execute("SELECT * FROM eval_results WHERE run_id = %s ORDER BY metric", (run_id,)).fetchall()
    return _j(run)


@app.get("/api/audit")
def audit_log(limit: int = Query(100, le=500), before: int | None = None, action: str | None = None,
              user: User = require(*READ_ALL)) -> dict[str, Any]:
    with tx() as conn:
        rows = conn.execute(
            """SELECT seq, id, at, actor, action, object_type, object_id, detail, prev_hash, entry_hash FROM audit_log
               WHERE hospital_id = %s AND (%s::bigint IS NULL OR seq < %s) AND (%s::text IS NULL OR action LIKE %s)
               ORDER BY seq DESC LIMIT %s""",
            (user.hospital_id, before, before, action, f"{action}%" if action else None, limit)).fetchall()
        total = one(conn, "SELECT count(*) AS n FROM audit_log WHERE hospital_id = %s", (user.hospital_id,))["n"]
        actions = conn.execute("""SELECT split_part(action, '.', 1) AS area, count(*) AS n FROM audit_log
                                  WHERE hospital_id = %s GROUP BY 1 ORDER BY 2 DESC""", (user.hospital_id,)).fetchall()
    return _j({"entries": rows, "total": total, "areas": actions})
