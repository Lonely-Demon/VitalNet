-- Phase 47: Restrict fn_schema_fingerprint to service_role and add fn_list_policies
-- for structured drift reporting (VN-2026-08-C3-06, Phase 6).
--
-- Restricts schema introspection functions from authenticated non-service callers,
-- ensuring fingerprint and policy listings are only executable by CI and service_role.

BEGIN;

-- 1. Restrict fn_schema_fingerprint
REVOKE EXECUTE ON FUNCTION public.fn_schema_fingerprint() FROM authenticated;
REVOKE EXECUTE ON FUNCTION public.fn_schema_fingerprint() FROM anon;
GRANT EXECUTE ON FUNCTION public.fn_schema_fingerprint() TO service_role;

-- 2. Create fn_list_policies for structured drift reporting in CI
CREATE OR REPLACE FUNCTION public.fn_list_policies()
RETURNS TABLE (
  tablename text,
  policyname text,
  cmd text,
  qual text,
  with_check text
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF auth.role() IS DISTINCT FROM 'service_role' THEN
    RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
  END IF;

  RETURN QUERY
  SELECT
    p.tablename::text,
    p.policyname::text,
    p.cmd::text,
    p.qual::text,
    p.with_check::text
  FROM pg_policies p
  WHERE p.schemaname = 'public'
  ORDER BY p.tablename, p.policyname;
END;
$$;

REVOKE ALL ON FUNCTION public.fn_list_policies() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.fn_list_policies() FROM authenticated, anon;
GRANT EXECUTE ON FUNCTION public.fn_list_policies() TO service_role;

COMMIT;
