# Fix Log: R3-DATA-RLS-R3-006

**Unit ID:** R3-DATA-RLS-R3-006
**Priority:** P1 (HIGH)
**Title:** No RLS Policy for facilities Table Allows Unauthorized PHC Data Exfiltration
**Status:** COMPLETED

## Finding Summary
The `facilities` table had no RLS policies, allowing any authenticated user to read all facility data.

## Location
- `backend/app/api/routes/admin_routes.py:183`
- Supabase RLS configuration

## Remediation Applied
Added RLS policy in `phase15_data_security_hardening.sql`:

```sql
ALTER TABLE public.facilities ENABLE ROW LEVEL SECURITY;

CREATE POLICY facilities_select_policy
  ON public.facilities
  FOR SELECT
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
```

## Policy Logic
- **Admins:** Can view all facilities
- **Staff:** Can only view their own facility
- **Unauthenticated:** No access

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql` (Section 4)

## Risk Assessment
- **Before:** HIGH - Cross-facility data leakage possible
- **After:** LOW - Facility data properly scoped
