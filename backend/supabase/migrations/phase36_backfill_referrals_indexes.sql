-- Phase 36: Backfill the two indexes phase19_referrals.sql silently failed
-- to create.
--
-- Found during code review of the PR that dropped case_referrals (phase34):
-- phase19_referrals.sql runs `CREATE INDEX IF NOT EXISTS idx_referrals_case_id
-- ON public.referrals(case_id)` and the same for idx_referrals_status.
-- Postgres index names are schema-scoped, not table-scoped — and
-- public.case_referrals (a different, since-dropped table) already had
-- indexes by those exact names when phase19 ran. `IF NOT EXISTS` treats
-- "an index by this name exists anywhere in the schema" as satisfied and
-- silently no-ops, so public.referrals — the table the referral workflow
-- actually uses — has been missing indexes on case_id and status ever
-- since, confirmed by backend/supabase/schema_snapshot.sql's live capture
-- (only idx_referrals_referring_facility/idx_referrals_receiving_facility
-- exist on public.referrals).
--
-- phase34 (this same PR) drops case_referrals and its indexes, freeing the
-- names — but doesn't recreate them on the table that actually needs them.
-- This migration does that.

BEGIN;

CREATE INDEX IF NOT EXISTS idx_referrals_case_id ON public.referrals(case_id);
CREATE INDEX IF NOT EXISTS idx_referrals_status ON public.referrals(status);

COMMIT;
