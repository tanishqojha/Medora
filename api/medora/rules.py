"""Pure gap-check logic (F9, F10, F12). No database, no clock: same inputs give the same decision.

The compiled SQL finds candidates in bulk. This module decides each one and writes the explanation.
Replay calls the same function on the stored events and compares result hashes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

from medora.dates import IST
from medora.hashing import hash_obj


@dataclass(frozen=True)
class Ev:
    id: str
    type: str
    at: datetime
    outcome: str | None = None


@dataclass(frozen=True)
class Gap:
    from_step: str
    expected_step: str
    from_type: str
    expected_type: str
    from_label: str
    expected_label: str
    max_gap_days: int
    flag_after_days: int


@dataclass
class Decision:
    from_step: str
    expected_step: str
    from_event_id: str
    state: str                       # open | closed_evidence
    evidence_event_id: str | None
    due_by: datetime
    flag_kind: str | None            # overdue | missed | unreachable | None
    days_overdue: int
    missed_count: int
    attempts: int
    unreachable: bool
    reason_line: str
    steps: list[str] = field(default_factory=list)
    source_event_ids: list[str] = field(default_factory=list)
    result_hash: str = ""

    def rank_inputs(self, patient_id: str) -> dict[str, Any]:
        return {"days_overdue": self.days_overdue, "missed_count": self.missed_count,
                "attempts": self.attempts, "unreachable": self.unreachable,
                "due_by": self.due_by.isoformat(), "patient_id": patient_id}


def gaps_from_spec(spec: dict[str, Any]) -> list[Gap]:
    """Every step with max_gap_days_from is a handover. An obligations entry may set a flag threshold."""
    steps = {s["id"]: s for s in spec["steps"]}
    flag_after = {(o["when"], o["expects"]): o["flag_if_missing_after_days"] for o in spec.get("obligations", [])}
    out = []
    for s in spec["steps"]:
        if "max_gap_days_from" not in s:
            continue
        src = steps[s["max_gap_days_from"]]
        out.append(Gap(
            from_step=src["id"], expected_step=s["id"], from_type=src["event_type"], expected_type=s["event_type"],
            from_label=src["label"], expected_label=s["label"], max_gap_days=s["max_gap_days"],
            flag_after_days=flag_after.get((src["id"], s["id"]), s["max_gap_days"]),
        ))
    return out


def _d(dt: datetime) -> str:
    return dt.astimezone(IST).date().isoformat()


def check(rule_version: str, gap: Gap, from_ev: Ev, events: list[Ev], as_of: datetime,
          unreachable_after: int) -> Decision:
    """Decide one obligation for one patient. `events` are that patient's live events up to as_of."""
    evs = sorted((e for e in events if e.at <= as_of), key=lambda e: (e.at, e.id))
    after = [e for e in evs if e.at >= from_ev.at and e.id != from_ev.id]
    evidence = next((e for e in after if e.type == gap.expected_type), None)
    horizon = evidence.at if evidence else as_of
    window = [e for e in after if e.at <= horizon]
    missed = [e for e in window if e.type == "appointment_missed"]
    attempts = [e for e in window if e.type == "contact_attempted"]
    reached = any(e.type == "contact_outcome_recorded" and e.outcome == "reached" for e in window)
    due_by = from_ev.at + timedelta(days=gap.max_gap_days)
    flag_after = from_ev.at + timedelta(days=gap.flag_after_days)
    days_overdue = max(0, (as_of - due_by).days) if not evidence else 0
    unreachable = len(attempts) >= unreachable_after and not reached

    steps = [
        f"Rule {rule_version}: after {gap.from_label}, expect {gap.expected_label} within {gap.max_gap_days} days.",
        f"Found {gap.from_label} on {_d(from_ev.at)} (event {from_ev.id[:8]}).",
    ]
    if evidence:
        steps.append(f"Found {gap.expected_label} on {_d(evidence.at)} (event {evidence.id[:8]}). Obligation closed.")
        state, kind = "closed_evidence", None
    else:
        steps.append(f"Looked for {gap.expected_type} from {_d(from_ev.at)} to {_d(as_of)}: none found.")
        steps.append(f"Due by {_d(due_by)}. Checked on {_d(as_of)}: {days_overdue} days past due.")
        state = "open"
        kind = None
        if unreachable:
            kind = "unreachable"
        elif missed:
            kind = "missed"
        elif as_of > flag_after:
            kind = "overdue"
    steps.append(f"Missed appointments: {len(missed)}. Call attempts: {len(attempts)}. "
                 f"Reached: {'yes' if reached else 'no'}.")
    steps.append(f"Result: flag {kind}." if kind else "Result: no flag.")

    days_since = (as_of - from_ev.at).days
    if kind == "unreachable":
        reason = f"{len(attempts)} call attempts, not reached. No {gap.expected_label} recorded."
    elif kind == "missed":
        reason = f"Missed appointment on {_d(missed[-1].at)}, no {gap.expected_label} recorded."
    elif kind == "overdue":
        reason = f"{gap.from_label} {days_since} days ago, no {gap.expected_label} recorded."
    else:
        reason = "On track."
    reason = reason[:1].upper() + reason[1:]

    source = [from_ev.id] + ([evidence.id] if evidence else []) + [e.id for e in missed + attempts]
    d = Decision(
        from_step=gap.from_step, expected_step=gap.expected_step, from_event_id=from_ev.id, state=state,
        evidence_event_id=evidence.id if evidence else None, due_by=due_by, flag_kind=kind,
        days_overdue=days_overdue, missed_count=len(missed), attempts=len(attempts), unreachable=unreachable,
        reason_line=reason, steps=steps, source_event_ids=source,
    )
    d.result_hash = decision_hash(d)
    return d


def decision_hash(d: Decision) -> str:
    body = asdict(d)
    body.pop("result_hash")
    return hash_obj(body)
