-- CI-only stubs for Supabase-managed objects that schema_snapshot.sql and
-- the tracked migrations reference but don't (and shouldn't) define
-- themselves — the auth schema is Supabase infrastructure, not something
-- migrations create. Used only by the db-schema-drift CI job to let a
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
CREATE OR REPLACE FUNCTION auth.role() RETURNS text LANGUAGE sql STABLE AS $$
  SELECT COALESCE(auth.jwt() ->> 'role', 'anon')::text
$$;
-- Real Supabase projects grant USAGE on auth + EXECUTE on these to PUBLIC
-- (every role, not just authenticated/anon) — matched here so RLS
-- policies that call them actually work under a non-superuser role.
GRANT USAGE ON SCHEMA auth TO PUBLIC;
GRANT EXECUTE ON FUNCTION auth.uid() TO PUBLIC;
GRANT EXECUTE ON FUNCTION auth.jwt() TO PUBLIC;
GRANT EXECUTE ON FUNCTION auth.role() TO PUBLIC;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

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
