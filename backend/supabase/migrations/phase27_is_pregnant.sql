-- Phase 27: Structured pregnancy flag (docs/DECISIONS.md §30)
-- Idempotent — safe to run multiple times.
--
-- Feeds the preeclampsia-specific safety-net rule in classifier.py /
-- clinicalRules.js. Nullable: existing rows and any submission that
-- doesn't set it stay NULL (unknown), never coerced to false.

BEGIN;

ALTER TABLE public.case_records
  ADD COLUMN IF NOT EXISTS is_pregnant boolean;

COMMIT;
