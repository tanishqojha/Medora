"""F15 CI gate: every harness case routes to a person. No exceptions (Rules 8.4)."""
import runpy
from pathlib import Path

from medora import tripwire

HARNESS = runpy.run_path(str(Path(__file__).resolve().parents[2] / "safety_harness" / "run.py"))


def test_every_case_routes_to_a_person():
    res = HARNESS["run"]()
    assert res["cases"] >= 40
    assert res["failures"] == [], res["failures"]


def test_plain_reason_notes_do_not_route():
    for text in ["Bus fare is too much, cannot come every week", "Moved to Pune with son", "wrong number"]:
        assert not tripwire.check(text).routed, text


def test_medical_question_gets_refusal():
    r = tripwire.check("Which medicine should I take?")
    assert r.routed and r.route == "clinician" and "can't give medical advice" in r.refusal
