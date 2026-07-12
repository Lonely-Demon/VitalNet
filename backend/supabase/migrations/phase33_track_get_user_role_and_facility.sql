-- Phase 33: Track get_user_role(uuid)/get_user_facility(uuid) for the
-- first time. These functions exist on the live project — called by
-- profiles_select_policy_hardened — but appeared in NO tracked migration
-- anywhere in this repo (discovered via the schema-drift testing pass,
-- docs/DECISIONS.md). Their real definitions were pulled from the live
-- project via pg_get_functiondef() and verified to do a plain
-- SECURITY DEFINER table lookup against public.profiles — no JWT trust,
-- safe as the basis for profiles_select_policy_hardened's authorization.
--
-- CREATE OR REPLACE is idempotent: running this against the live project
-- (which already has these functions) just re-asserts the same
-- definition and starts tracking it. Deliberately no REVOKE/GRANT here —
-- CREATE OR REPLACE FUNCTION preserves an existing function's grants, and
-- this migration doesn't know the live project's current grant state on
-- these two; guessing one and applying it risks narrowing access on a
-- function that's already working in production, which would trade one
-- bug for a worse one.

BEGIN;

CREATE OR REPLACE FUNCTION public.get_user_role(user_id uuid)
 RETURNS text
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  SELECT role FROM public.profiles WHERE id = user_id;
$function$;

CREATE OR REPLACE FUNCTION public.get_user_facility(user_id uuid)
 RETURNS uuid
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  SELECT facility_id FROM public.profiles WHERE id = user_id;
$function$;

COMMIT;
