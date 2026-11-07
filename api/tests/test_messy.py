"""F4 messy lane: scanned PDF through OCR, vision fallback used and vision fallback failing closed."""
import importlib.util
from datetime import date
from pathlib import Path

import pytest
from PIL import Image

from medora import llm, messy, synth


@pytest.fixture(scope="module")
def scan(tmp_path_factory):
    d = tmp_path_factory.mktemp("scan")
    rows = [r for r in synth.clean_rows(synth.make_patients(20, 5, date(2026, 10, 10)))][:6]
    png = d / "register.png"
    synth.render_photo(rows, png, seed=5)
    pdf = d / "register.pdf"
    Image.open(png).convert("RGB").save(pdf)  # an image-only PDF: no text layer, like a scanner makes
    return pdf, rows


def test_scanned_pdf_goes_through_ocr_with_crops(scan):
    pdf, rows = scan
    it = messy.reader(pdf, "pdf")
    headers = next(it)
    assert {"patient_name", "phone", "hospital_number", "event_date"} <= set(headers)
    got = [dict(zip(headers, v, strict=False)) for _, v in it]
    assert len(got) == len(rows)
    read = {str(g["hospital_number"]["v"]).replace(" ", "") for g in got}
    assert sum(r["UHID"] in read for r in rows) >= len(rows) - 1
    assert all(c["ref"]["crop"] and c["ref"]["page"] == 1 for g in got for c in g.values())


def test_low_ocr_confidence_uses_vision_on_the_row_crop(scan, monkeypatch):
    pdf, _ = scan
    real = messy.setting
    monkeypatch.setattr(messy, "setting", lambda k: 1.01 if k == "messy.ocr_min_confidence" else real(k))
    sent = []

    def fake_call(prompt, inputs, known=None, model_var="LLM_MODEL"):
        sent.append(inputs)
        return {"fields": [{"name": "patient_name", "value": "From Vision", "confidence": 0.97}]}, \
            {"prompt_version": "vision_extract_v1", "replay": False}
    monkeypatch.setattr(messy.llm, "call", fake_call)
    it = messy.reader(pdf, "pdf")
    headers = next(it)
    first = dict(zip(headers, next(it)[1], strict=False))
    assert first["patient_name"]["v"] == "From Vision" and first["patient_name"]["ref"]["method"] == "vision"
    assert sent and sent[0]["image_crop"][:4] == b"\x89PNG" and set(sent[0]) == {"image_crop", "fields", "page_hint"}


def test_vision_unavailable_keeps_ocr_values_for_review(scan, monkeypatch):
    pdf, _ = scan
    real = messy.setting
    monkeypatch.setattr(messy, "setting", lambda k: 1.01 if k == "messy.ocr_min_confidence" else real(k))

    def down(*a, **k):
        raise llm.LLMUnavailable("no provider")
    monkeypatch.setattr(messy.llm, "call", down)
    it = messy.reader(pdf, "pdf")
    headers = next(it)
    first = dict(zip(headers, next(it)[1], strict=False))
    # The row keeps what OCR read, with OCR's own confidence; ingest then routes it by the field threshold.
    assert first["patient_name"]["ref"]["method"] == "ocr"
    assert first["patient_name"]["v"] and 0 < first["patient_name"]["c"] <= 1


@pytest.mark.db
def test_worker_verifies_each_chain_once_a_day(hospital):
    spec = importlib.util.spec_from_file_location("worker", Path(__file__).resolve().parents[2] / "worker" / "worker.py")
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    from medora.db import tx

    worker.verify_chains_daily()
    worker.verify_chains_daily()
    with tx() as conn:
        runs = conn.execute("SELECT passed FROM eval_runs WHERE hospital_id = %s AND kind = 'audit_chain'", (hospital,)).fetchall()
    assert [r["passed"] for r in runs] == [True]
