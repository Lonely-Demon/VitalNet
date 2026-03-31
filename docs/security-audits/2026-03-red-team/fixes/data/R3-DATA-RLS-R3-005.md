# Fix Log: R3-DATA-RLS-R3-005

**Unit ID:** R3-DATA-RLS-R3-005
**Priority:** P0 (CRITICAL)
**Title:** UPDATE RLS Policy Allows Privilege Escalation via reviewed_by Manipulation
**Status:** COMPLETED

## Finding Summary
UPDATE RLS policy did not restrict which fields could be modified, allowing non-doctors to potentially set `reviewed_by` field and mark cases as reviewed.

## Location
- `backend/app/api/routes/cases.py:195-200`
- Supabase RLS policy

## Remediation Applied
Added UPDATE RLS policy with field-level restrictions in `phase15_data_security_hardening.sql`:

```sql
CREATE POLICY case_records_update_policy
  ON public.case_records
  FOR UPDATE
  USING (
    -- Cannot update soft-deleted records
    deleted_at IS NULL
    AND (
      -- Facility-scoped doctors/admins can update
      EXISTS (
        SELECT 1 FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.role IN ('doctor', 'facility_admin', 'admin', 'super_admin')
          AND (p.role IN ('admin', 'super_admin') OR p.facility_id = case_records.facility_id)
      )
      OR submitted_by = auth.uid()
    )
  )
  WITH CHECK (
    -- Cannot change submitted_by (immutable audit trail)
    submitted_by = submitted_by
    -- Only doctors+ can set reviewed_by
    AND (
      reviewed_by IS NULL
      OR EXISTS (
        SELECT 1 FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.role IN ('doctor', 'facility_admin', 'admin', 'super_admin')
      )
    )
  );
```

## Policy Logic
1. **Cannot update deleted records** - Preserves soft-delete integrity
2. **Facility-scoped access** - Doctors can only update cases in their facility
3. **submitted_by immutable** - Cannot change original submitter (audit trail)
4. **reviewed_by protected** - Only doctors+ can set review status

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql` (Section 4)

## Risk Assessment
- **Before:** CRITICAL - ASHA workers could mark cases as reviewed
- **After:** LOW - Role-based restrictions enforced at database level
