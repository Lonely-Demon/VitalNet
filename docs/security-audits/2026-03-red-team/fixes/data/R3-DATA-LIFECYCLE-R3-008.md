# Fix Log: R3-DATA-LIFECYCLE-R3-008

**Unit ID:** R3-DATA-LIFECYCLE-R3-008
**Priority:** P2 (MEDIUM)
**Title:** Soft-deleted records can still be mutated by review endpoint
**Status:** COMPLETED

## Finding Summary
Review endpoint did not check `deleted_at` status, allowing updates to soft-deleted records.

## Location
- `backend/app/api/routes/cases.py:195,200,156,231,266`

## Remediation Applied
1. **RLS Policy Update** - UPDATE policy in phase15 migration explicitly blocks updates to soft-deleted records:
```sql
USING (
  deleted_at IS NULL  -- Cannot update soft-deleted records
  AND ...
)
```

2. **Application-level check** added to review endpoint (cases.py).

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql` (RLS policy)
- `backend/app/api/routes/cases.py` (soft-delete check)

## Risk Assessment
- **Before:** MEDIUM - Deleted records could be modified
- **After:** LOW - Both RLS and application enforce soft-delete immutability
