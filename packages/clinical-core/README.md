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
  model's opinion — see `triage.ts`'s mode handling. In `rules_first`
  mode (the default), the model's tier is never read for `tier` at all.
- Every fired rule carries a citation (`FiredRule.citation`) so a clinician
  can trace *why* a tier was assigned back to a named guideline — see
  `test/engine.test.ts` for the safety-net/pregnancy/paediatric cases each
  citation-bearing rule must get right.
- `noUncheckedIndexedAccess` is on in `tsconfig.base.json` — vitals are
  frequently absent in the field (no BP cuff, no pulse oximeter) and every
  lookup must handle that explicitly, not implicitly.

## Tests (`pnpm test`)

- `test/engine.test.ts` — ported from `backend/tests/test_classifier_safety.py`:
  every hand-picked safety-net, pregnancy, and paediatric case against `assignTier()`.
- `test/engine.fuzz.test.ts` — ported from `backend/tests/test_classifier_fuzz.py`:
  ~11,000 seeded randomized cases asserting `triage()`/`assignTier()` never
  crash and the output contract + safety-net invariant hold under noise.
- `test/contraindications.test.ts` — ported from `apps/web/tests/contraindications.test.mjs`.
- `test/features.golden.test.ts` / `test/treeEvaluator.golden.test.ts` — replay
  the committed `apps/web/tests/fixtures/*` golden vectors against
  `buildFeatureMap()` / `evaluateTrees()`.
- `test/cli.test.ts` — exercises `cli.mjs` as a real subprocess.
- `test/conformance/hybrid.conformance.test.ts` — the migration conformance
  gate: replays 10,000 synthetic patients through `triage()` in `hybrid`
  mode and asserts agreement with the current model-primary contract; it also
  generates an informational `rules_first` versus current-production delta
  report. Regenerate the patient set with
  `python tools/training/export_conformance_patients.py`; see
  `test/conformance/report.md` for the latest run's results.

## Regenerating training artifacts

`cli.mjs` exposes `label` and `engineer-features` JSONL subcommands. The
Python training pipeline in `tools/training/` already calls this CLI for labels
and engineered features; it does not maintain a second production labeler.
Build this package before running the pipeline so its compiled CLI and package
artifacts are available:

```bash
pnpm --filter @vitalnet/clinical-core build
cd tools/training
python train_classifier.py
```

The command regenerates the frozen backend model artifacts, web tree/config
artifacts, and golden-vector fixtures together. Never hand-edit one generated
artifact or retrain the production model as part of routine cleanup. The web
runtime deliberately uses `hybrid` mode to match the live FastAPI backend,
while the not-yet-live Edge Function exercises `rules_first` mode; both modes
use this same package and are covered by the relevant tests.
