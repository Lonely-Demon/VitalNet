-- Phase 29: outbox event dedup table + advisory-model columns
-- (Round 6 rebuild plan, items 2 and 3 / DECISIONS.md §32)
-- Idempotent — safe to run multiple times.
--
-- client_events is the server-side half of the unified offline outbox
-- (Phase 5): each queued client action carries a client-generated
-- event_id (uuid). On sync, the server upserts by event_id — a retried
-- submission (flaky connectivity, a retried fetch) replays the SAME
-- stored response instead of re-applying the action or erroring, which is
-- what makes the outbox idempotent end to end, not just idempotent on the
-- one client_id/case_records path case.py already had.
--
-- model_tier/rules_fired/model_agreed are additive, nullable columns on
-- case_records for the advisory ML output once rules_first ships (Phase
-- 4): triage_level stays the rules engine's decision; these three record
-- what the model's own (non-authoritative) opinion was, so ml-agreement
-- analytics and the model-promotion gate have real data to work from
-- before anyone considers making the model authoritative again.

BEGIN;

CREATE TABLE IF NOT EXISTS public.client_events (
  event_id uuid PRIMARY KEY,
  event_type text NOT NULL,
  submitted_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  processed_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
  response jsonb NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_client_events_submitted_by ON public.client_events(submitted_by);
CREATE INDEX IF NOT EXISTS idx_client_events_processed_at ON public.client_events(processed_at);

ALTER TABLE public.client_events ENABLE ROW LEVEL SECURITY;

-- A worker can see their own replayed responses (useful for client-side
-- debugging of a stuck sync); nothing else. Inserts/updates only ever
-- happen through the API's service-role idempotency middleware, never
-- directly from a client — no INSERT/UPDATE/DELETE policy is added, so
-- RLS default-denies those by omission, same convention as case_outcomes
-- (phase17_triage_provenance_and_override.sql).
DROP POLICY IF EXISTS client_events_select_policy ON public.client_events;
CREATE POLICY client_events_select_policy
  ON public.client_events
  FOR SELECT
  USING (
    submitted_by = auth.uid()
    OR EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid() AND p.role = 'admin'
    )
  );

-- Advisory ML output (Phase 4, rules_first): additive and nullable, so
-- existing rows and the current (pre-Phase-4) hybrid-mode write path are
-- both unaffected until the API is repointed to populate them.
ALTER TABLE public.case_records
  ADD COLUMN IF NOT EXISTS model_tier text,
  ADD COLUMN IF NOT EXISTS rules_fired jsonb,
  ADD COLUMN IF NOT EXISTS model_agreed boolean;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'case_records_model_tier_check'
  ) THEN
    ALTER TABLE public.case_records
      ADD CONSTRAINT case_records_model_tier_check
      CHECK (model_tier IS NULL OR model_tier IN ('ROUTINE', 'URGENT', 'EMERGENCY'));
  END IF;
END $$;

COMMIT;
