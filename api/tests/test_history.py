from medora.history import build_history


def test_history_orders_dates_and_leaves_out_causes():
    ev = [
        {"id": 2, "type": "appointment_booked", "effective_at": "2026-10-08", "payload": {"appointment_date": "2026-10-15"}},
        {"id": 1, "type": "tb_decision_recorded", "effective_at": "2026-10-01", "payload": {}},
        {"id": 3, "type": "contact_outcome_recorded", "effective_at": "2026-10-12", "payload": {"reason_code": "cost"}},
    ]
    h = build_history(ev)
    assert [p["days_since_previous"] for p in h] == [None, 7, 4]
    assert h[1]["detail"] == "for 2026-10-15"
    assert "cost" not in str(h)
