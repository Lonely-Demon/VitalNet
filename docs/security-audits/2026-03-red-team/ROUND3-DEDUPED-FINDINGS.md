# Round 3 Deduplication and Extension Mapping Report
**Generated**: 2026-03-29 19:13:09

## Summary

- **Total Unique Findings**: 323
- **NET-NEW Findings**: 323
- **Extension Findings**: 0
- **Duplicates Merged**: 3
- **Duplicate Groups**: 3

## Severity Distribution (Deduped)

- **CRITICAL**: 39
- **HIGH**: 152
- **MEDIUM**: 120
- **LOW**: 12

## Domain Distribution (Deduped)

- **security**: 64
- **data**: 54
- **ux**: 53
- **qa**: 49
- **performance**: 33
- **devops**: 32
- **reliability**: 21
- **ml-clinical**: 17

---

## Duplicate Groups

Found 3 groups of duplicate findings that were merged:

### Group 1: SEC-API-R3-003
**Primary Title**: Bulk User Enumeration via Admin Directory Endpoint
**Merged From**: SEC-RBAC-R3-011

  - SEC-RBAC-R3-011: Role Enumeration via User Creation Endpoint

### Group 2: DATA-SCHEMA-R3-001
**Primary Title**: Missing Database-Level Enum Constraint for patient_sex
**Merged From**: DATA-SCHEMA-R3-002

  - DATA-SCHEMA-R3-002: Missing Database-Level Enum Constraint for triage_level

### Group 3: ML-FEAT-R3-1
**Primary Title**: Age 0 Is Silently Rewritten to Adult Defaults
**Merged From**: ML-EDGE-R3-001

  - ML-EDGE-R3-001: Age `0` is coerced to adult defaults


---

## All Unique Findings (Sorted by Severity)

### DATA-MIGRATE-R3-006: Baseline Schema Script Omits `patient_name` Required by Current Runtime
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: data / migration
- **Location**: ``Context/VitalNet_Phase6_Instructions.md:206`, `backend/app/models/schemas.py:8`, `backend/app/api/routes/cases.py:71`, `backend/app/api/routes/cases.py:152``

### DATA-QUERY-R3-001: No Connection Pooling - New Supabase Client Created Per Request
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: data / query-perf
- **Location**: ``backend/app/core/database.py:26-33``

### DATA-QUERY-R3-002: SELECT * on case_records Table Without Column Projection
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: data / query-perf
- **Location**: ``backend/app/api/routes/analytics_routes.py:27``

### DATA-QUERY-R3-003: Five Sequential Queries in Analytics Summary - No Parallelization
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: data / query-perf
- **Location**: ``backend/app/api/routes/analytics_routes.py:33-68``

### DATA-QUERY-R3-004: Unbounded Query on Admin Stats Endpoint
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: data / query-perf
- **Location**: ``backend/app/api/routes/admin_routes.py:216-217``

### DATA-QUERY-R3-005: N+1 Query Pattern in Admin User List - Profile + Auth User Join
- **Severity**: CRITICAL
- **Type**: Extension of PERF-006
- **Domain**: data / query-perf
- **Location**: ``backend/app/api/routes/admin_routes.py:52-78``

### DATA-REF-R3-002: User-Deletion Cascade Chain Is Internally Inconsistent
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: data / referential
- **Location**: ``Context/VitalNet_Phase6_Instructions.md:169`, `Context/VitalNet_Phase6_Instructions.md:211`, `Context/VitalNet_Phase6_Instructions.md:239`, `Context/VitalNet_Phase6_Instructions.md:248``

### DATA-RLS-R3-001: Admin Stats Endpoint Bypasses RLS via service_role Client
- **Severity**: CRITICAL
- **Type**: NET-NEW (Extension of DATA-R3-001 with different attack vector)
- **Domain**: data / rls-policy
- **Location**: ``backend/app/api/routes/admin_routes.py:216-217``

### DATA-RLS-R3-002: Missing DELETE RLS Policy Allows Unauthorized Case Purging
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: data / rls-policy
- **Location**: `Supabase RLS configuration (no DELETE policy exists)`

### DATA-RLS-R3-003: Frontend Anon Key Enables Direct RLS Bypass Attacks
- **Severity**: CRITICAL
- **Type**: NET-NEW (Distinct from SEC-009 which focused on anon key exposure; this focuses on RLS exploitation)
- **Domain**: data / rls-policy
- **Location**: ``frontend/src/lib/supabase.js:29-31` + `frontend/.env.local``

### DATA-RLS-R3-004: Realtime Subscription Filter Can Be Overwritten by Client
- **Severity**: CRITICAL
- **Type**: NET-NEW (Extension of DATA-R3-004 from team-lead, deeper exploitation path)
- **Domain**: data / rls-policy
- **Location**: ``frontend/src/hooks/useRealtimeCases.js:23-44``

### DATA-RLS-R3-005: UPDATE RLS Policy Allows Privilege Escalation via reviewed_by Manipulation
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: data / rls-policy
- **Location**: ``backend/app/api/routes/cases.py:195-200` + Supabase RLS policy`

### DATA-SCHEMA-R3-001: Missing Database-Level Enum Constraint for patient_sex
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: data / schema
- **Merged**: 1 duplicate(s)
  - From: DATA-SCHEMA-R3-002
- **Location**: ``backend/app/models/schemas.py:10` (Pydantic only), Database constraint missing`

### DATA-SCHEMA-R3-001: Missing Database-Level Enum Constraint for patient_sex
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: data / schema
- **Location**: ``backend/app/models/schemas.py:10` (Pydantic only), Database constraint missing`

### DATA-SCHEMA-R3-003: Missing Foreign Key Constraint on facility_id
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: data / schema
- **Location**: ``backend/app/api/routes/cases.py:70`, Database schema missing FK`

### DATA-SCHEMA-R3-007: Timestamp Fields Missing Timezone Enforcement
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: data / schema
- **Location**: ``backend/app/api/routes/cases.py:94-96,198`, Database schema`

### DEVOPS-CICD-R3-001: Secrets are injected into PR jobs that execute repo-controlled code
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: devops / ci-cd-security
- **Location**: ``.github/workflows/ci.yml:4-29``

### DEVOPS-DR-R3-002: Documented restore path can overwrite live production data
- **Severity**: CRITICAL
- **Type**: Extension of DEVOPS-R3-007
- **Domain**: devops / backup-dr
- **Location**: ``reports/red-team/devops/team-lead.md:396``

### DEVOPS-MONITOR-R3-001: Degraded health checks still return HTTP 200
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: devops / monitoring-alerting
- **Location**: ``backend/app/main.py:105``

### ML-CLINICAL-R3-1: Unhandled stroke/anaphylaxis/acute abdomen symptom set can bypass escalation
- **Severity**: CRITICAL
- **Type**: Extension of ML-DD-007
- **Domain**: ml-clinical / clinical-accuracy
- **Location**: ``backend/app/ml/clinical_features.py:78``

### PERF-ASSET-R3-001: PWA Precache Missing Critical WASM Assets for Offline ML
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: performance / asset-optimization
- **Location**: ``frontend/vite.config.js:28``

### QA-SEC-R3-006: No regression coverage for service‑role key misuse (RLS bypass)
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: qa / security-tests
- **Location**: ``backend/app/core/database.py:48-54``

### REL-RECOVER-R3-001: Startup hard-fails if the ML model cannot load
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: reliability / recovery
- **Location**: ``backend/app/main.py:36-39``

### SEC-AUTH-R3-001: JWT Access Tokens Stored in Plaintext IndexedDB (Trivial Extraction)
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: security / auth-flow
- **Location**: ``frontend/src/lib/supabase.js:4-27``

### SEC-AUTH-R3-002: Race Condition in Authentication State Allows Unauthorized Access
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: security / auth-flow
- **Location**: ``frontend/src/store/authStore.jsx:10-26`, `frontend/src/App.jsx:13-28``

### SEC-AUTH-R3-003: Backend Authorization Uses Stale JWT Role (No Profile Re-validation)
- **Severity**: CRITICAL
- **Type**: Extension of AUTH-DD-002
- **Domain**: security / auth-flow
- **Location**: ``backend/app/core/auth.py:53-59``

### SEC-CONFIG-R3-001: Plaintext Role Credentials Documented for Production Use
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: security / secrets-config
- **Location**: ``Context/test_credentials.md:3`, `Context/test_credentials.md:6`, `Context/test_credentials.md:7`, `Context/test_credentials.md:18`, `Context/test_credentials.md:19`, `Context/VitalNet_Phase6_Instructions.md:333`, `Context/VitalNet_Phase6_Instructions.md:334`, `Context/VitalNet_Phase6_Instructions.md:335``

### SEC-CRYPTO-R3-001: Supabase Anon Key Exposed in Production Bundle
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: security / crypto
- **Location**: `- `frontend/dist/assets/index-BGCXiES4.js` (production bundle)`

### SEC-CRYPTO-R3-002: JWT Secret Stored in Plaintext .env.local
- **Severity**: CRITICAL
- **Type**: Extension of PENTEST-001
- **Domain**: security / crypto
- **Location**: `- `backend/.env.local:3``

### SEC-INJ-R3-001: LLM Prompt Injection via Patient Input Fields
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: security / injection
- **Location**: ``backend/app/services/llm.py:107-125``

### SEC-INJ-R3-002: PostgREST Filter Injection via Composite Cursor
- **Severity**: CRITICAL
- **Type**: Extension of PENTEST-002
- **Domain**: security / injection
- **Location**: ``backend/app/api/routes/cases.py:164-167``

### SEC-INJ-R3-003: Log Injection with PHI Leakage
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: security / injection
- **Location**: ``backend/app/api/routes/cases.py:110-113``

### SEC-INJ-R3-004: Second-Order LLM Injection via Stored Case Notes
- **Severity**: CRITICAL
- **Type**: Extension of PENTEST-003 + ML-DD-001
- **Domain**: security / injection
- **Location**: ``backend/app/services/llm.py:100-125` + `backend/app/api/routes/cases.py:253-270``

### SEC-RBAC-R3-001: Arbitrary Role Assignment During User Creation
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: security / rbac
- **Location**: ``backend/app/api/routes/admin_routes.py:82-111``

### SEC-RBAC-R3-002: No Case Ownership Validation in Detail Endpoint
- **Severity**: CRITICAL
- **Type**: NET-NEW (Horizontal Privilege Escalation)
- **Domain**: security / rbac
- **Location**: ``backend/app/api/routes/cases.py:253-270``

### SEC-RBAC-R3-003: Analytics Endpoints Expose Cross-Facility Data
- **Severity**: CRITICAL
- **Type**: Extension of SEC-004 (inconsistent role checks)
- **Domain**: security / rbac
- **Location**: ``backend/app/api/routes/analytics_routes.py:10-89``

### SEC-SUPPLY-R3-001: Python 3.14 Runtime vs 3.13 CI/CD Version Skew Creates Untested Attack Surface
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: security / supply-chain
- **Location**: `- Runtime: `python --version` returns `3.14.3``

### SEC-SUPPLY-R3-002: 16 Unpinned Backend Dependencies Allow Phantom Dependency Attacks
- **Severity**: CRITICAL
- **Type**: NET-NEW
- **Domain**: security / supply-chain
- **Location**: ``backend/requirements.txt:1-20``

### SEC-SUPPLY-R3-003: python-jose 3.3.0 Contains Known JWT Signature Bypass (CVE-2022-29217)
- **Severity**: CRITICAL
- **Type**: Extension of AUTH-DD-001, AUTH-DD-002
- **Domain**: security / supply-chain
- **Location**: `- `backend/requirements.txt:15` - `python-jose[cryptography]==3.3.0``

### DATA-LIFECYCLE-R3-001: Case soft-delete fields are unreachable from API
- **Severity**: HIGH
- **Type**: Extension of COMPLY-007
- **Domain**: data / lifecycle
- **Location**: ``backend/app/api/routes/cases.py:124`, `backend/app/api/routes/cases.py:207`, `backend/app/api/routes/cases.py:253`, `Context/VitalNet_Phase6_Instructions.md:247``

### DATA-LIFECYCLE-R3-003: Frontend deactivation path does not clear device-side PHI queues
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / lifecycle
- **Location**: ``frontend/src/store/authStore.jsx:49`, `frontend/src/App.jsx:20`, `frontend/src/lib/offlineQueue.js:3`, `frontend/src/lib/offlineQueue.js:4`, `frontend/src/lib/offlineQueue.js:39``

### DATA-LIFECYCLE-R3-004: Offline queue has timestamp but no TTL or purge execution path
- **Severity**: HIGH
- **Type**: Extension of COMPLY-006
- **Domain**: data / lifecycle
- **Location**: ``frontend/src/lib/offlineQueue.js:42`, `frontend/src/lib/offlineQueue.js:53`, `frontend/src/stores/syncStore.js:81``

### DATA-MIGRATE-R3-001: Realtime Migration Is Labeled Idempotent but Uses Non-Idempotent DDL
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / migration
- **Location**: ``backend/supabase/migrations/phase10_realtime_setup.sql:8`, `backend/supabase/migrations/phase10_realtime_setup.sql:9``

### DATA-MIGRATE-R3-002: Critical Schema Changes Are Executed Out-of-Band in SQL Editor (Not Migration-Controlled)
- **Severity**: HIGH
- **Type**: Extension of DATA-R3-016
- **Domain**: data / migration
- **Location**: ``docs/REBUILD_INSTRUCTIONS.md:560`, `docs/ARCHITECTURE_RESTRUCTURE.md:243``

### DATA-MIGRATE-R3-003: Runbook Forces Non-Atomic, Stepwise DDL Execution (Partial-Migration Risk)
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / migration
- **Location**: ``docs/REBUILD_INSTRUCTIONS.md:560`, `docs/REBUILD_INSTRUCTIONS.md:567`, `docs/REBUILD_INSTRUCTIONS.md:579``

### DATA-MIGRATE-R3-004: Recommended UNIQUE/Index DDL Is Lock-Heavy and Can Block Clinical Writes
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / migration
- **Location**: ``docs/REBUILD_INSTRUCTIONS.md:579`, `docs/REBUILD_INSTRUCTIONS.md:596``

### DATA-MIGRATE-R3-005: Schema-Rollout Mismatch Can Permanently Drop Offline Cases
- **Severity**: HIGH
- **Type**: Extension of SYNC-DD-003
- **Domain**: data / migration
- **Location**: ``frontend/src/stores/syncStore.js:117`, `docs/REBUILD_INSTRUCTIONS.md:1097``

### DATA-MIGRATE-R3-007: Phase-6 Bootstrap SQL Is Not Re-runnable After Partial Failure
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / migration
- **Location**: ``Context/VitalNet_Phase6_Instructions.md:128`, `Context/VitalNet_Phase6_Instructions.md:198`, `Context/VitalNet_Phase6_Instructions.md:269``

### DATA-MIGRATE-R3-009: No Schema Compatibility Gate Before Serving Traffic
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / migration
- **Location**: ``backend/app/main.py:112`, `backend/app/api/routes/cases.py:153`, `backend/app/api/routes/cases.py:157``

### DATA-MIGRATE-R3-010: JWT Role-Hook Migration Depends on Manual Dashboard Toggle (Rollback Fragility)
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / migration
- **Location**: ``Context/VitalNet_Phase6_Instructions.md:323`, `backend/app/core/auth.py:55`, `backend/app/core/auth.py:61``

### DATA-QUERY-R3-006: Missing Index on case_records.facility_id
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / query-perf
- **Location**: `Inferred from `analytics_routes.py:29`, `cases.py:156``

### DATA-QUERY-R3-007: Missing Composite Index on (triage_priority, created_at)
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / query-perf
- **Location**: ``backend/app/api/routes/cases.py:157-159``

### DATA-QUERY-R3-008: COUNT(*) Aggregation Without count='exact' Uses Estimate
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / query-perf
- **Location**: ``backend/app/api/routes/admin_routes.py:216-217``

### DATA-QUERY-R3-009: Auth.admin.list_users() Has No Timeout
- **Severity**: HIGH
- **Type**: Extension of CHAOS-001
- **Domain**: data / query-perf
- **Location**: ``backend/app/api/routes/admin_routes.py:60``

### DATA-REF-R3-001: Facility Delete Has No Explicit FK Child Action (Defaults to NO ACTION)
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / referential
- **Location**: ``Context/VitalNet_Phase6_Instructions.md:173`, `Context/VitalNet_Phase6_Instructions.md:212``

### DATA-REF-R3-003: A Case Can Exist Without a Submitting User (Nullable FK + Service-Role Paths)
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / referential
- **Location**: ``Context/VitalNet_Phase6_Instructions.md:211`, `Context/VitalNet_Phase6_Instructions.md:278`, `backend/app/core/database.py:48`, `backend/app/api/routes/cases.py:230``

### DATA-REF-R3-004: Deactivated Users Can Still Be Persisted as `reviewed_by` Parents
- **Severity**: HIGH
- **Type**: Extension of AUTH-DD-002
- **Domain**: data / referential
- **Location**: ``backend/app/api/routes/admin_routes.py:162`, `backend/app/core/auth.py:55`, `backend/app/api/routes/cases.py:197``

### DATA-REF-R3-005: Facility Relationship Drift Between Profile FK and JWT Metadata
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / referential
- **Location**: ``backend/app/api/routes/cases.py:70`, `backend/app/api/routes/admin_routes.py:132`, `backend/app/api/routes/admin_routes.py:144``

### DATA-REF-R3-007: No Constraint Ensures `case_records.facility_id` Matches Submitter's Profile Facility
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / referential
- **Location**: ``Context/VitalNet_Phase6_Instructions.md:211`, `Context/VitalNet_Phase6_Instructions.md:212`, `backend/app/api/routes/cases.py:70`, `backend/app/api/routes/analytics_routes.py:29``

### DATA-REF-R3-008: `create_user` Assumes Trigger-Created Profile Exists (Can Produce Auth Users Without Profile Parent)
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / referential
- **Location**: ``Context/VitalNet_Phase6_Instructions.md:184`, `Context/VitalNet_Phase6_Instructions.md:198`, `backend/app/api/routes/admin_routes.py:105`, `backend/app/api/routes/admin_routes.py:106``

### DATA-RLS-R3-006: No RLS Policy for facilities Table Allows Unauthorized PHC Data Exfiltration
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / rls-policy
- **Location**: ``backend/app/api/routes/admin_routes.py:183` + Supabase RLS config`

### DATA-RLS-R3-007: profiles Table RLS Allows ASHA Workers to Enumerate All Facility Staff
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / rls-policy
- **Location**: `Supabase RLS policy + `backend/app/api/routes/analytics_routes.py:65``

### DATA-RLS-R3-008: Service Role Key Usage in Seed Script Violates Least Privilege
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / rls-policy
- **Location**: ``backend/seed_user.py:5``

### DATA-SCHEMA-R3-004: Vital Signs Stored as Nullable Without Clinical Validation
- **Severity**: HIGH
- **Type**: NET-NEW (different from CODE-001 schema validation difference)
- **Domain**: data / schema
- **Location**: ``backend/app/models/schemas.py:15-19`, Database schema`

### DATA-SCHEMA-R3-005: Missing NOT NULL Constraint on submitted_by (PHI Audit Trail)
- **Severity**: HIGH
- **Type**: NET-NEW (extends COMPLY-002: No audit logging for PHI access)
- **Domain**: data / schema
- **Location**: ``backend/app/api/routes/cases.py:69`, Database schema`

### DATA-SCHEMA-R3-006: Missing UNIQUE Constraint on client_id (Duplicate Detection)
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: data / schema
- **Location**: ``backend/app/api/routes/cases.py:101`, Database schema`

### DATA-SCHEMA-R3-008: Missing Indexes on Frequently Queried Columns
- **Severity**: HIGH
- **Type**: NET-NEW (extends PERF-006: N+1 query pattern)
- **Domain**: data / schema
- **Location**: `Multiple query patterns`

### DEVOPS-CICD-R3-002: GitHub Actions are referenced by mutable release tags
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: devops / ci-cd-security
- **Location**: ``.github/workflows/ci.yml:11-12,35-36``

### DEVOPS-CICD-R3-004: Python dependency resolution is non-hermetic in secret-bearing CI jobs
- **Severity**: HIGH
- **Type**: Extension of DEVOPS-CICD-R3-001
- **Domain**: devops / ci-cd-security
- **Location**: ``.github/workflows/ci.yml:18-19`, `backend/requirements.txt:1-8`, `backend/requirements.txt:13-14`, `backend/requirements.txt:17`, `backend/requirements.txt:20``

### DEVOPS-CICD-R3-005: Frontend CI executes dependency install scripts from lockfile packages
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: devops / ci-cd-security
- **Location**: ``.github/workflows/ci.yml:42`, `frontend/package-lock.json:3610`, `frontend/package-lock.json:5262``

### DEVOPS-CONTAINER-R3-001: PR workflow exposes privileged secrets to untrusted code
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: devops / container-deployment
- **Location**: ``.github/workflows/ci.yml:24``

### DEVOPS-CONTAINER-R3-004: Uvicorn is launched without worker and in-process connection guards
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: devops / container-deployment
- **Location**: ``backend/railway.toml:6`, `backend/Procfile:1``

### DEVOPS-DR-R3-001: Backups are not restore-tested anywhere
- **Severity**: HIGH
- **Type**: Extension of DEVOPS-R3-007
- **Domain**: devops / backup-dr
- **Location**: ``.github/workflows/ci.yml:1``

### DEVOPS-DR-R3-004: Failover is blocked by single-endpoint architecture across API and database paths
- **Severity**: HIGH
- **Type**: Extension of DEVOPS-R3-007
- **Domain**: devops / backup-dr
- **Location**: ``backend/app/core/config.py:5`, `backend/app/core/database.py:20`, `frontend/src/api/cases.js:6``

### DEVOPS-DR-R3-005: ML recovery procedure rebuilds a different artifact than runtime expects
- **Severity**: HIGH
- **Type**: Extension of REL-RECOVER-R3-001
- **Domain**: devops / backup-dr
- **Location**: ``AGENTS.md:20`, `backend/app/ml/classifier.py:13`, `backend/app/ml/classifier.py:31`, `backend/scripts/retrain_and_export.py:43`, `backend/scripts/retrain_and_export.py:505``

### DEVOPS-DR-R3-006: DR scope excludes unsynced offline submissions, creating unrecoverable edge data loss
- **Severity**: HIGH
- **Type**: Extension of DEVOPS-R3-007
- **Domain**: devops / backup-dr
- **Location**: ``frontend/src/lib/offlineQueue.js:3`, `frontend/src/lib/offlineQueue.js:39`, `docs/ARCHITECTURE_RESTRUCTURE.md:347``

### DEVOPS-ENV-R3-001: Staging/Prod Can Inherit Local `.env.local` State
- **Severity**: HIGH
- **Type**: Extension of DEVOPS-012
- **Domain**: devops / environment
- **Location**: ``backend/app/core/config.py:13``

### DEVOPS-ENV-R3-004: Reachability Probe Uses a Different Base URL Than API Traffic
- **Severity**: HIGH
- **Type**: Extension of DEVOPS-012
- **Domain**: devops / environment
- **Location**: ``frontend/src/lib/connectivity.js:8`, `frontend/src/stores/syncStore.js:17`, `frontend/src/stores/syncStore.js:53``

### DEVOPS-ENV-R3-007: CI Frontend Build Is Staging-Pinned at Compile Time
- **Severity**: HIGH
- **Type**: Extension of DEVOPS-012
- **Domain**: devops / environment
- **Location**: ``.github/workflows/ci.yml:47`, `frontend/src/api/cases.js:6``

### DEVOPS-INFRA-R3-001: Public Health Check Becomes an Anonymous Internal-State Oracle
- **Severity**: HIGH
- **Type**: Extension of SEC-R3-010
- **Domain**: devops / infra-security
- **Location**: ``backend/app/main.py:103-115``

### DEVOPS-INFRA-R3-002: Admin Control Plane Is Exposed on the Same Public API Edge
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: devops / infra-security
- **Location**: ``backend/app/main.py:79`, `backend/app/api/routes/admin_routes.py:8`, `frontend/src/api/admin.js:6`, `backend/railway.toml:6``

### DEVOPS-INFRA-R3-003: Submit-Path Ingress Throttling Trusts Unsigned JWT Claims
- **Severity**: HIGH
- **Type**: Extension of SEC-002
- **Domain**: devops / infra-security
- **Location**: ``backend/app/api/routes/cases.py:27-41`, `backend/app/api/routes/cases.py:50-56`, `backend/Procfile:1``

### DEVOPS-MONITOR-R3-002: Health coverage misses the clinician write path and RLS-scoped auth path
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: devops / monitoring-alerting
- **Location**: ``backend/app/main.py:110``

### DEVOPS-MONITOR-R3-003: Auth abuse signals (401/403 spikes) are not logged for detection or paging
- **Severity**: HIGH
- **Type**: Extension of REL-016
- **Domain**: devops / monitoring-alerting
- **Location**: ``backend/app/main.py:85`, `backend/app/core/auth.py:20``

### DEVOPS-MONITOR-R3-004: LLM tier usage is persisted as `unknown`, eliminating degradation visibility
- **Severity**: HIGH
- **Type**: Extension of ML-FALLBACK-R3-002
- **Domain**: devops / monitoring-alerting
- **Location**: ``backend/app/services/llm.py:210`, `backend/app/api/routes/cases.py:92``

### ML-CLINICAL-R3-2: Missing vitals are treated as normal, creating unsafe downgrades
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ml-clinical / clinical-accuracy
- **Location**: ``backend/app/ml/clinical_features.py:92``

### ML-CLINICAL-R3-3: Impossible blood pressure combinations are accepted and never flagged clinically
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ml-clinical / clinical-accuracy
- **Location**: ``backend/app/models/schemas.py:15``

### ML-CONF-R3-1: High Uncertainty Never Aborts Triage
- **Severity**: HIGH
- **Type**: Extension of ML-DD-003
- **Domain**: ml-clinical / confidence
- **Location**: ``backend/app/ml/enhanced_classifier.py:165``

### ML-CONF-R3-2: Offline Confidence Is Uncalibrated While Backend Confidence Is Calibrated
- **Severity**: HIGH
- **Type**: Extension of ML-DD-009
- **Domain**: ml-clinical / confidence
- **Location**: ``frontend/src/utils/triageClassifier.js:383``

### ML-CONF-R3-3: LLM Briefing Drops Classifier Uncertainty Before Prompting
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ml-clinical / confidence
- **Location**: ``backend/app/services/llm.py:122``

### ML-DRIFT-R3-1: Model Artifacts Load Without Integrity Verification
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ml-clinical / versioning-drift
- **Location**: ``backend/app/ml/classifier.py:28``

### ML-DRIFT-R3-2: Drift Metrics Are Training-Only and Never Turn Into Live Monitoring
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ml-clinical / versioning-drift
- **Location**: ``backend/app/ml/enhanced_classifier.py:245``

### ML-EDGE-R3-003: Symptoms are not normalized before scoring
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ml-clinical / model-edge
- **Location**: ``backend/app/ml/clinical_features.py:68``

### ML-FALLBACK-R3-001: Generic fallback advice under-triages emergencies
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ml-clinical / fallback-chain
- **Location**: ``backend/app/services/llm.py:263``

### ML-FALLBACK-R3-002: Parser failure path silently fail-opens into saved boilerplate briefings
- **Severity**: HIGH
- **Type**: Extension of ML-DD-001
- **Domain**: ml-clinical / fallback-chain
- **Location**: ``backend/app/services/llm.py:245`, `backend/app/api/routes/cases.py:63``

### ML-FEAT-R3-1: Age 0 Is Silently Rewritten to Adult Defaults
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ml-clinical / feature-pipeline
- **Merged**: 1 duplicate(s)
  - From: ML-EDGE-R3-001
- **Location**: ``backend/app/ml/clinical_features.py:97``

### ML-FEAT-R3-1: Age 0 Is Silently Rewritten to Adult Defaults
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ml-clinical / feature-pipeline
- **Location**: ``backend/app/ml/clinical_features.py:97``

### ML-FEAT-R3-3: Backend Feature Extraction Is Not Robust to Blank or Non-Finite Numeric Inputs
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ml-clinical / feature-pipeline
- **Location**: ``backend/app/ml/clinical_features.py:45``

### PERF-BUNDLE-R3-001: Role Panels Are Eagerly Bundled Into the Shell
- **Severity**: HIGH
- **Type**: Extension of PERF-001
- **Domain**: performance / bundle-splitting
- **Location**: ``frontend/src/App.jsx:1-7,30-32``

### PERF-BUNDLE-R3-004: ASHA History View Still Pulls Intake ONNX and Zod Stack
- **Severity**: HIGH
- **Type**: Extension of PERF-002
- **Domain**: performance / bundle-splitting
- **Location**: ``frontend/src/panels/ASHAPanel.jsx:3,95-97`, `frontend/src/pages/IntakeForm.jsx:6,8`, `frontend/src/hooks/useLocalTriage.js:3`, `frontend/src/utils/triageClassifier.js:6`, `frontend/src/utils/validation.js:9``

### PERF-MEM-R3-002: Overlapping offline sync runs retain queue snapshots
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: performance / memory-gc
- **Location**: ``frontend/src/panels/ASHAPanel.jsx:31-54``

### PERF-MEM-R3-003: Dashboard retains an unbounded case buffer and clones it per realtime event
- **Severity**: HIGH
- **Type**: Extension of PERF-004
- **Domain**: performance / memory-gc
- **Location**: ``frontend/src/pages/Dashboard.jsx:9`, `frontend/src/pages/Dashboard.jsx:47-51`, `frontend/src/pages/Dashboard.jsx:67-70`, `frontend/src/pages/Dashboard.jsx:76-78``

### PERF-NET-R3-06: Reachability probe can target a different origin than real API traffic
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: performance / network-caching
- **Location**: ``frontend/src/lib/connectivity.js:8,29-33`, `frontend/src/stores/syncStore.js:17,37,53-55``

### PERF-RENDER-R3-001: Toast Provider Invalidates the Entire App on Every Toast
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: performance / rendering
- **Location**: ``frontend/src/App.jsx:38-44``

### PERF-RENDER-R3-005: Dashboard Realtime UPDATE Path Rebuilds Entire Case Array on Miss
- **Severity**: HIGH
- **Type**: Extension of PERF-R3-005
- **Domain**: performance / rendering
- **Location**: ``frontend/src/pages/Dashboard.jsx:75-78``

### PERF-VITALS-R3-003: Dashboard Hides All Clinical Queue UI Behind Initial Fetch
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: performance / core-web-vitals
- **Location**: ``frontend/src/pages/Dashboard.jsx:20``

### PERF-VITALS-R3-004: Authenticated Cold Start Can Render a Blank Viewport
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: performance / core-web-vitals
- **Location**: ``frontend/src/App.jsx:33``

### PERF-VITALS-R3-005: "Load More" Triggers Redundant First-Page Fetches and Extra Main-Thread Work
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: performance / core-web-vitals
- **Location**: ``frontend/src/pages/Dashboard.jsx:44``

### QA-A11Y-R3-001: No Automated Accessibility Regression Coverage
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / accessibility-tests
- **Location**: ``frontend/tests/offline.spec.js:3-94``

### QA-A11Y-R3-002: Custom Intake Controls Lack Keyboard and Name Regression Tests
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / accessibility-tests
- **Location**: ``frontend/src/pages/IntakeForm.jsx:276-365``

### QA-A11Y-R3-003: Briefing Expand/Collapse Semantics Are Unprotected by Tests
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / accessibility-tests
- **Location**: ``frontend/src/components/BriefingCard.jsx:43-68``

### QA-A11Y-R3-005: Update Prompt Modal Lacks Keyboard Trap and Escape Sequence Regression Test
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / accessibility-tests
- **Location**: ``frontend/src/components/UpdatePrompt.jsx:28-48``

### QA-A11Y-R3-007: Admin Dropdowns Lack Arrow-Key Navigation Regression Tests
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / accessibility-tests
- **Location**: ``frontend/src/components/admin/AdminUsers.jsx:136-206``

### QA-E2E-R3-001: Offline sync drains but ASHA history never updates
- **Severity**: HIGH
- **Type**: Extension of REL-005
- **Domain**: qa / e2e-scenarios
- **Location**: ``frontend/src/panels/ASHAPanel.jsx:31``

### QA-E2E-R3-002: Cached profile survives auth/profile fetch failure and misroutes the active role
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / e2e-scenarios
- **Location**: ``frontend/src/store/authStore.jsx:28``

### QA-E2E-R3-003: Emergency cases have no explicit handoff or escalation path
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / e2e-scenarios
- **Location**: ``frontend/src/components/BriefingCard.jsx:127``

### QA-E2E-R3-004: Role-based route guard missing from panel entry but present for component‑level views
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / e2e-scenarios
- **Location**: ``frontend/src/components/RouteGuard.jsx:20``

### QA-EDGE-R3-001: Intake submit can deadlock on local triage failure
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / edge-cases
- **Location**: ``frontend/src/pages/IntakeForm.jsx:162``

### QA-EDGE-R3-005: ONNX feature vector mismatch if patient_sex = 'other'
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / edge-cases
- **Location**: ``frontend/src/utils/triageClassifier.js:130``

### QA-INTEG-R3-001: Review-state transition has no end-to-end assertion
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / integration-tests
- **Location**: ``backend/app/api/routes/cases.py:186``

### QA-INTEG-R3-002: ASHA personal-submissions flow is unverified
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / integration-tests
- **Location**: ``backend/app/api/routes/cases.py:207``

### QA-INTEG-R3-006: LLM fallback‑chain integration is completely untested
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / integration-tests
- **Location**: ``backend/app/services/llm.py:188``

### QA-PERF-R3-001: No Load Tests for Analytics and Admin Aggregations
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / performance-tests
- **Location**: ``backend/app/api/routes/analytics_routes.py:25`, `backend/app/api/routes/admin_routes.py:211`, `backend/tests/test_cases_api.py:9`, `frontend/tests/offline.spec.js:3``

### QA-PERF-R3-003: No Endurance Test for Repeated Triage Submission and Queue Drain
- **Severity**: HIGH
- **Type**: Extension of QA-R3-004
- **Domain**: qa / performance-tests
- **Location**: ``backend/app/api/routes/cases.py:50`, `frontend/src/stores/syncStore.js:81`, `backend/tests/test_cases_api.py:83`, `frontend/tests/offline.spec.js:36``

### QA-PERF-R3-005: No Regression Tests for Queue Growth Under Network Churn
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / performance-tests
- **Location**: ``frontend/src/stores/syncStore.js:96-138`, `frontend/src/lib/connectivity.js:21-40`, `backend/app/api/routes/cases.py:50``

### QA-SEC-R3-001: Admin privilege-escalation paths have no regression coverage
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / security-tests
- **Location**: ``backend/tests/test_cases_api.py:20-148``

### QA-SEC-R3-002: Forged-role auth bypass is not regression-tested on case detail/review flows
- **Severity**: HIGH
- **Type**: Extension of AUTH-DD-001
- **Domain**: qa / security-tests
- **Location**: ``backend/tests/test_cases_api.py:20-148``

### QA-SEC-R3-005: Rate-limiting logic lacks regression tests for bypass via tampered tokens
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / security-tests
- **Location**: ``backend/app/api/routes/cases.py:27-44``

### QA-SEC-R3-007: No tests for token‑parsing failures leading to RLS mismatch
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / security-tests
- **Location**: ``backend/app/api/routes/cases.py:144-145``

### QA-UNIT-R3-001: Role guard fallback paths are untested
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / unit-tests
- **Location**: ``backend/app/core/auth.py:53``

### QA-UNIT-R3-003: Offline queue sync branches lack deterministic unit tests
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / unit-tests
- **Location**: ``frontend/src/stores/syncStore.js:31``

### QA-UNIT-R3-005: ML clinical feature‑engineer edge‑case helper functions have zero unit coverage
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / unit-tests
- **Location**: ``backend/app/ml/clinical_features.py:167`, `196`, `217`, `245`, `276`, `304``

### QA-UNIT-R3-007: Uncertainty‑calculation branch in enhanced classifier untested
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: qa / unit-tests
- **Location**: ``backend/app/ml/enhanced_classifier.py:215``

### REL-CB-R3-001: Case Intake Is Serialized Behind LLM Enrichment
- **Severity**: HIGH
- **Type**: Extension of CHAOS-002
- **Domain**: reliability / circuit-breaker
- **Location**: ``backend/app/api/routes/cases.py:60``

### REL-CB-R3-002: Fallback Chain Traverses Every Tier With No Fast-Fail Budget
- **Severity**: HIGH
- **Type**: Extension of CHAOS-002
- **Domain**: reliability / circuit-breaker
- **Location**: ``backend/app/services/llm.py:205``

### REL-DATA-R3-001: Admin writes can split auth and profile state
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: reliability / data-consistency
- **Location**: ``backend/app/api/routes/admin_routes.py:92-110,126-146``

### REL-OBS-R3-001: Missing request correlation IDs in backend error logs
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: reliability / observability
- **Location**: ``backend/app/main.py:85``

### REL-OBS-R3-002: Realtime subscription failures are invisible
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: reliability / observability
- **Location**: ``frontend/src/hooks/useRealtimeCases.js:21``

### REL-OBS-R3-004: Queue sync failures lack structured telemetry
- **Severity**: HIGH
- **Type**: Extension of REL-005
- **Domain**: reliability / observability
- **Location**: ``frontend/src/stores/syncStore.js:99``

### REL-RACE-R3-001: Auth Profile Fetch Can Overwrite Newer Session State
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: reliability / race-concurrency
- **Location**: ``frontend/src/store/authStore.jsx:12``

### REL-RACE-R3-002: Realtime Update Can Be Lost Before Initial History Load Completes
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: reliability / race-concurrency
- **Location**: ``frontend/src/panels/ASHAPanel.jsx:57``

### REL-RECOVER-R3-002: Auth success can resolve to a blank app with no recovery UI
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: reliability / recovery
- **Location**: ``frontend/src/App.jsx:30-33``

### REL-RECOVER-R3-003: Offline queue sync rejects are not surfaced to the user
- **Severity**: HIGH
- **Type**: Extension of REL-005
- **Domain**: reliability / recovery
- **Location**: ``frontend/src/panels/ASHAPanel.jsx:31-50``

### REL-TIMEOUT-R3-01: No end-to-end request deadline for case submission
- **Severity**: HIGH
- **Type**: Extension of REL-002
- **Domain**: reliability / timeout-retry
- **Location**: ``backend/app/api/routes/cases.py:61``

### REL-TIMEOUT-R3-02: Offline queue replays can run concurrently and duplicate expensive submissions
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: reliability / timeout-retry
- **Location**: ``frontend/src/panels/ASHAPanel.jsx:31``

### SEC-API-R3-001: Public OpenAPI / Swagger Exposure
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: security / api-security
- **Location**: ``backend/app/main.py:46``

### SEC-API-R3-002: Extension of SEC-001 - Only `submit_case` Is Throttled
- **Severity**: HIGH
- **Type**: Extension of SEC-001
- **Domain**: security / api-security
- **Location**: ``backend/app/main.py:51-53``

### SEC-AUTH-R3-004: Logout Does Not Clear IndexedDB Auth Tokens
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: security / auth-flow
- **Location**: ``frontend/src/store/authStore.jsx:49``

### SEC-AUTH-R3-005: No Token Binding - Stolen Tokens Usable on Any Device
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: security / auth-flow
- **Location**: ``backend/app/core/auth.py:12-45`, `frontend/src/lib/supabase.js:29-40``

### SEC-AUTH-R3-006: Frontend Role Authorization Bypassable via Direct API Access
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: security / auth-flow
- **Location**: ``frontend/src/App.jsx:30-33`, all API routes`

### SEC-AUTH-R3-007: Profile Fetch Failure Leaves User in Indeterminate Auth State
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: security / auth-flow
- **Location**: ``frontend/src/store/authStore.jsx:28-40``

### SEC-CONFIG-R3-002: Service-Role Seed Script Hardcodes a Reusable Doctor Password
- **Severity**: HIGH
- **Type**: Extension of [PENTEST-001]
- **Domain**: security / secrets-config
- **Location**: ``backend/seed_user.py:5`, `backend/seed_user.py:16`, `backend/seed_user.py:24``

### SEC-CRYPTO-R3-003: Auth Tokens Stored Unencrypted in IndexedDB
- **Severity**: HIGH
- **Type**: Extension of COMPLY-003
- **Domain**: security / crypto
- **Location**: `- `frontend/src/lib/supabase.js:14-27` (auth token storage)`

### SEC-CRYPTO-R3-004: Admin Password Policy Not Enforced Server-Side
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: security / crypto
- **Location**: `- `backend/app/api/routes/admin_routes.py:81-111` (create_user endpoint)`

### SEC-CRYPTO-R3-005: Service Role Key Has No Expiration or Rotation
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: security / crypto
- **Location**: `- `backend/.env.local:4``

### SEC-INJ-R3-005: CSV Injection in Admin User Export
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: security / injection
- **Location**: ``backend/app/api/routes/admin_routes.py:41-78` (list_users endpoint)`

### SEC-INJ-R3-006: NoSQL Injection via Supabase RLS Filter Manipulation
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: security / injection
- **Location**: ``backend/app/api/routes/analytics_routes.py:26-30``

### SEC-INJ-R3-007: Error Message Injection via HTTP 500 Responses
- **Severity**: HIGH
- **Type**: Extension of SEC-006 (verbose error messages)
- **Domain**: security / injection
- **Location**: ``backend/app/api/routes/cases.py:115-118` + `backend/app/main.py:87-97``

### SEC-INJ-R3-008: Username Enumeration via Error Messages
- **Severity**: HIGH
- **Type**: Extension of AUTH-DD-001
- **Domain**: security / injection
- **Location**: ``backend/app/core/auth.py:40-45``

### SEC-INJ-R3-009: LDAP Injection (Future Risk)
- **Severity**: HIGH
- **Type**: NET-NEW (Proactive)
- **Domain**: security / injection
- **Location**: `N/A (not yet implemented)`

### SEC-RBAC-R3-004: Admin Can Elevate Own Role to Super Admin
- **Severity**: HIGH
- **Type**: NET-NEW (Self-Escalation)
- **Domain**: security / rbac
- **Location**: ``backend/app/api/routes/admin_routes.py:114-148``

### SEC-RBAC-R3-005: No Facility-Based Filtering in Case Review Endpoint
- **Severity**: HIGH
- **Type**: Extension of SEC-RBAC-R3-002 (Horizontal Access)
- **Domain**: security / rbac
- **Location**: ``backend/app/api/routes/cases.py:186-201``

### SEC-RBAC-R3-006: ASHA Workers Can Access Other ASHA Workers' Submissions via ID Manipulation
- **Severity**: HIGH
- **Type**: NET-NEW (Horizontal Privilege Escalation)
- **Domain**: security / rbac
- **Location**: ``backend/app/api/routes/cases.py:207-247``

### SEC-RBAC-R3-007: No Audit Trail for Admin Privilege Operations
- **Severity**: HIGH
- **Type**: NET-NEW (Compliance / Forensics Gap)
- **Domain**: security / rbac
- **Location**: ``backend/app/api/routes/admin_routes.py` (entire file)`

### SEC-RBAC-R3-008: Facility Toggle Endpoint Lacks Cascade Impact Analysis
- **Severity**: HIGH
- **Type**: NET-NEW (Data Integrity / Authorization)
- **Domain**: security / rbac
- **Location**: ``backend/app/api/routes/admin_routes.py:197-206``

### SEC-RBAC-R3-009: Admin Stats Endpoint Returns User Count Without RLS Enforcement
- **Severity**: HIGH
- **Type**: Extension of SEC-004 (inconsistent role checks)
- **Domain**: security / rbac
- **Location**: ``backend/app/api/routes/admin_routes.py:211-237``

### SEC-SUPPLY-R3-004: serialize-javascript RCE in vite-plugin-pwa Build Chain (GHSA-5c6j-r48x-rmvq)
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: security / supply-chain
- **Location**: `- Transitive dependency: `vite-plugin-pwa@1.2.0` → `workbox-build@7.4.0` → `@rollup/plugin-terser@0.4.4` → `serialize-javascript@6.0.2``

### SEC-SUPPLY-R3-005: picomatch ReDoS Allows Build-Time DoS in Glob Patterns (GHSA-c2c7-rcm5-vvqj)
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: security / supply-chain
- **Location**: `- Transitive: `vite-plugin-pwa@1.2.0` → `tinyglobby@0.2.15` → `picomatch@4.0.3``

### SEC-SUPPLY-R3-006: axios 1.13.6 Does NOT Exist - Phantom Version in package.json
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: security / supply-chain
- **Location**: ``frontend/package.json:15` - `"axios": "^1.13.6"``

### SEC-SUPPLY-R3-007: uuid 13.0.0 is Future/Non-Existent Version - Possible Supply Chain Attack
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: security / supply-chain
- **Location**: `- `frontend/package.json:21` - `"uuid": "^13.0.0"``

### SEC-SUPPLY-R3-008: zod 4.3.6 is Unreleased Major Version - Schema Validation at Risk
- **Severity**: HIGH
- **Type**: NET-NEW (related to CODE-001: schema drift)
- **Domain**: security / supply-chain
- **Location**: `- `frontend/package.json:24` - `"zod": "^4.3.6"``

### UX-A11Y-R3-001: Login fields have no programmatic labels
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ux / accessibility-wcag
- **Location**: ``frontend/src/pages/LoginPage.jsx:49``

### UX-A11Y-R3-002: Briefing cards are expand/collapse controls only for mouse users
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ux / accessibility-wcag
- **Location**: ``frontend/src/components/BriefingCard.jsx:43``

### UX-A11Y-R3-006: Intake form labels are visual only
- **Severity**: HIGH
- **Type**: Extension of UX-A11Y-R3-001
- **Domain**: ux / accessibility-wcag
- **Location**: ``frontend/src/pages/IntakeForm.jsx:446``

### UX-A11Y-R3-007: Sex choice group lacks proper fieldset semantics
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ux / accessibility-wcag
- **Location**: ``frontend/src/pages/IntakeForm.jsx:276``

### UX-A11Y-R3-008: Intake form is not submitted as a form
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ux / accessibility-wcag
- **Location**: ``frontend/src/pages/IntakeForm.jsx:248``

### UX-FORM-R3-001: Patient intake fields can be silently autofilled with stale data
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ux / form-input
- **Location**: ``frontend/src/pages/IntakeForm.jsx:269``

### UX-FORM-R3-005: No focus management or scroll-to-error on validation failure
- **Severity**: HIGH
- **Type**: Extension of UX-004
- **Domain**: ux / form-input
- **Location**: ``frontend/src/pages/IntakeForm.jsx:153-160``

### UX-FORM-R3-010: New user role is preselected to the lowest-privilege account type
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ux / form-input
- **Location**: ``frontend/src/components/admin/AdminUsers.jsx:25,136-142``

### UX-IA-R3-007: No affordance to clear auto-saved drafts traps users with stale data
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ux / information-architecture
- **Location**: ``frontend/src/pages/IntakeForm.jsx:104``

### UX-IA-R3-008: Case review action is hidden behind a non-obvious disclosure
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ux / information-architecture
- **Location**: ``frontend/src/components/BriefingCard.jsx:6``

### UX-IA-R3-010: Draft identity is keyed to the user, not the form instance
- **Severity**: HIGH
- **Type**: Extension of UX-IA-R3-007
- **Domain**: ux / information-architecture
- **Location**: ``frontend/src/pages/IntakeForm.jsx:89``

### UX-IA-R3-011: Emergency red flags are flattened into the same symptom grid as routine findings
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ux / information-architecture
- **Location**: ``frontend/src/pages/IntakeForm.jsx:35``

### UX-LOAD-R3-001: Critical toasts disappear before clinical users can act
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ux / loading-feedback
- **Location**: ``frontend/src/components/ToastProvider.jsx:24``

### UX-LOAD-R3-002: Admin mutations have no in-flight or success feedback
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ux / loading-feedback
- **Location**: ``frontend/src/components/admin/AdminUsers.jsx:71``

### UX-MOBILE-R3-001: Bottom-right toast stack blocks thumb-zone actions
- **Severity**: HIGH
- **Type**: Extension of MOBILE-DD-006
- **Domain**: ux / mobile-touch-gesture
- **Location**: ``frontend/src/components/ToastProvider.jsx:33-42``

### UX-OFFLINE-R3-001: Pending Queue Has No Case-Level State
- **Severity**: HIGH
- **Type**: Extension of SYNC-DD-002
- **Domain**: ux / offline-pwa
- **Location**: ``frontend/src/components/OfflineBanner.jsx:29``

### UX-OFFLINE-R3-002: Sync Failures Look Like Normal Sync
- **Severity**: HIGH
- **Type**: Extension of REL-005
- **Domain**: ux / offline-pwa
- **Location**: ``frontend/src/panels/ASHAPanel.jsx:33``

### UX-OFFLINE-R3-004: Offline-Ready State Is Console-Only (No User Trust Signal)
- **Severity**: HIGH
- **Type**: NET-NEW
- **Domain**: ux / offline-pwa
- **Location**: ``frontend/src/main.jsx:18``

### UX-OFFLINE-R3-005: Background Sync Queue Is Invisible to Sync UX
- **Severity**: HIGH
- **Type**: Extension of SYNC-DD-002
- **Domain**: ux / offline-pwa
- **Location**: ``frontend/vite.config.js:34`, `frontend/src/components/OfflineBanner.jsx:2`, `frontend/src/components/OfflineBanner.jsx:43``

### UX-OFFLINE-R3-006: Realtime Connection Health Is Not Exposed to Users
- **Severity**: HIGH
- **Type**: Extension of REL-004
- **Domain**: ux / offline-pwa
- **Location**: ``frontend/src/hooks/useRealtimeCases.js:21`, `frontend/src/pages/Dashboard.jsx:64``

### DATA-LIFECYCLE-R3-002: Reviewed and archived lifecycle states are modeled but never advanced
- **Severity**: MEDIUM
- **Type**: Extension of COMPLY-006
- **Domain**: data / lifecycle
- **Location**: ``backend/app/api/routes/cases.py:186`, `backend/app/api/routes/cases.py:195`, `Context/VitalNet_Phase6_Instructions.md:240`, `Context/VitalNet_Phase6_Instructions.md:245`, `backend/app/api/routes/cases.py:99``

### DATA-LIFECYCLE-R3-005: Draft purge capability exists but is never invoked
- **Severity**: MEDIUM
- **Type**: Extension of COMPLY-006
- **Domain**: data / lifecycle
- **Location**: ``frontend/src/hooks/useDraftSave.js:100`, `frontend/src/hooks/useDraftSave.js:98`, `frontend/src/App.jsx:36`, `frontend/src/pages/IntakeForm.jsx:89``

### DATA-LIFECYCLE-R3-006: Realtime feed can reintroduce soft-deleted records into in-memory dashboards
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: data / lifecycle
- **Location**: ``backend/supabase/migrations/phase10_realtime_setup.sql:5`, `frontend/src/hooks/useRealtimeCases.js:40`, `frontend/src/pages/Dashboard.jsx:75`, `backend/app/api/routes/cases.py:156``

### DATA-LIFECYCLE-R3-007: User deactivation is account-state only and leaves all linked case lifecycle data active
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: data / lifecycle
- **Location**: ``backend/app/api/routes/admin_routes.py:151`, `backend/app/api/routes/admin_routes.py:162`, `backend/app/api/routes/admin_routes.py:159`, `frontend/src/api/admin.js:35``

### DATA-LIFECYCLE-R3-008: Soft-deleted records can still be mutated by review endpoint
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: data / lifecycle
- **Location**: ``backend/app/api/routes/cases.py:195`, `backend/app/api/routes/cases.py:200`, `backend/app/api/routes/cases.py:156`, `backend/app/api/routes/cases.py:231`, `backend/app/api/routes/cases.py:266``

### DATA-MIGRATE-R3-008: Seed Facility Insert Is Non-Idempotent and Duplicates on Replay
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: data / migration
- **Location**: ``Context/VitalNet_Phase6_Instructions.md:140`, `Context/VitalNet_Phase6_Instructions.md:161``

### DATA-QUERY-R3-010: Inefficient Date Grouping in Analytics Emergency Rate
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: data / query-perf
- **Location**: ``backend/app/api/routes/analytics_routes.py:118-130``

### DATA-QUERY-R3-011: No Index on case_records.submitted_by
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: data / query-perf
- **Location**: ``backend/app/api/routes/cases.py:230`, `analytics_routes.py:65-67``

### DATA-REF-R3-006: No FK-Backed Child Table for Reviews (Mutable Inline Relation Overwrites History)
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: data / referential
- **Location**: ``Context/VitalNet_Phase6_Instructions.md:239`, `backend/app/api/routes/cases.py:195``

### DATA-SCHEMA-R3-009: No Database-Level Constraint on triage_priority vs triage_level Mapping
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: data / schema
- **Location**: ``backend/app/api/routes/cases.py:88`, Database schema`

### DEVOPS-CICD-R3-003: The workflow does not restrict GITHUB_TOKEN permissions
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: devops / ci-cd-security
- **Location**: ``.github/workflows/ci.yml:1-47``

### DEVOPS-CICD-R3-006: Checkout leaves repository token material available to later steps by default
- **Severity**: MEDIUM
- **Type**: Extension of DEVOPS-CICD-R3-003
- **Domain**: devops / ci-cd-security
- **Location**: ``.github/workflows/ci.yml:11`, `.github/workflows/ci.yml:35``

### DEVOPS-CONTAINER-R3-002: GitHub Actions are not pinned to immutable revisions
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: devops / container-deployment
- **Location**: ``.github/workflows/ci.yml:11``

### DEVOPS-CONTAINER-R3-003: Railway deployment defines no explicit runtime resource caps
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: devops / container-deployment
- **Location**: ``backend/railway.toml:1``

### DEVOPS-CONTAINER-R3-005: Image hardening posture is not enforceable in current Nixpacks deployment
- **Severity**: MEDIUM
- **Type**: Extension of DEVOPS-011
- **Domain**: devops / container-deployment
- **Location**: ``backend/railway.toml:2``

### DEVOPS-CONTAINER-R3-006: CI workflow has no timeout or run-concurrency guardrails
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: devops / container-deployment
- **Location**: ``.github/workflows/ci.yml:1`, `.github/workflows/ci.yml:8`, `.github/workflows/ci.yml:33``

### DEVOPS-DR-R3-003: Health check can go green after a bad restore
- **Severity**: MEDIUM
- **Type**: Extension of DEVOPS-R3-007
- **Domain**: devops / backup-dr
- **Location**: ``backend/app/main.py:105``

### DEVOPS-ENV-R3-002: Misspelled Env Vars Fail Open Instead of Failing Fast
- **Severity**: MEDIUM
- **Type**: Extension of DEVOPS-012
- **Domain**: devops / environment
- **Location**: ``backend/app/core/config.py:11``

### DEVOPS-ENV-R3-003: Production Still Trusts Localhost Origins
- **Severity**: MEDIUM
- **Type**: Extension of SEC-003
- **Domain**: devops / environment
- **Location**: ``backend/app/main.py:58``

### DEVOPS-ENV-R3-005: `ENVIRONMENT` Exists in Env Files but Is Not Enforced by Runtime
- **Severity**: MEDIUM
- **Type**: Extension of DEVOPS-012
- **Domain**: devops / environment
- **Location**: ``backend/.env:3`, `backend/app/core/config.py:4`, `backend/app/core/config.py:13`, `backend/app/main.py:58``

### DEVOPS-ENV-R3-006: `SUPABASE_JWT_SECRET` Is Required and Documented but Functionally Unused
- **Severity**: MEDIUM
- **Type**: Extension of SEC-002
- **Domain**: devops / environment
- **Location**: ``backend/app/core/config.py:7`, `backend/.env.example:3`, `backend/app/core/auth.py:31``

### ML-DRIFT-R3-3: Offline ONNX Model Is Unversioned and Can Silently Stay Stale
- **Severity**: MEDIUM
- **Type**: Extension of ML-DD-006
- **Domain**: ml-clinical / versioning-drift
- **Location**: ``frontend/src/utils/triageClassifier.js:13``

### ML-EDGE-R3-002: `patient_sex = other` collapses into different unsafe defaults
- **Severity**: MEDIUM
- **Type**: Extension of ML-DD-004
- **Domain**: ml-clinical / model-edge
- **Location**: ``frontend/src/utils/triageClassifier.js:130``

### ML-FEAT-R3-2: "Other" Sex Collapses Into Female Encoding on the Client
- **Severity**: MEDIUM
- **Type**: Extension of ML-DD-004
- **Domain**: ml-clinical / feature-pipeline
- **Location**: ``frontend/src/utils/triageClassifier.js:130``

### PERF-ASSET-R3-002: Excessive Render-Blocking Font Weight Payload
- **Severity**: MEDIUM
- **Type**: Extension of PERF-008
- **Domain**: performance / asset-optimization
- **Location**: ``frontend/index.html:9``

### PERF-BUNDLE-R3-002: Admin Tab Content Is Not Split From the Admin Shell
- **Severity**: MEDIUM
- **Type**: Extension of PERF-001
- **Domain**: performance / bundle-splitting
- **Location**: ``frontend/src/panels/AdminPanel.jsx:1-6,21-25``

### PERF-BUNDLE-R3-003: PWA Precache Pulls Optional ML Assets Into Every Install
- **Severity**: MEDIUM
- **Type**: Extension of PERF-002
- **Domain**: performance / bundle-splitting
- **Location**: ``frontend/vite.config.js:26-32,50-59` and `frontend/src/main.jsx:13-21``

### PERF-BUNDLE-R3-005: Duplicate Service Worker Entry Points Create Redundant Dynamic-Import Edges
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: performance / bundle-splitting
- **Location**: ``frontend/src/main.jsx:5,14`, `frontend/src/components/UpdatePrompt.jsx:10,16`, `frontend/dist/.vite/manifest.json:7-10``

### PERF-MEM-R3-001: Toast timeouts survive unmount
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: performance / memory-gc
- **Location**: ``frontend/src/components/ToastProvider.jsx:21-26``

### PERF-MEM-R3-004: Draft key instability leaves orphaned IndexedDB records
- **Severity**: MEDIUM
- **Type**: Extension of COMPLY-006
- **Domain**: performance / memory-gc
- **Location**: ``frontend/src/pages/IntakeForm.jsx:76`, `frontend/src/pages/IntakeForm.jsx:89`, `frontend/src/hooks/useDraftSave.js:39``

### PERF-MEM-R3-005: Autosave path reopens IndexedDB on every debounce tick
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: performance / memory-gc
- **Location**: ``frontend/src/pages/IntakeForm.jsx:105-110`, `frontend/src/hooks/useDraftSave.js:18-20`, `frontend/src/hooks/useDraftSave.js:57-60``

### PERF-NET-R3-01: API responses are never compressed
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: performance / network-caching
- **Location**: ``backend/app/main.py:49-73``

### PERF-NET-R3-04: Service worker is registered twice
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: performance / network-caching
- **Location**: ``frontend/src/main.jsx:13-21``

### PERF-NET-R3-05: Dashboard pagination cursor is dropped, causing repeated page-1 fetches
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: performance / network-caching
- **Location**: ``frontend/src/pages/Dashboard.jsx:44`, `frontend/src/api/cases.js:8-13`, `backend/app/api/routes/cases.py:162-167``

### PERF-NET-R3-07: Two independent offline retry queues can replay the same submit twice
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: performance / network-caching
- **Location**: ``frontend/vite.config.js:34-47`, `frontend/src/stores/syncStore.js:63-69,81-108``

### PERF-NET-R3-08: Queue drain has no in-flight lock, enabling duplicate replay bursts across tabs
- **Severity**: MEDIUM
- **Type**: Extension of SYNC-DD-001
- **Domain**: performance / network-caching
- **Location**: ``frontend/src/panels/ASHAPanel.jsx:31-44`, `frontend/src/stores/syncStore.js:81-83,99-108`, `frontend/src/lib/offlineQueue.js:53-56``

### PERF-RENDER-R3-002: AdminUsers Rerenders the Full User Grid on Every Local Edit
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: performance / rendering
- **Location**: ``frontend/src/components/admin/AdminUsers.jsx:27-247``

### PERF-RENDER-R3-003: AnalyticsDashboard Recomputes Derived Charts on Every Re-render
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: performance / rendering
- **Location**: ``frontend/src/components/AnalyticsDashboard.jsx:63-167``

### PERF-RENDER-R3-004: Inline `onReviewed` Prop Identity Churn Blocks BriefingCard Memoization
- **Severity**: MEDIUM
- **Type**: Extension of PERF-005
- **Domain**: performance / rendering
- **Location**: ``frontend/src/pages/Dashboard.jsx:132`, `frontend/src/pages/Dashboard.jsx:141`, `frontend/src/pages/Dashboard.jsx:150``

### PERF-RENDER-R3-006: ASHAPanel Realtime Updates Re-render Intake Form During New Case Entry
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: performance / rendering
- **Location**: ``frontend/src/panels/ASHAPanel.jsx:62-74`, `frontend/src/panels/ASHAPanel.jsx:95``

### PERF-RENDER-R3-007: AdminFacilities Keystrokes Invalidate Full Facilities Table
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: performance / rendering
- **Location**: ``frontend/src/components/admin/AdminFacilities.jsx:16`, `frontend/src/components/admin/AdminFacilities.jsx:91`, `frontend/src/components/admin/AdminFacilities.jsx:129-155``

### PERF-VITALS-R3-001: Draft Rehydration Inserts Controls After First Paint
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: performance / core-web-vitals
- **Location**: ``frontend/src/pages/IntakeForm.jsx:92``

### PERF-VITALS-R3-002: Offline Banner Pushes Clinical Content When Connectivity Changes
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: performance / core-web-vitals
- **Location**: ``frontend/src/components/OfflineBanner.jsx:29``

### PERF-VITALS-R3-006: Infinite Box-Shadow Pulse on Emergency Cards Causes Paint-Heavy Jank
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: performance / core-web-vitals
- **Location**: ``frontend/src/components/BriefingCard.jsx:40``

### QA-A11Y-R3-004: Live Status Messages Have No Screen Reader Regression Test
- **Severity**: MEDIUM
- **Type**: Extension of UX-003
- **Domain**: qa / accessibility-tests
- **Location**: ``frontend/src/components/ToastProvider.jsx:29-42``

### QA-A11Y-R3-006: No CSS Focus Style Regression Test
- **Severity**: MEDIUM
- **Type**: Extension of UX-002
- **Domain**: qa / accessibility-tests
- **Location**: ``frontend/src/index.css:1-104``

### QA-E2E-R3-005: Local triage state lingers after online submission, causing redundant UI display
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: qa / e2e-scenarios
- **Location**: ``frontend/src/pages/IntakeForm.jsx:165``

### QA-E2E-R3-006: Analytics dashboard live counter increments on INSERT but never resets or ages out
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: qa / e2e-scenarios
- **Location**: ``frontend/src/components/AnalyticsDashboard.jsx:40``

### QA-EDGE-R3-002: Review endpoint reports success even when no row changed
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: qa / edge-cases
- **Location**: ``backend/app/api/routes/cases.py:195``

### QA-EDGE-R3-003: Facility toggle is non-atomic under concurrent admins
- **Severity**: MEDIUM
- **Type**: Extension of REL-007
- **Domain**: qa / edge-cases
- **Location**: ``backend/app/api/routes/admin_routes.py:203``

### QA-EDGE-R3-006: LLM rate-limit sleep can race with cascade fallback
- **Severity**: MEDIUM
- **Type**: Extension of REL-006
- **Domain**: qa / edge-cases
- **Location**: ``backend/app/services/llm.py:215``

### QA-EDGE-R3-007: Offline queue capacity check race can still exceed limit
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: qa / edge-cases
- **Location**: ``frontend/src/lib/offlineQueue.js:33``

### QA-EDGE-R3-008: Clinical feature engineer returns -1 for missing vitals, mismatched with ONNX fallback
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: qa / edge-cases
- **Location**: ``backend/app/ml/clinical_features.py:71``

### QA-INTEG-R3-003: Analytics scoping/aggregation lacks integration coverage
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: qa / integration-tests
- **Location**: ``backend/app/api/routes/analytics_routes.py:10``

### QA-INTEG-R3-004: Idempotent duplicate submission (client_id) flow has no integration test
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: qa / integration-tests
- **Location**: ``backend/app/api/routes/cases.py:101``

### QA-INTEG-R3-005: Rate‑limiting path is untested across all endpoint flows
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: qa / integration-tests
- **Location**: ``backend/app/api/routes/cases.py:51``

### QA-PERF-R3-002: CI Has No Latency or Throughput Budget Gates
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: qa / performance-tests
- **Location**: ``.github/workflows/ci.yml:15`, `.github/workflows/ci.yml:39``

### QA-PERF-R3-004: No Frontend or CI Benchmark for ONNX Cold‑Start Latency
- **Severity**: MEDIUM
- **Type**: Extension of PERF-002
- **Domain**: qa / performance-tests
- **Location**: ``frontend/src/utils/triageClassifier.js:29-73`, `frontend/tests/offline.spec.js:3`, `.github/workflows/ci.yml:39``

### QA-SEC-R3-003: Analytics facility-scoping is completely untested
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: qa / security-tests
- **Location**: ``backend/tests/test_cases_api.py:20-148``

### QA-SEC-R3-004: Input-fuzzing coverage is missing for cursor and ID parameters on case endpoints
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: qa / security-tests
- **Location**: ``backend/tests/test_cases_api.py:63-147``

### QA-SEC-R3-008: Missing regression tests for environment‑variable leakage in test‑runner logs
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: qa / security-tests
- **Location**: ``backend/tests/test_cases_api.py:1-153``

### QA-UNIT-R3-002: Bearer parsing in `get_db_session()` is not unit-covered
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: qa / unit-tests
- **Location**: ``backend/app/core/database.py:36``

### QA-UNIT-R3-004: Optional vital-field validation branches are untested
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: qa / unit-tests
- **Location**: ``frontend/src/utils/validation.js:13``

### QA-UNIT-R3-006: ONNX feature‑vector helper `containsAny` and `clamp` untested
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: qa / unit-tests
- **Location**: ``frontend/src/utils/triageClassifier.js:110`, `115``

### QA-UNIT-R3-008: Toast and RouteGuard component rendering edge‑cases have zero test coverage
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: qa / unit-tests
- **Location**: ``frontend/src/components/ToastProvider.jsx:21` and `frontend/src/components/RouteGuard.jsx:4``

### REL-CB-R3-003: Realtime Case Streams Have No Subscription Bulkhead
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: reliability / circuit-breaker
- **Location**: ``frontend/src/hooks/useRealtimeCases.js:18``

### REL-DATA-R3-002: Facility toggle is a read-modify-write race
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: reliability / data-consistency
- **Location**: ``backend/app/api/routes/admin_routes.py:197-206``

### REL-DATA-R3-003: Case pagination is not stable across equal timestamps
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: reliability / data-consistency
- **Location**: ``backend/app/api/routes/cases.py:149-179,224-247``

### REL-DATA-R3-004: Review endpoint reports success without confirming persistence
- **Severity**: MEDIUM
- **Type**: Extension of DATA-R3-007
- **Domain**: reliability / data-consistency
- **Location**: ``backend/app/api/routes/cases.py:195-201``

### REL-OBS-R3-003: Safety-critical toasts auto-dismiss too quickly
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: reliability / observability
- **Location**: ``frontend/src/components/ToastProvider.jsx:21``

### REL-RACE-R3-003: Offline Queue Capacity Check Is Not Atomic Across Tabs
- **Severity**: MEDIUM
- **Type**: Extension of REL-004
- **Domain**: reliability / race-concurrency
- **Location**: ``frontend/src/lib/offlineQueue.js:33``

### REL-RECOVER-R3-004: Review failures disappear into the console only
- **Severity**: MEDIUM
- **Type**: Extension of REL-005
- **Domain**: reliability / recovery
- **Location**: ``frontend/src/components/BriefingCard.jsx:13-23``

### REL-TIMEOUT-R3-03: Case-list requests cannot be aborted when the UI moves on
- **Severity**: MEDIUM
- **Type**: Extension of CHAOS-003
- **Domain**: reliability / timeout-retry
- **Location**: ``frontend/src/api/cases.js:8``

### SEC-API-R3-003: Bulk User Enumeration via Admin Directory Endpoint
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: security / api-security
- **Merged**: 1 duplicate(s)
  - From: SEC-RBAC-R3-011
- **Location**: ``backend/app/api/routes/admin_routes.py:41-78``

### SEC-API-R3-003: Bulk User Enumeration via Admin Directory Endpoint
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: security / api-security
- **Location**: ``backend/app/api/routes/admin_routes.py:41-78``

### SEC-AUTH-R3-008: No Authentication Rate Limiting (Brute Force via Supabase)
- **Severity**: MEDIUM
- **Type**: Extension of SEC-001
- **Domain**: security / auth-flow
- **Location**: ``frontend/src/pages/LoginPage.jsx:11-23``

### SEC-AUTH-R3-009: Token Refresh Race Condition Can Leave User Logged Out
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: security / auth-flow
- **Location**: ``frontend/src/lib/supabase.js:35-36`, multiple API call sites`

### SEC-AUTH-R3-010: No Multi-Factor Authentication (MFA) Support
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: security / auth-flow
- **Location**: ``frontend/src/pages/LoginPage.jsx:11-23`, entire auth flow`

### SEC-AUTH-R3-011: No Password Reset Flow Leads to Insecure Workarounds
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: security / auth-flow
- **Location**: ``frontend/src/pages/LoginPage.jsx` (missing "Forgot Password?" link)`

### SEC-CONFIG-R3-003: Hardcoded Test Login Secrets Embedded in Executable Test Suites
- **Severity**: MEDIUM
- **Type**: Extension of [PENTEST-001]
- **Domain**: security / secrets-config
- **Location**: ``backend/tests/test_cases_api.py:43`, `backend/tests/test_cases_api.py:44`, `backend/tests/test_cases_api.py:54`, `backend/tests/test_cases_api.py:55`, `frontend/tests/offline.spec.js:16`, `frontend/tests/offline.spec.js:17``

### SEC-CRYPTO-R3-006: No HSTS Header on API Responses
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: security / crypto
- **Location**: `- `backend/app/main.py` (missing security headers middleware)`

### SEC-CRYPTO-R3-007: JWT Algorithm Confusion Not Prevented
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: security / crypto
- **Location**: `- `backend/app/core/auth.py:8` (algorithm specification)`

### SEC-INJ-R3-010: URL Parameter Pollution in Pagination
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: security / injection
- **Location**: ``backend/app/api/routes/cases.py:128-130``

### SEC-INJ-R3-011: React Key Injection (Low Exploitability)
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: security / injection
- **Location**: ``frontend/src/components/BriefingCard.jsx:80-84``

### SEC-INJ-R3-012: Template Injection in Future Email Notifications
- **Severity**: MEDIUM
- **Type**: NET-NEW (Proactive)
- **Domain**: security / injection
- **Location**: `N/A (not yet implemented)`

### SEC-RBAC-R3-010: Frontend RouteGuard Only Checks Client-Side Role
- **Severity**: MEDIUM
- **Type**: NET-NEW (Defense-in-Depth Gap)
- **Domain**: security / rbac
- **Location**: ``frontend/src/components/RouteGuard.jsx:4-33``

### SEC-RBAC-R3-012: App.jsx Role Routing Trusts profile.role Without Backend Verification
- **Severity**: MEDIUM
- **Type**: NET-NEW (Defense-in-Depth Gap)
- **Domain**: security / rbac
- **Location**: ``frontend/src/App.jsx:9-34``

### SEC-SUPPLY-R3-009: CI/CD Installs Test Dependencies Without Hash Verification
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: security / supply-chain
- **Location**: ``.github/workflows/ci.yml:18-19``

### SEC-SUPPLY-R3-010: No Subresource Integrity (SRI) for CDN Assets in PWA
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: security / supply-chain
- **Location**: ``frontend/vite.config.js:23-84` (PWA manifest)`

### SEC-SUPPLY-R3-011: brace-expansion DoS in CI/CD Glob Operations (GHSA-f886-m6hf-6m8v)
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: security / supply-chain
- **Location**: `Transitive via workbox-build → minimatch → brace-expansion 2.0.2, 5.0.4`

### SEC-SUPPLY-R3-012: Missing Dependency Provenance and SBOM in CI/CD
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: security / supply-chain
- **Location**: ``.github/workflows/ci.yml` (entire file)`

### UX-A11Y-R3-003: Analytics charts have no textual equivalent
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / accessibility-wcag
- **Location**: ``frontend/src/components/AnalyticsDashboard.jsx:97``

### UX-A11Y-R3-004: Update prompt is not exposed as an accessible notification
- **Severity**: MEDIUM
- **Type**: Extension of UX-003
- **Domain**: ux / accessibility-wcag
- **Location**: ``frontend/src/components/UpdatePrompt.jsx:27``

### UX-A11Y-R3-005: Tab-like navigation is missing tab semantics
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / accessibility-wcag
- **Location**: ``frontend/src/components/NavBar.jsx:28``

### UX-A11Y-R3-009: Login failure message is not announced
- **Severity**: MEDIUM
- **Type**: Extension of UX-003
- **Domain**: ux / accessibility-wcag
- **Location**: ``frontend/src/pages/LoginPage.jsx:41``

### UX-A11Y-R3-010: Create-user disclosure button has no expanded state
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / accessibility-wcag
- **Location**: ``frontend/src/components/admin/AdminUsers.jsx:104``

### UX-FORM-R3-002: Switching away from "Other" destroys the typed complaint
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / form-input
- **Location**: ``frontend/src/pages/IntakeForm.jsx:119``

### UX-FORM-R3-003: Age entry can be silently truncated to the wrong value
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / form-input
- **Location**: ``frontend/src/pages/IntakeForm.jsx:145``

### UX-FORM-R3-004: Lack of `<form>` element breaks "Enter" key submission
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / form-input
- **Location**: ``frontend/src/pages/IntakeForm.jsx:248-428``

### UX-FORM-R3-006: Suboptimal mobile keyboard for numeric vital inputs
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / form-input
- **Location**: ``frontend/src/pages/IntakeForm.jsx:324``

### UX-FORM-R3-007: Intake fields are missing programmatic label associations
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / form-input
- **Location**: ``frontend/src/pages/IntakeForm.jsx:446-452``

### UX-FORM-R3-008: Login form omits autofill semantics for credentials
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / form-input
- **Location**: ``frontend/src/pages/LoginPage.jsx:35-68``

### UX-FORM-R3-009: Cancelled admin user creation retains sensitive values
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / form-input
- **Location**: ``frontend/src/components/admin/AdminUsers.jsx:33-63,104-109``

### UX-FORM-R3-011: New user password field is not marked as a new secret
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / form-input
- **Location**: ``frontend/src/components/admin/AdminUsers.jsx:118-131``

### UX-FORM-R3-012: Facility type defaults to PHC without an explicit choice
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / form-input
- **Location**: ``frontend/src/components/admin/AdminFacilities.jsx:6-8,98-104``

### UX-IA-R3-001: Admin stats are split across competing admin entry points
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / information-architecture
- **Location**: ``frontend/src/panels/AdminPanel.jsx:8``

### UX-IA-R3-002: User creation form exposes ASHA-specific data on every role
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / information-architecture
- **Location**: ``frontend/src/components/admin/AdminUsers.jsx:117``

### UX-IA-R3-006: Client-side tab filtering breaks server-side pagination mental model
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / information-architecture
- **Location**: ``frontend/src/pages/Dashboard.jsx:83``

### UX-IA-R3-009: Unknown roles fall through to a blank application shell
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / information-architecture
- **Location**: ``frontend/src/App.jsx:30``

### UX-IA-R3-012: Recovered draft is announced before users know what patient context it belongs to
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / information-architecture
- **Location**: ``frontend/src/pages/IntakeForm.jsx:94``

### UX-LOAD-R3-003: Intake submission uses one generic spinner for multiple hidden phases
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / loading-feedback
- **Location**: ``frontend/src/pages/IntakeForm.jsx:135``

### UX-LOAD-R3-004: Draft restore is only signaled by a brief toast
- **Severity**: MEDIUM
- **Type**: Extension of UX-LOAD-R3-001
- **Domain**: ux / loading-feedback
- **Location**: ``frontend/src/pages/IntakeForm.jsx:94-98``

### UX-LOAD-R3-005: Refresh Queue blanks the live case list
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / loading-feedback
- **Location**: ``frontend/src/pages/Dashboard.jsx:21-35,91-105``

### UX-LOAD-R3-006: Offline sync banner gives no progress or ETA
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / loading-feedback
- **Location**: ``frontend/src/components/OfflineBanner.jsx:42-47``

### UX-MOBILE-R3-002: Update prompt competes with system chrome and nearby taps
- **Severity**: MEDIUM
- **Type**: Extension of MOBILE-DD-006
- **Domain**: ux / mobile-touch-gesture
- **Location**: ``frontend/src/components/UpdatePrompt.jsx:28-46``

### UX-MOBILE-R3-003: Tap-to-expand case cards steal scroll gestures
- **Severity**: MEDIUM
- **Type**: Extension of MOBILE-DD-006
- **Domain**: ux / mobile-touch-gesture
- **Location**: ``frontend/src/components/BriefingCard.jsx:43-46``

### UX-MOBILE-R3-004: Admin table row actions too small for touch in dense layout
- **Severity**: MEDIUM
- **Type**: Extension of UX-001 / MOBILE-DD-002
- **Domain**: ux / mobile-touch-gesture
- **Location**: ``frontend/src/components/admin/AdminUsers.jsx:225-236``

### UX-MOBILE-R3-005: Inline table dropdowns in edit mode have cramped touch targets
- **Severity**: MEDIUM
- **Type**: Extension of MOBILE-DD-001
- **Domain**: ux / mobile-touch-gesture
- **Location**: ``frontend/src/components/admin/AdminUsers.jsx:184-206``

### UX-MOBILE-R3-006: Symptom checkbox grid uses visually hidden inputs with small tap area
- **Severity**: MEDIUM
- **Type**: Extension of UX-001
- **Domain**: ux / mobile-touch-gesture
- **Location**: ``frontend/src/pages/IntakeForm.jsx:352-367``

### UX-OFFLINE-R3-003: Update Prompt Can Overlap Clinical Actions and Vanish Without Reminder
- **Severity**: MEDIUM
- **Type**: NET-NEW
- **Domain**: ux / offline-pwa
- **Location**: ``frontend/src/components/UpdatePrompt.jsx:27``

### PERF-NET-R3-02: PWA precaches triage model assets for every user
- **Severity**: LOW
- **Type**: Extension of PERF-002
- **Domain**: performance / network-caching
- **Location**: ``frontend/vite.config.js:23-32``

### PERF-NET-R3-03: Identical case fetches are not coalesced
- **Severity**: LOW
- **Type**: NET-NEW
- **Domain**: performance / network-caching
- **Location**: ``frontend/src/api/cases.js:8-18``

### QA-EDGE-R3-004: Analytics buckets can misplace boundary timestamps
- **Severity**: LOW
- **Type**: NET-NEW
- **Domain**: qa / edge-cases
- **Location**: ``backend/app/api/routes/analytics_routes.py:125``

### QA-EDGE-R3-009: LLM fallback briefing omits _model_used key after tier cascade
- **Severity**: LOW
- **Type**: NET-NEW
- **Domain**: qa / edge-cases
- **Location**: ``backend/app/services/llm.py:271``

### SEC-API-R3-004: API Versioning Is Metadata Only
- **Severity**: LOW
- **Type**: NET-NEW
- **Domain**: security / api-security
- **Location**: ``backend/app/main.py:46``

### SEC-AUTH-R3-012: Session Tokens Visible in Browser DevTools Network Tab
- **Severity**: LOW
- **Type**: NET-NEW
- **Domain**: security / auth-flow
- **Location**: `All API calls with `Authorization: Bearer` headers`

### SEC-CRYPTO-R3-008: Missing Constant-Time Comparison for Tokens
- **Severity**: LOW
- **Type**: NET-NEW
- **Domain**: security / crypto
- **Location**: `- `backend/app/core/auth.py:27` (string splitting, not constant-time comparison)`

### SEC-RBAC-R3-013: Profile Updates via Supabase Client Don't Validate Role Changes
- **Severity**: LOW
- **Type**: NET-NEW (Missing Authorization Layer)
- **Domain**: security / rbac
- **Location**: ``frontend/src/store/authStore.jsx:28-40``

### UX-IA-R3-003: Doctor refresh control uses queue language for a case dashboard
- **Severity**: LOW
- **Type**: NET-NEW
- **Domain**: ux / information-architecture
- **Location**: ``frontend/src/pages/Dashboard.jsx:101``

### UX-IA-R3-004: Complaint terminology changes mid-flow
- **Severity**: LOW
- **Type**: NET-NEW
- **Domain**: ux / information-architecture
- **Location**: ``frontend/src/pages/IntakeForm.jsx:291``

### UX-IA-R3-005: Empty state copy for 'All Cases' tab falsely implies a pending queue
- **Severity**: LOW
- **Type**: NET-NEW
- **Domain**: ux / information-architecture
- **Location**: ``frontend/src/pages/Dashboard.jsx:116``

### UX-MOBILE-R3-007: No touch-action CSS to prevent double-tap zoom and improve tap response
- **Severity**: LOW
- **Type**: NET-NEW
- **Domain**: ux / mobile-touch-gesture
- **Location**: ``frontend/src/index.css` (entire file), all interactive components`
