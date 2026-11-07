"""LLM eval sets (S10, Rules 4.4). Runs with a provider or replay recordings; otherwise says so and skips.

Usage: uv run --project api python eval/run_llm_eval.py [--record]
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

from medora import llm
from medora.config import env, setting
from medora.evals import Metric
from medora.pii import Tokeniser, signature

HERE = Path(__file__).parent / "llm"
CODES = ["cost", "distance", "fear", "feeling_better", "wrong_number", "moved", "other"]
TARGETS = ["patient_name", "phone", "hospital_number", "sex", "age", "birth_year", "event_type", "event_date",
           "appointment_date", "department", "status", "ignore"]


def reason() -> list[Metric]:
    cases = yaml.safe_load((HERE / "reason_cases.yaml").read_text(encoding="utf-8"))["cases"]
    bar = float(setting("callassist.reason_min_confidence"))
    accepted = right = closed = 0
    for c in cases:
        try:
            out, _ = llm.call("reason_code_v1", {"text_tokenised": Tokeniser().tokenise(c["text"]), "allowed_codes": CODES})
        except llm.LLMUnavailable:
            closed += 1
            continue
        if out["confidence"] >= bar:
            accepted += 1
            right += out["reason_code"] == c["expected"]
    return [Metric("accuracy_when_confident", right / max(accepted, 1), 0.9),
            Metric("to_human_rate", (len(cases) - accepted) / len(cases), None, higher_is_better=False),
            Metric("fail_closed_calls", float(closed)), Metric("cases", float(len(cases)))]


def mapping() -> list[Metric]:
    cases = yaml.safe_load((HERE / "mapping_cases.yaml").read_text(encoding="utf-8"))["cases"]
    right = total = 0
    for c in cases:
        headers = list(c["headers"])
        try:
            out, _ = llm.call("mapping_v1", {"headers": headers, "sample_rows": [[signature(None)] * len(headers)],
                                             "target_fields": TARGETS})
        except llm.LLMUnavailable:
            total += len(headers)
            continue
        got = {x["header"]: x["field"] for x in out["columns"]}
        for h, exp in c["headers"].items():
            total += 1
            right += got.get(h, "ignore") == exp
    return [Metric("header_accuracy", right / max(total, 1), 0.9), Metric("cases", float(len(cases)))]


def main() -> int:
    if not env("LLM_API_KEY") and llm.mode() != "replay":
        print("SKIPPED: no LLM provider configured and not in replay mode. LLM evals not run.")
        return 0
    if llm.mode() == "replay" and not any(llm.RECORDINGS.glob("*.json")):
        print("SKIPPED: replay mode but no recordings. Record a live run first. LLM evals not run.")
        return 0
    results = {"llm_eval_reason": reason(), "llm_eval_mapping": mapping()}
    for k, ms in results.items():
        print(k, {m.metric: round(m.value, 4) for m in ms})
    if "--record" in sys.argv:
        from medora import evals
        from medora.db import tx

        with tx() as conn:
            for k, ms in results.items():
                evals.record(conn, k, ms, summary={"labels": "draft", "replay": llm.mode() == "replay"})
    fails = [f"{k}.{m.metric}={m.value:.3f} < {m.bar}" for k, ms in results.items() for m in ms if not m.passed]
    for f in fails:
        print("GATE FAIL:", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
