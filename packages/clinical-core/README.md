# @vitalnet/clinical-core

The single source of clinical truth for VitalNet — replaces four previously
hand-mirrored Python/JS pairs (Pydantic↔Zod validation, `_safety_net_check`↔
`safetyNetCheck`, `ClinicalFeatureEngineer`↔`buildFeatureMap`, and the
contraindication tables) with one TypeScript implementation imported
verbatim by both the web app (`apps/web`) and the API (`apps/api`).

A clinical rule is written once, here. Online/offline agreement stops being
a test suite you can fail and becomes a compile-time fact: both runtimes
import the same `triage()` function from the same npm package.

## What lives here

- `src/schema.ts` — Zod `IntakeForm` schema (patient identifiers, vitals,
  symptoms, consent) with bounds and cross-field validators (e.g.
  diastolic < systolic, symptom allow-list).
- `src/rules/bands.ts` — NEWS2/PALS vital-sign scoring bands, adult and
  age-banded, each row citing its clinical source.
- `src/rules/rules.ts` — deterministic escalation rules: the safety-net
  overrides, the preeclampsia rule (ACOG Practice Bulletin 222), qSOFA
  (age-gated), critical-symptom overrides.
- `src/rules/engine.ts` — the aggregate scorer and tier-assignment logic
  that decides `ROUTINE` / `URGENT` / `EMERGENCY` from fired rules.
- `src/features.ts` — the 43-feature clinical feature engineering used by
  the trained model.
- `src/treeEvaluator.ts` — a dependency-free evaluator for the exported
  gradient-boosted tree ensemble (`triage_trees.json`), plus Saabas-style
  per-feature attribution for the advisory model output.
- `src/contraindications.ts` — the medication/condition/symptom
  contraindication flag table.
- `src/triage.ts` — the orchestrator: `triage(form, trees?)` → tier, fired
  rules (each with its citation), contraindication flags, and an advisory
  model opinion when a tree bundle is supplied.
- `src/patientKey.ts` — the patient continuity key generator/validator.
- `cli.mjs` — `label` and `engineer-features` subcommands (JSONL in/out)
  so the Python training pipeline can call into this package as a
  subprocess instead of maintaining its own copy of the rules.

## Design invariants (do not violate)

- A rule that only ever **raises** a tier must never be changed to lower
  one (NEWS2-floor invariant).
- The deterministic safety-net/rules layer always overrides the advisory
  model's opinion — see `triage.ts`'s mode handling.
- Every rule row carries a citation and at least one embedded test vector
  (`{ id, citation, tests: [{ input, expect }] }`) — `test/rules.test.ts`
  executes every embedded vector automatically; a rule with no vector
  fails the suite.
- `noUncheckedIndexedAccess` is on in `tsconfig.base.json` — vitals are
  frequently absent in the field (no BP cuff, no pulse oximeter) and every
  lookup must handle that explicitly, not implicitly.

## Regenerating training artifacts

`tools/training/train_classifier.py` calls this package's CLI for labeling
and feature engineering, so the trained model's labels and the runtime
rules engine can never drift apart. See `tools/training/README.md`.
