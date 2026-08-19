# VitalNet Safety Remediation Design: Missing-Context & Under-Triage Mitigation

> **Status**: Tracked Design & Governance Specification (Design-Only — Production Code & Models Frozen)
> **Applies to**: Future Candidate Triage Models, Candidate Input Contracts, Frontline Intake Workflows, and External Validation Frameworks
> **Related Documents**: `docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md`, `docs/EVALUATION_DATA_BOUNDARY.md`, `docs/evaluation/PUBLIC_DATA_EVALUATION_CLOSURE.md`, `docs/evaluation/KTAS_2019_SOURCE_CARD.md`, `docs/evaluation/NHAMCS_2022_SOURCE_CARD.md`, `docs/CLINICAL_RISK_MANAGEMENT.md`, `docs/CLINICAL_GOVERNANCE.md`, `backend/app/ml/MODEL_CARD.md`.

---

## 1. Executive Summary & Problem Statement

Across VitalNet's completed public-data external evaluation cycle and synthetic ablation studies, an acute, systematic safety failure mode was empirically demonstrated:

> **Core Failure Mode**: **Severe Emergency Under-Triage under Missing Clinical Context**.
> When patient encounters lack structured symptoms, free-text chief complaints, or complete physiological observations, the frozen production triage inference engine defaults toward lower-acuity classifications (`URGENT` or `ROUTINE`), under-triaging true emergency presentations at unacceptable rates in evaluated cohorts.

This document establishes the formal **Safety Remediation Design** for VitalNet. It synthesizes the empirical evidence, specifies a missing-context policy for frontline intake, defines candidate architectural remediations (as proposals for future investigation), pre-registers evaluation arms and safety metrics, and institutes strict clinical governance boundaries.

---

## 2. Empirical Evidence Base

The under-triage failure mode was verified across two independent international real-world emergency cohorts and a comprehensive 16-arm synthetic ablation study:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              EMPIRICAL EVIDENCE SUMMARY                                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. CDC NHAMCS 2022 (Gate 1B Proxy Evaluation — 16,025 Inspected / 10,207 Evaluated)    │
│    • Emergency Sensitivity: 14.4% in vital-only partial-input mode.                    │
│    • Emergency Miss Rate: 85.6% of proxy-emergency encounters under-triaged.          │
│    • Finding: When chief complaints and structured symptoms are omitted, vital signs   │
│      alone fail to trigger emergency classification in the vast majority of cases.    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. Korean KTAS 2019 (Gate 3A Benchmark — N = 1,267 Encounters / 563 Complete Vitals)   │
│    • Primary Contract (ktas_triage_contract_v1): 25.2% Emergency Sensitivity           │
│      (95% Wilson CI: 20.2% – 31.0%; 184 of 246 emergencies missed / 74.8% miss rate).  │
│    • Primary Overall Under-Triage: 372 / 1,267 = 29.36%.                               │
│    • Vital-Only Sensitivity Arm (ktas_vital_only_partial_v1): 17.9% Emergency Sens.    │
│      (95% Wilson CI: 13.6% – 23.2%; 202 of 246 emergencies missed / 82.1% miss rate).  │
│    • Vital-Only Overall Under-Triage: 531 / 1,267 = 41.91%.                            │
│    • Impact of Removing Symptoms: 7.3 percentage-point drop in emergency sensitivity,  │
│      and ~12.5 percentage-point increase in overall under-triage (12.55 pp).           │
│    • Site Limitation: All 563 complete-five-vital records (44.44%) are confined to    │
│      Regional ED Group 2 (579 total); Local ED Group 1 (688 total) had zero numeric    │
│      SpO2 measurements.                                                                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 3. Synthetic Frozen-Model ASHA Input-Contract Study (16 Controlled Ablation Arms)     │
│    • Baseline with Full Structured Symptoms: 99.13% Emergency Sensitivity.             │
│    • Removing Structured Symptoms: Sensitivity dropped to 86.01% (NHAMCS-like: 84.20%).│
│    • Field Role Differentiation: `observations` was completely inert in the tested    │
│      classifier/rules path; `current_medications` did not alter base triage tiers but  │
│      materially drives contraindication-review flags; structured symptoms and five     │
│      vitals carry the primary predictive weight.                                       │
│    • Missingness Hazard: Missing vital signs defaulting or treated as normal creates   │
│      silent downward acuity drift.                                                     │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Strict Boundary: Frozen Production Baseline vs. Future Candidate Systems

To preserve system integrity, auditability, and regulatory compliance:

1. **Production System Immutability (Frozen Baseline)**:
   - The production classifier (`backend/app/ml/models/triage_classifier.pkl`), browser-side decision trees (`apps/web/public/models/triage_trees.json`), feature configurations (`features_config.json`), deterministic safety rules (`packages/clinical-core/src/rules/**`), backend API routes, and database schemas remain **100% frozen and unmodified**.
   - Zero retraining, parameter tuning, weight adjustment, threshold modification, or runtime code changes are performed in this design package.
2. **Candidate System Designation**:
   - Any remediation model, restructured input schema, or modified inference pipeline is designated strictly as a **Future Candidate System**.
   - Proposed features (such as indeterminate states or guided symptom prompts) are design proposals for future candidate evaluation, **not active runtime behaviors of the current production system**.

---

## 4. Missing-Context Policy & Field Utilization Contract

In frontline healthcare delivery (e.g., ASHA community health workers and Primary Health Centre medical officers), clinical data is frequently incomplete due to equipment availability, patient distress, or operational context.

### 4.1 Non-Negotiable Missing-Context Principle
> **The Absence of Documented Derangement is NOT Evidence of Physiological Stability.**
> When clinical context (symptoms, complaints, vital signs) is uncollected or missing, a candidate triage system MUST NEVER silently assume normality, impute median/healthy values, or default the patient to a low-acuity tier (`ROUTINE`).

### 4.2 Frontline ASHA / PHC Field Ingestion Matrix (Proposed Candidate Specification)

The following table defines the proposed field handling for future candidate contracts:

| Intake Field Name | ASHA Workflow Role | Model / Rules Role | Missingness Safety Policy (Proposed Candidate Behavior) |
|---|---|---|---|
| `patient_age` | Mandatory / Required | Core Feature (`patient_age`) | Fail-closed: Candidate evaluation requires age. |
| `patient_sex` | Mandatory / Required | Core Feature (`patient_sex`) | Fail-closed: Must be specified (`male` / `female`). |
| `bp_systolic` | Core Vital (When equipment available) | Core Feature (`bp_systolic`, Shock Index, NEWS2) | If unmeasured: Tracked as missing; cannot contribute to stability evidence. |
| `bp_diastolic` | Core Vital (When equipment available) | Core Feature (`bp_diastolic`, MAP) | If unmeasured: Inverted or missing BP treated as incomplete. |
| `heart_rate` | Core Vital (Mandatory) | Core Feature (`heart_rate`, Shock Index, NEWS2) | If unmeasured: NEWS2 calculation flagged as partial. |
| `temperature` | Core Vital (Mandatory) | Core Feature (`temperature`, Fever rules) | If unmeasured: Fever safety rules cannot clear. |
| `spo2` | Core Vital (When oximeter available) | Core Feature (`spo2`, Hypoxia rules) | If unmeasured: Hypoxia safety rules cannot clear. |
| `symptoms` | Mandatory Guided Checklist (Proposed) | Core Feature (12 Canonical Binary Indicators) | If empty: A future candidate should flag missing context or trigger an indeterminate state rather than assuming absence of danger signs. |
| `chief_complaint` | Optional Free Text | NLP Keyword Feature Map | If empty: System relies entirely on structured symptom declarations. |
| `complaint_duration` | Optional Field | Temporal Context | **No assumption of acute or chronic**: Unknown duration must remain unknown and contribute to insufficient-information handling or human review. |
| `is_pregnant` | Conditional (Childbearing age) | Obstetric Safety Rules | If unknown: Obstetric red flags evaluated if symptoms indicate pregnancy risk. |
| `current_medications` | Optional Field | Contraindication & Drug Review | Base triage tier is not altered, but missing medications should generate a prompt that drug contraindication review was skipped. |
| `known_conditions` | Optional Field | Comorbidity Attribution | If empty: No comorbidity risk adjustment applied. |
| `observations` | Optional Free Text | Clinical Briefing / Handoff | Completely inert in tested triage model/rules; preserved strictly for clinician handoff notes. |

---

## 5. Insufficient-Information Handling & Human Escalation (Proposed Architecture)

To prevent false reassurance and unsafe under-triage of incomplete presentations, future candidate architectures should incorporate explicit uncertainty and escalation pathways:

```
                          [Patient Intake Encounter]
                                      │
                                      ▼
                        [Completeness & Context Gate]
                                      │
               ┌──────────────────────┴──────────────────────┐
               ▼                                             ▼
     [Adequate Clinical Context]                 [Insufficient Information]
     (Vitals + Structured Symptoms)              (Missing vitals OR undeclared symptoms)
               │                                             │
               ▼                                             ▼
    [Rules Engine + ML Model]                   [Proposed Safety Fallback]
               │                                 • Proposed State: "INSUFFICIENT_INFORMATION_FOR_CDS"
               ├───────────────┐                 • Prohibits ROUTINE classification
               ▼               ▼                 • Guided ASHA prompt for danger signs
        [Agreement]     [Disagreement]           • Mandatory Human MO / RN Review
               │        (Model != Rules)                     │
               ▼               │                             ▼
      [Assigned Tier]          └────────────────► [Escalated Clinical Adjudication]
```

### 5.1 Proposed Candidate States & Vocabulary
To standardize future contracts, a consistent proposed vocabulary is defined below (requiring formal clinical and product governance approval prior to implementation):
- **Proposed Operational State**: `INSUFFICIENT_INFORMATION_FOR_CDS` (or `INDETERMINATE`).
  - *Definition*: Emitted when an encounter lacks essential structured symptom confirmation or has severe vital sparsity, indicating that algorithmic confidence is insufficient for clinical decision-support.
  - *Constraint*: A candidate system in this state must be prohibited from outputting `ROUTINE` or displaying "Low Risk".
- **Proposed Symptom Declaration Contract**: `no_acute_danger_signs_declared`.
  - *Definition*: Explicit user confirmation that all 12 allow-listed red-flag symptoms were screened and confirmed absent, distinguishing active negative screening from omitted/blank input.

### 5.2 Proposed Human-Review Escalation Pathway
A future candidate architecture should define clear triggers for routing cases to human clinical review:
1. Low algorithmic confidence or high output entropy.
2. Divergence between deterministic safety rules (e.g., NEWS2 floor trigger) and statistical model predictions.
3. Incomplete intake presentations where critical danger signs cannot be ruled out.

*Note: These mechanisms are design proposals for future candidate evaluation. The current runtime does not route live queues or enforce new UI states.*

---

## 6. Candidate Remediation Options (Proposals for Future Research)

The following four options are proposed for investigation in future remediation studies (strictly non-implemented in this PR):

### Option 1: Mandatory Guided Structured Symptom Capture
- **Concept**: The remediation study will test whether requiring health workers to explicitly confirm or deny red-flag danger signs (rather than leaving symptom lists blank) eliminates the partial-input drop in emergency sensitivity.
- **Hypothesis**: Active negative confirmation converts implicit missingness into explicit clinical evidence, restoring emergency recall.

### Option 2: Dedicated "Insufficient Information" Operational State
- **Concept**: A future candidate should evaluate a 4th non-triage state (`INSUFFICIENT_INFORMATION_FOR_CDS`) that halts automated risk tiering when data is sparse and prompts the operator to complete required observations.
- **Hypothesis**: Prevents dangerous misclassification of sparse emergency encounters as routine.

### Option 3: Conservative Safe-Fail Escalation Policy
- **Concept**: The study will evaluate a deterministic floor rule where any encounter with partial vital signs or missing symptom declarations cannot be assigned lower than `URGENT` unless all measured parameters confirm stability.
- **Hypothesis**: Biases algorithmic failure toward conservative over-triage rather than catastrophic under-triage.

### Option 4: Dual-Engine Disagreement Flagging
- **Concept**: A future candidate should evaluate an explicit adjudication workflow whenever deterministic clinical rules (NEWS2, shock index, pediatric fever) diverge from statistical classifier predictions.
- **Hypothesis**: Prevents statistical models from overriding deterministic safety floors under out-of-distribution presentations.

---

## 7. Pre-Registered Evaluation Arms & Protocol

Any future candidate model or remediation contract must be evaluated against the following pre-registered arms:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             PRE-REGISTERED EVALUATION ARMS                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ ARM 1: Frozen Production Baseline                                                      │
│ • Configuration: triage_classifier.pkl + production rules engine                       │
│ • Input Contract: Standard full_input contract                                         │
│ • Role: Controls for baseline performance and historical benchmark reference.          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ ARM 2: Candidate Remediation Contract (Primary Intervention Arm)                        │
│ • Configuration: Candidate model / guided symptom capture / indeterminate state         │
│ • Input Contract: candidate_triage_contract_v1                                         │
│ • Role: Measures empirical remediation efficacy and emergency recall recovery.         │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ ARM 3: Vital-Only Sensitivity Arm (Stress Test / Worst-Case Missingness)               │
│ • Configuration: Candidate model with all symptom & text fields stripped               │
│ • Input Contract: vital_only_partial_v1 (chief_complaint="", symptoms=[])              │
│ • Role: Quantifies vital-sign-alone resilience under complete symptom omission.        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Safety Metrics & Evaluation Dimensions

All future candidate evaluations must compute and report the following standardized aggregate metrics:

### 8.1 Primary Safety Metrics
1. **EMERGENCY Sensitivity (Primary Safety Recall)**:
   $$\text{Sens}_{\text{EMERGENCY}} = \frac{\text{True EMERGENCY Predictions}}{\text{Total True EMERGENCY Reference Cases}}$$
   Reported with exact Wilson 95% score confidence intervals.
2. **EMERGENCY Miss Count & Miss Rate**:
   $$\text{Miss Rate}_{\text{EMERGENCY}} = 1.0 - \text{Sens}_{\text{EMERGENCY}} = \frac{\text{Under-triaged EMERGENCY Cases}}{\text{Total True EMERGENCY Cases}}$$
3. **Critical Two-Tier Drop Rate (EMERGENCY $\to$ ROUTINE)**:
   $$\text{Two-Tier Drop Rate} = \frac{\text{Reference EMERGENCY cases predicted as ROUTINE}}{\text{Total True EMERGENCY Cases}}$$
   *Measures the most dangerous failure mode (catastrophic under-triage).*
4. **Overall Under-Triage Rate**:
   $$\text{Under-Triage Rate} = \frac{\text{Encounters where Predicted Tier} < \text{Reference Tier}}{\text{Total Evaluated Encounters}}$$

### 8.2 Subgroup & Stratified Slices
Every evaluation must report performance stratified across:
- **Age Bands**: Pediatric ($<5$ years, $5–17$ years), Adult ($18–64$ years), Geriatric ($\ge 65$ years).
- **Biological Sex**: Female vs. Male (auditing sex-specific under-triage disparities).
- **Missingness Strata**: $0$ missing vitals, $1$ missing vital, $2$ missing vitals, $\ge 3$ missing vitals.
- **Symptom Availability**: Complete symptoms present vs. zero symptoms recorded.

### 8.3 Calibration & Guardrail Diagnostics
- **Confidence Distribution Diagnostic**: Evaluation of prediction entropy and class probability distributions across a pre-registered diagnostic grid (e.g., assessing the proportion of encounters falling below $\max P(\text{tier}) \in \{0.50, 0.60, 0.70, 0.80\}$). *Note: Any diagnostic grid threshold is strictly an exploratory engineering metric for distribution auditing, not a clinical acceptance threshold. Clinical pass/fail criteria remain exclusively owned and defined by qualified clinical governance.*
- **NEWS2 Floor Trigger Rate**: Frequency of deterministic NEWS2 overrides.
- **Safety Net Lift**: Difference in emergency sensitivity between raw ML predictions and the hybrid safety-net system.

---

## 9. Clinical Governance, Thresholds & Deployment Roadmap

### 9.1 Clinical Acceptance Thresholds Mandate
> [!IMPORTANT]
> **Prohibition on Arbitrary Engineering Thresholds**:
> Engineering teams MUST NOT invent, define, or unilaterally declare clinical pass/fail thresholds for emergency sensitivity or under-triage rates. All clinical acceptance criteria (including acceptable sensitivity floors and tolerable over-triage tradeoffs) must be formally defined and signed off by a **Qualified Medical Doctor / Clinical Governance Committee**. No clinical sign-off is claimed in this design-only document.

### 9.2 Staged Remediation Verification Roadmap

```
[Phase 1: Design & Problem Specification]  ◄── (CURRENT STAGE — PR AGAINST DEV)
                   │
                   ▼
[Phase 2: 100% Synthetic-First Test Suite Execution]
• Unit tests, boundary suites, adversarial generators, invariant assertions
                   │
                   ▼
[Phase 3: Separately Authorized Reruns on Acquired Public Data]
• Authorized via dataset-specific CLI flags (--gate-3a-scoring-authorized, Gate M4)
• Local execution only; zero patient leakage
                   │
                   ▼
[Phase 4: Clinical Review & Metric Acceptance Sign-Off]
• Formal adjudication with qualified clinician panel
                   │
                   ▼
[Phase 5: Silent / Shadow Deployment in Frontline Clinical Setting]
• Real-time parallel execution in rural Indian PHC without influencing patient care
• Comparison against live medical officer clinical decisions
                   │
                   ▼
[Phase 6: Prospective Clinical Trial & Regulatory Evaluation (CDSCO)]
```

### 9.3 Shadow-Deployment Requirement
Prior to any candidate model or remediation logic influencing clinical care, it must undergo a mandatory **Silent / Shadow Deployment Phase**:
- The candidate software executes in a frontline PHC environment, receiving live de-identified intake streams.
- Predictions and triage recommendations are logged strictly for retrospective audit and are **completely invisible to treating clinicians and patients**.
- Zero influence on clinical decisions, triage routing, or patient care is permitted during shadow deployment.

---

## 10. Explicit Limitations & Clinical Non-Claims

To maintain absolute ethical, clinical, and regulatory clarity:

1. **No Clinical Validation Claim**: This document and the associated evaluation harnesses do not constitute clinical validation, medical efficacy proof, or clinical trial evidence.
2. **No Regulatory Clearance**: VitalNet is an investigational software prototype. It has not received Software as a Medical Device (SaMD) clearance, CE mark, or approval from the Central Drugs Standard Control Organisation (CDSCO), US FDA, or any other medical regulatory authority.
3. **No Autonomous Triage**: VitalNet is strictly a clinical decision-support research tool. It does not provide autonomous clinical diagnosis or triage. All triage decisions must be made and verified by licensed human healthcare professionals.
4. **No Rural / ASHA Equivalence in Public Benchmarks**: External evaluations conducted on US hospital ED data (NHAMCS, MIMIC) or South Korean hospital ED data (KTAS) serve solely as algorithmic resilience and proxy physiological benchmarks. Foreign tertiary hospital cohorts do not reflect the disease epidemiology, malnutrition prevalence, baseline vitals, cultural presentation styles, or resource constraints of rural Indian primary care.
