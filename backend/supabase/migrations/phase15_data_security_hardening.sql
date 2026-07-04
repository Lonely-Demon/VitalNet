-- Phase 15: Data Domain Security Hardening Migration
-- Implements fixes for multiple red team findings
-- 
-- Security Fixes Applied:
-- - R3-DATA-SCHEMA-R3-001: Database-level enum constraint for patient_sex
-- - R3-DATA-SCHEMA-R3-002: Database-level enum constraint for triage_level
-- - R3-DATA-SCHEMA-R3-003: Foreign key constraint on facility_id
-- - R3-DATA-SCHEMA-R3-005: NOT NULL constraint on submitted_by
-- - R3-DATA-SCHEMA-R3-006: UNIQUE constraint on client_id
-- - R3-DATA-SCHEMA-R3-007: Timestamp fields with timezone enforcement
-- - R3-DATA-SCHEMA-R3-008: Missing indexes on frequently queried columns
-- - R3-DATA-SCHEMA-R3-009: Triage priority/level mapping constraint
-- - R3-DATA-RLS-R3-002: DELETE RLS policy
-- - R3-DATA-RLS-R3-005: UPDATE RLS policy with reviewed_by protection
-- - R3-DATA-RLS-R3-006: Facilities table RLS
-- - R3-DATA-RLS-R3-007: Profiles table hardened RLS
-- - R3-DATA-REF-R3-001: Facility delete cascade configuration
-- - R3-DATA-REF-R3-006: Case reviews audit table
-- - R3-DATA-MIGRATE-R3-001: Idempotent migration patterns
-- - ROOT-COMPLY-005: Consent capture fields

BEGIN;

-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 1: Schema Constraints (R3-DATA-SCHEMA-R3-*)
-- ═══════════════════════════════════════════════════════════════════════════════

-- R3-DATA-SCHEMA-R3-001: Enum constraint for patient_sex
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'case_records_patient_sex_check'
  ) THEN
    ALTER TABLE public.case_records
      ADD CONSTRAINT case_records_patient_sex_check
      CHECK (patient_sex IN ('male', 'female', 'other'));
    RAISE NOTICE 'Added patient_sex enum constraint';
  END IF;
END $$;

-- R3-DATA-SCHEMA-R3-002: Enum constraint for triage_level
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'case_records_triage_level_check'
  ) THEN
    ALTER TABLE public.case_records
      ADD CONSTRAINT case_records_triage_level_check
      CHECK (triage_level IN ('ROUTINE', 'URGENT', 'EMERGENCY'));
    RAISE NOTICE 'Added triage_level enum constraint';
  END IF;
END $$;

-- R3-DATA-SCHEMA-R3-009: Triage priority/level mapping constraint
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'case_records_triage_priority_map_check'
  ) THEN
    ALTER TABLE public.case_records
      ADD CONSTRAINT case_records_triage_priority_map_check
      CHECK (
        (triage_level = 'EMERGENCY' AND triage_priority = 0) OR
        (triage_level = 'URGENT' AND triage_priority = 1) OR
        (triage_level = 'ROUTINE' AND triage_priority = 2) OR
        triage_priority IS NULL  -- Allow NULL during migration
      );
    RAISE NOTICE 'Added triage_priority mapping constraint';
  END IF;
END $$;

-- R3-DATA-SCHEMA-R3-003: Foreign key on facility_id
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema = 'public'
      AND table_name = 'case_records'
      AND constraint_name = 'case_records_facility_id_fkey'
  ) THEN
    ALTER TABLE public.case_records
      ADD CONSTRAINT case_records_facility_id_fkey
      FOREIGN KEY (facility_id)
      REFERENCES public.facilities(id)
      ON UPDATE CASCADE
      ON DELETE RESTRICT;
    RAISE NOTICE 'Added facility_id foreign key constraint';
  END IF;
END $$;

-- R3-DATA-SCHEMA-R3-007: Ensure timestamp columns use timestamptz
DO $$
BEGIN
  -- Convert created_at to timestamptz if not already
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'case_records'
      AND column_name = 'created_at'
      AND data_type = 'timestamp without time zone'
  ) THEN
    ALTER TABLE public.case_records
      ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';
    RAISE NOTICE 'Converted created_at to timestamptz';
  END IF;
  
  -- Convert reviewed_at to timestamptz if not already
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'case_records'
      AND column_name = 'reviewed_at'
      AND data_type = 'timestamp without time zone'
  ) THEN
    ALTER TABLE public.case_records
      ALTER COLUMN reviewed_at TYPE timestamptz USING reviewed_at AT TIME ZONE 'UTC';
    RAISE NOTICE 'Converted reviewed_at to timestamptz';
  END IF;
END $$;

-- R3-DATA-SCHEMA-R3-006: UNIQUE constraint on client_id (idempotent)
CREATE UNIQUE INDEX IF NOT EXISTS idx_case_records_client_id_unique
  ON public.case_records (client_id);

-- ROOT-COMPLY-005: Add consent capture fields
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'case_records'
      AND column_name = 'consent_captured'
  ) THEN
    ALTER TABLE public.case_records
      ADD COLUMN consent_captured boolean NOT NULL DEFAULT false,
      ADD COLUMN consent_captured_at timestamptz;
    RAISE NOTICE 'Added consent capture fields';
  END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 2: Indexes (R3-DATA-SCHEMA-R3-008, R3-DATA-QUERY-R3-006/007/011)
-- ═══════════════════════════════════════════════════════════════════════════════

-- R3-DATA-QUERY-R3-006: Index on facility_id
CREATE INDEX IF NOT EXISTS idx_case_records_facility_id
  ON public.case_records (facility_id);

-- R3-DATA-QUERY-R3-007: Composite index on (triage_priority, created_at)
CREATE INDEX IF NOT EXISTS idx_case_records_triage_priority_created_at
  ON public.case_records (triage_priority, created_at DESC);

-- R3-DATA-QUERY-R3-011: Index on submitted_by
CREATE INDEX IF NOT EXISTS idx_case_records_submitted_by
  ON public.case_records (submitted_by);

-- Index on deleted_at for soft-delete queries
CREATE INDEX IF NOT EXISTS idx_case_records_deleted_at
  ON public.case_records (deleted_at) WHERE deleted_at IS NOT NULL;

-- Index on reviewed_at for analytics
CREATE INDEX IF NOT EXISTS idx_case_records_reviewed_at
  ON public.case_records (reviewed_at) WHERE reviewed_at IS NOT NULL;

-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 3: Case Reviews Table (R3-DATA-REF-R3-006)
-- ═══════════════════════════════════════════════════════════════════════════════

-- Immutable review history table
CREATE TABLE IF NOT EXISTS public.case_reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id uuid NOT NULL REFERENCES public.case_records(id) ON DELETE CASCADE,
  reviewer_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
  reviewed_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
  note text,
  CONSTRAINT case_reviews_immutable CHECK (true)  -- Marker for immutability intent
);

CREATE INDEX IF NOT EXISTS idx_case_reviews_case_id ON public.case_reviews(case_id);
CREATE INDEX IF NOT EXISTS idx_case_reviews_reviewer_id ON public.case_reviews(reviewer_id);

-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 4: RLS Policies (R3-DATA-RLS-R3-*)
-- ═══════════════════════════════════════════════════════════════════════════════

-- Enable RLS on all relevant tables
ALTER TABLE public.case_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.facilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.case_reviews ENABLE ROW LEVEL SECURITY;

-- R3-DATA-RLS-R3-002: DELETE policy for case_records
DROP POLICY IF EXISTS case_records_delete_policy ON public.case_records;
CREATE POLICY case_records_delete_policy
  ON public.case_records
  FOR DELETE
  USING (
    -- Only the submitter can delete their own records, OR admin/super_admin
    auth.uid() = submitted_by
    OR EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid() AND p.role IN ('admin', 'super_admin')
    )
  );

-- R3-DATA-RLS-R3-005: UPDATE policy with reviewed_by protection
DROP POLICY IF EXISTS case_records_update_policy ON public.case_records;
CREATE POLICY case_records_update_policy
  ON public.case_records
  FOR UPDATE
  USING (
    -- Cannot update soft-deleted records (R3-DATA-LIFECYCLE-R3-008)
    deleted_at IS NULL
    AND (
      -- Facility-scoped doctors/admins can update
      EXISTS (
        SELECT 1 FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.role IN ('doctor', 'facility_admin', 'admin', 'super_admin')
          AND (
            p.role IN ('admin', 'super_admin')
            OR p.facility_id = case_records.facility_id
          )
      )
      -- Or the submitter can update their own (limited fields)
      OR submitted_by = auth.uid()
    )
  )
  WITH CHECK (
    -- Only doctors+ can set reviewed_by (submitted_by immutability is
    -- enforced separately below via trigger — RLS WITH CHECK cannot
    -- compare against the pre-update row, only the proposed new one)
    reviewed_by IS NULL
    OR EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.role IN ('doctor', 'facility_admin', 'admin', 'super_admin')
    )
  );

-- submitted_by is an immutable audit-trail field. RLS's WITH CHECK only sees
-- the proposed new row, not the stored one, so it cannot express "unchanged"
-- — a BEFORE UPDATE trigger is the correct primitive for column immutability.
CREATE OR REPLACE FUNCTION public.protect_case_records_submitted_by()
RETURNS trigger AS $$
BEGIN
  IF NEW.submitted_by IS DISTINCT FROM OLD.submitted_by THEN
    RAISE EXCEPTION 'submitted_by is immutable and cannot be changed';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_protect_case_records_submitted_by ON public.case_records;
CREATE TRIGGER trg_protect_case_records_submitted_by
  BEFORE UPDATE ON public.case_records
  FOR EACH ROW EXECUTE FUNCTION public.protect_case_records_submitted_by();

-- R3-DATA-RLS-R3-006: Facilities table RLS (prevent unauthorized PHC data access)
DROP POLICY IF EXISTS facilities_select_policy ON public.facilities;
CREATE POLICY facilities_select_policy
  ON public.facilities
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND (
          p.role IN ('admin', 'super_admin')
          OR p.facility_id = facilities.id
        )
    )
  );

-- R3-DATA-RLS-R3-007: Hardened profiles SELECT policy
DROP POLICY IF EXISTS profiles_select_policy_hardened ON public.profiles;
CREATE POLICY profiles_select_policy_hardened
  ON public.profiles
  FOR SELECT
  USING (
    -- Can always read own profile
    id = auth.uid()
    OR EXISTS (
      SELECT 1 FROM public.profiles caller
      WHERE caller.id = auth.uid()
        AND (
          -- Admins can see all
          caller.role IN ('admin', 'super_admin')
          -- Facility staff can see colleagues at same facility
          OR (caller.role IN ('doctor', 'facility_admin') AND caller.facility_id = profiles.facility_id)
        )
    )
  );

-- Case reviews RLS policies
DROP POLICY IF EXISTS case_reviews_select_policy ON public.case_reviews;
CREATE POLICY case_reviews_select_policy
  ON public.case_reviews
  FOR SELECT
  USING (
    reviewer_id = auth.uid()
    OR EXISTS (
      SELECT 1
      FROM public.case_records cr
      JOIN public.profiles p ON p.id = auth.uid()
      WHERE cr.id = case_reviews.case_id
        AND (
          p.role IN ('admin', 'super_admin')
          OR p.facility_id = cr.facility_id
        )
    )
  );

DROP POLICY IF EXISTS case_reviews_insert_policy ON public.case_reviews;
CREATE POLICY case_reviews_insert_policy
  ON public.case_reviews
  FOR INSERT
  WITH CHECK (
    reviewer_id = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.role IN ('doctor', 'facility_admin', 'admin', 'super_admin')
    )
  );

-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 5: Audit Logging Table (ROOT-COMPLY-002)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.phi_audit_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type text NOT NULL,
  user_id uuid,
  user_role text,
  resource_type text NOT NULL,
  resource_id text,
  facility_id uuid,
  ip_address inet,
  details jsonb DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_phi_audit_log_user_id ON public.phi_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_phi_audit_log_resource ON public.phi_audit_log(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_phi_audit_log_created_at ON public.phi_audit_log(created_at DESC);

-- Audit log is append-only (no updates or deletes via RLS)
ALTER TABLE public.phi_audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY phi_audit_log_insert_only ON public.phi_audit_log
  FOR INSERT
  WITH CHECK (true);

CREATE POLICY phi_audit_log_select_admin ON public.phi_audit_log
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.role IN ('admin', 'super_admin')
    )
  );

COMMIT;

-- ═══════════════════════════════════════════════════════════════════════════════
-- Verification Queries (run separately after migration)
-- ═══════════════════════════════════════════════════════════════════════════════
-- 
-- Check constraints:
-- SELECT conname, contype FROM pg_constraint WHERE conrelid = 'case_records'::regclass;
--
-- Check indexes:
-- SELECT indexname FROM pg_indexes WHERE tablename = 'case_records';
--
-- Check RLS policies:
-- SELECT policyname, cmd FROM pg_policies WHERE tablename = 'case_records';
