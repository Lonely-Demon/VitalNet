# Rules-first vs. production-Python triage delta report

Generated from the same 2000 synthetic patients as REPORT.md.
Compares Python's `predict_triage` (production baseline) against clinical-core's `triage()` in `rules_first` mode
(the Phase 4 target architecture, where clinical-core rules are 100% authoritative and the model is advisory).

**Identical classification: 1985/2000 (99.250%)**
**Changed classification: 15/2000 (0.750%)**

## Confusion matrix (rows = Python tier, columns = rules_first tier)

| Python \ RulesFirst | ROUTINE | URGENT | EMERGENCY |
|---|---|---|---|
| ROUTINE | 553 | 1 | 0 |
| URGENT | 0 | 888 | 5 |
| EMERGENCY | 0 | 9 | 544 |

## Sample deltas (first 20)

- #105: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
- #289: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
- #695: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
- #735: production_python=URGENT -> rules_first=EMERGENCY (model_agreed=false)
- #764: production_python=ROUTINE -> rules_first=URGENT (model_agreed=false)
- #826: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
- #1056: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
- #1114: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
- #1450: production_python=URGENT -> rules_first=EMERGENCY (model_agreed=false)
- #1484: production_python=URGENT -> rules_first=EMERGENCY (model_agreed=false)
- #1756: production_python=URGENT -> rules_first=EMERGENCY (model_agreed=false)
- #1767: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
- #1878: production_python=URGENT -> rules_first=EMERGENCY (model_agreed=false)
- #1883: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
- #1951: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
