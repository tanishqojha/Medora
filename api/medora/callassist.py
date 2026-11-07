"""Call-assist (F10, F13, S19, S20). Outreach is a person on a phone. Medora never messages a patient.

Outcome by one tap, typed note or voice memo. Text always passes the symptom tripwire first; if it fires the
text goes to the nurse or clinician queue and the coordinator flow stops. Otherwise an LLM may suggest a reason
code from the fixed taxonomy; below the confidence bar a person picks. Audio is deleted after transcription
unless a retention rule is set. Free text is never stored as a note: only the coded reason and a pointer.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from medora import audit, engine, graphs, llm, tripwire
from medora.config import load_yaml, setting
from medora.db import Conn, one, tx
from medora.events import NewEvent, append
from medora.hashing import sha256
from medora.ingest import _canonical, upload_dir
from medora.pii import Tokeniser

log = logging.getLogger("medora.callassist")
CONTACT_CODES = ["cost", "distance", "fear", "feeling_better", "wrong_number", "moved", "other"]
OUTCOMES = {"reached", "no_answer", "busy", "wrong_number", "callback"}


class CallError(ValueError):
    pass


def _known(conn: Conn, patient_id: str) -> dict[str, list[str]]:
    rows = conn.execute(
        """SELECT i.kind, i.value FROM patient_identifiers i JOIN patient_canonical c ON c.patient_id = i.patient_id
           WHERE c.canonical_id = (SELECT canonical_id FROM patient_canonical WHERE patient_id = %s)
             AND i.kind IN ('name', 'name_latin', 'phone', 'hospital_number')""", (patient_id,)).fetchall()
    out: dict[str, list[str]] = {"patient_name": [], "phone": [], "hospital_number": []}
    for r in rows:
        out["patient_name" if r["kind"] in ("name", "name_latin") else r["kind"]].append(r["value"])
    return out


BUNDLE_WINDOW_DAYS = 14


def bundle_hint(appointments: list[dict[str, str]], today: date) -> dict[str, Any] | None:
    """Visit bundling (COULD tier), from the patient's own booked appointments only.

    Two or more upcoming visits on different days within two weeks: suggest asking the desk to put them on one
    day. It only names dates the hospital already booked; it never picks a slot or a clinic.
    ponytail: one patient, plain grouping. OR-Tools only earns its place once lab, consult and pharmacy slot
    calendars are ingested and many patients compete for the same slots.
    """
    upcoming = sorted({(a["date"], a.get("department") or "Visit") for a in appointments
                       if a.get("date") and today <= date.fromisoformat(a["date"]) <= today + timedelta(days=BUNDLE_WINDOW_DAYS)})
    days = sorted({d for d, _ in upcoming})
    if len(days) < 2:
        return None
    visits = ", ".join(f"{dep} on {date.fromisoformat(d).strftime('%d %b')}" for d, dep in upcoming)
    return {"dates": days, "text": f"{len(days)} visits on different days: {visits}. Ask the scheduling desk if they "
                                   f"can be on one day to save trips.", "proposed": True}


def _fill(body: str, slots: dict[str, str]) -> str:
    for k, v in slots.items():
        body = body.replace("{" + k + "}", v)
    return body


def call_card(conn: Conn, hospital_id: str, flag_id: str, coordinator_name: str, hospital_name: str,
              language: str = "en") -> dict[str, Any]:
    f = conn.execute(
        """SELECT f.*, p.display_name, p.sex, p.birth_year, p.synthetic, o.due_by, o.from_step, o.expected_step,
                  x.rule_version, x.steps, v.spec
           FROM flags f JOIN patients p ON p.id = f.patient_id JOIN obligations o ON o.id = f.obligation_id
           JOIN flag_explanations x ON x.flag_id = f.id JOIN pathway_versions v ON v.id = f.pathway_version_id
           WHERE f.id = %s AND f.hospital_id = %s""", (flag_id, hospital_id)).fetchone()
    if not f:
        raise LookupError("flag not found")
    phones = conn.execute(
        """SELECT DISTINCT i.value FROM patient_identifiers i JOIN patient_canonical c ON c.patient_id = i.patient_id
           WHERE c.canonical_id = %s AND i.kind = 'phone'""", (f["patient_id"],)).fetchall()
    attempts = conn.execute(
        """SELECT a.id, a.attempted_at, a.by_user, o.outcome, o.reason_code, o.reason_confidence, o.reason_source,
                  o.routed_to_nurse
           FROM contact_attempts a LEFT JOIN contact_outcomes o ON o.attempt_id = a.id
           WHERE a.patient_id = %s AND a.hospital_id = %s ORDER BY a.attempted_at DESC LIMIT 10""",
        (f["patient_id"], hospital_id)).fetchall()
    last_reason = next((a["reason_code"] for a in attempts if a["reason_code"]), None)
    steps = {s["id"]: s["label"] for s in f["spec"]["steps"]}
    key = {"overdue": "overdue_booking", "missed": "missed_visit", "unreachable": "unreachable_retry"}[f["kind"]]
    templates = load_yaml("call_templates.yaml")["templates"]
    tpl = next((t for t in templates if t["key"] == key and t["language"] == language), None) or next(
        t for t in templates if t["key"] == key and t["language"] == "en")
    signed = conn.execute(
        "SELECT signed_by FROM call_templates WHERE hospital_id = %s AND key = %s AND version = %s AND language = %s",
        (hospital_id, tpl["key"], tpl["version"], tpl["language"])).fetchone()
    slots = {"patient_name": f["display_name"], "coordinator_name": coordinator_name, "hospital_name": hospital_name,
             "step_label": steps.get(f["expected_step"], f["expected_step"]),
             "days": str(f["rank_inputs"]["days_overdue"]), "last_date": f["due_by"].date().isoformat()}
    playbook = load_yaml("playbooks.yaml")["by_reason"].get(last_reason) if last_reason else None
    booked = conn.execute(
        """SELECT payload->>'appointment_date' AS date, payload->>'department' AS department FROM live_events
           WHERE canonical_id = %s AND type = 'appointment_booked' AND payload ? 'appointment_date'""",
        (f["patient_id"],)).fetchall()
    return {
        "flag_id": flag_id, "patient_id": str(f["patient_id"]), "synthetic": f["synthetic"],
        "who": {"name": f["display_name"], "sex": f["sex"], "birth_year": f["birth_year"],
                "phones": [p["value"] for p in phones]},
        "why": {"kind": f["kind"], "reason_line": f["reason_line"], "rule_version": f["rule_version"],
                "due_by": f["due_by"].isoformat(), "steps": f["steps"]["lines"]},
        "attempts": [{**a, "id": str(a["id"])} for a in attempts],
        "script": {"key": tpl["key"], "version": tpl["version"], "language": tpl["language"],
                   "text": _fill(tpl["body"], slots), "approved": bool(signed and signed["signed_by"])},
        "playbook": {"reason": last_reason, "text": playbook, "proposed": True} if playbook else None,
        "bundle": bundle_hint(booked, datetime.now(UTC).date()),
    }


def record_attempt(conn: Conn, hospital_id: str, flag_id: str, actor: str) -> str:
    f = one(conn, "SELECT patient_id FROM flags WHERE id = %s AND hospital_id = %s", (flag_id, hospital_id))
    a = one(conn, "INSERT INTO contact_attempts (hospital_id, patient_id, flag_id, by_user) VALUES (%s,%s,%s,%s) RETURNING *",
            (hospital_id, f["patient_id"], flag_id, actor))
    append(conn, NewEvent(hospital_id=hospital_id, type="contact_attempted", occurred_at=a["attempted_at"],
                          source_ref={"kind": "contact_attempt", "attempt": str(a["id"])}, confidence=1.0, actor=actor,
                          patient_id=str(f["patient_id"]), dedupe_key=f"attempt:{a['id']}"))
    audit.append(conn, hospital_id, actor, "call.attempt", "contact_attempt", a["id"], {"flag_id": flag_id})
    return str(a["id"])


def _store_audio_if_retained(audio: bytes, filename: str) -> str | None:
    hours = int(setting("callassist.audio_retention_hours"))
    if hours <= 0:
        return None  # default: audio exists only in memory for the transcription call
    d = upload_dir() / "audio"
    d.mkdir(exist_ok=True)
    p = d / f"{sha256(audio)[:16]}{Path(filename).suffix}"
    p.write_bytes(audio)
    return str(p)


def purge_expired_audio() -> int:
    hours = int(setting("callassist.audio_retention_hours"))
    d = upload_dir() / "audio"
    if not d.exists():
        return 0
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    n = 0
    for p in d.iterdir():
        if datetime.fromtimestamp(p.stat().st_mtime, UTC) < cutoff:
            p.unlink()
            n += 1
    return n


def record_outcome(hospital_id: str, attempt_id: str, outcome: str, source: str, actor: str,
                   reason_code: str | None = None, note: str | None = None, audio: bytes | None = None,
                   audio_name: str = "memo.webm", language: str | None = None) -> dict[str, Any]:
    if outcome not in OUTCOMES:
        raise CallError("unknown outcome")
    if source not in ("tap", "note", "voice"):
        raise CallError("unknown source")
    with tx() as conn:
        att = one(conn, "SELECT * FROM contact_attempts WHERE id = %s AND hospital_id = %s", (attempt_id, hospital_id))
        known = _known(conn, str(att["patient_id"]))
    text: str | None = note
    asr_meta: dict[str, Any] | None = None
    if source == "voice":
        if not audio:
            raise CallError("voice memo is empty")
        _store_audio_if_retained(audio, audio_name)
        try:
            text, asr_meta = llm.transcribe(audio, audio_name, language)
        except llm.LLMUnavailable as e:
            text = None
            log.info("asr unavailable, coordinator picks the reason", extra={"error": str(e)})
        audio = None  # drop the bytes now; nothing below keeps them

    trip = tripwire.check(text) if text else None
    suggestion: dict[str, Any] | None = None
    if trip is None or not trip.routed:
        if source == "tap":
            if reason_code is not None and reason_code not in CONTACT_CODES:
                raise CallError("reason must come from the fixed list")
        elif text:
            tok = Tokeniser()
            try:
                out, meta = llm.call("reason_code_v1", {"text_tokenised": tok.tokenise(text, known),
                                                        "allowed_codes": CONTACT_CODES}, known)
                suggestion = {**out, "prompt_version": meta["prompt_version"], "replay": meta["replay"]}
            except (llm.LLMUnavailable, llm.PayloadRejected) as e:
                suggestion = {"error": str(e)}
    min_conf = float(setting("callassist.reason_min_confidence"))
    with tx() as conn:
        routed = bool(trip and trip.routed)
        code, conf = (reason_code, 1.0) if source == "tap" else (None, None)
        if suggestion and "reason_code" in suggestion and suggestion["confidence"] >= min_conf and not routed:
            code, conf = suggestion["reason_code"], float(suggestion["confidence"])
        pointer = sha256(text)[:16] if text else None
        oc = one(conn, """INSERT INTO contact_outcomes (hospital_id, attempt_id, outcome, reason_code, reason_confidence,
                                                         reason_source, transcript_ref, routed_to_nurse, decided_by)
                          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                 (hospital_id, attempt_id, outcome, code, conf, source, pointer, routed,
                  actor if source == "tap" else ("llm_suggestion" if code else actor)))
        pid = str(att["patient_id"])
        append(conn, NewEvent(hospital_id=hospital_id, type="contact_outcome_recorded", occurred_at=oc["created_at"],
                              source_ref={"kind": "contact_outcome", "outcome": str(oc["id"])}, confidence=conf or 1.0,
                              actor=actor, patient_id=pid,
                              payload={"outcome": outcome, **({"reason_code": code} if code else {})},
                              dedupe_key=f"outcome:{oc['id']}"))
        result: dict[str, Any] = {"outcome_id": str(oc["id"]), "reason_code": code, "confidence": conf,
                                  "routed": routed, "needs_reason": False, "asr": asr_meta, "suggestion": suggestion}
        if routed and trip and text:
            ni = one(conn, """INSERT INTO nurse_items (hospital_id, patient_id, source, route, excerpt, matched, created_by)
                              VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                     (hospital_id, pid, "transcript" if source == "voice" else "note", trip.route, text[:2000],
                      Jsonb(trip.as_dict()), actor))
            audit.append(conn, hospital_id, "tripwire", "tripwire.route", "nurse_item", ni["id"],
                         {"route": trip.route, "categories": trip.categories})
            result.update({"nurse_item_id": str(ni["id"]), "route": trip.route, "refusal": trip.refusal})
        elif source != "tap" and code is None:
            item = one(conn, """INSERT INTO review_items (hospital_id, type, payload, confidence, dedupe_key, due_at)
                                VALUES (%s,'reason',%s,%s,%s, now() + make_interval(hours => %s)) RETURNING id""",
                       (hospital_id, Jsonb({"outcome_id": str(oc["id"]), "text": text, "suggestion": suggestion,
                                            "allowed_codes": CONTACT_CODES}),
                        (suggestion or {}).get("confidence"), f"reason:{oc['id']}",
                        int(setting("review.escalate_after_hours"))))
            result.update({"needs_reason": True, "review_item_id": str(item["id"])})
        audit.append(conn, hospital_id, actor, "call.outcome", "contact_outcome", oc["id"],
                     {"outcome": outcome, "source": source, "reason_code": code, "routed": routed})
        engine.evaluate_active(conn, hospital_id, patients=_canonical(conn, [pid]), actor=actor)
    if result["needs_reason"]:
        graphs.start("reason", hospital_id, result["review_item_id"], {"outcome_id": result["outcome_id"]})
    return result


def _set_reason(conn: Conn, hospital_id: str, outcome_id: str, code: str, actor: str, via: str) -> None:
    if code not in CONTACT_CODES:
        raise CallError("reason must come from the fixed list")
    oc = conn.execute("""UPDATE contact_outcomes SET reason_code = %s, reason_confidence = 1.0, decided_by = %s
                         WHERE id = %s AND hospital_id = %s RETURNING *""",
                      (code, actor, outcome_id, hospital_id)).fetchone()
    if not oc:
        raise LookupError("outcome not found")
    ev = one(conn, "SELECT id FROM events WHERE hospital_id = %s AND dedupe_key = %s", (hospital_id, f"outcome:{outcome_id}"))
    append(conn, NewEvent(hospital_id=hospital_id, type="correction", occurred_at=datetime.now(UTC),
                          source_ref={"kind": "human_correction", "by": actor}, confidence=1.0, actor=actor,
                          supersedes_id=str(ev["id"]), payload={"corrected_field": "reason_code", "corrected_value": code}))
    audit.append(conn, hospital_id, actor, f"call.reason_{via}", "contact_outcome", outcome_id, {"reason_code": code})


@graphs.register("reason")
def _apply_reason(hospital_id: str, item_id: str, proposal: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    with tx() as conn:
        item = conn.execute("SELECT * FROM review_items WHERE id = %s AND hospital_id = %s FOR UPDATE",
                            (item_id, hospital_id)).fetchone()
        if not item or item["state"] == "decided":
            raise CallError("reason review not open")
        _set_reason(conn, hospital_id, proposal["outcome_id"], decision["reason_code"], decision["actor"], "confirm")
        # Drop the free text now that a coded reason exists (Rules 2.9).
        conn.execute("""UPDATE review_items SET state = 'decided', decided_by = %s, decision = %s, decided_at = now(),
                               payload = payload - 'text' WHERE id = %s""",
                     (decision["actor"], Jsonb({"reason_code": decision["reason_code"]}), item_id))
    return {"reason_code": decision["reason_code"]}


def confirm_reason(hospital_id: str, item_id: str, code: str, actor: str) -> dict[str, Any]:
    with tx() as conn:
        item = one(conn, "SELECT payload FROM review_items WHERE id = %s AND hospital_id = %s", (item_id, hospital_id))
    return graphs.decide("reason", hospital_id, item_id, {"outcome_id": item["payload"]["outcome_id"]},
                         {"reason_code": code, "actor": actor})


def override_reason(conn: Conn, hospital_id: str, outcome_id: str, code: str, actor: str) -> None:
    """Human override on an AI-suggested reason, any time (Rules 1.3)."""
    _set_reason(conn, hospital_id, outcome_id, code, actor, "override")


def close_obligation(conn: Conn, hospital_id: str, obligation_id: str, actor: str, reason_code: str | None = None,
                     evidence_event_id: str | None = None) -> None:
    """F10: done only with linked evidence or a coded closure reason. Never a bare tick-box."""
    ob = conn.execute("SELECT o.*, v.spec FROM obligations o JOIN pathway_versions v ON v.id = o.pathway_version_id "
                      "WHERE o.id = %s AND o.hospital_id = %s FOR UPDATE", (obligation_id, hospital_id)).fetchone()
    if not ob:
        raise LookupError("obligation not found")
    if ob["state"] != "open":
        raise CallError("obligation is already closed")
    if evidence_event_id:
        expected = next(s["event_type"] for s in ob["spec"]["steps"] if s["id"] == ob["expected_step"])
        ev = conn.execute(
            """SELECT e.id FROM live_events e JOIN live_events f ON f.id = %s
               WHERE e.id = %s AND e.hospital_id = %s AND e.canonical_id = f.canonical_id AND e.type = %s
                 AND e.effective_at >= f.effective_at""",
            (ob["from_event_id"], evidence_event_id, hospital_id, expected)).fetchone()
        if not ev:
            raise CallError(f"evidence must be a later {expected} event for the same patient")
        conn.execute("""UPDATE obligations SET state = 'closed_evidence', closed_by_event = %s, closed_by_user = %s,
                        closed_at = now() WHERE id = %s""", (evidence_event_id, actor, obligation_id))
    elif reason_code:
        rc = conn.execute("SELECT 1 FROM reason_codes WHERE code = %s AND category = 'closure'", (reason_code,)).fetchone()
        if not rc:
            raise CallError("closure reason must come from the coded list")
        conn.execute("""UPDATE obligations SET state = 'closed_reason', closure_reason_code = %s, closed_by_user = %s,
                        closed_at = now() WHERE id = %s""", (reason_code, actor, obligation_id))
    else:
        raise CallError("link evidence or choose a coded closure reason")
    conn.execute("UPDATE flags SET state = 'resolved', resolved_at = now() WHERE obligation_id = %s AND state = 'open'",
                 (obligation_id,))
    audit.append(conn, hospital_id, actor, "obligation.close", "obligation", obligation_id,
                 {"reason_code": reason_code, "evidence_event_id": evidence_event_id})
