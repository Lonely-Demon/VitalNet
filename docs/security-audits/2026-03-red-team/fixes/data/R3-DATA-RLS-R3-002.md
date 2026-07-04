# Fix Log: R3-DATA-RLS-R3-002

**Unit ID:** R3-DATA-RLS-R3-002
**Priority:** P0 (CRITICAL)
**Title:** Missing DELETE RLS Policy Allows Unauthorized Case Purging
**Status:** COMPLETED

## Finding Summary
No RLS policy existed for DELETE operations on `case_records`, allowing any authenticated user to delete any record.

## Location
Supabase RLS configuration (no DELETE policy existed)

## Remediation Applied
Added DELETE RLS policy in `phase15_data_security_hardening.sql`:

```sql
CREATE POLICY case_records_delete_policy
  ON public.case_records
  FOR DELETE
  USING (
    -- Only the submitter can delete their own records, OR admin/super_admin
    auth.uid() = submitted_by
    OR EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid() AND p.role IN ('admin', 'super_admin')
    )
  );
```

## Policy Logic
- **Submitter:** Can delete their own submissions
- **Admin/Super_admin:** Can delete any record (for data management)
- **Other roles:** Cannot delete records

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql` (Section 4)

## Risk Assessment
- **Before:** CRITICAL - Any authenticated user could delete any PHI record
- **After:** LOW - Proper authorization enforced at database level

## Testing Notes
```sql
-- As ASHA worker, attempt to delete another facility's case (should fail)
DELETE FROM case_records WHERE id = '<other_facility_case_id>';
-- Expected: 0 rows affected (RLS blocks)
```
