"""Pathway-as-code (F9, S3). YAML -> validated spec -> compiled SQL gap checks -> immutable version.

Activation requires a clinician sign-off record. Claude never signs: scripts/sign_pathway.py is run by a person.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema
import yaml
from psycopg.types.json import Jsonb

from medora import audit, whitelist
from medora.config import ROOT
from medora.db import Conn, one
from medora.hashing import sha256
from medora.rules import Gap, gaps_from_spec

PATHWAY_DIR = ROOT / "pathways"


class PathwayError(ValueError):
    pass


@lru_cache
def _schema() -> dict[str, Any]:
    return json.loads((PATHWAY_DIR / "schema.json").read_text(encoding="utf-8"))


def parse(text: str) -> dict[str, Any]:
    spec = yaml.safe_load(text)
    try:
        jsonschema.validate(spec, _schema())
    except jsonschema.ValidationError as e:
        raise PathwayError(f"pathway schema: {e.message}") from e
    ids = [s["id"] for s in spec["steps"]]
    if len(ids) != len(set(ids)):
        raise PathwayError("duplicate step ids")
    for s in spec["steps"]:
        if s["event_type"] not in whitelist.event_types():
            raise PathwayError(f"step {s['id']}: event type {s['event_type']} is not whitelisted")
        if "max_gap_days_from" in s and s["max_gap_days_from"] not in ids:
            raise PathwayError(f"step {s['id']}: unknown max_gap_days_from {s['max_gap_days_from']}")
    for o in spec.get("obligations", []):
        if o["when"] not in ids or o["expects"] not in ids:
            raise PathwayError(f"obligation {o} references an unknown step")
        if not any(g.from_step == o["when"] and g.expected_step == o["expects"] for g in gaps_from_spec(spec)):
            raise PathwayError(f"obligation {o['when']} -> {o['expects']} has no matching step gap")
    if not gaps_from_spec(spec):
        raise PathwayError("pathway has no handovers (no step with max_gap_days_from)")
    return spec


def load_file(path: Path) -> tuple[str, dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    return text, parse(text)


def _gap_sql(g: Gap) -> str:
    # Values are schema-validated (identifier patterns, integers, whitelisted types), so inlining is safe.
    return f"""  SELECT '{g.from_step}'::text AS from_step, '{g.expected_step}'::text AS expected_step,
         f.id AS from_event_id, f.canonical_id AS patient_id, f.effective_at AS from_at,
         f.effective_at + make_interval(days => {g.max_gap_days}) AS due_by,
         f.effective_at + make_interval(days => {g.flag_after_days}) AS flag_after,
         (SELECT t.id FROM live_events t
           WHERE t.hospital_id = f.hospital_id AND t.canonical_id = f.canonical_id
             AND t.type = '{g.expected_type}' AND t.id <> f.id
             AND t.effective_at >= f.effective_at AND t.effective_at <= %(as_of)s
           ORDER BY t.effective_at, t.id LIMIT 1) AS evidence_event_id
  FROM live_events f
  WHERE f.hospital_id = %(hospital_id)s AND f.type = '{g.from_type}' AND f.effective_at <= %(as_of)s
    AND (%(patients)s::uuid[] IS NULL OR f.canonical_id = ANY(%(patients)s::uuid[]))"""


def compile_sql(spec: dict[str, Any]) -> str:
    header = f"-- compiled from {spec['pathway']} v{spec['version']}. Do not edit; recompile from YAML.\n"
    body = "\nUNION ALL\n".join(_gap_sql(g) for g in gaps_from_spec(spec))
    return header + "SELECT * FROM (\n" + body + "\n) gaps ORDER BY patient_id, from_at, from_event_id, expected_step"


def register(conn: Conn, hospital_id: str, text: str, actor: str) -> dict[str, Any]:
    """Store a new immutable version. Same content returns the existing row. Never signs or activates."""
    spec = parse(text)
    content_hash = sha256(text)
    pw = one(conn, 
        """INSERT INTO pathways (hospital_id, key, name) VALUES (%s, %s, %s)
           ON CONFLICT (hospital_id, key) DO UPDATE SET name = EXCLUDED.name RETURNING id""",
        (hospital_id, spec["pathway"], spec["name"]),
    )
    existing = conn.execute(
        "SELECT * FROM pathway_versions WHERE pathway_id = %s AND version = %s", (pw["id"], spec["version"])
    ).fetchone()
    if existing:
        if existing["content_hash"] != content_hash:
            raise PathwayError(f"version {spec['version']} already exists with different content; bump the version")
        return existing
    row = one(conn, 
        """INSERT INTO pathway_versions (hospital_id, pathway_id, version, yaml, spec, compiled_sql, content_hash, demo)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
        (hospital_id, pw["id"], spec["version"], text, Jsonb(spec), compile_sql(spec), content_hash,
         bool(spec.get("demo"))),
    )
    audit.append(conn, hospital_id, actor, "pathway.register", "pathway_version", row["id"],
                 {"pathway": spec["pathway"], "version": spec["version"], "content_hash": content_hash})
    return row


def sign(conn: Conn, hospital_id: str, version_id: str, signer_name: str, signer_role: str) -> None:
    """Record a clinician sign-off. Only a person with the clinical_lead role may sign."""
    if signer_role != "clinical_lead":
        raise PathwayError("only a clinical lead can sign a pathway version")
    if not signer_name.strip():
        raise PathwayError("signer name required")
    cur = conn.execute(
        """UPDATE pathway_versions SET signed_by = %s, signed_role = %s, signed_at = %s
           WHERE id = %s AND hospital_id = %s AND signed_by IS NULL""",
        (signer_name.strip(), signer_role, datetime.now(UTC), version_id, hospital_id),
    )
    if cur.rowcount != 1:
        raise PathwayError("version not found or already signed")
    audit.append(conn, hospital_id, signer_name, "pathway.sign", "pathway_version", version_id, {"role": signer_role})


def activate(conn: Conn, hospital_id: str, version_id: str, actor: str) -> None:
    v = conn.execute("SELECT * FROM pathway_versions WHERE id = %s AND hospital_id = %s",
                     (version_id, hospital_id)).fetchone()
    if not v:
        raise PathwayError("version not found")
    if not v["signed_by"]:
        raise PathwayError("cannot activate an unsigned pathway version")
    conn.execute("UPDATE pathway_versions SET active = false WHERE pathway_id = %s AND active", (v["pathway_id"],))
    conn.execute("UPDATE pathway_versions SET active = true WHERE id = %s", (version_id,))
    audit.append(conn, hospital_id, actor, "pathway.activate", "pathway_version", version_id,
                 {"version": v["version"]})


def rule_version(v: dict[str, Any]) -> str:
    return f"{v['spec']['pathway']} v{v['version']} ({v['content_hash'][:8]})"
