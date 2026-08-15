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
| **Primary Citation** | Kashani et al. (2024), Retrospective Emergency Department Triage and Admission Dataset |
| **License** | Creative Commons Attribution 4.0 International (CC BY 4.0) |
| **Collection Setting** | Single-center tertiary academic hospital emergency department in Iran |
| **Primary File** | `triage.csv` (143,582 records) |
| **Optional Linkage File** | `ED_admission.csv` (linked on `triage_code`) |
| **Access Requirements** | Public open access; manual local placement under `tools/training/data/iran_ed/` |

---

## 2. Published Schema & Header Specifications

The primary triage dataset contains exactly 10 published headers (with exact case and spelling as published in the source release):

```csv
BlooddpressurSystol,BlooddpressurDiastol,PulseRate,Temperature,O2Saturation,ChiefComplaint,TriageGrade,CriticalStatus,NeedFastExecute,triage_code
```

### 2.1 Field Definitions & Target VitalNet Alignment

| Published Header | Raw Type | Description / Units | VitalNet Field Equivalent | Ingestion / Inspection Handling |
|---|---|---|---|---|
| `BlooddpressurSystol` | float / str | Systolic blood pressure (mmHg) | `bp_systolic` | Parsed for missingness & range; vital completeness check |
| `BlooddpressurDiastol` | float / str | Diastolic blood pressure (mmHg) | `bp_diastolic` | Parsed for missingness & range; vital completeness check |
| `PulseRate` | float / str | Heart rate (beats/min) | `heart_rate` | Parsed for missingness & range (0–240 bpm) |
| `Temperature` | float / str | Body temperature (°C) | `temperature` | Parsed for missingness & range (32.0–42.0°C) |
| `O2Saturation` | float / str | Pulse oximetry SpO₂ (%) | `spo2` | Parsed for missingness & range (0–100%) |
| `ChiefComplaint` | str | Free-text presenting complaint | `chief_complaint` | Parsed for presence only; **NEVER logged or exported in reports** |
| `TriageGrade` | int / str | Source triage grade (1, 2, 3, 4, 5) | Reference Acuity | Audited for distribution; published semantics are binary |
| `CriticalStatus` | int / str | Binary critical indicator (0 / 1) | Metadata | Inspection statistics |
| `NeedFastExecute` | int / str | Binary rapid execution flag (0 / 1) | Metadata | Inspection statistics |
| `triage_code` | int / str | Unique encounter identifier | Relational Key | Linkage key to `ED_admission.csv`; **omitted from reports** |

---

## 3. Audited Dataset Facts & Severe Sparsity Profile

A deep forensic analysis of the published 143,582 records reveals critical structural characteristics and severe data sparsity:

### 3.1 Total Triage Records
- Primary encounter volume: exactly **143,582 rows**.

### 3.2 Published Binary Triage Semantics
Although the source records integer `TriageGrade` values from 1 to 5, the hospital's operational and published research protocol operates on a **binary urgency framework**:
- **Grades 1 & 2 (Urgent / Critical)**: Resuscitation, life-threatening instability, or acute time-sensitive deterioration risk.
- **Grades 3, 4 & 5 (Non-Urgent)**: Stable, routine, or delayed emergency care presentations.

### 3.3 Severe Vital Missingness: The 91-Row Reality
In routine clinical practice at the source hospital, comprehensive vital sign sets were not recorded at triage for standard presentations; vitals were only documented conditionally (e.g., SpO₂ measured only if respiratory distress was noted, temperature measured only if fever was suspected).

| Vital Parameter | Audited Missingness Rate | Valid Populated Rows |
|---|---|---|
| `BlooddpressurSystol` | > 99.2% | ~1,100 rows |
| `BlooddpressurDiastol` | > 99.2% | ~1,100 rows |
| `PulseRate` | > 99.0% | ~1,400 rows |
| `Temperature` | > 99.5% | ~700 rows |
| `O2Saturation` | > 99.3% | ~1,000 rows |
| **Complete 5-Vital Set** (`SBP + DBP + HR + Temp + SpO₂`) | **> 99.93%** | **Exactly 91 rows** |

Only **91 out of 143,582 patients (< 0.07%)** possess a full set of the five standard physiological vitals required by deployed triage systems.

### 3.4 Admission Linkage (`ED_admission.csv`)
The secondary dataset `ED_admission.csv` provides hospital admission outcomes. When provided, the adapter calculates aggregate admission proportions across triage grades without exposing patient IDs.

---

## 4. Operational Role: Gate 1A Inspection-Only Analysis

Under VitalNet's multi-gate validation framework (`docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md`), the Iran ED dataset is designated exclusively for **Gate 1A: Inspection-Only and Sparse-Input Data Quality Analysis**.

### 4.1 Permitted Capabilities (`--inspect-source iran-ed`)
When invoked in inspection mode, the adapter produces an aggregate-only diagnostic report containing:
1. File verification, byte size, and SHA-256 cryptographic checksum.
2. Verification of the 10 published CSV column headers.
3. Total encounter count (verifying 143,582 rows).
4. Missingness statistics (count and percentage missing per column).
5. TriageGrade distribution across grades 1, 2, 3, 4, and 5.
6. Binary urgency summary (Grades 1–2 vs Grades 3–5).
7. Complete vital set count (identifying the 91 complete records).
8. Encounter linkage match rate against `ED_admission.csv` (if provided).

---

## 5. Mandatory Scoring Refusal Rationale (Non-Negotiable Invariant)

Attempting to run model evaluation, scoring, or accuracy assessment against the Iran ED dataset (`--source iran-ed` with evaluation flags) is **strictly prohibited**.

### 5.1 Refusal Enforcement & Verbatim Error Message
If evaluation or scoring is requested on the Iran ED dataset, the adapter MUST immediately raise `EvaluationRefusedError` and terminate execution with a **non-zero exit code (`sys.exit(1)`)**, outputting the exact verbatim error string:

```
Iran ED triage grade is binary in the published source and is unsupported for three-tier full-input evaluation; inspection/sparse-input analysis only.
```

### 5.2 Scientific & Clinical Refusal Rationale
1. **Incompatible Ground Truth Granularity**: VitalNet's clinical engine triages encounters into a 3-tier structure (`ROUTINE`, `URGENT`, `EMERGENCY`). The published Iran ED dataset provides binary labels (Urgent vs Non-urgent). Mapping a binary label to a 3-tier classifier requires fabricating clinical thresholds (e.g., arbitrarily deciding whether Non-urgent means `ROUTINE` or `URGENT`, or whether Urgent means `URGENT` or `EMERGENCY`), which produces unscientific and misleading sensitivity/under-triage metrics.
2. **Extreme Sparsity Precludes Generalizable Inference**: Evaluating 143,582 records where >99.9% of vital fields are blank would test missing-value imputation heuristics rather than genuine triage discrimination.
3. **Prohibition on Synthetic Imputation**: Imputing 99.9% missing vitals using statistical medians or mean values introduces severe artificial correlations that mask real-world failure modes.
4. **Prohibition on `predict_triage()` Execution**: The adapter must never invoke `predict_triage()` or the rules engine on Iran ED records.

---

## 6. Explicit Non-Claims & Safety Disclaimers

1. **No Clinical Safety Claim**: Inspection of the Iran ED dataset does not constitute evidence of clinical efficacy or safety.
2. **No Indian Healthcare Equivalence**: The single-center Iranian tertiary ED patient population, referral patterns, and admission criteria do not represent primary care in rural India or Accredited Social Health Activist (ASHA) community triage.
3. **Decision-Support Prototype Notice**: VitalNet is a clinical decision-support prototype. It is not an autonomous diagnostic device, and all predictions require qualified human clinical oversight.
