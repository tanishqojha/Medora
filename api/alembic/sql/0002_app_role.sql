-- App role with limited grants. The app never connects as the superuser (Rules 8.7).
-- :app_password is substituted by the migration from MEDORA_APP_PASSWORD.
DO $do$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'medora_app') THEN
    CREATE ROLE medora_app LOGIN;
  END IF;
END $do$;
ALTER ROLE medora_app WITH LOGIN PASSWORD :app_password;

GRANT USAGE ON SCHEMA public TO medora_app;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO medora_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO medora_app;

-- Mutable workflow tables. events and audit_log are NOT in this list: insert and select only.
GRANT UPDATE ON hospitals, users, patients, source_files, mappings, ingest_jobs, ingest_chunks,
  pathway_versions, obligations, flags, flag_explanations, review_items, nurse_items,
  patient_merges, call_templates, eval_runs, contact_outcomes, pathways TO medora_app;
GRANT DELETE ON ingest_chunks TO medora_app;

REVOKE UPDATE, DELETE, TRUNCATE ON events, audit_log FROM medora_app;
REVOKE UPDATE, DELETE, TRUNCATE ON events, audit_log FROM PUBLIC;

-- Supabase Data API safety: RLS on everywhere. Only medora_app gets a policy, so anon and
-- authenticated (the Data API roles) see nothing even if the Data API stays on.
DO $do$
DECLARE t text;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version' LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS medora_app_all ON public.%I', t);
    EXECUTE format('CREATE POLICY medora_app_all ON public.%I TO medora_app USING (true) WITH CHECK (true)', t);
  END LOOP;
END $do$;
