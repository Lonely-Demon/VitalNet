# VitalNet Red Team - Known Issues from Rounds 1 & 2

> **Purpose**: This document summarizes ALL findings from Red Team Rounds 1 and 2.
> Round 3 specialists MUST review this to avoid duplicating existing findings.
> Only report **NET-NEW** issues or **EXTENSIONS** of existing findings.

---

## Quick Reference: Finding Counts

| Round | Domain | Critical | High | Medium | Low | Total |
|-------|--------|----------|------|--------|-----|-------|
| R1 | Security | 1 | 5 | 8 | 1 | 15 |
| R1 | Performance | 2 | 5 | 8 | 0 | 15 |
| R1 | Reliability | 1 | 6 | 7 | 1 | 15 |
| R1 | UX/Accessibility | 2 | 7 | 6 | 0 | 15 |
| R1 | Code Quality | 1 | 2 | 6 | 6 | 15 |
| R2 | Auth Deep-Dive | 2 | 5 | 5 | 2 | 14 |
| R2 | Sync Deep-Dive | 2 | 3 | 5 | 2 | 12 |
| R2 | ML Safety Deep-Dive | 4 | 4 | 4 | 2 | 14 |
| R2 | Mobile UX Deep-Dive | 3 | 5 | 6 | 2 | 16 |
| R2 | Healthcare Compliance | 3 | 5 | 5 | 2 | 15 |
| R2 | Penetration Testing | 2 | 6 | 7 | 4 | 19 |
| R2 | Chaos Engineering | 2 | 4 | 6 | 3 | 15 |
| **TOTAL** | | **25** | **57** | **73** | **25** | **180** |

---

## SECURITY DOMAIN (30 findings)

### Critical
- **SEC-002 / AUTH-DD-001**: JWT payload decoded without verification; user_metadata.role used for authorization allowing privilege escalation
  - Location: `backend/app/core/auth.py:55-58`
  - Status: UNFIXED
  
- **AUTH-DD-002**: Deactivated users can still access API until token expires
  - Location: `backend/app/core/auth.py:29-38`
  - Status: UNFIXED

- **PENTEST-001**: Hardcoded Groq API key committed to repository
  - Location: `backend/.env` (in git history)
  - Status: REQUIRES IMMEDIATE ROTATION

### High
- **SEC-001**: No rate limiting on authentication endpoints
  - Location: `backend/app/api/routes/auth.py`
  
- **SEC-003**: CORS allows all origins in development mode
  - Location: `backend/app/main.py:25-30`
  
- **SEC-004**: Role checks inconsistent across endpoints
  - Location: Multiple route files
  
- **SEC-005**: No CSRF protection on state-changing endpoints
  - Location: `backend/app/main.py`
  
- **AUTH-DD-003**: Token refresh doesn't invalidate old tokens
  - Location: `backend/app/core/auth.py`
  
- **AUTH-DD-004**: Session fixation possible via token reuse
  - Location: `backend/app/api/routes/auth.py`
  
- **PENTEST-002**: SQL injection via unsanitized case search
  - Location: `backend/app/api/routes/cases.py:145`
  
- **PENTEST-003**: XSS via case notes field (stored)
  - Location: `frontend/src/components/BriefingCard.jsx:78`

### Medium
- **SEC-006 to SEC-013**: Various input validation gaps, missing security headers, verbose error messages, etc.
- **AUTH-DD-005 to AUTH-DD-009**: Session timeout issues, concurrent session handling gaps
- **PENTEST-004 to PENTEST-010**: IDOR vulnerabilities, path traversal risks, dependency CVEs

### Low
- **SEC-014, SEC-015**: Minor logging issues, debug endpoints exposed

---

## PERFORMANCE DOMAIN (21 findings)

### Critical
- **PERF-001**: No code splitting - entire app loaded upfront (~2MB)
  - Location: `frontend/vite.config.js`
  - Status: UNFIXED
  
- **PERF-002**: ONNX runtime (~2MB) loaded for ALL users, even non-ASHA workers
  - Location: `frontend/src/utils/triageClassifier.js:1-10`
  - Status: UNFIXED

### High
- **PERF-003**: Realtime subscription memory leak on unmount
  - Location: `frontend/src/hooks/useRealtimeCases.js:45-60`
  
- **PERF-004**: No virtualization for case lists (renders all DOM nodes)
  - Location: `frontend/src/pages/Dashboard.jsx:120-180`
  
- **PERF-005**: BriefingCard re-renders on every parent state change
  - Location: `frontend/src/components/BriefingCard.jsx`
  
- **PERF-006**: N+1 query pattern in analytics endpoint
  - Location: `backend/app/api/routes/analytics_routes.py:45-80`
  
- **PERF-007**: No HTTP caching headers on static API responses
  - Location: `backend/app/main.py`

### Medium
- **PERF-008 to PERF-015**: Bundle analysis issues, font loading, image optimization gaps, service worker caching issues

---

## RELIABILITY DOMAIN (27 findings)

### Critical
- **REL-001**: No React Error Boundary - component crash kills entire app
  - Location: `frontend/src/App.jsx`
  - Status: UNFIXED
  
- **CHAOS-001**: No timeout on Supabase database calls
  - Location: `backend/app/core/database.py`
  - Status: UNFIXED

### High
- **REL-002**: No timeout on Gemini LLM calls (can hang indefinitely)
  - Location: `backend/app/services/llm.py:180-220`
  
- **REL-003**: Retry logic missing on all API calls
  - Location: `frontend/src/api/cases.js`
  
- **REL-004**: IndexedDB queue has no size limit (can exhaust storage)
  - Location: `frontend/src/lib/offlineQueue.js:20-45`
  
- **REL-005**: Sync failures silently swallowed
  - Location: `frontend/src/stores/syncStore.js:80-95`
  
- **REL-006**: No exponential backoff on retries
  - Location: Multiple locations
  
- **SYNC-DD-003**: Silent data loss on 4xx server errors (cases deleted from queue)
  - Location: `frontend/src/stores/syncStore.js:117-125`
  
- **CHAOS-002**: No circuit breaker for LLM services
  - Location: `backend/app/services/llm.py`
  
- **CHAOS-003**: No timeout on frontend fetch calls
  - Location: `frontend/src/api/cases.js`
  
- **CHAOS-004**: Thundering herd on reconnection (all clients retry simultaneously)
  - Location: `frontend/src/hooks/useRealtimeCases.js`

### Medium
- **REL-007 to REL-015**: Transaction handling gaps, stale data issues, race conditions
- **SYNC-DD-001, SYNC-DD-002**: Multi-tab coordination issues, partial sync handling
- **CHAOS-005 to CHAOS-010**: Cascading failure risks, recovery path gaps

### Low
- **REL-016**: Minor logging gaps

---

## UX/ACCESSIBILITY DOMAIN (31 findings)

### Critical
- **UX-001 / MOBILE-DD-002**: Touch targets below 44x44px healthcare minimum
  - Location: `frontend/src/components/NavBar.jsx:30-38`
  - Status: UNFIXED
  
- **UX-006**: Native alert/confirm dialogs used instead of accessible modals
  - Location: Multiple components
  
- **MOBILE-DD-001**: Viewport not optimized for 320px minimum width
  - Location: `frontend/index.html`, various components

### High
- **UX-002**: No visible focus indicators for keyboard navigation
  - Location: `frontend/src/index.css`
  
- **UX-003**: Toast notifications not announced to screen readers
  - Location: `frontend/src/components/ToastProvider.jsx`
  
- **UX-004**: Form validation errors not associated with inputs (aria-describedby)
  - Location: `frontend/src/pages/IntakeForm.jsx`
  
- **UX-005**: Color contrast issues in low-light conditions
  - Location: Various components
  
- **MOBILE-DD-003**: Virtual keyboard hides submit button on intake form
  - Location: `frontend/src/pages/IntakeForm.jsx`
  
- **MOBILE-DD-004**: No offline indicator visible to users
  - Location: `frontend/src/App.jsx`
  
- **MOBILE-DD-005**: Font loading causes layout shift (CLS)
  - Location: `frontend/index.html`

### Medium
- **UX-007 to UX-015**: Navigation patterns, information hierarchy, loading states
- **MOBILE-DD-006 to MOBILE-DD-012**: PWA install flow, gesture conflicts, safe area issues

### Low
- **MOBILE-DD-013 to MOBILE-DD-016**: Minor polish issues

---

## ML/CLINICAL SAFETY DOMAIN (14 findings)

### Critical
- **ML-DD-002**: ONNX returns ROUTINE on unknown label index (silent misclassification)
  - Location: `frontend/src/utils/triageClassifier.js:380-381`
  - Status: UNFIXED
  
- **ML-DD-003**: No confidence threshold on ML predictions
  - Location: Multiple locations
  - Status: UNFIXED
  
- **ML-DD-004**: Feature schema drift between frontend/backend
  - Location: `frontend/src/utils/triageClassifier.js`, `backend/app/ml/clinical_features.py`
  
- **ML-DD-005**: No validation of input ranges before inference
  - Location: `backend/app/ml/enhanced_classifier.py`

### High
- **ML-DD-001**: LLM fallback returns unstructured text parsed unsafely
  - Location: `backend/app/services/llm.py:250-280`
  
- **ML-DD-006**: No model versioning - frontend/backend can use mismatched models
  - Location: No version check exists
  
- **ML-DD-007**: Clinical red flags not explicitly checked
  - Location: `backend/app/ml/enhanced_classifier.py`
  
- **ML-DD-008**: No human override mechanism in triage flow
  - Location: `frontend/src/pages/IntakeForm.jsx`

### Medium
- **ML-DD-009 to ML-DD-012**: Model drift detection, calibration issues, edge case handling

### Low
- **ML-DD-013, ML-DD-014**: Documentation gaps

---

## HEALTHCARE COMPLIANCE DOMAIN (15 findings)

### Critical
- **COMPLY-001**: PHI transmitted to LLM services without Data Processing Agreement
  - Location: `backend/app/services/llm.py:100-125`
  - Status: LEGAL RISK
  
- **COMPLY-002**: No audit logging for PHI access
  - Location: `backend/app/api/routes/cases.py`
  - Status: UNFIXED
  
- **COMPLY-003**: PHI stored in IndexedDB without encryption
  - Location: `frontend/src/lib/offlineQueue.js`
  - Status: UNFIXED

### High
- **COMPLY-004**: No session inactivity timeout
  - Location: `frontend/src/store/authStore.jsx`
  
- **COMPLY-005**: No patient consent capture mechanism
  - Location: `frontend/src/pages/IntakeForm.jsx`
  
- **COMPLY-006**: No data retention policy implemented
  - Location: No implementation exists
  
- **COMPLY-007**: No patient data deletion endpoint
  - Location: `backend/app/api/routes/`
  
- **COMPLY-008**: PHI visible in browser console logs
  - Location: Multiple components with console.log

### Medium
- **COMPLY-009 to COMPLY-013**: Data minimization issues, access control gaps

### Low
- **COMPLY-014, COMPLY-015**: Documentation gaps

---

## CODE QUALITY DOMAIN (15 findings)

### Critical
- **CODE-008**: Zero test coverage on safety-critical ML triage code
  - Location: `backend/app/ml/`, `backend/tests/`
  - Status: UNFIXED

### High
- **CODE-001**: Schema validation differs between frontend and backend
  - Location: `frontend/src/utils/validation.js`, `backend/app/models/schemas.py`
  
- **CODE-002**: Magic numbers throughout codebase (no constants file)
  - Location: Multiple files

### Medium
- **CODE-003 to CODE-008**: Dead code, inconsistent error handling, missing TypeScript/type hints

### Low
- **CODE-009 to CODE-015**: Style inconsistencies, minor refactoring opportunities

---

## CROSS-CUTTING PATTERNS (Do NOT re-report these)

These patterns were identified across multiple domains. Round 3 specialists should look for SPECIFIC INSTANCES not yet documented, not re-report the pattern itself:

1. **Missing Timeouts**: Found everywhere - DB calls, LLM calls, fetch calls, ONNX inference
2. **Silent Failures**: Errors swallowed without user feedback or logging
3. **No Retry Logic**: No exponential backoff anywhere in the codebase
4. **Schema Drift**: Frontend/backend validation ranges and field names differ
5. **Memory Leaks**: Realtime subscriptions, event listeners not cleaned up
6. **No Circuit Breakers**: Sequential fallback without fast-fail
7. **PHI Handling Gaps**: Logging, encryption, consent, audit trails all missing

---

## KEY FILES ALREADY AUDITED

Round 3 specialists should look for issues NOT YET FOUND in these files:

### Backend (Python/FastAPI)
- `backend/app/main.py` - App setup, CORS, middleware
- `backend/app/core/auth.py` - JWT validation, role guards
- `backend/app/core/database.py` - Supabase clients
- `backend/app/api/routes/cases.py` - Case CRUD
- `backend/app/api/routes/admin_routes.py` - Admin operations
- `backend/app/api/routes/analytics_routes.py` - Analytics
- `backend/app/services/llm.py` - LLM fallback chain
- `backend/app/ml/classifier.py` - ML classifier
- `backend/app/ml/enhanced_classifier.py` - Enhanced classifier
- `backend/app/ml/clinical_features.py` - Feature engineering
- `backend/app/models/schemas.py` - Pydantic models

### Frontend (React/Vite)
- `frontend/src/App.jsx` - Main app, routing
- `frontend/src/panels/ASHAPanel.jsx` - ASHA worker view (KNOWN BUG: My Submissions blank)
- `frontend/src/pages/Dashboard.jsx` - Doctor dashboard
- `frontend/src/pages/IntakeForm.jsx` - Case submission
- `frontend/src/api/cases.js` - API wrappers
- `frontend/src/stores/syncStore.js` - Offline sync
- `frontend/src/lib/offlineQueue.js` - IndexedDB queue
- `frontend/src/utils/triageClassifier.js` - ONNX inference
- `frontend/src/hooks/useRealtimeCases.js` - Realtime subscriptions
- `frontend/src/components/NavBar.jsx` - Navigation
- `frontend/src/components/ToastProvider.jsx` - Notifications
- `frontend/src/components/BriefingCard.jsx` - Case cards

---

## INSTRUCTIONS FOR ROUND 3 SPECIALISTS

1. **DO NOT DUPLICATE**: If you find something already listed above, skip it
2. **EXTENSIONS ALLOWED**: If you find a deeper instance or new attack vector for an existing issue, report as "Extension of [FINDING-ID]"
3. **NET-NEW ONLY**: Focus on issues NOT documented above
4. **EXACT EVIDENCE REQUIRED**: Include file:line references with code snippets
5. **MULTI-PASS VALIDATION**: Verify each finding 3 times before reporting

---

*Last Updated: Red Team Round 3 Preparation*
*Total Known Issues: 180*
*Status: Ready for Round 3 Specialist Dispatch*
