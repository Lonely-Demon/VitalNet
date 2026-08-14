-- Phase 41: Protocol Questions Supervisor global scope (make facility_id nullable)
-- (docs/DECISIONS.md §40)
--
-- Permits organisation-wide Protocol Assistant questions by allowing
-- public.protocol_questions.facility_id to be NULL when asked by a facility-unassigned
-- Supervisor. Existing FK and index are preserved; Phase 39 RLS policies already
-- permit Supervisor global select/insert/curation while maintaining strict facility
-- isolation for PHC Admin, Doctor, and ASHA Worker.

BEGIN;

ALTER TABLE public.protocol_questions
  ALTER COLUMN facility_id DROP NOT NULL;

COMMIT;
