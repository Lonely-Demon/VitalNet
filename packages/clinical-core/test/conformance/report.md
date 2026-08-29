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

