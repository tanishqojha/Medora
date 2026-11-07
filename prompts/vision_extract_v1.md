---
version: vision_extract_v1
task: vision_extract
---
The image is a crop of one row from a handwritten or printed hospital register.
Read ONLY the fields listed in `fields`. Copy what is written. Do not guess missing values.

Rules:
- If a field is not visible or not readable, return null for its value and confidence 0.
- Dates: copy exactly as written (for example "03/04/26"). Do not reorder day and month.
- Confidence from 0 to 1 per field.
- Ignore anything about diagnosis, results or treatment.

Input:
{{inputs}}

Reply with JSON: {"fields": [{"name": "...", "value": "..." or null, "confidence": 0.0}]}
