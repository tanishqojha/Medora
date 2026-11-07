-- Medora base schema. PRD section 9. All ids UUID, all tables carry hospital_id.
-- events and audit_log are append-only: trigger + revoked grants (see 0002). Audit parts are two-key.

CREATE TABLE hospitals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid GENERATED ALWAYS AS (id) STORED,
  name text NOT NULL,
  synthetic boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE roles (
  name text PRIMARY KEY,
  label text NOT NULL
);
INSERT INTO roles VALUES
  ('coordinator', 'Care Coordinator'), ('clinical_lead', 'Clinical Lead'), ('nurse', 'Nurse'),
  ('admin', 'Hospital Admin'), ('data_steward', 'Data Steward');

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  email text NOT NULL,
  display_name text NOT NULL,
  role text NOT NULL REFERENCES roles(name),
  password_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (hospital_id, email)
);

CREATE TABLE patients (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  display_name text NOT NULL,
  sex text CHECK (sex IN ('F', 'M', 'O', 'U')),
  birth_year int,
  synthetic boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE patient_identifiers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  patient_id uuid NOT NULL REFERENCES patients(id),
  kind text NOT NULL CHECK (kind IN ('phone', 'hospital_number', 'name', 'name_latin', 'phonetic', 'exact_key')),
  value text NOT NULL,
  source_ref jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (patient_id, kind, value)
);
CREATE INDEX ON patient_identifiers (hospital_id, kind, value);

-- Merges are reversible: a merge row plus a reversal timestamp. Never rewrites patients or events.
CREATE TABLE patient_merges (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  from_patient uuid NOT NULL REFERENCES patients(id),
  into_patient uuid NOT NULL REFERENCES patients(id),
  outcome text NOT NULL CHECK (outcome IN ('auto_merge', 'review_merge')),
  score numeric NOT NULL,
  features jsonb NOT NULL,
  decided_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  reversed_at timestamptz,
  reversed_by text,
  CHECK (from_patient <> into_patient)
);
CREATE UNIQUE INDEX one_live_merge ON patient_merges (from_patient) WHERE reversed_at IS NULL;

CREATE TABLE source_files (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  filename text NOT NULL,
  kind text NOT NULL CHECK (kind IN ('csv', 'xlsx', 'pdf', 'image')),
  content_hash text NOT NULL,
  size_bytes bigint NOT NULL,
  storage_path text NOT NULL,
  uploaded_by text NOT NULL,
  synthetic boolean NOT NULL DEFAULT true,
  received_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON source_files (hospital_id, content_hash);

CREATE TABLE mappings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  fingerprint text NOT NULL,
  version int NOT NULL,
  headers jsonb NOT NULL,
  mapping jsonb NOT NULL,
  proposed_by text NOT NULL CHECK (proposed_by IN ('llm', 'human')),
  prompt_version text,
  llm_confidence numeric,
  date_convention text CHECK (date_convention IN ('dmy', 'mdy', 'ymd')),
  confirmed_by text,
  confirmed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (hospital_id, fingerprint, version),
  CHECK ((confirmed_by IS NULL) = (confirmed_at IS NULL))
);

CREATE TABLE ingest_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  source_file_id uuid NOT NULL REFERENCES source_files(id),
  state text NOT NULL DEFAULT 'queued'
    CHECK (state IN ('queued', 'needs_mapping', 'running', 'paused', 'killed', 'done', 'failed')),
  mapping_id uuid REFERENCES mappings(id),
  total_chunks int NOT NULL DEFAULT 0,
  done_chunks int NOT NULL DEFAULT 0,
  rows_total bigint NOT NULL DEFAULT 0,
  rows_loaded bigint NOT NULL DEFAULT 0,
  rows_skipped bigint NOT NULL DEFAULT 0,
  rows_review bigint NOT NULL DEFAULT 0,
  llm_calls int NOT NULL DEFAULT 0,
  fingerprint text,
  headers jsonb,
  profile jsonb,                 -- per-column shape and distinct labels from the planning pass
  error text,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ingest_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  job_id uuid NOT NULL REFERENCES ingest_jobs(id),
  seq int NOT NULL,
  row_start bigint NOT NULL,
  row_end bigint NOT NULL,
  content_hash text NOT NULL,
  state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'running', 'done', 'failed')),
  attempts int NOT NULL DEFAULT 0,
  worker text,
  started_at timestamptz,
  finished_at timestamptz,
  rows_loaded int NOT NULL DEFAULT 0,
  rows_skipped int NOT NULL DEFAULT 0,
  rows_review int NOT NULL DEFAULT 0,
  error text,
  UNIQUE (job_id, seq)
);
CREATE INDEX ON ingest_chunks (state, job_id);

CREATE TABLE events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  type text NOT NULL,
  patient_id uuid REFERENCES patients(id),
  occurred_at timestamptz NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  source_ref jsonb NOT NULL CHECK (jsonb_typeof(source_ref) = 'object' AND source_ref ? 'kind'),
  confidence numeric NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  supersedes_id uuid REFERENCES events(id),
  dedupe_key text NOT NULL,
  actor text NOT NULL,
  synthetic boolean NOT NULL DEFAULT true,
  UNIQUE (hospital_id, dedupe_key)
);
CREATE INDEX ON events (patient_id, occurred_at);
CREATE INDEX ON events (hospital_id, type);

CREATE TABLE pathways (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  key text NOT NULL,
  name text NOT NULL,
  UNIQUE (hospital_id, key)
);

CREATE TABLE pathway_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  pathway_id uuid NOT NULL REFERENCES pathways(id),
  version int NOT NULL,
  yaml text NOT NULL,
  spec jsonb NOT NULL,
  compiled_sql text NOT NULL,
  content_hash text NOT NULL,
  demo boolean NOT NULL DEFAULT false,
  signed_by text,
  signed_role text,
  signed_at timestamptz,
  active boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (pathway_id, version),
  -- F9: a version cannot be active without a clinician sign-off record.
  CONSTRAINT active_requires_signoff CHECK (
    NOT active OR (signed_by IS NOT NULL AND signed_at IS NOT NULL AND signed_role = 'clinical_lead'))
);
CREATE UNIQUE INDEX one_active_version ON pathway_versions (pathway_id) WHERE active;

-- Versions are immutable once written. Changing a threshold means a new version.
CREATE FUNCTION pathway_version_immutable() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
  IF NEW.yaml <> OLD.yaml OR NEW.spec <> OLD.spec OR NEW.compiled_sql <> OLD.compiled_sql
     OR NEW.version <> OLD.version OR NEW.content_hash <> OLD.content_hash THEN
    RAISE EXCEPTION 'pathway versions are immutable; create a new version';
  END IF;
  IF OLD.signed_by IS NOT NULL AND (NEW.signed_by IS DISTINCT FROM OLD.signed_by
                                    OR NEW.signed_at IS DISTINCT FROM OLD.signed_at) THEN
    RAISE EXCEPTION 'sign-off cannot be changed';
  END IF;
  RETURN NEW;
END $fn$;
CREATE TRIGGER pathway_version_immutable BEFORE UPDATE ON pathway_versions
  FOR EACH ROW EXECUTE FUNCTION pathway_version_immutable();

CREATE TABLE reason_codes (
  code text PRIMARY KEY,
  category text NOT NULL CHECK (category IN ('contact', 'closure')),
  label text NOT NULL,
  proposed boolean NOT NULL DEFAULT false
);
INSERT INTO reason_codes VALUES
  ('cost', 'contact', 'Cost', false), ('distance', 'contact', 'Distance', false),
  ('fear', 'contact', 'Fear', false), ('feeling_better', 'contact', 'Feeling better', false),
  ('wrong_number', 'contact', 'Wrong number', false), ('moved', 'contact', 'Moved', false),
  ('other', 'contact', 'Other', false),
  ('treated_elsewhere', 'closure', 'Seen at another hospital', true),
  ('patient_declined', 'closure', 'Patient declined', true),
  ('duplicate_record', 'closure', 'Duplicate record', true),
  ('data_error', 'closure', 'Data error in source file', true);

CREATE TABLE obligations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  pathway_version_id uuid NOT NULL REFERENCES pathway_versions(id),
  patient_id uuid NOT NULL REFERENCES patients(id),
  from_step text NOT NULL,
  expected_step text NOT NULL,
  from_event_id uuid NOT NULL REFERENCES events(id),
  due_by timestamptz NOT NULL,
  state text NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'closed_evidence', 'closed_reason')),
  closed_by_event uuid REFERENCES events(id),
  closure_reason_code text REFERENCES reason_codes(code),
  closed_by_user text,
  closed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (pathway_version_id, from_event_id, expected_step),
  -- F10: closes only on evidence, or a coded reason chosen by a person.
  CHECK (state <> 'closed_evidence' OR closed_by_event IS NOT NULL),
  CHECK (state <> 'closed_reason' OR (closure_reason_code IS NOT NULL AND closed_by_user IS NOT NULL))
);
CREATE INDEX ON obligations (hospital_id, state);

CREATE TABLE flags (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  obligation_id uuid NOT NULL REFERENCES obligations(id),
  patient_id uuid NOT NULL REFERENCES patients(id),
  pathway_version_id uuid NOT NULL REFERENCES pathway_versions(id),
  kind text NOT NULL CHECK (kind IN ('overdue', 'missed', 'unreachable')),
  rank_inputs jsonb NOT NULL,
  reason_line text NOT NULL,
  state text NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'resolved')),
  created_at timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz,
  UNIQUE (obligation_id)
);

CREATE TABLE flag_explanations (
  flag_id uuid PRIMARY KEY REFERENCES flags(id),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  rule_version text NOT NULL,
  source_event_ids uuid[] NOT NULL,
  steps jsonb NOT NULL,
  result_hash text NOT NULL,
  computed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE contact_attempts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  patient_id uuid NOT NULL REFERENCES patients(id),
  flag_id uuid REFERENCES flags(id),
  channel text NOT NULL DEFAULT 'call' CHECK (channel = 'call'),
  attempted_at timestamptz NOT NULL DEFAULT now(),
  by_user text NOT NULL
);

CREATE TABLE contact_outcomes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  attempt_id uuid NOT NULL REFERENCES contact_attempts(id),
  outcome text NOT NULL CHECK (outcome IN ('reached', 'no_answer', 'busy', 'wrong_number', 'callback')),
  reason_code text REFERENCES reason_codes(code),
  reason_confidence numeric,
  reason_source text CHECK (reason_source IN ('tap', 'note', 'voice')),
  transcript_ref text,
  routed_to_nurse boolean NOT NULL DEFAULT false,
  decided_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE review_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  type text NOT NULL CHECK (type IN ('extraction', 'identity', 'date', 'reason', 'mapping', 'row')),
  state text NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'decided', 'escalated')),
  payload jsonb NOT NULL,
  source_ref jsonb,
  confidence numeric,
  job_id uuid REFERENCES ingest_jobs(id),
  dedupe_key text,
  created_at timestamptz NOT NULL DEFAULT now(),
  due_at timestamptz,
  decided_by text,
  decision jsonb,
  decided_at timestamptz,
  UNIQUE (hospital_id, dedupe_key)
);
CREATE INDEX ON review_items (hospital_id, state, type);

CREATE TABLE nurse_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  patient_id uuid REFERENCES patients(id),
  source text NOT NULL CHECK (source IN ('note', 'transcript', 'message')),
  route text NOT NULL DEFAULT 'nurse' CHECK (route IN ('nurse', 'clinician')),
  excerpt text NOT NULL,
  matched jsonb NOT NULL,
  state text NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'handled')),
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  handled_by text,
  handled_at timestamptz,
  handled_note text
);

CREATE TABLE call_templates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  key text NOT NULL,
  version int NOT NULL,
  language text NOT NULL DEFAULT 'en',
  body text NOT NULL,
  slots text[] NOT NULL,
  proposed boolean NOT NULL DEFAULT true,
  signed_by text,
  signed_at timestamptz,
  UNIQUE (hospital_id, key, version, language)
);

CREATE TABLE consent (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  patient_id uuid NOT NULL REFERENCES patients(id),
  status text NOT NULL CHECK (status IN ('granted', 'refused', 'unknown')),
  source_ref jsonb NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE audit_log (
  seq bigserial PRIMARY KEY,
  id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
  hospital_id uuid NOT NULL REFERENCES hospitals(id),
  at timestamptz NOT NULL DEFAULT now(),
  actor text NOT NULL,
  action text NOT NULL,
  object_type text NOT NULL,
  object_id text NOT NULL,
  detail jsonb NOT NULL DEFAULT '{}'::jsonb,
  prev_hash text NOT NULL,
  entry_hash text NOT NULL UNIQUE
);
CREATE INDEX ON audit_log (hospital_id, seq);

CREATE TABLE eval_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid REFERENCES hospitals(id),
  kind text NOT NULL,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  git_sha text,
  synthetic boolean NOT NULL DEFAULT true,
  passed boolean,
  summary jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX ON eval_runs (kind, started_at DESC);

CREATE TABLE eval_results (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id uuid REFERENCES hospitals(id),
  run_id uuid NOT NULL REFERENCES eval_runs(id),
  metric text NOT NULL,
  value numeric NOT NULL,
  bar numeric,
  higher_is_better boolean NOT NULL DEFAULT true,
  passed boolean NOT NULL,
  detail jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- Append-only enforcement (F8, Rules 2.5).
CREATE FUNCTION reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
  RAISE EXCEPTION '% is append-only: % not allowed', TG_TABLE_NAME, TG_OP;
END $fn$;
CREATE TRIGGER events_append_only BEFORE UPDATE OR DELETE ON events
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER events_no_truncate BEFORE TRUNCATE ON events
  FOR EACH STATEMENT EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER audit_no_truncate BEFORE TRUNCATE ON audit_log
  FOR EACH STATEMENT EXECUTE FUNCTION reject_mutation();
