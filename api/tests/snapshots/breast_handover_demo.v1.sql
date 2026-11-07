-- compiled from breast_handover_demo v1. Do not edit; recompile from YAML.
SELECT * FROM (
  SELECT 'surgery_done'::text AS from_step, 'oncology_booked'::text AS expected_step,
         f.id AS from_event_id, f.canonical_id AS patient_id, f.effective_at AS from_at,
         f.effective_at + make_interval(days => 14) AS due_by,
         f.effective_at + make_interval(days => 14) AS flag_after,
         (SELECT t.id FROM live_events t
           WHERE t.hospital_id = f.hospital_id AND t.canonical_id = f.canonical_id
             AND t.type = 'appointment_booked' AND t.id <> f.id
             AND t.effective_at >= f.effective_at AND t.effective_at <= %(as_of)s
           ORDER BY t.effective_at, t.id LIMIT 1) AS evidence_event_id
  FROM live_events f
  WHERE f.hospital_id = %(hospital_id)s AND f.type = 'surgery_recorded' AND f.effective_at <= %(as_of)s
    AND (%(patients)s::uuid[] IS NULL OR f.canonical_id = ANY(%(patients)s::uuid[]))
UNION ALL
  SELECT 'oncology_booked'::text AS from_step, 'oncology_attended'::text AS expected_step,
         f.id AS from_event_id, f.canonical_id AS patient_id, f.effective_at AS from_at,
         f.effective_at + make_interval(days => 14) AS due_by,
         f.effective_at + make_interval(days => 14) AS flag_after,
         (SELECT t.id FROM live_events t
           WHERE t.hospital_id = f.hospital_id AND t.canonical_id = f.canonical_id
             AND t.type = 'appointment_attended' AND t.id <> f.id
             AND t.effective_at >= f.effective_at AND t.effective_at <= %(as_of)s
           ORDER BY t.effective_at, t.id LIMIT 1) AS evidence_event_id
  FROM live_events f
  WHERE f.hospital_id = %(hospital_id)s AND f.type = 'appointment_booked' AND f.effective_at <= %(as_of)s
    AND (%(patients)s::uuid[] IS NULL OR f.canonical_id = ANY(%(patients)s::uuid[]))
) gaps ORDER BY patient_id, from_at, from_event_id, expected_step