# Fix Log: R3-DATA-SCHEMA-R3-003

**Unit ID:** R3-DATA-SCHEMA-R3-003
**Priority:** P0 (CRITICAL)
**Title:** Missing Foreign Key Constraint on facility_id
**Status:** COMPLETED

## Finding Summary
`case_records.facility_id` had no foreign key constraint referencing `facilities` table, allowing orphaned records and invalid facility references.

## Location
- `backend/app/api/routes/cases.py:70`
- Database schema missing FK

## Remediation Applied
Added foreign key constraint in `phase15_data_security_hardening.sql`:

```sql
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema = 'public'
      AND table_name = 'case_records'
      AND constraint_name = 'case_records_facility_id_fkey'
  ) THEN
    ALTER TABLE public.case_records
      ADD CONSTRAINT case_records_facility_id_fkey
      FOREIGN KEY (facility_id)
      REFERENCES public.facilities(id)
      ON UPDATE CASCADE
      ON DELETE RESTRICT;
  END IF;
END $$;
```

## Cascade Behavior
- **ON UPDATE CASCADE** - If facility ID changes, update references
- **ON DELETE RESTRICT** - Prevent facility deletion if cases exist (data protection)

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql` (Section 1)

## Risk Assessment
- **Before:** HIGH - Cases could reference non-existent facilities, breaking queries
- **After:** LOW - Referential integrity enforced at database level

## Testing Notes
```sql
-- Should fail
INSERT INTO case_records (facility_id, ...) VALUES ('non-existent-uuid', ...);
-- Expected: Foreign key violation
```
