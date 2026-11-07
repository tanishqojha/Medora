import pytest

from medora.config import ROOT
from medora.pathways import PathwayError, compile_sql, load_file, parse

SNAP = ROOT / "api" / "tests" / "snapshots"


@pytest.mark.parametrize("name", ["gi_cancer_handover.v1", "breast_handover_demo.v1"])
def test_compile_snapshot(name):
    _, spec = load_file(ROOT / "pathways" / f"{name}.yaml")
    sql = compile_sql(spec)
    snap = SNAP / f"{name}.sql"
    if not snap.exists():
        snap.write_text(sql, encoding="utf-8")
    assert sql == snap.read_text(encoding="utf-8"), "compiled SQL changed; review and refresh the snapshot"


def test_rejects_unknown_event_type():
    text = (ROOT / "pathways" / "gi_cancer_handover.v1.yaml").read_text(encoding="utf-8")
    with pytest.raises(PathwayError):
        parse(text.replace("appointment_booked", "lab_result_received"))


def test_rejects_injection_in_ids():
    text = (ROOT / "pathways" / "gi_cancer_handover.v1.yaml").read_text(encoding="utf-8")
    with pytest.raises(PathwayError):
        parse(text.replace("id: treatment_booked", "id: \"x'; DROP TABLE events;--\""))


def test_rejects_obligation_without_gap():
    text = (ROOT / "pathways" / "gi_cancer_handover.v1.yaml").read_text(encoding="utf-8")
    with pytest.raises(PathwayError):
        parse(text.replace("expects: treatment_booked", "expects: treatment_attended"))
