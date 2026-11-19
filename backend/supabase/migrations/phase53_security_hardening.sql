-- backend/supabase/migrations/phase53_security_hardening.sql
-- Phase 53: Security Hardening & Parity Fixes (VN-53-06 through VN-53-12)
-- Enforces facility pinning on case updates even when unreviewed, supervisor denial on consent revocation,
-- fn_deterioration_count window ceiling and role guards, two-tier facility scoping on metrics RPCs,
-- profiles_insert_own self-registration guard, fixed 4-hour rate-limit horizon,
-- and two-tier facility scoping + is_active checks on ancillary tables.
-- Idempotent — safe to re-run. Compatible with db-schema-drift.yml.

BEGIN;

-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 1. [VN-53-06] Enforce Facility Pinning on case_records_update_policy
--    Removes the reviewed_by IS NULL short-circuit that permitted unreviewed
--    cases to be updated without verifying facility tenancy on the updater.
-- ═══════════════════════════════════════════════════════════════════════════

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
          AND (p.role = 'super_admin'::text OR p.facility_id = case_records.facility_id)
      )
      OR (submitted_by = auth.uid())
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND (
      EXISTS (
        SELECT 1 FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.is_active = true
          AND (
            p.role = 'super_admin'::text
            OR p.facility_id = case_records.facility_id
            OR (case_records.submitted_by = auth.uid() AND (p.facility_id IS NULL OR p.facility_id = case_records.facility_id))
          )
      )
    )
  );

-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 2. [VN-53-07] Consent Revocation & Erasure Supervisor Denial
--    Explicitly denies supervisor from invoking fn_erase_case_pii.
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

  -- Explicit supervisor denial (VN-53-07): supervisor is aggregate-only analytics role
  IF v_role = 'supervisor' THEN
    RAISE EXCEPTION 'insufficient_privilege: supervisor role cannot perform DSR erasure or consent revocation' USING ERRCODE = '42501';
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
-- SECTION 3. [VN-53-08] fn_deterioration_count Window Ceiling & Role Check
--    Enforces window ceiling (1 to 30 days) and restricts execution to
--    clinical/admin roles ('asha_worker', 'doctor', 'facility_admin', 'admin', 'super_admin').
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.fn_deterioration_count(
  p_patient_key text,
  p_current_triage_level text,
  p_window_days integer DEFAULT 7
)
RETURNS TABLE(has_pattern boolean, visit_count integer)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_caller_active boolean;
  v_role text;
  v_prior_count integer;
  v_total integer;
BEGIN
  SELECT p.is_active, p.role INTO v_caller_active, v_role
  FROM public.profiles p WHERE p.id = auth.uid();

  IF v_caller_active IS NOT TRUE OR v_role IS NULL OR v_role NOT IN ('asha_worker', 'doctor', 'facility_admin', 'admin', 'super_admin') THEN
    RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
  END IF;

  IF p_window_days IS NULL OR p_window_days < 1 OR p_window_days > 30 THEN
    RAISE EXCEPTION 'fn_deterioration_count: p_window_days must be between 1 and 30' USING ERRCODE = '22023';
  END IF;

  IF p_patient_key IS NULL THEN
    RETURN QUERY SELECT false, NULL::integer;
    RETURN;
  END IF;

  SELECT count(*) INTO v_prior_count
  FROM public.case_records cr
  WHERE cr.patient_key = p_patient_key
    AND cr.created_at >= now() - make_interval(days => p_window_days)
    AND cr.triage_level IN ('URGENT', 'EMERGENCY')
    AND cr.deleted_at IS NULL;

  v_total := v_prior_count + (CASE WHEN p_current_triage_level IN ('URGENT', 'EMERGENCY') THEN 1 ELSE 0 END);

  RETURN QUERY SELECT (v_total >= 2), (CASE WHEN v_total >= 2 THEN v_total ELSE NULL END);
END;
$$;

REVOKE ALL ON FUNCTION public.fn_deterioration_count(text, text, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fn_deterioration_count(text, text, integer) TO authenticated;

-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 4. [VN-53-09] Two-Tier Alignment & Null Facility Guards on Metrics RPCs
--    Enforces that 'admin', 'facility_admin', and 'supervisor' are pinned to
--    v_own_facility and fail closed with 22023 if unassigned, while 'super_admin'
--    retains system-wide analytics access.
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.fn_team_metrics(
  p_facility_id uuid DEFAULT NULL,
  p_since timestamptz DEFAULT NULL
)
RETURNS TABLE(
  submitted_by uuid,
  full_name text,
  triage_level text,
  needs_review boolean,
  contraindication_flags jsonb,
  deterioration_alert boolean
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
  FROM public.profiles p WHERE p.id = auth.uid() AND p.is_active = true;

  IF v_role IS NULL OR v_role NOT IN ('supervisor', 'facility_admin', 'admin', 'super_admin') THEN
    RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
  END IF;

  -- Only super_admin may query system-wide without a facility.
  -- All other roles require an assigned facility and are strictly pinned to it.
  IF v_role <> 'super_admin' THEN
    IF v_own_facility IS NULL THEN
      RAISE EXCEPTION 'account has no facility assigned' USING ERRCODE = '22023';
    END IF;
    p_facility_id := v_own_facility;
  END IF;

  IF p_since IS NULL THEN
    RAISE EXCEPTION 'fn_team_metrics: p_since is required' USING ERRCODE = '22023';
  END IF;

  RETURN QUERY
  SELECT cr.submitted_by, pr.full_name, cr.triage_level, cr.needs_review,
         cr.contraindication_flags, cr.deterioration_alert
  FROM public.case_records cr
  LEFT JOIN public.profiles pr ON pr.id = cr.submitted_by
  WHERE cr.deleted_at IS NULL
    AND cr.created_at >= p_since
    AND (p_facility_id IS NULL OR cr.facility_id = p_facility_id);
END;
$$;

REVOKE ALL ON FUNCTION public.fn_team_metrics(uuid, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fn_team_metrics(uuid, timestamptz) TO authenticated;

CREATE OR REPLACE FUNCTION public.fn_outbreak_signal_counts(
  p_facility_id uuid DEFAULT NULL,
  p_since timestamptz DEFAULT NULL
)
RETURNS TABLE(facility_id uuid, symptoms jsonb, created_at timestamptz)
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

  IF v_role IS NULL OR v_role NOT IN ('doctor', 'supervisor', 'admin', 'facility_admin', 'super_admin') THEN
    RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
  END IF;

  -- Only super_admin may query across all facilities.
  -- All other roles require an assigned facility and are strictly pinned to it.
  IF v_role <> 'super_admin' THEN
    IF v_own_facility IS NULL THEN
      RAISE EXCEPTION 'account has no facility assigned' USING ERRCODE = '22023';
    END IF;
    p_facility_id := v_own_facility;
  END IF;

  IF p_since IS NULL THEN
    RAISE EXCEPTION 'fn_outbreak_signal_counts: p_since is required' USING ERRCODE = '22023';
  END IF;

  RETURN QUERY
  SELECT cr.facility_id, to_jsonb(cr.symptoms) AS symptoms, cr.created_at
  FROM public.case_records cr
  WHERE cr.deleted_at IS NULL
    AND cr.created_at >= p_since
    AND (p_facility_id IS NULL OR cr.facility_id = p_facility_id);
END;
$$;

REVOKE ALL ON FUNCTION public.fn_outbreak_signal_counts(uuid, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fn_outbreak_signal_counts(uuid, timestamptz) TO authenticated;

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

  IF v_role IS NULL OR v_role NOT IN ('admin', 'facility_admin', 'super_admin', 'supervisor') THEN
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
    IF v_own_facility IS NULL THEN
      RAISE EXCEPTION 'account has no facility assigned' USING ERRCODE = '22023';
    END IF;
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

-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 5. [VN-53-10] profiles_insert_own RLS Policy
--    Restricts profile self-registration to non-privileged inactive roles.
-- ═══════════════════════════════════════════════════════════════════════════

DROP POLICY IF EXISTS profiles_insert_own ON public.profiles;
CREATE POLICY profiles_insert_own ON public.profiles
  FOR INSERT TO authenticated
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND id = auth.uid()
    AND role = ANY (ARRAY['asha_worker'::text, 'doctor'::text])
    AND is_active = false
  );

-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 6. [VN-53-11] fn_rate_limit 4-Hour Fixed Cleanup Horizon
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.fn_rate_limit(
  p_key text,
  p_max integer,
  p_window_s integer
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_window_start timestamptz;
  v_count integer;
BEGIN
  IF p_key IS NULL OR length(p_key) = 0 THEN
    RAISE EXCEPTION 'fn_rate_limit: key must not be empty';
  END IF;
  IF p_max IS NULL OR p_max < 1 OR p_window_s IS NULL OR p_window_s < 1 THEN
    RAISE EXCEPTION 'fn_rate_limit: max and window_s must be positive';
  END IF;

  v_window_start := to_timestamp(floor(extract(epoch FROM now()) / p_window_s) * p_window_s);

  INSERT INTO public.rate_limit_counters (key, window_start, count)
  VALUES (p_key, v_window_start, 1)
  ON CONFLICT (key, window_start) DO UPDATE SET count = rate_limit_counters.count + 1
  RETURNING count INTO v_count;

  -- Opportunistic cleanup of stale windows on ~1% of calls (fixed 4-hour horizon)
  IF random() < 0.01 THEN
    DELETE FROM public.rate_limit_counters
    WHERE window_start < now() - interval '4 hours';
  END IF;

  RETURN v_count <= p_max;
END;
$$;

REVOKE ALL ON FUNCTION public.fn_rate_limit(text, integer, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fn_rate_limit(text, integer, integer) TO anon, authenticated;

-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 7. [VN-53-12] Two-Tier Scoping & is_active on Ancillary Tables
-- ═══════════════════════════════════════════════════════════════════════════

-- 7.1 case_outcomes
DROP POLICY IF EXISTS case_outcomes_select_policy ON public.case_outcomes;
CREATE POLICY case_outcomes_select_policy ON public.case_outcomes
  FOR SELECT TO authenticated
  USING (
    auth.uid() IS NOT NULL
    AND (
      recorded_by = auth.uid()
      OR EXISTS (
        SELECT 1
        FROM public.case_records cr
        JOIN public.profiles p ON p.id = auth.uid()
        WHERE cr.id = case_outcomes.case_id
          AND p.is_active = true
          AND (
            p.role = 'super_admin'::text
            OR (p.role = ANY (ARRAY['doctor'::text, 'admin'::text, 'facility_admin'::text]) AND p.facility_id = cr.facility_id)
          )
      )
    )
  );

-- 7.2 case_reviews
DROP POLICY IF EXISTS case_reviews_select_policy ON public.case_reviews;
CREATE POLICY case_reviews_select_policy ON public.case_reviews
  FOR SELECT TO authenticated
  USING (
    auth.uid() IS NOT NULL
    AND (
      reviewer_id = auth.uid()
      OR EXISTS (
        SELECT 1
        FROM public.case_records cr
        JOIN public.profiles p ON p.id = auth.uid()
        WHERE cr.id = case_reviews.case_id
          AND p.is_active = true
          AND (
            p.role = 'super_admin'::text
            OR (p.role = ANY (ARRAY['doctor'::text, 'admin'::text, 'facility_admin'::text]) AND p.facility_id = cr.facility_id)
          )
      )
    )
  );

DROP POLICY IF EXISTS case_reviews_insert_policy ON public.case_reviews;
CREATE POLICY case_reviews_insert_policy ON public.case_reviews
  FOR INSERT TO authenticated
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND reviewer_id = auth.uid()
    AND EXISTS (
      SELECT 1
      FROM public.case_records cr
      JOIN public.profiles p ON p.id = auth.uid()
      WHERE cr.id = case_reviews.case_id
        AND p.is_active = true
        AND p.role = ANY (ARRAY['doctor'::text, 'admin'::text, 'facility_admin'::text, 'super_admin'::text])
        AND (p.role = 'super_admin'::text OR p.facility_id = cr.facility_id)
    )
  );

-- 7.3 case_attachments
DROP POLICY IF EXISTS case_attachments_select_policy ON public.case_attachments;
CREATE POLICY case_attachments_select_policy ON public.case_attachments
  FOR SELECT TO authenticated
  USING (
    auth.uid() IS NOT NULL
    AND (
      uploaded_by = auth.uid()
      OR EXISTS (
        SELECT 1
        FROM public.case_records cr
        JOIN public.profiles p ON p.id = auth.uid()
        WHERE cr.id = case_attachments.case_id
          AND p.is_active = true
          AND (
            p.role = 'super_admin'::text
            OR (p.role = ANY (ARRAY['doctor'::text, 'admin'::text, 'facility_admin'::text]) AND p.facility_id = cr.facility_id)
            OR cr.submitted_by = auth.uid()
          )
      )
    )
  );

DROP POLICY IF EXISTS case_attachments_insert_policy ON public.case_attachments;
CREATE POLICY case_attachments_insert_policy ON public.case_attachments
  FOR INSERT TO authenticated
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND uploaded_by = auth.uid()
    AND EXISTS (
      SELECT 1
      FROM public.case_records cr
      JOIN public.profiles p ON p.id = auth.uid()
      WHERE cr.id = case_attachments.case_id
        AND p.is_active = true
        AND (
          p.role = 'super_admin'::text
          OR (p.role = ANY (ARRAY['doctor'::text, 'admin'::text, 'facility_admin'::text]) AND p.facility_id = cr.facility_id)
          OR cr.submitted_by = auth.uid()
        )
    )
  );

-- 7.4 client_events
DROP POLICY IF EXISTS client_events_select_policy ON public.client_events;
CREATE POLICY client_events_select_policy ON public.client_events
  FOR SELECT TO authenticated
  USING (
    auth.uid() IS NOT NULL
    AND (
      submitted_by = auth.uid()
      OR EXISTS (
        SELECT 1 FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.is_active = true
          AND (
            p.role = 'super_admin'::text
            OR (
              p.role = ANY (ARRAY['admin'::text, 'facility_admin'::text])
              AND EXISTS (
                SELECT 1 FROM public.profiles sub_p
                WHERE sub_p.id = client_events.submitted_by
                  AND sub_p.facility_id = p.facility_id
              )
            )
          )
      )
    )
  );

-- 7.5 referrals
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
          OR (p.role = ANY (ARRAY['doctor'::text, 'admin'::text, 'facility_admin'::text]) AND p.facility_id = receiving_facility_id)
        )
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.is_active = true
        AND (
          p.role = 'super_admin'::text
          OR (p.role = ANY (ARRAY['doctor'::text, 'admin'::text, 'facility_admin'::text]) AND p.facility_id = receiving_facility_id)
        )
    )
  );

-- 7.6 phi_audit_log
DROP POLICY IF EXISTS phi_audit_log_insert_authenticated ON public.phi_audit_log;
CREATE POLICY phi_audit_log_insert_authenticated ON public.phi_audit_log
  FOR INSERT TO authenticated
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND user_id = auth.uid()
  );

COMMIT;
