"""Gold-set evaluation (S16). Everything is SYNTHETIC. Labels come from the generator truth, not from a model.

Usage (from repo root):
  uv run --project api python eval/run_eval.py               # run, print, gate against bars and baseline
  uv run --project api python eval/run_eval.py --record      # also write eval_runs (needs DATABASE_URL)
  uv run --project api python eval/run_eval.py --write-baseline
Exit 1 if a metric misses its bar or drops more than the tolerance below eval/baseline.json.
"""
from __future__ import annotations

import itertools
import json
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from medora import identity, mapping, messy, synth
from medora.config import setting
from medora.dates import parse
from medora.evals import Metric

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "eval" / "gold"
BASELINE = ROOT / "eval" / "baseline.json"
SEED, N, AS_OF = 42, 400, date(2026, 10, 10)
MAPPING = json.loads((GOLD / "register_mapping.json").read_text(encoding="utf-8"))


def structured(rows: list[dict[str, Any]]) -> list[Metric]:
    compared = correct = review = with_prov = 0
    per_field: dict[str, list[int]] = {}
    for r in rows:
        ap = mapping.apply_row(MAPPING, {h: r[h] for h in synth.HEADERS})
        if ap.problems:
            review += 1
            continue
        with_prov += all(f in ap.cells for f in ap.fields)
        expected = {"event_type": r["truth_event_type"], "event_date": r["truth_date"],
                    "hospital_number": r["UHID"].upper()}
        got = {"event_type": ap.event_type, "event_date": ap.occurred.value.isoformat() if ap.occurred.value else None,
               "hospital_number": identity.Record(hospital_number=ap.fields.get("hospital_number")).hospital_number}
        if "wrong_phone" not in r["corruptions"]:
            expected["phone"] = identity.normalise_phone(r["truth_phone"])
            got["phone"] = identity.normalise_phone(ap.fields.get("phone"))
        for k, v in expected.items():
            ok = int(got[k] == v)
            per_field.setdefault(k, [0, 0])
            per_field[k][0] += ok
            per_field[k][1] += 1
            compared += 1
            correct += ok
    accepted = len(rows) - review
    return [Metric("field_accuracy", correct / max(compared, 1), 0.98,
                   detail={k: round(a / b, 4) for k, (a, b) in per_field.items()}),
            Metric("review_rate", review / len(rows), None, higher_is_better=False),
            Metric("provenance_rate", with_prov / max(accepted, 1), 1.0),
            Metric("rows", float(len(rows)))]


PHOTO_FIELDS = {"Patient Name": "patient_name", "Mobile No": "phone", "UHID": "hospital_number", "Date": "event_date"}


def scan(ds_dir: Path) -> list[Metric]:
    truth: dict[str, list[dict[str, Any]]] = {}
    for line in (ds_dir / "photos_truth.jsonl").read_text(encoding="utf-8").splitlines():
        t = json.loads(line)
        truth.setdefault(t["photo"], []).append(t)
    min_conf = float(setting("messy.field_min_confidence"))
    compared = correct = review = total = with_prov = 0
    for photo, expected_rows in sorted(truth.items()):
        it = messy.reader(ds_dir / photo, "image")
        headers = next(it)
        got_rows = [dict(zip(headers, vals, strict=False)) for _, vals in it]
        by_uhid = {str((g.get("hospital_number") or {}).get("v") or "").replace(" ", "").upper(): g for g in got_rows}
        for i, exp in enumerate(expected_rows):
            total += 1
            g = by_uhid.get(exp["UHID"]) or (got_rows[i] if i < len(got_rows) else None)
            if g is None or min((c.get("c") or 0) for c in g.values()) < min_conf:
                review += 1
                continue
            with_prov += all(c.get("ref") for c in g.values())
            for col, f in PHOTO_FIELDS.items():
                v = (g.get(f) or {}).get("v")
                if f == "patient_name":
                    ok = identity.normalise_name(v) == identity.normalise_name(exp[col])
                elif f == "phone":
                    ok = identity.normalise_phone(v) == identity.normalise_phone(exp[col])
                elif f == "event_date":
                    ok = parse(v, "dmy").value == date.fromisoformat(exp["truth_date"])
                else:
                    ok = str(v or "").replace(" ", "").upper() == exp[col]
                compared += 1
                correct += int(ok)
    return [Metric("field_accuracy", correct / max(compared, 1), 0.90),
            Metric("review_rate", review / max(total, 1), None, higher_is_better=False),
            Metric("provenance_rate", with_prov / max(total - review, 1), 1.0),
            Metric("rows", float(total))]


def identity_pairs(rows: list[dict[str, Any]]) -> list[Metric]:
    recs: dict[str, tuple[str, identity.Record]] = {}
    for r in rows:
        rec = identity.Record(name=r["Patient Name"], phone=r["Mobile No"], hospital_number=r["UHID"], sex=r["Sex"],
                              birth_year=int(r["truth_date"][:4]) - int(r["Age"]))
        recs.setdefault(rec.exact_key(), (r["truth_patient"], rec))
    blocks: dict[str, list[str]] = {}
    for k, (_, rec) in recs.items():
        for key in filter(None, [rec.phone and "p:" + rec.phone, rec.phonetic and "n:" + rec.phonetic,
                                 rec.hospital_number and "h:" + rec.hospital_number]):
            blocks.setdefault(key, []).append(k)
    pairs = {tuple(sorted(p)) for ks in blocks.values() for p in itertools.combinations(ks, 2)}
    tp = fp = same = found = weak = 0
    for a, b in sorted(pairs):
        (ta, ra), (tb, rb) = recs[a], recs[b]
        m = identity.score(ra, rb)
        is_same = ta == tb
        same += is_same
        if m.outcome == "auto_merge":
            tp += is_same
            fp += not is_same
            f = m.features
            weak += not (f["phone_match"] and f["name_match"] and (f["hospital_number_match"] or f["birth_year_match"]))
        if is_same and m.outcome in ("auto_merge", "review"):
            found += 1
    return [Metric("auto_merges_on_weak_evidence", float(weak), 0.0, higher_is_better=False),
            Metric("false_auto_merges", float(fp), 0.0, higher_is_better=False),
            Metric("auto_merge_precision", tp / max(tp + fp, 1), 1.0),
            Metric("same_person_recall_to_merge_or_review", found / max(same, 1)),
            Metric("pairs", float(len(pairs)))]


def run_all() -> dict[str, list[Metric]]:
    out_dir = Path(tempfile.mkdtemp(prefix="medora_gold_"))
    ds = synth.build(out_dir, n_patients=N, seed=SEED, as_of=AS_OF, photos=3)
    pats = {p.pid: p for p in ds.patients}
    for r in ds.rows:
        r["truth_phone"] = pats[r["truth_patient"]].phone
    return {"gold_extraction_structured": structured(ds.rows), "gold_extraction_scan": scan(out_dir),
            "gold_identity": identity_pairs(ds.rows)}


def gate(results: dict[str, list[Metric]]) -> list[str]:
    tol = float(setting("eval.tolerance"))
    base = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    problems = []
    for kind, metrics in results.items():
        for m in metrics:
            if not m.passed:
                problems.append(f"{kind}.{m.metric} = {m.value:.4f} misses bar {m.bar}")
            b = base.get(kind, {}).get(m.metric)
            if b is not None and m.bar is not None:
                drop = (b - m.value) if m.higher_is_better else (m.value - b)
                if drop > tol:
                    problems.append(f"{kind}.{m.metric} dropped {drop:.4f} from baseline {b:.4f}")
    return problems


def render(results: dict[str, list[Metric]], run_ids: dict[str, str]) -> str:
    lines = ["# Evaluation report (SYNTHETIC data)", "", f"Seed {SEED}, {N} patients, as of {AS_OF}. "
             "Labels from generator truth, pending human sign-off. Bars are proposed (PRD section 6).", ""]
    for kind, metrics in results.items():
        lines += [f"## {kind}" + (f" (run {run_ids[kind]})" if kind in run_ids else ""), "",
                  "| Metric | Value | Bar | Pass |", "|---|---|---|---|"]
        lines += [f"| {m.metric} | {m.value:.4f} | {'' if m.bar is None else m.bar} | {'yes' if m.passed else 'no'} |"
                  for m in metrics]
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    results = run_all()
    run_ids: dict[str, str] = {}
    if "--record" in sys.argv:
        from medora import evals
        from medora.db import tx

        with tx() as conn:
            for kind, metrics in results.items():
                run_ids[kind] = evals.record(conn, kind, metrics, summary={"seed": SEED, "patients": N, "gold_signed_off": False})
    if "--write-baseline" in sys.argv:
        BASELINE.write_text(json.dumps({k: {m.metric: round(m.value, 6) for m in ms} for k, ms in results.items()},
                                       indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = render(results, run_ids)
    (ROOT / "docs" / "eval").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs" / "eval" / "latest.md").write_text(report, encoding="utf-8")
    print(report)
    problems = gate(results)
    for p in problems:
        print("GATE FAIL:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
