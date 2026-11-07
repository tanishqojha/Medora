"""S3 step 4: on time, late, missed, unreachable patients against the GI pathway."""
from datetime import datetime, timedelta

from medora.config import ROOT
from medora.pathways import load_file
from medora.rules import Ev, check, gaps_from_spec

_, SPEC = load_file(ROOT / "pathways" / "gi_cancer_handover.v1.yaml")
GAP = gaps_from_spec(SPEC)[0]  # tumour board -> treatment booked
D0 = datetime.fromisoformat("2026-10-01T00:00:00+05:30")
TB = Ev("tb-1", "tb_decision_recorded", D0)


def run(events, days_later):
    return check("gi v1", GAP, TB, [TB, *events], D0 + timedelta(days=days_later), 3)


def test_on_time_closes_by_evidence():
    d = run([Ev("bk-1", "appointment_booked", D0 + timedelta(days=3))], 10)
    assert d.state == "closed_evidence" and d.evidence_event_id == "bk-1" and d.flag_kind is None


def test_not_yet_due_no_flag():
    d = run([], 5)
    assert d.state == "open" and d.flag_kind is None


def test_late_is_overdue_with_reason():
    d = run([], 9)
    assert d.flag_kind == "overdue" and d.days_overdue == 2
    assert d.reason_line == "Tumour board decision 9 days ago, no treatment booking recorded."


def test_missed_flags_before_due():
    d = run([Ev("m-1", "appointment_missed", D0 + timedelta(days=2))], 4)
    assert d.flag_kind == "missed" and d.missed_count == 1


def test_unreachable_after_three_attempts():
    tries = [Ev(f"a{i}", "contact_attempted", D0 + timedelta(days=8 + i)) for i in range(3)]
    d = run(tries, 12)
    assert d.flag_kind == "unreachable" and d.attempts == 3


def test_reached_is_not_unreachable():
    tries = [Ev(f"a{i}", "contact_attempted", D0 + timedelta(days=8 + i)) for i in range(3)]
    d = run([*tries, Ev("o", "contact_outcome_recorded", D0 + timedelta(days=10), "reached")], 12)
    assert d.flag_kind == "overdue"


def test_deterministic_hash():
    assert run([], 9).result_hash == run([], 9).result_hash
    assert run([], 9).result_hash != run([], 10).result_hash


def test_events_after_as_of_ignored():
    d = run([Ev("bk-late", "appointment_booked", D0 + timedelta(days=20))], 9)
    assert d.flag_kind == "overdue"


def test_bundle_hint_only_for_several_days_soon():
    from datetime import date as d

    from medora.callassist import bundle_hint
    today = d(2026, 10, 10)
    assert bundle_hint([{"date": "2026-10-12", "department": "Lab"}], today) is None
    assert bundle_hint([{"date": "2026-10-12"}, {"date": "2026-10-12"}], today) is None       # already one day
    assert bundle_hint([{"date": "2026-10-12"}, {"date": "2026-11-30"}], today) is None       # second is far off
    h = bundle_hint([{"date": "2026-10-12", "department": "Lab"}, {"date": "2026-10-15", "department": "Medical Oncology"}], today)
    assert h and h["dates"] == ["2026-10-12", "2026-10-15"] and "Lab on 12 Oct" in h["text"]
    assert bundle_hint([{"date": "2026-10-01"}, {"date": "2026-10-12"}], today) is None       # past visits ignored
