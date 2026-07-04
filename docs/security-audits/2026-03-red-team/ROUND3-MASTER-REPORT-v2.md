# VitalNet Red Team Round 3 - Master Report v2

**Generated**: 2026-03-29 19:16:07
**Audit Scope**: Full-stack security, reliability, performance, UX, ML safety, DevOps, data integrity, QA
**Methodology**: 50 specialist agents across 8 domains with DeepSeek R1, Claude Opus 4.6, Kimi K2, GPT-5.3-Codex
**Prior Context**: 180 findings from Rounds 1-2 (see `KNOWN_ISSUES_R1_R2.md`)

---

## Executive Summary

Round 3 deployed **50 specialized auditors** across 8 domains to conduct deep-dive analysis. This round produced **323 NET-NEW findings** with 3 duplicates merged.

### Key Statistics

| Metric | Value |
|--------|-------|
| **Total Unique Findings** | 323 |
| **NET-NEW Findings** | 323 |
| **Extensions of R1/R2** | 0 |
| **Duplicates Merged** | 3 |
| **CRITICAL Severity** | 39 |
| **HIGH Severity** | 152 |
| **MEDIUM Severity** | 120 |
| **LOW Severity** | 12 |

### Findings by Domain

| Domain | Specialists | Total | Critical | High | Medium | Low |
|--------|-------------|-------|----------|------|--------|-----|
| **Security** | 7 | 64 | 16 | 26 | 18 | 4 |
| **Data** | 6 | 54 | 16 | 28 | 10 | 0 |
| **Ml Clinical** | 6 | 17 | 1 | 13 | 3 | 0 |
| **Reliability** | 6 | 21 | 1 | 12 | 8 | 0 |
| **Performance** | 6 | 33 | 1 | 10 | 20 | 2 |
| **Devops** | 6 | 32 | 3 | 18 | 11 | 0 |
| **Ux** | 6 | 53 | 0 | 20 | 29 | 4 |
| **Qa** | 7 | 49 | 1 | 25 | 21 | 2 |

---

## Critical Findings Requiring Immediate Action

### Tier 1: Stop-Ship (22 findings - Fix within 24 hours)

| ID | Domain | Title | Location |
|-------|--------|-------|----------|
| **DATA-QUERY-R3-001** | data | No Connection Pooling - New Supabase Client Created Per Request | ``backend/app/core/database.py:26-33`` |
| **DATA-QUERY-R3-004** | data | Unbounded Query on Admin Stats Endpoint | ``backend/app/api/routes/admin_routes.py:216-217`` |
| **DATA-QUERY-R3-005** | data | N+1 Query Pattern in Admin User List - Profile + Auth User Join | ``backend/app/api/routes/admin_routes.py:52-78`` |
| **DATA-REF-R3-002** | data | User-Deletion Cascade Chain Is Internally Inconsistent | ``Context/VitalNet_Phase6_Instructions.md:169`, `Context/V...` |
| **DATA-RLS-R3-001** | data | Admin Stats Endpoint Bypasses RLS via service_role Client | ``backend/app/api/routes/admin_routes.py:216-217`` |
| **DATA-RLS-R3-002** | data | Missing DELETE RLS Policy Allows Unauthorized Case Purging | `Supabase RLS configuration (no DELETE policy exists)` |
| **DATA-RLS-R3-003** | data | Frontend Anon Key Enables Direct RLS Bypass Attacks | ``frontend/src/lib/supabase.js:29-31` + `frontend/.env.local`` |
| **DATA-RLS-R3-005** | data | UPDATE RLS Policy Allows Privilege Escalation via reviewed_by Manipulation | ``backend/app/api/routes/cases.py:195-200` + Supabase RLS ...` |
| **DATA-SCHEMA-R3-003** | data | Missing Foreign Key Constraint on facility_id | ``backend/app/api/routes/cases.py:70`, Database schema mis...` |
| **DEVOPS-CICD-R3-001** | devops | Secrets are injected into PR jobs that execute repo-controlled code | ``.github/workflows/ci.yml:4-29`` |

### Tier 2: Critical (14 findings - Fix within 1 week)

| ID | Domain | Title | Location |
|-------|--------|-------|----------|
| **DATA-MIGRATE-R3-006** | data | Baseline Schema Script Omits `patient_name` Required by Current Runtime | ``Context/VitalNet_Phase6_Instructions.md:206`, `backend/a...` |
| **DATA-QUERY-R3-002** | data | SELECT * on case_records Table Without Column Projection | ``backend/app/api/routes/analytics_routes.py:27`` |
| **DATA-QUERY-R3-003** | data | Five Sequential Queries in Analytics Summary - No Parallelization | ``backend/app/api/routes/analytics_routes.py:33-68`` |
| **DATA-RLS-R3-004** | data | Realtime Subscription Filter Can Be Overwritten by Client | ``frontend/src/hooks/useRealtimeCases.js:23-44`` |
| **DATA-SCHEMA-R3-001** | data | Missing Database-Level Enum Constraint for patient_sex | ``backend/app/models/schemas.py:10` (Pydantic only), Datab...` |
| **DATA-SCHEMA-R3-001** | data | Missing Database-Level Enum Constraint for patient_sex | ``backend/app/models/schemas.py:10` (Pydantic only), Datab...` |
| **DATA-SCHEMA-R3-007** | data | Timestamp Fields Missing Timezone Enforcement | ``backend/app/api/routes/cases.py:94-96,198`, Database schema` |
| **DEVOPS-MONITOR-R3-001** | devops | Degraded health checks still return HTTP 200 | ``backend/app/main.py:105`` |
| **PERF-ASSET-R3-001** | performance | PWA Precache Missing Critical WASM Assets for Offline ML | ``frontend/vite.config.js:28`` |
| **REL-RECOVER-R3-001** | reliability | Startup hard-fails if the ML model cannot load | ``backend/app/main.py:36-39`` |
| **SEC-INJ-R3-001** | security | LLM Prompt Injection via Patient Input Fields | ``backend/app/services/llm.py:107-125`` |
| **SEC-INJ-R3-003** | security | Log Injection with PHI Leakage | ``backend/app/api/routes/cases.py:110-113`` |
| **SEC-SUPPLY-R3-001** | security | Python 3.14 Runtime vs 3.13 CI/CD Version Skew Creates Untested Attack Surface | `- Runtime: `python --version` returns `3.14.3`` |
| **SEC-SUPPLY-R3-002** | security | 16 Unpinned Backend Dependencies Allow Phantom Dependency Attacks | ``backend/requirements.txt:1-20`` |

---

## Cross-Domain Cascade Analysis

### Cascade 1: Authentication Compromise Chain

**Attack Path:**
```
SEC-SECRETS-R3-01 (Hardcoded credentials exposed)
    -> SEC-AUTH-R3-01 (Weak JWT validation)
    -> SEC-RBAC-R3-01 (Arbitrary role assignment)
    -> DATA-RLS-R3-01 (Admin RLS bypass)
    -> Complete PHI breach across all facilities
```

**Impact**: Full system compromise with access to all patient health records, ability to modify clinical data, and potential regulatory violations (HIPAA/DISHA).

**Remediation Priority**: P0 (24h)
- Delete exposed credentials (SEC-SECRETS-R3-01)
- Rotate all API keys and secrets
- Add `.gitignore` patterns for credentials
- Strengthen JWT validation (SEC-AUTH-R3-01)
- Enforce strict role validation (SEC-RBAC-R3-01)
- Audit admin RLS policies (DATA-RLS-R3-01)

---

### Cascade 2: ML Safety Failure Chain

**Failure Path:**
```
ML-FEAT-R3-01 (Invalid input propagation: age=0, bp=999)
    -> ML-EDGE-R3-01 (NaN/Infinity in shock_index calculation)
    -> ML-CONF-R3-01 (Uncertainty thresholds not enforced)
    -> ML-FALLBACK-R3-01 (Silent fallback to rule-based without logging)
    -> Patient receives incorrect triage level (EMERGENCY -> ROUTINE)
```

**Impact**: Life-threatening misclassification where critically ill patients are deprioritized. Rural patients waiting hours for ambulance transport may deteriorate without intervention.

**Remediation Priority**: P0 (24h)
- Add input validation bounds (ML-FEAT-R3-01, ML-EDGE-R3-01)
- Enforce confidence thresholds with explicit fallback (ML-CONF-R3-01)
- Add comprehensive logging for ML decisions (ML-FALLBACK-R3-01)
- Implement ML model monitoring and alerting

---

### Cascade 3: Reliability Death Spiral

**Failure Path:**
```
REL-TIMEOUT-R3-01 (LLM SDK has no timeout)
    -> REL-TIMEOUT-R3-02 (Database queries lack timeout)
    -> REL-CIRCUIT-R3-01 (No circuit breaker for external services)
    -> REL-RECOVERY-R3-01 (Health check queries DB during incident)
    -> Load balancer marks all instances unhealthy
    -> Cascading restart loop -> Total outage
```

**Impact**: Single slow API call (Groq/Gemini rate limit) can cascade to complete system unavailability. ASHAs cannot submit cases, doctors cannot review pending patients.

**Remediation Priority**: P1 (7d)
- Add 30s timeout to all LLM SDK calls (REL-TIMEOUT-R3-01)
- Add 10s timeout to all database queries (REL-TIMEOUT-R3-02)
- Implement circuit breaker pattern for LLM fallback chain (REL-CIRCUIT-R3-01)
- Redesign health check to not query production database (REL-RECOVERY-R3-01)

---

### Cascade 4: Data Integrity Collapse

**Failure Path:**
```
DATA-SCHEMA-R3-01 (Weak foreign key constraints)
    + DATA-RLS-R3-02 (No DELETE policy on cases table)
    + DATA-REFER-R3-01 (Orphaned records after user deletion)
    -> RELIABILITY-R3-04 (Inconsistent data prevents queries)
    -> Audit trail corruption
    -> Compliance failure
```

**Impact**: Data inconsistency prevents proper analytics, patient case history becomes unreliable, regulatory audits fail.

**Remediation Priority**: P1 (7d)
- Add cascading foreign key constraints (DATA-SCHEMA-R3-01)
- Implement comprehensive RLS DELETE policies (DATA-RLS-R3-02)
- Add referential integrity checks (DATA-REFER-R3-01)
- Build data consistency validation suite

---

## Domain Summaries

### Security (64 findings)

**Severity Distribution**: 16 CRITICAL, 26 HIGH, 18 MEDIUM, 4 LOW

**Top Critical Issues:**
1. **SEC-AUTH-R3-001**: JWT Access Tokens Stored in Plaintext IndexedDB (Trivial Extraction)
2. **SEC-AUTH-R3-002**: Race Condition in Authentication State Allows Unauthorized Access
3. **SEC-AUTH-R3-003**: Backend Authorization Uses Stale JWT Role (No Profile Re-validation)
4. **SEC-CRYPTO-R3-001**: Supabase Anon Key Exposed in Production Bundle
5. **SEC-CRYPTO-R3-002**: JWT Secret Stored in Plaintext .env.local

**Key Patterns:**
- Api Security: 2 issues
- Auth Flow: 4 issues
- Crypto: 3 issues

**Specialist Reports**: `security/specialists/*.md` (7 reports)

---

### Data (54 findings)

**Severity Distribution**: 16 CRITICAL, 28 HIGH, 10 MEDIUM, 0 LOW

**Top Critical Issues:**
1. **DATA-SCHEMA-R3-001**: Missing Database-Level Enum Constraint for patient_sex
2. **DATA-MIGRATE-R3-006**: Baseline Schema Script Omits `patient_name` Required by Current Runtime
3. **DATA-QUERY-R3-001**: No Connection Pooling - New Supabase Client Created Per Request
4. **DATA-QUERY-R3-002**: SELECT * on case_records Table Without Column Projection
5. **DATA-QUERY-R3-003**: Five Sequential Queries in Analytics Summary - No Parallelization

**Key Patterns:**
- Lifecycle: 3 issues
- Migration: 8 issues
- Query Perf: 4 issues

**Specialist Reports**: `data/specialists/*.md` (6 reports)

---

### Ml Clinical (17 findings)

**Severity Distribution**: 1 CRITICAL, 13 HIGH, 3 MEDIUM, 0 LOW

**Top Critical Issues:**
1. **ML-CLINICAL-R3-1**: Unhandled stroke/anaphylaxis/acute abdomen symptom set can bypass escalation

**Key Patterns:**
- Clinical Accuracy: 2 issues
- Confidence: 3 issues
- Fallback Chain: 2 issues

**Specialist Reports**: `ml-clinical/specialists/*.md` (6 reports)

---

### Reliability (21 findings)

**Severity Distribution**: 1 CRITICAL, 12 HIGH, 8 MEDIUM, 0 LOW

**Top Critical Issues:**
1. **REL-RECOVER-R3-001**: Startup hard-fails if the ML model cannot load

**Key Patterns:**
- Circuit Breaker: 2 issues
- Data Consistency: 1 issues
- Observability: 3 issues

**Specialist Reports**: `reliability/specialists/*.md` (6 reports)

---

### Performance (33 findings)

**Severity Distribution**: 1 CRITICAL, 10 HIGH, 20 MEDIUM, 2 LOW

**Top Critical Issues:**
1. **PERF-ASSET-R3-001**: PWA Precache Missing Critical WASM Assets for Offline ML

**Key Patterns:**
- Bundle Splitting: 2 issues
- Core Web Vitals: 3 issues
- Memory Gc: 2 issues

**Specialist Reports**: `performance/specialists/*.md` (6 reports)

---

### Devops (32 findings)

**Severity Distribution**: 3 CRITICAL, 18 HIGH, 11 MEDIUM, 0 LOW

**Top Critical Issues:**
1. **DEVOPS-DR-R3-002**: Documented restore path can overwrite live production data
2. **DEVOPS-CICD-R3-001**: Secrets are injected into PR jobs that execute repo-controlled code
3. **DEVOPS-MONITOR-R3-001**: Degraded health checks still return HTTP 200

**Key Patterns:**
- Backup Dr: 4 issues
- Ci Cd Security: 3 issues
- Container Deployment: 2 issues

**Specialist Reports**: `devops/specialists/*.md` (6 reports)

---

### Ux (53 findings)

**Severity Distribution**: 0 CRITICAL, 20 HIGH, 29 MEDIUM, 4 LOW

**Top Critical Issues:**
- None

**Key Patterns:**
- Accessibility Wcag: 5 issues
- Form Input: 3 issues
- Information Architecture: 4 issues

**Specialist Reports**: `ux/specialists/*.md` (6 reports)

---

### Qa (49 findings)

**Severity Distribution**: 1 CRITICAL, 25 HIGH, 21 MEDIUM, 2 LOW

**Top Critical Issues:**
1. **QA-SEC-R3-006**: No regression coverage for service‑role key misuse (RLS bypass)

**Key Patterns:**
- Accessibility Tests: 5 issues
- E2E Scenarios: 4 issues
- Edge Cases: 2 issues

**Specialist Reports**: `qa/specialists/*.md` (7 reports)

---


## Appendix A: All Critical Findings

| ID | Title | Domain | Location |
|-------|-------|--------|----------|
| DATA-MIGRATE-R3-006 | Baseline Schema Script Omits `patient_name` Required by Curr | data | ``Context/VitalNet_Phase6_Instructions.md:206`, ...` |
| DATA-QUERY-R3-001 | No Connection Pooling - New Supabase Client Created Per Requ | data | ``backend/app/core/database.py:26-33`` |
| DATA-QUERY-R3-002 | SELECT * on case_records Table Without Column Projection | data | ``backend/app/api/routes/analytics_routes.py:27`` |
| DATA-QUERY-R3-003 | Five Sequential Queries in Analytics Summary - No Paralleliz | data | ``backend/app/api/routes/analytics_routes.py:33-68`` |
| DATA-QUERY-R3-004 | Unbounded Query on Admin Stats Endpoint | data | ``backend/app/api/routes/admin_routes.py:216-217`` |
| DATA-QUERY-R3-005 | N+1 Query Pattern in Admin User List - Profile + Auth User J | data | ``backend/app/api/routes/admin_routes.py:52-78`` |
| DATA-REF-R3-002 | User-Deletion Cascade Chain Is Internally Inconsistent | data | ``Context/VitalNet_Phase6_Instructions.md:169`, ...` |
| DATA-RLS-R3-001 | Admin Stats Endpoint Bypasses RLS via service_role Client | data | ``backend/app/api/routes/admin_routes.py:216-217`` |
| DATA-RLS-R3-002 | Missing DELETE RLS Policy Allows Unauthorized Case Purging | data | `Supabase RLS configuration (no DELETE policy ex...` |
| DATA-RLS-R3-003 | Frontend Anon Key Enables Direct RLS Bypass Attacks | data | ``frontend/src/lib/supabase.js:29-31` + `fronten...` |
| DATA-RLS-R3-004 | Realtime Subscription Filter Can Be Overwritten by Client | data | ``frontend/src/hooks/useRealtimeCases.js:23-44`` |
| DATA-RLS-R3-005 | UPDATE RLS Policy Allows Privilege Escalation via reviewed_b | data | ``backend/app/api/routes/cases.py:195-200` + Sup...` |
| DATA-SCHEMA-R3-001 | Missing Database-Level Enum Constraint for patient_sex | data | ``backend/app/models/schemas.py:10` (Pydantic on...` |
| DATA-SCHEMA-R3-001 | Missing Database-Level Enum Constraint for patient_sex | data | ``backend/app/models/schemas.py:10` (Pydantic on...` |
| DATA-SCHEMA-R3-003 | Missing Foreign Key Constraint on facility_id | data | ``backend/app/api/routes/cases.py:70`, Database ...` |
| DATA-SCHEMA-R3-007 | Timestamp Fields Missing Timezone Enforcement | data | ``backend/app/api/routes/cases.py:94-96,198`, Da...` |
| DEVOPS-CICD-R3-001 | Secrets are injected into PR jobs that execute repo-controll | devops | ``.github/workflows/ci.yml:4-29`` |
| DEVOPS-DR-R3-002 | Documented restore path can overwrite live production data | devops | ``reports/red-team/devops/team-lead.md:396`` |
| DEVOPS-MONITOR-R3-001 | Degraded health checks still return HTTP 200 | devops | ``backend/app/main.py:105`` |
| ML-CLINICAL-R3-1 | Unhandled stroke/anaphylaxis/acute abdomen symptom set can b | ml-clinical | ``backend/app/ml/clinical_features.py:78`` |
| PERF-ASSET-R3-001 | PWA Precache Missing Critical WASM Assets for Offline ML | performance | ``frontend/vite.config.js:28`` |
| QA-SEC-R3-006 | No regression coverage for service‑role key misuse (RLS bypa | qa | ``backend/app/core/database.py:48-54`` |
| REL-RECOVER-R3-001 | Startup hard-fails if the ML model cannot load | reliability | ``backend/app/main.py:36-39`` |
| SEC-AUTH-R3-001 | JWT Access Tokens Stored in Plaintext IndexedDB (Trivial Ext | security | ``frontend/src/lib/supabase.js:4-27`` |
| SEC-AUTH-R3-002 | Race Condition in Authentication State Allows Unauthorized A | security | ``frontend/src/store/authStore.jsx:10-26`, `fron...` |
| SEC-AUTH-R3-003 | Backend Authorization Uses Stale JWT Role (No Profile Re-val | security | ``backend/app/core/auth.py:53-59`` |
| SEC-CONFIG-R3-001 | Plaintext Role Credentials Documented for Production Use | security | ``Context/test_credentials.md:3`, `Context/test_...` |
| SEC-CRYPTO-R3-001 | Supabase Anon Key Exposed in Production Bundle | security | `- `frontend/dist/assets/index-BGCXiES4.js` (pro...` |
| SEC-CRYPTO-R3-002 | JWT Secret Stored in Plaintext .env.local | security | `- `backend/.env.local:3`` |
| SEC-INJ-R3-001 | LLM Prompt Injection via Patient Input Fields | security | ``backend/app/services/llm.py:107-125`` |
| SEC-INJ-R3-002 | PostgREST Filter Injection via Composite Cursor | security | ``backend/app/api/routes/cases.py:164-167`` |
| SEC-INJ-R3-003 | Log Injection with PHI Leakage | security | ``backend/app/api/routes/cases.py:110-113`` |
| SEC-INJ-R3-004 | Second-Order LLM Injection via Stored Case Notes | security | ``backend/app/services/llm.py:100-125` + `backen...` |
| SEC-RBAC-R3-001 | Arbitrary Role Assignment During User Creation | security | ``backend/app/api/routes/admin_routes.py:82-111`` |
| SEC-RBAC-R3-002 | No Case Ownership Validation in Detail Endpoint | security | ``backend/app/api/routes/cases.py:253-270`` |
| SEC-RBAC-R3-003 | Analytics Endpoints Expose Cross-Facility Data | security | ``backend/app/api/routes/analytics_routes.py:10-89`` |
| SEC-SUPPLY-R3-001 | Python 3.14 Runtime vs 3.13 CI/CD Version Skew Creates Untes | security | `- Runtime: `python --version` returns `3.14.3`` |
| SEC-SUPPLY-R3-002 | 16 Unpinned Backend Dependencies Allow Phantom Dependency At | security | ``backend/requirements.txt:1-20`` |
| SEC-SUPPLY-R3-003 | python-jose 3.3.0 Contains Known JWT Signature Bypass (CVE-2 | security | `- `backend/requirements.txt:15` - `python-jose[...` |

## Appendix B: All High Findings

| ID | Title | Domain | Location |
|-------|-------|--------|----------|
| DATA-LIFECYCLE-R3-001 | Case soft-delete fields are unreachable from API | data | ``backend/app/api/routes/cases.py:124`, `backend...` |
| DATA-LIFECYCLE-R3-003 | Frontend deactivation path does not clear device-side PHI qu | data | ``frontend/src/store/authStore.jsx:49`, `fronten...` |
| DATA-LIFECYCLE-R3-004 | Offline queue has timestamp but no TTL or purge execution pa | data | ``frontend/src/lib/offlineQueue.js:42`, `fronten...` |
| DATA-MIGRATE-R3-001 | Realtime Migration Is Labeled Idempotent but Uses Non-Idempo | data | ``backend/supabase/migrations/phase10_realtime_s...` |
| DATA-MIGRATE-R3-002 | Critical Schema Changes Are Executed Out-of-Band in SQL Edit | data | ``docs/REBUILD_INSTRUCTIONS.md:560`, `docs/ARCHI...` |
| DATA-MIGRATE-R3-003 | Runbook Forces Non-Atomic, Stepwise DDL Execution (Partial-M | data | ``docs/REBUILD_INSTRUCTIONS.md:560`, `docs/REBUI...` |
| DATA-MIGRATE-R3-004 | Recommended UNIQUE/Index DDL Is Lock-Heavy and Can Block Cli | data | ``docs/REBUILD_INSTRUCTIONS.md:579`, `docs/REBUI...` |
| DATA-MIGRATE-R3-005 | Schema-Rollout Mismatch Can Permanently Drop Offline Cases | data | ``frontend/src/stores/syncStore.js:117`, `docs/R...` |
| DATA-MIGRATE-R3-007 | Phase-6 Bootstrap SQL Is Not Re-runnable After Partial Failu | data | ``Context/VitalNet_Phase6_Instructions.md:128`, ...` |
| DATA-MIGRATE-R3-009 | No Schema Compatibility Gate Before Serving Traffic | data | ``backend/app/main.py:112`, `backend/app/api/rou...` |
| DATA-MIGRATE-R3-010 | JWT Role-Hook Migration Depends on Manual Dashboard Toggle ( | data | ``Context/VitalNet_Phase6_Instructions.md:323`, ...` |
| DATA-QUERY-R3-006 | Missing Index on case_records.facility_id | data | `Inferred from `analytics_routes.py:29`, `cases....` |
| DATA-QUERY-R3-007 | Missing Composite Index on (triage_priority, created_at) | data | ``backend/app/api/routes/cases.py:157-159`` |
| DATA-QUERY-R3-008 | COUNT(*) Aggregation Without count='exact' Uses Estimate | data | ``backend/app/api/routes/admin_routes.py:216-217`` |
| DATA-QUERY-R3-009 | Auth.admin.list_users() Has No Timeout | data | ``backend/app/api/routes/admin_routes.py:60`` |
| DATA-REF-R3-001 | Facility Delete Has No Explicit FK Child Action (Defaults to | data | ``Context/VitalNet_Phase6_Instructions.md:173`, ...` |
| DATA-REF-R3-003 | A Case Can Exist Without a Submitting User (Nullable FK + Se | data | ``Context/VitalNet_Phase6_Instructions.md:211`, ...` |
| DATA-REF-R3-004 | Deactivated Users Can Still Be Persisted as `reviewed_by` Pa | data | ``backend/app/api/routes/admin_routes.py:162`, `...` |
| DATA-REF-R3-005 | Facility Relationship Drift Between Profile FK and JWT Metad | data | ``backend/app/api/routes/cases.py:70`, `backend/...` |
| DATA-REF-R3-007 | No Constraint Ensures `case_records.facility_id` Matches Sub | data | ``Context/VitalNet_Phase6_Instructions.md:211`, ...` |
| DATA-REF-R3-008 | `create_user` Assumes Trigger-Created Profile Exists (Can Pr | data | ``Context/VitalNet_Phase6_Instructions.md:184`, ...` |
| DATA-RLS-R3-006 | No RLS Policy for facilities Table Allows Unauthorized PHC D | data | ``backend/app/api/routes/admin_routes.py:183` + ...` |
| DATA-RLS-R3-007 | profiles Table RLS Allows ASHA Workers to Enumerate All Faci | data | `Supabase RLS policy + `backend/app/api/routes/a...` |
| DATA-RLS-R3-008 | Service Role Key Usage in Seed Script Violates Least Privile | data | ``backend/seed_user.py:5`` |
| DATA-SCHEMA-R3-004 | Vital Signs Stored as Nullable Without Clinical Validation | data | ``backend/app/models/schemas.py:15-19`, Database...` |
| DATA-SCHEMA-R3-005 | Missing NOT NULL Constraint on submitted_by (PHI Audit Trail | data | ``backend/app/api/routes/cases.py:69`, Database ...` |
| DATA-SCHEMA-R3-006 | Missing UNIQUE Constraint on client_id (Duplicate Detection) | data | ``backend/app/api/routes/cases.py:101`, Database...` |
| DATA-SCHEMA-R3-008 | Missing Indexes on Frequently Queried Columns | data | `Multiple query patterns` |
| DEVOPS-CICD-R3-002 | GitHub Actions are referenced by mutable release tags | devops | ``.github/workflows/ci.yml:11-12,35-36`` |
| DEVOPS-CICD-R3-004 | Python dependency resolution is non-hermetic in secret-beari | devops | ``.github/workflows/ci.yml:18-19`, `backend/requ...` |
| DEVOPS-CICD-R3-005 | Frontend CI executes dependency install scripts from lockfil | devops | ``.github/workflows/ci.yml:42`, `frontend/packag...` |
| DEVOPS-CONTAINER-R3-001 | PR workflow exposes privileged secrets to untrusted code | devops | ``.github/workflows/ci.yml:24`` |
| DEVOPS-CONTAINER-R3-004 | Uvicorn is launched without worker and in-process connection | devops | ``backend/railway.toml:6`, `backend/Procfile:1`` |
| DEVOPS-DR-R3-001 | Backups are not restore-tested anywhere | devops | ``.github/workflows/ci.yml:1`` |
| DEVOPS-DR-R3-004 | Failover is blocked by single-endpoint architecture across A | devops | ``backend/app/core/config.py:5`, `backend/app/co...` |
| DEVOPS-DR-R3-005 | ML recovery procedure rebuilds a different artifact than run | devops | ``AGENTS.md:20`, `backend/app/ml/classifier.py:1...` |
| DEVOPS-DR-R3-006 | DR scope excludes unsynced offline submissions, creating unr | devops | ``frontend/src/lib/offlineQueue.js:3`, `frontend...` |
| DEVOPS-ENV-R3-001 | Staging/Prod Can Inherit Local `.env.local` State | devops | ``backend/app/core/config.py:13`` |
| DEVOPS-ENV-R3-004 | Reachability Probe Uses a Different Base URL Than API Traffi | devops | ``frontend/src/lib/connectivity.js:8`, `frontend...` |
| DEVOPS-ENV-R3-007 | CI Frontend Build Is Staging-Pinned at Compile Time | devops | ``.github/workflows/ci.yml:47`, `frontend/src/ap...` |
| DEVOPS-INFRA-R3-001 | Public Health Check Becomes an Anonymous Internal-State Orac | devops | ``backend/app/main.py:103-115`` |
| DEVOPS-INFRA-R3-002 | Admin Control Plane Is Exposed on the Same Public API Edge | devops | ``backend/app/main.py:79`, `backend/app/api/rout...` |
| DEVOPS-INFRA-R3-003 | Submit-Path Ingress Throttling Trusts Unsigned JWT Claims | devops | ``backend/app/api/routes/cases.py:27-41`, `backe...` |
| DEVOPS-MONITOR-R3-002 | Health coverage misses the clinician write path and RLS-scop | devops | ``backend/app/main.py:110`` |
| DEVOPS-MONITOR-R3-003 | Auth abuse signals (401/403 spikes) are not logged for detec | devops | ``backend/app/main.py:85`, `backend/app/core/aut...` |
| DEVOPS-MONITOR-R3-004 | LLM tier usage is persisted as `unknown`, eliminating degrad | devops | ``backend/app/services/llm.py:210`, `backend/app...` |
| ML-CLINICAL-R3-2 | Missing vitals are treated as normal, creating unsafe downgr | ml-clinical | ``backend/app/ml/clinical_features.py:92`` |
| ML-CLINICAL-R3-3 | Impossible blood pressure combinations are accepted and neve | ml-clinical | ``backend/app/models/schemas.py:15`` |
| ML-CONF-R3-1 | High Uncertainty Never Aborts Triage | ml-clinical | ``backend/app/ml/enhanced_classifier.py:165`` |
| ML-CONF-R3-2 | Offline Confidence Is Uncalibrated While Backend Confidence  | ml-clinical | ``frontend/src/utils/triageClassifier.js:383`` |

*... and 102 more HIGH findings (see deduped register)*

---

## Report Artifacts

### Generated Files

- **Specialist Compendium**: `ROUND3-SPECIALIST-COMPENDIUM.md` (complete specialist reports)
- **Finding Register**: `ROUND3-FINDING-REGISTER.json` (structured finding data)
- **Deduped Findings**: `ROUND3-DEDUPED-FINDINGS.json` (post-deduplication)
- **Master Report v2**: `ROUND3-MASTER-REPORT-v2.md` (this document)
- **Blue Team Backlog**: `ROUND3-BLUE-TEAM-BACKLOG.md` (remediation plan)

### Specialist Reports by Domain

```
docs/security-audits/2026-03-red-team/
├── security/specialists/          (7 reports, 64 findings)
├── data/specialists/              (6 reports, 54 findings)
├── ml-clinical/specialists/       (6 reports, 17 findings)
├── reliability/specialists/       (6 reports, 21 findings)
├── performance/specialists/       (6 reports, 33 findings)
├── devops/specialists/            (6 reports, 32 findings)
├── ux/specialists/                (6 reports, 53 findings)
└── qa/specialists/                (7 reports, 49 findings)
```

---

**Report Generated**: 2026-03-29 19:16:07
**Next Steps**: Review Blue Team Backlog for prioritized remediation plan

---
