# PRD build check

Checked 2026-11-06 against [PRD.md](../PRD.md). Each row says where the feature lives and which check covers it.
"Test" means a pytest in `api/tests`. Numbers are not typed here: accuracy and speed come from `eval_runs`
(see `docs/eval/latest.md` and the Trust screen). Everything is synthetic data.

| ID | Feature | Where | Check | Status |
|---|---|---|---|---|
| F1 | File intake and job control | `api/medora/ingest.py`, `worker/worker.py`, Uploads screen | `test_same_shape_zero_llm_calls_and_kill_resume`, `test_parallel_chunks_do_not_duplicate_patients` | Done |
| F2 | Structured lane, streaming | `ingest.py`, `readers.py` | `test_vertical_slice`; `scripts/bench.py` (10k and 100k MVP rows) | Done. Benchmark numbers live in `eval_runs` |
| F3 | Compile-once mapping | `mapping.py`, Mapping Confirm screen | `test_same_shape_zero_llm_calls_and_kill_resume`, `test_mapping_sample_is_shape_only` | Done. Needs an LLM key to propose a new shape; without one a person writes the mapping |
| F4 | Messy lane (PDF, scans, photos) | `messy.py`, `prompts/vision_extract_v1.*` | `test_scanned_pdf_goes_through_ocr_with_crops`, `test_low_ocr_confidence_uses_vision_on_the_row_crop`, `test_vision_unavailable_keeps_ocr_values_for_review` | Done. Vision needs a provider key; fails closed to review |
| F5 | Whitelist and tokenisation | `whitelist.py`, `pii.py`, `llm.py`, `config/field_whitelist.yaml` | `test_rejects_non_whitelisted_key`, `test_rejects_raw_phone_and_known_name`, `test_tokenised_text_passes_and_payload_is_clean` | Done |
| F6 | Date parsing with ambiguity flags | `dates.py` | 10 tests in `test_dates.py`, including `test_ambiguous_never_silently_resolved` | Done |
| F7 | Identity resolution | `identity.py`, `reviews.py` | `test_same_batch_duplicates_link_one_way_and_stay_visible`; gold set in `eval/run_eval.py` reports weak-evidence auto-merges (bar 0) | Done. Proposed bars, not yet tuned on real data |
| F8 | Canonical timeline, append-only | `events.py`, migrations `0001`, `0003` | `test_events_reject_update_and_delete`, `test_correction_is_new_event_and_live_view_applies` | Done |
| F9 | Pathway-as-code and gap checks | `pathways.py`, `rules.py`, `pathways/*.yaml` | `test_unsigned_pathway_cannot_activate`, `test_only_clinical_lead_signs_and_versions_are_immutable`, `test_compile_snapshot` | Done. Thresholds are proposed until a clinician signs |
| F10 | Obligation ledger | `engine.py` | `test_obligation_close_needs_evidence_or_code`, `test_on_time_closes_by_evidence` | Done |
| F11 | Priority list with reason line | `ranking.py`, Stuck List screen | `test_order_and_deterministic_tiebreak`, `test_rejects_non_whitelisted_inputs`, `test_stuck_list_ranked_with_reasons_and_replay` | Done |
| F12 | Why-flagged replay | `engine.replay`, Patient Timeline screen | `test_stuck_list_ranked_with_reasons_and_replay`, `test_deterministic_hash` | Done |
| F13 | Call-assist | `callassist.py`, Call Card screen, `prompts/reason_code_v1.*` | `test_call_flow_tap_symptom_and_reason_review` | Done. Voice needs an ASR key; audio is deleted after transcription |
| F14 | Symptom tripwire | `tripwire.py`, Nurse Queue screen | `test_call_flow_tap_symptom_and_reason_review`, `test_every_case_routes_to_a_person` | Done. Keyword list is a draft pending the Clinical Lead |
| F15 | Safety harness in CI | `safety_harness/` | `test_every_case_routes_to_a_person`; runner reports 41 of 41 routed to a person | Done. Cases are drafts until a clinician approves |
| F16 | Trust screen | `evals.py`, Trust screen | `test_refusal_preview_and_trust` | Done. Every number links to its run |
| Tier SHOULD | Audit chain | `audit.py`, Audit Log screen | `test_audit_chain_verifies_and_detects_tamper`, `test_worker_verifies_each_chain_once_a_day` | Done |
| Tier COULD | Data-quality radar, visit bundler, FHIR export | `/api/jobs/{id}/quality`, `callassist.py`, `fhir.py` | `test_fhir_export_and_quality`, `test_bundle_hint_only_for_several_days_soon` | Done |
| LangGraph gates (S11) | Approval survives restart | `graphs.py` | `test_pending_gate_survives_restart`, `test_timeout_escalates_never_approves` | Done |

## Screens (PRD section 11)

All ten screens are built and wired. Details and departures from the Stitch mocks are in
[design/SCREEN_MAP.md](../design/SCREEN_MAP.md).

## Added this round, outside the PRD list

| Item | Where | Notes |
|---|---|---|
| Doctor panel | `web/app/doctor`, `web/components/HistoryPoint.tsx`, `FileReader.tsx`, `api/medora/history.py` | Reads a file and shows dated history points per patient. Schedule facts only: no reasons, no outcomes, no causes. Test: `test_history_orders_dates_and_leaves_out_causes`, `test_doctor_panel_history_points_have_no_causes` |
| Admin panel | `web/app/(app)/admin` | A hub over the existing screens, with live counts |
| Landing page | `web/app/welcome` | Plain description of the product |
| Pseudo data generator | `scripts/gen_pseudo.py` | Seeded, synthetic, labelled |

**Departure to review:** the Doctor panel and Admin panel are not in the PRD screen list and have no Stitch screen.
They were built from `design/DESIGN.md` tokens and existing components at the user's request, which Rules 7.4 would
otherwise treat as "stop and ask". Please generate them in Stitch or approve the build. The doctor role is the existing
`clinical_lead` role; no new role was added.

## Known gaps

- No real data, no real LLM or ASR run in this checkout. Those steps are tested with fakes and recordings, and fail closed.
- Gap thresholds, call scripts, the tripwire list and harness cases are proposed or draft. They need the Clinical Lead.
- Production scope stays unbuilt: WhatsApp and SMS, AWS or Docker deployment, 1M-row load tests, Langfuse, SSO.
- The Trust screen has no Stitch mock (the generation timed out). See SCREEN_MAP.md.
