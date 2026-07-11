-- Phase 31: fn_client_event_record — SECURITY DEFINER insert helper for
-- client_events (Round 6 rebuild plan, Phase 5's idempotency middleware,
-- apps/api/supabase/functions/api/_shared/idempotency.ts). client_events
-- has no INSERT policy (phase29_events_and_advisory_model.sql) — RLS
-- default-denies inserts from the authenticated role, the same convention
-- as case_outcomes (immutable audit-trail tables are never directly
-- writable by clients). This function is the one narrow, server-invoked
-- exception: the calling user's own JWT sets submitted_by (never a
-- client-supplied value), so a caller can only ever record events under
-- their own identity.
--
-- The LOOKUP half of the idempotency check does NOT need a function —
-- client_events' existing SELECT policy (submitted_by = auth.uid() OR
-- admin) already lets a caller read back their own prior response through
-- their normal RLS-scoped client; only the write needed this exception.
-- idempotency.ts therefore never touches a service-role client at all.

BEGIN;

CREATE OR REPLACE FUNCTION public.fn_client_event_record(
  p_event_id uuid,
  p_event_type text,
  p_response jsonb
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.client_events (event_id, event_type, submitted_by, response)
  VALUES (p_event_id, p_event_type, auth.uid(), p_response)
  ON CONFLICT (event_id) DO NOTHING;
END;
$$;

REVOKE ALL ON FUNCTION public.fn_client_event_record(uuid, text, jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fn_client_event_record(uuid, text, jsonb) TO authenticated;

COMMIT;
