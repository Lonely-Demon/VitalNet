-- Phase 30: fn_triage_metrics — the one business metric GET /api/metrics
-- (Round 6 rebuild plan, Phase 3) can serve without a new write path.
-- Idempotent — safe to run multiple times.
--
-- app/core/metrics.py's Prometheus counters (vitalnet_http_requests_total,
-- vitalnet_http_request_duration_seconds, vitalnet_triage_classifications_total)
-- live in the FastAPI process's in-memory prometheus_client registry — a
-- model that assumes a long-running process. It does not translate to an
-- edge isolate, which is recycled unpredictably between invocations; an
-- in-Deno-memory counter would silently reset on every cold start and
-- report near-meaningless numbers.
--
-- Of the three metrics, only vitalnet_triage_classifications_total has a
-- real, already-persisted data source with no new write infrastructure
-- needed: case_records.triage_level. This function exposes it as a
-- cumulative all-time count per tier (a Prometheus Counter's actual
-- semantic — ever-increasing since the series began — arguably a BETTER
-- fit here than the old in-process counter, which reset on every deploy).
--
-- HTTP request-rate/latency (vitalnet_http_requests_total,
-- vitalnet_http_request_duration_seconds) are deliberately NOT ported
-- here: recording those per-request would mean a synchronous Postgres
-- write on every single API call, a real latency/cost regression versus
-- an in-process increment, and needs its own design pass (a dedicated
-- counter table + batched/async writes, or relying on the platform-level
-- invocation metrics Supabase Edge Functions already emit). Tracked as a
-- known, deliberate gap — apps/api/README.md — not a silent omission.

BEGIN;

CREATE OR REPLACE FUNCTION public.fn_triage_metrics()
RETURNS TABLE(triage_level text, count bigint)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_role text;
BEGIN
  SELECT p.role INTO v_role FROM public.profiles p WHERE p.id = auth.uid() AND p.is_active;
  IF v_role IS DISTINCT FROM 'admin' THEN
    RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
  END IF;

  RETURN QUERY
  SELECT cr.triage_level, count(*)::bigint
  FROM public.case_records cr
  WHERE cr.deleted_at IS NULL
    AND cr.triage_level IS NOT NULL
  GROUP BY cr.triage_level;
END;
$$;

REVOKE ALL ON FUNCTION public.fn_triage_metrics() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fn_triage_metrics() TO authenticated;

COMMIT;
