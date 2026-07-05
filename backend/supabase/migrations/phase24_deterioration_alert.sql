-- Phase 24: Cross-visit deterioration alert
-- Idempotent — safe to run multiple times.
--
-- When a new case shares a patient_key with prior visits, and the
-- combined count of URGENT/EMERGENCY visits (this one included) within a
-- trailing 7-day window reaches 2 or more, the submission is flagged as a
-- deterioration pattern and forced into needs_review — a repeated severe
-- presentation is a signal worth a clinician's eyes even if today's
-- reading alone wouldn't have triggered review. See docs/DECISIONS.md §22.

BEGIN;

ALTER TABLE public.case_records
  ADD COLUMN IF NOT EXISTS deterioration_alert boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS deterioration_visit_count integer;

COMMIT;
