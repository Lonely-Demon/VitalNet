# VitalNet — Repository Status and Maintenance Guide

> **Last verified:** 2026-08-22
>
> This document describes the current repository and deployment posture. It is
> the short operational companion to `CODEBASE_MAP.md`, not a replacement for
> the detailed architecture, API, clinical-governance, security, or evaluation
> documents. Historical audit and rebuild documents remain historical records;
> always prefer the current-state documents listed below when making decisions.

## Current status

VitalNet is an offline-first clinical triage decision-support prototype for ASHA community health workers and PHC clinicians in rural India. It is **not clinically validated software** and must not be presented as such.

The approved engineering refinement cycle is complete on `dev`. The current `dev` branch contains the merged review-routing, cross-visit trends, deterministic SBAR handoff, governance-gated paediatric capture, localization-review infrastructure, browser-test harness correction, and documentation closeout work. The preproduction `test` branch contains the verified refinement package for controlled testing.

Agy-owned PR #116 remains a separate, research-only pull request and is intentionally **not** part of the merged `dev` or `test` package. Its synthetic model-contract study must not be treated as production behavior or clinical evidence.

## Architecture and ownership map

| Area | Current source of truth | Current posture |
|---|---|---|
| Live backend | `backend/app/` | Legacy FastAPI backend; remains the live/runtime authority until an explicitly governed cutover |
| Shared clinical logic | `packages/clinical-core/src/` | TypeScript rules, schema, feature engineering, tree evaluator, and citations; consumed by the web app and Edge Function backend |
| Web application | `apps/web/` | React/Vite PWA with offline outbox, role panels, localization, and browser tests |
| Edge Function backend | `apps/api/supabase/functions/api/` | Implemented and tested, but not cut over to production traffic |
| Model training/evaluation | `tools/training/` | Research and engineering tooling; real datasets and reports remain local-only and gitignored |
| Database schema | `backend/supabase/migrations/` | Version-controlled SQL migration source; changes require migration review and drift checks |
| Historical evidence | `docs/security-audits/`, `docs/REBUILD_INSTRUCTIONS.md`, `docs/IMPROVEMENTS.md` | Read-only archaeology; findings require cross-checking against current code |

The production model remains frozen. Do not retrain, tune, alter thresholds, change feature engineering, or hand-edit model artifacts as part of routine repository maintenance.

## Branch and deployment map

| Branch/project | Purpose | Safety boundary |
|---|---|---|
| `dev` | Active engineering and documentation work | Normal development target; current merged refinement baseline |
| `test` | Preproduction staging | Controlled synthetic/non-production testing only; do not use real patient data |
| `main` | Production branch | Do not modify as part of routine development or evaluation work |
| Vercel `vitalnet-preprod` | Preproduction frontend | Associated with the `test` deployment path |
| Vercel `vital-net` | Separate frontend project used for preview/production aliases | Project Root Directory is `apps/web`; its workspace-aware Build Command must build `clinical-core` before the web bundle |
| Render preproduction API | `vitalnet-preprod-api.onrender.com` | Read-only health checks are allowed; no patient submissions without a separately authorized test protocol |

The Vercel project setting and the tracked root `vercel.json` are related but not identical configuration surfaces. If either changes, update the deployment documentation and verify both `vitalnet-preprod` and the relevant preview project. Do not select or trigger Production while repairing Preview/Pre-Production deployments.

The last recorded read-only preproduction checks returned HTTP 200 for the frontend, HTTP 200 with `status: ok` from `/api/health`, and HTTP 200 for the synthetic ASHA CORS preflight. These are historical verification results, not a guarantee of continuous availability.

## Verified engineering baseline

| Verification area | Last recorded result |
|---|---:|
| Synthetic training/evaluation suite | 184 passed |
| Python backend suite | 133 passed |
| Clinical-core suite | 66 passed |
| Localization manifest suite | 2 passed |
| Frontend browser suite | 25/25 passed after PR #128 |
| Clinical-core direct build | Passed |
| Vite production build | Passed |
| Final Preview/Pre-Production Vercel deployment | `READY` on `test` commit `4fdeda6` |

These counts are repository verification evidence, not clinical performance claims. They must be updated whenever the relevant suites or test harnesses change.

## Evaluation and data boundary

No real patient records, credentials, or raw external datasets belong in GitHub, CI logs, issue comments, browser traces, deployment artifacts, or chat. Evaluation datasets and generated reports under `tools/training/data/` and `tools/training/outputs/` are local-only and must remain ignored. Tracked fixtures must be synthetic and must not contain patient-level clinical records.

Public-data source cards, inspection gates, the shadow-evaluation protocol, and safety-remediation studies describe research controls; they do not establish clinical validity. Any future real-data operation requires its own authorization, provenance record, aggregate-only output contract, and explicit stop conditions.

## Governance gates that remain open

The paediatric advisory is disabled by default and requires a qualified clinical-governance decision before activation. Hindi and Tamil resources remain English placeholders marked as not pilot-approved until qualified medical-language review is complete. Any future shadow evaluation requires a named clinical owner, ethics/data-use route, data custodian, rollback plan, incident pathway, and human-escalation capacity decision.

The new Edge Function backend and rules-first mode must not receive production traffic until the clinical review and release gates in `docs/CLINICAL_REVIEW.md`, `docs/CLINICAL_GOVERNANCE.md`, and `docs/evaluation/CLINICAL_GOVERNANCE_PARTNERSHIP_PATHWAY.md` are satisfied.

## Documentation source-of-truth hierarchy

| Question | Use first |
|---|---|
| What exists today? | `CODEBASE_MAP.md` and this document |
| Why was a design chosen? | `docs/DECISIONS.md` |
| What does an endpoint accept/return? | `docs/API_REFERENCE.md` |
| How do I build or test it? | `README.md`, package README, `docs/TESTING_STRATEGY.md` |
| What is safe to change clinically? | `docs/CLINICAL_REVIEW.md`, `docs/CLINICAL_GOVERNANCE.md`, `backend/app/ml/MODEL_CARD.md` |
| What data may be used for evaluation? | `docs/EVALUATION_DATA_BOUNDARY.md` and the relevant source card |
| What happened historically? | `docs/security-audits/`, `docs/REBUILD_INSTRUCTIONS.md`, `docs/IMPROVEMENTS.md` |

When a structural, endpoint, build, test, or deployment change is made, update the relevant current-state documentation in the same change. Do not bulk-rewrite historical audit records merely to make old paths look current.

## Repository hygiene rules

Generated artifacts such as `node_modules/`, package `dist/` directories, Vite output, Playwright reports, pytest caches, local `.env` files, and evaluation outputs are ignored and should be removed from a working checkout when no longer needed. Never remove local real-data files solely to make Git status look clean unless the data owner explicitly requests destruction; the required condition is that they remain outside Git and outside logs.

Before publishing a cleanup change, verify that the worktree is clean except for intended files, no secret-bearing files are tracked, no real-data paths are staged, model artifacts are unchanged, and the change targets `dev` only. Use a short-lived branch and a squash merge for non-trivial cleanup work.
