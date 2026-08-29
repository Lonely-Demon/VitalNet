# Evaluation Source Card: Korean KTAS 2019 ED Dataset (Gate 3A)

> **Status**: Completed aggregate inspection and one authorized scoring cycle; model scoring is not repeatable without fresh explicit authorization.
> **Gate Role**: Gate 3A — Open external emergency-acuity benchmark.
> **Dataset**: Korean Triage and Acuity Scale (KTAS), Moon et al. (2019), PLOS ONE supplementary data.
> **Related Documents**: `docs/EVALUATION_DATA_BOUNDARY.md`, `docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md`, `docs/VALIDATION_PROTOCOL.md`, `docs/evaluation/PUBLIC_DATA_EVALUATION_CLOSURE.md`.

## 1. Provenance and access

| Field | Verified value |
|---|---|
| Publication | Moon et al. (2019), PLOS ONE, DOI [10.1371/journal.pone.0216972](https://doi.org/10.1371/journal.pone.0216972) |
| Official data workbook | [Publisher-hosted supplementary file S1](https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0216972.s001) |
| Official coding workbook | [Publisher-hosted supplementary file S2](https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0216972.s002) |
| Access | Open publisher-hosted supplementary files; manually placed locally under `tools/training/data/ktas_gate3a/` |
| License note | The article is published under CC BY 4.0. Reuse of the supplementary workbooks remains subject to the publisher’s article and supplementary-file terms. |
| Dataset size | 1,267 emergency-department encounters; official data workbook has 24 headers. |
| Sites | Local ED (Group 1) and Regional ED (Group 2). |
| Local-only files | `plos_ktas_s001.xlsx` and `plos_ktas_s002.xlsx`; raw files and generated reports are gitignored. |

## 2. Consumed fields and prohibited fields

The adapter consumes age, sex, five physiological vitals, the `KTAS_expert` reference label, and the chief complaint only for deterministic allow-listed symptom extraction in the primary arm. The raw complaint is never retained, emitted, or passed to the model. `Patients number per hour` is accepted as source metadata but is explicitly ignored and cannot influence canonical inputs, labels, or metrics.

Diagnosis, disposition, error group, length of stay, KTAS duration, mistriage, raw nurse labels, and other downstream or audit-only fields are excluded from canonical records. Nurse-versus-expert information is retained only as aggregate distributions in local reports.

## 3. Pre-registered label and input contracts

The `ktas_v1` mapping is fixed before scoring:

| KTAS expert level | VitalNet reference tier |
|---:|---|
| 1–2 | `EMERGENCY` |
| 3 | `URGENT` |
| 4–5 | `ROUTINE` |

Two arms were pre-registered and run once under explicit authorization:

| Arm | Canonical input |
|---|---|
| `ktas_triage_contract_v1` | Age, sex, five vitals, and deterministic bilingual allow-listed symptoms; `chief_complaint` is empty after parsing. |
| `ktas_vital_only_partial_v1` | Age, sex, five vitals, empty `symptoms`, and empty `chief_complaint`. This is a separately labeled partial-input sensitivity arm. |

The deterministic parser is `ktas_symptom_parser_v1`. It supports Korean Hangul and English emergency descriptors with explicit Korean and English negation handling. No cloud NLP or external service is used.

## 4. Aggregate inspection findings

The source contains 1,267 records. The expert-label distribution is `ROUTINE=534`, `URGENT=487`, and `EMERGENCY=246`. Only 563 records (44.44%) have all five canonical vitals. All complete-five-vital records are in Regional ED Group 2; Local ED Group 1 has 688 records and zero numeric oxygen-saturation measurements.

These site and completeness properties mean that complete-vital subgroup findings are not representative of both source sites.

## 5. Authorized scoring findings

The primary arm achieved 49.49% overall agreement and 25.2% `EMERGENCY` sensitivity (95% Wilson CI 20.2%–31.0%). It missed 184 of 246 reference-`EMERGENCY` encounters (74.8%). The vital-only arm achieved 46.65% overall agreement and 17.9% `EMERGENCY` sensitivity (95% Wilson CI 13.6%–23.2%), missing 202 of 246 emergency encounters (82.1%).

Removing structured symptoms reduced emergency sensitivity by 7.3 percentage points and increased overall under-triage by 12.5 percentage points. These results are a serious safety signal, not evidence of clinical validation.

The scoring reports contain a corrected-by-PR-110 cohort-counter path for future runs. The reports from this scoring cycle were generated before PR #110 and have a known `cohort_flow.valid_records=0` metadata defect, although their metric arrays were calculated over all 1,267 records. No rerun is implied by this source card.

## 6. Non-claims and governance

KTAS is a Korean emergency-department acuity benchmark, not an Indian PHC or ASHA cohort. KTAS acuity is not equivalent to prospective rural clinical outcomes, medical-device evidence, or regulatory validation. The findings do not justify deployment, promotion to preproduction, clinical claims, or model retraining.

All raw files and scoring reports remain local-only. No patient-level rows, identifiers, raw complaints, predictions, or probabilities may enter Git, CI, chat, cloud APIs, or production systems. Future KTAS scoring requires a new explicit authorization and must use the frozen model unless a separately governed candidate-model study is approved.
