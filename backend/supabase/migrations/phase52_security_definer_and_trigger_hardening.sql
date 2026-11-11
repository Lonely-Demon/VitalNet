-- ============================================================================
-- FILE: backend/supabase/migrations/phase52_security_definer_and_trigger_hardening.sql
-- MIGRATION: Phase 52: SMS-Stub Trigger Privilege Escalation Fix, Atomic DSR
--            Erasure RPC, Two-Tier RBAC Policy Alignment & Trajectory RPC
-- REMEDIATES: BUG-02, BUG-09, BUG-10, BUG-29, BUG-30, BUG-35, BUG-51, BUG-52, BUG-54, BUG-56
-- SEQUENCED: Immediately after phase51_enterprise_care_continuity_hardening.sql
-- IDEMPOTENCY: Fully transactional and idempotent
-- ============================================================================

BEGIN;

-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 1. [BUG-02 & BUG-52] Harden protect_case_records_clinical_columns()
--    Fixes the unconditional RETURN NEW bypass during SMS-stub promotion
--    (OLD.is_sms_stub = true -> NEW.is_sms_stub = false) that previously allowed
--    a frontline submitter to forge clinician-only columns (overridden_triage,
--    reviewed_by, reviewed_at, doctor_notes, needs_review, facility_id) or
--    clobber an already-reviewed stub.
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
  SELECT EXISTS (
    SELECT 1 FROM public.profiles p
    WHERE p.id = auth.uid()
      AND p.is_active = true
      AND p.role = ANY (ARRAY['doctor'::text, 'facility_admin'::text, 'admin'::text, 'super_admin'::text])
  ) INTO v_is_clinician_or_admin;

  -- One-time promotion from an offline SMS stub by the original submitter
  IF OLD.is_sms_stub IS TRUE AND NEW.is_sms_stub IS FALSE AND auth.uid() = OLD.submitted_by AND NOT v_is_clinician_or_admin THEN
    -- 1. If a clinician already reviewed or overrode the SMS stub while offline,
    --    preserve the clinician's triage/review state and forbid overwriting it.
    IF OLD.reviewed_at IS NOT NULL OR OLD.overridden_triage IS NOT NULL THEN
      NEW.triage_level := OLD.triage_level;
      NEW.triage_priority := OLD.triage_priority;
      NEW.needs_review := OLD.needs_review;
    END IF;

    -- 2. Verify no clinician-only or tenant-identity columns were modified
    IF (to_jsonb(NEW) - v_allowed_sms_promotion_cols) IS DISTINCT FROM (to_jsonb(OLD) - v_allowed_sms_promotion_cols) THEN
      RAISE EXCEPTION 'SMS stub promotion cannot modify clinician review, override, or tenant identity columns' USING ERRCODE = '42501';
    END IF;

    RETURN NEW;
  END IF;

  -- Standard subsequent updates by a non-clinical submitter
  IF auth.uid() = OLD.submitted_by AND NOT v_is_clinician_or_admin THEN
    IF (to_jsonb(NEW) - v_allowed_submitter_cols) IS DISTINCT FROM (to_jsonb(OLD) - v_allowed_submitter_cols) THEN
      RAISE EXCEPTION 'Clinical, triage, override, and identity columns cannot be modified by the submitter' USING ERRCODE = '42501';
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 2. [BUG-35 & BUG-51] Update fn_mark_referral_followup_due to support
--    two-tier RBAC ('super_admin' global, 'doctor'/'admin'/'facility_admin'
--    confined to receiving_facility_id).
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.fn_mark_referral_followup_due(
  p_case_id uuid,
  p_referral_id uuid
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_role text;
  v_own_facility uuid;
  v_receiving_facility uuid;
  v_referral_status text;
BEGIN
  SELECT p.role, p.facility_id INTO v_role, v_own_facility
  FROM public.profiles p WHERE p.id = auth.uid() AND p.is_active = true;

  IF v_role IS NULL OR v_role NOT IN ('doctor', 'facility_admin', 'admin', 'super_admin') THEN
    RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
  END IF;

  SELECT r.receiving_facility_id, r.status INTO v_receiving_facility, v_referral_status
  FROM public.referrals r
  WHERE r.id = p_referral_id AND r.case_id = p_case_id;

  IF v_receiving_facility IS NULL THEN
    RAISE EXCEPTION 'referral not found' USING ERRCODE = 'P0002';
  END IF;

  IF v_referral_status <> 'completed' THEN
    RAISE EXCEPTION 'referral must be in completed status to schedule post-discharge follow-up' USING ERRCODE = '22023';
  END IF;

  IF v_role <> 'super_admin' AND v_own_facility IS DISTINCT FROM v_receiving_facility THEN
    RAISE EXCEPTION 'only receiving facility can trigger post-referral follow-up' USING ERRCODE = '42501';
  END IF;

  UPDATE public.case_records
  SET follow_up_required = true,
      follow_up_due_at = COALESCE(follow_up_due_at, now() + interval '48 hours'),
      updated_at = now()
  WHERE id = p_case_id AND deleted_at IS NULL;
END;
$$;

REVOKE ALL ON FUNCTION public.fn_mark_referral_followup_due(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fn_mark_referral_followup_due(uuid, uuid) TO authenticated;

-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 3. [BUG-09, BUG-10, BUG-29, BUG-30] Atomic SECURITY DEFINER RPC
--    fn_erase_case_pii(p_case_id uuid)
--    Eliminates direct service_role (supabase_admin) usage in DSR/revocation
--    routes and executes multi-table redaction + attachment/event deletion
--    inside a single atomic PostgreSQL transaction.
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.fn_erase_case_pii(
  p_case_id uuid
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_role text;
  v_own_facility uuid;
  v_case record;
  v_redacted constant text := '[REDACTED — DSR ERASURE]';
  v_new_briefing jsonb;
BEGIN
  SELECT p.role, p.facility_id INTO v_role, v_own_facility
  FROM public.profiles p
  WHERE p.id = auth.uid() AND p.is_active = true;

  IF v_role IS NULL THEN
    RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
  END IF;

  SELECT id, client_id, submitted_by, facility_id, deleted_at, patient_name, briefing
  INTO v_case
  FROM public.case_records
  WHERE id = p_case_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'case not found' USING ERRCODE = 'P0002';
  END IF;

  -- Authorization rules:
  -- 1. asha_worker: must be the original submitter (auth.uid() = submitted_by)
  --    AND belong to the same facility (if facility_id is non-null).
  -- 2. doctor / facility_admin / admin: must have a non-null facility_id matching
  --    the case's facility_id.
  -- 3. super_admin: global access.
  IF v_role = 'asha_worker' THEN
    IF v_case.submitted_by IS DISTINCT FROM auth.uid() THEN
      RAISE EXCEPTION 'asha_worker can only revoke consent for own submitted cases' USING ERRCODE = '42501';
    END IF;
    IF v_case.facility_id IS NOT NULL AND v_own_facility IS DISTINCT FROM v_case.facility_id THEN
      RAISE EXCEPTION 'cross-facility revocation denied' USING ERRCODE = '42501';
    END IF;
  ELSIF v_role IN ('doctor', 'facility_admin', 'admin') THEN
    IF v_own_facility IS NULL OR v_own_facility IS DISTINCT FROM v_case.facility_id THEN
      RAISE EXCEPTION 'cross-facility erasure denied' USING ERRCODE = '42501';
    END IF;
  ELSIF v_role <> 'super_admin' THEN
    RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
  END IF;

  -- Idempotency check
  IF v_case.deleted_at IS NOT NULL AND v_case.patient_name = v_redacted THEN
    RETURN jsonb_build_object(
      'status', 'already_revoked',
      'case_id', v_case.id,
      'client_id', v_case.client_id,
      'facility_id', v_case.facility_id
    );
  END IF;

  -- Scrub narrative fields in briefing JSONB while preserving non-PHI structure
  IF v_case.briefing IS NOT NULL AND jsonb_typeof(v_case.briefing) = 'object' THEN
    v_new_briefing := jsonb_build_object(
      'triage_level', v_case.briefing -> 'triage_level',
      'primary_risk_driver', to_jsonb(v_redacted),
      'differential_diagnoses', jsonb_build_array(v_redacted),
      'red_flags', jsonb_build_array(v_redacted),
      'recommended_immediate_actions', COALESCE(v_case.briefing -> 'recommended_immediate_actions', '[]'::jsonb),
      'recommended_tests', COALESCE(v_case.briefing -> 'recommended_tests', '[]'::jsonb),
      'uncertainty_flags', to_jsonb(v_redacted),
      'disclaimer', v_case.briefing -> 'disclaimer',
      'llm_status', to_jsonb('redacted_dsr'::text),
      'needs_review', to_jsonb(false)
    );
  ELSE
    v_new_briefing := v_case.briefing;
  END IF;

  UPDATE public.case_records
  SET patient_name = v_redacted,
      patient_location = v_redacted,
      chief_complaint = v_redacted,
      observations = v_redacted,
      known_conditions = v_redacted,
      current_medications = v_redacted,
      human_review_reason = v_redacted,
      doctor_notes = CASE WHEN doctor_notes IS NOT NULL THEN v_redacted ELSE NULL END,
      override_reason = CASE WHEN override_reason IS NOT NULL THEN v_redacted ELSE NULL END,
      briefing = v_new_briefing,
      deleted_at = COALESCE(deleted_at, now()),
      updated_at = now()
  WHERE id = p_case_id;

  UPDATE public.referrals
  SET reason = v_redacted,
      sbar_draft = v_redacted,
      updated_at = now()
  WHERE case_id = p_case_id;

  DELETE FROM public.case_attachments
  WHERE case_id = p_case_id;

  IF v_case.client_id IS NOT NULL THEN
    DELETE FROM public.client_events
    WHERE event_id = v_case.client_id;
  END IF;

  RETURN jsonb_build_object(
    'status', 'erased',
    'case_id', v_case.id,
    'client_id', v_case.client_id,
    'facility_id', v_case.facility_id
  );
END;
$$;

REVOKE ALL ON FUNCTION public.fn_erase_case_pii(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fn_erase_case_pii(uuid) TO authenticated;

-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 4. [BUG-54] Facility-Scoped Longitudinal Trajectory RPC
--    fn_patient_recent_trajectory(p_patient_key text, p_limit integer)
--    Allows an ASHA worker or clinician to retrieve the trailing N de-identified
--    vital/triage trajectory rows for a returning patient within their own
--    facility, even when prior visits were recorded by a shift colleague.
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.fn_patient_recent_trajectory(
  p_patient_key text,
  p_limit integer DEFAULT 3
)
RETURNS TABLE (
  id uuid,
  created_at timestamptz,
  triage_level text,
  bp_systolic integer,
  bp_diastolic integer,
  spo2 integer,
  heart_rate integer,
  respiratory_rate integer,
  temperature numeric,
  chief_complaint text
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_role text;
  v_own_facility uuid;
  v_capped_limit integer := LEAST(GREATEST(COALESCE(p_limit, 3), 1), 10);
BEGIN
  IF p_patient_key IS NULL OR length(trim(p_patient_key)) = 0 THEN
    RETURN;
  END IF;

  SELECT p.role, p.facility_id INTO v_role, v_own_facility
  FROM public.profiles p
  WHERE p.id = auth.uid() AND p.is_active = true;

  IF v_role IS NULL THEN
    RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
  END IF;

  IF v_role = 'super_admin' THEN
    RETURN QUERY
    SELECT cr.id, cr.created_at, cr.triage_level, cr.bp_systolic, cr.bp_diastolic,
           cr.spo2, cr.heart_rate, cr.respiratory_rate, cr.temperature, cr.chief_complaint
    FROM public.case_records cr
    WHERE cr.patient_key = p_patient_key
      AND cr.deleted_at IS NULL
    ORDER BY cr.created_at DESC
    LIMIT v_capped_limit;
  ELSIF v_own_facility IS NOT NULL THEN
    RETURN QUERY
    SELECT cr.id, cr.created_at, cr.triage_level, cr.bp_systolic, cr.bp_diastolic,
           cr.spo2, cr.heart_rate, cr.respiratory_rate, cr.temperature, cr.chief_complaint
    FROM public.case_records cr
    WHERE cr.patient_key = p_patient_key
      AND cr.facility_id = v_own_facility
      AND cr.deleted_at IS NULL
    ORDER BY cr.created_at DESC
    LIMIT v_capped_limit;
  ELSE
    RETURN QUERY
    SELECT cr.id, cr.created_at, cr.triage_level, cr.bp_systolic, cr.bp_diastolic,
           cr.spo2, cr.heart_rate, cr.respiratory_rate, cr.temperature, cr.chief_complaint
    FROM public.case_records cr
    WHERE cr.patient_key = p_patient_key
      AND cr.submitted_by = auth.uid()
      AND cr.deleted_at IS NULL
    ORDER BY cr.created_at DESC
    LIMIT v_capped_limit;
  END IF;
END;
$$;

REVOKE ALL ON FUNCTION public.fn_patient_recent_trajectory(text, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fn_patient_recent_trajectory(text, integer) TO authenticated;

-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 5. [BUG-51] Align Remaining RLS Policies with Two-Tier Admin Model
--    Scopes PHC 'admin' to p.facility_id across INSERT/UPDATE/DELETE on
--    case_records and SELECT/INSERT/UPDATE on referrals, reserving global
--    cross-facility mutation privileges strictly for 'super_admin'.
-- ═══════════════════════════════════════════════════════════════════════════

DROP POLICY IF EXISTS case_records_insert_policy ON public.case_records;
CREATE POLICY case_records_insert_policy ON public.case_records
  FOR INSERT TO authenticated
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND submitted_by = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.is_active = true
        AND (
          p.role = 'super_admin'::text
          OR p.facility_id = case_records.facility_id
        )
    )
  );

DROP POLICY IF EXISTS case_records_update_policy ON public.case_records;
CREATE POLICY case_records_update_policy ON public.case_records
  FOR UPDATE TO authenticated
  USING (
    auth.uid() IS NOT NULL
    AND deleted_at IS NULL
    AND (
      EXISTS (
        SELECT 1 FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.is_active = true
          AND p.role = ANY (ARRAY['doctor'::text, 'facility_admin'::text, 'admin'::text, 'super_admin'::text])
          AND (
            p.role = 'super_admin'::text
            OR p.facility_id = case_records.facility_id
          )
      )
      OR submitted_by = auth.uid()
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL AND (
      reviewed_by IS NULL
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

DROP POLICY IF EXISTS case_records_delete_policy ON public.case_records;
CREATE POLICY case_records_delete_policy ON public.case_records
  FOR DELETE TO authenticated
  USING (
    auth.uid() IS NOT NULL AND (
      auth.uid() = submitted_by
      OR EXISTS (
        SELECT 1 FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.is_active = true
          AND p.role = ANY (ARRAY['admin'::text, 'super_admin'::text])
          AND (
            p.role = 'super_admin'::text
            OR p.facility_id = case_records.facility_id
          )
      )
    )
  );

DROP POLICY IF EXISTS referrals_select_policy ON public.referrals;
CREATE POLICY referrals_select_policy ON public.referrals
  FOR SELECT TO authenticated
  USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.is_active = true
        AND (
          p.role = 'super_admin'::text
          OR p.facility_id IN (referring_facility_id, receiving_facility_id)
        )
    )
  );

DROP POLICY IF EXISTS referrals_insert_policy ON public.referrals;
CREATE POLICY referrals_insert_policy ON public.referrals
  FOR INSERT TO authenticated
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND referred_by = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.is_active = true
        AND p.role = ANY (ARRAY['doctor'::text, 'admin'::text, 'super_admin'::text])
        AND (p.role = 'super_admin'::text OR p.facility_id = referring_facility_id)
    )
    AND EXISTS (
      SELECT 1 FROM public.case_records cr
      WHERE cr.id = case_id
        AND cr.facility_id = referring_facility_id
        AND cr.deleted_at IS NULL
    )
  );

DROP POLICY IF EXISTS referrals_update_policy ON public.referrals;
CREATE POLICY referrals_update_policy ON public.referrals
  FOR UPDATE TO authenticated
  USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.is_active = true
        AND (
          p.role = 'super_admin'::text
          OR (p.role = ANY (ARRAY['doctor'::text, 'admin'::text]) AND p.facility_id = receiving_facility_id)
        )
    )
  );

-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 6. [BUG-56] Align fn_triage_metrics with Two-Tier RBAC & Supervisor Scope
--    Permits 'admin', 'super_admin', and 'supervisor' to query aggregate
--    triage metrics without failing with 42501 insufficient_privilege.
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.fn_triage_metrics()
RETURNS TABLE(triage_level text, count bigint)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_role text;
  v_own_facility uuid;
BEGIN
  SELECT p.role, p.facility_id INTO v_role, v_own_facility
  FROM public.profiles p WHERE p.id = auth.uid() AND p.is_active = true;

  IF v_role IS NULL OR v_role NOT IN ('admin', 'super_admin', 'supervisor') THEN
    RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
  END IF;

  IF v_role IN ('super_admin', 'supervisor') THEN
    RETURN QUERY
    SELECT cr.triage_level, count(*)::bigint
    FROM public.case_records cr
    WHERE cr.deleted_at IS NULL
      AND cr.triage_level IS NOT NULL
    GROUP BY cr.triage_level;
  ELSE
    RETURN QUERY
    SELECT cr.triage_level, count(*)::bigint
    FROM public.case_records cr
    WHERE cr.deleted_at IS NULL
      AND cr.facility_id = v_own_facility
      AND cr.triage_level IS NOT NULL
    GROUP BY cr.triage_level;
  END IF;
END;
$$;

REVOKE ALL ON FUNCTION public.fn_triage_metrics() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fn_triage_metrics() TO authenticated;

COMMIT;
