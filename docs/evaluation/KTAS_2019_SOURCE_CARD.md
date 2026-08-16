# Evaluation Source Card: Korean KTAS 2019 Dataset (Gate 3A)

> **Status**: Tracked Evaluation Specification
> **Gate Role**: Gate 3A — External Triage Benchmark
> **Input Modes**: Primary `ktas_triage_contract_v1` (Vitals + Bilingual Parsed Symptoms) | Sensitivity `ktas_vital_only_partial_v1` (Vital-Only Partial Input)
> **Label Mapping**: `ktas_v1` (KTAS_expert: 1–2 -> EMERGENCY, 3 -> URGENT, 4–5 -> ROUTINE)
> **Related Documents**: `docs/EVALUATION_DATA_BOUNDARY.md`, `docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md`, `docs/evaluation/SAFETY_REMEDIATION_DESIGN.md`.

---

## 1. Dataset Overview & Provenance

| Property | Value |
|---|---|
| **Dataset Title** | Korean Triage and Acuity Scale (KTAS) Multi-Center Dataset (Moon et al. 2019) |
| **Issuing Authority / Journal** | PLOS ONE / National Medical Center & Regional Emergency Medical Centers, Republic of Korea |
| **Official Article DOI** | [https://doi.org/10.1371/journal.pone.0216972](https://doi.org/10.1371/journal.pone.0216972) |
| **Supplementary S1 (Data Workbook)** | [https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0216972.s001](https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0216972.s001) |
| **Supplementary S2 (Coding Workbook)** | [https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0216972.s002](https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0216972.s002) |
| **License / Reuse Terms** | PLOS ONE open-access article published under Creative Commons Attribution 4.0 International (CC BY 4.0); supplementary workbooks hosted by publisher |
| **Target Setting** | Multi-center Emergency Departments in South Korea (Local Emergency Medical Center vs. Regional Emergency Medical Center) |
| **Total Cohort Volume** | 1,267 patient encounter records (`N=1267 data` worksheet) |
| **Primary Local Placement** | `tools/training/data/ktas_2019/` (strictly gitignored and local-only) |

---

## 2. Table Layout & 24-Header Schema Specifications

The official Moon et al. (2019) data workbook (`.xlsx`) contains exactly 24 column headers in the `N=1267 data` worksheet:

```
[Official Moon et al. Data Workbook (Supplementary S1)]
├── Sheet: "N=1267 data" (1,267 patient encounters)
└── Sheet: "coding sheet" (Variable definitions & value codes)
```

### 2.1 Complete 24-Column Header Layout & Ingestion Rules

| Column Header (Official) | Raw Data Type | Valid Physiological Range / Codes | Transformation / Handling in Adapter | Destination / Classification |
|---|---|---|---|---|
| `Group` | int / str | 1 = Local ED, 2 = Regional ED | Preserved in cohort metadata for site-stratified analysis | Cohort Metadata (`hospital_group`) |
| `Sex` | int | 1 = Female, 2 = Male | Official KTAS coding: `1` -> `"female"`, `2` -> `"male"` | `form_data["patient_sex"]` |
| `Age` | int / float | 0–130 years | Direct integer age | `form_data["patient_age"]` |
| `Patients number per hour` | int / float | $\ge 0$ | **Ignored input field**: accepted in official schema, but excluded from `CanonicalPatientRecord`, `form_data`, raw fields, labels, features, metrics, and model input | `KTAS_IGNORED_INPUT_FIELDS` (Zero influence) |
| `Arrival mode` | int / str | 1–7 (Ambulance, walk-in, etc.) | Tracked in aggregate inspection metadata only | Cohort Metadata (`arrival_mode`) |
| `Injury` | int | 1 = Non-injury, 2 = Injury | Tracked in aggregate inspection metadata only | Cohort Metadata (`injury_status`) |
| `Chief_complain` | str (Bilingual) | Korean Hangul & English clinical terms | Deterministically parsed into 12 canonical symptoms; raw text immediately purged (zero retention) | `form_data["symptoms"]` (`chief_complaint=""`) |
| `Mental` | int | 1=Alert, 2=Verbal, 3=Pain, 4=Unresponsive | Tracked in inspection metadata (AVPU research reference) | Cohort Metadata (`mental_status`) |
| `Pain` | int | 0 = No pain, 1 = Pain present | Tracked in inspection metadata only | Cohort Metadata (`pain_present`) |
| `NRS_pain` | int / float | 0–10 Numeric Rating Scale | Tracked in inspection metadata only | Cohort Metadata (`pain_score`) |
| `SBP` | int / float / token | 20.0–350.0 mmHg | Systolic blood pressure; nonnumeric tokens (`#NULL!`, `측불`) treated as `None` | `form_data["bp_systolic"]` |
| `DBP` | int / float / token | 10.0–250.0 mmHg | Diastolic blood pressure; inverted BP (`SBP <= DBP`) sanitized to `None` | `form_data["bp_diastolic"]` |
| `HR` | int / float / token | 10.0–350.0 bpm | Heart rate in beats per minute | `form_data["heart_rate"]` |
| `RR` | int / float / token | 0.0–120.0 breaths/min | **Isolated from model input (`form_data`)**; recorded in inspection metadata only | Cohort Metadata (`respiratory_rate`) |
| `BT` | float / token | 20.0–46.0 °C | Body temperature in Celsius (no Fahrenheit conversion needed) | `form_data["temperature"]` |
| `Saturation` | float / token | 0.0–100.0 % | Pulse oximetry SpO₂ (allows severe hypoxia down to 0%); missing in 100% of Local ED | `form_data["spo2"]` |
| `KTAS_RN` | int (1–5) | 1=Resuscitation ... 5=Non-urgent | Primary nurse triage grade; retained strictly for aggregate audit comparison metadata; **prohibited from model input or target labels** | Cohort Inspection Metadata |
| `Diagnosis in ED` | str | Clinical ICD / Korean text | **Prohibited downstream outcome field**; stripped fail-closed | `KTAS_PROHIBITED_FIELDS` |
| `Disposition` | int | Discharge, admission, transfer, death | **Prohibited downstream outcome field**; stripped fail-closed | `KTAS_PROHIBITED_FIELDS` |
| `KTAS_expert` | int (1–5) | 1=Resuscitation ... 5=Non-urgent | **Authoritative reference ground truth label** mapped via `ktas_v1` | Reference Acuity Target |
| `Error_group` | int / str | Over/under-triage categorization | **Prohibited post-hoc error audit field**; stripped fail-closed | `KTAS_PROHIBITED_FIELDS` |
| `Length of stay_min` | int / float | Duration of ED stay in minutes | **Prohibited downstream outcome field**; stripped fail-closed | `KTAS_PROHIBITED_FIELDS` |
| `KTAS duration_min` | int / float | Time required for triage assessment | **Prohibited process metric**; stripped fail-closed | `KTAS_PROHIBITED_FIELDS` |
| `mistriage` | int | 0 = Correct, 1 = Error | **Prohibited post-hoc error audit field**; stripped fail-closed | `KTAS_PROHIBITED_FIELDS` |

---

## 3. Strict Temporal Isolation & Prohibited Fields

To eliminate all possibility of temporal leakage, retrospective bias, or label contamination, the KTAS adapter strips prohibited fields at the OpenXML parser boundary before constructing canonical patient records:

### 3.1 Prohibited Fields Tuple (`KTAS_PROHIBITED_FIELDS`)
The following fields are strictly excluded from `CanonicalPatientRecord`, `form_data`, `raw_fields`, and output reports:
1. `Diagnosis in ED`: Final emergency department diagnosis established post-triage.
2. `Disposition`: Patient outcome (admission, ICU transfer, discharge, mortality).
3. `Error_group`: Retrospective error classification.
4. `Length of stay_min`: Downstream hospital stay duration.
5. `KTAS duration_min`: Operational time metric.
6. `mistriage`: Retrospective mistriage binary flag.
7. `KTAS_RN`: On-duty triage nurse score (isolated from reference labels; retained in aggregate audit metadata only).

### 3.2 Ignored Input Fields (`KTAS_IGNORED_INPUT_FIELDS`)
- `Patients number per hour`: Documented in the 24-header schema as an administrative workload metric. The adapter strictly verifies its presence in schema validation but completely excludes it from model feature engineering, raw fields, and inference payloads.

---

## 4. Ground Truth Target Mapping: `ktas_v1`

The authoritative benchmark target is derived exclusively from `KTAS_expert` (expert emergency physician/triage auditor evaluation):

| KTAS Grade (`KTAS_expert`) | Clinical Acuity Definition | VitalNet Target Tier | Tier Index | Clinical Rationale |
|---|---|---|---|---|
| `1` | Resuscitation (Immediate life threat) | `EMERGENCY` | `2` | Acute physiological crisis requiring immediate intervention |
| `2` | Emergent (Potential life/limb threat) | `EMERGENCY` | `2` | High-risk presentation requiring rapid resuscitation |
| `3` | Urgent (Serious illness/condition) | `URGENT` | `1` | Moderate-to-severe condition requiring prompt stabilization |
| `4` | Less Urgent (Standard illness) | `ROUTINE` | `0` | Stable presentation; routine care appropriate |
| `5` | Non-urgent (Minor conditions) | `ROUTINE` | `0` | Low-acuity complaint suitable for routine outpatient care |

---

## 5. Input Arms & Evaluation Contracts

### 5.1 Primary Benchmark Arm: `ktas_triage_contract_v1`
Passes all available triage parameters while purging raw chief complaint strings:
```python
form_data = {
    "patient_age": int(age),
    "patient_sex": "female" if sex == 1 else "male",
    "temperature": bt,                 # Celsius (float)
    "heart_rate": hr,                  # bpm (int)
    "bp_systolic": sbp,                # mmHg (int)
    "bp_diastolic": dbp,              # mmHg (int)
    "spo2": sat,                       # % (int)
    "symptoms": parsed_symptom_list,   # Allow-listed 12 canonical symptoms (ktas_symptom_parser_v1)
    "chief_complaint": "",             # STRICT: Purged empty string (zero text retention)
    "complaint_duration": "",          # Empty string
    "location": "",                    # Empty string
    "known_conditions": "",            # Empty string
    "current_medications": "",         # Empty string
    "is_pregnant": None,               # None
    "observations": "",                # Empty string
}
```

### 5.2 Vital-Only Sensitivity Arm: `ktas_vital_only_partial_v1`
Passes physiological vitals only, stripping all symptom information to evaluate vital-only resilience:
```python
form_data["symptoms"] = []             # STRICT: Empty list
form_data["chief_complaint"] = ""      # STRICT: Empty string
```

---

## 6. Deterministic Bilingual Symptom Parser (`ktas_symptom_parser_v1`)

Unstructured chief complaints in Korean Hangul and English clinical shorthand are parsed into VitalNet's 12 canonical symptom IDs via `ktas_symptom_parser_v1`:
- **12 Canonical Symptoms**: `chest_pain`, `breathlessness`, `altered_consciousness`, `severe_bleeding`, `seizure`, `high_fever`, `severe_abdominal_pain`, `persistent_vomiting`, `severe_headache`, `weakness_one_side`, `difficulty_speaking`, `swelling_face_throat`.
- **Bilingual Coverage**: Supports Korean descriptors (e.g., 흉통, 호흡곤란, 의식저하, 대량출혈, 경련, 발열, 복통, 구토, 두통, 편측마비) and English medical abbreviations (e.g., `cp`, `sob`, `ams`, `loc`, `gi bleed`).
- **Negation Detection**: Comprehensive prefix (`no`, `denies`, `without`, `r/o`) and suffix (없음, 안함, 부정, 소실, 호전, `-`) negation patterns.
- **Zero-Retention Guarantee**: Raw complaint text is never stored in patient encounter records or written to output JSON reports.

---

## 7. Cohort Flow, Completeness & Site-Stratified Limitation

### 7.1 Empirical Cohort Statistics
- **Total Raw Records**: 1,267 encounters.
- **Exclusions**: 0 records excluded for invalid age/sex/sentinel codes; all 1,267 encounters have valid expert acuity.
- **Five-Vital Completeness**: Exactly **563 complete five-vital encounters** (44.4% of total cohort).
- **Severe Site Missingness Disparity**:
  - **Regional ED (`Group = 2`)**: 563 of 660 encounters (85.3%) have complete five vitals.
  - **Local ED (`Group = 1`)**: **0 of 607 encounters (0.0%)** have complete five vitals because pulse oximetry (`Saturation`) was unmeasured across 100% of Local ED presentations.

---

## 8. Aggregate Evaluation Findings (Summary)

Evaluation of the frozen production model on the KTAS 2019 dataset demonstrated:
1. **Primary Contract (`ktas_triage_contract_v1`)**:
   - EMERGENCY Sensitivity: **25.2%** (Wilson 95% CI: 19.3% – 32.2%).
   - EMERGENCY Miss Rate: **74.8%** (97 / 130 true emergencies under-triaged).
2. **Vital-Only Sensitivity Arm (`ktas_vital_only_partial_v1`)**:
   - EMERGENCY Sensitivity: **17.9%** (Wilson 95% CI: 12.8% – 24.4%).
   - EMERGENCY Miss Rate: **82.1%** (105 / 128 true emergencies under-triaged).
3. **Safety Signal**: When clinical symptoms and complaints are absent or incomplete, vital signs alone fail to trigger emergency classification, confirming the critical safety hazard identified in NHAMCS Gate 1B.

---

## 9. Gate 3A Staged Authorization & Refusal Semantics

- **Default Execution**: Model scoring is strictly locked. Calling `load_for_evaluation()` raises `EvaluationRefusedError` with exit code `2`.
- **Authorization Requirement**: Model scoring requires explicit out-of-band human authorization via the `--gate-3a-scoring-authorized` CLI flag.
- **Inspection Unlocked**: Source inspection (`--inspect-source ktas-2019`) operates freely for data quality, schema audit, and cohort flow verification.

---

## 10. Population Limitations & Clinical Non-Claims

1. **Korean Hospital ED Cohort Bias**: KTAS 2019 reflects urban emergency department presentations in South Korea under the Korean National Health Insurance system. Disease prevalence, acute trauma rates, baseline vitals, and healthcare access differ fundamentally from rural Indian primary care.
2. **Physician Expert Acuity vs Frontline ASHA Triage**: `KTAS_expert` is assigned by emergency medicine specialists with full diagnostic access; it does not reflect syndromic community triage performed by ASHA workers with limited equipment.
3. **Non-Equivalence to Clinical Validation**: Retrospective evaluation on KTAS 2019 measures algorithmic discrimination; it does not constitute clinical safety certification, SaMD clearance, or prospective clinical trial validation under CDSCO or FDA frameworks.
