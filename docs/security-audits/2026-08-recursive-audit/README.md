# VitalNet Recursive Adversarial Audit — 2026-08

> **Status:** In progress (10-cycle deep read-only audit)
> **Auditor:** Mavis (MiniMax Code root session)
> **Date:** 2026-08-29
> **Scope:** Entire repository at `D:\Southern_Ring_Nebula\VitalNet` (commit `7a91639`).
> **Method:** Recursive read-only inspection of source, configuration, tests, infra, and
> data layers. Builds on but is independent from the March 2026 red-team exercise
> (`docs/security-audits/2026-03-red-team/`). Findings are organised by audit cycle.

## Severity legend

| Tag              | Meaning                                                                                            |
|------------------|----------------------------------------------------------------------------------------------------|
| **CRITICAL**     | Direct path to PHI exposure, account takeover, integrity loss, RCE, or patient-harm misclassification. |
| **HIGH**         | Privilege escalation, broken access control, ML safety regression, supply-chain compromise, RLS bypass. |
| **MEDIUM**       | Auth/AuthZ weak default, DoS, partial information disclosure, ML robustness gap, secret-hygiene.     |
| **LOW**          | Defensive-in-depth gap, ergonomics bug, lint/test hygiene, maintainability-driven security risk.     |
| **INFO**         | Note / observation worth recording but not a defect.                                                |

Each finding has a stable ID `VN-2026-08-C{c}-{nn}` and a per-finding file under
`docs/security-audits/2026-08-recursive-audit/findings/`.

## Cycle index

| Cycle | Theme                                          | Status        |
|-------|------------------------------------------------|---------------|
| 1     | Repo shape, attack surface map                 | completed     |
| 2     | Backend Python/FastAPI: auth, input, secrets   | completed     |
| 3     | Supabase RLS, migrations, RPC contracts        | completed     |
| 4     | Frontend (apps/web): XSS, CSRF, PII, token     | completed     |
| 5     | apps/api (Deno/Hono): endpoints, CORS, schema  | completed     |
| 6     | clinical-core: rules engine, feature safety    | completed     |
| 7     | ML pipeline: training, models, SHAP, deps      | completed     |
| 8     | Supply chain, CI/CD, build, infra, secrets      | completed     |
| 9     | Error handling, logging, PII, DoS, rate-limit  | completed     |
| 10    | Cross-cutting + final consolidated report      | completed     |
| 11    | Verification pass: re-validate, find new       | completed     |

## Verification pass (2026-08-29)

After the original 10-cycle audit, an independent verification pass
re-validated every finding against the current code. Results:

- 37 of 38 findings confirmed valid (1 false positive: `C2-05`).
- 8 new findings discovered (VER-01 through VER-08).
- 3 of the new findings are CRITICAL: VER-01 (DSR cross-tenant
  IDOR), VER-06 (untracked permissive INSERT policy on live DB),
  VER-07 (live DB still has `user_metadata` RLS policies phase32
  was supposed to drop).

See [MASTER_REPORT.md](MASTER_REPORT.md) §"Verification pass" for
the full writeup and 3 new chained attacks (G, H, I).
