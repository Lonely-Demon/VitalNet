# Fix Log: R3-DATA-SCHEMA-R3-001

**Unit ID:** R3-DATA-SCHEMA-R3-001
**Priority:** P0 (CRITICAL)
**Title:** Missing Database-Level Enum Constraint for patient_sex
**Status:** COMPLETED

## Finding Summary
`patient_sex` field had Pydantic validation only, with no database-level constraint. Invalid values could be inserted via direct DB access or API bypass.

## Location
- `backend/app/models/schemas.py:10` (Pydantic only)
- Database constraint missing

## Remediation Applied
Added CHECK constraint in `phase15_data_security_hardening.sql`:

```sql
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'case_records_patient_sex_check'
  ) THEN
    ALTER TABLE public.case_records
      ADD CONSTRAINT case_records_patient_sex_check
      CHECK (patient_sex IN ('male', 'female', 'other'));
  END IF;
END $$;
```

## Allowed Values
- `male`
- `female`
- `other`

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql` (Section 1)

## Risk Assessment
- **Before:** HIGH - Invalid data could corrupt analytics/clinical workflows
- **After:** LOW - Database enforces valid enum values

## Testing Notes
```sql
-- Should fail
INSERT INTO case_records (patient_sex, ...) VALUES ('invalid', ...);
-- Expected: CHECK constraint violation
```
