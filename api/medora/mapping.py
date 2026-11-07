"""Compile-once column mapping (F3, S5).

A new file shape gets one LLM proposal from headers plus shape-only samples. A person confirms it on the
Mapping Confirm screen. Files with the same header fingerprint reuse the confirmed mapping with zero LLM calls.
If the LLM is unavailable, rule-based suggestions are shown instead and a person completes the mapping.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import jsonschema
from psycopg.types.json import Jsonb

from medora import audit, llm, whitelist
from medora.config import setting
from medora.dates import ParsedDate, parse
from medora.db import Conn, one
from medora.hashing import sha256
from medora.pii import signature


def norm_header(h: Any) -> str:
    return re.sub(r"\s+", " ", str(h or "").strip().lower())


def fingerprint(headers: list[Any]) -> str:
    return sha256("|".join(norm_header(h) for h in headers))


# Rule-based fallback. Shown as "suggested by rules", never applied without a person confirming.
_HEADER_RULES: list[tuple[str, str]] = [
    (r"mobile|phone|contact|cell|फोन|मोबाइल", "phone"),
    (r"\bmrn\b|uhid|hosp.*(no|num|id)|reg.*(no|num)|patient.*id|cr no|ipd|opd no", "hospital_number"),
    (r"name|नाम", "patient_name"),
    (r"\bsex\b|gender|लिंग", "sex"),
    (r"\bage\b|आयु|उम्र", "age"),
    (r"birth|dob|yob", "birth_year"),
    (r"appt|appointment|slot|scheduled for|next visit", "appointment_date"),
    (r"date|dt\b|on\b|तारीख|दिनांक", "event_date"),
    (r"dept|department|clinic|unit|ward|विभाग", "department"),
    (r"status|attend|outcome|dna", "status"),
    (r"event|visit type|activity|action|decision|type", "event_type"),
]

_LABEL_RULES: list[tuple[str, str]] = [
    (r"tumou?r board|mdt|\btb\b|board decision", "tb_decision_recorded"),
    (r"surg|operat|ot done", "surgery_recorded"),
    (r"no answer|not picked|switched off|not reachable|unreachable|wrong n(o|umber)|busy", "contact_attempted"),
    (r"\bspoke|talked to", "contact_outcome_recorded"),
    (r"\bdna\b|did not (attend|come)|missed|no.?show|absent", "appointment_missed"),
    (r"cancel", "appointment_cancelled"),
    (r"attend|\batt\b|seen|visited|present|done|completed", "appointment_attended"),
    (r"book|sched|appoint|\bappt given|slot|(given|new) date|date given|registered", "appointment_booked"),
]


def suggest_field(header: str) -> str:
    h = norm_header(header)
    for pat, target in _HEADER_RULES:
        if re.search(pat, h):
            return target
    return "ignore"


def suggest_label(label: str) -> str | None:
    lab = str(label).strip().lower()
    for pat, target in _LABEL_RULES:
        if re.search(pat, lab):
            return target
    return None


MAPPING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["columns", "event_type_values"],
    "additionalProperties": False,
    "properties": {
        "columns": {"type": "object", "additionalProperties": {"type": "string"}},
        "event_type_values": {"type": "object", "additionalProperties": {"type": ["string", "null"]}},
        "status_values": {"type": "object", "additionalProperties": {"type": ["string", "null"]}},
        "default_event_type": {"type": ["string", "null"]},
        "date_convention": {"enum": ["dmy", "mdy", "ymd", None]},
    },
}


class MappingInvalid(ValueError):
    pass


def validate(mapping: dict[str, Any], headers: list[str]) -> None:
    try:
        jsonschema.validate(mapping, MAPPING_SCHEMA)
    except jsonschema.ValidationError as e:
        raise MappingInvalid(e.message) from e
    fields = whitelist.canonical_fields()
    types = whitelist.event_types()
    used: dict[str, str] = {}
    for header, target in mapping["columns"].items():
        if header not in headers:
            raise MappingInvalid(f"unknown header {header!r}")
        if target not in fields:
            raise MappingInvalid(f"{header!r} maps to non-whitelisted field {target!r}")
        if target != "ignore":
            if target in used:
                raise MappingInvalid(f"{target} is mapped twice ({used[target]!r}, {header!r})")
            used[target] = header
    for values in (mapping["event_type_values"], mapping.get("status_values") or {}):
        for label, t in values.items():
            if t is not None and t not in types:
                raise MappingInvalid(f"label {label!r} maps to unknown event type {t!r}")
    if mapping.get("default_event_type") and mapping["default_event_type"] not in types:
        raise MappingInvalid("default_event_type is not a whitelisted event type")
    if "event_date" not in used:
        raise MappingInvalid("a column must map to event_date")
    if not ({"event_type", "status"} & set(used)) and not mapping.get("default_event_type"):
        raise MappingInvalid("map an event_type or status column, or set a default event type")
    if not ({"patient_name", "phone", "hospital_number"} & set(used)):
        raise MappingInvalid("at least one identifier column (name, phone or hospital number) is required")


def propose(headers: list[str], sample_rows: list[list[Any]], profile: dict[str, Any]) -> dict[str, Any]:
    """Returns {mapping, proposed_by, confidences, llm_calls, prompt_version, error}. Never raises for LLM trouble."""
    n = int(setting("mapping.sample_rows"))
    shapes = [[signature(v) for v in row] for row in sample_rows[:n]]
    targets = sorted(whitelist.canonical_fields())
    result: dict[str, Any] = {"llm_calls": 0, "prompt_version": None, "error": None, "confidences": {}}
    columns: dict[str, str] = {}
    try:
        out, meta = llm.call("mapping_v1", {"headers": headers, "sample_rows": shapes, "target_fields": targets})
        result["llm_calls"] = 0 if meta["replay"] else 1
        result["replay"] = meta["replay"]
        result["prompt_version"] = meta["prompt_version"]
        seen: set[str] = set()
        for c in out["columns"]:
            if c["header"] in headers and c["field"] in targets and (c["field"] == "ignore" or c["field"] not in seen):
                columns[c["header"]] = c["field"]
                result["confidences"][c["header"]] = c["confidence"]
                seen.add(c["field"])
        result["proposed_by"] = "llm"
        guess = out["date_convention_guess"]
        result["date_convention_guess"] = None if guess == "unknown" else guess
    except (llm.LLMUnavailable, llm.PayloadRejected) as e:
        result["error"] = str(e)
        result["proposed_by"] = "rules"
    seen = set(columns.values()) - {"ignore"}
    for h in headers:  # rules fill anything the LLM skipped; rules never override the LLM
        if h not in columns:
            f = suggest_field(h)
            columns[h] = "ignore" if f in seen else f
            seen.add(columns[h])
            result["confidences"].setdefault(h, None)
    labels: dict[str, dict[str, str | None]] = {}
    for h, f in columns.items():
        if f in ("event_type", "status"):
            for lab in profile.get("columns", {}).get(h, {}).get("labels", []):
                labels.setdefault(f, {})[lab] = suggest_label(lab)
    result["mapping"] = {
        "columns": columns,
        "event_type_values": labels.get("event_type", {}),
        "status_values": labels.get("status", {}),
        "default_event_type": None,
        "date_convention": result.get("date_convention_guess") or profile.get("date_convention_hint"),
    }
    return result


def find_confirmed(conn: Conn, hospital_id: str, fp: str) -> dict[str, Any] | None:
    return conn.execute(
        """SELECT * FROM mappings WHERE hospital_id = %s AND fingerprint = %s AND confirmed_by IS NOT NULL
           ORDER BY version DESC LIMIT 1""", (hospital_id, fp)).fetchone()


def save_confirmed(conn: Conn, hospital_id: str, fp: str, headers: list[str], mapping: dict[str, Any],
                   proposed_by: str, prompt_version: str | None, actor: str,
                   llm_confidence: float | None = None) -> dict[str, Any]:
    validate(mapping, headers)
    row = one(conn, 
        """INSERT INTO mappings (hospital_id, fingerprint, version, headers, mapping, proposed_by, prompt_version,
                                 llm_confidence, date_convention, confirmed_by, confirmed_at)
           VALUES (%s, %s, COALESCE((SELECT max(version) FROM mappings WHERE hospital_id = %s AND fingerprint = %s), 0) + 1,
                   %s, %s, %s, %s, %s, %s, %s, now())
           RETURNING *""",
        (hospital_id, fp, hospital_id, fp, Jsonb(headers), Jsonb(mapping),
         "llm" if proposed_by == "llm" else "human", prompt_version, llm_confidence,
         mapping.get("date_convention"), actor),
    )
    audit.append(conn, hospital_id, actor, "mapping.confirm", "mapping", row["id"],
                 {"fingerprint": fp, "version": row["version"], "proposed_by": proposed_by})
    return row


@dataclass
class Applied:
    fields: dict[str, Any]          # canonical field -> raw value
    event_type: str | None
    occurred: ParsedDate
    appointment: ParsedDate | None
    problems: list[str]
    cells: dict[str, str]           # canonical field -> source header (provenance)


def apply_row(mapping: dict[str, Any], row: dict[str, Any]) -> Applied:
    """Pure: one source row -> canonical fields. Unknown labels and bad dates become problems, not drops."""
    fields: dict[str, Any] = {}
    cells: dict[str, str] = {}
    for header, target in mapping["columns"].items():
        if target == "ignore":
            continue
        fields[target] = row.get(header)
        cells[target] = header
    problems: list[str] = []
    et: str | None = None
    status_raw = fields.get("status")
    if status_raw not in (None, "") and mapping.get("status_values"):
        et = mapping["status_values"].get(str(status_raw).strip())
    if et is None and fields.get("event_type") not in (None, ""):
        label = str(fields["event_type"]).strip()
        et = mapping["event_type_values"].get(label)
        if et is None:
            problems.append(f"unknown event label {label!r}")
    if et is None and not problems:
        et = mapping.get("default_event_type")
    if et is None and not problems:
        problems.append("no event type")
    conv = mapping.get("date_convention")
    occurred = parse(fields.get("event_date"), conv)
    if not occurred.ok:
        problems.append(f"event date: {occurred.reason}")
    appt = None
    if fields.get("appointment_date") not in (None, ""):
        appt = parse(fields.get("appointment_date"), conv)
        if not appt.ok:
            problems.append(f"appointment date: {appt.reason}")
    if not any(fields.get(k) not in (None, "") for k in ("patient_name", "phone", "hospital_number")):
        problems.append("no identifier")
    return Applied(fields, et, occurred, appt, problems, cells)
