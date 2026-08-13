# Rules-first vs. production-Python triage delta report

Generated from the same 10000 synthetic patients as REPORT.md.
Compares Python's `predict_triage` (production baseline) against clinical-core's `triage()` in `rules_first` mode
(the Phase 4 target architecture, where clinical-core rules are 100% authoritative and the model is advisory).

**Identical classification: 9912/10000 (99.120%)**
**Changed classification: 88/10000 (0.880%)**

## Confusion matrix (rows = Python tier, columns = rules_first tier)

| Python \ RulesFirst | ROUTINE | URGENT | EMERGENCY |
|---|---|---|---|
| ROUTINE | 2755 | 14 | 2 |
| URGENT | 2 | 4475 | 19 |
| EMERGENCY | 0 | 51 | 2682 |

## Sample deltas (first 20)

- #105: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
- #289: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
- #695: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
- #735: production_python=URGENT -> rules_first=EMERGENCY (model_agreed=false)
- #764: production_python=ROUTINE -> rules_first=URGENT (model_agreed=false)
- #826: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
- #959: production_python=URGENT -> rules_first=EMERGENCY (model_agreed=false)
- #1056: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
- #1114: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
- #1450: production_python=URGENT -> rules_first=EMERGENCY (model_agreed=false)
- #1484: production_python=URGENT -> rules_first=EMERGENCY (model_agreed=false)
- #1756: production_python=URGENT -> rules_first=EMERGENCY (model_agreed=false)
- #1767: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
- #1878: production_python=URGENT -> rules_first=EMERGENCY (model_agreed=false)
- #1883: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
- #1951: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
- #2005: production_python=URGENT -> rules_first=EMERGENCY (model_agreed=false)
- #2292: production_python=EMERGENCY -> rules_first=URGENT (model_agreed=false)
- #2394: production_python=URGENT -> rules_first=EMERGENCY (model_agreed=false)
- #2459: production_python=URGENT -> rules_first=EMERGENCY (model_agreed=false)
