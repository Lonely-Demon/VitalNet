-- Phase 23: Patient continuity key
-- Idempotent — safe to run multiple times.
--
-- An opaque, offline-generated identifier (format XXXX-XXXX, no PII encoded)
-- that lets an ASHA worker or doctor recognize a returning patient across
-- visits without any centralized patient registry. Generated client-side
-- (frontend/src/utils/patientKey.js) so it works for a brand-new patient
-- with zero connectivity. Nullable — a patient who has never returned, or
-- whose worker skips the field, simply has no key.

BEGIN;

ALTER TABLE public.case_records
  ADD COLUMN IF NOT EXISTS patient_key text;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'case_records_patient_key_format_check'
  ) THEN
    ALTER TABLE public.case_records
      ADD CONSTRAINT case_records_patient_key_format_check
      CHECK (patient_key IS NULL OR patient_key ~ '^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}$');
  END IF;
END $$;

-- Partial index — only rows that actually carry a key are relevant to the
-- by-patient-key lookup, and most cases never set one.
CREATE INDEX IF NOT EXISTS idx_case_records_patient_key
  ON public.case_records (patient_key) WHERE patient_key IS NOT NULL;

COMMIT;
