# Fix Log: R3-DATA-RLS-R3-007

**Unit ID:** R3-DATA-RLS-R3-007
**Priority:** P1 (HIGH)
**Title:** profiles Table RLS Allows ASHA Workers to Enumerate All Facility Staff
**Status:** COMPLETED

## Finding Summary
RLS policy on `profiles` table allowed any user to view all profiles, enabling staff enumeration across facilities.

## Location
- Supabase RLS policy
- `backend/app/api/routes/analytics_routes.py:65`

## Remediation Applied
Added hardened RLS policy in `phase15_data_security_hardening.sql`:

```sql
CREATE POLICY profiles_select_policy_hardened
  ON public.profiles
  FOR SELECT
  USING (
    -- Can always read own profile
    id = auth.uid()
    OR EXISTS (
      SELECT 1 FROM public.profiles caller
      WHERE caller.id = auth.uid()
        AND (
          -- Admins can see all
          caller.role IN ('admin', 'super_admin')
          -- Facility staff can see colleagues at same facility
          OR (caller.role IN ('doctor', 'facility_admin') 
              AND caller.facility_id = profiles.facility_id)
        )
    )
  );
```

## Policy Logic
- **Own profile:** Always readable
- **Admins:** Can view all profiles
- **Doctors/Facility admins:** Can view profiles at same facility
- **ASHA workers:** Can only view own profile

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql` (Section 4)

## Risk Assessment
- **Before:** HIGH - Staff enumeration enabled social engineering
- **After:** LOW - Profile visibility properly scoped
