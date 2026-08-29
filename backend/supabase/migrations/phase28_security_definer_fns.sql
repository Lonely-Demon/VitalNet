-- Phase 28: SECURITY DEFINER functions replacing app-layer supabase_admin
-- aggregate discipline (Round 6 rebuild plan, item 4 / DECISIONS.md §29 §32)
-- Idempotent — safe to run multiple times.
--
-- Four call sites in the FastAPI backend use the service-role client
-- (supabase_admin) for exactly one narrow, documented cross-user aggregate
-- each, because an RLS-scoped user client structurally can't see the
-- other rows it needs to count (cases.py::_check_deterioration_pattern,
-- referral_routes.py's open-case-count-per-facility, supervisor_routes.py's
-- team metrics, outbreak_routes.py's EARS signal query). Each is already a
-- careful, minimal RLS bypass — this migration does not change WHAT data
-- crosses the boundary, only WHERE the bypass and its role check live: in
-- the database, next to the tables it protects, instead of in Python. A
-- SECURITY DEFINER function re-checks the caller's role via auth.uid() on
-- every call (SECURITY DEFINER runs with the function owner's privileges,
-- bypassing RLS entirely — this internal check is not optional), so the
-- edge functions (Phase 3/4) and the legacy backend can both call these
-- via .rpc() as an ordinary authenticated user, no service-role key needed.
-- Net effect: service-role usage shrinks to /api/admin + phi_audit_log
-- writes only, per the Phase 2 plan.
--
-- Also adds fn_rate_limit (a Postgres-backed token-bucket counter) so the
-- Phase 3 Deno edge functions have a rate limiter that doesn't depend on
-- in-process state (slowapi's in-memory store doesn't survive an edge
-- isolate being recycled), and fn_schema_fingerprint (admin/service-role
-- only) for the CI/scheduled drift-detection job that catches untracked
-- live schema changes — exactly the class of incident DECISIONS.md §25
-- already documents happening once (an undocumented profiles_role_check
-- CHECK constraint change made directly against the live database).
--
-- CAVEAT: this repo's earliest tracked migration is phase10 — the base
-- tables (profiles, case_records, facilities) predate migration tracking
-- (DECISIONS.md §25, §29) and their exact column types are inferred here
-- from application code (app/api/routes/*.py), not read from a live
-- schema dump. Dry-run this migration against a staging clone of the real
-- database before applying to production; if a referenced column's name
-- or type differs from what's assumed below, this migration will fail
-- loudly (inside its own transaction, so it will not partially apply)
-- rather than silently misbehave.

BEGIN;

-- ═══════════════════════════════════════════════════════════════════════
-- fn_deterioration_count — cases.py::_check_deterioration_pattern
-- ═══════════════════════════════════════════════════════════════════════
-- Any authenticated caller with an active profile may call this: a
-- patient_key carries no PII (DECISIONS.md §22), and the ASHA worker
-- submitting THIS case is already trusted to reason about whether this
-- same patient has recently had repeated severe visits across workers.

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
  v_prior_count integer;
  v_total integer;
BEGIN
  SELECT p.is_active INTO v_caller_active FROM public.profiles p WHERE p.id = auth.uid();
  IF v_caller_active IS NOT TRUE THEN
    RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
  END IF;

  IF p_window_days IS NULL OR p_window_days < 1 THEN
    RAISE EXCEPTION 'fn_deterioration_count: p_window_days must be positive';
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

-- ═══════════════════════════════════════════════════════════════════════
-- fn_open_case_counts — referral_routes.py's facility-list open-case load
-- ═══════════════════════════════════════════════════════════════════════
-- Deliberately global (no facility scoping): a doctor choosing WHERE to
-- refer needs every candidate facility's load, not just their own. Never
-- returns patient data, free text, or individual case rows — counts only.

CREATE OR REPLACE FUNCTION public.fn_open_case_counts()
RETURNS TABLE(facility_id uuid, open_count bigint)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_role text;
BEGIN
  SELECT p.role INTO v_role FROM public.profiles p WHERE p.id = auth.uid() AND p.is_active;
  IF v_role IS DISTINCT FROM 'doctor' AND v_role IS DISTINCT FROM 'admin' THEN
    RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
  END IF;

  RETURN QUERY
  SELECT cr.facility_id, count(*)::bigint AS open_count
  FROM public.case_records cr
  WHERE cr.reviewed_at IS NULL
    AND cr.deleted_at IS NULL
    AND cr.facility_id IS NOT NULL
  GROUP BY cr.facility_id;
END;
$$;

REVOKE ALL ON FUNCTION public.fn_open_case_counts() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fn_open_case_counts() TO authenticated;

-- ═══════════════════════════════════════════════════════════════════════
-- fn_team_metrics — supervisor_routes.py's per-ASHA-worker aggregate
-- ═══════════════════════════════════════════════════════════════════════
-- supervisor is pinned to their own facility (p_facility_id is ignored —
-- overwritten with their own); admin may pass NULL for system-wide or a
-- specific facility_id, mirroring app/core/scoping.py::resolve_facility_scope.

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

  IF v_role IS DISTINCT FROM 'supervisor' AND v_role IS DISTINCT FROM 'admin' THEN
    RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
  END IF;

  IF v_role <> 'admin' THEN
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
-- Same scoping rule as fn_team_metrics: doctor/supervisor pinned to their
-- own facility, admin may pass NULL (system-wide) or narrow explicitly.
-- to_jsonb() on symptoms tolerates either a jsonb or a text[] column —
-- verify against the live schema (see the file header caveat) before relying
-- on this in production; it will not silently misbehave either way.

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
  -- Table-qualified: this function's RETURNS TABLE declares a facility_id
  -- OUT parameter, which would otherwise make an unqualified `facility_id`
  -- here ambiguous between that OUT parameter and the profiles column.
  SELECT p.role, p.facility_id INTO v_role, v_own_facility
  FROM public.profiles p WHERE p.id = auth.uid() AND p.is_active;

  IF v_role NOT IN ('doctor', 'supervisor', 'admin') THEN
    RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
  END IF;

  IF v_role <> 'admin' THEN
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

-- ═══════════════════════════════════════════════════════════════════════
-- fn_rate_limit — Postgres-backed token bucket for Phase 3 edge functions
-- ═══════════════════════════════════════════════════════════════════════
-- slowapi's rate-limit store is in-process memory, which doesn't survive
-- an edge isolate being recycled between requests. This fixed-window
-- counter is the Deno-side replacement (called via .rpc(), no service-role
-- key needed). Callable by anon too — rate limiting must apply BEFORE auth
-- resolves (e.g. login attempts), so it cannot require a profiles row.
-- The underlying table is not directly grantable; only this function can
-- touch it, so a caller cannot forge another key's count.

CREATE TABLE IF NOT EXISTS public.rate_limit_counters (
  key text NOT NULL,
  window_start timestamptz NOT NULL,
  count integer NOT NULL DEFAULT 0,
  PRIMARY KEY (key, window_start)
);

REVOKE ALL ON public.rate_limit_counters FROM PUBLIC, anon, authenticated;

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

  -- Opportunistic cleanup of stale windows on ~1% of calls — the table is
  -- naturally self-bounding without a dedicated cron job, and this never
  -- blocks or slows down the caller's own rate-limit check.
  IF random() < 0.01 THEN
    DELETE FROM public.rate_limit_counters
    WHERE window_start < now() - make_interval(secs => p_window_s * 4);
  END IF;

  RETURN v_count <= p_max;
END;
$$;

REVOKE ALL ON FUNCTION public.fn_rate_limit(text, integer, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fn_rate_limit(text, integer, integer) TO anon, authenticated;

-- ═══════════════════════════════════════════════════════════════════════
-- fn_schema_fingerprint — live-schema drift detection (admin/service-role)
-- ═══════════════════════════════════════════════════════════════════════
-- Hashes public-schema columns, constraints, and RLS policies into one
-- md5. The CI drift job (see .github/workflows/ci.yml) computes the same
-- fingerprint from the migrations-applied-in-order snapshot and compares;
-- a scheduled weekly job also calls this live (via the service-role
-- secret) and compares against the last-known-good fingerprint, catching
-- exactly the kind of untracked live change DECISIONS.md §25 recorded
-- (an undocumented profiles_role_check CHECK constraint edit made
-- directly against the database, outside any tracked migration).

CREATE OR REPLACE FUNCTION public.fn_schema_fingerprint()
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_role text;
  v_columns text;
  v_constraints text;
  v_policies text;
BEGIN
  IF auth.role() IS DISTINCT FROM 'service_role' THEN
    SELECT p.role INTO v_role FROM public.profiles p WHERE p.id = auth.uid() AND p.is_active;
    IF v_role IS DISTINCT FROM 'admin' THEN
      RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
    END IF;
  END IF;

  SELECT string_agg(
    table_name || '.' || column_name || ':' || data_type || ':' || is_nullable
      || ':' || coalesce(column_default, '-'),
    ',' ORDER BY table_name, column_name
  ) INTO v_columns
  FROM information_schema.columns
  WHERE table_schema = 'public';

  SELECT string_agg(
    conrelid::regclass::text || '.' || conname || ':' || pg_get_constraintdef(oid),
    ',' ORDER BY conrelid::regclass::text, conname
  ) INTO v_constraints
  FROM pg_constraint
  WHERE connamespace = 'public'::regnamespace;

  SELECT string_agg(
    tablename || '.' || policyname || ':' || cmd || ':' || coalesce(qual, '-') || ':' || coalesce(with_check, '-'),
    ',' ORDER BY tablename, policyname
  ) INTO v_policies
  FROM pg_policies
  WHERE schemaname = 'public';

  RETURN md5(coalesce(v_columns, '') || '|' || coalesce(v_constraints, '') || '|' || coalesce(v_policies, ''));
END;
$$;

REVOKE ALL ON FUNCTION public.fn_schema_fingerprint() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fn_schema_fingerprint() TO authenticated, service_role;

COMMIT;
