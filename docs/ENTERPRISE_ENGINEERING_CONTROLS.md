# VitalNet Enterprise Engineering Controls

**Status:** Implemented control baseline for `dev`
**Scope:** Repository, build, release, runtime, offline data, evaluation tooling, and operational governance
**Clinical boundary:** This document does not declare clinical validation and does not authorize a production model, threshold, or workflow change.

## Purpose

Enterprise-grade engineering is a control system around the product. The objective is not merely to make source code elegant; it is to make unsafe changes difficult to introduce, visible when they occur, blocked before release, observable at runtime, recoverable after failure, and traceable afterward. This document turns that idea into repository-enforceable controls for VitalNet.

The framework follows the lifecycle orientation of the NIST Secure Software Development Framework, the governance and measurement orientation of the NIST AI Risk Management Framework, the artifact-integrity focus of SLSA, the quality dimensions of ISO/IEC 25010, and the reliability principles of SRE. These references guide engineering controls; they do not substitute for qualified clinical governance or clinical validation. [1] [2] [3] [4] [5]

## Control model

| Control layer | Failure it prevents | VitalNet implementation | Enforcement state |
|---|---|---|---|
| Change integrity | Unreviewed or unsafe code reaches a branch | Protected branch workflow, CODEOWNERS for clinical surfaces, dev-only remediation branches, explicit no-production boundary | Enforced by repository process; clinical reviewer still required for clinical changes |
| CI trust | A mutable action or unreviewed build tool executes in CI | Full-SHA GitHub Action pins, `tools/ci/check_action_pins.py`, pinned SBOM CLI, no-secrets PR jobs | Machine-enforced on pull requests |
| Dependency integrity | Known vulnerable transitive packages remain in the web graph | pnpm overrides, committed lockfile, pnpm audit gate, Dependabot | Machine-checked; Deno ecosystem requires manual cadence |
| Python supply chain | New runtime or training vulnerabilities go unnoticed | `pip-audit` pull-request gate with one documented, verification-only ecdsa exception | Machine-checked; exception must remain justified |
| Build transparency | The artifact cannot be reconstructed or inventoried | CycloneDX backend/frontend SBOM artifact, frozen model hash, explicit build commands | Push artifact and retraining guard |
| Authentication boundary | Internal verifier or upstream details leak to clients | Fixed generic 401 response, server-side exception logging, profile-based role resolution | Unit-tested |
| Authorization boundary | A valid identity receives data outside role/facility scope | FastAPI role and facility checks, RLS, Edge `requireRole`, admin-route tests | Existing tests plus parity review |
| Offline PHI lifecycle | One worker sees another worker’s data, or data is orphaned forever | Owner-scoped outbox, ownerless legacy recovery state, aggregate-only UI, explicit stale-row review/purge | Browser and unit regression coverage |
| Evaluation isolation | External data or outputs alter production behavior | Inspection/scoring gates, local-only data directories, frozen production model, candidate-only retraining | Existing evaluation guards plus model hash gate |
| Parser safety | Malicious external workbook triggers unsafe XML behavior | `defusedxml` at KTAS OpenXML boundaries, streaming rows, fail-closed schema | Dependency and parser control |
| Runtime resilience | Abuse protection disappears during an infrastructure fault | Edge rate limiter fails closed; trusted proxy headers opt-in only | Implemented in non-live Edge backend |
| Release governance | A technically green build is mistaken for clinical approval | `dev`/`test`/production separation, deployment runbook, clinical-review gates, no automatic promotion | Process-enforced; clinical ownership remains external |
| Evidence and recovery | Incidents cannot be reconstructed or reversed | Correlation IDs, PHI audit log, SBOMs, changelog, decision log, rollback runbook | Existing operational controls |

## Non-negotiable invariants

The following invariants apply to every pull request and release candidate:

1. The production classifier artifact remains frozen unless a separately governed model-change process is approved. A candidate model is written to a separate path and cannot overwrite `triage_classifier.pkl` through the retraining utility.
2. Clinical thresholds, tier mappings, feature engineering, intake schema, and escalation policy are not changed by security or maintainability work.
3. No real patient data, external patient-level records, predictions, hashes of patient records, credentials, or generated evaluation reports are committed to Git, CI artifacts, logs, chat, or cloud APIs.
4. `dev` is the only branch permitted for this remediation program. No change is promoted to `test`, `main`, production Render, production Vercel, or production Supabase by this work.
5. An ownerless legacy offline row is never submitted under a later authenticated worker. It becomes non-submittable recovery state until explicitly purged.
6. Security controls fail closed when continuing would silently remove authentication, authorization, rate limiting, or data-boundary protection.
7. Engineering diagnostics, model metrics, and synthetic or proxy-label results are never presented as clinical validation or clinical acceptance.

## Pull-request gates

A safe pull request should pass the following gates before merge to `dev`:

| Gate | Command or check | Required result |
|---|---|---|
| Action integrity | `python tools/ci/check_action_pins.py` | Every remote action uses a full commit SHA |
| JavaScript dependency integrity | `pnpm audit` | Zero known advisories in the locked graph |
| Python dependency integrity | `pip-audit --strict ... --ignore-vuln GHSA-wj6h-64fc-37mp` | No new findings beyond the documented exception |
| Formatting | `git diff --check` | No whitespace errors |
| Backend behavior | `python -m pytest backend/tests/ --ignore=backend/tests/test_e2e.py` | All synthetic/unit tests pass |
| Evaluation boundary | `python -m pytest tools/training/tests/` | All safety, synthetic, parser, and gate tests pass |
| Shared clinical package | `pnpm --filter @vitalnet/clinical-core test` | All shared-contract tests pass |
| Frontend build | `pnpm --filter @vitalnet/web run build` | Production build succeeds with placeholder/test configuration |
| Browser safety | `pnpm --filter @vitalnet/web exec playwright test tests/offline.spec.js tests/offline-migration.spec.js` | Offline and migration flows pass using synthetic mocks |
| Edge contract | `deno fmt --check .`, `deno lint .`, `deno test --allow-net --allow-env` | All Edge checks pass; no production cutover implied |

A known unrelated baseline check may remain non-blocking only when it is documented in the repository status and the change does not alter the affected deployment configuration.

## Release and promotion gates

A green CI run is an engineering prerequisite, not clinical authorization. Promotion from `dev` to `test` requires a clean branch comparison, the deployment runbook, a preproduction smoke check, and confirmation that no model or clinical contract changed. Promotion beyond `test` is outside this remediation scope and requires separate governance ownership.

The Edge Function remains non-live until its authentication, RLS, rate-limit, audit, clinical parity, observability, and rollback gates are separately accepted. The live endpoint map therefore remains authoritative for deciding which backend serves traffic.

## Exception handling

An exception must be explicit, narrow, time-bounded, and documented with an owner and removal condition. The current Python dependency exception is limited to `GHSA-wj6h-64fc-37mp` because the advisory concerns ECDSA signing and key generation, while VitalNet uses the transitive package only through JWT verification; the advisory has no upstream fix. Any future use of the package for signing, key generation, or ECDH invalidates this exception and blocks release until the dependency design changes.

No CodeQL suppression, dependency exception, clinical threshold exception, or production-boundary exception may be introduced merely to make CI green.

## Remaining governance dependencies

Engineering controls can make unsafe software changes harder to introduce, but they cannot manufacture clinical authority. VitalNet still needs qualified clinical review for clinical acceptance criteria, paediatric activation, language validation, shadow-evaluation ownership, and any production-facing model or workflow change. Until those dependencies exist, the correct product posture remains **research prototype / decision-support prototype, not clinically validated software**.

## References

[1]: https://csrc.nist.gov/pubs/sp/800/218/final "NIST Secure Software Development Framework (SSDF)"

[2]: https://www.nist.gov/itl/ai-risk-management-framework "NIST AI Risk Management Framework"

[3]: https://slsa.dev/ "SLSA: Supply-chain Levels for Software Artifacts"

[4]: https://www.iso.org/obp/ui/#iso:std:iso-iec:25010:ed-2:v1:en "ISO/IEC 25010 Software Product Quality Model"

[5]: https://sre.google/sre-book/part-II-principles/ "Google SRE Principles"
