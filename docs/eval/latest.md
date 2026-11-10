# Evaluation report (SYNTHETIC data)

Seed 42, 400 patients, as of 2026-10-10. Labels from generator truth, pending human sign-off. Bars are proposed (PRD section 6).

## gold_extraction_structured (run abbd60a0-753b-4220-9e98-7e5dbecf0559)

| Metric | Value | Bar | Pass |
|---|---|---|---|
| field_accuracy | 0.9978 | 0.98 | yes |
| review_rate | 0.0000 |  | yes |
| provenance_rate | 1.0000 | 1.0 | yes |
| rows | 894.0000 |  | yes |

## gold_extraction_scan (run 8d66849f-0b3a-4e1d-a5b8-b14598601759)

| Metric | Value | Bar | Pass |
|---|---|---|---|
| field_accuracy | 0.9674 | 0.9 | yes |
| review_rate | 0.0417 |  | yes |
| provenance_rate | 1.0000 | 1.0 | yes |
| rows | 24.0000 |  | yes |

## gold_identity (run b297c3ad-bd17-4aef-bc7e-409e0a298cd0)

| Metric | Value | Bar | Pass |
|---|---|---|---|
| auto_merges_on_weak_evidence | 0.0000 | 0.0 | yes |
| false_auto_merges | 0.0000 | 0.0 | yes |
| auto_merge_precision | 1.0000 | 1.0 | yes |
| same_person_recall_to_merge_or_review | 1.0000 |  | yes |
| pairs | 141.0000 |  | yes |
