-- Phase 21: Contraindication/interaction flags (app/ml/contraindications.py)
-- Idempotent — safe to run multiple times.
--
-- Deterministic keyword-matched flags (NSAID+renal, ACE-inhibitor+renal,
-- metformin+persistent-vomiting, anticoagulant+severe-bleeding,
-- beta-blocker+bradycardia, insulin/sulfonylurea+altered-consciousness) —
-- never change the triage tier, only force needs_review so a doctor looks.

BEGIN;

ALTER TABLE public.case_records
  ADD COLUMN IF NOT EXISTS contraindication_flags jsonb NOT NULL DEFAULT '[]'::jsonb;

COMMIT;
