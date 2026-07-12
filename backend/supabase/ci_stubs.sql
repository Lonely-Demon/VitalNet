-- CI-only stubs for Supabase-managed objects that schema_snapshot.sql and
-- the tracked migrations reference but don't (and shouldn't) define
-- themselves — the auth schema is Supabase infrastructure, not something
-- migrations create. Used only by the db-schema-drift CI job to let a
-- fresh Postgres container load the snapshot/migrations; never applied to
-- a real project.
CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE IF NOT EXISTS auth.users (id uuid PRIMARY KEY);
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$ SELECT NULL::uuid $$;
CREATE OR REPLACE FUNCTION auth.jwt() RETURNS jsonb LANGUAGE sql STABLE AS $$ SELECT '{}'::jsonb $$;
CREATE OR REPLACE FUNCTION auth.role() RETURNS text LANGUAGE sql STABLE AS $$ SELECT 'anon'::text $$;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- get_user_role(uuid)/get_user_facility(uuid) are called by
-- profiles_select_policy_hardened in schema_snapshot.sql but exist on the
-- live project in NO tracked migration anywhere in this repo (discovered
-- 2026-07 while building this drift check — see docs/DECISIONS.md).
-- Stubbed here so the snapshot loads; real definitions still need to be
-- pulled from the live project and tracked properly.
CREATE OR REPLACE FUNCTION public.get_user_role(uuid) RETURNS text LANGUAGE sql STABLE AS $$ SELECT NULL::text $$;
CREATE OR REPLACE FUNCTION public.get_user_facility(uuid) RETURNS uuid LANGUAGE sql STABLE AS $$ SELECT NULL::uuid $$;
