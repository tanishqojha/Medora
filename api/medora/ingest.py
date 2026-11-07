"""File intake, job control and chunk processing (F1, F2, S4).

Upload -> source_files (hash) -> ingest_jobs. The worker plans a job in one streaming pass: it spools rows
into chunk files, hashes each chunk and profiles columns. Each chunk is then processed in a single
transaction (events + review items + chunk done), so a killed worker never leaves a half chunk and a
restarted worker never redoes a finished one.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from medora import audit, engine, mapping, messy, readers
from medora.config import ROOT, env, setting
from medora.dates import detect_convention
from medora.db import Conn, one
from medora.events import NewEvent, bulk_append
from medora.hashing import sha256
from medora.identity import Record, best_match

log = logging.getLogger("medora.ingest")
LEASE_MINUTES = 2
KINDS = {".csv": "csv", ".xlsx": "xlsx", ".pdf": "pdf", ".png": "image", ".jpg": "image", ".jpeg": "image"}
MAGIC = {"xlsx": b"PK\x03\x04", "pdf": b"%PDF", "png": b"\x89PNG", "jpg": b"\xff\xd8\xff"}


class IntakeRejected(ValueError):
    pass


def upload_dir() -> Path:
    p = Path(env("UPLOAD_DIR", str(ROOT / "uploads")))
    if not p.is_absolute():
        p = ROOT / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def detect_kind(filename: str, head: bytes) -> str:
    ext = Path(filename).suffix.lower()
    kind = KINDS.get(ext)
    if not kind:
        raise IntakeRejected(f"file type {ext or '(none)'} is not accepted. Use CSV, XLSX, PDF, PNG or JPG.")
    if kind == "xlsx" and not head.startswith(MAGIC["xlsx"]):
        raise IntakeRejected("file says .xlsx but is not an Excel workbook")
    if kind == "pdf" and not head.startswith(MAGIC["pdf"]):
        raise IntakeRejected("file says .pdf but is not a PDF")
    if kind == "image" and not (head.startswith(MAGIC["png"]) or head.startswith(MAGIC["jpg"])):
        raise IntakeRejected("image must be PNG or JPG")
    if kind == "csv" and b"\x00" in head[:4096]:
        raise IntakeRejected("CSV contains binary data")
    return kind


def intake(conn: Conn, hospital_id: str, filename: str, tmp_path: Path, actor: str) -> dict[str, Any]:
    """Register an uploaded file (already streamed to tmp_path) and create a job. Same content = same job."""
    size = tmp_path.stat().st_size
    if size > int(setting("ingest.max_upload_mb")) * 1024 * 1024:
        tmp_path.unlink(missing_ok=True)
        raise IntakeRejected("file is larger than the upload limit")
    with open(tmp_path, "rb") as f:
        head = f.read(8192)
    try:
        kind = detect_kind(filename, head)
    except IntakeRejected:
        tmp_path.unlink(missing_ok=True)
        raise
    h = hashlib.sha256()
    with open(tmp_path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    content_hash = h.hexdigest()
    existing = conn.execute(
        """SELECT j.* FROM ingest_jobs j JOIN source_files s ON s.id = j.source_file_id
           WHERE s.hospital_id = %s AND s.content_hash = %s AND j.state <> 'failed'
           ORDER BY j.created_at LIMIT 1""", (hospital_id, content_hash)).fetchone()
    if existing:
        tmp_path.unlink(missing_ok=True)
        audit.append(conn, hospital_id, actor, "ingest.duplicate_upload", "ingest_job", existing["id"],
                     {"content_hash": content_hash})
        return {**existing, "duplicate": True}
    dest = upload_dir() / str(hospital_id) / f"{content_hash}{Path(filename).suffix.lower()}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.replace(dest)
    safe_name = re.sub(r"[^\w.\- ]", "_", Path(filename).name)[:200]
    sf = one(conn, 
        """INSERT INTO source_files (hospital_id, filename, kind, content_hash, size_bytes, storage_path, uploaded_by)
           VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (hospital_id, safe_name, kind, content_hash, size, str(dest), actor))
    job = one(conn, 
        "INSERT INTO ingest_jobs (hospital_id, source_file_id, created_by) VALUES (%s,%s,%s) RETURNING *",
        (hospital_id, sf["id"], actor))
    audit.append(conn, hospital_id, actor, "ingest.upload", "ingest_job", job["id"],
                 {"file": safe_name, "kind": kind, "size": size, "content_hash": content_hash})
    return {**job, "duplicate": False}


# ---------- job control ----------

_TRANSITIONS = {"pause": ({"running", "queued", "needs_mapping"}, "paused"),
                "kill": ({"running", "queued", "paused", "needs_mapping"}, "killed"),
                "resume": ({"paused", "killed"}, None)}


def control(conn: Conn, hospital_id: str, job_id: str, action: str, actor: str) -> dict[str, Any]:
    allowed, target = _TRANSITIONS[action]
    job = conn.execute("SELECT * FROM ingest_jobs WHERE id = %s AND hospital_id = %s FOR UPDATE",
                       (job_id, hospital_id)).fetchone()
    if not job:
        raise LookupError("job not found")
    if job["state"] not in allowed:
        raise IntakeRejected(f"cannot {action} a job that is {job['state']}")
    if action == "resume":
        target = "running" if job["mapping_id"] else ("queued" if not job["fingerprint"] else "needs_mapping")
    conn.execute("UPDATE ingest_jobs SET state = %s, updated_at = now() WHERE id = %s", (target, job_id))
    audit.append(conn, hospital_id, actor, f"ingest.{action}", "ingest_job", job_id, {"from": job["state"], "to": target})
    return {**job, "state": target}


# ---------- planning (worker) ----------

def _spool_dir(job_id: str) -> Path:
    d = upload_dir() / "spool" / str(job_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _rows(path: Path, kind: str) -> Any:
    if kind in ("csv", "xlsx"):
        return readers.reader(path, kind)
    return messy.reader(path, kind)


def _plain(v: Any) -> Any:
    return v["v"] if isinstance(v, dict) and "v" in v else v


def plan(conn: Conn, job: dict[str, Any]) -> None:
    """One streaming pass: spool chunk files, hash chunks, profile columns, then look up or propose a mapping."""
    sf = one(conn, "SELECT * FROM source_files WHERE id = %s", (job["source_file_id"],))
    chunk_rows = int(setting("ingest.chunk_rows"))
    spool = _spool_dir(job["id"])
    it = _rows(Path(sf["storage_path"]), sf["kind"])
    headers: list[str] = [str(h) for h in next(it)]
    if not headers:
        raise IntakeRejected("file has no header row")
    labels: dict[str, set[str] | None] = {h: set() for h in headers}
    filled = dict.fromkeys(headers, 0)
    date_samples: list[Any] = []
    sample: list[list[Any]] = []
    chunks: list[tuple[int, int, int, str]] = []
    buf: list[str] = []
    first_row = 0
    total = 0

    def flush(seq: int, last_row: int) -> None:
        body = "\n".join(buf) + "\n"
        (spool / f"{seq:06d}.jsonl").write_text(body, encoding="utf-8")
        chunks.append((seq, first_row, last_row, sha256(sf["content_hash"] + body)))
        buf.clear()

    last = 0
    for row_no, values in it:
        if not buf:
            first_row = row_no
        buf.append(json.dumps({"r": row_no, "v": values}, ensure_ascii=False, default=str))
        total += 1
        last = row_no
        if len(sample) < 20:
            sample.append([_plain(v) for v in values])
        for h, v in zip(headers, values, strict=False):
            pv = _plain(v)
            if pv in (None, ""):
                continue
            filled[h] += 1
            s = labels[h]
            if s is not None:
                text = str(pv)
                if len(text) > 60 or len(s) >= 50:
                    labels[h] = None  # high-cardinality column: not a label column, stop tracking
                else:
                    s.add(text)
            if len(date_samples) < 3000 and isinstance(pv, str) and re.fullmatch(r"[\d०-९]{1,2}[-/.][\d०-९]{1,2}[-/.][\d०-९]{2,4}", pv):
                date_samples.append(pv)
        if len(buf) >= chunk_rows:
            flush(len(chunks) + 1, row_no)
    if buf:
        flush(len(chunks) + 1, last)

    profile = {"columns": {h: {"filled": filled[h], "labels": sorted(labels[h] or [])}
                           for h in headers},
               "date_convention_hint": detect_convention(date_samples), "rows": total, "sample": sample[:5]}
    fp = mapping.fingerprint(headers) if sf["kind"] in ("csv", "xlsx") else "messy:" + mapping.fingerprint(headers)
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO ingest_chunks (hospital_id, job_id, seq, row_start, row_end, content_hash)
               VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (job_id, seq) DO NOTHING""",
            [(job["hospital_id"], job["id"], s, a, b, h) for s, a, b, h in chunks])
    confirmed = mapping.find_confirmed(conn, job["hospital_id"], fp)
    state = "running" if confirmed else "needs_mapping"
    conn.execute(
        """UPDATE ingest_jobs SET fingerprint = %s, headers = %s, profile = %s, total_chunks = %s, rows_total = %s,
                  mapping_id = %s, state = CASE WHEN state = 'queued' THEN %s ELSE state END, updated_at = now()
           WHERE id = %s""",
        (fp, Jsonb(headers), Jsonb(profile), len(chunks), total, confirmed["id"] if confirmed else None, state,
         job["id"]))
    audit.append(conn, job["hospital_id"], "worker", "ingest.planned", "ingest_job", job["id"],
                 {"rows": total, "chunks": len(chunks), "mapping_reused": bool(confirmed)})
    if not confirmed:
        proposal = mapping.propose(headers, sample, profile)
        conn.execute("UPDATE ingest_jobs SET llm_calls = llm_calls + %s WHERE id = %s",
                     (proposal["llm_calls"], job["id"]))
        conn.execute(
            """INSERT INTO review_items (hospital_id, type, payload, job_id, dedupe_key, due_at)
               VALUES (%s, 'mapping', %s, %s, %s, now() + make_interval(hours => %s))
               ON CONFLICT (hospital_id, dedupe_key) DO NOTHING""",
            (job["hospital_id"], Jsonb({"fingerprint": fp, "headers": headers, **proposal}), job["id"],
             f"mapping:{job['id']}", int(setting("review.escalate_after_hours"))))


# ---------- chunk processing (worker) ----------

def claim_chunk(conn: Conn, worker: str) -> dict[str, Any] | None:
    """SKIP LOCKED claim. A chunk left 'running' past the lease (worker killed) is claimable again."""
    return conn.execute(
        f"""UPDATE ingest_chunks c SET state = 'running', worker = %s, started_at = now(), attempts = attempts + 1
            WHERE c.id = (
              SELECT c2.id FROM ingest_chunks c2 JOIN ingest_jobs j ON j.id = c2.job_id
              WHERE j.state = 'running'
                AND (c2.state = 'pending'
                     OR (c2.state = 'running' AND c2.started_at < now() - interval '{LEASE_MINUTES} minutes'))
              ORDER BY j.created_at, c2.seq
              FOR UPDATE OF c2 SKIP LOCKED LIMIT 1)
            RETURNING c.*""", (worker,)).fetchone()


def _resolve_identities(conn: Conn, hospital_id: str, recs: dict[str, Record],
                        src: dict[str, dict[str, Any]]) -> dict[str, str]:
    """exact_key -> patient_id. Creates patients for new keys and scores them against candidates (F7)."""
    # Chunks of one hospital resolve identities one at a time (lock held until the chunk commits), so two
    # workers never create the same person twice in parallel transactions that cannot see each other.
    # ponytail: per-hospital lock serialises this step; partition by blocking key if throughput ever needs it.
    conn.execute("SELECT pg_advisory_xact_lock(hashtext('identity:' || %s))", (str(hospital_id),))
    keys = list(recs)
    found = {r["value"]: str(r["patient_id"]) for r in conn.execute(
        """SELECT value, patient_id FROM patient_identifiers
           WHERE hospital_id = %s AND kind = 'exact_key' AND value = ANY(%s)""", (hospital_id, keys)).fetchall()}
    new = [k for k in keys if k not in found]
    if not new:
        return found
    # One batched insert, ids made here, instead of a round trip per patient.
    created = {k: str(uuid.uuid4()) for k in new}
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO patients (id, hospital_id, display_name, sex, birth_year) VALUES (%s,%s,%s,%s,%s)",
            [(created[k], hospital_id, recs[k].name or recs[k].norm_name or "Unnamed", recs[k].sex, recs[k].birth_year)
             for k in new])
        ident_rows = []
        for k, pid in created.items():
            r = recs[k]
            ref = Jsonb(src[k])
            ident_rows.append((hospital_id, pid, "exact_key", k, ref))
            for kind, val in (("phone", r.phone), ("hospital_number", r.hospital_number), ("name", r.name),
                              ("name_latin", r.norm_name), ("phonetic", r.phonetic)):
                if val:
                    ident_rows.append((hospital_id, pid, kind, val, ref))
        cur.executemany(
            """INSERT INTO patient_identifiers (hospital_id, patient_id, kind, value, source_ref)
               VALUES (%s,%s,%s,%s,%s) ON CONFLICT (patient_id, kind, value) DO NOTHING""", ident_rows)
    found.update(created)

    def keys_of(r: Record) -> list[tuple[str, str]]:
        return [(kind, v) for kind, v in (("phone", r.phone), ("hospital_number", r.hospital_number),
                                          ("phonetic", r.phonetic)) if v]

    wanted = {kv for k in new for kv in keys_of(recs[k])}
    blocks: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in conn.execute(
        """SELECT i.kind, i.value, c.canonical_id::text AS pid FROM patient_identifiers i
           JOIN patient_canonical c ON c.patient_id = i.patient_id
           WHERE i.hospital_id = %s AND i.kind IN ('phone', 'hospital_number', 'phonetic') AND i.value = ANY(%s)""",
        (hospital_id, sorted({v for _, v in wanted}))).fetchall():
        if (row["kind"], row["value"]) in wanted:
            blocks[(row["kind"], row["value"])].add(row["pid"])
    cand_ids = sorted(set().union(*blocks.values())) if blocks else []
    cands: dict[str, Record] = {}
    if cand_ids:
        info = conn.execute(
            """SELECT p.id::text AS pid, p.display_name, p.sex, p.birth_year,
                      (SELECT value FROM patient_identifiers WHERE patient_id = p.id AND kind = 'phone' LIMIT 1) AS phone,
                      (SELECT value FROM patient_identifiers WHERE patient_id = p.id AND kind = 'hospital_number' LIMIT 1) AS hn
               FROM patients p WHERE p.id = ANY(%s::uuid[])""", (cand_ids,)).fetchall()
        cands = {r["pid"]: Record(name=r["display_name"], phone=r["phone"], hospital_number=r["hn"], sex=r["sex"],
                                  birth_year=r["birth_year"]) for r in info}
    # Merge direction is always new into older: a record never sees itself or anything created after it in this
    # batch, so two new records can never link into each other (a cycle would hide both timelines).
    later = set(created.values())
    for k in new:
        pid = created[k]
        later.discard(pid)
        near = set().union(*(blocks.get(kv, set()) for kv in keys_of(recs[k]))) - later - {pid}
        target, m = best_match(recs[k], [(cid, cands[cid]) for cid in sorted(near) if cid in cands])
        if target is None or m.outcome == "apart":
            continue
        if m.outcome == "auto_merge":
            mid = conn.execute(
                """INSERT INTO patient_merges (hospital_id, from_patient, into_patient, outcome, score, features, decided_by)
                   VALUES (%s,%s,%s,'auto_merge',%s,%s,'identity_rules') ON CONFLICT DO NOTHING RETURNING id""",
                (hospital_id, pid, target, m.score, Jsonb(m.features))).fetchone()
            if mid:
                audit.append(conn, hospital_id, "identity_rules", "identity.auto_merge", "patient_merge", mid["id"],
                             {"from": pid, "into": target, "score": m.score})
        else:
            pair = sorted([pid, target])
            conn.execute(
                """INSERT INTO review_items (hospital_id, type, payload, source_ref, confidence, dedupe_key, due_at)
                   VALUES (%s,'identity',%s,%s,%s,%s, now() + make_interval(hours => %s))
                   ON CONFLICT (hospital_id, dedupe_key) DO NOTHING""",
                (hospital_id, Jsonb({"patient_a": pid, "patient_b": target, "score": m.score,
                                     "features": m.features}), Jsonb(src[k]), m.score,
                 f"identity:{pair[0]}:{pair[1]}", int(setting("review.escalate_after_hours"))))
    return found


def process_chunk(conn: Conn, chunk: dict[str, Any]) -> dict[str, Any]:
    job = one(conn, "SELECT * FROM ingest_jobs WHERE id = %s", (chunk["job_id"],))
    hospital_id = str(job["hospital_id"])
    sf = one(conn, "SELECT * FROM source_files WHERE id = %s", (job["source_file_id"],))
    # A chunk with identical content already loaded for this hospital: skip, nothing to recompute.
    dup = conn.execute(
        """SELECT 1 FROM ingest_chunks WHERE hospital_id = %s AND content_hash = %s AND state = 'done' AND id <> %s
           LIMIT 1""", (hospital_id, chunk["content_hash"], chunk["id"])).fetchone()
    if dup:
        n = chunk["row_end"] - chunk["row_start"] + 1
        _finish(conn, job, chunk, 0, n, 0)
        return {"loaded": 0, "skipped": n, "review": 0, "patients": []}
    mp = one(conn, "SELECT * FROM mappings WHERE id = %s", (job["mapping_id"],))
    m = mp["mapping"]
    headers = job["headers"]
    min_conf = float(setting("messy.field_min_confidence"))
    lines = (_spool_dir(job["id"]) / f"{chunk['seq']:06d}.jsonl").read_text(encoding="utf-8").splitlines()

    pending: list[tuple[int, str, Any, dict[str, Any], float]] = []
    reviews: list[tuple[Any, ...]] = []
    recs: dict[str, Record] = {}
    srcs: dict[str, dict[str, Any]] = {}
    for line in lines:
        if not line:
            continue
        item = json.loads(line)
        row_no, raw = item["r"], item["v"]
        conf = 1.0
        crops: dict[str, Any] = {}
        values: dict[str, Any] = {}
        for h, v in zip(headers, raw, strict=False):
            if isinstance(v, dict) and "v" in v:
                values[h] = v["v"]
                conf = min(conf, float(v.get("c", 0)))
                if v.get("ref"):
                    crops[h] = v["ref"]
            else:
                values[h] = v
        ap = mapping.apply_row(m, values)
        src = {"kind": "file_row" if not crops else "file_crop", "file": str(sf["id"]), "file_hash": sf["content_hash"],
               "filename": sf["filename"], "row": row_no, "cells": ap.cells}
        if crops:
            src["crops"] = crops
        rowkey = sha256(f"{sf['content_hash']}:{row_no}:{json.dumps(raw, ensure_ascii=False, default=str)}")
        whitelisted = {k: (str(v) if v is not None else None) for k, v in ap.fields.items()}
        if ap.problems or conf < min_conf:
            ambiguous = ap.occurred.ambiguous or bool(ap.appointment and ap.appointment.ambiguous)
            rtype = "extraction" if conf < min_conf else ("date" if ambiguous else "row")
            payload = {"row": row_no, "fields": whitelisted, "problems": ap.problems or ["low read confidence"],
                       "event_type": ap.event_type,
                       "date_candidates": [d.isoformat() for d in ap.occurred.candidates]}
            reviews.append((hospital_id, rtype, Jsonb(payload), Jsonb(src), conf, job["id"], f"row:{rowkey}"))
            continue
        rec = Record(name=str(ap.fields.get("patient_name") or ""), phone=ap.fields.get("phone"),
                     hospital_number=ap.fields.get("hospital_number"), sex=_sex(ap.fields.get("sex")),
                     birth_year=_birth_year(ap.fields, ap.occurred.value.year if ap.occurred.value else None))
        k = rec.exact_key()
        recs.setdefault(k, rec)
        srcs.setdefault(k, src)
        payload = {"event_label": str(ap.fields.get("event_type") or ap.fields.get("status") or "") or None,
                   "department": ap.fields.get("department"),
                   "status_label": ap.fields.get("status"),
                   "appointment_date": ap.appointment.value.isoformat() if ap.appointment and ap.appointment.value else None}
        payload = {k2: str(v) for k2, v in payload.items() if v not in (None, "")}
        pending.append((row_no, k, ap, {**src, "_payload": payload, "_key": rowkey}, conf))

    patient_of = _resolve_identities(conn, hospital_id, recs, srcs) if recs else {}
    evs = []
    for _row_no, k, ap, src, conf in pending:
        payload = src.pop("_payload")
        rowkey = src.pop("_key")
        assert ap.event_type is not None
        evs.append(NewEvent(hospital_id=hospital_id, type=ap.event_type, occurred_at=ap.occurred.as_datetime(),
                            source_ref=src, confidence=conf, actor=f"ingest:{job['id']}", patient_id=patient_of[k],
                            payload=payload, dedupe_key=rowkey))
    loaded = bulk_append(conn, evs)
    if reviews:
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO review_items (hospital_id, type, payload, source_ref, confidence, job_id, dedupe_key)
                   VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (hospital_id, dedupe_key) DO NOTHING""", reviews)
    touched = sorted({patient_of[k] for _, k, *_ in pending})
    _finish(conn, job, chunk, loaded, len(evs) - loaded, len(reviews))
    if loaded and touched:
        # Incremental recompute: only patients touched by new events (PRD 13).
        engine.evaluate_active(conn, hospital_id, patients=_canonical(conn, touched), actor="worker")
    return {"loaded": loaded, "skipped": len(evs) - loaded, "review": len(reviews), "patients": touched}


def _canonical(conn: Conn, pids: list[str]) -> list[str]:
    rows = conn.execute("SELECT DISTINCT canonical_id::text AS c FROM patient_canonical WHERE patient_id = ANY(%s::uuid[])",
                        (pids,)).fetchall()
    return [r["c"] for r in rows]


def _finish(conn: Conn, job: dict[str, Any], chunk: dict[str, Any], loaded: int, skipped: int,
            review: int) -> None:
    conn.execute(
        """UPDATE ingest_chunks SET state = 'done', finished_at = now(), rows_loaded = %s, rows_skipped = %s,
                  rows_review = %s, error = NULL WHERE id = %s""", (loaded, skipped, review, chunk["id"]))
    row = one(conn,
        """UPDATE ingest_jobs SET done_chunks = (SELECT count(*) FROM ingest_chunks WHERE job_id = %s AND state = 'done'),
                  rows_loaded = rows_loaded + %s, rows_skipped = rows_skipped + %s, rows_review = rows_review + %s,
                  updated_at = now()
           WHERE id = %s RETURNING done_chunks, total_chunks, state""",
        (job["id"], loaded, skipped, review, job["id"]))
    if row["done_chunks"] >= row["total_chunks"] and row["state"] == "running":
        conn.execute("UPDATE ingest_jobs SET state = 'done', updated_at = now() WHERE id = %s", (job["id"],))
        audit.append(conn, job["hospital_id"], "worker", "ingest.done", "ingest_job", job["id"],
                     {"chunks": row["total_chunks"]})


def fail_chunk(conn: Conn, chunk_id: str, error: str) -> None:
    conn.execute("UPDATE ingest_chunks SET state = 'failed', error = %s, finished_at = now() WHERE id = %s",
                 (error[:500], chunk_id))


def _sex(v: Any) -> str | None:
    if v in (None, ""):
        return None
    s = str(v).strip().lower()
    if s in ("f", "female", "w", "woman", "महिला", "स्त्री"):
        return "F"
    if s in ("m", "male", "man", "पुरुष"):
        return "M"
    return "U"


def _birth_year(fields: dict[str, Any], event_year: int | None) -> int | None:
    for key in ("birth_year",):
        v = fields.get(key)
        if v not in (None, "") and re.fullmatch(r"\d{4}", str(v).strip()):
            return int(str(v).strip())
    age = fields.get("age")
    if age not in (None, "") and event_year and re.fullmatch(r"\d{1,3}", str(age).strip()):
        return event_year - int(str(age).strip())
    return None


def chunk_counts(conn: Conn, job_id: str) -> dict[str, int]:
    rows = conn.execute("SELECT state, count(*) AS n FROM ingest_chunks WHERE job_id = %s GROUP BY state",
                        (job_id,)).fetchall()
    out: dict[str, int] = defaultdict(int)
    for r in rows:
        out[r["state"]] = r["n"]
    return dict(out)
