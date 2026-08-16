# Evaluation Source Card: MIMIC-IV-ED v2.2 (Gate 2)

> **Status**: Tracked Evaluation Specification; credentialing deferred and no full MIMIC score completed
> **Gate Role**: Gate 2 — Deferred Credentialed Triage-Time External Benchmark
> **Input Mode**: Strict `mimic_triage_contract_v1` (available MIMIC triage context)
> **Label Mapping**: `mimic_esi_v1` (ESI 1–2 -> EMERGENCY, 3 -> URGENT, 4–5 -> ROUTINE)
> **Cohort Policies**: `all_stays` (Primary encounter-level) | `first_stay_only` (Pre-registered patient-level sensitivity)
> **Related Documents**: `docs/EVALUATION_DATA_BOUNDARY.md`, `docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md`, `docs/evaluation/PUBLIC_DATA_EVALUATION_CLOSURE.md`, `docs/VALIDATION_PROTOCOL.md`, `docs/DECISIONS.md`.

---

## 1. Dataset Overview & Provenance

| Property | Value |
|---|---|
| **Dataset Title** | Medical Information Mart for Intensive Care IV — Emergency Department (MIMIC-IV-ED) |
| **Dataset Version** | v2.2 (Official PhysioNet Release) |
| **Issuing Authority** | MIT Laboratory for Computational Physiology / Beth Israel Deaconess Medical Center (BIDMC) |
| **Official Dataset Portal** | [https://physionet.org/content/mimic-iv-ed/2.2/](https://physionet.org/content/mimic-iv-ed/2.2/) |
| **Official Digital Object Identifier (DOI)** | [https://doi.org/10.13026/5ntk-km72](https://doi.org/10.13026/5ntk-km72) |
| **Linked Core Demographics** | MIMIC-IV Core v2.2 (`mimiciv.medical.patients` / `patients.csv`) for `anchor_age` |
| **License / Access Agreement** | PhysioNet Credentialed Health Data Use Agreement (100% de-identified health data) |
| **Access Requirements** | Verified PhysioNet credentialing, CITI Data or Specimens Only Research course completion report, local-only processing |
| **Target Population / Setting** | Single-center large tertiary academic medical center emergency department (BIDMC, Boston, MA, USA; 2011–2019) |
| **Encounter Volume** | ~425,000 emergency department stays |
| **Primary Local Placement** | `tools/training/data/mimic_iv_ed/` (strictly gitignored and local-only) |

---

## 2. Table Layout & Multi-Table Linkage Specifications

The evaluation requires MIMIC-IV-ED v2.2 tables linked with MIMIC-IV core demographics. The table linkage hierarchy is strictly defined:

```
[mimiciv_ed.triage] (triage.csv) ── stay_id ──► [mimiciv_ed.edstays] (edstays.csv)
        │
    subject_id
        ▼
[mimiciv.medical.patients] (patients.csv)
```

### 2.1 Table Schemas & Ingestion Rules

| Table / File | Field Name | Description & Precedence | Ingestion & Handling |
|---|---|---|---|
| `triage.csv` | `stay_id` | Unique emergency department stay identifier | Primary encounter unit for cohort evaluation |
| `triage.csv` | `subject_id` | Unique patient identifier | Used for patient linkage and repeated-visit auditing |
| `triage.csv` | `temperature` | Body temperature recorded in Fahrenheit (°F) | Converted to Celsius via `round((temp_f - 32.0) * 5/9, 1)`. Plausible range: 80.0–110.0°F |
| `triage.csv` | `heartrate` | Heart rate in beats per minute | Valid range: 0–240 bpm. Doppler code 998 sanitized to `None` |
| `triage.csv` | `sbp` | Systolic blood pressure in mmHg | Valid range: 40–290 mmHg. Doppler 998 sanitized to `None` |
| `triage.csv` | `dbp` | Diastolic blood pressure in mmHg | Valid range: 20–190 mmHg. Doppler 998 sanitized to `None`. Inverted BP (`sbp <= dbp`) sanitized to `None` |
| `triage.csv` | `o2sat` | Pulse oximetry SpO₂ (%) | Valid range: 0–100% |
| `triage.csv` | `chiefcomplaint` | Presenting chief complaint text | Deterministically parsed into allowed symptoms; **raw text never logged or emitted** |
| `triage.csv` | `acuity` | Emergency Severity Index (ESI 1–5) | Mapped to VitalNet tiers via `mimic_esi_v1` (1-2->EMERGENCY, 3->URGENT, 4-5->ROUTINE) |
| `triage.csv` | `resprate` | Respiratory rate in breaths/min | **STRICT: Isolated from model input (`form_data`)**; recorded in inspection metadata only |
| `triage.csv` | `pain` | Documented pain score (0–10 / text) | **STRICT: Isolated from model input (`form_data`)**; recorded in inspection metadata only |
| `edstays.csv` | `gender` | Stay-level administrative sex | **Primary sex source**. Mapped to `"male"` / `"female"` |
| `patients.csv` | `gender` | Patient-level demographic sex | **Fallback sex source** (used only if stay-level gender is missing). Disagreements tracked under `gender_conflict` |
| `patients.csv` | `anchor_age` | Patient anchor age (integer) | **Primary age source**. In MIMIC-IV, age $\ge 89$ is top-coded as integer `91` (HIPAA Safe Harbor). Preserved directly |

---

## 3. Strict Prohibited Tables & Temporal Leakage Prevention

To prevent temporal leakage and retrospective bias during triage-time evaluation, the adapter strictly prohibits post-triage and outcome data:

### 3.1 Prohibited Tables Constant (`PROHIBITED_TABLE_NAMES`)
Under no circumstances may any of the following tables be ingested or referenced:
1. `diagnosis` / `diagnosis.csv`: In-ED billing and clinical discharge diagnoses (established post-triage).
2. `pyxis` / `pyxis.csv`: Automated medication dispensing in the ED (administered post-triage).
3. `vitalsign` / `vitalsign.csv`: Longitudinal vital sign monitoring throughout the ED stay (creates severe temporal leakage).
4. `disposition`: Stay discharge disposition or mortality.
5. `admission` / `outcomes`: In-hospital admission, ICU transfer, or length of stay.

### 3.2 Prohibited Fields Constant (`PROHIBITED_FIELD_NAMES`)
The following fields are stripped *before* canonical patient record construction and must never appear in `form_data`, `raw_fields`, or output reports:
`hadm_id`, `outtime`, `disposition`, `length_of_stay`, `los`, `dod`, `anchor_year`, `anchor_year_group`.

---

## 4. Pre-Registered Target Mapping Contract: `mimic_esi_v1`

The primary benchmark target is frozen prior to result review:

| MIMIC Acuity (`triage.acuity`) | Clinical ESI Severity | VitalNet Benchmark Tier | Handling & Governance |
|---|---|---|---|
| `1` | Resuscitation (Immediate life threat) | `EMERGENCY` | Pre-registered primary target mapping |
| `2` | Emergent (High risk, acute distress) | `EMERGENCY` | Pre-registered primary target mapping |
| `3` | Urgent (Moderate risk, $\ge 2$ resources) | `URGENT` | Pre-registered primary target mapping |
| `4` | Less Urgent / Semi-urgent (1 resource) | `ROUTINE` | Pre-registered primary target mapping |
| `5` | Non-urgent (0 resources) | `ROUTINE` | Pre-registered primary target mapping |
| Other / Missing | Null, 0, >5, or unrecorded | Excluded | Tracked in `invalid_or_missing_acuity` exclusion counter |

---

## 5. Input Arms & Contract Definitions

### 5.1 Primary Benchmark Arm: `mimic_triage_contract_v1`
Passes strictly the available triage-time parameters:
- `patient_age`: `patients.anchor_age` (integer, preserving `91` top-coding).
- `patient_sex`: `edstays.gender` (fallback: `patients.gender`).
- `temperature`: `triage.temperature` (°F -> °C).
- `heart_rate`: `triage.heartrate` (bpm).
- `bp_systolic`: `triage.sbp` (mmHg).
- `bp_diastolic`: `triage.dbp` (mmHg).
- `spo2`: `triage.o2sat` (%).
- `chief_complaint`: `triage.chiefcomplaint` (bounded string).
- `symptoms`: Allow-list symptoms deterministically parsed from `chiefcomplaint`.
- **Explicit Uninvented ASHA Placeholders**: `complaint_duration=""`, `location=""`, `known_conditions=""`, `current_medications=""`, `is_pregnant=None`, `observations=""`.

### 5.2 Hard-Disabled Medication Arm: `mimic_full_available_context_v1`
- **Status: HARD-DISABLED / REFUSED BY DEFAULT.**
- `medrecon.charttime` records medication reconciliation entry time, which does not prove availability at the triage instant.
- Gate M4 authorization alone **does not** unlock this arm.
- Unlocking requires a separate temporal-eligibility study and explicit dual authorization (`gate_medrecon_temporal_authorized=True`).

---

## 6. Deterministic Symptom Parser Contract (`mimic_symptom_parser_v1`)

Unstructured chief complaints are parsed into VitalNet's 12 canonical `ALLOWED_SYMPTOMS` using a 100% deterministic, rule-based keyword/regex parser (`mimic_symptom_parser.py`):
1. `chest_pain`
2. `breathlessness`
3. `altered_consciousness`
4. `severe_bleeding`
5. `seizure`
6. `high_fever`
7. `severe_abdominal_pain`
8. `persistent_vomiting`
9. `severe_headache`
10. `weakness_one_side`
11. `difficulty_speaking`
12. `swelling_face_throat`

**Zero-Leakage Guarantee**: Raw complaint text is never included in output logs, error messages, or JSON reports. Only aggregate parser coverage counts and per-symptom distributions are reported.

---

## 7. Pre-Registered Cohort Policies

To prevent post-hoc cohort tuning:
1. **`all_stays` (Primary Benchmark)**:
   - Evaluates all eligible `stay_id` encounters.
   - Audits repeated visits per `subject_id` in aggregate inspection metadata.
2. **`first_stay_only` (Pre-Registered Sensitivity)**:
   - Evaluates only the first chronological stay per `subject_id`.
   - Excluded subsequent stays are tracked under `duplicate_subject_excluded`.

---

## 8. Staged Authorization Gates & Stop Conditions

```
[Gate M0: CITI + PhysioNet DUA Approval]
                │
                ▼
[Gate M1: Code-Only Adapter & Synthetic Fixture PR]  ◄── (CURRENT STAGE)
                │
                ▼
[Gate M2: Explicit Authorization for Download & Local Inspection]
                │
                ▼
[Gate M3: Review of Aggregate Data Quality & Linkage Report]
                │
                ▼
[Gate M4: Explicit Human Authorization for Frozen-Model Score]
                │
                ▼
[Gate M5: Review of Score Limitations (No Promotion to Test/Preprod)]
```

### Stop Conditions:
1. Acuity field missing or mapped differently than `mimic_esi_v1`.
2. Age linkage cannot be established without temporal leakage.
3. Symptom parser depends on an external service or cloud LLM.
4. Post-triage data (`vitalsign`, `diagnosis`, `pyxis`, `disposition`) enters model input.
5. Repeated-subject visit contamination is not tracked.
6. Credentialed files or raw patient data are committed or transmitted to any cloud service.
7. Patient-level identifiers, free text, or individual predictions appear in output reports.

---

## 9. Population Limitations & Clinical Non-Claims

1. **Tertiary US Hospital ED Cohort Bias**: MIMIC-IV-ED reflects acute presentations at a single major urban academic medical center in Boston, MA. Disease epidemiology, resource availability, and baseline health characteristics differ fundamentally from rural Indian primary healthcare.
2. **ESI Acuity vs Frontline Rural Triage**: ESI acuity is based on projected resource utilization and acute physician evaluation, not community health worker (ASHA) syndromic triage.
3. **Partial Presentation Caveat**: Frontline rural community features (pregnancy status, rural endemic exposures, duration of illness) are absent in standard tertiary ED triage.
4. **Non-Equivalence to Clinical Trial**: Offline validation on MIMIC-IV-ED evaluates algorithmic discrimination and safety net behavior; it does not constitute clinical safety certification, SaMD clearance, or prospective clinical trial validation.
