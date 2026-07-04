# Fix Log: R3-DATA-SCHEMA-R3-006

**Unit ID:** R3-DATA-SCHEMA-R3-006
**Priority:** P1 (HIGH)
**Title:** Missing UNIQUE Constraint on client_id (Duplicate Detection)
**Status:** COMPLETED

## Finding Summary
`client_id` column (used for offline sync deduplication) lacked a UNIQUE constraint, allowing duplicate case submissions.

## Location
- `backend/app/api/routes/cases.py:101`
- Database schema

## Remediation Applied
Added unique index in `phase15_data_security_hardening.sql`:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_case_records_client_id_unique
  ON public.case_records (client_id);
```

## Design Choice
Used unique index instead of constraint because:
1. Same enforcement behavior
2. Provides index for lookups (needed for dedup checks)
3. More flexible for partial uniqueness if needed later

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql` (Section 1)

## Risk Assessment
- **Before:** HIGH - Duplicate cases could corrupt analytics and create confusion
- **After:** LOW - Database enforces uniqueness

## Testing Notes
```sql
-- Should fail with duplicate key violation
INSERT INTO case_records (client_id, ...) VALUES ('existing-id', ...);
```
