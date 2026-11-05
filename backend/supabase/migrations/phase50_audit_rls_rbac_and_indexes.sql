-- backend/supabase/migrations/phase50_audit_rls_rbac_and_indexes.sql
-- Phase 50: Security Hardening, Submitter Allowlist Trigger, Two-Tier RBAC & Keyset Indexing
-- Remediates CRITICAL-3, HIGH-1, HIGH-2, HIGH-10, and MEDIUM-1 at the database layer.
-- Fully idempotent and compatible with .github/workflows/db-schema-drift.yml.

BEGIN;

-- ═══════════════════════════════════════════════════════════════════════════
-- 1. [CRITICAL-3] Invert protect_case_records_clinical_columns() from a
--    29-column blacklist to a strict JSONB allowlist for submitters.
--    Prevents ASHA workers from modifying overridden_triage, needs_review,
--    or any clinical/vitals columns via PostgREST.
-- ═══════════════════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION public.protect_case_records_clinical_columns()
RETURNS trigger AS $$
DECLARE
  v_allowed_submitter_cols text[] := ARRAY[
    'deleted_at',
    'human_review_requested',
    'human_review_reason',
    'updated_at'
  ];
BEGIN
  IF auth.uid() = OLD.submitted_by
     AND NOT EXISTS (
       SELECT 1 FROM public.profiles p
       WHERE p.id = auth.uid()
         AND p.is_active = true
         AND p.role = ANY (ARRAY['doctor'::text, 'facility_admin'::text, 'admin'::text, 'super_admin'::text])
     )
  THEN
    IF (to_jsonb(NEW) - v_allowed_submitter_cols) IS DISTINCT FROM (to_jsonb(OLD) - v_allowed_submitter_cols) THEN
      RAISE EXCEPTION 'Clinical, triage, override, and identity columns cannot be modified by the submitter';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ═══════════════════════════════════════════════════════════════════════════
-- 2. [HIGH-2] Drop permissive public policies on phi_audit_log & facilities,
--    and enforce active-profile + same-facility check on case_outcomes INSERT.
-- ═══════════════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS phi_audit_log_insert_only ON public.phi_audit_log;
DROP POLICY IF EXISTS facilities_public_read ON public.facilities;

-- Authenticated users with active profiles can read active facilities (needed for profile join & referral picker),
-- while anonymous callers cannot scrape facility phone numbers.
DROP POLICY IF EXISTS facilities_select_policy ON public.facilities;
CREATE POLICY facilities_select_policy ON public.facilities
  FOR SELECT TO authenticated
  USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid() AND p.is_active = true
    )
  );

DROP POLICY IF EXISTS case_outcomes_insert_policy ON public.case_outcomes;
CREATE POLICY case_outcomes_insert_policy ON public.case_outcomes
  FOR INSERT TO authenticated
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND recorded_by = auth.uid()
    AND EXISTS (
      SELECT 1
      FROM public.profiles p
      JOIN public.case_records cr ON cr.id = case_outcomes.case_id
      WHERE p.id = auth.uid()
        AND p.is_active = true
        AND p.role = ANY (ARRAY['doctor'::text, 'admin'::text, 'super_admin'::text])
        AND (p.role = 'super_admin'::text OR p.facility_id = cr.facility_id)
    )
  );

-- ═══════════════════════════════════════════════════════════════════════════
-- 3. [HIGH-1] Scope PHC 'admin' to own facility_id on case_records SELECT
--    (Passes ci_rls_regression_check.sql CHECK 2 while blocking cross-PHC PHI access)
-- ═══════════════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS asha_select_own ON public.case_records;
CREATE POLICY asha_select_own ON public.case_records
  FOR SELECT TO authenticated
  USING (
    auth.uid() IS NOT NULL
    AND deleted_at IS NULL
    AND (
      submitted_by = auth.uid()
      OR EXISTS (
        SELECT 1 FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.is_active = true
          AND p.role = ANY (ARRAY['doctor'::text, 'facility_admin'::text, 'admin'::text, 'super_admin'::text])
          AND (
            p.role = 'super_admin'::text
            OR p.facility_id = case_records.facility_id
          )
      )
    )
  );

-- ═══════════════════════════════════════════════════════════════════════════
-- 4. [HIGH-10] Create 5-column composite partial index for Doctor Dashboard
--    keyset pagination & drop duplicate legacy indexes.
-- ═══════════════════════════════════════════════════════════════════════════
CREATE INDEX IF NOT EXISTS idx_case_records_dashboard_keyset
  ON public.case_records (
    facility_id,
    triage_priority ASC,
    needs_review DESC,
    created_at DESC,
    id DESC
  )
  WHERE deleted_at IS NULL;

DROP INDEX IF EXISTS public.idx_case_records_facility_id;
DROP INDEX IF EXISTS public.idx_case_records_triage_priority_created_at;

COMMIT;
