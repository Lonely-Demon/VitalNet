# Fix Log: R3-DATA-SCHEMA-R3-009

**Unit ID:** R3-DATA-SCHEMA-R3-009
**Priority:** P2 (MEDIUM)
**Title:** No Database-Level Constraint on triage_priority vs triage_level Mapping
**Status:** COMPLETED

## Finding Summary
`triage_priority` (numeric) and `triage_level` (text) could have inconsistent values.

## Location
- `backend/app/api/routes/cases.py:88`
- Database schema

## Remediation Applied
Added mapping constraint in `phase15_data_security_hardening.sql`:

```sql
ALTER TABLE public.case_records
  ADD CONSTRAINT case_records_triage_priority_map_check
  CHECK (
    (triage_level = 'EMERGENCY' AND triage_priority = 0) OR
    (triage_level = 'URGENT' AND triage_priority = 1) OR
    (triage_level = 'ROUTINE' AND triage_priority = 2) OR
    triage_priority IS NULL  -- Allow NULL during migration
  );
```

## Mapping
| triage_level | triage_priority |
|--------------|-----------------|
| EMERGENCY    | 0               |
| URGENT       | 1               |
| ROUTINE      | 2               |

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql` (Section 1)
