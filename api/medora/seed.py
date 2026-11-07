"""Seed a synthetic tenant: hospital, users, pathway versions (unsigned), call templates (proposed).

Never signs a pathway. A person with the clinical_lead role signs in the Pathway Viewer or with
scripts/sign_pathway.py.
"""
from __future__ import annotations

from typing import Any

from medora import audit, pathways
from medora.auth import hash_password
from medora.config import ROOT, env, load_yaml
from medora.db import Conn, one

USERS = [
    ("meera@medora.test", "Meera (Care Coordinator)", "coordinator"),
    ("lead@medora.test", "Clinical Lead (synthetic account)", "clinical_lead"),
    ("nurse@medora.test", "Nurse Anjali (synthetic)", "nurse"),
    ("admin@medora.test", "Hospital Admin (synthetic)", "admin"),
    ("steward@medora.test", "Data Steward (synthetic)", "data_steward"),
]


def create_hospital(conn: Conn, name: str = "Kronex Demo Hospital (synthetic)", password: str | None = None,
                    with_users: bool = True) -> str:
    """with_users=False for internal tenants (benchmarks): nobody should ever sign in to them."""
    h = one(conn, "INSERT INTO hospitals (name, synthetic) VALUES (%s, true) RETURNING id", (name,))
    hid = str(h["id"])
    pw = hash_password(password or env("SEED_PASSWORD", "medora-demo"))
    for email, display, role in USERS if with_users else []:
        conn.execute("INSERT INTO users (hospital_id, email, display_name, role, password_hash) VALUES (%s,%s,%s,%s,%s)",
                     (hid, email, display, role, pw))
    audit.append(conn, hid, "seed", "tenant.create", "hospital", hid, {"name": name, "synthetic": True})
    for t in load_yaml("call_templates.yaml")["templates"]:
        slots = sorted({s.split("}")[0] for s in t["body"].split("{")[1:]})
        conn.execute("""INSERT INTO call_templates (hospital_id, key, version, language, body, slots, proposed)
                        VALUES (%s,%s,%s,%s,%s,%s,true) ON CONFLICT DO NOTHING""",
                     (hid, t["key"], t["version"], t["language"], t["body"], slots))
    return hid


def register_pathways(conn: Conn, hospital_id: str, names: tuple[str, ...] = ("gi_cancer_handover.v1",)) -> dict[str, Any]:
    out = {}
    for n in names:
        text = (ROOT / "pathways" / f"{n}.yaml").read_text(encoding="utf-8")
        out[n] = pathways.register(conn, hospital_id, text, "seed")
    return out
