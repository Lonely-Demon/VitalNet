# Changelog

All notable changes to VitalNet, consolidated across backend, frontend, and
ML. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).
For the ML model's own detailed version history, see
`backend/CLASSIFIER_CHANGELOG.md`. For the *why* behind major entries, see
`docs/DECISIONS.md`.

## [Unreleased] — Round 4: independent validation review + pregnancy-hypertension safety-net rule

A user-run, independent AI validation report ("Clinical AI Validation
Laboratory") claimed 18 critical safety violations. Reviewed and
reproduced each one; 16 were artifacts of a test script using a fabricated
form-data schema, one was a genuine gap now fixed, and the rest are
documented, out-of-scope limitations. Full verdict and reproduced evidence
in `docs/DECISIONS.md` §30.

### Added
- `is_pregnant` intake field (`IntakeForm` schema, `IntakeForm.jsx`
  checkbox shown for `patient_sex === "female"`, Zod validation,
  `phase27_is_pregnant.sql`) gating a new deterministic safety-net rule:
  severe hypertension in pregnancy (BP ≥160/110, or ≥140/90 with a severe
  feature — ACOG Practice Bulletin 222) now always escalates to EMERGENCY,
  mirrored identically in `classifier.py` and `clinicalRules.js`.
- `frontend/tests/safetyNet.test.mjs` — first direct test coverage for
  `safetyNetCheck`/`news2ConcerningVital` (previously only exercised
  indirectly via the tree/feature parity tests), wired into both CI jobs.
- Three new safety-net property tests in `test_classifier_safety.py` for
  the pregnancy rule.
- A "preeclampsia" glossary entry (`docs/GLOSSARY.md`).

### Documented (not fixed — see `docs/DECISIONS.md` §30 for reasoning)
- The trained model's own age/altitude-unaware over-triage tendency
  (a normal infant heart rate, chronic high-altitude SpO2) — recorded in
  `MODEL_CARD.md`'s known limitations; over-triage is the safer direction
  and the correct fix is a synthetic-data/retraining change, not a
  safety-net rule.
- "Temporal blindness" (a single encounter's static snapshot can't see a
  developing trend) — an accurate description of the architecture, partly
  mitigated cross-visit by the existing `deterioration_alert` (§22), not a
  defect to patch.

## Round 3 — supervisor dashboard, outbreak signals, protocol assistant

Built in response to a direct request for a supervisor dashboard, an
outbreak early-warning dashboard, a protocol/guideline lookup assistant,
and a researched (not assumed) decision on the role/access model — plus a
live E2E verification pass against the real Supabase project once it was
built. See `docs/DECISIONS.md` §25-29 for the full reasoning behind each
piece.

### Added
- Fourth role, `supervisor` — facility-scoped, aggregate-only, non-PHI,
  modeled on NHM's real ASHA Facilitator role. `GET /api/supervisor/
  team-metrics` + `SupervisorPanel.jsx`/`TeamMetrics.jsx` (`docs/DECISIONS.md` §25).
- Outbreak early-warning dashboard using CDC's EARS C1 aberration-detection
  method over `case_records.symptoms`. `GET /api/outbreak/signals` +
  `OutbreakSignals.jsx`, shared across Doctor/Supervisor/Admin panels.
  Framed explicitly as informational, not a validated surveillance system
  (`docs/DECISIONS.md` §26).
- Protocol/guideline lookup assistant, informed by ASHABot's own published
  design (Khushi Baby + Microsoft Research India, CHI 2025) — grounded via
  context-stuffed `protocol_knowledge.md`, refuses patient-specific
  questions, and replaces ASHABot's too-slow (~60h average) synchronous
  consensus with async curation. New `protocol_questions` table (real
  Postgres RLS, not the `supabase_admin` exception — this table has no
  PHI). `POST /api/protocol/ask`, `GET .../questions`, `PATCH
  .../curate` + `ProtocolAssistant.jsx` across all four panels
  (`docs/DECISIONS.md` §27).
- `app/core/scoping.py::resolve_facility_scope` — shared facility-scoping
  helper for the two new aggregate-only routers.
- Two GitHub Actions keep-alive workflows for the free-tier deployment
  reality: `supabase-keepalive.yml` (prevents the 7-day pause) and
  `backend-keepalive.yml` (mitigates free-host cold starts, explicitly
  documented as best-effort — see `docs/DECISIONS.md` §28).
- `phase25_protocol_questions.sql`, `phase26_role_check_constraint.sql`.

### Fixed
- Resolved all 10 open Dependabot PRs — merged what was safe (slowapi,
  skl2onnx, json-repair, GitHub Actions SHA pins, vite 8/@vitejs/plugin-react 6),
  explicitly rejected two with documented reasoning (httpx 0.28 conflicts
  with the pinned `supabase==2.10.0`; numpy 2.5.x requires Python ≥3.12,
  breaking the documented 3.11+ local-dev floor).
- `NavBar.jsx` had no label/color entry for the `supervisor` role at all
  (would have rendered a blank badge) — found while wiring the new role.
- An untracked `profiles_role_check` CHECK constraint on the live
  Supabase project silently rejected `'supervisor'` — not present in any
  tracked migration, added directly against the project at some point
  outside version control. Found and fixed during live E2E verification
  (`docs/DECISIONS.md` §29); the live project also turned out to be ten
  migrations behind (stuck since before `phase16`).
- `ASHAPanel.jsx`'s "My Submissions" tab crashed (`TypeError:
  submissions.map is not a function`) for any ASHA worker with real
  submission history — `getMySubmissions()` returns the cursor-paginated
  `{ cases, hasMore, ... }` wrapper, not a bare array. Pre-existing,
  unrelated to the round-3 features; found only by driving a real browser
  against a real backend response (`docs/DECISIONS.md` §29).

## Round 2 — Enterprise-grade hardening

Autonomously-buildable subset of a broader enterprise-readiness roadmap —
everything that didn't require a human decision, external credential, or
organizational commitment. See `docs/CLINICAL_GOVERNANCE.md` and
`docs/COMPLIANCE_DPDP.md` for what's explicitly *not* included and why
(regulatory classification, DPO/grievance-officer designation, real-data
validation — all genuinely require a human/organization, not code).

### Added
- `docs/CLINICAL_GOVERNANCE.md` — regulatory posture against India's CDSCO
  Draft Guidance on Medical Device Software (Oct 2025), the five-layer
  guardrail architecture, model lifecycle governance.
- `docs/COMPLIANCE_DPDP.md` — full DPDP Act 2023 data-principal-rights
  mapping, with an honest list of what's an organizational/legal gap.
- DPDP data-subject-request lifecycle: `GET/POST /api/admin/cases/{id}
  /export|erase` and `POST /api/admin/cases/purge-expired` (retention
  sweep, external-scheduler-driven, disabled by default).
- Offline-emergency SMS facility-alert (`EmergencySmsAlert.jsx`) — closes
  a real gap versus the original design intent: an `sms:` URI intent with
  a fixed, PHI-free workflow-ping message, shown when an ASHA worker is
  offline and the on-device triage is EMERGENCY.
- Server-side Groq Whisper voice transcription (`POST
  /api/voice/transcribe`) — closes the other real original-intent gap:
  the browser's SpeechRecognition was always meant to be a UX-layer
  convenience, not the clinical transcription accuracy layer. Falls back
  to the browser path only if the server call fails.
- `backend/scripts/fairness_audit.py` and `drift_monitor.py` — operator-run
  ML diagnostics (subgroup performance, feature-distribution drift),
  explicit about being synthetic-data checks, not real-world audits.
- CI: a push-only `sbom` job generating a CycloneDX SBOM for backend and
  frontend dependencies.
- `docs/INCIDENT_RESPONSE.md` — security incident runbook (detection
  through post-incident review, DPDP breach-notification hook).
- `backend/scripts/load_test.py` — lightweight asyncio+httpx load
  generator, refuses to target anything but localhost without an explicit
  confirmation flag.
- `docs/ACCESSIBILITY.md` and a WCAG 2.1 AA pass: form-label association
  (previously visual-only, not programmatic, across the app's most-used
  screens), fieldset/legend grouping, `role="status" aria-live="polite"`
  on toasts/offline banner, and corrected color-contrast tokens
  (`--color-text3`, `--color-urgent`) that were failing AA.
- `docs/SLO.md` and `GET /api/metrics` (Prometheus text format, admin-only)
  — HTTP request/latency/error metrics and a triage-classification counter.

### Changed
- `test_admin_authz.py` generalized to scan every admin-only route module
  (`admin_routes`, `dsr_routes`, `metrics_routes`), not just one, so the
  require_role('admin')-only invariant keeps covering new admin surfaces
  automatically.

## Documentation overhaul

### Added
- `docs/API_REFERENCE.md` — complete endpoint-by-endpoint reference.
- `docs/DECISIONS.md` — consolidated architecture decision log (ADR-style).
- `docs/TESTING_STRATEGY.md`, `docs/SECURITY.md`, `docs/GLOSSARY.md`,
  `docs/ONBOARDING.md` — new dedicated reference docs.
- `CONTRIBUTING.md` — branch strategy, PR process, commit conventions.
- `backend/README.md`, `frontend/README.md` — subproject quick-start entry points.
- Mermaid architecture/sequence/ER/auth-flow diagrams in `CODEBASE_MAP.md`.

### Changed
- `CODEBASE_MAP.md`, `README.md`, `AGENTS.md` refreshed to reflect the
  current pytest suite, the Tier 2/3 feature set, and the git branch
  workflow.

## Tier 3 — SMS/photo-attachment scaffolding

### Added
- `app/services/sms.py` — SMS-fallback gateway interface + strict inbound
  parser (FEATURES_ROADMAP §3.1). No live webhook — vendor decision pending.
- `case_attachments` schema (`phase20_case_attachments.sql`) +
  `frontend/src/utils/imageCompression.js` (FEATURES_ROADMAP §3.2). No live
  upload endpoint — storage/consent decision pending.

## Tier 2 — i18n, voice-to-text, referral workflow

### Added
- `react-i18next` infrastructure, language switcher, fully wired on
  `IntakeForm.jsx` (FEATURES_ROADMAP §2.1). Hindi/Tamil are placeholder
  translations pending clinician review (`docs/DECISIONS.md` §10).
- Browser-native voice-to-text on intake free-text fields, gated on
  connectivity (§2.2).
- Inter-facility referral workflow: `referrals` table + RLS, referral
  create/list/status-advance endpoints, `ReferralsPanel.jsx` (§2.3).

### Fixed
- CodeQL suppression comments updated from the legacy `lgtm[query-id]`
  syntax to the current `codeql[query-id]` syntax (`docs/DECISIONS.md` §13).
- Golden-vector ML parity tests now freeze the clock — `time_of_day_risk`/
  `seasonal_risk` had made the fixture flaky across real time-of-day
  boundaries (`docs/DECISIONS.md` §12).

## Tier 1 / 1b — Web Push, outcome loop, analytics, admin bulk import

### Added
- Web Push notifications for EMERGENCY cases + unreviewed-case re-alert
  (external-scheduler-driven).
- Doctor triage-override + case-outcome recording (real-label source for
  retraining).
- `scripts/retrain_from_outcomes.py` — human-gated retraining pipeline
  blending real outcomes with synthetic data; never auto-deploys.
- Response-time SLA dashboard, ML/doctor agreement-rate analytics, case CSV
  export.
- Admin CSV bulk user onboarding (`POST /api/admin/users/bulk`) with
  per-row failure isolation.
- Admin PHI audit-log viewer.
- Golden-vector feature-engineering parity test (`test_feature_parity.py` /
  `featureParity.test.mjs`) — caught a real bug (newborns mis-scored as
  adults in the offline-only path) during development.
- Version-controlled Supabase migrations (`backend/supabase/migrations/`)
  as the canonical schema source going forward.

## Round 2/3 hardening — hybrid auth, pure-JS offline engine, ML safety layers

### Added
- Hybrid JWT verification (local signature check + network fallback +
  short-TTL revocation recheck), replacing a per-request Supabase network
  round-trip (`docs/DECISIONS.md` §1).
- Pure-JS offline tree evaluator, replacing `onnxruntime-web` (~12 MB WASM
  removed entirely) — `docs/DECISIONS.md` §2.
- Deterministic safety-net escalation + NEWS2 concerning-vital floor +
  `low_confidence` abstention flag on the unified ML model
  (`docs/DECISIONS.md` §3).
- SHAP-based real feature-attribution explanations replacing a
  hand-written heuristic.
- Security headers, structured JSON logging with correlation IDs,
  CSRF/device-guard middleware, PHI audit logging.
- Model card (`backend/app/ml/MODEL_CARD.md`) — honest metrics,
  limitations, and validation status.

### Fixed
- A startup-crashing ML model load bug (scikit-learn version
  incompatibility with a committed `.pkl`) — led to exact-version pinning
  for `scikit-learn`/`shap`.
- An IDOR and a dead-role-scoping bug found during a structured Red Team
  audit (see `docs/security-audits/` for the historical findings register).
- Consolidated a 4-sub-model ensemble classifier into one unified,
  exportable model (see `backend/CLASSIFIER_CHANGELOG.md` for the full
  retirement rationale).

### Removed
- `onnxruntime-web` dependency and its ~12 MB WASM binary from the
  frontend bundle.
- The retired multi-model ensemble classifier and its associated training
  scripts.

## Repository restructuring

### Changed
- Consolidated to exactly three long-lived branches: `main`, `dev`, `test`
  (`docs/DECISIONS.md` §9). `dev` is the active development line.
- Fixed all flagged Dependabot vulnerabilities (backend pip + frontend npm).
- Removed ~700KB of superseded historical planning documentation
  (`Context/`), relocated historical hardening-phase execution logs into
  `docs/`, removed an unused backend dependency (`python-multipart`).

## Early development — 24-hour sprint through Phase 10 rebuild

The original build-out, prior to the hardening phases above. Historical
detail (largely superseded by current docs, kept for archaeology) lives in
`docs/ARCHITECTURE_RESTRUCTURE.md`, `docs/REBUILD_INSTRUCTIONS.md`,
`docs/IMPROVEMENTS.md`, and `docs/security-audits/`.

### Added
- Initial FastAPI + React PWA scaffold, Supabase integration, offline-first
  intake queue, real-time doctor dashboard, LLM briefing generation.
