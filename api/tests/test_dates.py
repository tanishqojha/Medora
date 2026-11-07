from datetime import date

from medora.dates import detect_convention, parse

T = date(2026, 10, 10)


def test_excel_serial():
    assert parse(45940, today=T).value == date(2025, 10, 10)
    assert parse("45940", today=T).value == date(2025, 10, 10)


def test_devanagari_numerals():
    p = parse("२५/०९/२०२६", today=T)
    assert p.value == date(2026, 9, 25) and "devanagari_numerals" in p.notes


def test_unambiguous_dmy_and_mdy():
    assert parse("25/09/2026", today=T).value == date(2026, 9, 25)
    assert parse("09/25/2026", today=T).value == date(2026, 9, 25)


def test_ambiguous_never_silently_resolved():
    p = parse("03/04/2026", today=T)
    assert p.value is None and p.ambiguous
    assert set(p.candidates) == {date(2026, 4, 3), date(2026, 3, 4)}


def test_ambiguous_resolved_only_by_confirmed_convention():
    assert parse("03/04/2026", convention="dmy", today=T).value == date(2026, 4, 3)
    assert parse("03/04/2026", convention="mdy", today=T).value == date(2026, 3, 4)


def test_same_day_month_is_not_ambiguous():
    assert parse("05/05/2026", today=T).ok


def test_two_digit_year():
    p = parse("25/09/26", today=T)
    assert p.value == date(2026, 9, 25) and "two_digit_year" in p.notes
    assert parse("25/09/85", today=T).value == date(1985, 9, 25)


def test_iso_and_named():
    assert parse("2026-09-25", today=T).value == date(2026, 9, 25)
    assert parse("12 Oct 2026", today=T).value == date(2026, 10, 12)
    assert parse("Oct 12, 2026", today=T).value == date(2026, 10, 12)


def test_invalid_and_empty():
    assert parse("31/02/2026", today=T).value is None
    assert parse("", today=T).reason == "empty"
    assert parse("soon", today=T).value is None


def test_detect_convention():
    assert detect_convention(["25/09/2026", "03/04/2026"]) == "dmy"
    assert detect_convention(["09/25/2026"]) == "mdy"
    assert detect_convention(["03/04/2026"]) is None
