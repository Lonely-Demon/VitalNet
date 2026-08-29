-- Governance-gated paediatric capture fields.
-- Nullable by design: omitted data remains unknown and old rows remain valid.
-- These fields are persistence/research inputs only until a separate clinical
-- governance decision authorizes advisory or triage integration.
BEGIN;

ALTER TABLE public.case_records
  ADD COLUMN IF NOT EXISTS age_months integer,
  ADD COLUMN IF NOT EXISTS muac_mm integer,
  ADD COLUMN IF NOT EXISTS paediatric_advisory jsonb;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'case_records_age_months_bounds'
  ) THEN
    ALTER TABLE public.case_records
      ADD CONSTRAINT case_records_age_months_bounds
      CHECK (age_months IS NULL OR age_months BETWEEN 0 AND 23);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'case_records_muac_mm_bounds'
  ) THEN
    ALTER TABLE public.case_records
      ADD CONSTRAINT case_records_muac_mm_bounds
      CHECK (muac_mm IS NULL OR muac_mm BETWEEN 50 AND 300);
  END IF;
END $$;

COMMENT ON COLUMN public.case_records.age_months IS
  'Governance-gated infant age precision; valid only for patient_age under 2; not consumed by production triage.';
COMMENT ON COLUMN public.case_records.muac_mm IS
  'Governance-gated MUAC in millimetres; captured for children under 5; not an autonomous diagnosis or production triage input.';
COMMENT ON COLUMN public.case_records.paediatric_advisory IS
  'Versioned, default-off research metadata; never a diagnosis, treatment instruction, triage tier, or review flag.';

COMMIT;
