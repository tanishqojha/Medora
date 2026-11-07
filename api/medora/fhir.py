"""FHIR R4 export (COULD tier). Plain JSON bundle per patient; no FHIR server needed.

Only whitelisted schedule facts go out: Patient (minimal), Appointment per booking or visit, Task per open
obligation. Everything is tagged synthetic when the record is synthetic. No diagnoses, no clinical values.
"""
from __future__ import annotations

from typing import Any

SYNTHETIC_TAG = {"system": "urn:medora:data-origin", "code": "synthetic", "display": "Synthetic data"}
APPT_STATUS = {"appointment_booked": "booked", "appointment_attended": "fulfilled", "appointment_missed": "noshow",
               "appointment_cancelled": "cancelled"}
GENDER = {"F": "female", "M": "male", "O": "other", "U": "unknown"}


def bundle(patient: dict[str, Any], identifiers: list[dict[str, Any]], events: list[dict[str, Any]],
           obligations: list[dict[str, Any]]) -> dict[str, Any]:
    pid = str(patient["id"])
    meta = {"tag": [SYNTHETIC_TAG]} if patient.get("synthetic") else {}
    ref = {"reference": f"Patient/{pid}"}
    res: dict[str, Any] = {
        "resourceType": "Patient", "id": pid, "meta": meta, "name": [{"text": patient["display_name"]}],
        "identifier": [{"system": "urn:medora:hospital-number", "value": i["value"]} for i in identifiers
                       if i["kind"] == "hospital_number"],
        "telecom": [{"system": "phone", "value": i["value"]} for i in identifiers if i["kind"] == "phone"],
    }
    if patient.get("sex"):
        res["gender"] = GENDER.get(patient["sex"], "unknown")
    if patient.get("birth_year"):
        res["birthDate"] = str(patient["birth_year"])
    entries = [res]
    for e in events:
        status = APPT_STATUS.get(e["type"])
        if not status:
            continue
        start = e["payload"].get("appointment_date") or str(e["effective_at"])[:10]
        entries.append({
            "resourceType": "Appointment", "id": str(e["id"]), "meta": meta, "status": status,
            "start": f"{start}T00:00:00+05:30" if len(start) == 10 else start,
            "serviceType": [{"text": e["payload"]["department"]}] if e["payload"].get("department") else [],
            "participant": [{"actor": ref, "status": "accepted"}],
        })
    for o in obligations:
        if o["state"] != "open":
            continue
        entries.append({
            "resourceType": "Task", "id": str(o["id"]), "meta": meta, "status": "requested", "intent": "plan",
            "description": o.get("reason_line") or f"Expected step: {o['expected_step']}",
            "for": ref, "restriction": {"period": {"end": str(o["due_by"])}},
        })
    return {"resourceType": "Bundle", "type": "collection", "meta": meta,
            "entry": [{"fullUrl": f"urn:uuid:{r['id']}", "resource": r} for r in entries]}
