from pathlib import Path

from openpyxl import Workbook

from medora.readers import read_xlsx


def test_xlsx_skips_title_lines_and_repeated_headers(tmp_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["DEMO CENTRE REGISTER (SYNTHETIC)"])
    ws.append(["Export date 01-11-2026"])
    ws.append([])
    ws.append(["Date", "UHID", "Visit Type"])
    ws.append(["01-10-2026", "X/1", "OPD"])
    ws.append(["Date", "UHID", "Visit Type"])  # header printed again on page 2
    ws.append(["02-10-2026", "X/2", "Call"])
    p = tmp_path / "r.xlsx"
    wb.save(p)

    it = read_xlsx(p)
    assert next(it) == ["Date", "UHID", "Visit Type"]
    rows = list(it)
    assert [r[1][1] for r in rows] == ["X/1", "X/2"]
    assert [r[0] for r in rows] == [5, 7]  # row numbers stay true to the file for provenance


def test_register_labels_get_rule_suggestions() -> None:
    from medora.mapping import suggest_label
    expect = {"Appt given": "appointment_booked", "new date given": "appointment_booked", "Att.": "appointment_attended",
              "Did not come": "appointment_missed", "No answer": "contact_attempted", "Wrong no": "contact_attempted",
              "Spoke with family": "contact_outcome_recorded", "TB done": "tb_decision_recorded",
              "Reported": None, "OPD": None}
    assert {k: suggest_label(k) for k in expect} == expect
