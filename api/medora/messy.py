"""Messy lane: PDFs (text and scanned) and phone photos of registers (F4, S6).

Order of work, cheapest first:
1. PDF text layer (exact text, no model).
2. OCR (RapidOCR, runs locally) for scanned pages and photos.
3. Vision LLM on a crop of one row, only when OCR confidence for that row is low.
Output uses canonical field names, so columns outside the whitelist (diagnosis, results) are dropped here.
Each cell carries {"v": value, "c": confidence, "ref": crop or page/line reference}.
"""
from __future__ import annotations

import io
import logging
import re
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any

from medora import llm
from medora.config import setting
from medora.hashing import sha256
from medora.mapping import suggest_field

log = logging.getLogger("medora.messy")
ROW_STRIDE = 1000  # row number = page * 1000 + line, so provenance names page and line


@lru_cache
def _ocr() -> Any:
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _crop_dir(path: Path) -> Path:
    d = path.parent / "crops" / path.stem
    d.mkdir(parents=True, exist_ok=True)
    return d


def _canonical_columns(header_cells: list[str]) -> list[tuple[int, str]]:
    """Header cell index -> canonical field, dropping anything not whitelisted."""
    out, used = [], set()
    for i, h in enumerate(header_cells):
        f = suggest_field(h)
        if f != "ignore" and f not in used:
            out.append((i, f))
            used.add(f)
    return out


# ---------- PDF text layer ----------

def _split(line: str) -> list[str]:
    parts = re.split(r"\s*\|\s*|\t| {2,}", line.strip())
    return [p for p in parts if p]


def _pdf_text_rows(path: Path) -> Iterator[Any]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    max_pages = int(setting("ingest.max_pdf_pages"))
    columns: list[tuple[int, str]] | None = None
    scanned_pages: list[int] = []
    header_sent = False
    for pno, page in enumerate(reader.pages[:max_pages], start=1):
        text = page.extract_text() or ""
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) < 2:
            scanned_pages.append(pno)
            continue
        for lno, line in enumerate(lines, start=1):
            cells = _split(line)
            if columns is None:
                cand = _canonical_columns(cells)
                if len(cand) >= 2:
                    columns = cand
                    yield [f for _, f in columns]
                    header_sent = True
                continue
            if len(cells) < 2:
                continue
            ref = {"page": pno, "line": lno, "method": "pdf_text"}
            yield pno * ROW_STRIDE + lno, [{"v": cells[i] if i < len(cells) else None, "c": 1.0, "ref": ref}
                                           for i, _ in columns]
    if scanned_pages:
        yield from _pdf_scanned(path, scanned_pages, columns, header_sent)
    elif not header_sent:
        yield []


def _pdf_scanned(path: Path, pages: list[int], columns: list[tuple[int, str]] | None,
                 header_sent: bool) -> Iterator[Any]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    state: dict[str, Any] = {"fields": [f for _, f in columns] if columns else None, "header_sent": header_sent}
    try:
        for pno in pages:
            img = pdf[pno - 1].render(scale=2).to_pil()
            yield from _image_rows(img, path, pno, state)
    finally:
        pdf.close()
    if not state["header_sent"]:
        yield []


# ---------- OCR for photos and scans ----------

def _best_rotation(img: Any) -> tuple[Any, list[Any]]:
    """Phone photos arrive rotated. OCR reads each text box upright on its own, so text alone cannot tell
    orientation. Layout can: in the right orientation boxes are wide, and the header row sits on top."""
    import numpy as np

    best: tuple[tuple[float, int, float], Any, list[Any]] = ((-1.0, -99, -1.0), img, [])
    for angle in (0, 90, 180, 270):
        cand = img.rotate(angle, expand=True) if angle else img
        result, _ = _ocr()(np.array(cand.convert("RGB")))
        boxes = result or []
        if not boxes:
            continue
        wide = sum(1 for pts, _, _ in boxes if (max(p[0] for p in pts) - min(p[0] for p in pts))
                   > (max(p[1] for p in pts) - min(p[1] for p in pts))) / len(boxes)
        lines = _lines(boxes)
        header_at = next((i for i, ln in enumerate(lines)
                          if len({suggest_field(b["text"]) for b in ln} - {"ignore"}) >= 3), 99)
        key = (round(wide, 1), -header_at, sum(float(b[2]) for b in boxes))
        if key > best[0]:
            best = (key, cand, boxes)
    return best[1], best[2]


def _lines(boxes: list[Any]) -> list[list[dict[str, Any]]]:
    items = []
    for pts, text, score in boxes:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        items.append({"text": text, "score": float(score), "x0": min(xs), "x1": max(xs), "y0": min(ys), "y1": max(ys),
                      "xc": (min(xs) + max(xs)) / 2, "yc": (min(ys) + max(ys)) / 2, "h": max(ys) - min(ys)})
    if not items:
        return []
    items.sort(key=lambda b: b["yc"])
    heights = sorted(b["h"] for b in items)
    tol = 0.6 * heights[len(heights) // 2]
    lines: list[list[dict[str, Any]]] = [[items[0]]]
    for b in items[1:]:
        if abs(b["yc"] - lines[-1][-1]["yc"]) <= tol:
            lines[-1].append(b)
        else:
            lines.append([b])
    return [sorted(ln, key=lambda b: b["x0"]) for ln in lines]


def _image_rows(img: Any, path: Path, page: int, state: dict[str, Any]) -> Iterator[Any]:
    img, boxes = _best_rotation(img)
    lines = _lines(boxes)
    min_ocr = float(setting("messy.ocr_min_confidence"))
    header_x: list[tuple[float, str]] | None = None
    crops = _crop_dir(path)
    for lno, line in enumerate(lines, start=1):
        if header_x is None:
            fields = [(b["xc"], suggest_field(b["text"])) for b in line]
            fields = [(x, f) for x, f in fields if f != "ignore"]
            if len({f for _, f in fields}) >= 2:
                header_x = fields
                names = [f for _, f in header_x]
                if not state["header_sent"]:
                    state["fields"], state["header_sent"] = names, True
                    yield names
            continue
        cells: dict[str, list[dict[str, Any]]] = {}
        for b in line:
            nearest = min(header_x, key=lambda hf: abs(hf[0] - b["xc"]))[1]
            cells.setdefault(nearest, []).append(b)
        y0 = max(0, int(min(b["y0"] for b in line) - 6))
        y1 = int(max(b["y1"] for b in line) + 6)
        crop = img.crop((0, y0, img.width, y1))
        buf = io.BytesIO()
        crop.save(buf, format="PNG")
        png = buf.getvalue()
        crop_name = f"p{page}_l{lno}_{sha256(png)[:8]}.png"
        (crops / crop_name).write_bytes(png)
        ref = {"page": page, "line": lno, "crop": f"{path.stem}/{crop_name}", "method": "ocr"}
        values = {f: (" ".join(b["text"] for b in bs), min(b["score"] for b in bs)) for f, bs in cells.items()}
        row_conf = min((c for _, c in values.values()), default=0.0)
        if row_conf < min_ocr:
            values, ref = _vision(png, state["fields"], values, ref)
        # A blank cell is not a misread: it carries the row's read confidence.
        row_conf = min((c for _, c in values.values()), default=0.0)
        yield page * ROW_STRIDE + lno, [{"v": values.get(f, (None, row_conf))[0], "c": values.get(f, (None, row_conf))[1],
                                         "ref": ref} for f in state["fields"]]


def _vision(png: bytes, fields: list[str], ocr_values: dict[str, tuple[str, float]],
            ref: dict[str, Any]) -> tuple[dict[str, tuple[str, float]], dict[str, Any]]:
    """Low OCR confidence: ask the vision model about this one row crop. Any failure keeps OCR values (to review)."""
    try:
        out, meta = llm.call("vision_extract_v1", {"image_crop": png, "fields": fields, "page_hint": "register row"},
                             model_var="VISION_MODEL")
    except (llm.LLMUnavailable, llm.PayloadRejected) as e:
        log.info("vision fallback unavailable, row goes to review", extra={"error": str(e)})
        return ocr_values, ref
    vals = {f["name"]: (f["value"], float(f["confidence"])) for f in out["fields"]
            if f["name"] in fields and f["value"] is not None}
    return vals, {**ref, "method": "vision", "prompt_version": meta["prompt_version"], "replay": meta["replay"]}


def _image_file_rows(path: Path) -> Iterator[Any]:
    from PIL import Image

    with Image.open(path) as im:
        im.load()
        img = im.convert("RGB")
    state: dict[str, Any] = {"fields": None, "header_sent": False}
    yield from _image_rows(img, path, 1, state)
    if not state["header_sent"]:
        yield []


def reader(path: Path, kind: str) -> Iterator[Any]:
    if kind == "pdf":
        return _pdf_text_rows(path)
    if kind == "image":
        return _image_file_rows(path)
    raise ValueError(f"messy lane cannot read {kind}")
