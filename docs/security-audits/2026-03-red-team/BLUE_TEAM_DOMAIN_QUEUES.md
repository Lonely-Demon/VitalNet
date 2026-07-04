# Blue Team Domain Queues

**Generated**: 2026-03-30 00:46:06
**Total queue items**: 433
**R1/R2 roots**: 180
**R3 net-new standalone**: 245
**Cross-domain extension collisions**: 2
**Unresolved extensions**: 6

## Queue Sizes

| Domain | Queue Items | P0 | P1 | P2 | P3 |
|--------|-------------|----|----|----|----|
| data | 61 | 18 | 28 | 13 | 2 |
| devops | 28 | 3 | 16 | 9 | 0 |
| manual-triage | 29 | 0 | 0 | 0 | 29 |
| merge | 2 | 2 | 0 | 0 | 0 |
| ml-clinical | 23 | 6 | 12 | 3 | 2 |
| performance | 38 | 4 | 11 | 22 | 1 |
| qa | 57 | 2 | 25 | 21 | 9 |
| reliability | 42 | 3 | 18 | 21 | 0 |
| security | 83 | 16 | 26 | 35 | 6 |
| ux | 70 | 3 | 22 | 37 | 8 |

---

## data

### R3-DATA-MIGRATE-R3-006: Baseline Schema Script Omits `patient_name` Required by Current Runtime
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: DATA-MIGRATE-R3-006
- **Location**: `Context/VitalNet_Phase6_Instructions.md:206`, `backend/app/models/schemas.py:8`, `backend/app/api/routes/cases.py:71`, `backend/app/api/routes/cases.py:152`

### R3-DATA-QUERY-R3-001: No Connection Pooling - New Supabase Client Created Per Request
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: DATA-QUERY-R3-001
- **Location**: `backend/app/core/database.py:26-33`

### R3-DATA-QUERY-R3-002: SELECT * on case_records Table Without Column Projection
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: DATA-QUERY-R3-002
- **Location**: `backend/app/api/routes/analytics_routes.py:27`

### R3-DATA-QUERY-R3-003: Five Sequential Queries in Analytics Summary - No Parallelization
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: DATA-QUERY-R3-003
- **Location**: `backend/app/api/routes/analytics_routes.py:33-68`

### R3-DATA-QUERY-R3-004: Unbounded Query on Admin Stats Endpoint
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: DATA-QUERY-R3-004
- **Location**: `backend/app/api/routes/admin_routes.py:216-217`

### R3-DATA-REF-R3-002: User-Deletion Cascade Chain Is Internally Inconsistent
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: DATA-REF-R3-002
- **Location**: `Context/VitalNet_Phase6_Instructions.md:169`, `Context/VitalNet_Phase6_Instructions.md:211`, `Context/VitalNet_Phase6_Instructions.md:239`, `Context/VitalNet_Phase6_Instructions.md:248`

### R3-DATA-RLS-R3-001: Admin Stats Endpoint Bypasses RLS via service_role Client
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: DATA-RLS-R3-001
- **Location**: `backend/app/api/routes/admin_routes.py:216-217`

### R3-DATA-RLS-R3-002: Missing DELETE RLS Policy Allows Unauthorized Case Purging
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: DATA-RLS-R3-002
- **Location**: Supabase RLS configuration (no DELETE policy exists)

### R3-DATA-RLS-R3-003: Frontend Anon Key Enables Direct RLS Bypass Attacks
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: DATA-RLS-R3-003
- **Location**: `frontend/src/lib/supabase.js:29-31` + `frontend/.env.local`

### R3-DATA-RLS-R3-004: Realtime Subscription Filter Can Be Overwritten by Client
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: DATA-RLS-R3-004
- **Location**: `frontend/src/hooks/useRealtimeCases.js:23-44`

### R3-DATA-RLS-R3-005: UPDATE RLS Policy Allows Privilege Escalation via reviewed_by Manipulation
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: DATA-RLS-R3-005
- **Location**: `backend/app/api/routes/cases.py:195-200` + Supabase RLS policy

### R3-DATA-SCHEMA-R3-001: Missing Database-Level Enum Constraint for patient_sex
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: DATA-SCHEMA-R3-001
- **Location**: `backend/app/models/schemas.py:10` (Pydantic only), Database constraint missing

### R3-DATA-SCHEMA-R3-002: Missing Database-Level Enum Constraint for triage_level
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: DATA-SCHEMA-R3-002
- **Location**: `backend/app/models/schemas.py:33`, Database constraint missing

### R3-DATA-SCHEMA-R3-003: Missing Foreign Key Constraint on facility_id
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: DATA-SCHEMA-R3-003
- **Location**: `backend/app/api/routes/cases.py:70`, Database schema missing FK

### R3-DATA-SCHEMA-R3-007: Timestamp Fields Missing Timezone Enforcement
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: DATA-SCHEMA-R3-007
- **Location**: `backend/app/api/routes/cases.py:94-96,198`, Database schema

### ROOT-COMPLY-001: PHI transmitted to LLM services without Data Processing Agreement
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: COMPLY-001
- **Location**: `backend/app/services/llm.py:100-125`

### ROOT-COMPLY-002: No audit logging for PHI access
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: COMPLY-002
- **Location**: `backend/app/api/routes/cases.py`

### ROOT-COMPLY-003: PHI stored in IndexedDB without encryption
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: COMPLY-003, SEC-CRYPTO-R3-003
- **Location**: `frontend/src/lib/offlineQueue.js`

### R3-DATA-LIFECYCLE-R3-003: Frontend deactivation path does not clear device-side PHI queues
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-LIFECYCLE-R3-003
- **Location**: `frontend/src/store/authStore.jsx:49`, `frontend/src/App.jsx:20`, `frontend/src/lib/offlineQueue.js:3`, `frontend/src/lib/offlineQueue.js:4`, `frontend/src/lib/offlineQueue.js:39`

### R3-DATA-MIGRATE-R3-001: Realtime Migration Is Labeled Idempotent but Uses Non-Idempotent DDL
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-MIGRATE-R3-001
- **Location**: `backend/supabase/migrations/phase10_realtime_setup.sql:8`, `backend/supabase/migrations/phase10_realtime_setup.sql:9`

### R3-DATA-MIGRATE-R3-002: Critical Schema Changes Are Executed Out-of-Band in SQL Editor (Not Migration-Controlled)
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-MIGRATE-R3-002
- **Location**: `docs/REBUILD_INSTRUCTIONS.md:560`, `docs/ARCHITECTURE_RESTRUCTURE.md:243`

### R3-DATA-MIGRATE-R3-003: Runbook Forces Non-Atomic, Stepwise DDL Execution (Partial-Migration Risk)
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-MIGRATE-R3-003
- **Location**: `docs/REBUILD_INSTRUCTIONS.md:560`, `docs/REBUILD_INSTRUCTIONS.md:567`, `docs/REBUILD_INSTRUCTIONS.md:579`

### R3-DATA-MIGRATE-R3-004: Recommended UNIQUE/Index DDL Is Lock-Heavy and Can Block Clinical Writes
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-MIGRATE-R3-004
- **Location**: `docs/REBUILD_INSTRUCTIONS.md:579`, `docs/REBUILD_INSTRUCTIONS.md:596`

### R3-DATA-MIGRATE-R3-007: Phase-6 Bootstrap SQL Is Not Re-runnable After Partial Failure
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-MIGRATE-R3-007
- **Location**: `Context/VitalNet_Phase6_Instructions.md:128`, `Context/VitalNet_Phase6_Instructions.md:198`, `Context/VitalNet_Phase6_Instructions.md:269`

### R3-DATA-MIGRATE-R3-009: No Schema Compatibility Gate Before Serving Traffic
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-MIGRATE-R3-009
- **Location**: `backend/app/main.py:112`, `backend/app/api/routes/cases.py:153`, `backend/app/api/routes/cases.py:157`

### R3-DATA-MIGRATE-R3-010: JWT Role-Hook Migration Depends on Manual Dashboard Toggle (Rollback Fragility)
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-MIGRATE-R3-010
- **Location**: `Context/VitalNet_Phase6_Instructions.md:323`, `backend/app/core/auth.py:55`, `backend/app/core/auth.py:61`

### R3-DATA-QUERY-R3-006: Missing Index on case_records.facility_id
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-QUERY-R3-006
- **Location**: Inferred from `analytics_routes.py:29`, `cases.py:156`

### R3-DATA-QUERY-R3-007: Missing Composite Index on (triage_priority, created_at)
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-QUERY-R3-007
- **Location**: `backend/app/api/routes/cases.py:157-159`

### R3-DATA-QUERY-R3-008: COUNT(*) Aggregation Without count='exact' Uses Estimate
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-QUERY-R3-008
- **Location**: `backend/app/api/routes/admin_routes.py:216-217`

### R3-DATA-REF-R3-001: Facility Delete Has No Explicit FK Child Action (Defaults to NO ACTION)
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-REF-R3-001
- **Location**: `Context/VitalNet_Phase6_Instructions.md:173`, `Context/VitalNet_Phase6_Instructions.md:212`

### R3-DATA-REF-R3-003: A Case Can Exist Without a Submitting User (Nullable FK + Service-Role Paths)
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-REF-R3-003
- **Location**: `Context/VitalNet_Phase6_Instructions.md:211`, `Context/VitalNet_Phase6_Instructions.md:278`, `backend/app/core/database.py:48`, `backend/app/api/routes/cases.py:230`

### R3-DATA-REF-R3-005: Facility Relationship Drift Between Profile FK and JWT Metadata
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-REF-R3-005
- **Location**: `backend/app/api/routes/cases.py:70`, `backend/app/api/routes/admin_routes.py:132`, `backend/app/api/routes/admin_routes.py:144`

### R3-DATA-REF-R3-007: No Constraint Ensures `case_records.facility_id` Matches Submitter's Profile Facility
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-REF-R3-007
- **Location**: `Context/VitalNet_Phase6_Instructions.md:211`, `Context/VitalNet_Phase6_Instructions.md:212`, `backend/app/api/routes/cases.py:70`, `backend/app/api/routes/analytics_routes.py:29`

### R3-DATA-REF-R3-008: `create_user` Assumes Trigger-Created Profile Exists (Can Produce Auth Users Without Profile Parent)
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-REF-R3-008
- **Location**: `Context/VitalNet_Phase6_Instructions.md:184`, `Context/VitalNet_Phase6_Instructions.md:198`, `backend/app/api/routes/admin_routes.py:105`, `backend/app/api/routes/admin_routes.py:106`

### R3-DATA-RLS-R3-006: No RLS Policy for facilities Table Allows Unauthorized PHC Data Exfiltration
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-RLS-R3-006
- **Location**: `backend/app/api/routes/admin_routes.py:183` + Supabase RLS config

### R3-DATA-RLS-R3-007: profiles Table RLS Allows ASHA Workers to Enumerate All Facility Staff
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-RLS-R3-007
- **Location**: Supabase RLS policy + `backend/app/api/routes/analytics_routes.py:65`

### R3-DATA-RLS-R3-008: Service Role Key Usage in Seed Script Violates Least Privilege
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-RLS-R3-008
- **Location**: `backend/seed_user.py:5`

### R3-DATA-SCHEMA-R3-004: Vital Signs Stored as Nullable Without Clinical Validation
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-SCHEMA-R3-004
- **Location**: `backend/app/models/schemas.py:15-19`, Database schema

### R3-DATA-SCHEMA-R3-005: Missing NOT NULL Constraint on submitted_by (PHI Audit Trail)
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-SCHEMA-R3-005
- **Location**: `backend/app/api/routes/cases.py:69`, Database schema

### R3-DATA-SCHEMA-R3-006: Missing UNIQUE Constraint on client_id (Duplicate Detection)
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-SCHEMA-R3-006
- **Location**: `backend/app/api/routes/cases.py:101`, Database schema

### R3-DATA-SCHEMA-R3-008: Missing Indexes on Frequently Queried Columns
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DATA-SCHEMA-R3-008
- **Location**: Multiple query patterns

### ROOT-COMPLY-004: No session inactivity timeout
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: COMPLY-004
- **Location**: `frontend/src/store/authStore.jsx`

### ROOT-COMPLY-005: No patient consent capture mechanism
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: COMPLY-005
- **Location**: `frontend/src/pages/IntakeForm.jsx`

### ROOT-COMPLY-006: No data retention policy implemented
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: COMPLY-006, DATA-LIFECYCLE-R3-002, DATA-LIFECYCLE-R3-004, DATA-LIFECYCLE-R3-005, PERF-MEM-R3-004
- **Location**: No implementation exists

### ROOT-COMPLY-007: No patient data deletion endpoint
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: COMPLY-007, DATA-LIFECYCLE-R3-001
- **Location**: `backend/app/api/routes/`

### ROOT-COMPLY-008: PHI visible in browser console logs
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: COMPLY-008
- **Location**: Multiple components with console.log

### R3-DATA-LIFECYCLE-R3-006: Realtime feed can reintroduce soft-deleted records into in-memory dashboards
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: DATA-LIFECYCLE-R3-006
- **Location**: `backend/supabase/migrations/phase10_realtime_setup.sql:5`, `frontend/src/hooks/useRealtimeCases.js:40`, `frontend/src/pages/Dashboard.jsx:75`, `backend/app/api/routes/cases.py:156`

### R3-DATA-LIFECYCLE-R3-007: User deactivation is account-state only and leaves all linked case lifecycle data active
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: DATA-LIFECYCLE-R3-007
- **Location**: `backend/app/api/routes/admin_routes.py:151`, `backend/app/api/routes/admin_routes.py:162`, `backend/app/api/routes/admin_routes.py:159`, `frontend/src/api/admin.js:35`

### R3-DATA-LIFECYCLE-R3-008: Soft-deleted records can still be mutated by review endpoint
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: DATA-LIFECYCLE-R3-008
- **Location**: `backend/app/api/routes/cases.py:195`, `backend/app/api/routes/cases.py:200`, `backend/app/api/routes/cases.py:156`, `backend/app/api/routes/cases.py:231`, `backend/app/api/routes/cases.py:266`

### R3-DATA-MIGRATE-R3-008: Seed Facility Insert Is Non-Idempotent and Duplicates on Replay
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: DATA-MIGRATE-R3-008
- **Location**: `Context/VitalNet_Phase6_Instructions.md:140`, `Context/VitalNet_Phase6_Instructions.md:161`

### R3-DATA-QUERY-R3-010: Inefficient Date Grouping in Analytics Emergency Rate
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: DATA-QUERY-R3-010
- **Location**: `backend/app/api/routes/analytics_routes.py:118-130`

### R3-DATA-QUERY-R3-011: No Index on case_records.submitted_by
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: DATA-QUERY-R3-011
- **Location**: `backend/app/api/routes/cases.py:230`, `analytics_routes.py:65-67`

### R3-DATA-REF-R3-006: No FK-Backed Child Table for Reviews (Mutable Inline Relation Overwrites History)
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: DATA-REF-R3-006
- **Location**: `Context/VitalNet_Phase6_Instructions.md:239`, `backend/app/api/routes/cases.py:195`

### R3-DATA-SCHEMA-R3-009: No Database-Level Constraint on triage_priority vs triage_level Mapping
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: DATA-SCHEMA-R3-009
- **Location**: `backend/app/api/routes/cases.py:88`, Database schema

### ROOT-COMPLY-009: Data minimization issues, access control gaps
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: COMPLY-009

### ROOT-COMPLY-010: Data minimization issues, access control gaps
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: COMPLY-010

### ROOT-COMPLY-011: Data minimization issues, access control gaps
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: COMPLY-011

### ROOT-COMPLY-012: Data minimization issues, access control gaps
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: COMPLY-012

### ROOT-COMPLY-013: Data minimization issues, access control gaps
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: COMPLY-013

### ROOT-COMPLY-014: Documentation gaps
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: COMPLY-014

### ROOT-COMPLY-015: Documentation gaps
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: COMPLY-015


---

## devops

### R3-DEVOPS-CICD-R3-001: Secrets are injected into PR jobs that execute repo-controlled code
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: DEVOPS-CICD-R3-001
- **Location**: `.github/workflows/ci.yml:4-29`

### R3-DEVOPS-DR-R3-002: Documented restore path can overwrite live production data
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: DEVOPS-DR-R3-002
- **Location**: `reports/red-team/devops/team-lead.md:396`

### R3-DEVOPS-MONITOR-R3-001: Degraded health checks still return HTTP 200
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: DEVOPS-MONITOR-R3-001
- **Location**: `backend/app/main.py:105`

### R3-DEVOPS-CICD-R3-002: GitHub Actions are referenced by mutable release tags
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DEVOPS-CICD-R3-002
- **Location**: `.github/workflows/ci.yml:11-12,35-36`

### R3-DEVOPS-CICD-R3-004: Python dependency resolution is non-hermetic in secret-bearing CI jobs
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DEVOPS-CICD-R3-004
- **Location**: `.github/workflows/ci.yml:18-19`, `backend/requirements.txt:1-8`, `backend/requirements.txt:13-14`, `backend/requirements.txt:17`, `backend/requirements.txt:20`

### R3-DEVOPS-CICD-R3-005: Frontend CI executes dependency install scripts from lockfile packages
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DEVOPS-CICD-R3-005
- **Location**: `.github/workflows/ci.yml:42`, `frontend/package-lock.json:3610`, `frontend/package-lock.json:5262`

### R3-DEVOPS-CONTAINER-R3-001: PR workflow exposes privileged secrets to untrusted code
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DEVOPS-CONTAINER-R3-001
- **Location**: `.github/workflows/ci.yml:24`

### R3-DEVOPS-CONTAINER-R3-004: Uvicorn is launched without worker and in-process connection guards
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DEVOPS-CONTAINER-R3-004
- **Location**: `backend/railway.toml:6`, `backend/Procfile:1`

### R3-DEVOPS-DR-R3-001: Backups are not restore-tested anywhere
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DEVOPS-DR-R3-001
- **Location**: `.github/workflows/ci.yml:1`

### R3-DEVOPS-DR-R3-004: Failover is blocked by single-endpoint architecture across API and database paths
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DEVOPS-DR-R3-004
- **Location**: `backend/app/core/config.py:5`, `backend/app/core/database.py:20`, `frontend/src/api/cases.js:6`

### R3-DEVOPS-DR-R3-005: ML recovery procedure rebuilds a different artifact than runtime expects
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DEVOPS-DR-R3-005
- **Location**: `AGENTS.md:20`, `backend/app/ml/classifier.py:13`, `backend/app/ml/classifier.py:31`, `backend/scripts/retrain_and_export.py:43`, `backend/scripts/retrain_and_export.py:505`

### R3-DEVOPS-DR-R3-006: DR scope excludes unsynced offline submissions, creating unrecoverable edge data loss
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DEVOPS-DR-R3-006
- **Location**: `frontend/src/lib/offlineQueue.js:3`, `frontend/src/lib/offlineQueue.js:39`, `docs/ARCHITECTURE_RESTRUCTURE.md:347`

### R3-DEVOPS-INFRA-R3-001: Public Health Check Becomes an Anonymous Internal-State Oracle
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DEVOPS-INFRA-R3-001
- **Location**: `backend/app/main.py:103-115`

### R3-DEVOPS-INFRA-R3-002: Admin Control Plane Is Exposed on the Same Public API Edge
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DEVOPS-INFRA-R3-002
- **Location**: `backend/app/main.py:79`, `backend/app/api/routes/admin_routes.py:8`, `frontend/src/api/admin.js:6`, `backend/railway.toml:6`

### R3-DEVOPS-MONITOR-R3-002: Health coverage misses the clinician write path and RLS-scoped auth path
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DEVOPS-MONITOR-R3-002
- **Location**: `backend/app/main.py:110`

### R3-DEVOPS-MONITOR-R3-004: LLM tier usage is persisted as `unknown`, eliminating degradation visibility
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: DEVOPS-MONITOR-R3-004
- **Location**: `backend/app/services/llm.py:210`, `backend/app/api/routes/cases.py:92`

### UNRESOLVED-DEVOPS-ENV-R3-001: Staging/Prod Can Inherit Local `.env.local` State
- **Type**: r3_extension_unresolved
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: DEVOPS-ENV-R3-001, DEVOPS-012
- **Location**: `backend/app/core/config.py:13`

### UNRESOLVED-DEVOPS-ENV-R3-004: Reachability Probe Uses a Different Base URL Than API Traffic
- **Type**: r3_extension_unresolved
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: DEVOPS-ENV-R3-004, DEVOPS-012
- **Location**: `frontend/src/lib/connectivity.js:8`, `frontend/src/stores/syncStore.js:17`, `frontend/src/stores/syncStore.js:53`

### UNRESOLVED-DEVOPS-ENV-R3-007: CI Frontend Build Is Staging-Pinned at Compile Time
- **Type**: r3_extension_unresolved
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: DEVOPS-ENV-R3-007, DEVOPS-012
- **Location**: `.github/workflows/ci.yml:47`, `frontend/src/api/cases.js:6`

### R3-DEVOPS-CICD-R3-003: The workflow does not restrict GITHUB_TOKEN permissions
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: DEVOPS-CICD-R3-003
- **Location**: `.github/workflows/ci.yml:1-47`

### R3-DEVOPS-CICD-R3-006: Checkout leaves repository token material available to later steps by default
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: DEVOPS-CICD-R3-006
- **Location**: `.github/workflows/ci.yml:11`, `.github/workflows/ci.yml:35`

### R3-DEVOPS-CONTAINER-R3-002: GitHub Actions are not pinned to immutable revisions
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: DEVOPS-CONTAINER-R3-002
- **Location**: `.github/workflows/ci.yml:11`

### R3-DEVOPS-CONTAINER-R3-003: Railway deployment defines no explicit runtime resource caps
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: DEVOPS-CONTAINER-R3-003
- **Location**: `backend/railway.toml:1`

### R3-DEVOPS-CONTAINER-R3-006: CI workflow has no timeout or run-concurrency guardrails
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: DEVOPS-CONTAINER-R3-006
- **Location**: `.github/workflows/ci.yml:1`, `.github/workflows/ci.yml:8`, `.github/workflows/ci.yml:33`

### R3-DEVOPS-DR-R3-003: Health check can go green after a bad restore
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: DEVOPS-DR-R3-003
- **Location**: `backend/app/main.py:105`

### UNRESOLVED-DEVOPS-CONTAINER-R3-005: Image hardening posture is not enforceable in current Nixpacks deployment
- **Type**: r3_extension_unresolved
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: yes
- **Source IDs**: DEVOPS-CONTAINER-R3-005, DEVOPS-011
- **Location**: `backend/railway.toml:2`

### UNRESOLVED-DEVOPS-ENV-R3-002: Misspelled Env Vars Fail Open Instead of Failing Fast
- **Type**: r3_extension_unresolved
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: yes
- **Source IDs**: DEVOPS-ENV-R3-002, DEVOPS-012
- **Location**: `backend/app/core/config.py:11`

### UNRESOLVED-DEVOPS-ENV-R3-005: `ENVIRONMENT` Exists in Env Files but Is Not Enforced by Runtime
- **Type**: r3_extension_unresolved
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: yes
- **Source IDs**: DEVOPS-ENV-R3-005, DEVOPS-012
- **Location**: `backend/.env:3`, `backend/app/core/config.py:4`, `backend/app/core/config.py:13`, `backend/app/main.py:58`


---

## manual-triage

### ROOT-R1R2-GAP-001: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-001

### ROOT-R1R2-GAP-002: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-002

### ROOT-R1R2-GAP-003: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-003

### ROOT-R1R2-GAP-004: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-004

### ROOT-R1R2-GAP-005: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-005

### ROOT-R1R2-GAP-006: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-006

### ROOT-R1R2-GAP-007: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-007

### ROOT-R1R2-GAP-008: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-008

### ROOT-R1R2-GAP-009: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-009

### ROOT-R1R2-GAP-010: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-010

### ROOT-R1R2-GAP-011: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-011

### ROOT-R1R2-GAP-012: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-012

### ROOT-R1R2-GAP-013: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-013

### ROOT-R1R2-GAP-014: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-014

### ROOT-R1R2-GAP-015: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-015

### ROOT-R1R2-GAP-016: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-016

### ROOT-R1R2-GAP-017: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-017

### ROOT-R1R2-GAP-018: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-018

### ROOT-R1R2-GAP-019: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-019

### ROOT-R1R2-GAP-020: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-020

### ROOT-R1R2-GAP-021: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-021

### ROOT-R1R2-GAP-022: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-022

### ROOT-R1R2-GAP-023: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-023

### ROOT-R1R2-GAP-024: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-024

### ROOT-R1R2-GAP-025: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-025

### ROOT-R1R2-GAP-026: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-026

### ROOT-R1R2-GAP-027: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-027

### ROOT-R1R2-GAP-028: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-028

### ROOT-R1R2-GAP-029: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: UNKNOWN
- **Combined Fix**: no
- **Source IDs**: R1R2-GAP-029


---

## merge

### CROSS-SEC-INJ-R3-004: Second-Order LLM Injection via Stored Case Notes
- **Type**: cross_domain_extension
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: SEC-INJ-R3-004, PENTEST-003, ML-DD-001
- **Location**: `backend/app/services/llm.py:100-125` + `backend/app/api/routes/cases.py:253-270`

### CROSS-SEC-SUPPLY-R3-003: python-jose 3.3.0 Contains Known JWT Signature Bypass (CVE-2022-29217)
- **Type**: cross_domain_extension
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: SEC-SUPPLY-R3-003, SEC-002, AUTH-DD-002
- **Location**: - `backend/requirements.txt:15` - `python-jose[cryptography]==3.3.0`


---

## ml-clinical

### ROOT-ML-DD-001: LLM fallback returns unstructured text parsed unsafely
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: ML-DD-001, SEC-INJ-R3-004, ML-FALLBACK-R3-002
- **Location**: `backend/app/services/llm.py:250-280`

### ROOT-ML-DD-002: ONNX returns ROUTINE on unknown label index (silent misclassification)
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: ML-DD-002
- **Location**: `frontend/src/utils/triageClassifier.js:380-381`

### ROOT-ML-DD-003: No confidence threshold on ML predictions
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: ML-DD-003, ML-CONF-R3-1
- **Location**: Multiple locations

### ROOT-ML-DD-004: Feature schema drift between frontend/backend
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: ML-DD-004, ML-FEAT-R3-2, ML-EDGE-R3-002
- **Location**: `frontend/src/utils/triageClassifier.js`, `backend/app/ml/clinical_features.py`

### ROOT-ML-DD-005: No validation of input ranges before inference
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: ML-DD-005, ML-EDGE-R3-001
- **Location**: `backend/app/ml/enhanced_classifier.py`

### ROOT-ML-DD-007: Clinical red flags not explicitly checked
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: ML-DD-007, ML-CLINICAL-R3-1
- **Location**: `backend/app/ml/enhanced_classifier.py`

### R3-ML-CLINICAL-R3-2: Missing vitals are treated as normal, creating unsafe downgrades
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: ML-CLINICAL-R3-2
- **Location**: `backend/app/ml/clinical_features.py:92`

### R3-ML-CLINICAL-R3-3: Impossible blood pressure combinations are accepted and never flagged clinically
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: ML-CLINICAL-R3-3
- **Location**: `backend/app/models/schemas.py:15`

### R3-ML-CONF-R3-3: LLM Briefing Drops Classifier Uncertainty Before Prompting
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: ML-CONF-R3-3
- **Location**: `backend/app/services/llm.py:122`

### R3-ML-DRIFT-R3-1: Model Artifacts Load Without Integrity Verification
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: ML-DRIFT-R3-1
- **Location**: `backend/app/ml/classifier.py:28`

### R3-ML-DRIFT-R3-2: Drift Metrics Are Training-Only and Never Turn Into Live Monitoring
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: ML-DRIFT-R3-2
- **Location**: `backend/app/ml/enhanced_classifier.py:245`

### R3-ML-EDGE-R3-003: Symptoms are not normalized before scoring
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: ML-EDGE-R3-003
- **Location**: `backend/app/ml/clinical_features.py:68`

### R3-ML-FALLBACK-R3-001: Generic fallback advice under-triages emergencies
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: ML-FALLBACK-R3-001
- **Location**: `backend/app/services/llm.py:263`

### R3-ML-FEAT-R3-1: Age 0 Is Silently Rewritten to Adult Defaults
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: ML-FEAT-R3-1
- **Location**: `backend/app/ml/clinical_features.py:97`

### R3-ML-FEAT-R3-3: Backend Feature Extraction Is Not Robust to Blank or Non-Finite Numeric Inputs
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: ML-FEAT-R3-3
- **Location**: `backend/app/ml/clinical_features.py:45`

### ROOT-ML-DD-006: No model versioning - frontend/backend can use mismatched models
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: ML-DD-006, ML-DRIFT-R3-3
- **Location**: No version check exists

### ROOT-ML-DD-008: No human override mechanism in triage flow
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: ML-DD-008
- **Location**: `frontend/src/pages/IntakeForm.jsx`

### ROOT-ML-DD-009: Model drift detection, calibration issues, edge case handling
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: ML-DD-009, ML-CONF-R3-2

### ROOT-ML-DD-010: Model drift detection, calibration issues, edge case handling
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: ML-DD-010

### ROOT-ML-DD-011: Model drift detection, calibration issues, edge case handling
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: ML-DD-011

### ROOT-ML-DD-012: Model drift detection, calibration issues, edge case handling
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: ML-DD-012

### ROOT-ML-DD-013: Documentation gaps
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: ML-DD-013

### ROOT-ML-DD-014: Documentation gaps
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: ML-DD-014


---

## performance

### R3-PERF-ASSET-R3-001: PWA Precache Missing Critical WASM Assets for Offline ML
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: PERF-ASSET-R3-001
- **Location**: `frontend/vite.config.js:28`

### ROOT-PERF-001: No code splitting - entire app loaded upfront (~2MB)
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: PERF-001, PERF-BUNDLE-R3-001, PERF-BUNDLE-R3-002
- **Location**: `frontend/vite.config.js`

### ROOT-PERF-002: ONNX runtime (~2MB) loaded for ALL users, even non-ASHA workers
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: PERF-002, PERF-BUNDLE-R3-003, PERF-BUNDLE-R3-004, PERF-NET-R3-02, QA-PERF-R3-004
- **Location**: `frontend/src/utils/triageClassifier.js:1-10`

### ROOT-PERF-006: N+1 query pattern in analytics endpoint
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: PERF-006, DATA-QUERY-R3-005
- **Location**: `backend/app/api/routes/analytics_routes.py:45-80`

### R3-PERF-MEM-R3-002: Overlapping offline sync runs retain queue snapshots
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: PERF-MEM-R3-002
- **Location**: `frontend/src/panels/ASHAPanel.jsx:31-54`

### R3-PERF-NET-R3-06: Reachability probe can target a different origin than real API traffic
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: PERF-NET-R3-06
- **Location**: `frontend/src/lib/connectivity.js:8,29-33`, `frontend/src/stores/syncStore.js:17,37,53-55`

### R3-PERF-RENDER-R3-001: Toast Provider Invalidates the Entire App on Every Toast
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: PERF-RENDER-R3-001
- **Location**: `frontend/src/App.jsx:38-44`

### R3-PERF-RENDER-R3-005: Dashboard Realtime UPDATE Path Rebuilds Entire Case Array on Miss
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: PERF-RENDER-R3-005
- **Location**: `frontend/src/pages/Dashboard.jsx:75-78`

### R3-PERF-VITALS-R3-003: Dashboard Hides All Clinical Queue UI Behind Initial Fetch
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: PERF-VITALS-R3-003
- **Location**: `frontend/src/pages/Dashboard.jsx:20`

### R3-PERF-VITALS-R3-004: Authenticated Cold Start Can Render a Blank Viewport
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: PERF-VITALS-R3-004
- **Location**: `frontend/src/App.jsx:33`

### R3-PERF-VITALS-R3-005: "Load More" Triggers Redundant First-Page Fetches and Extra Main-Thread Work
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: PERF-VITALS-R3-005
- **Location**: `frontend/src/pages/Dashboard.jsx:44`

### ROOT-PERF-003: Realtime subscription memory leak on unmount
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: PERF-003
- **Location**: `frontend/src/hooks/useRealtimeCases.js:45-60`

### ROOT-PERF-004: No virtualization for case lists (renders all DOM nodes)
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: PERF-004, PERF-MEM-R3-003
- **Location**: `frontend/src/pages/Dashboard.jsx:120-180`

### ROOT-PERF-005: BriefingCard re-renders on every parent state change
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: PERF-005, PERF-RENDER-R3-004
- **Location**: `frontend/src/components/BriefingCard.jsx`

### ROOT-PERF-007: No HTTP caching headers on static API responses
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: PERF-007
- **Location**: `backend/app/main.py`

### R3-PERF-BUNDLE-R3-005: Duplicate Service Worker Entry Points Create Redundant Dynamic-Import Edges
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-BUNDLE-R3-005
- **Location**: `frontend/src/main.jsx:5,14`, `frontend/src/components/UpdatePrompt.jsx:10,16`, `frontend/dist/.vite/manifest.json:7-10`

### R3-PERF-MEM-R3-001: Toast timeouts survive unmount
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-MEM-R3-001
- **Location**: `frontend/src/components/ToastProvider.jsx:21-26`

### R3-PERF-MEM-R3-005: Autosave path reopens IndexedDB on every debounce tick
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-MEM-R3-005
- **Location**: `frontend/src/pages/IntakeForm.jsx:105-110`, `frontend/src/hooks/useDraftSave.js:18-20`, `frontend/src/hooks/useDraftSave.js:57-60`

### R3-PERF-NET-R3-01: API responses are never compressed
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-NET-R3-01
- **Location**: `backend/app/main.py:49-73`

### R3-PERF-NET-R3-04: Service worker is registered twice
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-NET-R3-04
- **Location**: `frontend/src/main.jsx:13-21`

### R3-PERF-NET-R3-05: Dashboard pagination cursor is dropped, causing repeated page-1 fetches
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-NET-R3-05
- **Location**: `frontend/src/pages/Dashboard.jsx:44`, `frontend/src/api/cases.js:8-13`, `backend/app/api/routes/cases.py:162-167`

### R3-PERF-NET-R3-07: Two independent offline retry queues can replay the same submit twice
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-NET-R3-07
- **Location**: `frontend/vite.config.js:34-47`, `frontend/src/stores/syncStore.js:63-69,81-108`

### R3-PERF-RENDER-R3-002: AdminUsers Rerenders the Full User Grid on Every Local Edit
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-RENDER-R3-002
- **Location**: `frontend/src/components/admin/AdminUsers.jsx:27-247`

### R3-PERF-RENDER-R3-003: AnalyticsDashboard Recomputes Derived Charts on Every Re-render
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-RENDER-R3-003
- **Location**: `frontend/src/components/AnalyticsDashboard.jsx:63-167`

### R3-PERF-RENDER-R3-006: ASHAPanel Realtime Updates Re-render Intake Form During New Case Entry
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-RENDER-R3-006
- **Location**: `frontend/src/panels/ASHAPanel.jsx:62-74`, `frontend/src/panels/ASHAPanel.jsx:95`

### R3-PERF-RENDER-R3-007: AdminFacilities Keystrokes Invalidate Full Facilities Table
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-RENDER-R3-007
- **Location**: `frontend/src/components/admin/AdminFacilities.jsx:16`, `frontend/src/components/admin/AdminFacilities.jsx:91`, `frontend/src/components/admin/AdminFacilities.jsx:129-155`

### R3-PERF-VITALS-R3-001: Draft Rehydration Inserts Controls After First Paint
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-VITALS-R3-001
- **Location**: `frontend/src/pages/IntakeForm.jsx:92`

### R3-PERF-VITALS-R3-002: Offline Banner Pushes Clinical Content When Connectivity Changes
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-VITALS-R3-002
- **Location**: `frontend/src/components/OfflineBanner.jsx:29`

### R3-PERF-VITALS-R3-006: Infinite Box-Shadow Pulse on Emergency Cards Causes Paint-Heavy Jank
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-VITALS-R3-006
- **Location**: `frontend/src/components/BriefingCard.jsx:40`

### ROOT-PERF-008: Bundle analysis issues, font loading, image optimization gaps, service worker caching issues
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: yes
- **Source IDs**: PERF-008, PERF-ASSET-R3-002

### ROOT-PERF-009: Bundle analysis issues, font loading, image optimization gaps, service worker caching issues
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-009

### ROOT-PERF-010: Bundle analysis issues, font loading, image optimization gaps, service worker caching issues
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-010

### ROOT-PERF-011: Bundle analysis issues, font loading, image optimization gaps, service worker caching issues
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-011

### ROOT-PERF-012: Bundle analysis issues, font loading, image optimization gaps, service worker caching issues
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-012

### ROOT-PERF-013: Bundle analysis issues, font loading, image optimization gaps, service worker caching issues
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-013

### ROOT-PERF-014: Bundle analysis issues, font loading, image optimization gaps, service worker caching issues
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-014

### ROOT-PERF-015: Bundle analysis issues, font loading, image optimization gaps, service worker caching issues
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PERF-015

### R3-PERF-NET-R3-03: Identical case fetches are not coalesced
- **Type**: r3_net_new
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: PERF-NET-R3-03
- **Location**: `frontend/src/api/cases.js:8-18`


---

## qa

### R3-QA-SEC-R3-006: No regression coverage for service‑role key misuse (RLS bypass)
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: QA-SEC-R3-006
- **Location**: `backend/app/core/database.py:48-54`

### ROOT-CODE-008: Zero test coverage on safety-critical ML triage code
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: CODE-008
- **Location**: `backend/app/ml/`, `backend/tests/`

### R3-QA-A11Y-R3-001: No Automated Accessibility Regression Coverage
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-A11Y-R3-001
- **Location**: `frontend/tests/offline.spec.js:3-94`

### R3-QA-A11Y-R3-002: Custom Intake Controls Lack Keyboard and Name Regression Tests
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-A11Y-R3-002
- **Location**: `frontend/src/pages/IntakeForm.jsx:276-365`

### R3-QA-A11Y-R3-003: Briefing Expand/Collapse Semantics Are Unprotected by Tests
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-A11Y-R3-003
- **Location**: `frontend/src/components/BriefingCard.jsx:43-68`

### R3-QA-A11Y-R3-005: Update Prompt Modal Lacks Keyboard Trap and Escape Sequence Regression Test
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-A11Y-R3-005
- **Location**: `frontend/src/components/UpdatePrompt.jsx:28-48`

### R3-QA-A11Y-R3-007: Admin Dropdowns Lack Arrow-Key Navigation Regression Tests
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-A11Y-R3-007
- **Location**: `frontend/src/components/admin/AdminUsers.jsx:136-206`

### R3-QA-E2E-R3-002: Cached profile survives auth/profile fetch failure and misroutes the active role
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-E2E-R3-002
- **Location**: `frontend/src/store/authStore.jsx:28`

### R3-QA-E2E-R3-003: Emergency cases have no explicit handoff or escalation path
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-E2E-R3-003
- **Location**: `frontend/src/components/BriefingCard.jsx:127`

### R3-QA-E2E-R3-004: Role-based route guard missing from panel entry but present for component‑level views
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-E2E-R3-004
- **Location**: `frontend/src/components/RouteGuard.jsx:20`

### R3-QA-EDGE-R3-001: Intake submit can deadlock on local triage failure
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-EDGE-R3-001
- **Location**: `frontend/src/pages/IntakeForm.jsx:162`

### R3-QA-EDGE-R3-005: ONNX feature vector mismatch if patient_sex = 'other'
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-EDGE-R3-005
- **Location**: `frontend/src/utils/triageClassifier.js:130`

### R3-QA-INTEG-R3-001: Review-state transition has no end-to-end assertion
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-INTEG-R3-001
- **Location**: `backend/app/api/routes/cases.py:186`

### R3-QA-INTEG-R3-002: ASHA personal-submissions flow is unverified
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-INTEG-R3-002
- **Location**: `backend/app/api/routes/cases.py:207`

### R3-QA-INTEG-R3-006: LLM fallback‑chain integration is completely untested
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-INTEG-R3-006
- **Location**: `backend/app/services/llm.py:188`

### R3-QA-PERF-R3-001: No Load Tests for Analytics and Admin Aggregations
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-PERF-R3-001
- **Location**: `backend/app/api/routes/analytics_routes.py:25`, `backend/app/api/routes/admin_routes.py:211`, `backend/tests/test_cases_api.py:9`, `frontend/tests/offline.spec.js:3`

### R3-QA-PERF-R3-003: No Endurance Test for Repeated Triage Submission and Queue Drain
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-PERF-R3-003
- **Location**: `backend/app/api/routes/cases.py:50`, `frontend/src/stores/syncStore.js:81`, `backend/tests/test_cases_api.py:83`, `frontend/tests/offline.spec.js:36`

### R3-QA-PERF-R3-005: No Regression Tests for Queue Growth Under Network Churn
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-PERF-R3-005
- **Location**: `frontend/src/stores/syncStore.js:96-138`, `frontend/src/lib/connectivity.js:21-40`, `backend/app/api/routes/cases.py:50`

### R3-QA-SEC-R3-001: Admin privilege-escalation paths have no regression coverage
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-SEC-R3-001
- **Location**: `backend/tests/test_cases_api.py:20-148`

### R3-QA-SEC-R3-005: Rate-limiting logic lacks regression tests for bypass via tampered tokens
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-SEC-R3-005
- **Location**: `backend/app/api/routes/cases.py:27-44`

### R3-QA-SEC-R3-007: No tests for token‑parsing failures leading to RLS mismatch
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-SEC-R3-007
- **Location**: `backend/app/api/routes/cases.py:144-145`

### R3-QA-UNIT-R3-001: Role guard fallback paths are untested
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-UNIT-R3-001
- **Location**: `backend/app/core/auth.py:53`

### R3-QA-UNIT-R3-003: Offline queue sync branches lack deterministic unit tests
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-UNIT-R3-003
- **Location**: `frontend/src/stores/syncStore.js:31`

### R3-QA-UNIT-R3-005: ML clinical feature‑engineer edge‑case helper functions have zero unit coverage
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-UNIT-R3-005
- **Location**: `backend/app/ml/clinical_features.py:167`, `196`, `217`, `245`, `276`, `304`

### R3-QA-UNIT-R3-007: Uncertainty‑calculation branch in enhanced classifier untested
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: QA-UNIT-R3-007
- **Location**: `backend/app/ml/enhanced_classifier.py:215`

### ROOT-CODE-001: Schema validation differs between frontend and backend
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: CODE-001
- **Location**: `frontend/src/utils/validation.js`, `backend/app/models/schemas.py`

### ROOT-CODE-002: Magic numbers throughout codebase (no constants file)
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: CODE-002
- **Location**: Multiple files

### R3-QA-E2E-R3-005: Local triage state lingers after online submission, causing redundant UI display
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: QA-E2E-R3-005
- **Location**: `frontend/src/pages/IntakeForm.jsx:165`

### R3-QA-E2E-R3-006: Analytics dashboard live counter increments on INSERT but never resets or ages out
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: QA-E2E-R3-006
- **Location**: `frontend/src/components/AnalyticsDashboard.jsx:40`

### R3-QA-EDGE-R3-002: Review endpoint reports success even when no row changed
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: QA-EDGE-R3-002
- **Location**: `backend/app/api/routes/cases.py:195`

### R3-QA-EDGE-R3-007: Offline queue capacity check race can still exceed limit
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: QA-EDGE-R3-007
- **Location**: `frontend/src/lib/offlineQueue.js:33`

### R3-QA-EDGE-R3-008: Clinical feature engineer returns -1 for missing vitals, mismatched with ONNX fallback
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: QA-EDGE-R3-008
- **Location**: `backend/app/ml/clinical_features.py:71`

### R3-QA-INTEG-R3-003: Analytics scoping/aggregation lacks integration coverage
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: QA-INTEG-R3-003
- **Location**: `backend/app/api/routes/analytics_routes.py:10`

### R3-QA-INTEG-R3-004: Idempotent duplicate submission (client_id) flow has no integration test
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: QA-INTEG-R3-004
- **Location**: `backend/app/api/routes/cases.py:101`

### R3-QA-INTEG-R3-005: Rate‑limiting path is untested across all endpoint flows
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: QA-INTEG-R3-005
- **Location**: `backend/app/api/routes/cases.py:51`

### R3-QA-PERF-R3-002: CI Has No Latency or Throughput Budget Gates
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: QA-PERF-R3-002
- **Location**: `.github/workflows/ci.yml:15`, `.github/workflows/ci.yml:39`

### R3-QA-SEC-R3-003: Analytics facility-scoping is completely untested
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: QA-SEC-R3-003
- **Location**: `backend/tests/test_cases_api.py:20-148`

### R3-QA-SEC-R3-004: Input-fuzzing coverage is missing for cursor and ID parameters on case endpoints
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: QA-SEC-R3-004
- **Location**: `backend/tests/test_cases_api.py:63-147`

### R3-QA-SEC-R3-008: Missing regression tests for environment‑variable leakage in test‑runner logs
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: QA-SEC-R3-008
- **Location**: `backend/tests/test_cases_api.py:1-153`

### R3-QA-UNIT-R3-002: Bearer parsing in `get_db_session()` is not unit-covered
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: QA-UNIT-R3-002
- **Location**: `backend/app/core/database.py:36`

### R3-QA-UNIT-R3-004: Optional vital-field validation branches are untested
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: QA-UNIT-R3-004
- **Location**: `frontend/src/utils/validation.js:13`

### R3-QA-UNIT-R3-006: ONNX feature‑vector helper `containsAny` and `clamp` untested
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: QA-UNIT-R3-006
- **Location**: `frontend/src/utils/triageClassifier.js:110`, `115`

### R3-QA-UNIT-R3-008: Toast and RouteGuard component rendering edge‑cases have zero test coverage
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: QA-UNIT-R3-008
- **Location**: `frontend/src/components/ToastProvider.jsx:21` and `frontend/src/components/RouteGuard.jsx:4`

### ROOT-CODE-003: Dead code, inconsistent error handling, missing TypeScript/type hints
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: CODE-003

### ROOT-CODE-004: Dead code, inconsistent error handling, missing TypeScript/type hints
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: CODE-004

### ROOT-CODE-005: Dead code, inconsistent error handling, missing TypeScript/type hints
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: CODE-005

### ROOT-CODE-006: Dead code, inconsistent error handling, missing TypeScript/type hints
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: CODE-006

### ROOT-CODE-007: Dead code, inconsistent error handling, missing TypeScript/type hints
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: CODE-007

### R3-QA-EDGE-R3-004: Analytics buckets can misplace boundary timestamps
- **Type**: r3_net_new
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: QA-EDGE-R3-004
- **Location**: `backend/app/api/routes/analytics_routes.py:125`

### R3-QA-EDGE-R3-009: LLM fallback briefing omits _model_used key after tier cascade
- **Type**: r3_net_new
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: QA-EDGE-R3-009
- **Location**: `backend/app/services/llm.py:271`

### ROOT-CODE-009: Style inconsistencies, minor refactoring opportunities
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: CODE-009

### ROOT-CODE-010: Style inconsistencies, minor refactoring opportunities
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: CODE-010

### ROOT-CODE-011: Style inconsistencies, minor refactoring opportunities
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: CODE-011

### ROOT-CODE-012: Style inconsistencies, minor refactoring opportunities
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: CODE-012

### ROOT-CODE-013: Style inconsistencies, minor refactoring opportunities
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: CODE-013

### ROOT-CODE-014: Style inconsistencies, minor refactoring opportunities
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: CODE-014

### ROOT-CODE-015: Style inconsistencies, minor refactoring opportunities
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: CODE-015


---

## reliability

### R3-REL-RECOVER-R3-001: Startup hard-fails if the ML model cannot load
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: REL-RECOVER-R3-001
- **Location**: `backend/app/main.py:36-39`

### ROOT-CHAOS-001: No timeout on Supabase database calls
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: CHAOS-001, DATA-QUERY-R3-009
- **Location**: `backend/app/core/database.py`

### ROOT-REL-001: No React Error Boundary - component crash kills entire app
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: REL-001
- **Location**: `frontend/src/App.jsx`

### R3-REL-DATA-R3-001: Admin writes can split auth and profile state
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: REL-DATA-R3-001
- **Location**: `backend/app/api/routes/admin_routes.py:92-110,126-146`

### R3-REL-OBS-R3-001: Missing request correlation IDs in backend error logs
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: REL-OBS-R3-001
- **Location**: `backend/app/main.py:85`

### R3-REL-OBS-R3-002: Realtime subscription failures are invisible
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: REL-OBS-R3-002
- **Location**: `frontend/src/hooks/useRealtimeCases.js:21`

### R3-REL-RACE-R3-001: Auth Profile Fetch Can Overwrite Newer Session State
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: REL-RACE-R3-001
- **Location**: `frontend/src/store/authStore.jsx:12`

### R3-REL-RACE-R3-002: Realtime Update Can Be Lost Before Initial History Load Completes
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: REL-RACE-R3-002
- **Location**: `frontend/src/panels/ASHAPanel.jsx:57`

### R3-REL-RECOVER-R3-002: Auth success can resolve to a blank app with no recovery UI
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: REL-RECOVER-R3-002
- **Location**: `frontend/src/App.jsx:30-33`

### R3-REL-TIMEOUT-R3-02: Offline queue replays can run concurrently and duplicate expensive submissions
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: REL-TIMEOUT-R3-02
- **Location**: `frontend/src/panels/ASHAPanel.jsx:31`

### ROOT-CHAOS-002: No circuit breaker for LLM services
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: CHAOS-002, REL-CB-R3-001, REL-CB-R3-002
- **Location**: `backend/app/services/llm.py`

### ROOT-CHAOS-003: No timeout on frontend fetch calls
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: CHAOS-003, REL-TIMEOUT-R3-03
- **Location**: `frontend/src/api/cases.js`

### ROOT-CHAOS-004: Thundering herd on reconnection (all clients retry simultaneously)
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: CHAOS-004
- **Location**: `frontend/src/hooks/useRealtimeCases.js`

### ROOT-REL-002: No timeout on Gemini LLM calls (can hang indefinitely)
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: REL-002, REL-TIMEOUT-R3-01
- **Location**: `backend/app/services/llm.py:180-220`

### ROOT-REL-003: Retry logic missing on all API calls
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: REL-003
- **Location**: `frontend/src/api/cases.js`

### ROOT-REL-004: IndexedDB queue has no size limit (can exhaust storage)
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: REL-004, REL-RACE-R3-003, UX-OFFLINE-R3-006
- **Location**: `frontend/src/lib/offlineQueue.js:20-45`

### ROOT-REL-005: Sync failures silently swallowed
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: REL-005, REL-OBS-R3-004, REL-RECOVER-R3-003, REL-RECOVER-R3-004, UX-OFFLINE-R3-002, QA-E2E-R3-001
- **Location**: `frontend/src/stores/syncStore.js:80-95`

### ROOT-REL-006: No exponential backoff on retries
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: REL-006, QA-EDGE-R3-006
- **Location**: Multiple locations

### ROOT-REL-016: Minor logging gaps
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: REL-016, DEVOPS-MONITOR-R3-003

### ROOT-SYNC-DD-002: Multi-tab coordination issues, partial sync handling
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: SYNC-DD-002, UX-OFFLINE-R3-001, UX-OFFLINE-R3-005

### ROOT-SYNC-DD-003: Silent data loss on 4xx server errors (cases deleted from queue)
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: SYNC-DD-003, DATA-MIGRATE-R3-005
- **Location**: `frontend/src/stores/syncStore.js:117-125`

### R3-REL-CB-R3-003: Realtime Case Streams Have No Subscription Bulkhead
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: REL-CB-R3-003
- **Location**: `frontend/src/hooks/useRealtimeCases.js:18`

### R3-REL-DATA-R3-002: Facility toggle is a read-modify-write race
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: REL-DATA-R3-002
- **Location**: `backend/app/api/routes/admin_routes.py:197-206`

### R3-REL-DATA-R3-003: Case pagination is not stable across equal timestamps
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: REL-DATA-R3-003
- **Location**: `backend/app/api/routes/cases.py:149-179,224-247`

### R3-REL-DATA-R3-004: Review endpoint reports success without confirming persistence
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: REL-DATA-R3-004
- **Location**: `backend/app/api/routes/cases.py:195-201`

### R3-REL-OBS-R3-003: Safety-critical toasts auto-dismiss too quickly
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: REL-OBS-R3-003
- **Location**: `frontend/src/components/ToastProvider.jsx:21`

### ROOT-CHAOS-005: Cascading failure risks, recovery path gaps
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: CHAOS-005

### ROOT-CHAOS-006: Cascading failure risks, recovery path gaps
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: CHAOS-006

### ROOT-CHAOS-007: Cascading failure risks, recovery path gaps
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: CHAOS-007

### ROOT-CHAOS-008: Cascading failure risks, recovery path gaps
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: CHAOS-008

### ROOT-CHAOS-009: Cascading failure risks, recovery path gaps
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: CHAOS-009

### ROOT-CHAOS-010: Cascading failure risks, recovery path gaps
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: CHAOS-010

### ROOT-REL-007: Transaction handling gaps, stale data issues, race conditions
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: yes
- **Source IDs**: REL-007, QA-EDGE-R3-003

### ROOT-REL-008: Transaction handling gaps, stale data issues, race conditions
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: REL-008

### ROOT-REL-009: Transaction handling gaps, stale data issues, race conditions
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: REL-009

### ROOT-REL-010: Transaction handling gaps, stale data issues, race conditions
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: REL-010

### ROOT-REL-011: Transaction handling gaps, stale data issues, race conditions
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: REL-011

### ROOT-REL-012: Transaction handling gaps, stale data issues, race conditions
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: REL-012

### ROOT-REL-013: Transaction handling gaps, stale data issues, race conditions
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: REL-013

### ROOT-REL-014: Transaction handling gaps, stale data issues, race conditions
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: REL-014

### ROOT-REL-015: Transaction handling gaps, stale data issues, race conditions
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: REL-015

### ROOT-SYNC-DD-001: Multi-tab coordination issues, partial sync handling
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: yes
- **Source IDs**: SYNC-DD-001, PERF-NET-R3-08


---

## security

### R3-SEC-AUTH-R3-001: JWT Access Tokens Stored in Plaintext IndexedDB (Trivial Extraction)
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: SEC-AUTH-R3-001
- **Location**: `frontend/src/lib/supabase.js:4-27`

### R3-SEC-AUTH-R3-002: Race Condition in Authentication State Allows Unauthorized Access
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: SEC-AUTH-R3-002
- **Location**: `frontend/src/store/authStore.jsx:10-26`, `frontend/src/App.jsx:13-28`

### R3-SEC-CONFIG-R3-001: Plaintext Role Credentials Documented for Production Use
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: SEC-CONFIG-R3-001
- **Location**: `Context/test_credentials.md:3`, `Context/test_credentials.md:6`, `Context/test_credentials.md:7`, `Context/test_credentials.md:18`, `Context/test_credentials.md:19`, `Context/VitalNet_Phase6_Instructions.md:333`, `Context/VitalNet_Phase6_Instructions.md:334`, `Context/VitalNet_Phase6_Instructions.md:335`

### R3-SEC-CRYPTO-R3-001: Supabase Anon Key Exposed in Production Bundle
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: SEC-CRYPTO-R3-001
- **Location**: - `frontend/dist/assets/index-BGCXiES4.js` (production bundle)

### R3-SEC-INJ-R3-001: LLM Prompt Injection via Patient Input Fields
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: SEC-INJ-R3-001
- **Location**: `backend/app/services/llm.py:107-125`

### R3-SEC-INJ-R3-003: Log Injection with PHI Leakage
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: SEC-INJ-R3-003
- **Location**: `backend/app/api/routes/cases.py:110-113`

### R3-SEC-RBAC-R3-001: Arbitrary Role Assignment During User Creation
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: SEC-RBAC-R3-001
- **Location**: `backend/app/api/routes/admin_routes.py:82-111`

### R3-SEC-RBAC-R3-002: No Case Ownership Validation in Detail Endpoint
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: SEC-RBAC-R3-002
- **Location**: `backend/app/api/routes/cases.py:253-270`

### R3-SEC-SUPPLY-R3-001: Python 3.14 Runtime vs 3.13 CI/CD Version Skew Creates Untested Attack Surface
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: SEC-SUPPLY-R3-001
- **Location**: - Runtime: `python --version` returns `3.14.3`

### R3-SEC-SUPPLY-R3-002: 16 Unpinned Backend Dependencies Allow Phantom Dependency Attacks
- **Type**: r3_net_new
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: SEC-SUPPLY-R3-002
- **Location**: `backend/requirements.txt:1-20`

### ROOT-AUTH-DD-002: Deactivated users can still access API until token expires
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: AUTH-DD-002, SEC-AUTH-R3-003, SEC-SUPPLY-R3-003, DATA-REF-R3-004
- **Location**: `backend/app/core/auth.py:29-38`

### ROOT-PENTEST-001: Hardcoded Groq API key committed to repository
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: PENTEST-001, SEC-CRYPTO-R3-002, SEC-CONFIG-R3-002, SEC-CONFIG-R3-003
- **Location**: `backend/.env` (in git history)

### ROOT-PENTEST-002: SQL injection via unsanitized case search
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: PENTEST-002, SEC-INJ-R3-002
- **Location**: `backend/app/api/routes/cases.py:145`

### ROOT-PENTEST-003: XSS via case notes field (stored)
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: PENTEST-003, SEC-INJ-R3-004
- **Location**: `frontend/src/components/BriefingCard.jsx:78`

### ROOT-SEC-002: JWT payload decoded without verification; user_metadata.role used for authorization allowing privilege escalation
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: SEC-002, SEC-INJ-R3-008, SEC-SUPPLY-R3-003, DEVOPS-ENV-R3-006, DEVOPS-INFRA-R3-003, QA-SEC-R3-002, AUTH-DD-001
- **Location**: `backend/app/core/auth.py:55-58`

### ROOT-SEC-004: Role checks inconsistent across endpoints
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: SEC-004, SEC-RBAC-R3-003, SEC-RBAC-R3-009
- **Location**: Multiple route files

### R3-SEC-API-R3-001: Public OpenAPI / Swagger Exposure
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-API-R3-001
- **Location**: `backend/app/main.py:46`

### R3-SEC-AUTH-R3-004: Logout Does Not Clear IndexedDB Auth Tokens
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-AUTH-R3-004
- **Location**: `frontend/src/store/authStore.jsx:49`

### R3-SEC-AUTH-R3-005: No Token Binding - Stolen Tokens Usable on Any Device
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-AUTH-R3-005
- **Location**: `backend/app/core/auth.py:12-45`, `frontend/src/lib/supabase.js:29-40`

### R3-SEC-AUTH-R3-006: Frontend Role Authorization Bypassable via Direct API Access
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-AUTH-R3-006
- **Location**: `frontend/src/App.jsx:30-33`, all API routes

### R3-SEC-AUTH-R3-007: Profile Fetch Failure Leaves User in Indeterminate Auth State
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-AUTH-R3-007
- **Location**: `frontend/src/store/authStore.jsx:28-40`

### R3-SEC-CRYPTO-R3-004: Admin Password Policy Not Enforced Server-Side
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-CRYPTO-R3-004
- **Location**: - `backend/app/api/routes/admin_routes.py:81-111` (create_user endpoint)

### R3-SEC-CRYPTO-R3-005: Service Role Key Has No Expiration or Rotation
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-CRYPTO-R3-005
- **Location**: - `backend/.env.local:4`

### R3-SEC-INJ-R3-005: CSV Injection in Admin User Export
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-INJ-R3-005
- **Location**: `backend/app/api/routes/admin_routes.py:41-78` (list_users endpoint)

### R3-SEC-INJ-R3-006: NoSQL Injection via Supabase RLS Filter Manipulation
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-INJ-R3-006
- **Location**: `backend/app/api/routes/analytics_routes.py:26-30`

### R3-SEC-INJ-R3-009: LDAP Injection (Future Risk)
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-INJ-R3-009
- **Location**: N/A (not yet implemented)

### R3-SEC-RBAC-R3-004: Admin Can Elevate Own Role to Super Admin
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-RBAC-R3-004
- **Location**: `backend/app/api/routes/admin_routes.py:114-148`

### R3-SEC-RBAC-R3-005: No Facility-Based Filtering in Case Review Endpoint
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-RBAC-R3-005
- **Location**: `backend/app/api/routes/cases.py:186-201`

### R3-SEC-RBAC-R3-006: ASHA Workers Can Access Other ASHA Workers' Submissions via ID Manipulation
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-RBAC-R3-006
- **Location**: `backend/app/api/routes/cases.py:207-247`

### R3-SEC-RBAC-R3-007: No Audit Trail for Admin Privilege Operations
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-RBAC-R3-007
- **Location**: `backend/app/api/routes/admin_routes.py` (entire file)

### R3-SEC-RBAC-R3-008: Facility Toggle Endpoint Lacks Cascade Impact Analysis
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-RBAC-R3-008
- **Location**: `backend/app/api/routes/admin_routes.py:197-206`

### R3-SEC-SUPPLY-R3-004: serialize-javascript RCE in vite-plugin-pwa Build Chain (GHSA-5c6j-r48x-rmvq)
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-SUPPLY-R3-004
- **Location**: - Transitive dependency: `vite-plugin-pwa@1.2.0` → `workbox-build@7.4.0` → `@rollup/plugin-terser@0.4.4` → `serialize-javascript@6.0.2`

### R3-SEC-SUPPLY-R3-005: picomatch ReDoS Allows Build-Time DoS in Glob Patterns (GHSA-c2c7-rcm5-vvqj)
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-SUPPLY-R3-005
- **Location**: - Transitive: `vite-plugin-pwa@1.2.0` → `tinyglobby@0.2.15` → `picomatch@4.0.3`

### R3-SEC-SUPPLY-R3-006: axios 1.13.6 Does NOT Exist - Phantom Version in package.json
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-SUPPLY-R3-006
- **Location**: `frontend/package.json:15` - `"axios": "^1.13.6"`

### R3-SEC-SUPPLY-R3-007: uuid 13.0.0 is Future/Non-Existent Version - Possible Supply Chain Attack
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-SUPPLY-R3-007
- **Location**: - `frontend/package.json:21` - `"uuid": "^13.0.0"`

### R3-SEC-SUPPLY-R3-008: zod 4.3.6 is Unreleased Major Version - Schema Validation at Risk
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-SUPPLY-R3-008
- **Location**: - `frontend/package.json:24` - `"zod": "^4.3.6"`

### ROOT-AUTH-DD-003: Token refresh doesn't invalidate old tokens
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: AUTH-DD-003
- **Location**: `backend/app/core/auth.py`

### ROOT-AUTH-DD-004: Session fixation possible via token reuse
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: AUTH-DD-004
- **Location**: `backend/app/api/routes/auth.py`

### ROOT-SEC-001: No rate limiting on authentication endpoints
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: SEC-001, SEC-API-R3-002, SEC-AUTH-R3-008
- **Location**: `backend/app/api/routes/auth.py`

### ROOT-SEC-003: CORS allows all origins in development mode
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: SEC-003, DEVOPS-ENV-R3-003
- **Location**: `backend/app/main.py:25-30`

### ROOT-SEC-005: No CSRF protection on state-changing endpoints
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: SEC-005
- **Location**: `backend/app/main.py`

### ROOT-SEC-006: Various input validation gaps, missing security headers, verbose error messages, etc.
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: SEC-006, SEC-INJ-R3-007

### R3-SEC-API-R3-003: Bulk User Enumeration via Admin Directory Endpoint
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-API-R3-003
- **Location**: `backend/app/api/routes/admin_routes.py:41-78`

### R3-SEC-AUTH-R3-009: Token Refresh Race Condition Can Leave User Logged Out
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-AUTH-R3-009
- **Location**: `frontend/src/lib/supabase.js:35-36`, multiple API call sites

### R3-SEC-AUTH-R3-010: No Multi-Factor Authentication (MFA) Support
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-AUTH-R3-010
- **Location**: `frontend/src/pages/LoginPage.jsx:11-23`, entire auth flow

### R3-SEC-AUTH-R3-011: No Password Reset Flow Leads to Insecure Workarounds
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-AUTH-R3-011
- **Location**: `frontend/src/pages/LoginPage.jsx` (missing "Forgot Password?" link)

### R3-SEC-CRYPTO-R3-006: No HSTS Header on API Responses
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-CRYPTO-R3-006
- **Location**: - `backend/app/main.py` (missing security headers middleware)

### R3-SEC-CRYPTO-R3-007: JWT Algorithm Confusion Not Prevented
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-CRYPTO-R3-007
- **Location**: - `backend/app/core/auth.py:8` (algorithm specification)

### R3-SEC-INJ-R3-010: URL Parameter Pollution in Pagination
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-INJ-R3-010
- **Location**: `backend/app/api/routes/cases.py:128-130`

### R3-SEC-INJ-R3-011: React Key Injection (Low Exploitability)
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-INJ-R3-011
- **Location**: `frontend/src/components/BriefingCard.jsx:80-84`

### R3-SEC-INJ-R3-012: Template Injection in Future Email Notifications
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-INJ-R3-012
- **Location**: N/A (not yet implemented)

### R3-SEC-RBAC-R3-010: Frontend RouteGuard Only Checks Client-Side Role
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-RBAC-R3-010
- **Location**: `frontend/src/components/RouteGuard.jsx:4-33`

### R3-SEC-RBAC-R3-011: Role Enumeration via User Creation Endpoint
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-RBAC-R3-011
- **Location**: `backend/app/api/routes/admin_routes.py:82-111`

### R3-SEC-RBAC-R3-012: App.jsx Role Routing Trusts profile.role Without Backend Verification
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-RBAC-R3-012
- **Location**: `frontend/src/App.jsx:9-34`

### R3-SEC-SUPPLY-R3-009: CI/CD Installs Test Dependencies Without Hash Verification
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-SUPPLY-R3-009
- **Location**: `.github/workflows/ci.yml:18-19`

### R3-SEC-SUPPLY-R3-010: No Subresource Integrity (SRI) for CDN Assets in PWA
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-SUPPLY-R3-010
- **Location**: `frontend/vite.config.js:23-84` (PWA manifest)

### R3-SEC-SUPPLY-R3-011: brace-expansion DoS in CI/CD Glob Operations (GHSA-f886-m6hf-6m8v)
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-SUPPLY-R3-011
- **Location**: Transitive via workbox-build → minimatch → brace-expansion 2.0.2, 5.0.4

### R3-SEC-SUPPLY-R3-012: Missing Dependency Provenance and SBOM in CI/CD
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-SUPPLY-R3-012
- **Location**: `.github/workflows/ci.yml` (entire file)

### ROOT-AUTH-DD-005: Session timeout issues, concurrent session handling gaps
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: AUTH-DD-005

### ROOT-AUTH-DD-006: Session timeout issues, concurrent session handling gaps
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: AUTH-DD-006

### ROOT-AUTH-DD-007: Session timeout issues, concurrent session handling gaps
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: AUTH-DD-007

### ROOT-AUTH-DD-008: Session timeout issues, concurrent session handling gaps
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: AUTH-DD-008

### ROOT-AUTH-DD-009: Session timeout issues, concurrent session handling gaps
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: AUTH-DD-009

### ROOT-PENTEST-004: IDOR vulnerabilities, path traversal risks, dependency CVEs
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PENTEST-004

### ROOT-PENTEST-005: IDOR vulnerabilities, path traversal risks, dependency CVEs
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PENTEST-005

### ROOT-PENTEST-006: IDOR vulnerabilities, path traversal risks, dependency CVEs
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PENTEST-006

### ROOT-PENTEST-007: IDOR vulnerabilities, path traversal risks, dependency CVEs
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PENTEST-007

### ROOT-PENTEST-008: IDOR vulnerabilities, path traversal risks, dependency CVEs
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PENTEST-008

### ROOT-PENTEST-009: IDOR vulnerabilities, path traversal risks, dependency CVEs
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PENTEST-009

### ROOT-PENTEST-010: IDOR vulnerabilities, path traversal risks, dependency CVEs
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: PENTEST-010

### ROOT-SEC-007: Various input validation gaps, missing security headers, verbose error messages, etc.
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-007

### ROOT-SEC-008: Various input validation gaps, missing security headers, verbose error messages, etc.
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-008

### ROOT-SEC-009: Various input validation gaps, missing security headers, verbose error messages, etc.
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-009

### ROOT-SEC-010: Various input validation gaps, missing security headers, verbose error messages, etc.
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-010

### ROOT-SEC-011: Various input validation gaps, missing security headers, verbose error messages, etc.
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-011

### ROOT-SEC-012: Various input validation gaps, missing security headers, verbose error messages, etc.
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-012

### ROOT-SEC-013: Various input validation gaps, missing security headers, verbose error messages, etc.
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: SEC-013

### R3-SEC-API-R3-004: API Versioning Is Metadata Only
- **Type**: r3_net_new
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: SEC-API-R3-004
- **Location**: `backend/app/main.py:46`

### R3-SEC-AUTH-R3-012: Session Tokens Visible in Browser DevTools Network Tab
- **Type**: r3_net_new
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: SEC-AUTH-R3-012
- **Location**: All API calls with `Authorization: Bearer` headers

### R3-SEC-CRYPTO-R3-008: Missing Constant-Time Comparison for Tokens
- **Type**: r3_net_new
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: SEC-CRYPTO-R3-008
- **Location**: - `backend/app/core/auth.py:27` (string splitting, not constant-time comparison)

### R3-SEC-RBAC-R3-013: Profile Updates via Supabase Client Don't Validate Role Changes
- **Type**: r3_net_new
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: SEC-RBAC-R3-013
- **Location**: `frontend/src/store/authStore.jsx:28-40`

### ROOT-SEC-014: Minor logging issues, debug endpoints exposed
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: SEC-014

### ROOT-SEC-015: Minor logging issues, debug endpoints exposed
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: SEC-015


---

## ux

### ROOT-MOBILE-DD-001: Viewport not optimized for 320px minimum width
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: MOBILE-DD-001, UX-MOBILE-R3-005
- **Location**: `frontend/index.html`, various components

### ROOT-UX-001: Touch targets below 44x44px healthcare minimum
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: yes
- **Source IDs**: UX-001, UX-MOBILE-R3-004, UX-MOBILE-R3-006, MOBILE-DD-002
- **Location**: `frontend/src/components/NavBar.jsx:30-38`

### ROOT-UX-006: Native alert/confirm dialogs used instead of accessible modals
- **Type**: root_bundle
- **Priority**: P0
- **Max Severity**: CRITICAL
- **Combined Fix**: no
- **Source IDs**: UX-006
- **Location**: Multiple components

### R3-UX-A11Y-R3-001: Login fields have no programmatic labels
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: UX-A11Y-R3-001
- **Location**: `frontend/src/pages/LoginPage.jsx:49`

### R3-UX-A11Y-R3-002: Briefing cards are expand/collapse controls only for mouse users
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: UX-A11Y-R3-002
- **Location**: `frontend/src/components/BriefingCard.jsx:43`

### R3-UX-A11Y-R3-006: Intake form labels are visual only
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: UX-A11Y-R3-006
- **Location**: `frontend/src/pages/IntakeForm.jsx:446`

### R3-UX-A11Y-R3-007: Sex choice group lacks proper fieldset semantics
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: UX-A11Y-R3-007
- **Location**: `frontend/src/pages/IntakeForm.jsx:276`

### R3-UX-A11Y-R3-008: Intake form is not submitted as a form
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: UX-A11Y-R3-008
- **Location**: `frontend/src/pages/IntakeForm.jsx:248`

### R3-UX-FORM-R3-001: Patient intake fields can be silently autofilled with stale data
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: UX-FORM-R3-001
- **Location**: `frontend/src/pages/IntakeForm.jsx:269`

### R3-UX-FORM-R3-010: New user role is preselected to the lowest-privilege account type
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: UX-FORM-R3-010
- **Location**: `frontend/src/components/admin/AdminUsers.jsx:25,136-142`

### R3-UX-IA-R3-007: No affordance to clear auto-saved drafts traps users with stale data
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: UX-IA-R3-007
- **Location**: `frontend/src/pages/IntakeForm.jsx:104`

### R3-UX-IA-R3-008: Case review action is hidden behind a non-obvious disclosure
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: UX-IA-R3-008
- **Location**: `frontend/src/components/BriefingCard.jsx:6`

### R3-UX-IA-R3-010: Draft identity is keyed to the user, not the form instance
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: UX-IA-R3-010
- **Location**: `frontend/src/pages/IntakeForm.jsx:89`

### R3-UX-IA-R3-011: Emergency red flags are flattened into the same symptom grid as routine findings
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: UX-IA-R3-011
- **Location**: `frontend/src/pages/IntakeForm.jsx:35`

### R3-UX-LOAD-R3-001: Critical toasts disappear before clinical users can act
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: UX-LOAD-R3-001
- **Location**: `frontend/src/components/ToastProvider.jsx:24`

### R3-UX-LOAD-R3-002: Admin mutations have no in-flight or success feedback
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: UX-LOAD-R3-002
- **Location**: `frontend/src/components/admin/AdminUsers.jsx:71`

### R3-UX-OFFLINE-R3-004: Offline-Ready State Is Console-Only (No User Trust Signal)
- **Type**: r3_net_new
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: UX-OFFLINE-R3-004
- **Location**: `frontend/src/main.jsx:18`

### ROOT-MOBILE-DD-003: Virtual keyboard hides submit button on intake form
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: MOBILE-DD-003
- **Location**: `frontend/src/pages/IntakeForm.jsx`

### ROOT-MOBILE-DD-004: No offline indicator visible to users
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: MOBILE-DD-004
- **Location**: `frontend/src/App.jsx`

### ROOT-MOBILE-DD-005: Font loading causes layout shift (CLS)
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: MOBILE-DD-005
- **Location**: `frontend/index.html`

### ROOT-MOBILE-DD-006: PWA install flow, gesture conflicts, safe area issues
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: MOBILE-DD-006, UX-MOBILE-R3-001, UX-MOBILE-R3-002, UX-MOBILE-R3-003

### ROOT-UX-002: No visible focus indicators for keyboard navigation
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: UX-002, QA-A11Y-R3-006
- **Location**: `frontend/src/index.css`

### ROOT-UX-003: Toast notifications not announced to screen readers
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: UX-003, UX-A11Y-R3-004, UX-A11Y-R3-009, QA-A11Y-R3-004
- **Location**: `frontend/src/components/ToastProvider.jsx`

### ROOT-UX-004: Form validation errors not associated with inputs (aria-describedby)
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: yes
- **Source IDs**: UX-004, UX-FORM-R3-005
- **Location**: `frontend/src/pages/IntakeForm.jsx`

### ROOT-UX-005: Color contrast issues in low-light conditions
- **Type**: root_bundle
- **Priority**: P1
- **Max Severity**: HIGH
- **Combined Fix**: no
- **Source IDs**: UX-005
- **Location**: Various components

### R3-UX-A11Y-R3-003: Analytics charts have no textual equivalent
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-A11Y-R3-003
- **Location**: `frontend/src/components/AnalyticsDashboard.jsx:97`

### R3-UX-A11Y-R3-005: Tab-like navigation is missing tab semantics
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-A11Y-R3-005
- **Location**: `frontend/src/components/NavBar.jsx:28`

### R3-UX-A11Y-R3-010: Create-user disclosure button has no expanded state
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-A11Y-R3-010
- **Location**: `frontend/src/components/admin/AdminUsers.jsx:104`

### R3-UX-FORM-R3-002: Switching away from "Other" destroys the typed complaint
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-FORM-R3-002
- **Location**: `frontend/src/pages/IntakeForm.jsx:119`

### R3-UX-FORM-R3-003: Age entry can be silently truncated to the wrong value
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-FORM-R3-003
- **Location**: `frontend/src/pages/IntakeForm.jsx:145`

### R3-UX-FORM-R3-004: Lack of `<form>` element breaks "Enter" key submission
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-FORM-R3-004
- **Location**: `frontend/src/pages/IntakeForm.jsx:248-428`

### R3-UX-FORM-R3-006: Suboptimal mobile keyboard for numeric vital inputs
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-FORM-R3-006
- **Location**: `frontend/src/pages/IntakeForm.jsx:324`

### R3-UX-FORM-R3-007: Intake fields are missing programmatic label associations
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-FORM-R3-007
- **Location**: `frontend/src/pages/IntakeForm.jsx:446-452`

### R3-UX-FORM-R3-008: Login form omits autofill semantics for credentials
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-FORM-R3-008
- **Location**: `frontend/src/pages/LoginPage.jsx:35-68`

### R3-UX-FORM-R3-009: Cancelled admin user creation retains sensitive values
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-FORM-R3-009
- **Location**: `frontend/src/components/admin/AdminUsers.jsx:33-63,104-109`

### R3-UX-FORM-R3-011: New user password field is not marked as a new secret
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-FORM-R3-011
- **Location**: `frontend/src/components/admin/AdminUsers.jsx:118-131`

### R3-UX-FORM-R3-012: Facility type defaults to PHC without an explicit choice
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-FORM-R3-012
- **Location**: `frontend/src/components/admin/AdminFacilities.jsx:6-8,98-104`

### R3-UX-IA-R3-001: Admin stats are split across competing admin entry points
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-IA-R3-001
- **Location**: `frontend/src/panels/AdminPanel.jsx:8`

### R3-UX-IA-R3-002: User creation form exposes ASHA-specific data on every role
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-IA-R3-002
- **Location**: `frontend/src/components/admin/AdminUsers.jsx:117`

### R3-UX-IA-R3-006: Client-side tab filtering breaks server-side pagination mental model
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-IA-R3-006
- **Location**: `frontend/src/pages/Dashboard.jsx:83`

### R3-UX-IA-R3-009: Unknown roles fall through to a blank application shell
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-IA-R3-009
- **Location**: `frontend/src/App.jsx:30`

### R3-UX-IA-R3-012: Recovered draft is announced before users know what patient context it belongs to
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-IA-R3-012
- **Location**: `frontend/src/pages/IntakeForm.jsx:94`

### R3-UX-LOAD-R3-003: Intake submission uses one generic spinner for multiple hidden phases
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-LOAD-R3-003
- **Location**: `frontend/src/pages/IntakeForm.jsx:135`

### R3-UX-LOAD-R3-004: Draft restore is only signaled by a brief toast
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-LOAD-R3-004
- **Location**: `frontend/src/pages/IntakeForm.jsx:94-98`

### R3-UX-LOAD-R3-005: Refresh Queue blanks the live case list
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-LOAD-R3-005
- **Location**: `frontend/src/pages/Dashboard.jsx:21-35,91-105`

### R3-UX-LOAD-R3-006: Offline sync banner gives no progress or ETA
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-LOAD-R3-006
- **Location**: `frontend/src/components/OfflineBanner.jsx:42-47`

### R3-UX-OFFLINE-R3-003: Update Prompt Can Overlap Clinical Actions and Vanish Without Reminder
- **Type**: r3_net_new
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-OFFLINE-R3-003
- **Location**: `frontend/src/components/UpdatePrompt.jsx:27`

### ROOT-MOBILE-DD-007: PWA install flow, gesture conflicts, safe area issues
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: MOBILE-DD-007

### ROOT-MOBILE-DD-008: PWA install flow, gesture conflicts, safe area issues
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: MOBILE-DD-008

### ROOT-MOBILE-DD-009: PWA install flow, gesture conflicts, safe area issues
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: MOBILE-DD-009

### ROOT-MOBILE-DD-010: PWA install flow, gesture conflicts, safe area issues
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: MOBILE-DD-010

### ROOT-MOBILE-DD-011: PWA install flow, gesture conflicts, safe area issues
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: MOBILE-DD-011

### ROOT-MOBILE-DD-012: PWA install flow, gesture conflicts, safe area issues
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: MOBILE-DD-012

### ROOT-UX-007: Navigation patterns, information hierarchy, loading states
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-007

### ROOT-UX-008: Navigation patterns, information hierarchy, loading states
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-008

### ROOT-UX-009: Navigation patterns, information hierarchy, loading states
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-009

### ROOT-UX-010: Navigation patterns, information hierarchy, loading states
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-010

### ROOT-UX-011: Navigation patterns, information hierarchy, loading states
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-011

### ROOT-UX-012: Navigation patterns, information hierarchy, loading states
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-012

### ROOT-UX-013: Navigation patterns, information hierarchy, loading states
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-013

### ROOT-UX-014: Navigation patterns, information hierarchy, loading states
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-014

### ROOT-UX-015: Navigation patterns, information hierarchy, loading states
- **Type**: root_bundle
- **Priority**: P2
- **Max Severity**: MEDIUM
- **Combined Fix**: no
- **Source IDs**: UX-015

### R3-UX-IA-R3-003: Doctor refresh control uses queue language for a case dashboard
- **Type**: r3_net_new
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: UX-IA-R3-003
- **Location**: `frontend/src/pages/Dashboard.jsx:101`

### R3-UX-IA-R3-004: Complaint terminology changes mid-flow
- **Type**: r3_net_new
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: UX-IA-R3-004
- **Location**: `frontend/src/pages/IntakeForm.jsx:291`

### R3-UX-IA-R3-005: Empty state copy for 'All Cases' tab falsely implies a pending queue
- **Type**: r3_net_new
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: UX-IA-R3-005
- **Location**: `frontend/src/pages/Dashboard.jsx:116`

### R3-UX-MOBILE-R3-007: No touch-action CSS to prevent double-tap zoom and improve tap response
- **Type**: r3_net_new
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: UX-MOBILE-R3-007
- **Location**: `frontend/src/index.css` (entire file), all interactive components

### ROOT-MOBILE-DD-013: Minor polish issues
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: MOBILE-DD-013

### ROOT-MOBILE-DD-014: Minor polish issues
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: MOBILE-DD-014

### ROOT-MOBILE-DD-015: Minor polish issues
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: MOBILE-DD-015

### ROOT-MOBILE-DD-016: Minor polish issues
- **Type**: root_bundle
- **Priority**: P3
- **Max Severity**: LOW
- **Combined Fix**: no
- **Source IDs**: MOBILE-DD-016
