# Evaluation Source Card: Iran Emergency Department Dataset (Gate 1A)

> **Status**: Tracked Evaluation Specification
> **Gate Role**: Gate 1A — Inspection-Only and Sparse-Input Data Quality Analysis
> **Evaluation Mode**: Inspection Only (`--inspect-source iran-ed`). **Model scoring strictly refused.**
> **Related Documents**: `docs/EVALUATION_DATA_BOUNDARY.md`, `docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md`, `PROJECT.md`.

---

## 1. Dataset Overview & Provenance

| Property | Value |
|---|---|
| **Dataset Title** | Iranian Emergency Department Triage Dataset |
| **Authors** | BaniHassan et al. (2024) |
| **Official Mendeley Release** | [https://data.mendeley.com/datasets/vhzyyktrz5/1](https://data.mendeley.com/datasets/vhzyyktrz5/1) |
| **Dataset DOI** | [https://doi.org/10.17632/vhzyyktrz5.1](https://doi.org/10.17632/vhzyyktrz5.1) |
| **Associated Publication** | *Data in Brief* (2024), [https://doi.org/10.1016/j.dib.2024.110827](https://doi.org/10.1016/j.dib.2024.110827) |
| **License** | Creative Commons Attribution 4.0 International (CC BY 4.0) |
| **Collection Setting** | Single-center tertiary academic hospital emergency department in Iran |
| **Primary File** | `ED_triage.csv` (143,582 records, 28 columns in official release) |
| **Optional Linkage File** | `ED_admission.csv` (linked on `triage_code`) |
| **Access Requirements** | Public open access; manual local placement under `tools/training/data/iran_ed/` |

---

## 2. Published Schema & Header Specifications

The official Mendeley dataset release of `ED_triage.csv` contains **28 columns**. The VitalNet adapter dynamically parses all present columns and specifically consumes a clinical subset of **10 key fields** for data quality and sparsity inspection:

```csv
BlooddpressurSystol,BlooddpressurDiastol,PulseRate,Temperature,O2Saturation,ChiefComplaint,TriageGrade,CriticalStatus,NeedFastExecute,triage_code
```

Non-clinical administrative fields (e.g. arrival timestamps, insurance, attending IDs) in the broader 28-column release are safely bypassed during parsing.

### 2.1 Consumed Field Definitions & VitalNet Handling

| Published Header | Raw Type | Description / Units | VitalNet Field Equivalent | Ingestion / Inspection Handling |
|---|---|---|---|---|
| `BlooddpressurSystol` | float / str | Systolic blood pressure (mmHg) | `bp_systolic` | Parsed for missingness & range; vital completeness check |
| `BlooddpressurDiastol` | float / str | Diastolic blood pressure (mmHg) | `bp_diastolic` | Parsed for missingness & range; vital completeness check |
| `PulseRate` | float / str | Heart rate (beats/min) | `heart_rate` | Parsed for missingness & range (0–240 bpm) |
| `Temperature` | float / str | Body temperature (°C) | `temperature` | Parsed for missingness & range (32.0–42.0°C) |
| `O2Saturation` | float / str | Pulse oximetry SpO₂ (%) | `spo2` | Parsed for missingness & range (0–100%) |
| `ChiefComplaint` | str | Free-text presenting complaint | `chief_complaint` | Parsed for presence only; **NEVER logged or exported in reports** |
| `TriageGrade` | int / str | Source triage grade (1, 2, 3, 4, 5) | Reference Acuity | Audited for distribution; published semantics are binary |
| `CriticalStatus` | int / str | Critical status indicator | Metadata | Audited for distribution (contains substantial non-binary/other values) |
| `NeedFastExecute` | int / str | Rapid execution flag | Metadata | Audited for distribution (contains substantial non-binary/other values) |
| `triage_code` | int / str | Unique encounter identifier | Relational Key | Linkage key to `ED_admission.csv`; **omitted from reports** |

---

## 3. Audited Dataset Facts & Severe Sparsity Profile

A comprehensive inspection of the official 143,582 records confirms critical structural characteristics and severe clinical data sparsity:

### 3.1 Total Triage Records
- Primary encounter volume: exactly **143,582 rows**.

### 3.2 Published Binary Triage Semantics
Although the source records integer `TriageGrade` values from 1 to 5, the hospital's operational and research protocol operates on a **binary urgency framework**:
- **Grades 1 & 2 (Urgent / Critical)**: Resuscitation, life-threatening instability, or acute deterioration risk.
- **Grades 3, 4 & 5 (Non-Urgent)**: Stable, routine, or delayed emergency care presentations.

### 3.3 Status & Fast Execution Fields
The `CriticalStatus` and `NeedFastExecute` columns contain substantial non-binary and other values in this release (including unclassified/empty entries). These fields are tracked strictly as inspection metadata and are **not used** to construct a three-tier scoring ground truth.

### 3.4 Severe Vital Missingness: The 91-Row Reality
In routine clinical triage at the source hospital, vital signs were documented selectively based on clinical presentation. Audited missingness across the 143,582 records:

| Vital Parameter | Audited Missingness Rate | Valid Populated Rows |
|---|---|---|
| `BlooddpressurSystol` (SBP) | **82.82%** | ~24,670 rows |
| `BlooddpressurDiastol` (DBP) | **82.62%** | ~24,950 rows |
| `PulseRate` (Heart Rate) | **75.47%** | ~35,220 rows |
| `Temperature` | **99.90%** | ~140 rows |
| `O2Saturation` (SpO₂) | **73.77%** | ~37,660 rows |
| **Complete 5-Vital Set** (`SBP + DBP + HR + Temp + SpO₂`) | **> 99.93%** | **Exactly 91 rows** |

Only **91 out of 143,582 patients (< 0.07%)** possess a complete set of the five standard physiological vitals required by deployed triage systems.

### 3.5 Admission Linkage (`ED_admission.csv`)
When linked with `ED_admission.csv`, the relational match rate between primary encounter `triage_code` and admission keys is **99.91%**. Aggregate admission proportions across triage grades are computed without exposing individual patient IDs.

---

## 4. Operational Role: Gate 1A Inspection-Only Analysis

Under VitalNet's multi-gate validation framework (`docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md`), the Iran ED dataset is designated exclusively for **Gate 1A: Inspection-Only and Sparse-Input Data Quality Analysis**.

### 4.1 Permitted Capabilities (`--inspect-source iran-ed`)
When invoked in inspection mode, the adapter produces an aggregate-only diagnostic report containing:
1. File verification, byte size, and SHA-256 cryptographic checksum.
2. Verification of the detected and consumed column headers.
3. Total encounter count (143,582 rows).
4. Missingness statistics (count and percentage missing per column).
5. TriageGrade distribution across grades 1, 2, 3, 4, and 5.
6. Binary urgency summary (Grades 1–2 vs Grades 3–5).
7. Complete vital set count (91 complete records).
8. Encounter linkage match rate against `ED_admission.csv` (99.91%).

---

## 5. Mandatory Scoring Refusal Rationale (Non-Negotiable Invariant)

Attempting to run model evaluation, scoring, or accuracy assessment against the Iran ED dataset (`--source iran-ed` or `--dataset iran-ed` with evaluation flags) is **strictly prohibited**.

### 5.1 Refusal Enforcement & Verbatim Error Message
If evaluation or scoring is requested on the Iran ED dataset, the adapter MUST immediately raise `EvaluationRefusedError` and terminate execution with a **non-zero exit code (`sys.exit(2)`)**, outputting the exact verbatim error string:

```
Iran ED triage grade is binary in the published source and is unsupported for three-tier full-input evaluation; inspection/sparse-input analysis only.
```

### 5.2 Scientific & Clinical Refusal Rationale
1. **Incompatible Ground Truth Granularity**: VitalNet triages encounters into a 3-tier structure (`ROUTINE`, `URGENT`, `EMERGENCY`). The published Iran ED dataset provides binary labels (Urgent vs Non-urgent). Mapping a binary label to a 3-tier classifier requires fabricating clinical thresholds, which produces unscientific and misleading sensitivity/under-triage metrics.
2. **Extreme Sparsity Precludes Generalizable Inference**: Evaluating 143,582 records where temperature is missing in 99.90% of cases and only 91 rows have complete vitals would test missing-value imputation heuristics rather than genuine triage discrimination.
3. **Prohibition on Synthetic Imputation**: Imputing missing vitals using statistical medians or mean values introduces artificial correlations that mask real-world failure modes.
4. **Prohibition on `predict_triage()` Execution**: The adapter must never invoke `predict_triage()` or the rules engine on Iran ED records.

---

## 6. Explicit Non-Claims & Safety Disclaimers

1. **No Clinical Safety Claim**: Inspection of the Iran ED dataset does not constitute evidence of clinical efficacy or safety.
2. **No Indian Healthcare Equivalence**: The single-center Iranian tertiary ED patient population, referral patterns, and admission criteria do not represent primary care in rural India or Accredited Social Health Activist (ASHA) community triage.
3. **Decision-Support Prototype Notice**: VitalNet is a clinical decision-support prototype. It is not an autonomous diagnostic device, and all predictions require qualified human clinical oversight.
