-- Phase 26: Widen profiles.role CHECK constraint to include 'supervisor'
-- Idempotent — safe to run multiple times.
--
-- Discovered during E2E verification of the supervisor role (docs/DECISIONS.md
-- §25): the live database has a `profiles_role_check` CHECK constraint that
-- is NOT defined in any tracked migration in this repo — untracked schema
-- drift, added directly against the project at some point outside version
-- control. It rejects 'supervisor', blocking the new role entirely. This
-- migration makes the constraint's definition explicit and tracked, and
-- widens it to the app's real 4-role model.

BEGIN;

ALTER TABLE public.profiles DROP CONSTRAINT IF EXISTS profiles_role_check;
ALTER TABLE public.profiles
  ADD CONSTRAINT profiles_role_check
  CHECK (role IN ('asha_worker', 'doctor', 'supervisor', 'admin'));

COMMIT;
