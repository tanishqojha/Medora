"""API end to end through FastAPI: roles, tenancy, call-assist (F10, F13, F14), Trust (F16)."""
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from medora import pathways, seed, synth
from medora.db import tx

pytestmark = pytest.mark.db
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client(pg):
    from medora.app import app
    return TestClient(app)


def login(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": "medora-demo"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def tenant(hospital, tmp_path):
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from _lib import REGISTER_MAPPING, drain, plan, preconfirm, upload

    ds = synth.build(tmp_path / "ds", n_patients=60, seed=3, as_of=date.today(), photos=0)
    with tx() as conn:
        v = seed.register_pathways(conn, hospital, ("gi_cancer_handover.v1", "breast_handover_demo.v1"))
        gi = v["gi_cancer_handover.v1"]
        pathways.sign(conn, hospital, gi["id"], "Test Lead (synthetic)", "clinical_lead")
        pathways.activate(conn, hospital, gi["id"], "Test Lead (synthetic)")
    preconfirm(hospital, synth.HEADERS, REGISTER_MAPPING, "steward")
    for k in ("register_csv", "register_xlsx"):
        plan(upload(hospital, Path(ds.files[k]), "steward")["id"])
    drain()
    return hospital


def test_roles_and_auth(client, tenant):
    assert client.get("/api/stuck").status_code == 401
    nurse = login(client, "nurse@medora.test")
    assert client.get("/api/stuck", headers=nurse).status_code == 403
    assert client.get("/api/nurse", headers=nurse).status_code == 200
    coord = login(client, "meera@medora.test")
    assert client.post("/api/pathways/00000000-0000-0000-0000-000000000000/sign", headers=coord).status_code == 403
    assert client.post("/api/auth/login", json={"email": "meera@medora.test", "password": "nope"}).status_code == 401


def test_stuck_list_ranked_with_reasons_and_replay(client, tenant):
    h = login(client, "meera@medora.test")
    body = client.get("/api/stuck", headers=h).json()
    items = body["items"]
    assert items and [i["rank"] for i in items] == list(range(1, len(items) + 1))
    assert all(i["reason_line"] for i in items)
    f = client.get(f"/api/flags/{items[0]['id']}", headers=h).json()
    assert f["rule_version"].startswith("gi_cancer_handover v1") and f["sources"]
    assert client.get(f"/api/flags/{items[0]['id']}/replay", headers=h).json()["match"] is True
    src = f["sources"][0]["source_ref"]
    row = client.get(f"/api/sources/{src['file']}/rows/{src['row']}", headers=h).json()
    assert row["row"] == src["row"] and row["synthetic"] is True


def test_call_flow_tap_symptom_and_reason_review(client, tenant):
    h = login(client, "meera@medora.test")
    flag = client.get("/api/stuck", headers=h).json()["items"][0]
    card = client.get(f"/api/flags/{flag['id']}/call-card", headers=h).json()
    assert card["script"]["approved"] is False and "{" not in card["script"]["text"]
    assert card["who"]["phones"]

    att = client.post(f"/api/flags/{flag['id']}/attempts", headers=h).json()["attempt_id"]
    r = client.post(f"/api/attempts/{att}/outcome", headers=h,
                    data={"outcome": "reached", "source": "tap", "reason_code": "cost"}).json()
    assert r["reason_code"] == "cost" and not r["routed"]

    # Symptom language in a note goes to the nurse queue, never the coordinator flow.
    att2 = client.post(f"/api/flags/{flag['id']}/attempts", headers=h).json()["attempt_id"]
    r2 = client.post(f"/api/attempts/{att2}/outcome", headers=h,
                     data={"outcome": "reached", "source": "note", "note": "she has fever and pain since monday"}).json()
    assert r2["routed"] and r2["route"] == "nurse" and r2["reason_code"] is None
    nurse = login(client, "nurse@medora.test")
    assert any(n["id"] == r2["nurse_item_id"] for n in client.get("/api/nurse", headers=nurse).json())

    # A plain note with no LLM configured fails closed: a person picks the reason through the gate.
    att3 = client.post(f"/api/flags/{flag['id']}/attempts", headers=h).json()["attempt_id"]
    r3 = client.post(f"/api/attempts/{att3}/outcome", headers=h,
                     data={"outcome": "reached", "source": "note", "note": "bus fare is too high"}).json()
    assert r3["needs_reason"] and r3["reason_code"] is None
    done = client.post(f"/api/review/{r3['review_item_id']}/reason", headers=h, json={"reason_code": "cost"}).json()
    assert done["reason_code"] == "cost"
    item = client.get("/api/review?state=decided&type=reason", headers=h).json()["items"][0]
    assert "text" not in item["payload"], "free text is dropped once a coded reason exists"


def test_obligation_close_needs_evidence_or_code(client, tenant):
    h = login(client, "meera@medora.test")
    flag = client.get("/api/stuck", headers=h).json()["items"][0]
    url = f"/api/obligations/{flag['obligation_id']}/close"
    assert client.post(url, headers=h, json={}).status_code == 400
    assert client.post(url, headers=h, json={"reason_code": "cost"}).status_code == 400  # contact code, not closure
    assert client.post(url, headers=h, json={"reason_code": "treated_elsewhere"}).status_code == 200


def test_refusal_preview_and_trust(client, tenant):
    h = login(client, "meera@medora.test")
    r = client.post("/api/assist/message", headers=h, json={"text": "What treatment is best for colon cancer?"}).json()
    assert r["routed"] and r["reply"] is None and "can't give medical advice" in r["refusal"]
    pw = client.get("/api/pathways", headers=h).json()
    demo = next(p for p in pw if p["key"] == "breast_handover_demo")
    assert demo["signed_by"] is None and not demo["active"]
    prev = client.get(f"/api/pathways/{demo['id']}/preview", headers=h).json()
    assert prev["preview"] is True and prev["signed"] is False
    lead = login(client, "lead@medora.test")
    assert client.post(f"/api/pathways/{demo['id']}/activate", headers=lead).status_code == 400
    v = client.post("/api/trust/verify-chain", headers=h).json()
    assert v["valid"] is True
    t = client.get("/api/trust", headers=h).json()
    assert t["runs"]["audit_chain"]["id"] == v["run_id"] and t["synthetic"] is True


def test_fhir_export_and_quality(client, tenant):
    h = login(client, "meera@medora.test")
    item = client.get("/api/stuck", headers=h).json()["items"][0]
    b = client.get(f"/api/patients/{item['patient_id']}/fhir", headers=h).json()
    kinds = {e["resource"]["resourceType"] for e in b["entry"]}
    assert b["resourceType"] == "Bundle" and {"Patient", "Task"} <= kinds
    assert all(e["resource"]["meta"]["tag"][0]["code"] == "synthetic" for e in b["entry"])
    assert "diagnosis" not in str(b).lower()
    job = client.get("/api/jobs", headers=h).json()[0]
    q = client.get(f"/api/jobs/{job['id']}/quality", headers=h).json()
    assert 0 <= q["missing_phone_rate"] <= 1 and q["rows"] > 0


def test_doctor_panel_history_points_have_no_causes(client, tenant):
    assert client.get("/api/doctor/patients", headers=login(client, "meera@medora.test")).status_code == 403
    h = login(client, "lead@medora.test")
    pts = client.get("/api/doctor/patients", headers=h).json()
    assert pts and all(p["points"] >= 1 for p in pts)
    hist = client.get(f"/api/doctor/patients/{pts[0]['id']}/history", headers=h).json()
    assert hist["points"] and all(p["source_ref"] and p["label"] for p in hist["points"])
    assert not {"reason_code", "outcome", "cause"} & set(str(hist).replace('"', " ").split())
