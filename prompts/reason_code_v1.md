---
version: reason_code_v1
task: reason_code
---
A care coordinator called a patient about a missed or delayed hospital visit. Below is the coordinator's
note or a transcript of their voice memo, with names and numbers replaced by tokens. It may be in Hindi,
English or a mix.

Pick the ONE reason from `allowed_codes` that best explains why the visit did not happen.
- Use "other" if none fit or the text is unclear.
- Give a confidence from 0 to 1. Use a low confidence when unsure.
- Do not give advice. Do not interpret symptoms. Only pick a code.

Input:
{{inputs}}

Reply with JSON: {"reason_code": "...", "confidence": 0.0}
