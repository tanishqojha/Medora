-- Canonical patient after live (unreversed) merges, and events with corrections applied.
CREATE INDEX IF NOT EXISTS events_supersedes_idx ON events (supersedes_id) WHERE supersedes_id IS NOT NULL;

CREATE VIEW patient_canonical WITH (security_invoker = true) AS
WITH RECURSIVE m AS (
  SELECT p.id AS patient_id, p.id AS canonical_id, 0 AS depth
  FROM patients p
  WHERE NOT EXISTS (SELECT 1 FROM patient_merges pm WHERE pm.from_patient = p.id AND pm.reversed_at IS NULL)
  UNION ALL
  SELECT pm.from_patient, m.canonical_id, m.depth + 1
  FROM patient_merges pm JOIN m ON pm.into_patient = m.patient_id
  WHERE pm.reversed_at IS NULL AND m.depth < 20
)
SELECT patient_id, canonical_id FROM m;

-- A correction with corrected_field 'void' removes an event from the live view.
-- A correction with corrected_field 'occurred_at' moves it. The original row never changes.
CREATE VIEW live_events WITH (security_invoker = true) AS
SELECT e.*, c.canonical_id,
       COALESCE((SELECT (x.payload->>'corrected_value')::timestamptz FROM events x
                 WHERE x.supersedes_id = e.id AND x.type = 'correction'
                   AND x.payload->>'corrected_field' = 'occurred_at'
                 ORDER BY x.recorded_at DESC LIMIT 1), e.occurred_at) AS effective_at
FROM events e
JOIN patient_canonical c ON c.patient_id = e.patient_id
WHERE e.type <> 'correction'
  AND NOT EXISTS (SELECT 1 FROM events v WHERE v.supersedes_id = e.id AND v.type = 'correction'
                    AND v.payload->>'corrected_field' = 'void');

GRANT SELECT ON patient_canonical, live_events TO medora_app;
