-- Phase 35: Re-track profiles_select_policy_hardened to match what's
-- actually live.
--
-- Found during code review of the PR that added this CI job: phase15
-- (backend/supabase/migrations/phase15_data_security_hardening.sql) tracks
-- this policy using an inline self-join EXISTS check against
-- public.profiles. But the live project's actual policy — captured
-- verbatim in backend/supabase/schema_snapshot.sql, a real pg_catalog
-- introspection, not a guess — calls get_user_role(auth.uid())/
-- get_user_facility(auth.uid()) instead. Someone changed this policy
-- directly against the live database at some point, outside any tracked
-- migration. This is exactly the failure mode docs/DECISIONS.md §35/§36
-- already found twice elsewhere (phase28-31 never applied; the JWT-metadata
-- policies) — a third instance, on the same table, caught by comparing the
-- tracked migration history against the live capture line by line.
--
-- Applying this against the live project is a no-op: it reproduces the
-- policy that's already there, verbatim (get_user_role()/get_user_facility()
-- are the same verified-safe SECURITY DEFINER table lookups phase33 tracks).
-- What this actually fixes is `backend/supabase/migrations/` itself:
-- without this, a fresh project bootstrapped from migrations alone (phase10
-- through phase35 in order, the path CODEBASE_MAP.md and apps/api/README.md
-- document for first-time setup) would end up with phase15's stale
-- self-join version instead of the current one — a second, would-be-silent
-- divergence between tracked and live state, introduced by the very
-- migration history meant to prevent that.

BEGIN;

DROP POLICY IF EXISTS profiles_select_policy_hardened ON public.profiles;
CREATE POLICY profiles_select_policy_hardened
  ON public.profiles
  FOR SELECT
  USING (
    (id = auth.uid())
    OR (get_user_role(auth.uid()) = ANY (ARRAY['admin', 'super_admin']))
    OR (
      (get_user_role(auth.uid()) = ANY (ARRAY['doctor', 'facility_admin']))
      AND (get_user_facility(auth.uid()) = facility_id)
    )
  );

COMMIT;
