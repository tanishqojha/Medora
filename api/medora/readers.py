"""Streaming readers for the structured lane (F2). Never load a whole file into memory.

Each reader yields the header list once, then (row_number, values) tuples. Row numbers are 1-based
spreadsheet rows so provenance points at the exact cell a person would open.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import polars as pl

BATCH = 5000


def _clean(v: Any) -> Any:
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def read_csv(path: Path) -> Iterator[Any]:
    lf = pl.scan_csv(path, infer_schema=False, encoding="utf8-lossy", truncate_ragged_lines=True,
                     has_header=True)
    headers = lf.collect_schema().names()
    yield headers
    row_no = 1  # header is row 1
    for batch in lf.collect_batches(chunk_size=BATCH):
        for values in batch.iter_rows():
            row_no += 1
            yield row_no, [_clean(v) for v in values]


def read_xlsx(path: Path) -> Iterator[Any]:
    from openpyxl import load_workbook

    # read_only streams rows; data_only reads cached values, never formulas or macros.
    wb = load_workbook(path, read_only=True, data_only=True, keep_vba=False)
    try:
        ws = wb.worksheets[0]
        headers: list[str] | None = None
        width = 0
        for row_no, values in enumerate(ws.iter_rows(values_only=True), start=1):
            vals = [_clean(v) for v in values]
            if headers is None:
                # Exports often start with title lines ("X CANCER CENTRE ... REGISTER", "Export date").
                # The header is the first row with at least 3 filled cells.
                if sum(v is not None for v in vals) < 3:
                    continue
                while vals and vals[-1] is None:
                    vals.pop()
                headers = [str(v) if v is not None else f"column_{i + 1}" for i, v in enumerate(vals)]
                width = len(headers)
                yield headers
                continue
            vals = (vals + [None] * width)[:width]
            # Printed registers repeat the header on every page; those rows are not data.
            if [str(v) if v is not None else None for v in vals] == [h if not h.startswith("column_") else None for h in headers]:
                continue
            if any(v is not None for v in vals):
                yield row_no, vals
        if headers is None:
            yield []
    finally:
        wb.close()


def reader(path: Path, kind: str) -> Iterator[Any]:
    if kind == "csv":
        return read_csv(path)
    if kind == "xlsx":
        return read_xlsx(path)
    raise ValueError(f"no structured reader for {kind}")
