-- CI-only functional RLS regression check.
-- Covers two concerns:
--
-- 1. JWT-metadata privilege escalation (phase32 fix, docs/DECISIONS.md §36):
--    A user who sets user_metadata.role = 'admin' via Supabase's Auth API,
--    without a matching public.profiles row, still sees nothing.
--
-- 2. Protocol Assistant RLS governance (phase39):
--    PHC Administrator is scoped to own facility only; Supervisor has global
--    read/curation access even without a facility_id.
--
-- Technique: seed minimal data, SET ROLE authenticated, simulate real
-- PostgREST-style JWT claims, assert row counts and write outcomes.
-- Superuser does NOT trigger RLS — only the SET ROLE block does.
\set ON_ERROR_STOP on

-- ── UUID legend ────────────────────────────────────────────────────────────
-- 00000000-0000-0000-0000-0000000000f1   CI Test PHC A (from ci_stubs.sql)
-- 00000000-0000-0000-0000-0000000000f2   CI Test PHC B (new, added here)
-- 00000000-0000-0000-0000-000000000a01   CI Admin PHC A
-- 00000000-0000-0000-0000-000000000a02   CI Admin PHC B
-- 00000000-0000-0000-0000-000000000b01   CI Supervisor (no facility_id)
-- 00000000-0000-0000-0000-00000000eeee   Attacker (no profiles row)
-- 00000000-0000-0000-0000-00000000ca01   CI case_record (PHC A)
-- 00000000-0000-0000-0000-00000000c001   CI protocol_question (PHC A)
-- 00000000-0000-0000-0000-00000000c002   CI protocol_question (PHC B)
-- ──────────────────────────────────────────────────────────────────────────

BEGIN;

INSERT INTO public.facilities (id, name, type, district, state)
VALUES ('00000000-0000-0000-0000-0000000000f2', 'CI PHC B', 'PHC', 'Test District B', 'Test State');

-- profiles.id has a FOREIGN KEY to auth.users(id) on the real project;
-- ci_stubs.sql's auth.users stub carries that same constraint shape.
INSERT INTO auth.users (id) VALUES ('00000000-0000-0000-0000-000000000a02');
INSERT INTO auth.users (id) VALUES ('00000000-0000-0000-0000-000000000b01');

-- Admin 1 assigned to PHC A
INSERT INTO public.profiles (id, full_name, role, facility_id, is_active)
VALUES ('00000000-0000-0000-0000-000000000a01', 'CI Real Admin', 'admin', '00000000-0000-0000-0000-0000000000f1', true)
ON CONFLICT (id) DO UPDATE SET facility_id = '00000000-0000-0000-0000-0000000000f1';

-- Admin 2 assigned to PHC B
INSERT INTO public.profiles (id, full_name, role, facility_id, is_active)
VALUES ('00000000-0000-0000-0000-000000000a02', 'CI Admin PHC B', 'admin', '00000000-0000-0000-0000-0000000000f2', true);

-- Supervisor with no facility_id
INSERT INTO public.profiles (id, full_name, role, facility_id, is_active)
VALUES ('00000000-0000-0000-0000-000000000b01', 'CI Supervisor', 'supervisor', NULL, true);

-- Case record seeded for PHC A (used by JWT-metadata and Admin A assertions below)
INSERT INTO public.case_records (
  id, client_id, submitted_by, facility_id, patient_age, patient_sex,
  chief_complaint, symptoms, triage_level
) VALUES (
  '00000000-0000-0000-0000-00000000ca01', '00000000-0000-0000-0000-00000000cc01',
  '00000000-0000-0000-0000-000000000a01', '00000000-0000-0000-0000-0000000000f1',
  30, 'female', 'fever', ARRAY['fever'], 'ROUTINE'
);

-- Protocol question for PHC A (c001)
INSERT INTO public.protocol_questions (
  id, asked_by, facility_id, question_text, status
) VALUES (
  '00000000-0000-0000-0000-00000000c001', '00000000-0000-0000-0000-000000000a01',
  '00000000-0000-0000-0000-0000000000f1', 'What is the dosage for paracetamol in children?', 'pending_curation'
);

-- Protocol question for PHC B (c002)
INSERT INTO public.protocol_questions (
  id, asked_by, facility_id, question_text, status
) VALUES (
  '00000000-0000-0000-0000-00000000c002', '00000000-0000-0000-0000-000000000a02',
  '00000000-0000-0000-0000-0000000000f2', 'How to manage severe hypertension in pregnancy?', 'pending_curation'
);

COMMIT;

-- ══════════════════════════════════════════════════════════════════════════
-- CHECK 1 — JWT-metadata attacker (no profiles row)
-- Expects: 0 case_records, 0 profiles, 0 protocol_questions
-- ══════════════════════════════════════════════════════════════════════════
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
    RAISE EXCEPTION 'RLS REGRESSION (check 1): user_metadata-only admin sees % case_records — phase32 fix broken', visible_cases;
  END IF;
  IF visible_profiles <> 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 1): user_metadata-only admin sees % profiles — phase32 fix broken', visible_profiles;
  END IF;
  IF visible_protocols <> 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 1): user_metadata-only admin sees % protocol_questions', visible_protocols;
  END IF;
END
$$;

RESET ROLE;

-- ══════════════════════════════════════════════════════════════════════════
-- CHECK 2 — PHC Admin A READ scope
-- Expects: sees own case_records and profiles, sees ONLY PHC A protocol_question
-- (1 row, not 2 — cross-PHC SELECT must be denied)
-- ══════════════════════════════════════════════════════════════════════════
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
    RAISE EXCEPTION 'RLS REGRESSION (check 2): PHC Admin A sees 0 case_records — over-restrictive policy';
  END IF;
  IF visible_profiles = 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 2): PHC Admin A sees 0 profiles — over-restrictive policy';
  END IF;
  IF visible_protocols <> 1 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 2): PHC Admin A sees % protocol_questions instead of 1 (cross-PHC SELECT leak!)', visible_protocols;
  END IF;
END
$$;

RESET ROLE;

-- ══════════════════════════════════════════════════════════════════════════
-- CHECK 3 — PHC Admin A WRITE scope (curation)
-- Admin A CAN curate their own PHC A question (c001).
-- Admin A CANNOT curate PHC B question (c002) — UPDATE must affect 0 rows.
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
  -- Admin A curates their OWN PHC A question — expect 1 row updated
  UPDATE public.protocol_questions
  SET curator_answer_text = 'Paracetamol 15mg/kg every 6 hours.', status = 'curated',
      curated_by = '00000000-0000-0000-0000-000000000a01',
      curated_at = now()
  WHERE id = '00000000-0000-0000-0000-00000000c001';
  GET DIAGNOSTICS rows_updated = ROW_COUNT;
  IF rows_updated <> 1 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 3): PHC Admin A cannot curate own PHC A question — got % rows updated', rows_updated;
  END IF;

  -- Admin A attempts to curate PHC B question — expect 0 rows updated (RLS blocks it)
  UPDATE public.protocol_questions
  SET curator_answer_text = 'Cross-PHC curation attempt', status = 'curated',
      curated_by = '00000000-0000-0000-0000-000000000a01',
      curated_at = now()
  WHERE id = '00000000-0000-0000-0000-00000000c002';
  GET DIAGNOSTICS rows_updated = ROW_COUNT;
  IF rows_updated <> 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 3): PHC Admin A curated a PHC B question — cross-PHC UPDATE not blocked! % rows updated', rows_updated;
  END IF;
END
$$;

RESET ROLE;

-- ══════════════════════════════════════════════════════════════════════════
-- CHECK 4 — Supervisor READ scope (no facility_id)
-- Supervisor must see ALL protocol_questions (2 rows).
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
BEGIN
  SELECT count(*) INTO visible_protocols FROM public.protocol_questions;
  IF visible_protocols <> 2 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 4): Supervisor sees % protocol_questions instead of 2 (global access broken)', visible_protocols;
  END IF;
END
$$;

RESET ROLE;

-- ══════════════════════════════════════════════════════════════════════════
-- CHECK 5 — Supervisor WRITE scope (curation, no facility_id)
-- Supervisor with NULL facility_id MUST be able to curate a PHC B question.
-- ══════════════════════════════════════════════════════════════════════════
SET ROLE authenticated;
SELECT set_config(
  'request.jwt.claims',
  '{"sub":"00000000-0000-0000-0000-000000000b01","role":"authenticated"}',
  false
);

DO $$
DECLARE
  rows_updated int;
BEGIN
  UPDATE public.protocol_questions
  SET curator_answer_text = 'Supervisor: IV labetalol per MFAC protocol.', status = 'curated',
      curated_by = '00000000-0000-0000-0000-000000000b01',
      curated_at = now()
  WHERE id = '00000000-0000-0000-0000-00000000c002';
  GET DIAGNOSTICS rows_updated = ROW_COUNT;
  IF rows_updated <> 1 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 5): Supervisor cannot curate PHC B question (no-facility global curation broken) — got % rows', rows_updated;
  END IF;
END
$$;

RESET ROLE;

SELECT 'All RLS checks passed: JWT-metadata escalation closed; PHC Admin scoped locally for SELECT and UPDATE; Supervisor has global SELECT and curation access.' AS result;
