"""Shared date parser (F6, S8). Ambiguous dates are never silently resolved.

Handles Excel serials, Devanagari numerals, two-digit years, dd/mm vs mm/dd, ISO and month names.
`convention` is the file-level convention confirmed by a person on the Mapping Confirm screen.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
_DEVANAGARI = str.maketrans("०१२३४५६७८९", "0123456789")
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_EXCEL_EPOCH = date(1899, 12, 30)
_NUMERIC = re.compile(r"^\d+(\.\d+)?$")
_ISO = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ T].*)?$")
_DMY = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})(?:[ T].*)?$")
_NAMED = re.compile(r"^(\d{1,2})[\s\-/.]*([A-Za-z]{3,9})[\s\-/.,]*(\d{2}|\d{4})$")
_NAMED_US = re.compile(r"^([A-Za-z]{3,9})[\s\-/.]*(\d{1,2})[\s,]*(\d{2}|\d{4})$")


@dataclass(frozen=True)
class ParsedDate:
    value: date | None
    ambiguous: bool = False
    reason: str = ""
    candidates: tuple[date, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.value is not None and not self.ambiguous

    def as_datetime(self) -> datetime:
        assert self.value is not None
        return datetime.combine(self.value, time(0, 0), tzinfo=IST)


def _year(y: str, today: date) -> tuple[int, tuple[str, ...]]:
    if len(y) == 4:
        return int(y), ()
    yy = int(y)
    full = 2000 + yy
    if full > today.year + 1:  # pivot: no follow-up event is dated more than a year ahead
        full = 1900 + yy
    return full, ("two_digit_year",)


def _safe(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def parse(raw: object, convention: str | None = None, today: date | None = None) -> ParsedDate:
    today = today or date.today()
    if raw is None:
        return ParsedDate(None, reason="empty")
    if isinstance(raw, datetime):
        return ParsedDate(raw.date())
    if isinstance(raw, date):
        return ParsedDate(raw)
    if isinstance(raw, int | float) and not isinstance(raw, bool):
        return _excel(float(raw))
    s = str(raw).strip().translate(_DEVANAGARI)
    notes: tuple[str, ...] = ("devanagari_numerals",) if s != str(raw).strip() else ()
    if not s:
        return ParsedDate(None, reason="empty")
    if _NUMERIC.match(s):
        p = _excel(float(s))
        return ParsedDate(p.value, p.ambiguous, p.reason, p.candidates, p.notes + notes)
    if m := _ISO.match(s):
        d = _safe(int(m[1]), int(m[2]), int(m[3]))
        return ParsedDate(d, reason="" if d else "invalid", notes=notes)
    if m := _NAMED.match(s):
        return _named(m[1], m[2], m[3], today, notes)
    if m := _NAMED_US.match(s):
        return _named(m[2], m[1], m[3], today, notes)
    if m := _DMY.match(s):
        a, b = int(m[1]), int(m[2])
        y, ynotes = _year(m[3], today)
        notes += ynotes
        dmy, mdy = _safe(y, b, a), _safe(y, a, b)
        if dmy and not mdy:
            return ParsedDate(dmy, notes=notes)
        if mdy and not dmy:
            return ParsedDate(mdy, notes=notes)
        if not dmy and not mdy:
            return ParsedDate(None, reason="invalid", notes=notes)
        if dmy == mdy:
            return ParsedDate(dmy, notes=notes)
        assert dmy and mdy
        if convention == "dmy":
            return ParsedDate(dmy, notes=notes + ("resolved_by_confirmed_convention",))
        if convention == "mdy":
            return ParsedDate(mdy, notes=notes + ("resolved_by_confirmed_convention",))
        return ParsedDate(None, ambiguous=True, reason="day/month order unclear", candidates=(dmy, mdy), notes=notes)
    return ParsedDate(None, reason="unrecognised format", notes=notes)


def _excel(n: float) -> ParsedDate:
    if 20000 <= n <= 80000:  # 1954..2119 as Excel serials
        return ParsedDate(_EXCEL_EPOCH + timedelta(days=int(n)), notes=("excel_serial",))
    return ParsedDate(None, reason="number is not a plausible date")


def _named(day: str, month: str, year: str, today: date, notes: tuple[str, ...]) -> ParsedDate:
    mon = _MONTHS.get(month[:3].lower())
    if not mon:
        return ParsedDate(None, reason="unknown month name", notes=notes)
    y, ynotes = _year(year, today)
    d = _safe(y, mon, int(day))
    return ParsedDate(d, reason="" if d else "invalid", notes=notes + ynotes)


def detect_convention(samples: list[object]) -> str | None:
    """Suggest a file convention from unambiguous samples. A person must still confirm it."""
    votes = {"dmy": 0, "mdy": 0}
    for s in samples:
        m = _DMY.match(str(s).strip().translate(_DEVANAGARI))
        if not m:
            continue
        a, b = int(m[1]), int(m[2])
        if a > 12 >= b:
            votes["dmy"] += 1
        elif b > 12 >= a:
            votes["mdy"] += 1
    if votes["dmy"] and not votes["mdy"]:
        return "dmy"
    if votes["mdy"] and not votes["dmy"]:
        return "mdy"
    return None
