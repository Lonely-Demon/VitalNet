-- Phase 40: Supervisor global aggregate scope correction for fn_team_metrics and fn_outbreak_signal_counts
-- (DECISIONS.md §39 / Round 6 rebuild plan Phase 4)
--
-- Aligns phase 28's SECURITY DEFINER aggregate functions with the agreed
-- two-tier governance RBAC model:
--   - Supervisor: organisation-wide aggregate scope by default (p_facility_id = NULL).
--     Does NOT require a facility_id on their profile. A caller-supplied
--     p_facility_id parameter narrows the aggregate query to that PHC.
--   - PHC Administrator ('admin'): strictly scoped to their resolved own facility
--     (v_own_facility). Any passed p_facility_id parameter is ignored/overwritten.
--   - Doctor: scoped to own facility for fn_outbreak_signal_counts; denied for fn_team_metrics.
--   - ASHA Worker: denied execution for both aggregate functions.
--
-- Idempotent — safe to re-run.

BEGIN;

-- ═══════════════════════════════════════════════════════════════════════
-- fn_team_metrics — supervisor_routes.py's per-ASHA-worker aggregate
-- ═══════════════════════════════════════════════════════════════════════
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
  FROM public.profiles p WHERE p.id = auth.uid() AND p.is_active;

  IF v_role NOT IN ('supervisor', 'admin') THEN
    RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
  END IF;

  -- Supervisor is global by default (p_facility_id = NULL means organisation-wide).
  -- A caller-supplied p_facility_id UUID narrows the aggregate scope for a Supervisor.
  -- PHC Administrator ('admin') is strictly pinned to their resolved own facility.
  IF v_role = 'admin' THEN
    IF v_own_facility IS NULL THEN
      RAISE EXCEPTION 'account has no facility assigned' USING ERRCODE = '22023';
    END IF;
    p_facility_id := v_own_facility;
  END IF;

  IF p_since IS NULL THEN
    RAISE EXCEPTION 'fn_team_metrics: p_since is required';
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

-- ═══════════════════════════════════════════════════════════════════════
-- fn_outbreak_signal_counts — outbreak_routes.py's EARS C1 signal query
-- ═══════════════════════════════════════════════════════════════════════
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
  FROM public.profiles p WHERE p.id = auth.uid() AND p.is_active;

  IF v_role NOT IN ('doctor', 'supervisor', 'admin') THEN
    RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
  END IF;

  -- Supervisor is global by default (p_facility_id = NULL means organisation-wide).
  -- A caller-supplied p_facility_id UUID narrows the aggregate scope for a Supervisor.
  -- Doctor and PHC Administrator ('admin') are strictly pinned to their resolved own facility.
  IF v_role IN ('doctor', 'admin') THEN
    IF v_own_facility IS NULL THEN
      RAISE EXCEPTION 'account has no facility assigned' USING ERRCODE = '22023';
    END IF;
    p_facility_id := v_own_facility;
  END IF;

  IF p_since IS NULL THEN
    RAISE EXCEPTION 'fn_outbreak_signal_counts: p_since is required';
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

COMMIT;
