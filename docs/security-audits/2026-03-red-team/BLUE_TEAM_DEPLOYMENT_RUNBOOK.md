# Blue Team Deployment Runbook

This runbook deploys the Blue Team remediation program for all findings from R1, R2, and R3.

## Generated Inputs

- `R1_R2_FINDING_REGISTER.json`
- `ROUND3-FINDING-REGISTER.json`
- `BLUE_TEAM_COMBINED_REGISTER.json`
- `BLUE_TEAM_DOMAIN_QUEUES.json`

## Agent Config

- Root config: `opencode.json`
- Agent prompts: `.opencode/prompts/blue-team/`
- Agent manifests: `.opencode/agents/`

## Domain Session Roster

- security: `github-copilot/gpt-5.3-codex`
- data: `mistralai/mistral-large-2512`
- ml-clinical: `deepseek/deepseek-v3.2-20251201`
- reliability: `minimax/minimax-m2.5-20260211`
- performance: `qwen/qwen3-coder-480b-a35b-07-25`
- devops: `qwen/qwen3.5-397b-a17b-20260216`
- ux: `github-copilot/gemini-3.1-pro-preview`
- qa: `github-copilot/gpt-5.4-mini`
- manual-triage: `qwen/qwq-32b`
- merge: `z-ai/glm-5-20260211`

## Launch Sequence

1. Start orchestrator session with `blue-team-orchestrator`.
2. Dispatch these sessions in parallel:
   - security-team-lead
   - data-team-lead
   - ml-team-lead
   - reliability-team-lead
   - performance-team-lead
   - devops-team-lead
   - ux-team-lead
   - qa-team-lead
   - manual-triage-team-lead
3. Wait for all domain reports under `docs/security-audits/2026-03-red-team/fixes/<domain>/SESSION-REPORT.md`.
4. Dispatch merge session (`merge-team-lead`).
5. Validate final report at `docs/security-audits/2026-03-red-team/fixes/merge/FINAL-MERGE-REPORT.md`.

## Session Output Requirements

Each domain must produce:

- per-unit fix logs at `docs/security-audits/2026-03-red-team/fixes/<domain>/<unit-id>.md`
- session report at `docs/security-audits/2026-03-red-team/fixes/<domain>/SESSION-REPORT.md`
- exactly one domain commit
- end-of-session test/lint outputs

## Combined Fix Handling

- Queue items with `combined_fix=true` are root+extension bundles.
- Fix as one remediation unit.

## Merge Conflict Handling

- Conflicts are intentionally deferred to the merge session.
- Merge session resolves semantic conflicts and reruns validations.

## Validation Baseline

- Backend:
  - `cd backend && ruff check .`
  - `cd backend && python test_direct.py` (if backend or ML touched)
- Frontend:
  - `cd frontend && npm run build`
