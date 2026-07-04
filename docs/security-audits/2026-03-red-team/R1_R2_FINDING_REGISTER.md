# R1/R2 Finding Register

**Generated**: 2026-03-30 00:46:06
**Expected from summary**: 180
**Explicit normalized findings**: 151
**Gap placeholders**: 29
**Total in register**: 180

## Distributions

### Severity

- **CRITICAL**: 18
- **HIGH**: 40
- **MEDIUM**: 75
- **LOW**: 18
- **UNKNOWN**: 29

### Fix Domain

- **security**: 33
- **ux**: 30
- **manual-triage**: 29
- **reliability**: 29
- **data**: 15
- **performance**: 15
- **qa**: 15
- **ml-clinical**: 14

---

## Findings

### AUTH-DD-002: Deactivated users can still access API until token expires
- **Severity**: CRITICAL
- **Round**: R2
- **Source Domain**: security
- **Fix Domain**: security
- **Location**: `backend/app/core/auth.py:29-38`
- **Status**: UNFIXED

### AUTH-DD-003: Token refresh doesn't invalidate old tokens
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: security
- **Fix Domain**: security
- **Location**: `backend/app/core/auth.py`

### AUTH-DD-004: Session fixation possible via token reuse
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: security
- **Fix Domain**: security
- **Location**: `backend/app/api/routes/auth.py`

### AUTH-DD-005: Session timeout issues, concurrent session handling gaps
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: security
- **Fix Domain**: security

### AUTH-DD-006: Session timeout issues, concurrent session handling gaps
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: security
- **Fix Domain**: security

### AUTH-DD-007: Session timeout issues, concurrent session handling gaps
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: security
- **Fix Domain**: security

### AUTH-DD-008: Session timeout issues, concurrent session handling gaps
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: security
- **Fix Domain**: security

### AUTH-DD-009: Session timeout issues, concurrent session handling gaps
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: security
- **Fix Domain**: security

### CHAOS-001: No timeout on Supabase database calls
- **Severity**: CRITICAL
- **Round**: R2
- **Source Domain**: reliability
- **Fix Domain**: reliability
- **Location**: `backend/app/core/database.py`
- **Status**: UNFIXED

### CHAOS-002: No circuit breaker for LLM services
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: reliability
- **Fix Domain**: reliability
- **Location**: `backend/app/services/llm.py`

### CHAOS-003: No timeout on frontend fetch calls
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: reliability
- **Fix Domain**: reliability
- **Location**: `frontend/src/api/cases.js`

### CHAOS-004: Thundering herd on reconnection (all clients retry simultaneously)
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: reliability
- **Fix Domain**: reliability
- **Location**: `frontend/src/hooks/useRealtimeCases.js`

### CHAOS-005: Cascading failure risks, recovery path gaps
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: reliability
- **Fix Domain**: reliability

### CHAOS-006: Cascading failure risks, recovery path gaps
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: reliability
- **Fix Domain**: reliability

### CHAOS-007: Cascading failure risks, recovery path gaps
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: reliability
- **Fix Domain**: reliability

### CHAOS-008: Cascading failure risks, recovery path gaps
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: reliability
- **Fix Domain**: reliability

### CHAOS-009: Cascading failure risks, recovery path gaps
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: reliability
- **Fix Domain**: reliability

### CHAOS-010: Cascading failure risks, recovery path gaps
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: reliability
- **Fix Domain**: reliability

### CODE-001: Schema validation differs between frontend and backend
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: code-quality
- **Fix Domain**: qa
- **Location**: `frontend/src/utils/validation.js`, `backend/app/models/schemas.py`

### CODE-002: Magic numbers throughout codebase (no constants file)
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: code-quality
- **Fix Domain**: qa
- **Location**: Multiple files

### CODE-003: Dead code, inconsistent error handling, missing TypeScript/type hints
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: code-quality
- **Fix Domain**: qa

### CODE-004: Dead code, inconsistent error handling, missing TypeScript/type hints
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: code-quality
- **Fix Domain**: qa

### CODE-005: Dead code, inconsistent error handling, missing TypeScript/type hints
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: code-quality
- **Fix Domain**: qa

### CODE-006: Dead code, inconsistent error handling, missing TypeScript/type hints
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: code-quality
- **Fix Domain**: qa

### CODE-007: Dead code, inconsistent error handling, missing TypeScript/type hints
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: code-quality
- **Fix Domain**: qa

### CODE-008: Zero test coverage on safety-critical ML triage code
- **Severity**: CRITICAL
- **Round**: R1
- **Source Domain**: code-quality
- **Fix Domain**: qa
- **Location**: `backend/app/ml/`, `backend/tests/`
- **Status**: UNFIXED

### CODE-009: Style inconsistencies, minor refactoring opportunities
- **Severity**: LOW
- **Round**: R1
- **Source Domain**: code-quality
- **Fix Domain**: qa

### CODE-010: Style inconsistencies, minor refactoring opportunities
- **Severity**: LOW
- **Round**: R1
- **Source Domain**: code-quality
- **Fix Domain**: qa

### CODE-011: Style inconsistencies, minor refactoring opportunities
- **Severity**: LOW
- **Round**: R1
- **Source Domain**: code-quality
- **Fix Domain**: qa

### CODE-012: Style inconsistencies, minor refactoring opportunities
- **Severity**: LOW
- **Round**: R1
- **Source Domain**: code-quality
- **Fix Domain**: qa

### CODE-013: Style inconsistencies, minor refactoring opportunities
- **Severity**: LOW
- **Round**: R1
- **Source Domain**: code-quality
- **Fix Domain**: qa

### CODE-014: Style inconsistencies, minor refactoring opportunities
- **Severity**: LOW
- **Round**: R1
- **Source Domain**: code-quality
- **Fix Domain**: qa

### CODE-015: Style inconsistencies, minor refactoring opportunities
- **Severity**: LOW
- **Round**: R1
- **Source Domain**: code-quality
- **Fix Domain**: qa

### COMPLY-001: PHI transmitted to LLM services without Data Processing Agreement
- **Severity**: CRITICAL
- **Round**: R2
- **Source Domain**: compliance
- **Fix Domain**: data
- **Location**: `backend/app/services/llm.py:100-125`
- **Status**: LEGAL RISK

### COMPLY-002: No audit logging for PHI access
- **Severity**: CRITICAL
- **Round**: R2
- **Source Domain**: compliance
- **Fix Domain**: data
- **Location**: `backend/app/api/routes/cases.py`
- **Status**: UNFIXED

### COMPLY-003: PHI stored in IndexedDB without encryption
- **Severity**: CRITICAL
- **Round**: R2
- **Source Domain**: compliance
- **Fix Domain**: data
- **Location**: `frontend/src/lib/offlineQueue.js`
- **Status**: UNFIXED

### COMPLY-004: No session inactivity timeout
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: compliance
- **Fix Domain**: data
- **Location**: `frontend/src/store/authStore.jsx`

### COMPLY-005: No patient consent capture mechanism
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: compliance
- **Fix Domain**: data
- **Location**: `frontend/src/pages/IntakeForm.jsx`

### COMPLY-006: No data retention policy implemented
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: compliance
- **Fix Domain**: data
- **Location**: No implementation exists

### COMPLY-007: No patient data deletion endpoint
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: compliance
- **Fix Domain**: data
- **Location**: `backend/app/api/routes/`

### COMPLY-008: PHI visible in browser console logs
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: compliance
- **Fix Domain**: data
- **Location**: Multiple components with console.log

### COMPLY-009: Data minimization issues, access control gaps
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: compliance
- **Fix Domain**: data

### COMPLY-010: Data minimization issues, access control gaps
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: compliance
- **Fix Domain**: data

### COMPLY-011: Data minimization issues, access control gaps
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: compliance
- **Fix Domain**: data

### COMPLY-012: Data minimization issues, access control gaps
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: compliance
- **Fix Domain**: data

### COMPLY-013: Data minimization issues, access control gaps
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: compliance
- **Fix Domain**: data

### COMPLY-014: Documentation gaps
- **Severity**: LOW
- **Round**: R2
- **Source Domain**: compliance
- **Fix Domain**: data

### COMPLY-015: Documentation gaps
- **Severity**: LOW
- **Round**: R2
- **Source Domain**: compliance
- **Fix Domain**: data

### ML-DD-001: LLM fallback returns unstructured text parsed unsafely
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: ml-clinical
- **Fix Domain**: ml-clinical
- **Location**: `backend/app/services/llm.py:250-280`

### ML-DD-002: ONNX returns ROUTINE on unknown label index (silent misclassification)
- **Severity**: CRITICAL
- **Round**: R2
- **Source Domain**: ml-clinical
- **Fix Domain**: ml-clinical
- **Location**: `frontend/src/utils/triageClassifier.js:380-381`
- **Status**: UNFIXED

### ML-DD-003: No confidence threshold on ML predictions
- **Severity**: CRITICAL
- **Round**: R2
- **Source Domain**: ml-clinical
- **Fix Domain**: ml-clinical
- **Location**: Multiple locations
- **Status**: UNFIXED

### ML-DD-004: Feature schema drift between frontend/backend
- **Severity**: CRITICAL
- **Round**: R2
- **Source Domain**: ml-clinical
- **Fix Domain**: ml-clinical
- **Location**: `frontend/src/utils/triageClassifier.js`, `backend/app/ml/clinical_features.py`

### ML-DD-005: No validation of input ranges before inference
- **Severity**: CRITICAL
- **Round**: R2
- **Source Domain**: ml-clinical
- **Fix Domain**: ml-clinical
- **Location**: `backend/app/ml/enhanced_classifier.py`

### ML-DD-006: No model versioning - frontend/backend can use mismatched models
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: ml-clinical
- **Fix Domain**: ml-clinical
- **Location**: No version check exists

### ML-DD-007: Clinical red flags not explicitly checked
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: ml-clinical
- **Fix Domain**: ml-clinical
- **Location**: `backend/app/ml/enhanced_classifier.py`

### ML-DD-008: No human override mechanism in triage flow
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: ml-clinical
- **Fix Domain**: ml-clinical
- **Location**: `frontend/src/pages/IntakeForm.jsx`

### ML-DD-009: Model drift detection, calibration issues, edge case handling
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: ml-clinical
- **Fix Domain**: ml-clinical

### ML-DD-010: Model drift detection, calibration issues, edge case handling
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: ml-clinical
- **Fix Domain**: ml-clinical

### ML-DD-011: Model drift detection, calibration issues, edge case handling
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: ml-clinical
- **Fix Domain**: ml-clinical

### ML-DD-012: Model drift detection, calibration issues, edge case handling
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: ml-clinical
- **Fix Domain**: ml-clinical

### ML-DD-013: Documentation gaps
- **Severity**: LOW
- **Round**: R2
- **Source Domain**: ml-clinical
- **Fix Domain**: ml-clinical

### ML-DD-014: Documentation gaps
- **Severity**: LOW
- **Round**: R2
- **Source Domain**: ml-clinical
- **Fix Domain**: ml-clinical

### MOBILE-DD-001: Viewport not optimized for 320px minimum width
- **Severity**: CRITICAL
- **Round**: R2
- **Source Domain**: ux
- **Fix Domain**: ux
- **Location**: `frontend/index.html`, various components

### MOBILE-DD-003: Virtual keyboard hides submit button on intake form
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: ux
- **Fix Domain**: ux
- **Location**: `frontend/src/pages/IntakeForm.jsx`

### MOBILE-DD-004: No offline indicator visible to users
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: ux
- **Fix Domain**: ux
- **Location**: `frontend/src/App.jsx`

### MOBILE-DD-005: Font loading causes layout shift (CLS)
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: ux
- **Fix Domain**: ux
- **Location**: `frontend/index.html`

### MOBILE-DD-006: PWA install flow, gesture conflicts, safe area issues
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: ux
- **Fix Domain**: ux

### MOBILE-DD-007: PWA install flow, gesture conflicts, safe area issues
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: ux
- **Fix Domain**: ux

### MOBILE-DD-008: PWA install flow, gesture conflicts, safe area issues
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: ux
- **Fix Domain**: ux

### MOBILE-DD-009: PWA install flow, gesture conflicts, safe area issues
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: ux
- **Fix Domain**: ux

### MOBILE-DD-010: PWA install flow, gesture conflicts, safe area issues
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: ux
- **Fix Domain**: ux

### MOBILE-DD-011: PWA install flow, gesture conflicts, safe area issues
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: ux
- **Fix Domain**: ux

### MOBILE-DD-012: PWA install flow, gesture conflicts, safe area issues
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: ux
- **Fix Domain**: ux

### MOBILE-DD-013: Minor polish issues
- **Severity**: LOW
- **Round**: R2
- **Source Domain**: ux
- **Fix Domain**: ux

### MOBILE-DD-014: Minor polish issues
- **Severity**: LOW
- **Round**: R2
- **Source Domain**: ux
- **Fix Domain**: ux

### MOBILE-DD-015: Minor polish issues
- **Severity**: LOW
- **Round**: R2
- **Source Domain**: ux
- **Fix Domain**: ux

### MOBILE-DD-016: Minor polish issues
- **Severity**: LOW
- **Round**: R2
- **Source Domain**: ux
- **Fix Domain**: ux

### PENTEST-001: Hardcoded Groq API key committed to repository
- **Severity**: CRITICAL
- **Round**: R2
- **Source Domain**: security
- **Fix Domain**: security
- **Location**: `backend/.env` (in git history)
- **Status**: REQUIRES IMMEDIATE ROTATION

### PENTEST-002: SQL injection via unsanitized case search
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: security
- **Fix Domain**: security
- **Location**: `backend/app/api/routes/cases.py:145`

### PENTEST-003: XSS via case notes field (stored)
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: security
- **Fix Domain**: security
- **Location**: `frontend/src/components/BriefingCard.jsx:78`

### PENTEST-004: IDOR vulnerabilities, path traversal risks, dependency CVEs
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: security
- **Fix Domain**: security

### PENTEST-005: IDOR vulnerabilities, path traversal risks, dependency CVEs
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: security
- **Fix Domain**: security

### PENTEST-006: IDOR vulnerabilities, path traversal risks, dependency CVEs
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: security
- **Fix Domain**: security

### PENTEST-007: IDOR vulnerabilities, path traversal risks, dependency CVEs
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: security
- **Fix Domain**: security

### PENTEST-008: IDOR vulnerabilities, path traversal risks, dependency CVEs
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: security
- **Fix Domain**: security

### PENTEST-009: IDOR vulnerabilities, path traversal risks, dependency CVEs
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: security
- **Fix Domain**: security

### PENTEST-010: IDOR vulnerabilities, path traversal risks, dependency CVEs
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: security
- **Fix Domain**: security

### PERF-001: No code splitting - entire app loaded upfront (~2MB)
- **Severity**: CRITICAL
- **Round**: R1
- **Source Domain**: performance
- **Fix Domain**: performance
- **Location**: `frontend/vite.config.js`
- **Status**: UNFIXED

### PERF-002: ONNX runtime (~2MB) loaded for ALL users, even non-ASHA workers
- **Severity**: CRITICAL
- **Round**: R1
- **Source Domain**: performance
- **Fix Domain**: performance
- **Location**: `frontend/src/utils/triageClassifier.js:1-10`
- **Status**: UNFIXED

### PERF-003: Realtime subscription memory leak on unmount
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: performance
- **Fix Domain**: performance
- **Location**: `frontend/src/hooks/useRealtimeCases.js:45-60`

### PERF-004: No virtualization for case lists (renders all DOM nodes)
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: performance
- **Fix Domain**: performance
- **Location**: `frontend/src/pages/Dashboard.jsx:120-180`

### PERF-005: BriefingCard re-renders on every parent state change
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: performance
- **Fix Domain**: performance
- **Location**: `frontend/src/components/BriefingCard.jsx`

### PERF-006: N+1 query pattern in analytics endpoint
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: performance
- **Fix Domain**: performance
- **Location**: `backend/app/api/routes/analytics_routes.py:45-80`

### PERF-007: No HTTP caching headers on static API responses
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: performance
- **Fix Domain**: performance
- **Location**: `backend/app/main.py`

### PERF-008: Bundle analysis issues, font loading, image optimization gaps, service worker caching issues
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: performance
- **Fix Domain**: performance

### PERF-009: Bundle analysis issues, font loading, image optimization gaps, service worker caching issues
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: performance
- **Fix Domain**: performance

### PERF-010: Bundle analysis issues, font loading, image optimization gaps, service worker caching issues
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: performance
- **Fix Domain**: performance

### PERF-011: Bundle analysis issues, font loading, image optimization gaps, service worker caching issues
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: performance
- **Fix Domain**: performance

### PERF-012: Bundle analysis issues, font loading, image optimization gaps, service worker caching issues
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: performance
- **Fix Domain**: performance

### PERF-013: Bundle analysis issues, font loading, image optimization gaps, service worker caching issues
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: performance
- **Fix Domain**: performance

### PERF-014: Bundle analysis issues, font loading, image optimization gaps, service worker caching issues
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: performance
- **Fix Domain**: performance

### PERF-015: Bundle analysis issues, font loading, image optimization gaps, service worker caching issues
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: performance
- **Fix Domain**: performance

### R1R2-GAP-001: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-002: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-003: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-004: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-005: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-006: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-007: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-008: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-009: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-010: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-011: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-012: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-013: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-014: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-015: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-016: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-017: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-018: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-019: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-020: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-021: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-022: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-023: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-024: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-025: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-026: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-027: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-028: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### R1R2-GAP-029: Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.
- **Severity**: UNKNOWN
- **Round**: R1/R2
- **Source Domain**: unknown
- **Fix Domain**: manual-triage
- **Status**: PENDING_MANUAL_TRIAGE
- **Inferred Placeholder**: yes

### REL-001: No React Error Boundary - component crash kills entire app
- **Severity**: CRITICAL
- **Round**: R1
- **Source Domain**: reliability
- **Fix Domain**: reliability
- **Location**: `frontend/src/App.jsx`
- **Status**: UNFIXED

### REL-002: No timeout on Gemini LLM calls (can hang indefinitely)
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: reliability
- **Fix Domain**: reliability
- **Location**: `backend/app/services/llm.py:180-220`

### REL-003: Retry logic missing on all API calls
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: reliability
- **Fix Domain**: reliability
- **Location**: `frontend/src/api/cases.js`

### REL-004: IndexedDB queue has no size limit (can exhaust storage)
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: reliability
- **Fix Domain**: reliability
- **Location**: `frontend/src/lib/offlineQueue.js:20-45`

### REL-005: Sync failures silently swallowed
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: reliability
- **Fix Domain**: reliability
- **Location**: `frontend/src/stores/syncStore.js:80-95`

### REL-006: No exponential backoff on retries
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: reliability
- **Fix Domain**: reliability
- **Location**: Multiple locations

### REL-007: Transaction handling gaps, stale data issues, race conditions
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: reliability
- **Fix Domain**: reliability

### REL-008: Transaction handling gaps, stale data issues, race conditions
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: reliability
- **Fix Domain**: reliability

### REL-009: Transaction handling gaps, stale data issues, race conditions
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: reliability
- **Fix Domain**: reliability

### REL-010: Transaction handling gaps, stale data issues, race conditions
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: reliability
- **Fix Domain**: reliability

### REL-011: Transaction handling gaps, stale data issues, race conditions
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: reliability
- **Fix Domain**: reliability

### REL-012: Transaction handling gaps, stale data issues, race conditions
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: reliability
- **Fix Domain**: reliability

### REL-013: Transaction handling gaps, stale data issues, race conditions
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: reliability
- **Fix Domain**: reliability

### REL-014: Transaction handling gaps, stale data issues, race conditions
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: reliability
- **Fix Domain**: reliability

### REL-015: Transaction handling gaps, stale data issues, race conditions
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: reliability
- **Fix Domain**: reliability

### REL-016: Minor logging gaps
- **Severity**: LOW
- **Round**: R1
- **Source Domain**: reliability
- **Fix Domain**: reliability

### SEC-001: No rate limiting on authentication endpoints
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: security
- **Fix Domain**: security
- **Location**: `backend/app/api/routes/auth.py`

### SEC-002: JWT payload decoded without verification; user_metadata.role used for authorization allowing privilege escalation
- **Severity**: CRITICAL
- **Round**: R1
- **Source Domain**: security
- **Fix Domain**: security
- **Alt IDs**: AUTH-DD-001
- **Location**: `backend/app/core/auth.py:55-58`
- **Status**: UNFIXED

### SEC-003: CORS allows all origins in development mode
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: security
- **Fix Domain**: security
- **Location**: `backend/app/main.py:25-30`

### SEC-004: Role checks inconsistent across endpoints
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: security
- **Fix Domain**: security
- **Location**: Multiple route files

### SEC-005: No CSRF protection on state-changing endpoints
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: security
- **Fix Domain**: security
- **Location**: `backend/app/main.py`

### SEC-006: Various input validation gaps, missing security headers, verbose error messages, etc.
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: security
- **Fix Domain**: security

### SEC-007: Various input validation gaps, missing security headers, verbose error messages, etc.
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: security
- **Fix Domain**: security

### SEC-008: Various input validation gaps, missing security headers, verbose error messages, etc.
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: security
- **Fix Domain**: security

### SEC-009: Various input validation gaps, missing security headers, verbose error messages, etc.
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: security
- **Fix Domain**: security

### SEC-010: Various input validation gaps, missing security headers, verbose error messages, etc.
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: security
- **Fix Domain**: security

### SEC-011: Various input validation gaps, missing security headers, verbose error messages, etc.
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: security
- **Fix Domain**: security

### SEC-012: Various input validation gaps, missing security headers, verbose error messages, etc.
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: security
- **Fix Domain**: security

### SEC-013: Various input validation gaps, missing security headers, verbose error messages, etc.
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: security
- **Fix Domain**: security

### SEC-014: Minor logging issues, debug endpoints exposed
- **Severity**: LOW
- **Round**: R1
- **Source Domain**: security
- **Fix Domain**: security

### SEC-015: Minor logging issues, debug endpoints exposed
- **Severity**: LOW
- **Round**: R1
- **Source Domain**: security
- **Fix Domain**: security

### SYNC-DD-001: Multi-tab coordination issues, partial sync handling
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: reliability
- **Fix Domain**: reliability

### SYNC-DD-002: Multi-tab coordination issues, partial sync handling
- **Severity**: MEDIUM
- **Round**: R2
- **Source Domain**: reliability
- **Fix Domain**: reliability

### SYNC-DD-003: Silent data loss on 4xx server errors (cases deleted from queue)
- **Severity**: HIGH
- **Round**: R2
- **Source Domain**: reliability
- **Fix Domain**: reliability
- **Location**: `frontend/src/stores/syncStore.js:117-125`

### UX-001: Touch targets below 44x44px healthcare minimum
- **Severity**: CRITICAL
- **Round**: R1
- **Source Domain**: ux
- **Fix Domain**: ux
- **Alt IDs**: MOBILE-DD-002
- **Location**: `frontend/src/components/NavBar.jsx:30-38`
- **Status**: UNFIXED

### UX-002: No visible focus indicators for keyboard navigation
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: ux
- **Fix Domain**: ux
- **Location**: `frontend/src/index.css`

### UX-003: Toast notifications not announced to screen readers
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: ux
- **Fix Domain**: ux
- **Location**: `frontend/src/components/ToastProvider.jsx`

### UX-004: Form validation errors not associated with inputs (aria-describedby)
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: ux
- **Fix Domain**: ux
- **Location**: `frontend/src/pages/IntakeForm.jsx`

### UX-005: Color contrast issues in low-light conditions
- **Severity**: HIGH
- **Round**: R1
- **Source Domain**: ux
- **Fix Domain**: ux
- **Location**: Various components

### UX-006: Native alert/confirm dialogs used instead of accessible modals
- **Severity**: CRITICAL
- **Round**: R1
- **Source Domain**: ux
- **Fix Domain**: ux
- **Location**: Multiple components

### UX-007: Navigation patterns, information hierarchy, loading states
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: ux
- **Fix Domain**: ux

### UX-008: Navigation patterns, information hierarchy, loading states
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: ux
- **Fix Domain**: ux

### UX-009: Navigation patterns, information hierarchy, loading states
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: ux
- **Fix Domain**: ux

### UX-010: Navigation patterns, information hierarchy, loading states
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: ux
- **Fix Domain**: ux

### UX-011: Navigation patterns, information hierarchy, loading states
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: ux
- **Fix Domain**: ux

### UX-012: Navigation patterns, information hierarchy, loading states
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: ux
- **Fix Domain**: ux

### UX-013: Navigation patterns, information hierarchy, loading states
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: ux
- **Fix Domain**: ux

### UX-014: Navigation patterns, information hierarchy, loading states
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: ux
- **Fix Domain**: ux

### UX-015: Navigation patterns, information hierarchy, loading states
- **Severity**: MEDIUM
- **Round**: R1
- **Source Domain**: ux
- **Fix Domain**: ux
