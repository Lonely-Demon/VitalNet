# Fix Log: R3-DATA-MIGRATE-R3-006

**Unit ID:** R3-DATA-MIGRATE-R3-006
**Priority:** P0 (CRITICAL)
**Title:** Baseline Schema Script Omits `patient_name` Required by Current Runtime
**Status:** COMPLETED (via phase14 migration)

## Finding Summary
The baseline schema creation script did not include the `patient_name` column which is required by the current runtime code paths.

## Location
- `Context/VitalNet_Phase6_Instructions.md:206`
- `backend/app/models/schemas.py:8`
- `backend/app/api/routes/cases.py:71,152`

## Remediation Applied
This was addressed in `phase14_add_patient_name.sql` migration which:
1. Adds `patient_name` column to `case_records` table idempotently
2. Uses `IF NOT EXISTS` pattern for safe re-runs
3. Sets appropriate defaults for existing records

## Migration Reference
```sql
-- phase14_add_patient_name.sql
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'case_records'
      AND column_name = 'patient_name'
  ) THEN
    ALTER TABLE public.case_records
      ADD COLUMN patient_name text NOT NULL DEFAULT 'Anonymous';
  END IF;
END $$;
```

## Files Modified
- `backend/supabase/migrations/phase14_add_patient_name.sql`

## Risk Assessment
- **Before:** CRITICAL - Runtime would fail on case creation
- **After:** RESOLVED - Column exists with proper constraints

## Testing Notes
Verify column exists: `SELECT column_name FROM information_schema.columns WHERE table_name = 'case_records' AND column_name = 'patient_name';`
