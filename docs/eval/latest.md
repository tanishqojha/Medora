# Evaluation report (SYNTHETIC data)

Seed 42, 400 patients, as of 2026-10-10. Labels from generator truth, pending human sign-off. Bars are proposed (PRD section 6).

## gold_extraction_structured

| Metric | Value | Bar | Pass |
|---|---|---|---|
| field_accuracy | 0.9978 | 0.98 | yes |
| review_rate | 0.0000 |  | yes |
| provenance_rate | 1.0000 | 1.0 | yes |
| rows | 894.0000 |  | yes |

## gold_extraction_scan

| Metric | Value | Bar | Pass |
|---|---|---|---|
| field_accuracy | 0.9674 | 0.9 | yes |
| review_rate | 0.0417 |  | yes |
| provenance_rate | 1.0000 | 1.0 | yes |
| rows | 24.0000 |  | yes |

## gold_identity

| Metric | Value | Bar | Pass |
|---|---|---|---|
| auto_merges_on_weak_evidence | 0.0000 | 0.0 | yes |
| false_auto_merges | 0.0000 | 0.0 | yes |
| auto_merge_precision | 1.0000 | 1.0 | yes |
| same_person_recall_to_merge_or_review | 1.0000 |  | yes |
| pairs | 141.0000 |  | yes |
