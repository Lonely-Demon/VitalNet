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
VALUES ('00000000-0000-0000-0000-0000000000f1', 'CI Test PHC', 'PHC', 'Test District', 'Test State');

-- profiles.id has a FOREIGN KEY to auth.users(id) on the real project;
-- ci_stubs.sql's auth.users stub carries that same constraint shape.
INSERT INTO auth.users (id) VALUES ('00000000-0000-0000-0000-000000000a01');

INSERT INTO public.profiles (id, full_name, role, facility_id, is_active)
VALUES ('00000000-0000-0000-0000-000000000a01', 'CI Real Admin', 'admin', NULL, true);

INSERT INTO public.case_records (
  id, client_id, submitted_by, facility_id, patient_age, patient_sex,
  chief_complaint, symptoms, triage_level
) VALUES (
  '00000000-0000-0000-0000-00000000ca01', '00000000-0000-0000-0000-00000000cc01',
  '00000000-0000-0000-0000-000000000a01', '00000000-0000-0000-0000-0000000000f1',
  30, 'female', 'fever', ARRAY['fever'], 'ROUTINE'
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
BEGIN
  SELECT count(*) INTO visible_cases FROM public.case_records;
  SELECT count(*) INTO visible_profiles FROM public.profiles;
  IF visible_cases <> 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION: a user_metadata-only "admin" (no public.profiles row) can see % case_records — phase32''s fix is not effective', visible_cases;
  END IF;
  IF visible_profiles <> 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION: a user_metadata-only "admin" (no public.profiles row) can see % profiles — phase32''s fix is not effective', visible_profiles;
  END IF;
END
$$;

RESET ROLE;

-- Real admin: has an actual row in public.profiles with role = 'admin'.
-- Legitimate access must still work — a check that only ever proves "no
-- one can see anything" would pass on a policy that's broken the other
-- way (denies everyone, including people who should have access).
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
BEGIN
  SELECT count(*) INTO visible_cases FROM public.case_records;
  SELECT count(*) INTO visible_profiles FROM public.profiles;
  IF visible_cases = 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION: a real admin (public.profiles row with role=admin) sees 0 case_records — profiles_select_policy_hardened or the case_records policies are over-restrictive';
  END IF;
  IF visible_profiles = 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION: a real admin (public.profiles row with role=admin) sees 0 profiles — profiles_select_policy_hardened is over-restrictive';
  END IF;
END
$$;

RESET ROLE;

SELECT 'RLS regression check passed: JWT-metadata privilege escalation stays closed, legitimate admin access stays open.' AS result;
