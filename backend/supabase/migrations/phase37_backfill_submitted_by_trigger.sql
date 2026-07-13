-- Phase 37: Backfill the submitted_by-immutability trigger phase15 defined
-- but that never actually reached the live project.
--
-- Found while checking whether schema_snapshot.sql could bootstrap a
-- genuinely new project on its own: phase15_data_security_hardening.sql
-- defines protect_case_records_submitted_by() and its trigger
-- trg_protect_case_records_submitted_by, but a direct existence check
-- against the live database (pg_proc/pg_trigger) confirmed BOTH are
-- absent. This is the same failure mode as phase28-31 (docs/DECISIONS.md
-- §35) and phase15's own profiles_select_policy_hardened (§36/§37) — a
-- tracked migration that never actually landed — except this one predates
-- schema_snapshot.sql's phase27 baseline, so nothing in the schema-drift
-- CI job could have caught it: the baseline treats everything before
-- phase28 as an opaque, already-applied black box.
--
-- This is not just a tracking gap. case_records_update_policy's WITH CHECK
-- includes a `submitted_by = submitted_by` clause that phase15's own
-- comment explains is intentionally a no-op — WITH CHECK cannot reference
-- the pre-update row, so a BEFORE UPDATE trigger is the correct primitive
-- for column immutability, and this trigger is that mechanism. Without it,
-- any doctor/facility_admin/admin (or the original submitter) with UPDATE
-- access to a case_records row — reachable directly via Supabase's
-- PostgREST API regardless of what any application endpoint validates —
-- could silently reassign submitted_by to an arbitrary uuid, corrupting
-- the audit trail for who actually submitted a case.

BEGIN;

CREATE OR REPLACE FUNCTION public.protect_case_records_submitted_by()
RETURNS trigger AS $$
BEGIN
  IF NEW.submitted_by IS DISTINCT FROM OLD.submitted_by THEN
    RAISE EXCEPTION 'submitted_by is immutable and cannot be changed';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_protect_case_records_submitted_by ON public.case_records;
CREATE TRIGGER trg_protect_case_records_submitted_by
  BEFORE UPDATE ON public.case_records
  FOR EACH ROW EXECUTE FUNCTION public.protect_case_records_submitted_by();

COMMIT;
