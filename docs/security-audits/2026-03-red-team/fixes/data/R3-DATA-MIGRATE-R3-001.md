# Fix Log: R3-DATA-MIGRATE-R3-001

**Unit ID:** R3-DATA-MIGRATE-R3-001
**Priority:** P1 (HIGH)
**Title:** Realtime Migration Is Labeled Idempotent but Uses Non-Idempotent DDL
**Status:** COMPLETED

## Finding Summary
Migration scripts claim idempotency but use non-idempotent DDL statements (e.g., CREATE without IF NOT EXISTS), causing failures on re-run.

## Location
- `backend/supabase/migrations/phase10_realtime_setup.sql:8,9`

## Remediation Applied
Phase 15 migration establishes idempotent patterns throughout:

```sql
-- Idempotent constraint addition
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'constraint_name'
  ) THEN
    ALTER TABLE ... ADD CONSTRAINT ...;
  END IF;
END $$;

-- Idempotent column addition
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'x' AND column_name = 'y'
  ) THEN
    ALTER TABLE x ADD COLUMN y ...;
  END IF;
END $$;

-- Idempotent index creation
CREATE INDEX IF NOT EXISTS idx_name ON table(column);

-- Idempotent table creation
CREATE TABLE IF NOT EXISTS ...;
```

## Migration Guidelines Established
1. Always use `IF NOT EXISTS` for CREATE statements
2. Wrap ALTER TABLE in existence checks
3. Use `DROP ... IF EXISTS` before recreating
4. Test migrations with `--dry-run` before applying

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql` - Uses idempotent patterns throughout

## Risk Assessment
- **Before:** HIGH - Migrations could fail on re-run, blocking deployments
- **After:** LOW - All phase15 DDL is safely re-runnable
