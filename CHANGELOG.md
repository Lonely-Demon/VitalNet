# Changelog

All notable changes to VitalNet, consolidated across backend, frontend, and
ML. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).
For the ML model's own detailed version history, see
`backend/CLASSIFIER_CHANGELOG.md`. For the *why* behind major entries, see
`docs/DECISIONS.md`.

## [Unreleased] — Documentation overhaul

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
