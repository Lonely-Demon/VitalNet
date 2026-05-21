# VitalNet Round 3 - Blue Team Remediation Backlog

**Generated**: 2026-03-29 19:19:03
**Source**: Round 3 Red Team audit (323 unique findings)
**Purpose**: Actionable remediation plan with priorities, owners, and verification criteria

---

## Priority Definitions

| Priority | Timeline | Criteria | Example |
|----------|----------|----------|---------|
| **P0** | 24 hours | Exposed credentials, RLS bypass, service_role misuse | Hardcoded admin password in repo |
| **P1** | 7 days | CRITICAL security/safety issues, ML misclassification, timeouts | No timeout on LLM calls |
| **P2** | 30 days | HIGH/MEDIUM issues affecting reliability, performance, UX | Missing unit tests for ML features |
| **P3** | 90 days | LOW severity, nice-to-have improvements | Better error messages |

---

## Summary Statistics

| Priority | Count | Total Effort (SP) | Deadline |
|----------|-------|-------------------|----------|
| **P0** | 17 | 115 | 2026-03-30 |
| **P1** | 70 | 372 | 2026-04-05 |
| **P2** | 224 | 883 | 2026-04-28 |
| **P3** | 12 | 30 | 2026-06-27 |

### By Domain

| Domain | P0 | P1 | P2 | P3 | Total |
|--------|----|----|----|----|-------|
| data | 6 | 15 | 33 | 0 | 54 |
| devops | 1 | 6 | 25 | 0 | 32 |
| ml-clinical | 0 | 5 | 12 | 0 | 17 |
| performance | 0 | 3 | 28 | 2 | 33 |
| qa | 1 | 9 | 37 | 2 | 49 |
| reliability | 0 | 4 | 17 | 0 | 21 |
| security | 9 | 23 | 28 | 4 | 64 |
| ux | 0 | 5 | 44 | 4 | 53 |

---

## P0: Stop-Ship (17 tasks - Due: 2026-03-30 19:19)

**Critical**: Must be completed before next deployment. Involves exposed secrets, authentication bypass, or RLS vulnerabilities.

| ID | Title | Owner | Effort | Verification |
|-------|-------|-------|--------|--------------|
| DATA-QUERY-R3-001 | No Connection Pooling - New Supabase Client Created Per Requ | Database Team | 8 SP | Manual test + security scan |
| DATA-REF-R3-002 | User-Deletion Cascade Chain Is Internally Inconsistent | Database Team | 8 SP | Manual test + security scan |
| DATA-RLS-R3-001 | Admin Stats Endpoint Bypasses RLS via service_role Client | Database Team (RLS) | 8 SP | Test RLS policies in staging |
| DATA-RLS-R3-003 | Frontend Anon Key Enables Direct RLS Bypass Attacks | Database Team (RLS) | 8 SP | Test RLS policies in staging |
| DATA-RLS-R3-005 | UPDATE RLS Policy Allows Privilege Escalation via reviewed_b | Database Team (RLS) | 5 SP | Test RLS policies in staging |
| DATA-SCHEMA-R3-003 | Missing Foreign Key Constraint on facility_id | Database Team | 2 SP | Manual test + security scan |
| DEVOPS-CICD-R3-001 | Secrets are injected into PR jobs that execute repo-controll | DevOps Team | 8 SP | Verify rotation + .gitignore |
| QA-SEC-R3-006 | No regression coverage for service‑role key misuse (RLS bypa | QA Team | 8 SP | Test RLS policies in staging |
| SEC-AUTH-R3-001 | JWT Access Tokens Stored in Plaintext IndexedDB (Trivial Ext | Backend Team (Auth) | 8 SP | Manual test + security scan |
| SEC-AUTH-R3-003 | Backend Authorization Uses Stale JWT Role (No Profile Re-val | Backend Team (Auth) | 2 SP | Manual test + security scan |
| SEC-CONFIG-R3-001 | Plaintext Role Credentials Documented for Production Use | Security Team | 8 SP | Verify rotation + .gitignore |
| SEC-CRYPTO-R3-001 | Supabase Anon Key Exposed in Production Bundle | Security Team | 8 SP | Manual test + security scan |
| SEC-CRYPTO-R3-002 | JWT Secret Stored in Plaintext .env.local | Security Team | 8 SP | Verify rotation + .gitignore |
| SEC-INJ-R3-002 | PostgREST Filter Injection via Composite Cursor | Security Team | 8 SP | Manual test + security scan |
| SEC-INJ-R3-004 | Second-Order LLM Injection via Stored Case Notes | Security Team | 8 SP | Manual test + security scan |
| SEC-RBAC-R3-001 | Arbitrary Role Assignment During User Creation | Security Team | 8 SP | Manual test + security scan |
| SEC-RBAC-R3-002 | No Case Ownership Validation in Detail Endpoint | Security Team | 2 SP | Manual test + security scan |

### P0 Detailed Tasks

#### 1. DATA-QUERY-R3-001: No Connection Pooling - New Supabase Client Created Per Request

- **Severity**: CRITICAL
- **Owner**: Database Team
- **Effort**: 8 story points
- **Location**: ``backend/app/core/database.py:26-33``
- **Source**: `data\specialists\query-perf.md`

**Remediation**:
  ```python
  # Option 1: Client cache with token-keyed pooling
  from functools import lru_cache
  @lru_cache(maxsize=128)

**Verification Criteria**:
- [ ] Code changes reviewed and approved
- [ ] Manual testing completed
- [ ] Security scan shows issue resolved
- [ ] Deployed to staging environment

---

#### 2. DATA-REF-R3-002: User-Deletion Cascade Chain Is Internally Inconsistent

- **Severity**: CRITICAL
- **Owner**: Database Team
- **Effort**: 8 story points
- **Location**: ``Context/VitalNet_Phase6_Instructions.md:169`, `Context/VitalNet_Phase6_Instructions.md:211`, `Context/VitalNet_Phase6_Instructions.md:239`, `Context/VitalNet_Phase6_Instructions.md:248``
- **Source**: `data\specialists\referential.md`

**Remediation**:
  Pick one coherent policy and encode it at DB level: either (A) keep hard deletes and set all `case_records -> profiles` FKs to `ON DELETE SET NULL` (with immutable audit snapshots), or (B) forbid hard delete and remove cascade from `profiles.id -> auth.users.id`, enforcing soft-deactivation only.

**Verification Criteria**:
- [ ] Code changes reviewed and approved
- [ ] Manual testing completed
- [ ] Security scan shows issue resolved
- [ ] Deployed to staging environment

---

#### 3. DATA-RLS-R3-001: Admin Stats Endpoint Bypasses RLS via service_role Client

- **Severity**: CRITICAL
- **Owner**: Database Team (RLS)
- **Effort**: 8 story points
- **Location**: ``backend/app/api/routes/admin_routes.py:216-217``
- **Source**: `data\specialists\rls-policy.md`

**Remediation**:
  ```python
  @router.get('/stats')
  async def get_stats(
  authorization: str = Header(None),
  user: dict = Depends(require_role('admin')),

**Verification Criteria**:
- [ ] Code changes reviewed and approved
- [ ] Manual testing completed
- [ ] Security scan shows issue resolved
- [ ] Deployed to staging environment

---

#### 4. DATA-RLS-R3-003: Frontend Anon Key Enables Direct RLS Bypass Attacks

- **Severity**: CRITICAL
- **Owner**: Database Team (RLS)
- **Effort**: 8 story points
- **Location**: ``frontend/src/lib/supabase.js:29-31` + `frontend/.env.local``
- **Source**: `data\specialists\rls-policy.md`

**Remediation**:
  1. **Audit ALL RLS policies** to ensure they deny unauthenticated access:
  ```sql
  -- Bad: Allows anon key reads if any condition passes
  using (submitted_by = auth.uid() or is_public = true)

**Verification Criteria**:
- [ ] Code changes reviewed and approved
- [ ] Manual testing completed
- [ ] Security scan shows issue resolved
- [ ] Deployed to staging environment

---

#### 5. DATA-RLS-R3-005: UPDATE RLS Policy Allows Privilege Escalation via reviewed_by Manipulation

- **Severity**: CRITICAL
- **Owner**: Database Team (RLS)
- **Effort**: 5 story points
- **Location**: ``backend/app/api/routes/cases.py:195-200` + Supabase RLS policy`
- **Source**: `data\specialists\rls-policy.md`

**Remediation**:
  ```sql
  -- Replace broad doctor_update policy with granular policies:
  -- Policy 1: Doctors can only mark cases as reviewed in their facility
  create policy "doctor_review_own_facility" on public.case_records for update

**Verification Criteria**:
- [ ] Code changes reviewed and approved
- [ ] Manual testing completed
- [ ] Security scan shows issue resolved
- [ ] Deployed to staging environment

---

#### 6. DATA-SCHEMA-R3-003: Missing Foreign Key Constraint on facility_id

- **Severity**: CRITICAL
- **Owner**: Database Team
- **Effort**: 2 story points
- **Location**: ``backend/app/api/routes/cases.py:70`, Database schema missing FK`
- **Source**: `data\specialists\schema.md`

**Remediation**:
  ```sql
  -- Add foreign key constraint
  ALTER TABLE case_records
  ADD CONSTRAINT fk_facility
  FOREIGN KEY (facility_id)

**Verification Criteria**:
- [ ] Code changes reviewed and approved
- [ ] Manual testing completed
- [ ] Security scan shows issue resolved
- [ ] Deployed to staging environment

---

#### 7. DEVOPS-CICD-R3-001: Secrets are injected into PR jobs that execute repo-controlled code

- **Severity**: CRITICAL
- **Owner**: DevOps Team
- **Effort**: 8 story points
- **Location**: ``.github/workflows/ci.yml:4-29``
- **Source**: `devops\specialists\ci-cd-security.md`

**Remediation**:
  Do not pass production-grade secrets into `pull_request` workflows. Split untrusted PR validation from secret-bearing integration tests, use least-privilege test credentials, and gate any secret-backed job behind a trusted event/approval boundary.

**Verification Criteria**:
- [ ] Code changes reviewed and approved
- [ ] Manual testing completed
- [ ] Security scan shows issue resolved
- [ ] Deployed to staging environment

---

#### 8. QA-SEC-R3-006: No regression coverage for service‑role key misuse (RLS bypass)

- **Severity**: CRITICAL
- **Owner**: QA Team
- **Effort**: 8 story points
- **Location**: ``backend/app/core/database.py:48-54``
- **Source**: `qa\specialists\security-tests.md`

**Remediation**:
  Add a static‑analysis check (pytest + import‑scan) that runs in CI and fails if any route‑handler file imports `supabase_admin` and uses it on `case_records` or `profiles` tables, or enforce the rule via a custom lint rule.

**Verification Criteria**:
- [ ] Code changes reviewed and approved
- [ ] Manual testing completed
- [ ] Security scan shows issue resolved
- [ ] Deployed to staging environment

---

#### 9. SEC-AUTH-R3-001: JWT Access Tokens Stored in Plaintext IndexedDB (Trivial Extraction)

- **Severity**: CRITICAL
- **Owner**: Backend Team (Auth)
- **Effort**: 8 story points
- **Location**: ``frontend/src/lib/supabase.js:4-27``
- **Source**: `security\specialists\auth-flow.md`

**Remediation**:
  1. Use Web Crypto API to encrypt tokens at rest in IndexedDB using device-bound key:
  ```javascript
  import { subtle } from 'crypto'
  async function encryptToken(token) {

**Verification Criteria**:
- [ ] Code changes reviewed and approved
- [ ] Manual testing completed
- [ ] Security scan shows issue resolved
- [ ] Deployed to staging environment

---

#### 10. SEC-AUTH-R3-003: Backend Authorization Uses Stale JWT Role (No Profile Re-validation)

- **Severity**: CRITICAL
- **Owner**: Backend Team (Auth)
- **Effort**: 2 story points
- **Location**: ``backend/app/core/auth.py:53-59``
- **Source**: `security\specialists\auth-flow.md`

**Remediation**:
  1. Add real-time profile validation in `get_current_user()`:
  ```python
  async def get_current_user(authorization: str = Header(None)) -> dict:
  # ... existing token validation ...

**Verification Criteria**:
- [ ] Code changes reviewed and approved
- [ ] Manual testing completed
- [ ] Security scan shows issue resolved
- [ ] Deployed to staging environment

---

#### 11. SEC-CONFIG-R3-001: Plaintext Role Credentials Documented for Production Use

- **Severity**: CRITICAL
- **Owner**: Security Team
- **Effort**: 8 story points
- **Location**: ``Context/test_credentials.md:3`, `Context/test_credentials.md:6`, `Context/test_credentials.md:7`, `Context/test_credentials.md:18`, `Context/test_credentials.md:19`, `Context/VitalNet_Phase6_Instructions.md:333`, `Context/VitalNet_Phase6_Instructions.md:334`, `Context/VitalNet_Phase6_Instructions.md:335``
- **Source**: `security\specialists\secrets-config.md`

**Remediation**:
  Remove all real credential values from repository docs immediately; rotate passwords for all listed users; disable/delete any `@test.vitalnet` accounts in non-dev environments; replace docs with placeholders and a secure secret-distribution process (vault/1Password/CI secrets).

**Verification Criteria**:
- [ ] Code changes reviewed and approved
- [ ] Manual testing completed
- [ ] Security scan shows issue resolved
- [ ] Deployed to staging environment

---

#### 12. SEC-CRYPTO-R3-001: Supabase Anon Key Exposed in Production Bundle

- **Severity**: CRITICAL
- **Owner**: Security Team
- **Effort**: 8 story points
- **Location**: `- `frontend/dist/assets/index-BGCXiES4.js` (production bundle)`
- **Source**: `security\specialists\crypto.md`

**Remediation**:
  1. **Accept that anon key exposure is by design** - Supabase docs state: "The anon key is safe to use in a browser if you have RLS policies enabled"
  2. **Fix AUTH-DD-001 IMMEDIATELY**: Backend MUST verify JWT signatures using `supabase_anon.auth.get_user(token)` (already implemented in `auth.py:31` but role enforcement still uses unverified payload at line 55-58)
  3. **Audit all RLS policies** for gaps (PENTEST-002 shows existing SQL injection risk)
  4. **Implement anon key rotation**:
  ```python

**Verification Criteria**:
- [ ] Code changes reviewed and approved
- [ ] Manual testing completed
- [ ] Security scan shows issue resolved
- [ ] Deployed to staging environment

---

#### 13. SEC-CRYPTO-R3-002: JWT Secret Stored in Plaintext .env.local

- **Severity**: CRITICAL
- **Owner**: Security Team
- **Effort**: 8 story points
- **Location**: `- `backend/.env.local:3``
- **Source**: `security\specialists\crypto.md`

**Remediation**:
  1. **IMMEDIATE (24h)**:
  - Rotate JWT secret in Supabase dashboard (Project Settings → API → Generate new JWT secret)
  - Update `.env.local` with new secret
  - Redeploy backend
  - Force logout all users (invalidates old JWTs)

**Verification Criteria**:
- [ ] Code changes reviewed and approved
- [ ] Manual testing completed
- [ ] Security scan shows issue resolved
- [ ] Deployed to staging environment

---

#### 14. SEC-INJ-R3-002: PostgREST Filter Injection via Composite Cursor

- **Severity**: CRITICAL
- **Owner**: Security Team
- **Effort**: 8 story points
- **Location**: ``backend/app/api/routes/cases.py:164-167``
- **Source**: `security\specialists\injection.md`

**Remediation**:
  ```python
  from urllib.parse import quote
  from datetime import datetime
  # Validate input types strictly

**Verification Criteria**:
- [ ] Code changes reviewed and approved
- [ ] Manual testing completed
- [ ] Security scan shows issue resolved
- [ ] Deployed to staging environment

---

#### 15. SEC-INJ-R3-004: Second-Order LLM Injection via Stored Case Notes

- **Severity**: CRITICAL
- **Owner**: Security Team
- **Effort**: 8 story points
- **Location**: ``backend/app/services/llm.py:100-125` + `backend/app/api/routes/cases.py:253-270``
- **Source**: `security\specialists\injection.md`

**Remediation**:
  1. **Sanitize on input** (Defense-in-depth with SEC-INJ-R3-001):
  ```python
  # cases.py:58 (in submit_case endpoint)
  form_data = form.model_dump()

**Verification Criteria**:
- [ ] Code changes reviewed and approved
- [ ] Manual testing completed
- [ ] Security scan shows issue resolved
- [ ] Deployed to staging environment

---

#### 16. SEC-RBAC-R3-001: Arbitrary Role Assignment During User Creation

- **Severity**: CRITICAL
- **Owner**: Security Team
- **Effort**: 8 story points
- **Location**: ``backend/app/api/routes/admin_routes.py:82-111``
- **Source**: `security\specialists\rbac.md`

**Remediation**:
  1. Add enum validation to `CreateUserRequest`:
  ```python
  from enum import Enum
  class UserRole(str, Enum):

**Verification Criteria**:
- [ ] Code changes reviewed and approved
- [ ] Manual testing completed
- [ ] Security scan shows issue resolved
- [ ] Deployed to staging environment

---

#### 17. SEC-RBAC-R3-002: No Case Ownership Validation in Detail Endpoint

- **Severity**: CRITICAL
- **Owner**: Security Team
- **Effort**: 2 story points
- **Location**: ``backend/app/api/routes/cases.py:253-270``
- **Source**: `security\specialists\rbac.md`

**Remediation**:
  1. Add explicit facility boundary check (defense-in-depth):
  ```python
  # After fetching the case
  case = result.data
  user_facility = user.get("user_metadata", {}).get("facility_id")

**Verification Criteria**:
- [ ] Code changes reviewed and approved
- [ ] Manual testing completed
- [ ] Security scan shows issue resolved
- [ ] Deployed to staging environment

---


## P1: Critical (70 tasks - Due: 2026-04-05)

**High Priority**: Security vulnerabilities, ML safety issues, reliability problems that could cause outages.

| ID | Title | Owner | Effort | Domain |
|-------|-------|-------|--------|--------|
| DATA-MIGRATE-R3-006 | Baseline Schema Script Omits `patient_name` Required by Curr | Database Team | 8 SP | data |
| DATA-QUERY-R3-002 | SELECT * on case_records Table Without Column Projection | Database Team | 8 SP | data |
| DATA-QUERY-R3-003 | Five Sequential Queries in Analytics Summary - No Paralleliz | Database Team | 8 SP | data |
| DATA-QUERY-R3-004 | Unbounded Query on Admin Stats Endpoint | Database Team | 8 SP | data |
| DATA-QUERY-R3-005 | N+1 Query Pattern in Admin User List - Profile + Auth User J | Database Team | 8 SP | data |
| DATA-RLS-R3-002 | Missing DELETE RLS Policy Allows Unauthorized Case Purging | Database Team (RLS) | 2 SP | data |
| DATA-RLS-R3-004 | Realtime Subscription Filter Can Be Overwritten by Client | Database Team (RLS) | 8 SP | data |
| DATA-SCHEMA-R3-001 | Missing Database-Level Enum Constraint for patient_sex | Database Team | 2 SP | data |
| DATA-SCHEMA-R3-001 | Missing Database-Level Enum Constraint for patient_sex | Database Team | 2 SP | data |
| DATA-SCHEMA-R3-007 | Timestamp Fields Missing Timezone Enforcement | Database Team | 2 SP | data |
| DEVOPS-DR-R3-002 | Documented restore path can overwrite live production data | DevOps Team | 8 SP | devops |
| DEVOPS-MONITOR-R3-001 | Degraded health checks still return HTTP 200 | DevOps Team | 8 SP | devops |
| ML-CLINICAL-R3-1 | Unhandled stroke/anaphylaxis/acute abdomen symptom set can b | ML Team | 8 SP | ml-clinical |
| PERF-ASSET-R3-001 | PWA Precache Missing Critical WASM Assets for Offline ML | Frontend Team | 2 SP | performance |
| REL-RECOVER-R3-001 | Startup hard-fails if the ML model cannot load | Backend Team (Reliability) | 8 SP | reliability |
| SEC-AUTH-R3-002 | Race Condition in Authentication State Allows Unauthorized A | Backend Team (Auth) | 8 SP | security |
| SEC-INJ-R3-001 | LLM Prompt Injection via Patient Input Fields | Security Team | 8 SP | security |
| SEC-INJ-R3-003 | Log Injection with PHI Leakage | Security Team | 2 SP | security |
| SEC-RBAC-R3-003 | Analytics Endpoints Expose Cross-Facility Data | Security Team | 8 SP | security |
| SEC-SUPPLY-R3-001 | Python 3.14 Runtime vs 3.13 CI/CD Version Skew Creates Untes | Security Team | 8 SP | security |
| SEC-SUPPLY-R3-002 | 16 Unpinned Backend Dependencies Allow Phantom Dependency At | Security Team | 8 SP | security |
| SEC-SUPPLY-R3-003 | python-jose 3.3.0 Contains Known JWT Signature Bypass (CVE-2 | Security Team | 8 SP | security |
| DATA-MIGRATE-R3-003 | Runbook Forces Non-Atomic, Stepwise DDL Execution (Partial-M | Database Team | 13 SP | data |
| DATA-MIGRATE-R3-010 | JWT Role-Hook Migration Depends on Manual Dashboard Toggle ( | Database Team | 13 SP | data |
| DATA-QUERY-R3-009 | Auth.admin.list_users() Has No Timeout | Database Team | 2 SP | data |
| DATA-RLS-R3-006 | No RLS Policy for facilities Table Allows Unauthorized PHC D | Database Team (RLS) | 5 SP | data |
| DATA-SCHEMA-R3-004 | Vital Signs Stored as Nullable Without Clinical Validation | Database Team | 2 SP | data |
| DEVOPS-DR-R3-001 | Backups are not restore-tested anywhere | DevOps Team | 5 SP | devops |
| DEVOPS-INFRA-R3-003 | Submit-Path Ingress Throttling Trusts Unsigned JWT Claims | DevOps Team | 5 SP | devops |
| DEVOPS-MONITOR-R3-003 | Auth abuse signals (401/403 spikes) are not logged for detec | DevOps Team | 2 SP | devops |
| DEVOPS-MONITOR-R3-004 | LLM tier usage is persisted as `unknown`, eliminating degrad | DevOps Team | 5 SP | devops |
| ML-CLINICAL-R3-3 | Impossible blood pressure combinations are accepted and neve | ML Team | 5 SP | ml-clinical |
| ML-CONF-R3-1 | High Uncertainty Never Aborts Triage | ML Team | 5 SP | ml-clinical |
| ML-CONF-R3-3 | LLM Briefing Drops Classifier Uncertainty Before Prompting | ML Team | 5 SP | ml-clinical |
| ML-DRIFT-R3-2 | Drift Metrics Are Training-Only and Never Turn Into Live Mon | ML Team | 5 SP | ml-clinical |
| PERF-BUNDLE-R3-004 | ASHA History View Still Pulls Intake ONNX and Zod Stack | Frontend Team | 5 SP | performance |
| PERF-MEM-R3-002 | Overlapping offline sync runs retain queue snapshots | Frontend Team | 5 SP | performance |
| QA-A11Y-R3-001 | No Automated Accessibility Regression Coverage | QA Team | 5 SP | qa |
| QA-E2E-R3-003 | Emergency cases have no explicit handoff or escalation path | QA Team | 5 SP | qa |
| QA-E2E-R3-004 | Role-based route guard missing from panel entry but present  | QA Team | 2 SP | qa |
| QA-INTEG-R3-006 | LLM fallback‑chain integration is completely untested | QA Team | 5 SP | qa |
| QA-PERF-R3-003 | No Endurance Test for Repeated Triage Submission and Queue D | QA Team | 5 SP | qa |
| QA-PERF-R3-005 | No Regression Tests for Queue Growth Under Network Churn | QA Team | 5 SP | qa |
| QA-SEC-R3-001 | Admin privilege-escalation paths have no regression coverage | QA Team | 5 SP | qa |
| QA-SEC-R3-005 | Rate-limiting logic lacks regression tests for bypass via ta | QA Team | 2 SP | qa |
| QA-SEC-R3-007 | No tests for token‑parsing failures leading to RLS mismatch | QA Team | 5 SP | qa |
| REL-OBS-R3-001 | Missing request correlation IDs in backend error logs | Backend Team (Reliability) | 2 SP | reliability |
| REL-OBS-R3-004 | Queue sync failures lack structured telemetry | Backend Team (Reliability) | 5 SP | reliability |
| REL-TIMEOUT-R3-02 | Offline queue replays can run concurrently and duplicate exp | Backend Team (Reliability) | 5 SP | reliability |
| SEC-API-R3-002 | Extension of SEC-001 - Only `submit_case` Is Throttled | Security Team | 5 SP | security |

*... and 20 more P1 tasks (see finding register)*


## P2: Important (224 tasks - Due: 2026-04-28)

**Medium Priority**: HIGH/MEDIUM severity issues affecting code quality, performance, UX, testing coverage.

| ID | Title | Owner | Effort | Domain |
|-------|-------|-------|--------|--------|
| DATA-LIFECYCLE-R3-001 | Case soft-delete fields are unreachable from API | Database Team | 5 SP | data |
| DATA-LIFECYCLE-R3-003 | Frontend deactivation path does not clear device-side PHI qu | Database Team | 5 SP | data |
| DATA-LIFECYCLE-R3-004 | Offline queue has timestamp but no TTL or purge execution pa | Database Team | 5 SP | data |
| DATA-MIGRATE-R3-001 | Realtime Migration Is Labeled Idempotent but Uses Non-Idempo | Database Team | 13 SP | data |
| DATA-MIGRATE-R3-002 | Critical Schema Changes Are Executed Out-of-Band in SQL Edit | Database Team | 13 SP | data |
| DATA-MIGRATE-R3-004 | Recommended UNIQUE/Index DDL Is Lock-Heavy and Can Block Cli | Database Team | 5 SP | data |
| DATA-MIGRATE-R3-005 | Schema-Rollout Mismatch Can Permanently Drop Offline Cases | Database Team | 5 SP | data |
| DATA-MIGRATE-R3-007 | Phase-6 Bootstrap SQL Is Not Re-runnable After Partial Failu | Database Team | 5 SP | data |
| DATA-MIGRATE-R3-009 | No Schema Compatibility Gate Before Serving Traffic | Database Team | 5 SP | data |
| DATA-QUERY-R3-006 | Missing Index on case_records.facility_id | Database Team | 2 SP | data |
| DATA-QUERY-R3-007 | Missing Composite Index on (triage_priority, created_at) | Database Team | 2 SP | data |
| DATA-QUERY-R3-008 | COUNT(*) Aggregation Without count='exact' Uses Estimate | Database Team | 5 SP | data |
| DATA-REF-R3-001 | Facility Delete Has No Explicit FK Child Action (Defaults to | Database Team | 5 SP | data |
| DATA-REF-R3-003 | A Case Can Exist Without a Submitting User (Nullable FK + Se | Database Team | 5 SP | data |
| DATA-REF-R3-004 | Deactivated Users Can Still Be Persisted as `reviewed_by` Pa | Database Team | 5 SP | data |
| DATA-REF-R3-005 | Facility Relationship Drift Between Profile FK and JWT Metad | Database Team | 5 SP | data |
| DATA-REF-R3-007 | No Constraint Ensures `case_records.facility_id` Matches Sub | Database Team | 5 SP | data |
| DATA-REF-R3-008 | `create_user` Assumes Trigger-Created Profile Exists (Can Pr | Database Team | 5 SP | data |
| DATA-RLS-R3-007 | profiles Table RLS Allows ASHA Workers to Enumerate All Faci | Database Team (RLS) | 5 SP | data |
| DATA-RLS-R3-008 | Service Role Key Usage in Seed Script Violates Least Privile | Database Team (RLS) | 5 SP | data |
| DATA-SCHEMA-R3-005 | Missing NOT NULL Constraint on submitted_by (PHI Audit Trail | Database Team | 2 SP | data |
| DATA-SCHEMA-R3-006 | Missing UNIQUE Constraint on client_id (Duplicate Detection) | Database Team | 2 SP | data |
| DATA-SCHEMA-R3-008 | Missing Indexes on Frequently Queried Columns | Database Team | 2 SP | data |
| DEVOPS-CICD-R3-002 | GitHub Actions are referenced by mutable release tags | DevOps Team | 5 SP | devops |
| DEVOPS-CICD-R3-004 | Python dependency resolution is non-hermetic in secret-beari | DevOps Team | 5 SP | devops |
| DEVOPS-CICD-R3-005 | Frontend CI executes dependency install scripts from lockfil | DevOps Team | 5 SP | devops |
| DEVOPS-CONTAINER-R3-001 | PR workflow exposes privileged secrets to untrusted code | DevOps Team | 5 SP | devops |
| DEVOPS-CONTAINER-R3-004 | Uvicorn is launched without worker and in-process connection | DevOps Team | 5 SP | devops |
| DEVOPS-DR-R3-004 | Failover is blocked by single-endpoint architecture across A | DevOps Team | 13 SP | devops |
| DEVOPS-DR-R3-005 | ML recovery procedure rebuilds a different artifact than run | DevOps Team | 13 SP | devops |
| DEVOPS-DR-R3-006 | DR scope excludes unsynced offline submissions, creating unr | DevOps Team | 5 SP | devops |
| DEVOPS-ENV-R3-001 | Staging/Prod Can Inherit Local `.env.local` State | DevOps Team | 5 SP | devops |
| DEVOPS-ENV-R3-004 | Reachability Probe Uses a Different Base URL Than API Traffi | DevOps Team | 5 SP | devops |
| DEVOPS-ENV-R3-007 | CI Frontend Build Is Staging-Pinned at Compile Time | DevOps Team | 5 SP | devops |
| DEVOPS-INFRA-R3-001 | Public Health Check Becomes an Anonymous Internal-State Orac | DevOps Team | 5 SP | devops |
| DEVOPS-INFRA-R3-002 | Admin Control Plane Is Exposed on the Same Public API Edge | DevOps Team | 5 SP | devops |
| DEVOPS-MONITOR-R3-002 | Health coverage misses the clinician write path and RLS-scop | DevOps Team | 5 SP | devops |
| ML-CLINICAL-R3-2 | Missing vitals are treated as normal, creating unsafe downgr | ML Team | 2 SP | ml-clinical |
| ML-CONF-R3-2 | Offline Confidence Is Uncalibrated While Backend Confidence  | ML Team | 5 SP | ml-clinical |
| ML-DRIFT-R3-1 | Model Artifacts Load Without Integrity Verification | ML Team | 5 SP | ml-clinical |
| ML-EDGE-R3-003 | Symptoms are not normalized before scoring | ML Team | 5 SP | ml-clinical |
| ML-FALLBACK-R3-001 | Generic fallback advice under-triages emergencies | ML Team | 5 SP | ml-clinical |
| ML-FALLBACK-R3-002 | Parser failure path silently fail-opens into saved boilerpla | ML Team | 5 SP | ml-clinical |
| ML-FEAT-R3-1 | Age 0 Is Silently Rewritten to Adult Defaults | ML Team | 5 SP | ml-clinical |
| ML-FEAT-R3-1 | Age 0 Is Silently Rewritten to Adult Defaults | ML Team | 5 SP | ml-clinical |
| ML-FEAT-R3-3 | Backend Feature Extraction Is Not Robust to Blank or Non-Fin | ML Team | 5 SP | ml-clinical |
| PERF-BUNDLE-R3-001 | Role Panels Are Eagerly Bundled Into the Shell | Frontend Team | 5 SP | performance |
| PERF-MEM-R3-003 | Dashboard retains an unbounded case buffer and clones it per | Frontend Team | 5 SP | performance |
| PERF-NET-R3-06 | Reachability probe can target a different origin than real A | Frontend Team | 5 SP | performance |
| PERF-RENDER-R3-001 | Toast Provider Invalidates the Entire App on Every Toast | Frontend Team | 5 SP | performance |

*... and 174 more P2 tasks (see finding register)*


## P3: Nice-to-Have (12 tasks - Due: 2026-06-27)

**Low Priority**: LOW severity issues, code cleanup, documentation improvements.

| ID | Title | Owner | Domain |
|-------|-------|-------|--------|
| PERF-NET-R3-02 | PWA precaches triage model assets for every user | Frontend Team | performance |
| PERF-NET-R3-03 | Identical case fetches are not coalesced | Frontend Team | performance |
| QA-EDGE-R3-004 | Analytics buckets can misplace boundary timestamps | QA Team | qa |
| QA-EDGE-R3-009 | LLM fallback briefing omits _model_used key after tier cascade | QA Team | qa |
| SEC-API-R3-004 | API Versioning Is Metadata Only | Security Team | security |
| SEC-AUTH-R3-012 | Session Tokens Visible in Browser DevTools Network Tab | Backend Team (Auth) | security |
| SEC-CRYPTO-R3-008 | Missing Constant-Time Comparison for Tokens | Backend Team (Auth) | security |
| SEC-RBAC-R3-013 | Profile Updates via Supabase Client Don't Validate Role Changes | Backend Team (Auth) | security |
| UX-IA-R3-003 | Doctor refresh control uses queue language for a case dashboard | Frontend Team (UX) | ux |
| UX-IA-R3-004 | Complaint terminology changes mid-flow | Frontend Team (UX) | ux |
| UX-IA-R3-005 | Empty state copy for 'All Cases' tab falsely implies a pending queue | Frontend Team (UX) | ux |
| UX-MOBILE-R3-007 | No touch-action CSS to prevent double-tap zoom and improve tap respons | Frontend Team (UX) | ux |

---

## Suggested Sprint Planning

### Sprint 1 (Week 1): P0 + Critical P1

**Focus**: Stop-ship issues and authentication/RLS vulnerabilities

**Goals**:
- Complete all P0 tasks (exposed secrets, RLS bypass)
- Address authentication chain vulnerabilities
- Fix ML input validation (emergency misclassification risk)

**Estimated Effort**: 115 SP (P0) + 56 SP (top 10 P1) = 171 SP total

**Team Allocation**:
- Security/Backend: P0 credential rotation, RLS policies, auth fixes
- ML Team: Input validation and confidence thresholds
- DevOps: Key rotation, .gitignore updates, security scanning setup

---

### Sprint 2 (Week 2-3): Remaining P1

**Focus**: Reliability, timeout issues, circuit breakers

**Goals**:
- Add timeouts to all external service calls
- Implement circuit breaker pattern for LLM fallback
- Fix database connection pooling
- Add comprehensive logging and monitoring

**Estimated Effort**: 131 SP

---

### Sprint 3-4 (Week 4-6): High-priority P2

**Focus**: Testing coverage, performance, UX improvements

**Goals**:
- Add unit tests for ML features (QA-UNIT-R3-*)
- Implement accessibility fixes (UX-A11Y-R3-*)
- Optimize frontend bundle size and rendering
- Add integration tests for critical flows

**Estimated Effort**: 167 SP

---

## Verification & Sign-off

### P0 Sign-off Criteria

Before marking P0 complete, verify:

- [ ] All exposed credentials deleted from git history
- [ ] All API keys and secrets rotated
- [ ] `.gitignore` updated to prevent future leaks
- [ ] RLS policies tested in staging with multiple roles
- [ ] Security scan (SAST/secrets) passes in CI
- [ ] Penetration test confirms vulnerabilities patched

### P1 Sign-off Criteria

- [ ] All fixes deployed to staging
- [ ] Integration tests pass
- [ ] Manual testing by QA team
- [ ] Performance benchmarks meet targets
- [ ] Documentation updated

---

## Related Documents

- **Master Report v2**: `ROUND3-MASTER-REPORT-v2.md`
- **Finding Register**: `ROUND3-FINDING-REGISTER.json`
- **Deduped Findings**: `ROUND3-DEDUPED-FINDINGS.json`
- **Specialist Reports**: `[domain]/specialists/*.md`

---

**Backlog Generated**: 2026-03-29 19:19:03
**Next Review**: Weekly sprint planning meeting
