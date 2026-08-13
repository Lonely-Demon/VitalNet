-- CI-only functional RLS regression check for the vulnerability fixed in
-- phase32_fix_jwt_metadata_rls_vulnerability.sql (docs/DECISIONS.md §36).
--
-- Everything before this file in the db-schema-drift job only proves
-- tracked SQL applies without error — it says nothing about whether the
-- resulting policies actually restrict access, since the job's own
-- connection runs as the postgres superuser, and RLS does not apply to
-- superusers or table owners regardless of what any policy says. This
-- file is the difference: it seeds minimal data, then SET ROLE
-- authenticated + simulates real PostgREST-style JWT claims (the same
-- technique used to verify the phase32 fix locally, documented in
-- docs/DECISIONS.md §36) to prove, on every PR, that a user who sets
-- user_metadata.role = 'admin' on themselves via Supabase's own Auth API
-- — without a matching row in public.profiles — still sees nothing. A
-- future migration that reintroduces this pattern, or otherwise breaks
-- profiles_select_policy_hardened / case_records access, fails this file
-- loudly instead of shipping unnoticed.
\set ON_ERROR_STOP on

BEGIN;

INSERT INTO public.facilities (id, name, type, district, state)
VALUES ('00000000-0000-0000-0000-0000000000f2', 'CI PHC B', 'PHC', 'Test District B', 'Test State');

INSERT INTO auth.users (id) VALUES ('00000000-0000-0000-0000-000000000a02');
INSERT INTO auth.users (id) VALUES ('00000000-0000-0000-0000-000000000s01');

-- Admin 1 assigned to PHC A
INSERT INTO public.profiles (id, full_name, role, facility_id, is_active)
VALUES ('00000000-0000-0000-0000-000000000a01', 'CI Admin PHC A', 'admin', '00000000-0000-0000-0000-0000000000f1', true)
ON CONFLICT (id) DO UPDATE SET facility_id = '00000000-0000-0000-0000-0000000000f1';

-- Admin 2 assigned to PHC B
INSERT INTO public.profiles (id, full_name, role, facility_id, is_active)
VALUES ('00000000-0000-0000-0000-000000000a02', 'CI Admin PHC B', 'admin', '00000000-0000-0000-0000-0000000000f2', true);

-- Supervisor with no facility_id
INSERT INTO public.profiles (id, full_name, role, facility_id, is_active)
VALUES ('00000000-0000-0000-0000-000000000s01', 'CI Supervisor', 'supervisor', NULL, true);

INSERT INTO public.protocol_questions (
  id, asked_by, facility_id, question_text, status
) VALUES (
  '00000000-0000-0000-0000-00000000pq01', '00000000-0000-0000-0000-000000000a01',
  '00000000-0000-0000-0000-0000000000f1', 'What is the dosage for paracetamol in children?', 'pending_curation'
), (
  '00000000-0000-0000-0000-00000000pq02', '00000000-0000-0000-0000-000000000a02',
  '00000000-0000-0000-0000-0000000000f2', 'How to manage severe hypertension in pregnancy?', 'pending_curation'
);

COMMIT;

-- Attacker: no row in public.profiles at all, but sets
-- user_metadata.role = 'admin' on their own JWT the way any authenticated
-- user legitimately can via Supabase's Auth API.
SET ROLE authenticated;
SELECT set_config(
  'request.jwt.claims',
  '{"sub":"00000000-0000-0000-0000-00000000eeee","role":"authenticated","user_metadata":{"role":"admin"}}',
  false
);

DO $$
DECLARE
  visible_cases int;
  visible_profiles int;
  visible_protocols int;
BEGIN
  SELECT count(*) INTO visible_cases FROM public.case_records;
  SELECT count(*) INTO visible_profiles FROM public.profiles;
  SELECT count(*) INTO visible_protocols FROM public.protocol_questions;
  IF visible_cases <> 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION: a user_metadata-only "admin" (no public.profiles row) can see % case_records — phase32''s fix is not effective', visible_cases;
  END IF;
  IF visible_profiles <> 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION: a user_metadata-only "admin" (no public.profiles row) can see % profiles — phase32''s fix is not effective', visible_profiles;
  END IF;
  IF visible_protocols <> 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION: a user_metadata-only "admin" (no public.profiles row) can see % protocol_questions', visible_protocols;
  END IF;
END
$$;

RESET ROLE;

-- PHC Admin A: should see ONLY protocol questions for PHC A (1 row, not 2).
SET ROLE authenticated;
SELECT set_config(
  'request.jwt.claims',
  '{"sub":"00000000-0000-0000-0000-000000000a01","role":"authenticated"}',
  false
);

DO $$
DECLARE
  visible_cases int;
  visible_profiles int;
  visible_protocols int;
BEGIN
  SELECT count(*) INTO visible_cases FROM public.case_records;
  SELECT count(*) INTO visible_profiles FROM public.profiles;
  SELECT count(*) INTO visible_protocols FROM public.protocol_questions;
  IF visible_cases = 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION: a real admin (public.profiles row with role=admin) sees 0 case_records';
  END IF;
  IF visible_profiles = 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION: a real admin (public.profiles row with role=admin) sees 0 profiles';
  END IF;
  IF visible_protocols <> 1 THEN
    RAISE EXCEPTION 'RLS REGRESSION: PHC Admin A sees % protocol_questions instead of 1 (cross-PHC leak!)', visible_protocols;
  END IF;
END
$$;

RESET ROLE;

-- Supervisor (no facility_id): should see ALL protocol questions (2 rows).
SET ROLE authenticated;
SELECT set_config(
  'request.jwt.claims',
  '{"sub":"00000000-0000-0000-0000-00000000s01","role":"authenticated"}',
  false
);

DO $$
DECLARE
  visible_protocols int;
BEGIN
  SELECT count(*) INTO visible_protocols FROM public.protocol_questions;
  IF visible_protocols <> 2 THEN
    RAISE EXCEPTION 'RLS REGRESSION: Supervisor (no facility_id) sees % protocol_questions instead of 2', visible_protocols;
  END IF;
END
$$;

RESET ROLE;

SELECT 'RLS regression check passed: JWT-metadata privilege escalation stays closed, PHC Admin protocol questions scoped locally, Supervisor global curation open.' AS result;

