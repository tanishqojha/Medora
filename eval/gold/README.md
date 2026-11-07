# Gold sets (SYNTHETIC)

Built by `api/medora/synth.py` with a fixed seed. Labels come from the generator's clean truth file,
never from the model under test (S15). A person must spot-check and sign off before the numbers are
quoted outside the team.

| Gold set | Source | Signed off by |
|---|---|---|
| Extraction, structured | `truth.jsonl` rows vs `register_mapping.json` | pending |
| Extraction, photo/scan | `photos_truth.jsonl` vs OCR of rendered register photos | pending |
| Identity pairs | same-person vs different-person pairs from `truth.jsonl` | pending |

`register_mapping.json` is the mapping a data steward confirms for the synthetic register shape.
