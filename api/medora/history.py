"""Doctor panel: turn a patient's events into plain history points.

A history point is a dated schedule fact with its source. It never states a cause, a reason, a result or an
interpretation (Rules 1.1, 2.9). Reason codes and call outcomes are left out on purpose. The only derived value
is the number of days since the previous point, which is date arithmetic.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

LABELS = {
    "tb_decision_recorded": "Tumour board decision recorded",
    "surgery_recorded": "Surgery recorded",
    "appointment_booked": "Appointment booked",
    "appointment_attended": "Visit attended",
    "appointment_missed": "Visit missed",
    "appointment_cancelled": "Appointment cancelled",
    "contact_attempted": "Call attempted",
    "contact_outcome_recorded": "Call outcome recorded",
    "correction": "Entry corrected by a person",
}


def _day(v: Any) -> date:
    return v.date() if isinstance(v, datetime) else date.fromisoformat(str(v)[:10])


def _detail(e: dict[str, Any]) -> str | None:
    p = e.get("payload") or {}
    parts = []
    if e["type"] == "appointment_booked" and p.get("appointment_date"):
        parts.append(f"for {p['appointment_date']}")
    if p.get("department") and e["type"] not in ("contact_attempted", "contact_outcome_recorded", "correction"):
        parts.append(str(p["department"]))
    return ", ".join(parts) or None


def build_history(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Events in, ordered history points out. Unknown event types are kept with a neutral label."""
    points: list[dict[str, Any]] = []
    prev: date | None = None
    for e in sorted(events, key=lambda x: (x["effective_at"], str(x["id"]))):
        d = _day(e["effective_at"])
        points.append({
            "id": str(e["id"]), "type": e["type"], "label": LABELS.get(e["type"], "Event recorded"),
            "detail": _detail(e), "date": d.isoformat(),
            "days_since_previous": (d - prev).days if prev else None,
            "source_ref": e.get("source_ref"), "confidence": e.get("confidence"), "synthetic": bool(e.get("synthetic")),
        })
        prev = d
    return points


if __name__ == "__main__":
    ev = [
        {"id": 2, "type": "appointment_booked", "effective_at": "2026-10-08", "payload": {"appointment_date": "2026-10-15"}},
        {"id": 1, "type": "tb_decision_recorded", "effective_at": "2026-10-01", "payload": {"department": "Tumour Board"}},
        {"id": 3, "type": "contact_outcome_recorded", "effective_at": "2026-10-12",
         "payload": {"reason_code": "cost", "outcome": "reached"}},
    ]
    h = build_history(ev)
    assert [p["type"] for p in h] == ["tb_decision_recorded", "appointment_booked", "contact_outcome_recorded"]
    assert [p["days_since_previous"] for p in h] == [None, 7, 4]
    assert "cost" not in str(h) and "reached" not in str(h), "no reasons or outcomes in the doctor view"
    print("history ok")
