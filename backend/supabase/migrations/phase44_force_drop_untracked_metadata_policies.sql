-- Phase 42: Force drop untracked user_metadata RLS policies, drop legacy
-- case_referrals table, and enforce facility-checked case_records INSERT policy.
--
-- Findings fixed:
--   - VN-2026-08-VER-07 (CRITICAL): Live DB retained user_metadata policies
--     that phase32 was supposed to DROP (doctor_update, asha_select_own,
--     case_referrals.*, profile_select).
--   - VN-2026-08-VER-06 (CRITICAL) & VN-2026-08-C3-01 (CRITICAL):
--     authenticated_insert had no facility check, allowing cross-tenant case
--     injection via PostgREST.
--
-- Transactional and fully idempotent.

BEGIN;

-- 1. Drop user_metadata policies on case_records (phase32 targets)
DROP POLICY IF EXISTS doctor_update ON public.case_records;
DROP POLICY IF EXISTS asha_select_own ON public.case_records;

-- 2. Drop user_metadata policies and legacy case_referrals table (phase34 targets)
DROP POLICY IF EXISTS "Doctors can create referrals from their facility" ON public.case_referrals;
DROP POLICY IF EXISTS "Doctors and admins can view referrals from their facility" ON public.case_referrals;
DROP POLICY IF EXISTS "Receiving facility can view incoming referrals" ON public.case_referrals;
DROP TABLE IF EXISTS public.case_referrals;

-- 3. Drop user_metadata policy on profiles
DROP POLICY IF EXISTS profile_select ON public.profiles;

-- 4. Drop untracked facility-less INSERT policy
DROP POLICY IF EXISTS authenticated_insert ON public.case_records;

-- 5. Drop target policies prior to recreate to guarantee idempotency
DROP POLICY IF EXISTS asha_select_own ON public.case_records;
DROP POLICY IF EXISTS case_records_insert_policy ON public.case_records;

-- 6. Recreate asha_select_own using safe profiles table-join
CREATE POLICY asha_select_own ON public.case_records
  FOR SELECT TO public
  USING (
    (deleted_at IS NULL) AND (
      (submitted_by = auth.uid())
      OR EXISTS (
        SELECT 1 FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.role = ANY (ARRAY['doctor'::text, 'facility_admin'::text, 'admin'::text, 'super_admin'::text])
          AND (
            p.role = ANY (ARRAY['admin'::text, 'super_admin'::text])
            OR p.facility_id = case_records.facility_id
          )
      )
    )
  );

-- 7. Create facility-checked INSERT policy (replaces authenticated_insert)
CREATE POLICY case_records_insert_policy ON public.case_records
  FOR INSERT TO authenticated
  WITH CHECK (
    (submitted_by = auth.uid())
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.is_active = true
        AND (
          p.role = ANY (ARRAY['admin'::text, 'super_admin'::text])
          OR p.facility_id = case_records.facility_id
        )
    )
  );

-- 8. Compute and display new schema fingerprint (if fn_schema_fingerprint exists)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'fn_schema_fingerprint') THEN
    PERFORM public.fn_schema_fingerprint();
  END IF;
END $$;

COMMIT;
