-- Phase 34: Drop case_referrals — a table with zero code references
-- anywhere in this repository (confirmed by a whole-repo grep across every
-- .py/.js/.jsx/.ts/.tsx file, not just backend/app and apps/api), fully
-- superseded by the `referrals` table (phase19_referrals.sql), and whose
-- three RLS policies had the same client-writable user_metadata JWT-trust
-- privilege-escalation bug documented and fixed elsewhere in
-- docs/DECISIONS.md §36 (phase32). Because Supabase exposes every public
-- table via its auto-generated PostgREST API regardless of whether this
-- codebase's own frontend queries it, those policies were a live,
-- exploitable access path — patching them would have removed the
-- vulnerability but left dead schema and any already-stored PHI-adjacent
-- referral rows (case_id/from_facility/to_facility/urgency/status) sitting
-- around indefinitely for no purpose. Dropping the table outright is the
-- data-minimization-correct outcome: no code path anywhere writes to or
-- reads from it, so there is nothing to break.
--
-- No FOREIGN KEY anywhere in the schema references case_referrals (verified
-- against schema_snapshot.sql), so this drop has no cascading effect on any
-- other table.

BEGIN;

DROP TABLE IF EXISTS public.case_referrals;

COMMIT;
