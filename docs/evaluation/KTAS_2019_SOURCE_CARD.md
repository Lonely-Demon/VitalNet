# Evaluation Source Card: Korean KTAS 2019 Dataset (Gate 3A)

> **Status**: Tracked Evaluation Specification
> **Gate Role**: Gate 3A — Open External Emergency Department Triage Benchmark
> **Input Modes**:
> - Primary Benchmark Arm: `ktas_triage_contract_v1` (Age, sex, five vitals, allow-listed symptoms, empty complaint string)
> - Sensitivity Arm: `ktas_vital_only_partial_v1` (Age, sex, five vitals, empty symptoms list, empty complaint string)
> **Label Mapping**: `ktas_v1` (KTAS 1–2 -> `EMERGENCY`, 3 -> `URGENT`, 4–5 -> `ROUTINE`)
> **Parser Version**: `ktas_symptom_parser_v1` (Deterministic bilingual Korean/English allow-list parser)
> **Related Documents**: `docs/EVALUATION_DATA_BOUNDARY.md`, `docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md`, `docs/evaluation/SAFETY_REMEDIATION_DESIGN.md`.

---

## 1. Dataset Overview & Provenance

| Property | Value |
|---|---|
| **Dataset Title** | Korean Triage and Acuity Scale (KTAS) Multi-Center Emergency Department Dataset |
| **Authors / Investigators** | Moon et al. (2019) |
| **Associated Publication** | *PLOS ONE* (2019), "Validation of the Korean Triage and Acuity Scale" |
| **Article DOI** | [https://doi.org/10.1371/journal.pone.0216972](https://doi.org/10.1371/journal.pone.0216972) |
| **Supplementary S1 (Data Workbook)** | [https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0216972.s001](https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0216972.s001) |
| **Supplementary S2 (Coding Workbook)** | [https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0216972.s002](https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0216972.s002) |
| **License / Terms** | Open-access article published under CC BY 4.0; publisher-hosted supplementary workbooks |
| **Target Setting** | Two emergency departments in South Korea: Local ED (Group 1) and Regional ED (Group 2) |
| **Total Cohort Volume** | Exactly **1,267 patient encounters** across two study sites |
| **Primary Data Worksheet** | Exact sheet name: `"N=1267 data"` |
| **Coding Sheet** | Exact sheet name: `"coding sheet"` (variable metadata only; never parsed as encounters) |
| **Primary Local Placement** | `tools/training/data/ktas_2019/` (strictly gitignored and local-only) |

---

## 2. Published 24-Header Schema & Field Alignment

The official Moon et al. (2019) data workbook (`s001`) contains exactly **24 column headers**. The VitalNet adapter (`tools/training/evaluation_sources/ktas_2019.py`) validates the presence of all 24 headers fail-closed, prohibiting duplicate or unexpected columns.

### 2.1 Complete 24-Header Layout Map

| Column # | Published Header | Raw Type | Description / Units | Handling in VitalNet Adapter | Destination in Canonical Record |
|---|---|---|---|---|---|
| 1 | `Group` | int (1, 2) | Study site: 1 = Local ED, 2 = Regional ED | Stratified cohort inspection; site completeness audit | Metadata (`site_stratified`) |
| 2 | `Sex` | int (1, 2) | Biological sex: 1 = Female, 2 = Male | Converted via official coding sheet (1->female, 2->male) | `form_data["patient_sex"]` |
| 3 | `Age` | float / int | Patient age in years (0–130) | Validated against plausible physiological range | `form_data["patient_age"]` |
| 4 | `Patients number per hour` | float / int | Hourly ED census / volume | **Classified as `KTAS_IGNORED_INPUT_FIELDS`**; excluded from canonical records and model inputs | Excluded from `form_data` & `raw_fields` |
| 5 | `Arrival mode` | int (1–7) | Mode of arrival (e.g. 119 ambulance, private vehicle) | Bypassed during inference; recorded in inspection metadata | Metadata only |
| 6 | `Injury` | int (1, 2) | Medical vs trauma presentation | Bypassed during inference; recorded in inspection metadata | Metadata only |
| 7 | `Chief_complain` | str (Bilingual) | Presenting chief complaint in Korean / English | Parsed via `ktas_symptom_parser_v1` into allow-listed symptoms; **raw text discarded immediately** | `form_data["symptoms"]` (primary arm) |
| 8 | `Mental` | int (1–4) | AVPU mental status level (Alert, Verbal, Pain, Unresponsive) | Audited in cohort inspection; omitted from standard 5-vital model input | Metadata only |
| 9 | `Pain` | int (0, 1) | Presence of pain symptom | Audited in cohort inspection; omitted from standard 5-vital model input | Metadata only |
| 10 | `NRS_pain` | float / int | Numeric Rating Scale pain score (0–10) | Audited in cohort inspection; omitted from standard 5-vital model input | Metadata only |
| 11 | `SBP` | float / int | Systolic blood pressure (mmHg) | Range validated (20–350 mmHg); inverted BP sanitized to `None` | `form_data["bp_systolic"]` |
| 12 | `DBP` | float / int | Diastolic blood pressure (mmHg) | Range validated (10–250 mmHg); inverted BP sanitized to `None` | `form_data["bp_diastolic"]` |
| 13 | `HR` | float / int | Heart rate in beats per minute | Range validated (10–350 bpm); nonnumeric `#NULL!`/`측불` -> `None` | `form_data["heart_rate"]` |
| 14 | `RR` | float / int | Respiratory rate (breaths/min) | Range validated (0–120 bpm); **isolated from model input** | Metadata only |
| 15 | `BT` | float / int | Body temperature in Celsius (°C) | Range validated (20.0–46.0°C) | `form_data["temperature"]` |
| 16 | `Saturation` | float / int | Pulse oximetry SpO₂ (%) | Range validated (0–100%); nonnumeric `#NULL!`/`측불` -> `None` | `form_data["spo2"]` |
| 17 | `KTAS_RN` | int (1–5) | On-duty nurse initial triage level | **Prohibited from model input and patient encounter records**; retained only for aggregate audit | Prohibited field |
| 18 | `Diagnosis in ED` | str | Final emergency department discharge diagnosis | **Strictly prohibited** (post-triage diagnostic leakage) | Prohibited field |
| 19 | `Disposition` | int (1–7) | Patient disposition (Discharge, Admit, Transfer, Death) | **Strictly prohibited** (post-triage outcome leakage) | Prohibited field |
| 20 | `KTAS_expert` | int (1–5) | Expert consensus reference triage level (1–5) | **Authoritative reference ground truth**; mapped via `ktas_v1` | Reference ground truth tier |
| 21 | `Error_group` | int (1–4) | Source mistriage error classification | **Strictly prohibited** (retrospective audit label) | Prohibited field |
| 22 | `Length of stay_min` | float / int | Total ED length of stay in minutes | **Strictly prohibited** (post-triage temporal leakage) | Prohibited field |
| 23 | `KTAS duration_min` | float / int | Triage interview duration in minutes | **Strictly prohibited** (post-triage temporal leakage) | Prohibited field |
| 24 | `mistriage` | int (0, 1) | Binary source mistriage indicator | **Strictly prohibited** (retrospective audit label) | Prohibited field |

---

## 3. Strict Prohibited Fields & Temporal Isolation

To prevent retrospective bias and data leakage, the adapter enforces hard pre-canonicalization stripping of the following 7 prohibited fields:
```python
KTAS_PROHIBITED_FIELDS = (
    "Diagnosis in ED",
    "Disposition",
    "Error_group",
    "Length of stay_min",
    "KTAS duration_min",
    "mistriage",
    "KTAS_RN",
)
```

Additionally, `Patients number per hour` is classified in `KTAS_IGNORED_INPUT_FIELDS` and excluded from canonical patient records.

---

## 4. Pre-Registered Target Mapping: `ktas_v1`

The authoritative reference ground truth is `KTAS_expert` (consensus expert triage), mapped to VitalNet's 3 clinical tiers:

| KTAS Expert Level | Official KTAS Clinical Acuity Definition | Target VitalNet Tier | Tier Code |
|---|---|---|---|
| **Level 1** | Resuscitation (Immediate threat to life or limb) | `EMERGENCY` | `2` |
| **Level 2** | Emergent (Potential threat to life, limb, or function) | `EMERGENCY` | `2` |
| **Level 3** | Urgent (Conditions with potential to progress to serious problem) | `URGENT` | `1` |
| **Level 4** | Less Urgent / Semi-urgent (Conditions related to patient age/distress) | `ROUTINE` | `0` |
| **Level 5** | Non-urgent (Non-emergency acute or minor chronic conditions) | `ROUTINE` | `0` |

---

## 5. Input Arms & Evaluation Contracts

### 5.1 Primary Benchmark Arm: `ktas_triage_contract_v1`
Passes the available triage parameters with deterministic symptom extraction:
- `patient_age`: Integer age in years.
- `patient_sex`: `"male"` or `"female"`.
- `temperature`: `BT` in °C.
- `heart_rate`: `HR` in bpm.
- `bp_systolic`: `SBP` in mmHg.
- `bp_diastolic`: `DBP` in mmHg.
- `spo2`: `Saturation` in %.
- `symptoms`: Extracted from `Chief_complain` via `ktas_symptom_parser_v1`.
- `chief_complaint`: Explicitly empty string `""` (raw text never retained).

### 5.2 Vital-Only Sensitivity Arm: `ktas_vital_only_partial_v1`
Stress-tests triage discrimination when zero clinical text or symptoms are available:
- `patient_age`, `patient_sex`, and five vital signs populated identically to the primary arm.
- `symptoms`: Strictly empty list `[]`.
- `chief_complaint`: Strictly empty string `""`.

---

## 6. Deterministic Bilingual Symptom Parser: `ktas_symptom_parser_v1`

Unstructured chief complaints in Korean and English (e.g. `chest pain`, `흉통`, `dyspnea`, `호흡곤란`, `fever`, `발열`, `dizziness`, `어지러움`) are deterministically parsed into VitalNet's 12 canonical `ALLOWED_SYMPTOMS`.
- **Zero Raw Text Retention**: Raw complaint strings are processed in a streaming fashion and immediately discarded.
- **No Cloud Dependencies**: Operates entirely with local deterministic keyword/regex matching.

---

## 7. Cohort Profile & Vital Completeness Site Confinement

Inspection of the complete 1,267-record dataset demonstrates critical structural and completeness properties:

| Metric / Parameter | Value across Cohort | Notes |
|---|---|---|
| **Total Cohort Size** | **1,267 records** | Exact row count matching publisher sheet |
| **Local ED (Group 1)** | 674 records (53.20%) | **0 complete 5-vital records** (100% missing `Saturation`) |
| **Regional ED (Group 2)** | 593 records (46.80%) | **563 complete 5-vital records** (94.94% completeness) |
| **Overall 5-Vital Completeness** | **563 / 1,267 records (44.44%)** | Complete 5-vital records are **strictly confined to Regional ED** |
| **Measurement Unavailable Tokens** | `#NULL!`, `측불` | Handled conservatively as missing (`None`), never coerced to 0 |

---

## 8. Summary of Evaluation Findings

In the completed Gate 3A scoring evaluation:

1. **Primary Arm (`ktas_triage_contract_v1`)**:
   - **Overall Agreement**: 49.49%
   - **Emergency Sensitivity**: **25.2%** (95% Wilson CI: 20.2% – 31.0%)
   - **Emergency Miss Rate**: **74.8%** (184 out of 246 reference emergencies missed)
   - **Under-Triage Rate**: 40.09% overall

2. **Vital-Only Partial Arm (`ktas_vital_only_partial_v1`)**:
   - **Overall Agreement**: 46.65%
   - **Emergency Sensitivity**: **17.9%** (95% Wilson CI: 13.6% – 23.2%)
   - **Emergency Miss Rate**: **82.1%** (202 out of 246 reference emergencies missed)
   - **Relative Sensitivity Drop**: 7.3 percentage point drop compared to the primary arm
   - **Under-Triage Rate**: 52.57% overall (+12.5 percentage point increase in under-triage)

---

## 9. Explicit Non-Claims & Safety Limitations

1. **Retrospective Foreign ED Benchmark**: The KTAS 2019 dataset represents emergency department presentations in urban South Korea. It is a benchmark for physiological and symptom-based triage discrimination; it does not represent rural Indian primary care or ASHA community health worker practice.
2. **Site-Confinement Warning**: Complete five-vital records are confined to Regional ED Group 2; complete-vital subgroup results must not be generalized across both hospital sites.
3. **No Clinical Validation or Clearance**: Evaluation on the KTAS 2019 dataset does not constitute clinical trial validation, medical device clearance, or regulatory safety certification.
4. **Mandatory Human Decision Support**: VitalNet is a decision-support prototype. It does not provide autonomous clinical triage or diagnosis.
