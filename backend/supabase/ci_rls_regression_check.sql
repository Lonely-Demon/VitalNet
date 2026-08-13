-- CI-only functional RLS regression check.
-- Covers two concerns:
--
-- 1. JWT-metadata privilege escalation (phase32 fix, docs/DECISIONS.md §36):
--    A user who sets user_metadata.role = 'admin' via Supabase's Auth API,
--    without a matching public.profiles row, still sees nothing.
--
-- 2. Protocol Assistant RLS governance (phase39):
--    PHC Administrator is scoped to own facility only (SELECT and UPDATE);
--    Supervisor has global read/curation access even without a facility_id.
--
-- Technique: seed minimal data, SET ROLE authenticated, simulate real
-- PostgREST-style JWT claims, assert row counts and write outcomes.
-- Superuser does NOT trigger RLS — only the SET ROLE block does.
--
-- SELF-CONTAINED: this file seeds every prerequisite it needs explicitly.
-- It does not rely on any undocumented data from ci_stubs.sql or the
-- schema_snapshot baseline. All ON CONFLICT DO NOTHING guards make it
-- safe to re-run on a partially-seeded DB (e.g. a retried CI job).
\set ON_ERROR_STOP on

-- ── UUID legend ────────────────────────────────────────────────────────────
-- 00000000-0000-0000-0000-0000000000f1   CI Test PHC A
-- 00000000-0000-0000-0000-0000000000f2   CI Test PHC B
-- 00000000-0000-0000-0000-000000000a01   CI Admin PHC A
-- 00000000-0000-0000-0000-000000000a02   CI Admin PHC B
-- 00000000-0000-0000-0000-000000000b01   CI Supervisor (no facility_id)
-- 00000000-0000-0000-0000-00000000eeee   Attacker (no profiles row)
-- 00000000-0000-0000-0000-00000000ca01   CI case_record (PHC A)
-- 00000000-0000-0000-0000-00000000c001   CI protocol_question (PHC A)
-- 00000000-0000-0000-0000-00000000c002   CI protocol_question (PHC B)
-- ──────────────────────────────────────────────────────────────────────────

BEGIN;

-- Seed both facilities first — all downstream inserts (profiles, case_records,
-- protocol_questions) foreign-key into facilities.
INSERT INTO public.facilities (id, name, type, district, state)
VALUES
  ('00000000-0000-0000-0000-0000000000f1', 'CI PHC A', 'PHC', 'Test District A', 'Test State'),
  ('00000000-0000-0000-0000-0000000000f2', 'CI PHC B', 'PHC', 'Test District B', 'Test State')
ON CONFLICT (id) DO NOTHING;

-- Auth identities for every profile used in SET ROLE checks below.
-- Attacker (eeee) deliberately has NO profiles row — the whole point of check 1.
INSERT INTO auth.users (id)
VALUES
  ('00000000-0000-0000-0000-000000000a01'),
  ('00000000-0000-0000-0000-000000000a02'),
  ('00000000-0000-0000-0000-000000000b01')
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

-- Case record for PHC A (used in checks 1 and 2)
INSERT INTO public.case_records (
  id, client_id, submitted_by, facility_id, patient_age, patient_sex,
  chief_complaint, symptoms, triage_level
) VALUES (
  '00000000-0000-0000-0000-00000000ca01',
  '00000000-0000-0000-0000-00000000cc01',
  '00000000-0000-0000-0000-000000000a01',
  '00000000-0000-0000-0000-0000000000f1',
  30, 'female', 'fever', ARRAY['fever'], 'ROUTINE'
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
    RAISE EXCEPTION 'RLS REGRESSION (check 2): PHC Admin A sees 0 case_records — over-restrictive policy';
  END IF;
  IF visible_profiles = 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 2): PHC Admin A sees 0 profiles — over-restrictive policy';
  END IF;
  IF visible_protocols <> 1 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 2): PHC Admin A sees % protocol_questions (expected 1 — cross-PHC SELECT leak or blanket denial)', visible_protocols;
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
  -- Own-PHC curation must succeed
  UPDATE public.protocol_questions
     SET curator_answer_text = 'Paracetamol 15 mg/kg every 6 hours (max 4 doses/day).',
         status              = 'curated',
         curated_by          = '00000000-0000-0000-0000-000000000a01',
         curated_at          = now()
   WHERE id = '00000000-0000-0000-0000-00000000c001';
  GET DIAGNOSTICS rows_updated = ROW_COUNT;
  IF rows_updated <> 1 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 3a): PHC Admin A cannot curate own PHC A question — got % rows updated', rows_updated;
  END IF;

  -- Cross-PHC curation must be blocked
  UPDATE public.protocol_questions
     SET curator_answer_text = 'Cross-PHC curation attempt',
         status              = 'curated',
         curated_by          = '00000000-0000-0000-0000-000000000a01',
         curated_at          = now()
   WHERE id = '00000000-0000-0000-0000-00000000c002';
  GET DIAGNOSTICS rows_updated = ROW_COUNT;
  IF rows_updated <> 0 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 3b): PHC Admin A curated a PHC B question — cross-PHC UPDATE not blocked (% rows updated)', rows_updated;
  END IF;
END
$$;

RESET ROLE;

-- ══════════════════════════════════════════════════════════════════════════
-- CHECK 4 — Supervisor SELECT scope (no facility_id)
-- Supervisor must see ALL protocol_questions across both PHCs (2 rows).
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
    RAISE EXCEPTION 'RLS REGRESSION (check 4): Supervisor sees % protocol_questions instead of 2 (global SELECT broken)', visible_protocols;
  END IF;
END
$$;

RESET ROLE;

-- ══════════════════════════════════════════════════════════════════════════
-- CHECK 5 — Supervisor UPDATE scope (curation, no facility_id)
-- A facility-unassigned Supervisor MUST be able to curate any PHC's question.
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
     SET curator_answer_text = 'Supervisor: IV labetalol per MFAC protocol.',
         status              = 'curated',
         curated_by          = '00000000-0000-0000-0000-000000000b01',
         curated_at          = now()
   WHERE id = '00000000-0000-0000-0000-00000000c002';
  GET DIAGNOSTICS rows_updated = ROW_COUNT;
  IF rows_updated <> 1 THEN
    RAISE EXCEPTION 'RLS REGRESSION (check 5): Supervisor cannot curate PHC B question (global curation broken) — got % rows updated', rows_updated;
  END IF;
END
$$;

RESET ROLE;

SELECT 'All RLS checks passed: JWT-metadata escalation closed; PHC Admin scoped locally for SELECT and UPDATE; Supervisor has global SELECT and curation access.' AS result;
