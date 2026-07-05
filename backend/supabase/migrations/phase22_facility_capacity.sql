-- Phase 22: Facility self-reported capacity status
-- Idempotent — safe to run multiple times.
--
-- Lets a facility's own doctor (or an admin) flag whether they can
-- currently take a referral. Self-reported, not derived from a bed-
-- management system this project doesn't have — a referring doctor sees
-- it as one more signal, not an automated capacity check.

BEGIN;

ALTER TABLE public.facilities
  ADD COLUMN IF NOT EXISTS capacity_status text NOT NULL DEFAULT 'available',
  ADD COLUMN IF NOT EXISTS capacity_updated_at timestamptz;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'facilities_capacity_status_check'
  ) THEN
    ALTER TABLE public.facilities
      ADD CONSTRAINT facilities_capacity_status_check
      CHECK (capacity_status IN ('available', 'limited', 'full'));
  END IF;
END $$;

-- No UPDATE policy existed on facilities before this (only the phase15
-- SELECT policy) — app/api/routes/referral_routes.py::update_facility_capacity
-- uses the RLS-scoped client (get_supabase_for_user), not supabase_admin,
-- since this is a mixed doctor/admin write (a doctor may only update their
-- own facility's row); this is the RLS backstop for that.
DROP POLICY IF EXISTS facilities_update_policy ON public.facilities;
CREATE POLICY facilities_update_policy
  ON public.facilities
  FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND (
          p.role IN ('admin', 'super_admin')
          OR p.facility_id = facilities.id
        )
    )
  );

COMMIT;
