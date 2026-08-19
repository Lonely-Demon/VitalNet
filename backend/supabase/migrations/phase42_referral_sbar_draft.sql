-- Deterministic, provenance-preserving SBAR referral draft.
-- The draft is generated from already-authorized case fields at referral creation.
-- It is editable/displayable by the existing referral visibility policies.
BEGIN;

ALTER TABLE public.referrals
  ADD COLUMN IF NOT EXISTS sbar_version text,
  ADD COLUMN IF NOT EXISTS sbar_draft text;

COMMENT ON COLUMN public.referrals.sbar_version IS
  'Version of the deterministic SBAR formatter used to create sbar_draft.';
COMMENT ON COLUMN public.referrals.sbar_draft IS
  'Editable deterministic handoff draft generated from recorded case/referral fields; not a diagnosis or autonomous recommendation.';

COMMIT;
