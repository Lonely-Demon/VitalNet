-- CI-only stubs for Supabase-managed objects that schema_snapshot.sql and
-- the tracked migrations reference but don't (and shouldn't) define
-- themselves — the auth schema is Supabase infrastructure, not something
-- migrations create. Used only by the db-schema-drift workflow to let a
-- fresh Postgres container load the snapshot/migrations; never applied to
-- a real project.
CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE IF NOT EXISTS auth.users (id uuid PRIMARY KEY);

-- Behaviorally accurate, not just present-for-parsing: reads the
-- request.jwt.claims GUC the same way Supabase's real auth schema
-- functions do, so a test that sets that GUC (SELECT
-- set_config('request.jwt.claims', '{"sub":"...", ...}', true)) actually
-- exercises RLS policies the way PostgREST does in production — needed to
-- functionally verify RLS fixes (docs/DECISIONS.md), not just check that
-- CREATE POLICY parses.
CREATE OR REPLACE FUNCTION auth.jwt() RETURNS jsonb LANGUAGE sql STABLE AS $$
  SELECT COALESCE(NULLIF(current_setting('request.jwt.claims', true), ''), '{}')::jsonb
$$;
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT NULLIF(auth.jwt() ->> 'sub', '')::uuid
$$;
-- Real Supabase's auth.role() returns NULL when request.jwt.claims has no
-- 'role' claim (e.g. no GUC set at all) — it does NOT default to 'anon'.
-- Defaulting here would mask a test that forgot to set_config() the claims
-- GUC before simulating a request: against this stub the missing setup
-- would silently read as a legitimate anon request instead of surfacing
-- as the uninitialized-session bug it actually is.
CREATE OR REPLACE FUNCTION auth.role() RETURNS text LANGUAGE sql STABLE AS $$
  SELECT NULLIF(auth.jwt() ->> 'role', '')::text
$$;
-- Real Supabase projects grant USAGE on auth + EXECUTE on these to PUBLIC
-- (every role, not just authenticated/anon) — matched here so RLS
-- policies that call them actually work under a non-superuser role.
GRANT USAGE ON SCHEMA auth TO PUBLIC;
GRANT EXECUTE ON FUNCTION auth.uid() TO PUBLIC;
GRANT EXECUTE ON FUNCTION auth.jwt() TO PUBLIC;
GRANT EXECUTE ON FUNCTION auth.role() TO PUBLIC;

-- authenticated/anon: the two PostgREST-facing roles every real Supabase
-- project has. Needed so a CI check can SET ROLE authenticated the same
-- way PostgREST does per-request, instead of running every query as the
-- postgres superuser — RLS does not apply to superusers or table owners,
-- so a check that never leaves that role would pass regardless of whether
-- any policy actually restricts anything.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN;
  END IF;
END
$$;
-- Real Supabase projects grant schema usage and table-level DML broadly to
-- these roles by default and rely on RLS, not table grants, as the actual
-- access boundary — matched here for the same reason as the auth.* grants
-- above. ALTER DEFAULT PRIVILEGES, not a plain GRANT ON ALL TABLES: this
-- file runs before schema_snapshot.sql/the migrations create any tables,
-- so a plain GRANT here would apply to nothing — default privileges apply
-- to tables the same role (postgres, the connection user for every step
-- in this job) creates afterward.
GRANT USAGE ON SCHEMA public TO authenticated, anon;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO authenticated, anon;

-- get_user_role(uuid)/get_user_facility(uuid) are called by
-- profiles_select_policy_hardened, which schema_snapshot.sql creates —
-- and the snapshot represents state as of phase27, before phase33 tracks
-- these functions' real definitions for the first time. Placeholder here
-- only so the snapshot's CREATE POLICY succeeds; phase33 (applied right
-- after, same as any other post-baseline migration) replaces this with
-- the real, verified definition via CREATE OR REPLACE before anything
-- actually queries through it.
CREATE OR REPLACE FUNCTION public.get_user_role(uuid) RETURNS text LANGUAGE sql STABLE AS $$ SELECT NULL::text $$;
CREATE OR REPLACE FUNCTION public.get_user_facility(uuid) RETURNS uuid LANGUAGE sql STABLE AS $$ SELECT NULL::uuid $$;
