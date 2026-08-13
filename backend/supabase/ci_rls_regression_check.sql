-- CI-only functional RLS & Security Definer regression check.
-- Covers three concerns:
--
-- 1. JWT-metadata privilege escalation (phase32 fix, docs/DECISIONS.md §36):
--    A user who sets user_metadata.role = 'admin' via Supabase's Auth API,
--    without a matching public.profiles row, still sees nothing.
--
-- 2. Protocol Assistant RLS governance (phase39):
--    PHC Administrator is scoped to own facility only (SELECT and UPDATE);
--    Supervisor has global read/curation access even without a facility_id.
--
-- 3. Supervisor Global Aggregate-Scope Governance (phase40):
--    fn_team_metrics & fn_outbreak_signal_counts:
--    Supervisor is global by default (p_facility_id = NULL), no facility_id needed.
--    Supervisor can optionally narrow by passing p_facility_id.
--    PHC Admin is strictly pinned to own facility (passing another PHC is overwritten).
--    Doctor is pinned to own facility for fn_outbreak_signal_counts; denied fn_team_metrics.
--    ASHA Worker is denied execution for both aggregate functions.
--    Supervisor has 0 direct case_records row access (clinical-data boundary).
--
-- Technique: seed minimal data, SET ROLE authenticated, simulate real
-- PostgREST-style JWT claims, assert row counts and function execution outcomes.
-- Superuser does NOT trigger RLS or security checks — only SET ROLE authenticated does.
\set ON_ERROR_STOP on

-- ── UUID legend ────────────────────────────────────────────────────────────
-- 00000000-0000-0000-0000-0000000000f1   CI Test PHC A
-- 00000000-0000-0000-0000-0000000000f2   CI Test PHC B
-- 00000000-0000-0000-0000-000000000a01   CI Admin PHC A
-- 00000000-0000-0000-0000-000000000a02   CI Admin PHC B
-- 00000000-0000-0000-0000-000000000b01   CI Supervisor (no facility_id)
-- 00000000-0000-0000-0000-000000000d01   CI Doctor PHC A
-- 00000000-0000-0000-0000-000000000e01   CI ASHA Worker PHC A
-- 00000000-0000-0000-0000-00000000eeee   Attacker (no profiles row)
-- 00000000-0000-0000-0000-00000000ca01   CI case_record (PHC A)
-- 00000000-0000-0000-0000-00000000ca02   CI case_record (PHC B)
-- 00000000-0000-0000-0000-00000000c001   CI protocol_question (PHC A)
-- 00000000-0000-0000-0000-00000000c002   CI protocol_question (PHC B)
-- ──────────────────────────────────────────────────────────────────────────

BEGIN;

INSERT INTO public.facilities (id, name, type, district, state)
VALUES
  ('00000000-0000-0000-0000-0000000000f1', 'CI PHC A', 'PHC', 'Test District A', 'Test State'),
  ('00000000-0000-0000-0000-0000000000f2', 'CI PHC B', 'PHC', 'Test District B', 'Test State')
ON CONFLICT (id) DO NOTHING;

INSERT INTO auth.users (id)
VALUES
  ('00000000-0000-0000-0000-000000000a01'),
  ('00000000-0000-0000-0000-000000000a02'),
  ('00000000-0000-0000-0000-000000000b01'),
  ('00000000-0000-0000-0000-000000000d01'),
  ('00000000-0000-0000-0000-000000000e01')
ON CONFLICT (id) DO NOTHING;

-- Admin A → PHC A
INSERT INTO public.profiles (id, full_name, role, facility_id, is_active)
VALUES ('00000000-0000-0000-0000-000000000a01', 'CI Admin PHC A', 'admin', '00000000-0000-0000-0000-0000000000f1', true)
ON CONFLICT (id) DO UPDATE SET facility_id = EXCLUDED.facility_id, role = EXCLUDED.role, is_active = EXCLUDED.is_active;

-- Admin B → PHC B
INSERT INTO public.profiles (id, full_name, role, facility_id, is_active)
VALUES ('00000000-0000-0000-0000-000000000a02', 'CI Admin PHC B', 'admin', '00000000-0000-0000-0000-0000000000f2', true)
ON CONFLICT (id) DO NOTHING;

-- Supervisor → no facility_id (organisation-wide governance model)
INSERT INTO public.profiles (id, full_name, role, facility_id, is_active)
VALUES ('00000000-0000-0000-0000-000000000b01', 'CI Supervisor', 'supervisor', NULL, true)
ON CONFLICT (id) DO NOTHING;

-- Doctor A → PHC A
INSERT INTO public.profiles (id, full_name, role, facility_id, is_active)
VALUES ('00000000-0000-0000-0000-000000000d01', 'CI Doctor PHC A', 'doctor', '00000000-0000-0000-0000-0000000000f1', true)
ON CONFLICT (id) DO NOTHING;

-- ASHA Worker A → PHC A
INSERT INTO public.profiles (id, full_name, role, facility_id, is_active)
VALUES ('00000000-0000-0000-0000-000000000e01', 'CI ASHA PHC A', 'asha_worker', '00000000-0000-0000-0000-0000000000f1', true)
ON CONFLICT (id) DO NOTHING;

-- Case record for PHC A
INSERT INTO public.case_records (
  id, client_id, submitted_by, facility_id, patient_age, patient_sex,
  chief_complaint, symptoms, triage_level, created_at
) VALUES (
  '00000000-0000-0000-0000-00000000ca01',
  '00000000-0000-0000-0000-00000000cc01',
  '00000000-0000-0000-0000-000000000e01',
  '00000000-0000-0000-0000-0000000000f1',
  30, 'female', 'fever', ARRAY['fever'], 'ROUTINE', now()
) ON CONFLICT (id) DO NOTHING;

-- Case record for PHC B
INSERT INTO public.case_records (
  id, client_id, submitted_by, facility_id, patient_age, patient_sex,
  chief_complaint, symptoms, triage_level, created_at
) VALUES (
  '00000000-0000-0000-0000-00000000ca02',
  '00000000-0000-0000-0000-00000000cc02',
  '00000000-0000-0000-0000-000000000a02',
  '00000000-0000-0000-0000-0000000000f2',
  45, 'male', 'breathlessness', ARRAY['breathlessness'], 'EMERGENCY', now()
) ON CONFLICT (id) DO NOTHING;

-- Protocol question for PHC A (c001)
INSERT INTO public.protocol_questions (
  id, asked_by, facility_id, question_text, status
) VALUES (
  '00000000-0000-0000-0000-00000000c001',
  '00000000-0000-0000-0000-000000000a01',
  '00000000-0000-0000-0000-0000000000f1',
  'What is the dosage for paracetamol in children?',
  'pending_curation'
) ON CONFLICT (id) DO NOTHING;

-- Protocol question for PHC B (c002)
INSERT INTO public.protocol_questions (
  id, asked_by, facility_id, question_text, status
) VALUES (
  '00000000-0000-0000-0000-00000000c002',
  '00000000-0000-0000-0000-000000000a02',
  '00000000-0000-0000-0000-0000000000f2',
  'How to manage severe hypertension in pregnancy?',
  'pending_curation'
) ON CONFLICT (id) DO NOTHING;

COMMIT;

-- ══════════════════════════════════════════════════════════════════════════
-- CHECK 1 — JWT-metadata attacker (no profiles row)
-- Expects: 0 case_records, 0 profiles, 0 protocol_questions visible.
-- ══════════════════════════════════════════════════════════════════════════
SET ROLE authenticated;
SELECT set_config(
  'request.jwt.claims',
  '{"sub":"00000000-0000-0000-0000-00000000eeee","role":"authenticated","user_metadata":{"role":"admin"}}',
  false
);

DO $$
DECLARE
  visible_cases    int;
  visible_profiles int;
  visible_protocols int;
BEGIN
  SELECT count(*) INTO visible_cases    FROM public.case_records;
  SELECT count(*) INTO visible_profiles FROM public.profiles;
  SELECT count(*) INTO visible_protocols FROM public.protocol_questions;
  IF visible_cases <> 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 1): user_metadata-only admin sees % case_records', visible_cases;
  END IF;
  IF visible_profiles <> 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 1): user_metadata-only admin sees % profiles', visible_profiles;
  END IF;
  IF visible_protocols <> 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 1): user_metadata-only admin sees % protocol_questions', visible_protocols;
  END IF;
END
$$;

RESET ROLE;

-- ══════════════════════════════════════════════════════════════════════════
-- CHECK 2 — PHC Admin A SELECT scope
-- Expects: sees own case_records and profiles; sees exactly 1
-- protocol_question (PHC A only — cross-PHC SELECT must be denied).
-- ══════════════════════════════════════════════════════════════════════════
SET ROLE authenticated;
SELECT set_config(
  'request.jwt.claims',
  '{"sub":"00000000-0000-0000-0000-000000000a01","role":"authenticated"}',
  false
);

DO $$
DECLARE
  visible_cases    int;
  visible_profiles int;
  visible_protocols int;
BEGIN
  SELECT count(*) INTO visible_cases    FROM public.case_records;
  SELECT count(*) INTO visible_profiles FROM public.profiles;
  SELECT count(*) INTO visible_protocols FROM public.protocol_questions;
  IF visible_cases = 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 2): PHC Admin A sees 0 case_records';
  END IF;
  IF visible_profiles = 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 2): PHC Admin A sees 0 profiles';
  END IF;
  IF visible_protocols <> 1 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 2): PHC Admin A sees % protocol_questions (expected 1)', visible_protocols;
  END IF;
END
$$;

RESET ROLE;

-- ══════════════════════════════════════════════════════════════════════════
-- CHECK 3 — PHC Admin A UPDATE scope (curation)
-- Admin A CAN curate their own PHC A question (c001) → 1 row updated.
-- Admin A CANNOT curate PHC B question (c002) → 0 rows updated (RLS blocks).
-- ══════════════════════════════════════════════════════════════════════════
SET ROLE authenticated;
SELECT set_config(
  'request.jwt.claims',
  '{"sub":"00000000-0000-0000-0000-000000000a01","role":"authenticated"}',
  false
);

DO $$
DECLARE
  rows_updated int;
BEGIN
  UPDATE public.protocol_questions
     SET curator_answer_text = 'Paracetamol 15 mg/kg every 6 hours (max 4 doses/day).',
         status              = 'curated',
         curated_by          = '00000000-0000-0000-0000-000000000a01',
         curated_at          = now()
   WHERE id = '00000000-0000-0000-0000-00000000c001';
  GET DIAGNOSTICS rows_updated = ROW_COUNT;
  IF rows_updated <> 1 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 3a): PHC Admin A cannot curate own PHC A question';
  END IF;

  UPDATE public.protocol_questions
     SET curator_answer_text = 'Cross-PHC curation attempt',
         status              = 'curated',
         curated_by          = '00000000-0000-0000-0000-000000000a01',
         curated_at          = now()
   WHERE id = '00000000-0000-0000-0000-00000000c002';
  GET DIAGNOSTICS rows_updated = ROW_COUNT;
  IF rows_updated <> 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 3b): PHC Admin A curated a PHC B question';
  END IF;
END
$$;

RESET ROLE;

-- ══════════════════════════════════════════════════════════════════════════
-- CHECK 4 — Supervisor SELECT scope (no facility_id)
-- Supervisor sees ALL protocol_questions (2 rows).
-- Clinical data boundary: Supervisor sees 0 case_records directly!
-- ══════════════════════════════════════════════════════════════════════════
SET ROLE authenticated;
SELECT set_config(
  'request.jwt.claims',
  '{"sub":"00000000-0000-0000-0000-000000000b01","role":"authenticated"}',
  false
);

DO $$
DECLARE
  visible_protocols int;
  visible_cases     int;
BEGIN
  SELECT count(*) INTO visible_protocols FROM public.protocol_questions;
  IF visible_protocols <> 2 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 4a): Supervisor sees % protocol_questions instead of 2', visible_protocols;
  END IF;

  -- Clinical-data boundary assertion: Supervisor has 0 direct case_records access
  SELECT count(*) INTO visible_cases FROM public.case_records;
  IF visible_cases <> 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 4b): Supervisor sees % case_records directly — clinical boundary violation!', visible_cases;
  END IF;
END
$$;

RESET ROLE;

-- ══════════════════════════════════════════════════════════════════════════
-- CHECK 5 — Phase 40: Supervisor Global Aggregate Execution (fn_team_metrics & fn_outbreak_signal_counts)
-- Supervisor with NULL facility_id MUST be able to call both functions with p_facility_id = NULL
-- and receive organization-wide aggregates without SQLSTATE 22023.
-- ══════════════════════════════════════════════════════════════════════════
SET ROLE authenticated;
SELECT set_config(
  'request.jwt.claims',
  '{"sub":"00000000-0000-0000-0000-000000000b01","role":"authenticated"}',
  false
);

DO $$
DECLARE
  team_metrics_count int;
  outbreak_count     int;
BEGIN
  -- 5a. Global fn_team_metrics call (p_facility_id = NULL)
  SELECT count(*) INTO team_metrics_count
  FROM public.fn_team_metrics(NULL, now() - interval '30 days');
  IF team_metrics_count <> 2 THEN
    RAISE EXCEPTION 'PHASE 40 REGRESSION (check 5a): Supervisor global fn_team_metrics returned % rows (expected 2 across PHC A and B)', team_metrics_count;
  END IF;

  -- 5b. Supervisor narrowed fn_team_metrics call (p_facility_id = PHC A)
  SELECT count(*) INTO team_metrics_count
  FROM public.fn_team_metrics('00000000-0000-0000-0000-0000000000f1'::uuid, now() - interval '30 days');
  IF team_metrics_count <> 1 THEN
    RAISE EXCEPTION 'PHASE 40 REGRESSION (check 5b): Supervisor narrowed fn_team_metrics for PHC A returned % rows (expected 1)', team_metrics_count;
  END IF;

  -- 5c. Global fn_outbreak_signal_counts call (p_facility_id = NULL)
  SELECT count(*) INTO outbreak_count
  FROM public.fn_outbreak_signal_counts(NULL, now() - interval '30 days');
  IF outbreak_count <> 2 THEN
    RAISE EXCEPTION 'PHASE 40 REGRESSION (check 5c): Supervisor global fn_outbreak_signal_counts returned % rows (expected 2)', outbreak_count;
  END IF;

  -- 5d. Supervisor narrowed fn_outbreak_signal_counts call (p_facility_id = PHC A)
  SELECT count(*) INTO outbreak_count
  FROM public.fn_outbreak_signal_counts('00000000-0000-0000-0000-0000000000f1'::uuid, now() - interval '30 days');
  IF outbreak_count <> 1 THEN
    RAISE EXCEPTION 'PHASE 40 REGRESSION (check 5d): Supervisor narrowed fn_outbreak_signal_counts for PHC A returned % rows (expected 1)', outbreak_count;
  END IF;
END
$$;

RESET ROLE;

-- ══════════════════════════════════════════════════════════════════════════
-- CHECK 6 — Phase 40: PHC Administrator Scoping Enforcement
-- Admin A attempts to query PHC B by passing PHC B's UUID -> function forces PHC A.
-- ══════════════════════════════════════════════════════════════════════════
SET ROLE authenticated;
SELECT set_config(
  'request.jwt.claims',
  '{"sub":"00000000-0000-0000-0000-000000000a01","role":"authenticated"}',
  false
);

DO $$
DECLARE
  team_metrics_count int;
  outbreak_count     int;
BEGIN
  -- Admin A attempts to pass PHC B's UUID to fn_team_metrics -> must return PHC A row only (1 row)
  SELECT count(*) INTO team_metrics_count
  FROM public.fn_team_metrics('00000000-0000-0000-0000-0000000000f2'::uuid, now() - interval '30 days');
  IF team_metrics_count <> 1 THEN
    RAISE EXCEPTION 'PHASE 40 REGRESSION (check 6a): Admin A passed PHC B UUID but got % rows instead of 1 (PHC A forced)', team_metrics_count;
  END IF;

  -- Admin A attempts to pass PHC B's UUID to fn_outbreak_signal_counts -> must return PHC A row only (1 row)
  SELECT count(*) INTO outbreak_count
  FROM public.fn_outbreak_signal_counts('00000000-0000-0000-0000-0000000000f2'::uuid, now() - interval '30 days');
  IF outbreak_count <> 1 THEN
    RAISE EXCEPTION 'PHASE 40 REGRESSION (check 6b): Admin A passed PHC B UUID but got % rows instead of 1 (PHC A forced)', outbreak_count;
  END IF;
END
$$;

RESET ROLE;

-- ══════════════════════════════════════════════════════════════════════════
-- CHECK 7 — Phase 40: Doctor and ASHA Worker Execution Permissions
-- Doctor A (PHC A) can call fn_outbreak_signal_counts (scoped to PHC A -> 1 row); denied fn_team_metrics.
-- ASHA Worker (PHC A) is denied execution for both functions.
-- ══════════════════════════════════════════════════════════════════════════
SET ROLE authenticated;
SELECT set_config(
  'request.jwt.claims',
  '{"sub":"00000000-0000-0000-0000-000000000d01","role":"authenticated"}',
  false
);

DO $$
DECLARE
  outbreak_count int;
  caught_metrics boolean := false;
BEGIN
  SELECT count(*) INTO outbreak_count
  FROM public.fn_outbreak_signal_counts(NULL, now() - interval '30 days');
  IF outbreak_count <> 1 THEN
    RAISE EXCEPTION 'PHASE 40 REGRESSION (check 7a): Doctor A fn_outbreak_signal_counts returned % rows instead of 1', outbreak_count;
  END IF;

  BEGIN
    PERFORM public.fn_team_metrics(NULL, now() - interval '30 days');
  EXCEPTION WHEN OTHERS THEN
    caught_metrics := true;
  END;
  IF NOT caught_metrics THEN
    RAISE EXCEPTION 'PHASE 40 REGRESSION (check 7b): Doctor A was NOT denied execution for fn_team_metrics!', caught_metrics;
  END IF;
END
$$;

RESET ROLE;

-- ASHA Worker check
SET ROLE authenticated;
SELECT set_config(
  'request.jwt.claims',
  '{"sub":"00000000-0000-0000-0000-000000000e01","role":"authenticated"}',
  false
);

DO $$
DECLARE
  caught_metrics  boolean := false;
  caught_outbreak boolean := false;
BEGIN
  BEGIN
    PERFORM public.fn_team_metrics(NULL, now() - interval '30 days');
  EXCEPTION WHEN OTHERS THEN
    caught_metrics := true;
  END;

  BEGIN
    PERFORM public.fn_outbreak_signal_counts(NULL, now() - interval '30 days');
  EXCEPTION WHEN OTHERS THEN
    caught_outbreak := true;
  END;

  IF NOT (caught_metrics AND caught_outbreak) THEN
    RAISE EXCEPTION 'PHASE 40 REGRESSION (check 7c): ASHA Worker was NOT denied execution for aggregate functions!';
  END IF;
END
$$;

RESET ROLE;

SELECT 'All RLS and Security Definer checks passed: Supervisor has global aggregate access & 0 direct case_records access; PHC Admin and Doctor are scoped locally; ASHA denied.' AS result;
