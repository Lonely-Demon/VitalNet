# Hybrid-mode conformance report

Generated from 10000 synthetic patients (backend/scripts/export_conformance_patients.py, seed 20260711).
Each was labeled by Python's `predict_triage` (production, pre-migration) and replayed through
clinical-core's `triage()` in `hybrid` mode (safety-net override -> trained model -> NEWS2 floor —
the same order as the Python path).

**Agreement: 10000/10000 (100.000%)**

## Confusion matrix (rows = Python tier, columns = TS tier)

| Python \ TS | ROUTINE | URGENT | EMERGENCY |
|---|---|---|---|
| ROUTINE | 2771 | 0 | 0 |
| URGENT | 0 | 4496 | 0 |
| EMERGENCY | 0 | 0 | 2733 |

## Mismatches: none


---

# rules_first vs. current-production delta (informational, DECISIONS §33 input)

Same 10000 patients, replayed through `triage()` in `rules_first` mode (the target end-state:
rules engine 100% authoritative, model advisory-only) instead of `hybrid` mode above.

**Changed: 88/10000 (0.880%)** — 35 upgraded to a higher tier, 53 downgraded to a lower tier.

## Confusion matrix (rows = Python/hybrid tier, columns = rules_first tier)

| Python \ rules_first | ROUTINE | URGENT | EMERGENCY |
|---|---|---|---|
| ROUTINE | 2755 | 14 | 2 |
| URGENT | 2 | 4475 | 19 |
| EMERGENCY | 0 | 51 | 2682 |

## Sample of changed cases (first 20)

- #105: python=EMERGENCY -> rules_first=URGENT (model agreed with rules_first: false)
- #289: python=EMERGENCY -> rules_first=URGENT (model agreed with rules_first: false)
- #695: python=EMERGENCY -> rules_first=URGENT (model agreed with rules_first: false)
- #735: python=URGENT -> rules_first=EMERGENCY (model agreed with rules_first: false)
- #764: python=ROUTINE -> rules_first=URGENT (model agreed with rules_first: false)
- #826: python=EMERGENCY -> rules_first=URGENT (model agreed with rules_first: false)
- #959: python=URGENT -> rules_first=EMERGENCY (model agreed with rules_first: false)
- #1056: python=EMERGENCY -> rules_first=URGENT (model agreed with rules_first: false)
- #1114: python=EMERGENCY -> rules_first=URGENT (model agreed with rules_first: false)
- #1450: python=URGENT -> rules_first=EMERGENCY (model agreed with rules_first: false)
- #1484: python=URGENT -> rules_first=EMERGENCY (model agreed with rules_first: false)
- #1756: python=URGENT -> rules_first=EMERGENCY (model agreed with rules_first: false)
- #1767: python=EMERGENCY -> rules_first=URGENT (model agreed with rules_first: false)
- #1878: python=URGENT -> rules_first=EMERGENCY (model agreed with rules_first: false)
- #1883: python=EMERGENCY -> rules_first=URGENT (model agreed with rules_first: false)
- #1951: python=EMERGENCY -> rules_first=URGENT (model agreed with rules_first: false)
- #2005: python=URGENT -> rules_first=EMERGENCY (model agreed with rules_first: false)
- #2292: python=EMERGENCY -> rules_first=URGENT (model agreed with rules_first: false)
- #2394: python=URGENT -> rules_first=EMERGENCY (model agreed with rules_first: false)
- #2459: python=URGENT -> rules_first=EMERGENCY (model agreed with rules_first: false)
