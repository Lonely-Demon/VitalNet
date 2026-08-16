# VitalNet Safety Remediation Study Design: Missing Clinical Context & Emergency Under-Triage

> **Status**: Tracked Design-Only Specification (Remediation Study Proposal)
> **Baseline Model Status**: **Frozen Production Baseline** (`v3.1.0`). No model weights, thresholds, rules, API routes, or database schemas are modified in this study design.
> **Lifecycle Phase**: Post-Evaluation Remediation Design (Public-data retrospective evaluation cycle closed).
> **Related Documents**: `docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md`, `docs/EVALUATION_DATA_BOUNDARY.md`, `docs/CLINICAL_RISK_MANAGEMENT.md`, `docs/VALIDATION_PROTOCOL.md`, `docs/CLINICAL_GOVERNANCE.md`.

---

## 1. Executive Summary & Problem Statement

Across the completed public-data retrospective evaluation cycle (CDC NHAMCS 2022, Korean KTAS 2019, Iran ED inspection, and the synthetic ASHA input-contract study), VitalNet's evaluation evidence consistently demonstrated a **critical clinical safety failure mode: emergency under-triage when structured symptoms and clinical context are missing or unavailable**.

### 1.1 Empirical Evidence Summary

| Evidence Source | Evaluation Role | Empirical Result | Safety Implication |
|---|---|---|---|
| **CDC NHAMCS 2022 ED** (Gate 1B) | Partial-input vital-only proxy benchmark | Emergency Sensitivity: **14.4%**; Proxy-Emergency Miss Rate: **85.6%** | Severe under-triage when VitalNet receives only physiological vitals without chief complaint or symptoms. |
| **Korean KTAS 2019 ED** (Gate 3A) | Multi-center open ED acuity benchmark | Primary Arm Emergency Sensitivity: **25.2%** (95% Wilson CI: 20.2%–31.0%); Vital-Only Arm Sensitivity: **17.9%** (95% Wilson CI: 13.6%–23.2%) | Confirms emergency under-triage on real hospital presentations. Removing symptoms caused a 7.3 percentage point sensitivity drop and 12.5 percentage point under-triage increase. (563 complete-vital records confined to Regional ED). |
| **Iran ED (2024)** (Gate 1A) | Extreme-sparsity data quality audit | 143,582 encounters; only 91 complete 5-vital records (0.0634%); binary labels | Demonstrates that real-world clinical triage data suffers from extreme vital missingness. Scoring permanently refused. |
| **Synthetic ASHA Input-Contract Study** | Controlled ablation on 36,000 synthetic patients | Removing structured symptoms reduced emergency sensitivity from **99.13% to 86.01%** (and **84.20%** in NHAMCS-like arm); removing observations/medications caused **0 tier changes** | Confirms that structured symptoms are load-bearing in the model's feature space, while free-text observations have zero influence on triage tier assignment. |

### 1.2 The Core Problem: The "Silent Baseline" Fallacy
When an encounter presents with abnormal or borderline vitals but without explicit structured symptoms or complaint narrative, the machine learning classifier and baseline rules frequently default to assigning `ROUTINE` or `URGENT` triage. In high-acuity clinical scenarios (such as early sepsis, silent myocardial infarction, atypical stroke, or compensated pediatric shock), physiological vitals alone may appear borderline while the patient is in critical danger. Treating missing context as "normal" or "low risk" creates an unacceptable rate of high-acuity under-triage.

---

## 2. Strict Separation: Frozen Baseline vs Candidate Proposals

To prevent unauthorized system drift and ensure scientific reproducibility, this document establishes a strict boundary between the active production baseline and any future candidate models or input contracts:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ FROZEN PRODUCTION BASELINE (Active Invariant)                                │
├──────────────────────────────────────────────────────────────────────────────┤
│ - Model Artifact: backend/app/ml/models/triage_classifier.pkl (v3.1.0)       │
│ - JS Tree Model: apps/web/public/models/triage_trees.json (v3.1.0)           │
│ - Rules Engine: packages/clinical-core/src/rules/ (NEWS2, Shock Index, etc.) │
│ - Input Contract: Accepts empty symptoms and empty complaints without error │
│ - Status: 100% IMMUTABLE during design and evaluation phases                 │
└──────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼ (Compared via Pre-Registered Arms)
┌──────────────────────────────────────────────────────────────────────────────┐
│ FUTURE CANDIDATE REMEDIATION PROPOSALS (Research & Study Design Only)        │
├──────────────────────────────────────────────────────────────────────────────┤
│ - Candidate Input Contracts (e.g., Mandatory Symptom Selection)              │
│ - Candidate Triage Policies (e.g., Explicit Insufficient Information State)  │
│ - Candidate Conservative Escalation & Floor Guardrails                       │
│ - Status: DESIGN PROPOSALS ONLY — NOT IMPLEMENTED IN RUNTIME PATHS           │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Field Categorization & Missing-Context Policy

### 3.1 ASHA / PHC Field Hierarchy

To eliminate ambiguity regarding data expectations, intake fields in the VitalNet frontline workflow are classified into three operational categories:

```
                     ┌────────────────────────────────────────┐
                     │         ASHA / PHC INTAKE FIELDS       │
                     └────────────────────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌──────────────────┐       ┌──────────────────┐        ┌──────────────────┐
│ REQUIRED FIELDS  │       │ OPTIONAL VITALS  │        │ UNAVAILABLE /    │
│ (Mandatory Data) │       │ & CONTEXT        │        │ NOT CAPTURED     │
├──────────────────┤       ├──────────────────┤        ├──────────────────┤
│ - patient_age    │       │ - temperature    │        │ - Respiratory    │
│ - patient_sex    │       │ - heart_rate     │        │   rate (no kit)  │
│ - chief_complaint│       │ - bp_systolic    │        │ - Numeric pain   │
│ - symptoms (>=1  │       │ - bp_diastolic   │        │   scale (0-10)   │
│   or explicit    │       │ - spo2           │        │ - Lab values     │
│   'none_declared'│       │ - observations   │        │ - Prior EHR      │
│ - consent        │       │ - medications    │        │   longitudinal   │
│                  │       │ - known_conds    │        │   history        │
│                  │       │ - duration       │        │                  │
└──────────────────┘       └──────────────────┘        └──────────────────┘
```

1. **Required Intake Fields (Mandatory Contract)**:
   - `patient_age`: Integer age in years.
   - `patient_sex`: Biological sex (`"male"`, `"female"`).
   - `chief_complaint`: Primary clinical reason for encounter.
   - `symptoms`: Structured selection of canonical danger signs (at least one positive selection, or an explicit active declaration of `"no_danger_signs_present"`).
   - `consent`: Explicit patient/guardian consent record.

2. **Optional Vitals & Context Fields**:
   - Physiological vitals: `temperature`, `heart_rate`, `bp_systolic`, `bp_diastolic`, `spo2`. (Optional because ASHA workers may lack a functioning device in the field).
   - Descriptive context: `observations`, `current_medications`, `known_conditions`, `complaint_duration`.

3. **Unavailable / Not Captured Fields in Frontline Setting**:
   - `respiratory_rate`: Standard ASHA diagnostic kits do not include automated capnography or standardized timer hardware; manual counts exhibit extreme variance.
   - Numeric pain scales (`NRS_pain` 0–10): Not culturally standardized across rural community health surveys.
   - Laboratory, imaging, and post-triage diagnostic data.

### 3.2 Missing-Context Policy: Prohibition on "Silent Routine"
1. **No Silent Routine Assumption**: If an encounter lacks structured symptoms and chief complaint text, the system must **never** treat missing fields as evidence of physiological normalcy or assign `ROUTINE` by default.
2. **Explicit Insufficient Information Behavior**: If minimum required context is absent, the system must explicitly designate the encounter as `INSUFFICIENT_INFORMATION` or require mandatory human clinical review.

---

## 4. Human-Review & Escalation Pathway

For encounters exhibiting severe missingness, clinical ambiguity, or high-risk vital abnormalities without explanatory symptoms, VitalNet establishes a structured human escalation protocol:

```
[Patient Intake Presentation]
              │
              ▼
   [Completeness & Safety Check]
              │
     ┌────────┴────────┐
     ▼                 ▼
[Complete Data]  [Missing Symptoms / Ambiguous Vitals / Rule Disagreement]
     │                 │
     ▼                 ▼
[Standard CDS]   [TRIGGER CLINICAL ESCALATION PATHWAY]
                 ├── Flag: "INSUFFICIENT_INFORMATION_FOR_CDS"
                 ├── Visual Alert: Highlight missing vitals & unselected symptoms
                 ├── Action: Route directly to PHC Medical Officer Pending Queue
                 └── Mandatory: Require Human Clinician Confirmation before disposition
```

### 4.1 Clinician BriefingCard Enhancements
When an escalated case is reviewed by the PHC Doctor:
1. **Uncertainty Banner**: The card displays an explicit notice: `"High Missingness: Triage recommendation confidence degraded due to absent symptom context."`
2. **Missingness Audit**: Displays a breakdown of which parameters were measured vs unrecorded.
3. **Override & Feedback Loop**: The doctor records the true clinical acuity and rationale, creating an audit trail for continuous quality improvement.

---

## 5. Candidate Safety Remediation Proposals (Design-Only Options)

The following four candidate remediation strategies are proposed for future empirical study. **None of these options are implemented in active production code in this PR.**

### Option A: Mandatory Structured Symptom Capture & Validation
- **Concept**: Update frontline intake validation to require explicit selection from the 12 allow-listed symptom danger signs or an active single-click declaration (`"no_acute_danger_signs_observed"`).
- **Rationale**: Eliminates accidental omission of symptom tags by ASHA workers, ensuring the ML model receives complete feature vectors.

### Option B: Explicit "Insufficient Information" / Indeterminate Triage State
- **Concept**: Decouple low-information encounters from standard 3-tier classification. If vital completeness is $<40\%$ and zero symptoms are selected, output an `INDETERMINATE` / `REQUIRES_CLINICAL_TRIAGE` status.
- **Rationale**: Prevents giving frontline workers false reassurance on un-evaluated high-risk presentations.

### Option C: Conservative Escalation Heuristics (Floor Guardrails)
- **Concept**: Introduce conservative floor rules for vital-only presentations (e.g., if any single vital exceeds Grade 2 severity on NEWS2, enforce an automatic floor of `URGENT` or `EMERGENCY` regardless of ML model probability).
- **Rationale**: Direct safety net that catches physiologically unstable patients even when the machine learning model fails to recognize the pattern without symptoms.

### Option D: Systematic Rule-Model Disagreement Escalation
- **Concept**: Whenever the deterministic clinical rules (e.g., pediatric fever rule, shock index) assign a higher acuity tier than the raw ML classifier, automatically flag the case for priority doctor review and explain the disagreement in `BriefingCard`.
- **Rationale**: Exploits the deterministic guardrail to rescue machine learning under-triage cases while training clinicians on model behavior.

---

## 6. Pre-Registered Evaluation Arms

Any future candidate model or input-contract modification must be evaluated across three pre-registered comparative arms:

| Evaluation Arm | Designation | Input Contract Specification | Purpose |
|---|---|---|---|
| **Arm 1: Frozen Baseline** | `frozen_baseline_v3.1.0` | Active production model + current permissive schema | Control baseline for all comparative statistics |
| **Arm 2: Candidate Remediation** | `candidate_remediation_v1` | Candidate input contract / candidate model / floor rules | Primary experimental arm evaluating safety improvement |
| **Arm 3: Vital-Only Sensitivity** | `vital_only_partial_stress` | Strictly vitals only (empty symptoms, empty complaint) | Stress-test measuring resilience against catastrophic data loss |

---

## 7. Pre-Registered Safety Metrics & Subgroup Strata

### 7.1 Primary and Secondary Safety Metrics

```
PRIMARY SAFETY METRIC:
  EMERGENCY Sensitivity (%) = [ True EMERGENCY / Total Reference EMERGENCY ] * 100
  (Goal: Maximize sensitivity; minimize missed acute emergencies)

CRITICAL SAFETY HAZARD METRICS:
  1. EMERGENCY Miss Rate (%) = [ Missed EMERGENCY / Total Reference EMERGENCY ] * 100
  2. Two-Tier Drop Rate (%) = [ Reference EMERGENCY predicted as ROUTINE / Total Reference EMERGENCY ] * 100
  3. Overall Under-Triage Rate (%) = [ Total Encounters Triaged Lower than Reference / Total Encounters ] * 100

SECONDARY METRICS (with Wilson 95% Confidence Intervals):
  - URGENT Sensitivity (%) & Specificity (%)
  - ROUTINE Specificity (%)
  - Positive Predictive Value (PPV) & Negative Predictive Value (NPV)
  - Diagnostic Expected Calibration Error (ECE)
  - Deterministic Guardrail Lift (Percentage point increase in EMERGENCY sensitivity attributable to rules)
```

### 7.2 Pre-Registered Subgroup Strata
All evaluation arms must report metrics stratified across:
1. **Age Bands**:
   - Infant / Toddler: $<5$ years
   - Child / Adolescent: $5–17$ years
   - Adult: $18–64$ years
   - Geriatric: $\ge 65$ years
2. **Biological Sex**: Male vs Female.
3. **Vital Sign Completeness**:
   - Complete 5-Vital Set (`temperature + heart_rate + sbp + dbp + spo2`)
   - Partial Vital Set (1 to 4 vitals present)
   - Zero Vitals Present
4. **Symptom Presence Strata**:
   - Structured symptoms present ($\ge 1$ symptom)
   - Zero symptoms present (vital-only presentation)

---

## 8. Clinical Acceptance Thresholds: Clinician Review Requirement

> [!IMPORTANT]
> **Strict Governance Mandate**: Engineering teams are **strictly prohibited** from unilaterally defining or inventing clinical acceptance thresholds (e.g., declaring that "85% emergency sensitivity is clinically safe").

### 8.1 Qualified Clinician Sign-Off Protocol
Prior to any decision to promote a remediated model or policy to preproduction:
1. **Formal Review Panel**: A qualified physician (Emergency Medicine specialist or Indian Public Health / Primary Care Medical Officer) must review the cross-dataset empirical findings and remediation study design.
2. **Context-Specific Acceptance Thresholds**: The clinical reviewer must formally establish:
   - The minimum acceptable `EMERGENCY` sensitivity threshold for the intended ASHA/PHC operational context.
   - The maximum tolerable two-tier drop rate (`EMERGENCY` $\rightarrow$ `ROUTINE`).
   - The acceptable trade-off between over-triage (facility burden) and under-triage (patient safety risk).
3. **Documented Clinical Review Record**: The defined thresholds and clinical justification must be committed to `docs/CLINICAL_REVIEW.md` with reviewer credentials.

---

## 9. Staged Validation Staging & Execution Roadmap

```
[Phase 1: Remediation Study Design PR] ◄── (CURRENT PHASE: Design Only)
                  │
                  ▼
[Phase 2: Synthetic-First Verification]
 - Programmatic ablation on 36k synthetic cohort
 - Parity validation across JS evaluator and Python classifier
 - Edge-case unit testing on missing-context boundaries
                  │
                  ▼
[Phase 3: Authorized Public Dataset Reruns]
 - Separately authorized reruns on CDC NHAMCS and Korean KTAS
 - Comparative evaluation: Arm 1 vs Arm 2 vs Arm 3
 - Zero patient data committed; aggregate JSON outputs only
                  │
                  ▼
[Phase 4: Clinician Review & Acceptance Evaluation]
 - Independent review of comparative metrics by qualified clinician
 - Sign-off on predefined clinical acceptance criteria
                  │
                  ▼
[Phase 5: Prospective Silent / Shadow Deployment]
 - Execution in real-world Indian PHC setting in parallel with standard care
 - Zero influence on clinical treatment or referral decisions
 - Prospective validation of ASHA usability and true clinical sensitivity
```

---

## 10. Explicit Non-Claims & Safety Disclaimers

1. **No Clinical Safety Claim**: This document is an engineering study design and does not constitute evidence of clinical safety, algorithmic efficacy, or diagnostic accuracy.
2. **No Regulatory Clearance**: VitalNet has not been cleared, approved, or certified by the Central Drugs Standard Control Organisation (CDSCO), the US Food and Drug Administration (FDA), or any medical device regulatory agency.
3. **No Autonomous Decision-Making**: VitalNet is strictly a clinical decision-support prototype. It does not provide autonomous clinical triage, diagnosis, or treatment recommendations. All recommendations require verification by a licensed human healthcare provider.
4. **No Direct Equivalence**: Retrospective public hospital datasets (NHAMCS, KTAS, MIMIC-IV-ED) do not match the disease prevalence, demographic profile, infrastructure limitations, or presentation timelines of rural Indian primary healthcare.
