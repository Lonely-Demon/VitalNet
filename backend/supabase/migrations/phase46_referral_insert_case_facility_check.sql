-- Phase 44: Strengthen referrals INSERT policy to verify that the case_id
-- belongs to the referring facility (VN-2026-08-C3-03).
--
-- Prevents cross-tenant referral injection where a doctor in Facility A
-- creates a referral for a case belonging to Facility B.

BEGIN;

DROP POLICY IF EXISTS referrals_insert_policy ON public.referrals;
CREATE POLICY referrals_insert_policy
  ON public.referrals
  FOR INSERT
  WITH CHECK (
    referred_by = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.role = ANY (ARRAY['doctor'::text, 'admin'::text, 'super_admin'::text])
        AND (p.role = ANY (ARRAY['admin'::text, 'super_admin'::text]) OR p.facility_id = referring_facility_id)
    )
    AND EXISTS (
      SELECT 1 FROM public.case_records cr
      WHERE cr.id = case_id
        AND cr.facility_id = referring_facility_id
        AND cr.deleted_at IS NULL
    )
  );

COMMIT;
