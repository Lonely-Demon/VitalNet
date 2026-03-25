# VitalNet Operational Status Briefing
**Date:** 2026-03-23
**Classification:** Internal Engineering Brief
**Prepared For:** Project Leads, Technical Review Board, Collaborators
**Repository Head (local main):** `71e407cd3b937c7cd4a9458ae5f6ad75568cd5b2`

---

## 1. Executive Summary

VitalNet is an end-to-end, role-based clinical triage platform operating across three user groups: ASHA worker, doctor, and admin. The system is currently in a late-stage Phase 10 posture with core mission capability online:

1. Structured intake from ASHA workers.
2. Server-side triage plus LLM briefing generation.
3. Doctor-facing prioritized queue with realtime updates.
4. Admin controls for users/facilities and analytics views.
5. Offline-first field operation via queueing and local ONNX triage.

The codebase is functionally mature for pilot workflows. Remaining work is primarily hardening, verification closure, and operational safeguards rather than foundational feature build-out.

---

## 2. Mission Profile and Operational Intent

### 2.1 Mission Statement
Enable frontline ASHA workers to capture standardized patient data and transmit triage-grade intelligence to doctors before patient arrival.

### 2.2 Primary Operational Flow

`ASHA intake -> FastAPI validation -> ML triage -> LLM briefing -> Supabase write -> Doctor review queue`

### 2.3 Secondary Operational Flows

1. **Offline field operation:** Queue submission in IndexedDB when disconnected, sync on reconnect.
2. **Realtime command visibility:** New case events flow into doctor/admin views through Supabase Realtime.
3. **Administrative governance:** User/facility lifecycle management and aggregate metrics.

### 2.4 Expert-Novice Gap Resolution (Strategic Design Choice)

VitalNet intentionally routes AI-generated reasoning to the clinical expert (doctor), not the frontline data collector (ASHA worker). This is a deliberate architecture choice documented in the RnD and developer context materials.

1. ASHA role: structured data capture.
2. Doctor role: interpret AI briefing in context and make clinical decisions.
3. System role: maintain explainable, auditable, non-diagnostic decision support.

This separation reduces misuse risk and is central to real-world adoption viability.

---

## 3. Current Capability Inventory

## 3.1 Backend API Capability

### Core Clinical Endpoints

1. `GET /api/health`
2. `POST /api/submit` (role-gated: ASHA/Admin)
3. `GET /api/cases` (role-gated: Doctor/Admin)
4. `PATCH /api/cases/{case_id}/review` (role-gated: Doctor/Admin)
5. `GET /api/cases/mine` (role-gated: ASHA/Admin)

### Administrative Endpoints (`/api/admin/*`)

1. User list/create/update/deactivate/reactivate
2. Facility list/create/toggle
3. System summary stats

### Analytics Endpoints (`/api/analytics/*`)

1. `GET /summary` - triage distribution, reviewed/unreviewed, daily volume, top submitters
2. `GET /emergency-rate` - weekly emergency trend over rolling window

## 3.2 Authentication and Authorization

1. JWT bearer extraction and validation through Supabase `get_user`.
2. Role guard dependency (`require_role`) enforced per endpoint.
3. Multi-client data access pattern:
   - anon client for public-safe reads,
   - user-scoped RLS client for normal data operations,
   - service-role admin client for privileged auth/admin operations.

## 3.3 Machine Intelligence Layer

1. Runtime classifier loading on service lifespan startup.
2. Enhanced clinical feature engineering pipeline (~45 engineered features).
3. Server-side triage with confidence and risk-driver output.
4. LLM briefing generation (Groq-backed) with classifier-driven triage integrity.

### 3.3.1 LLM Reliability and Fallback Posture

Context documents define a multi-tier fallback strategy and explicit failure-mode handling:

1. Primary clinical reasoning model path with strict schema constraints.
2. Alternate model fallback chain for rate limit/availability scenarios.
3. Triage classification remains independent of LLM availability.
4. Mandatory uncertainty output to prevent false certainty on sparse data.

## 3.4 Offline and Edge Intelligence

1. ONNX model served to frontend for local inference.
2. `useLocalTriage` hook for immediate client-side triage signal.
3. IndexedDB queue for offline submissions.
4. Queue processing on startup and on `online` events.
5. Workbox/PWA integration with background sync posture.

### 3.4.1 Offline Authentication Contract

Per Phase 6 architecture guidance, offline behavior depends on cached auth/session continuity:

1. Initial login requires connectivity.
2. Access and refresh token lifecycle is managed by Supabase session handling.
3. Queue sync requires valid session refresh when connectivity returns.
4. Backend JWT validation path is designed to preserve role-based enforcement across reconnect/sync operations.

### 3.4.2 ONNX Offline Limitation (Two-Stage Reveal)

Per Phase 9 guidance, ONNX conversion provides classifier inference only; full SHAP-style explanatory output does not run offline in-browser.

1. **Offline immediate output:** triage badge.
2. **Post-sync authoritative output:** full server-side briefing and richer explanation context.

## 3.5 Realtime Operations

1. Shared realtime subscription hook (`useRealtimeCases`).
2. INSERT/UPDATE event handling for doctor dashboard and ASHA history updates.
3. Facility/user-scoped event filters applied at subscription level.

## 3.6 Frontend Role Panels

1. **ASHA Panel:** New case + My submissions.
2. **Doctor Panel:** Pending review + all cases.
3. **Admin Panel:** Analytics + users + facilities + system.
4. **App-level route gating:** role-to-panel mapping plus deactivated-user lockout.

---

## 4. Implementation Dissection (Code-Level)

## 4.1 Backend Dissection

### 4.1.1 Service Bootstrap

`backend/main.py` uses lifespan boot to load classifier and expose health telemetry. CORS is constrained to localhost/dev plus configured frontend URL.

### 4.1.2 Submission Path

`POST /api/submit` sequence:

1. Validate request through `IntakeForm` schema (`backend/schemas.py`).
2. Run triage through classifier stack (`backend/classifier.py`).
3. Generate clinical briefing (`backend/llm.py`).
4. Persist structured record to `case_records` via user-scoped Supabase client.

This path preserves deterministic triage while allowing LLM enrichment.

### 4.1.3 Access Control Model

`backend/auth.py` enforces bearer token presence and role compliance. Role extraction checks both `user_metadata` and `app_metadata`, improving resilience across metadata propagation variations.

### 4.1.4 Admin and Analytics Segmentation

Operational control surfaces are separated into dedicated routers (`admin_routes.py`, `analytics_routes.py`) and mounted centrally. This supports clear blast-radius control and testable module boundaries.

## 4.2 Intelligence and Feature Engineering Dissection

### 4.2.1 Feature Engineering

`backend/clinical_features.py` transforms raw intake into clinically meaningful engineered features spanning:

1. Baseline vitals/symptom indicators
2. Derived hemodynamic/respiratory signals
3. Interaction terms
4. Age-stratified risk adjustments
5. Contextual risk proxies

### 4.2.2 Training and Export Toolchain

Scripts under `backend/scripts/` support retrain/export workflows. ONNX export bridges backend model representation to frontend runtime inference.

### 4.2.3 Explainability/Reasoning Envelope

System returns risk-driver style outputs and confidence metadata. This supports operator trust and downstream prioritization decisions.

## 4.3 Frontend Dissection

### 4.3.1 App Orchestration

`frontend/src/App.jsx` executes role-based panel routing under `AuthProvider`, `ToastProvider`, and `RouteGuard`, including account deactivation handling.

### 4.3.2 ASHA Workflow

`frontend/src/pages/IntakeForm.jsx`:

1. Captures patient data including patient name.
2. Executes local ONNX triage pre-submit when model is ready.
3. Submits to API or queues offline payload.
4. Presents immediate local status to user.

`frontend/src/panels/ASHAPanel.jsx` now includes pending-sync visibility by merging queued local rows with server-backed history.

### 4.3.3 Doctor Workflow

`frontend/src/pages/Dashboard.jsx`:

1. Fetches case list.
2. Applies priority ordering (Emergency/Urgent/Routine).
3. Handles realtime inserts/updates.
4. Includes client-side search over patient name and complaint.

### 4.3.4 Admin Workflow

Admin views support user/facility lifecycle operations and separate analytics/system visibility. Placeholder messaging has been updated to reflect live analytics availability.

## 4.4 Offline, PWA, and Realtime Dissection

### 4.4.1 Offline Queue

`frontend/src/lib/offlineQueue.js` provides durable IndexedDB storage with queue-change event broadcasts.

### 4.4.2 Sync Engine

`frontend/src/lib/api.js` `processQueue()` drains queue using refreshed auth session token and handles conflict/validation outcomes.

### 4.4.3 Realtime Subscriptions

`frontend/src/hooks/useRealtimeCases.js` creates scoped subscriptions for INSERT/UPDATE on `case_records` with safe cleanup semantics.

### 4.4.4 PWA Envelope

`frontend/vite.config.js` integrates plugin-driven service worker behavior and offline assets, including model artifact caching.

---

## 5. Security Posture

## 5.1 Strengths

1. Endpoint-level role gating with explicit dependencies.
2. RLS-aware user-scoped DB client usage.
3. Separation of service-role admin client from normal user data path.
4. JWT cryptographic validation delegated to Supabase auth service.

## 5.2 Key Risks

1. Service role key exposure remains catastrophic risk if mishandled.
2. JWT/metadata policy coupling requires consistent Supabase auth hook behavior.
3. LLM dependency introduces external-rate-limit and response-availability risk.
4. Realtime setup correctness depends on SQL publication/replica identity config.

## 5.3 Five-Layer Safety Guardrails (Context-Derived)

The Context documents define a layered safety model that complements code-level controls:

1. Input validation guardrail (schema-bound intake).
2. LLM-independent triage guardrail (classification not delegated to LLM).
3. Mandatory uncertainty signaling guardrail.
4. Non-removable clinical disclaimer guardrail.
5. Accountability-separation guardrail (ASHA capture vs doctor judgment).

These layers are important for both safety communication and regulatory posture.

---

## 6. Data and Persistence Model

Primary persistence is Supabase Postgres with RLS controls. Core entity axis:

1. `facilities`
2. `profiles`
3. `case_records`

Case records hold clinical payload, triage result, briefing payload, review metadata, and offline sync identifiers (`client_id`, client timestamp).

## 6.1 Three-Client Supabase Access Pattern

Phase 6 and Phase 7 architecture instructions emphasize strict separation of database clients:

1. **Anon client:** low-privilege/public-safe reads.
2. **Per-request user-scoped client:** RLS-enforced data path.
3. **Service-role admin client:** reserved for privileged admin/auth operations only.

This separation is a critical security boundary and should remain non-negotiable.

---

## 7. Testing and Verification Posture

Available backend tests/scripts include direct classifier checks and e2e-style scripts, plus Phase 10 verification checklist artifacts. Build verification has recently succeeded for frontend after dependency alignment.

Current maturity: **operationally capable, verification closure still required for full release confidence**.

## 7.1 Phase 10 Verification Blockers (Checklist Alignment)

`PHASE10_VERIFICATION.md` indicates remaining validation burden in four categories:

1. Realtime SQL enablement and verification queries.
2. Frontend realtime behavior under live inserts/updates and offline reconnect.
3. Analytics endpoint scoping/accuracy checks by role.
4. Performance/robustness checks (subscription cleanup, event loop behavior, API refetch thresholds).

Release confidence should be considered incomplete until checklist closure is explicitly recorded.

---

## 8. Current Repository State

## 8.1 Branch/Commit Position

Local `main` is aligned with latest fetched collaborator commit from this session (`71e407c...`).

## 8.2 Working Tree Delta (Uncommitted)

At report generation time, the following files contain local modifications from active implementation work:

1. `frontend/src/pages/Dashboard.jsx`
2. `frontend/src/panels/ASHAPanel.jsx`
3. `frontend/src/components/admin/AdminStats.jsx`

These changes improve Phase 10 usability and visibility:

1. Doctor search/filter capability.
2. ASHA pending-sync status exposure.
3. Admin stats copy alignment with live analytics tab.

---

## 9. Capability Readiness Matrix

| Domain | Status | Notes |
|---|---|---|
| Core submission pipeline | GREEN | End-to-end active |
| Role-based access control | GREEN | Enforced in API dependencies |
| Offline queueing | GREEN | IndexedDB + sync path active |
| Local ONNX triage | GREEN | Hooked into intake flow |
| Realtime doctor updates | GREEN | Subscription path integrated |
| Admin user/facility management | GREEN | CRUD/toggle endpoints and views active |
| Analytics visibility | GREEN/AMBER | Live analytics exists; harmonization/verification still useful |
| Release verification checklist closure | AMBER | Requires disciplined execution pass |
| Security hardening/compliance envelope | AMBER | Key management and audit depth remain priorities |

---

## 10. Commander's Assessment

VitalNet has crossed the threshold from prototype-only functionality to a coordinated operational system with resilient field workflows, role governance, and near-realtime command visibility. The architecture is coherent and implementation depth is substantial.

Primary remaining burden is not feature invention but **operational hardening and formal verification**:

1. Execute full verification checklist end-to-end.
2. Lock environment/key handling procedures.
3. Close remaining analytics/realtime edge-case tests.
4. Stabilize release process for retrain/export/deploy cadence.

With those actions completed, the project is positioned for controlled pilot deployment.

---

## 11. Adoption Pathway and Policy Dependency

The RnD context documents describe a two-step adoption reality:

1. **Phase 1 adoption:** voluntary operational usage where immediate workflow value is clear.
2. **Phase 2 scale adoption:** policy-level integration with public health reporting and incentive structures.

This means technical readiness alone does not guarantee system-wide uptake. Government/program integration is a strategic dependency.

---

## Appendix A - Key Files for Rapid Orientation

1. `backend/main.py`
2. `backend/auth.py`
3. `backend/classifier.py`
4. `backend/clinical_features.py`
5. `backend/enhanced_classifier.py`
6. `backend/admin_routes.py`
7. `backend/analytics_routes.py`
8. `frontend/src/App.jsx`
9. `frontend/src/pages/IntakeForm.jsx`
10. `frontend/src/pages/Dashboard.jsx`
11. `frontend/src/panels/ASHAPanel.jsx`
12. `frontend/src/panels/AdminPanel.jsx`
13. `frontend/src/hooks/useRealtimeCases.js`
14. `frontend/src/lib/api.js`
15. `frontend/src/lib/offlineQueue.js`
16. `frontend/src/utils/triageClassifier.js`
17. `frontend/vite.config.js`
18. `PHASE10_VERIFICATION.md`

## Appendix B - Historical Failure Lessons (From Progress Report)

Development history documents five high-impact issues that are now known traps:

1. NumPy/Windows compatibility failures at specific version combinations.
2. Pickle payload key mismatches between training/export and runtime assumptions.
3. Windows terminal encoding instability with non-ASCII log output.
4. SHAP multi-class limitations requiring fallback explainability strategy.
5. Sentinel-value-driven false emergency classifications requiring clinically safe missing-data handling.

These lessons should be treated as persistent engineering memory during future refactors.
