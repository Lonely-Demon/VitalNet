# Fix Log: R3-DATA-SCHEMA-R3-002

**Unit ID:** R3-DATA-SCHEMA-R3-002
**Priority:** P0 (CRITICAL)
**Title:** Missing Database-Level Enum Constraint for triage_level
**Status:** COMPLETED

## Finding Summary
`triage_level` field had Pydantic validation only, with no database-level constraint. Invalid values could be inserted via direct DB access or API bypass.

## Location
- `backend/app/models/schemas.py:33` (Pydantic only)
- Database constraint missing

## Remediation Applied
Added CHECK constraint in `phase15_data_security_hardening.sql`:

```sql
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'case_records_triage_level_check'
  ) THEN
    ALTER TABLE public.case_records
      ADD CONSTRAINT case_records_triage_level_check
      CHECK (triage_level IN ('ROUTINE', 'URGENT', 'EMERGENCY'));
  END IF;
END $$;
```

## Allowed Values
- `ROUTINE` (priority 2)
- `URGENT` (priority 1)
- `EMERGENCY` (priority 0)

## Additional Constraint
Also added triage_priority mapping constraint (R3-DATA-SCHEMA-R3-009):
```sql
CHECK (
  (triage_level = 'EMERGENCY' AND triage_priority = 0) OR
  (triage_level = 'URGENT' AND triage_priority = 1) OR
  (triage_level = 'ROUTINE' AND triage_priority = 2) OR
  triage_priority IS NULL
)
```

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql` (Section 1)

## Risk Assessment
- **Before:** HIGH - Invalid triage levels could disrupt clinical prioritization
- **After:** LOW - Database enforces valid enum values with consistent mapping
