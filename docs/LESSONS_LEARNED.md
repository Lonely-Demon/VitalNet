# VitalNet — Lessons Learned (living document)

This is not another architecture doc — `CODEBASE_MAP.md` and `docs/DECISIONS.md`
already own "what" and "why." This file is for the things that don't fit
either: how work actually gets verified in this repo, dead ends worth not
re-walking, and — critically — unintegrated work sitting on branches that a
future agent or maintainer could easily miss because it never made it into
`dev`.

**This file is meant to be appended to, not rewritten.** If you (human or
agent) hit a dead end, discover stale-but-relevant work, or learn something
the hard way that isn't captured anywhere else, add a dated entry. Don't let
it go stale — an entry that's wrong is worse than no entry (same principle
`AGENTS.md` states for every other doc here).

## How this repo verifies claims — read this before trusting a "fixed" claim

A pattern that has repeatedly caught real bugs across this project's history:
**don't trust that a migration, CI fix, or parity claim works by reading the
diff — reproduce the failure, then reproduce the fix, against something real.**

- A DB migration "looks right"? Stand up a real local Postgres (`docker run
  postgres:16` or equivalent), apply it, and actually exercise the RLS
  policies/functions with role-switching — don't just read the SQL. This is
  how the phase28/29/31 `SECURITY DEFINER` functions were verified (real
  Postgres, not inspection), and it's how a genuine "insert denied without
  the function" gap would have been caught before shipping, not after.
- A CI workflow "should" build correctly? Reproduce the exact failure locally
  first (e.g. move `dist/` aside, run the exact CI command, watch it fail),
  fix it, then re-run the exact same sequence and watch it pass. This is how
  a real bug in `api-edge-function.yml` (missing a `clinical-core` build step
  before Deno steps — every `apps/api` PR would have failed from a fresh
  checkout) was found and confirmed fixed, not just patched and hoped.
- A cross-language "parity" claim (JS vs Python, hybrid vs rules_first, old
  vs new)? Generate a real dataset and diff the actual outputs
  (`packages/clinical-core/test/conformance/`) rather than asserting
  equivalence from reading both implementations side by side. Two
  implementations that *look* equivalent on inspection have, in this
  project's history, turned out not to be (see the Round 6 offline-triage
  entry below).
- Independent review matters even after self-verification: the person
  reviewing PR #54 caught a real bug (offline triage silently shipping
  `rules_first` mode with no gate) that survived a full self-verification
  pass, by checking out the actual commit and re-running things themselves
  rather than trusting the PR description. Don't skip review because CI is
  green and tests pass.

## Tried and abandoned

Entries here are things actually built (or seriously started) and then
reverted or replaced — not just "considered and rejected" (that's what
`docs/DECISIONS.md`'s per-entry alternatives sections are for; check there
too, this list isn't exhaustive of every rejected alternative).

- **The 4-sub-model "enhanced" ensemble classifier** (`enhanced_classifier.py`,
  now deleted) — retired because the shipped `.pkl` was incompatible with the
  scikit-learn version actually installed (a live startup-crashing bug), it
  was ~25 MB and ran three tree models redundantly per prediction for no
  measurable accuracy gain, and it was trained independently from the
  ONNX-exported offline model so online/offline triage could disagree for the
  same patient. Full detail: `backend/CLASSIFIER_CHANGELOG.md`.
- **v1.0/v2.0 classifiers** (`classifier_original.py`, `classifier_v2.py`,
  both deleted) — early iterations, superseded. `backend/CLASSIFIER_CHANGELOG.md`.
- **`onnxruntime-web` (WASM) for offline inference** — replaced with a
  dependency-free pure-JS tree evaluator (~12 MB WASM binary removed
  entirely). See `CODEBASE_MAP.md`'s "Frontend build-size notes" and
  `MODEL_CARD.md`.
- **The `feature/ts-clinical-core` branch** — the first several phases of the
  Round 6 TypeScript migration were built here before the migration's scope
  grew large enough to need a dedicated long-lived branch; the branch was
  then recreated as `experimental` pointing at the same history (not
  rebuilt) — see `docs/DECISIONS.md` §32. `feature/ts-clinical-core` still
  exists on `origin` as of this writing, frozen at an early Phase 3 commit.
  **It is stale — do not build on it or assume it reflects current state.**
  It's a candidate for deletion once nobody needs the historical reference,
  but hasn't been explicitly authorized for deletion.
- **Offline triage hardcoded to `rules_first` mode with no gate** (Round 6,
  caught in PR #54 review, fixed same PR) — `apps/web`'s offline path
  briefly called `triage()` in `rules_first` mode unconditionally, which
  would have let an offline ASHA worker see a preliminary tier from the
  not-yet-clinically-approved architecture, disagreeing with what the still-live
  legacy backend would assign on sync. Fixed by gating to `hybrid` mode
  (matches the live backend) until the real cutover happens. Full account,
  including why it wasn't a data-integrity bug (the outbox enqueues the raw
  form, not the locally-computed tier): `docs/DECISIONS.md` §33's
  "Correction, found in PR review" addendum. The general lesson: a mode flag
  that defaults to the *target* architecture instead of the *currently-live*
  one is an easy, easy-to-miss mistake in a strangler-fig migration —
  check which one every new call site actually uses, don't assume.

## Unintegrated parallel work that needs a decision — read this one

**As of 2026-07-11, three branches exist on `origin` containing real,
substantive work that was never merged into `dev` or reconciled with the
Round 6 migration.** They were discovered late (after Round 6 already merged)
and are flagged here rather than acted on unilaterally, because reconciling
them means real architectural and clinical-safety decisions only a human
should make. Check `git branch -a` / `git log <branch>` before assuming this
list is still accurate — branches can be merged, deleted, or go further
stale after this entry is written.

### `origin/claude/ml-clinical-safety-foundation` (and its earlier sibling `origin/claude/codebase-red-team-audit-r1a985`) — likely the single most valuable unintegrated asset in this repo

Six new files, purely additive (no existing code touched), explicitly marked
safe to merge on their own:
- `docs/RULES_PRIMARY_DESIGN.md` — a **different** rules-primary proposal
  than what Round 6 shipped. Round 6 made the rules engine 100% authoritative
  (`T_final = T_rule`, model purely advisory/informational). This proposal is
  `T_final = max(T_rule, T_model)` — the model can still *escalate* above the
  rule, just never de-escalate below it. Grounded in a real ablation
  (`backend/scripts/ablation_model_vs_rule.py`, results in
  `CLINICAL_RISK_MANAGEMENT.md`) finding **191/60,000 cases where the
  (pre-Round-6) model shipped a tier below the deterministic rule, including
  8 two-tier EMERGENCY→ROUTINE drops**. **This is a genuine, unreconciled
  design fork from Round 6's approach and deserves a real side-by-side
  comparison before anyone assumes Round 6's design is simply "the" answer.**
- `docs/CLINICAL_RISK_MANAGEMENT.md` — an ISO 14971-style hazard analysis.
  Not reviewed by a clinician, but a serious first draft of exactly the kind
  of document `docs/CLINICAL_REVIEW.md`'s sign-off gate will eventually need
  something like.
- `docs/VALIDATION_PROTOCOL.md` — names the actual bottleneck in almost the
  same words later used in this project's own conversations: **"the two
  unlocks" are a clinical collaborator and real de-identified data**,
  separates what's executable *without* either (synthetic-only hardening,
  done) from what's hard-gated on them, and is explicit that "no engineering
  on synthetic data substitutes for either."
- `docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md` — a concrete, legally-
  reasoned plan for *external validation against real public clinical
  datasets* (not scraping, not retraining) as the highest-value thing
  achievable **before** a clinical collaborator is found. Names specific
  candidate real-world data sources and organizations. If the project is
  ever stuck on "we have no clinician and no real data," this document is
  the most concrete existing answer to "what can we still do."
- `backend/scripts/ablation_model_vs_rule.py`, `backend/scripts/evaluate_on_real.py`
  — real tooling, not just docs. Written against the pre-Round-6
  `backend/scripts/` path; would need re-pathing to `tools/training/` (or
  wherever `packages/clinical-core`'s equivalent lives) to run against the
  current codebase, since Round 6 moved and partially rewrote what these
  scripts call into.

**Recommendation for whoever picks this up**: read `VALIDATION_PROTOCOL.md`
and `RULES_PRIMARY_DESIGN.md` in full before doing anything else
clinical-safety-related in this repo. At minimum, the docs (explicitly
marked safe/additive) are worth merging into `dev` as reference material even
before deciding whether to adopt `max(T_rule, T_model)` over Round 6's pure
`T_final = T_rule`. The scripts need porting to run against current code.
None of this should be merged or acted on without the same rigor Round 6's
own clinical changes went through (`docs/CLINICAL_REVIEW.md`).

### `origin/claude/codebase-audit-docs-security-lnn9fr`

Older (2026-07-04, "Round 2" docs sync), touches the pre-migration `frontend/`
layout extensively. Given its age and that multiple full rounds (3 through 6)
have superseded that era of the codebase, this is very likely safely stale —
but wasn't diffed file-by-file to confirm before this entry was written.
Check before assuming.

## Stale branches, generally

`git branch -a` currently also shows `main` and `test` as long-lived
deployment branches (see `CONTRIBUTING.md`) — not stale, don't confuse with
the above. `experimental` (the Round 6 migration's branch) was deleted by
GitHub's auto-delete-on-merge after PR #54 merged into `dev`; per
`docs/DECISIONS.md` §32 it's meant to be recreated for the *next* reform of
similar scope, not treated as permanently gone.
