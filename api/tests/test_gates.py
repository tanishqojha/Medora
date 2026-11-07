"""S11: a pending approval survives a restart; a timeout escalates and never approves."""
import importlib

import pytest

from medora import graphs, reviews
from medora.db import one, tx

pytestmark = pytest.mark.db


def _identity_item(hid):
    with tx() as conn:
        a, b = (str(conn.execute("INSERT INTO patients (hospital_id, display_name) VALUES (%s, %s) RETURNING id",
                                 (hid, n)).fetchone()["id"]) for n in ("Asha Rao", "Asha Rao"))
        return str(one(conn, """INSERT INTO review_items (hospital_id, type, payload, due_at)
                               VALUES (%s, 'identity', %s::jsonb, now() - interval '1 hour') RETURNING id""",
                       (hid, f'{{"patient_a": "{a}", "patient_b": "{b}", "score": 0.7, "features": {{}}}}'))["id"])


def test_pending_gate_survives_restart(hospital):
    item = _identity_item(hospital)
    graphs.start("identity", hospital, item, {})
    assert graphs.pending("identity", item)
    importlib.reload(graphs)        # simulate a fresh process: no in-memory state survives
    importlib.reload(reviews)       # re-registers the gate handlers on the reloaded module
    assert graphs.pending("identity", item)
    res = reviews.decide_identity(hospital, item, True, "Steward (synthetic)")
    assert res["merged"] is True
    assert not graphs.pending("identity", item)
    with tx() as conn:
        assert one(conn, "SELECT count(*) AS n FROM audit_log WHERE hospital_id = %s AND action = 'identity.merge'",
                   (hospital,))["n"] == 1
    with pytest.raises(ValueError):
        reviews.decide_identity(hospital, item, False, "someone else")


def test_timeout_escalates_never_approves(hospital):
    item = _identity_item(hospital)
    with tx() as conn:
        reviews.escalate_overdue(conn)
        row = one(conn, "SELECT state, decision FROM review_items WHERE id = %s", (item,))
        merges = one(conn, "SELECT count(*) AS n FROM patient_merges WHERE hospital_id = %s", (hospital,))["n"]
    assert row["state"] == "escalated" and row["decision"] is None and merges == 0
