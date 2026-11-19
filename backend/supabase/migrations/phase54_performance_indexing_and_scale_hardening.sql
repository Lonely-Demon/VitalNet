-- backend/supabase/migrations/phase54_performance_indexing_and_scale_hardening.sql
-- Phase 54: Architecture, Performance, Indexing & Scale Hardening
-- Enforces:
--   1. [F-05] respiratory_rate schema reconciliation on public.case_records with CHECK bounds [5, 120]
--   2. [B1] STABLE RLS helpers and InitPlan caching for asha_select_own
--   3. [B2] Fast-path short-circuit in protect_case_records_clinical_columns() while strictly preserving Phase 52's fail-closed JSONB allowlist
--   4. [B3 & F-11] Composite, partial, and cleanup indexes on case_records, referrals, and protocol_questions
--   5. [A3-2] In-database fn_ears_daily_counts SQL aggregation RPC with IST timezone grouping
-- Idempotent — safe to re-run. Compatible with db-schema-drift.yml.

BEGIN;

-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 1. [F-05] Reconcile respiratory_rate schema column & bounds
-- ═══════════════════════════════════════════════════════════════════════════

ALTER TABLE public.case_records
  ADD COLUMN IF NOT EXISTS respiratory_rate integer;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'case_records_respiratory_rate_bounds'
  ) THEN
    ALTER TABLE public.case_records
      ADD CONSTRAINT case_records_respiratory_rate_bounds
      CHECK (respiratory_rate IS NULL OR (respiratory_rate >= 5 AND respiratory_rate <= 120));
  END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 2. [B1] STABLE RLS Helpers & InitPlan Caching for asha_select_own
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.get_user_role(user_id uuid)
RETURNS text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
  SELECT role FROM public.profiles WHERE id = user_id;
$function$;

CREATE OR REPLACE FUNCTION public.get_user_facility(user_id uuid)
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
  SELECT facility_id FROM public.profiles WHERE id = user_id;
$function$;

CREATE OR REPLACE FUNCTION public.get_current_user_role()
RETURNS text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
  SELECT role FROM public.profiles WHERE id = (SELECT auth.uid()) AND is_active = true;
$function$;

CREATE OR REPLACE FUNCTION public.get_current_user_facility()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
  SELECT facility_id FROM public.profiles WHERE id = (SELECT auth.uid()) AND is_active = true;
$function$;

REVOKE ALL ON FUNCTION public.get_current_user_role() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_current_user_role() TO authenticated;

REVOKE ALL ON FUNCTION public.get_current_user_facility() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_current_user_facility() TO authenticated;

DROP POLICY IF EXISTS asha_select_own ON public.case_records;
CREATE POLICY asha_select_own ON public.case_records
  FOR SELECT TO authenticated
  USING (
    (SELECT auth.uid()) IS NOT NULL
    AND deleted_at IS NULL
    AND (
      submitted_by = (SELECT auth.uid())
      OR (
        public.get_current_user_role() = 'super_admin'
        OR (
          public.get_current_user_role() = ANY (ARRAY['doctor'::text, 'facility_admin'::text, 'admin'::text])
          AND public.get_current_user_facility() = case_records.facility_id
        )
      )
    )
  );

-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 3. [B2] Fast-Path Trigger Short-Circuit with Preserved JSONB Allowlist
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.protect_case_records_clinical_columns()
RETURNS trigger AS $$
DECLARE
  -- Standard post-submission columns a non-clinical submitter may update:
  v_allowed_submitter_cols text[] := ARRAY[
    'deleted_at',
    'human_review_requested',
    'human_review_reason',
    'follow_up_completed_at',
    'updated_at'
  ];
  -- Columns permitted to change during one-time SMS stub promotion
  -- (OLD.is_sms_stub = true -> NEW.is_sms_stub = false).
  -- Strictly excludes clinician-only and tenant-isolation columns:
  --   reviewed_by, reviewed_at, doctor_notes, overridden_triage,
  --   override_reason, overridden_at, facility_id, submitted_by, id, client_id,
  --   follow_up_required, follow_up_due_at.
  v_allowed_sms_promotion_cols text[] := ARRAY[
    'is_sms_stub',
    'patient_name',
    'patient_age',
    'age_months',
    'patient_sex',
    'patient_location',
    'patient_key',
    'chief_complaint',
    'complaint_duration',
    'symptoms',
    'observations',
    'known_conditions',
    'current_medications',
    'is_pregnant',
    'muac_mm',
    'contraindication_flags',
    'temperature',
    'heart_rate',
    'bp_systolic',
    'bp_diastolic',
    'spo2',
    'respiratory_rate',
    'triage_level',
    'triage_priority',
    'triage_confidence',
    'triage_model_version',
    'risk_driver',
    'low_confidence',
    'needs_review',
    'deterioration_alert',
    'deterioration_visit_count',
    'briefing',
    'consent_given',
    'consent_timestamp',
    'created_offline',
    'client_submitted_at',
    'updated_at'
  ];
  v_is_clinician_or_admin boolean;
BEGIN
  -- Fast-path: non-submitter updates (clinicians, system, admins) bypass submitter restrictions
  IF (SELECT auth.uid()) IS DISTINCT FROM OLD.submitted_by THEN
    RETURN NEW;
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM public.profiles p
    WHERE p.id = (SELECT auth.uid())
      AND p.is_active = true
      AND p.role = ANY (ARRAY['doctor'::text, 'facility_admin'::text, 'admin'::text, 'super_admin'::text])
  ) INTO v_is_clinician_or_admin;

  -- If submitter is also clinician/admin, allow update
  IF v_is_clinician_or_admin THEN
    RETURN NEW;
  END IF;

  -- One-time promotion from an offline SMS stub by the original submitter
  IF OLD.is_sms_stub IS TRUE AND NEW.is_sms_stub IS FALSE THEN
    -- 1. If a clinician already reviewed or overrode the SMS stub while offline,
    --    preserve the clinician's triage/review state and forbid overwriting it.
    IF OLD.reviewed_at IS NOT NULL OR OLD.overridden_triage IS NOT NULL THEN
      NEW.triage_level := OLD.triage_level;
      NEW.triage_priority := OLD.triage_priority;
      NEW.needs_review := OLD.needs_review;
    END IF;

    -- 2. Verify no clinician-only or tenant-identity columns were modified (fail-closed JSONB allowlist)
    IF (to_jsonb(NEW) - v_allowed_sms_promotion_cols) IS DISTINCT FROM (to_jsonb(OLD) - v_allowed_sms_promotion_cols) THEN
      RAISE EXCEPTION 'SMS stub promotion cannot modify clinician review, override, or tenant identity columns' USING ERRCODE = '42501';
    END IF;

    RETURN NEW;
  END IF;

  -- Standard subsequent updates by a non-clinical submitter (fail-closed JSONB allowlist)
  IF (to_jsonb(NEW) - v_allowed_submitter_cols) IS DISTINCT FROM (to_jsonb(OLD) - v_allowed_submitter_cols) THEN
    RAISE EXCEPTION 'Clinical, triage, override, and identity columns cannot be modified by the submitter' USING ERRCODE = '42501';
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_protect_case_records_clinical_columns ON public.case_records;
CREATE TRIGGER trg_protect_case_records_clinical_columns
  BEFORE UPDATE ON public.case_records
  FOR EACH ROW EXECUTE FUNCTION public.protect_case_records_clinical_columns();

-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 4. [B3 & F-11] Composite, Partial, and Cleanup Indexes
-- ═══════════════════════════════════════════════════════════════════════════

-- 1. ASHA worker submissions fast scan & ordering
CREATE INDEX IF NOT EXISTS idx_case_records_submitted_created
  ON public.case_records (submitted_by, created_at DESC)
  WHERE deleted_at IS NULL;

-- 2. Facility historical & outbreak queries
CREATE INDEX IF NOT EXISTS idx_case_records_facility_created
  ON public.case_records (facility_id, created_at DESC)
  WHERE deleted_at IS NULL;

-- 3. Referrals queue keyset scan
CREATE INDEX IF NOT EXISTS idx_referrals_receiving_status_created
  ON public.referrals (receiving_facility_id, status, created_at DESC);

-- 4. Protocol questions queue keyset scan
CREATE INDEX IF NOT EXISTS idx_protocol_questions_facility_status_created
  ON public.protocol_questions (facility_id, status, created_at DESC);

-- 5 & 6. Drop redundant/superseded legacy single-column indexes
DROP INDEX IF EXISTS public.idx_case_records_submitted_by;
DROP INDEX IF EXISTS public.idx_case_records_deleted_at;
DROP INDEX IF EXISTS public.idx_case_records_needs_review;
DROP INDEX IF EXISTS public.idx_referrals_status;

-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 5. [A3-2] fn_ears_daily_counts SQL Aggregation RPC
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.fn_ears_daily_counts(
  p_facility_id uuid DEFAULT NULL,
  p_since timestamptz DEFAULT NULL
)
RETURNS TABLE(
  facility_id uuid,
  date text,
  symptom text,
  daily_count bigint
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_role text;
  v_own_facility uuid;
BEGIN
  SELECT p.role, p.facility_id INTO v_role, v_own_facility
  FROM public.profiles p WHERE p.id = (SELECT auth.uid()) AND p.is_active = true;

  IF v_role IS NULL OR v_role NOT IN ('doctor', 'facility_admin', 'supervisor', 'admin', 'super_admin') THEN
    RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
  END IF;

  -- Non-global roles are pinned to their own facility
  IF v_role NOT IN ('admin', 'super_admin', 'supervisor') THEN
    IF v_own_facility IS NULL THEN
      RAISE EXCEPTION 'account has no facility assigned' USING ERRCODE = '22023';
    END IF;
    p_facility_id := v_own_facility;
  END IF;

  IF p_since IS NULL THEN
    RAISE EXCEPTION 'fn_ears_daily_counts: p_since is required' USING ERRCODE = '22023';
  END IF;

  RETURN QUERY
  SELECT
    cr.facility_id,
    to_char(cr.created_at AT TIME ZONE 'Asia/Kolkata', 'YYYY-MM-DD') AS date,
    s.symptom,
    COUNT(*)::bigint AS daily_count
  FROM public.case_records cr,
       jsonb_array_elements_text(to_jsonb(cr.symptoms)) AS s(symptom)
  WHERE cr.deleted_at IS NULL
    AND cr.created_at >= p_since
    AND (p_facility_id IS NULL OR cr.facility_id = p_facility_id)
  GROUP BY cr.facility_id, to_char(cr.created_at AT TIME ZONE 'Asia/Kolkata', 'YYYY-MM-DD'), s.symptom;
END;
$$;

REVOKE ALL ON FUNCTION public.fn_ears_daily_counts(uuid, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fn_ears_daily_counts(uuid, timestamptz) TO authenticated;

COMMIT;
