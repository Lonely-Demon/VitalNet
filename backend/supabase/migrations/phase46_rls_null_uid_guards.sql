-- Phase 46: Add explicit auth.uid() IS NOT NULL guards to RLS policies (VN-2026-08-C3-05).
--
-- Explicitly guards against NULL semantics when queries are executed without
-- an active authenticated session (e.g. anonymous client requests).

BEGIN;

-- 1. case_records: delete policy
DROP POLICY IF EXISTS case_records_delete_policy ON public.case_records;
CREATE POLICY case_records_delete_policy
  ON public.case_records
  FOR DELETE
  USING (
    auth.uid() IS NOT NULL AND (
      auth.uid() = submitted_by
      OR EXISTS (
        SELECT 1 FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.is_active = true
          AND p.role = ANY (ARRAY['admin'::text, 'super_admin'::text])
      )
    )
  );

-- 2. case_records: update policy
DROP POLICY IF EXISTS case_records_update_policy ON public.case_records;
CREATE POLICY case_records_update_policy
  ON public.case_records
  FOR UPDATE
  USING (
    auth.uid() IS NOT NULL
    AND deleted_at IS NULL
    AND (
      EXISTS (
        SELECT 1 FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.is_active = true
          AND p.role = ANY (ARRAY['doctor'::text, 'facility_admin'::text, 'admin'::text, 'super_admin'::text])
          AND (
            p.role = ANY (ARRAY['admin'::text, 'super_admin'::text])
            OR p.facility_id = case_records.facility_id
          )
      )
      OR submitted_by = auth.uid()
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL AND (
      reviewed_by IS NULL
      OR EXISTS (
        SELECT 1 FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.is_active = true
          AND p.role = ANY (ARRAY['doctor'::text, 'facility_admin'::text, 'admin'::text, 'super_admin'::text])
      )
    )
  );

-- 3. referrals: select policy
DROP POLICY IF EXISTS referrals_select_policy ON public.referrals;
CREATE POLICY referrals_select_policy
  ON public.referrals
  FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.is_active = true
        AND (
          p.role = ANY (ARRAY['admin'::text, 'super_admin'::text])
          OR p.facility_id IN (referring_facility_id, receiving_facility_id)
        )
    )
  );

-- 4. referrals: update policy
DROP POLICY IF EXISTS referrals_update_policy ON public.referrals;
CREATE POLICY referrals_update_policy
  ON public.referrals
  FOR UPDATE
  USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.is_active = true
        AND (
          p.role = ANY (ARRAY['admin'::text, 'super_admin'::text])
          OR (p.role = 'doctor'::text AND p.facility_id = receiving_facility_id)
        )
    )
  );

COMMIT;
