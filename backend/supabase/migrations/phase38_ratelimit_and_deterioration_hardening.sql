-- Phase 38: Harden two phase28 SECURITY DEFINER functions that were reachable
-- directly via PostgREST RPC with weaker guarantees than intended.
-- Idempotent — safe to run multiple times.
--
-- 1. fn_rate_limit (HIGH — unauthenticated storage-exhaustion vector)
--    Granted EXECUTE to anon, so it is callable as
--    POST /rest/v1/rpc/fn_rate_limit with only the public anon key. The
--    original had no upper bound on p_window_s and no length cap on p_key,
--    and its opportunistic cleanup deletes rows older than 4 * p_window_s —
--    a caller-chosen value. A loop with a huge p_window_s (defeating cleanup
--    entirely) and fresh random/long p_key values grows rate_limit_counters
--    without bound, degrading the shared limiter every endpoint depends on.
--    Fix: bound p_window_s (<= 3600s) and p_max (<= 1e6), cap p_key length
--    (<= 200 chars — real keys are "user:<uuid>" or "ip:<addr>", well under
--    that), and clamp the cleanup horizon so no caller can pin stale rows in
--    memory. Legitimate callers (rateLimit.ts) only ever pass window <= ~300s
--    and keys <= ~50 chars, so none of these bounds affect real traffic.
--
-- 2. fn_deterioration_count (MED — sibling-inconsistent authorization)
--    Every other phase28 SECURITY DEFINER function checks a specific role;
--    this one only checked is_active, so ANY active authenticated user —
--    including a supervisor — could call it with an arbitrary patient_key.
--    supervisor_routes.py documents that a supervisor is deliberately given
--    NO path into case data ("this endpoint is the only sanctioned path"),
--    a guarantee this RPC quietly broke: a supervisor could probe whether a
--    given patient_key has had repeated severe visits. The only legitimate
--    callers are the case-submission path (asha_worker/admin) and doctors
--    (who already have facility-scoped case_records access under RLS). Fix:
--    restrict to those clinical roles, closing the supervisor backdoor while
--    leaving the submit path untouched.

BEGIN;

-- ── fn_rate_limit: bound inputs + clamp cleanup horizon ──────────────────
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
  -- Cap key length: a keyed limiter with unbounded key length lets a caller
  -- write arbitrarily large rows. Real keys are short (user:<uuid>/ip:<addr>).
  IF length(p_key) > 200 THEN
    RAISE EXCEPTION 'fn_rate_limit: key too long';
  END IF;
  IF p_max IS NULL OR p_max < 1 OR p_max > 1000000 THEN
    RAISE EXCEPTION 'fn_rate_limit: max must be between 1 and 1000000';
  END IF;
  -- Bound the window: an unbounded p_window_s makes the cleanup horizon
  -- (4 * p_window_s) unbounded too, so stale rows would never be reclaimed.
  IF p_window_s IS NULL OR p_window_s < 1 OR p_window_s > 3600 THEN
    RAISE EXCEPTION 'fn_rate_limit: window_s must be between 1 and 3600';
  END IF;

  v_window_start := to_timestamp(floor(extract(epoch FROM now()) / p_window_s) * p_window_s);

  INSERT INTO public.rate_limit_counters (key, window_start, count)
  VALUES (p_key, v_window_start, 1)
  ON CONFLICT (key, window_start) DO UPDATE SET count = rate_limit_counters.count + 1
  RETURNING count INTO v_count;

  -- Opportunistic cleanup on ~1% of calls. The retention horizon is now
  -- bounded (p_window_s <= 3600, so at most 4 hours) — no caller can inflate
  -- it to keep rows alive indefinitely. LEAST() is belt-and-suspenders in
  -- case a future caller passes a larger window past the guard above.
  IF random() < 0.01 THEN
    DELETE FROM public.rate_limit_counters
    WHERE window_start < now() - make_interval(secs => LEAST(p_window_s, 3600) * 4);
  END IF;

  RETURN v_count <= p_max;
END;
$$;

REVOKE ALL ON FUNCTION public.fn_rate_limit(text, integer, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fn_rate_limit(text, integer, integer) TO anon, authenticated;

-- ── fn_deterioration_count: restrict to clinical submit-path roles ───────
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
  v_role text;
  v_prior_count integer;
  v_total integer;
BEGIN
  -- Was: is_active-only. Now role-checked, consistent with every sibling
  -- function. asha_worker/admin cover the submission path that legitimately
  -- computes this; doctor is included because doctors already have
  -- facility-scoped case_records access under RLS. supervisor is
  -- deliberately excluded — see the file header and supervisor_routes.py.
  SELECT p.role INTO v_role FROM public.profiles p WHERE p.id = auth.uid() AND p.is_active;
  IF v_role IS NULL OR v_role NOT IN ('asha_worker', 'doctor', 'admin') THEN
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

COMMIT;
