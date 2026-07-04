-- Phase 17: Model provenance, doctor triage-override, and outcome tracking
-- (FEATURES_ROADMAP §1b.5, §1b.1, §1.3)
-- Idempotent — safe to run multiple times.

BEGIN;

-- §1b.5: which model version actually produced this case's triage, so a
-- doctor auditing an old case (or an admin investigating a mis-triage) can
-- tell which model was in effect.
ALTER TABLE public.case_records
  ADD COLUMN IF NOT EXISTS triage_model_version text;

-- §1b.1: doctor triage-override + reason capture. Nullable — existing rows
-- and the common case (no override) are unaffected. This is one of the two
-- real-label sources the outcome-retraining loop (§1.3) reads.
ALTER TABLE public.case_records
  ADD COLUMN IF NOT EXISTS overridden_triage text,
  ADD COLUMN IF NOT EXISTS override_reason text,
  ADD COLUMN IF NOT EXISTS overridden_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS overridden_at timestamptz;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'case_records_overridden_triage_check'
  ) THEN
    ALTER TABLE public.case_records
      ADD CONSTRAINT case_records_overridden_triage_check
      CHECK (overridden_triage IS NULL OR overridden_triage IN ('ROUTINE', 'URGENT', 'EMERGENCY'));
  END IF;
END $$;

-- §1.3: recorded patient outcomes — the other real-label source for
-- retraining. Immutable (insert-only, matching medical record conventions —
-- corrections are new rows, not edits).
CREATE TABLE IF NOT EXISTS public.case_outcomes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id uuid NOT NULL REFERENCES public.case_records(id) ON DELETE CASCADE,
  recorded_by uuid NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
  actual_severity text NOT NULL CHECK (actual_severity IN ('ROUTINE', 'URGENT', 'EMERGENCY')),
  patient_disposition text NOT NULL CHECK (
    patient_disposition IN ('treated_discharged', 'admitted', 'referred_higher_facility', 'deceased', 'unknown')
  ),
  outcome_notes text,
  recorded_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_case_outcomes_case_id ON public.case_outcomes(case_id);
CREATE INDEX IF NOT EXISTS idx_case_outcomes_recorded_by ON public.case_outcomes(recorded_by);

ALTER TABLE public.case_outcomes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS case_outcomes_select_policy ON public.case_outcomes;
CREATE POLICY case_outcomes_select_policy
  ON public.case_outcomes
  FOR SELECT
  USING (
    recorded_by = auth.uid()
    OR EXISTS (
      SELECT 1
      FROM public.case_records cr
      JOIN public.profiles p ON p.id = auth.uid()
      WHERE cr.id = case_outcomes.case_id
        AND (p.role = 'admin' OR p.facility_id = cr.facility_id)
    )
  );

DROP POLICY IF EXISTS case_outcomes_insert_policy ON public.case_outcomes;
CREATE POLICY case_outcomes_insert_policy
  ON public.case_outcomes
  FOR INSERT
  WITH CHECK (
    recorded_by = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid() AND p.role IN ('doctor', 'admin')
    )
  );

-- No UPDATE/DELETE policies — immutable by omission (RLS default-denies
-- any command without a matching policy).

COMMIT;
