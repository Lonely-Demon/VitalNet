-- Phase 19: Inter-facility referral workflow (FEATURES_ROADMAP §2.3)
-- Idempotent — safe to run multiple times.

BEGIN;

CREATE TABLE IF NOT EXISTS public.referrals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id uuid NOT NULL REFERENCES public.case_records(id) ON DELETE CASCADE,
  referred_by uuid NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
  referring_facility_id uuid NOT NULL REFERENCES public.facilities(id) ON DELETE RESTRICT,
  receiving_facility_id uuid NOT NULL REFERENCES public.facilities(id) ON DELETE RESTRICT,
  reason text NOT NULL,
  urgency text NOT NULL CHECK (urgency IN ('ROUTINE', 'URGENT', 'EMERGENCY')),
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'acknowledged', 'patient_arrived', 'completed', 'cancelled')),
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT referrals_distinct_facilities CHECK (referring_facility_id <> receiving_facility_id)
);

CREATE INDEX IF NOT EXISTS idx_referrals_case_id ON public.referrals(case_id);
CREATE INDEX IF NOT EXISTS idx_referrals_referring_facility ON public.referrals(referring_facility_id);
CREATE INDEX IF NOT EXISTS idx_referrals_receiving_facility ON public.referrals(receiving_facility_id);
CREATE INDEX IF NOT EXISTS idx_referrals_status ON public.referrals(status);

ALTER TABLE public.referrals ENABLE ROW LEVEL SECURITY;

-- Visible to admin (global) or a doctor whose facility is on either side of
-- the referral — a receiving facility needs to see an incoming referral
-- just as much as the referring facility needs to track its outgoing one.
DROP POLICY IF EXISTS referrals_select_policy ON public.referrals;
CREATE POLICY referrals_select_policy
  ON public.referrals
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND (p.role = 'admin' OR p.facility_id IN (referring_facility_id, receiving_facility_id))
    )
  );

-- Only a doctor/admin scoped to the REFERRING facility can create a referral
-- (mirrors the app-level check in referral_routes.py::create_referral).
DROP POLICY IF EXISTS referrals_insert_policy ON public.referrals;
CREATE POLICY referrals_insert_policy
  ON public.referrals
  FOR INSERT
  WITH CHECK (
    referred_by = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.role IN ('doctor', 'admin')
        AND (p.role = 'admin' OR p.facility_id = referring_facility_id)
    )
  );

-- Only the RECEIVING facility's doctor/admin can advance a referral's
-- status — the referring side made the referral, the receiving side owns
-- what happens to the patient next.
DROP POLICY IF EXISTS referrals_update_policy ON public.referrals;
CREATE POLICY referrals_update_policy
  ON public.referrals
  FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND (p.role = 'admin' OR (p.role = 'doctor' AND p.facility_id = receiving_facility_id))
    )
  );

-- Realtime — mirrors phase10_realtime_setup.sql's setup for case_records, so
-- useRealtimeReferrals gets full row data on UPDATE, not just the changed keys.
-- Guarded (unlike phase10's bare ALTER PUBLICATION) because re-adding an
-- already-member table to a publication errors rather than no-oping.
ALTER TABLE public.referrals REPLICA IDENTITY FULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND schemaname = 'public' AND tablename = 'referrals'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.referrals;
  END IF;
END $$;

COMMIT;
