# VitalNet Safety Remediation Design: Missing-Context & Under-Triage Mitigation

> **Status**: Tracked Design & Governance Specification (Design-Only — Production Code & Models Frozen)
> **Applies to**: Future Candidate Triage Models, Input Contracts, Frontline Intake Workflows, and External Validation Frameworks
> **Related Documents**: `docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md`, `docs/EVALUATION_DATA_BOUNDARY.md`, `docs/CLINICAL_RISK_MANAGEMENT.md`, `docs/CLINICAL_GOVERNANCE.md`, `backend/app/ml/MODEL_CARD.md`.

---

## 1. Executive Summary & Problem Statement

Across VitalNet's completed public-data external validation cycle and synthetic ablation studies, an acute, systematic safety failure mode was empirically demonstrated:

> **Core Failure Mode**: **Severe Emergency Under-Triage under Missing Context**.
> When patient encounters lack structured symptoms, free-text chief complaints, or complete physiological observations, the triage inference engine defaults toward lower-acuity classifications (`URGENT` or `ROUTINE`), failing to recognize life-threatening clinical emergencies.

This document establishes the formal **Safety Remediation Design** for VitalNet. It synthesizes the empirical evidence, specifies a rigorous missing-context policy, defines candidate architectural remediations (as proposals for future work), pre-registers evaluation arms and safety metrics, and institutes strict clinical governance boundaries.

---

## 2. Empirical Evidence Base

The under-triage failure mode was verified across two independent international real-world emergency cohorts and a comprehensive 16-arm synthetic ablation study:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              EMPIRICAL EVIDENCE SUMMARY                                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. CDC NHAMCS 2022 (Gate 1B Proxy Evaluation — N = 12,347 Encounters)                  │
│    • Emergency Sensitivity: 14.4% (Wilson 95% CI: 13.0% – 15.9%)                       │
│    • Emergency Miss Rate: 85.6% (1,848 of 2,159 true emergencies under-triaged)       │
│    • Finding: In vital-only partial-input mode, the production classifier misses       │
│      over 85% of acute emergencies because it lacks symptom & narrative NLP signals.  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. Korean KTAS 2019 (Gate 3A Benchmark — N = 1,267 Encounters / 563 Complete Vitals)   │
│    • Primary Contract (ktas_triage_contract_v1): 25.2% Emergency Sensitivity           │
│      (Wilson 95% CI: 19.3% – 32.2%; 97 of 130 emergencies missed / 74.8% miss rate)   │
│    • Vital-Only Sensitivity Arm (ktas_vital_only_partial_v1): 17.9% Emergency Sens.    │
│      (Wilson 95% CI: 12.8% – 24.4%; 105 of 128 emergencies missed / 82.1% miss rate)  │
│    • Finding: Even with allow-listed bilingual symptom parsing from chief complaints,  │
│      emergency sensitivity remains unacceptable (<26%); stripping symptoms drops it to │
│      17.9%, corroborating the NHAMCS safety signal.                                    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 3. Synthetic Frozen-Model ASHA Input-Contract Study (16 Controlled Ablation Arms)     │
│    • Full Input Baseline: >95% Emergency Sensitivity on synthetic test distributions.   │
│    • Symptom Stripping Ablation: Emergency sensitivity drops to ~15%–20%.              │
│    • Field Inertness Verification: Free-text `observations` and `patient_name` are     │
│      100% inert in triage inference; `current_medications` affects contraindications    │
│      only; five vitals + symptoms carry the entire predictive weight.                  │
│    • Missingness Hazard: Missing vital signs defaulting or treated as neutral creates  │
│      silent downward acuity drift.                                                     │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Strict Boundary: Frozen Production Baseline vs. Future Candidate Systems

To preserve system integrity, auditability, and regulatory compliance:

1. **Production System Immutability (Frozen Baseline)**:
   - The production classifier (`backend/app/ml/models/triage_classifier.pkl`), browser-side decision trees (`apps/web/public/models/triage_trees.json`), feature configurations (`features_config.json`), deterministic safety rules (`packages/clinical-core/src/rules/**`), backend API routes, and database schemas are **100% frozen and unmodified**.
   - Zero retraining, parameter tuning, weight adjustment, threshold modification, or code changes to runtime inference paths are permitted in this safety remediation design package.
2. **Candidate System Designation**:
   - Any remediation model, restructured input schema, or modified inference pipeline is designated strictly as a **Future Candidate System**.
   - Candidate systems must be developed in isolated research branches, verified against synthetic test gates, and separately authorized before any prospective shadow evaluation.

---

## 4. Missing-Context Policy & Field Utilization Contract

In frontline healthcare delivery (e.g., ASHA community health workers and Primary Health Centre medical officers), clinical data is frequently incomplete due to equipment constraints, patient distress, or operational urgency.

### 4.1 Non-Negotiable Missing-Context Principle
> **The Absence of Documented Derangement is NOT Evidence of Physiological Stability.**
> When clinical context (symptoms, complaints, vital signs) is uncollected or missing, the system MUST NEVER silently assume normality, impute median/healthy values, or default the patient to a low-acuity tier (`ROUTINE`).

### 4.2 Frontline ASHA / PHC Field Ingestion Matrix

| Intake Field Name | ASHA Workflow Classification | Model Feature Utilization | Triage Influence | Missingness Safety Policy |
|---|---|---|---|---|
| `patient_age` | **Mandatory / Required** | Core Feature (`patient_age`) | High (Pediatric & geriatric risk scaling) | Fail-closed: Triage cannot proceed without age |
| `patient_sex` | **Mandatory / Required** | Core Feature (`patient_sex`) | Moderate (Gender-stratified baselines) | Fail-closed: Must be specified (`male` / `female`) |
| `bp_systolic` | **Core Vital (Required if equipment available)** | Core Feature (`bp_systolic`, Shock Index, NEWS2) | Critical (Hypotension / hypertensive crisis) | If missing: Tracked as unmeasured; cannot contribute to stability |
| `bp_diastolic` | **Core Vital (Required if equipment available)** | Core Feature (`bp_diastolic`, MAP) | High (Diastolic collapse / crisis) | If missing: Inverted or missing BP treated as incomplete |
| `heart_rate` | **Core Vital (Required)** | Core Feature (`heart_rate`, Shock Index, NEWS2) | Critical (Severe tachycardia / bradycardia) | If missing: NEWS2 calculation flagged as partial |
| `temperature` | **Core Vital (Required)** | Core Feature (`temperature`, Fever rules) | High (Hyperpyrexia / hypothermia) | If missing: Pediatric fever safety net cannot clear |
| `spo2` | **Core Vital (Required if pulse oximeter available)** | Core Feature (`spo2`, Hypoxia rules) | Critical (Silent hypoxia / respiratory distress) | If missing: Cannot rule out respiratory compromise |
| `symptoms` | **Mandatory Guided Checklist** | Core Feature (12 Canonical Binary Indicators) | Critical (Primary driver of emergency acuity) | **If empty list: Triggers missing-context warning / Indeterminate state** |
| `chief_complaint` | **Optional Narrative** | NLP Keyword Feature Map | High | If empty: System relies entirely on structured symptoms |
| `complaint_duration` | **Optional** | Acuity Modifier (Acute vs Chronic) | Moderate | If empty: Assumed acute (<24h) for safety |
| `is_pregnant` | **Conditional (Females of childbearing age)** | Obstetric Safety Rules | Critical | If unknown/None: Obstetric emergencies flagged if symptoms present |
| `current_medications` | **Optional** | Contraindication & Drug-Drug Engine | Isolated (Does not alter base triage tier) | If empty: Drug contraindication checks skipped with warning |
| `known_conditions` | **Optional** | Comorbidity Attribution | Moderate | If empty: No comorbidity risk adjustment |
| `observations` | **Optional Free Text** | Clinical Briefing / Persistence Only | **Zero (Inert in model & rules)** | Displayed in clinician handoff; zero influence on triage tier |

---

## 5. Explicit "Insufficient Information" & Human-Escalation Pathways

To prevent false reassurance and unsafe discharge of under-triaged emergencies, future candidate architectures must incorporate explicit uncertainty handling:

```
                          [Patient Intake Encounter]
                                      │
                                      ▼
                        [Completeness & Context Gate]
                                      │
               ┌──────────────────────┴──────────────────────┐
               ▼                                             ▼
     [Adequate Clinical Context]                 [Insufficient Information]
     (Vitals + Structured Symptoms)              (Missing vitals OR empty symptoms)
               │                                             │
               ▼                                             ▼
    [Rules Engine + ML Model]                   [Safety Fallback / Triage Refusal]
               │                                 • Non-Acuity State: "INDETERMINATE"
               ├───────────────┐                 • Prohibits ROUTINE classification
               ▼               ▼                 • Mandatory ASHA prompt for symptoms
        [Agreement]     [Disagreement]           • Mandatory Human MO / RN Review
               │        (Model != Rules)                     │
               ▼               │                             ▼
      [Assigned Tier]          └────────────────► [Escalated Clinical Adjudication]
```

### 5.1 The "Insufficient Information" (Indeterminate) State
- When an encounter presents with **zero structured symptoms** AND **fewer than 4 measured vital signs**, the system must emit an explicit status of `INDETERMINATE / INSUFFICIENT_INFORMATION`.
- **Prohibition on Routine Assignment**: An indeterminate encounter is strictly prohibited from being classified as `ROUTINE` or displayed as "Low Risk".
- **ASHA UI Guidance**: The frontline interface must guide the health worker with interactive prompts (e.g., *"No symptoms recorded. Please verify: Does the patient have chest pain, breathing difficulty, or altered consciousness?"*).

### 5.2 Mandatory Human Review / Escalation Pathway
- **Clinical Escalation Trigger**: Any encounter with:
  1. High model uncertainty (entropy / low confidence threshold).
  2. Disagreement between deterministic safety rules (e.g., NEWS2 floor trigger) and statistical model prediction.
  3. Severe physiological derangement with conflicting patient narrative.
- **Action**: The system flags the encounter with a prominent **"Human Clinical Adjudication Required"** directive, routing the case immediately to the Medical Officer (MO) dashboard.

---

## 6. Candidate Remediation Options (Proposals for Future Research)

The following architectural options are proposed for investigation in future remediation phases (strictly non-implemented in this PR):

### Option 1: Mandatory / Guided Structured Symptom Capture
- **Concept**: Refactor the frontend intake workflow so that ASHA workers must explicitly complete a 12-item red-flag checklist (Confirm Present / Confirm Absent) rather than leaving symptom selection blank.
- **Rationale**: Eliminates the partial-input failure mode at the data capture layer by converting implicit absence into explicit clinical confirmation.

### Option 2: Dedicated "Insufficient Information" Acuity State
- **Concept**: Expand the system output from a 3-tier classification (`ROUTINE`, `URGENT`, `EMERGENCY`) to include an explicit 4th operational state (`INDETERMINATE`).
- **Rationale**: Formally segregates unclassifiable/sparse encounters from clinically stable encounters, preventing dangerous under-triage.

### Option 3: Conservative Safe-Fail Escalation Policy
- **Concept**: Implement a deterministic floor rule where any patient presenting with partial inputs or missing symptom data can be triaged no lower than `URGENT` unless all 5 vitals are documented within strictly normal physiological limits.
- **Rationale**: Ensures the system fails conservatively (fail-safe) toward over-triage rather than under-triage.

### Option 4: Dual-Engine Disagreement Adjudication
- **Concept**: Enforce strict hierarchical precedence where deterministic clinical rules (NEWS2, shock index, pediatric fever) hold absolute override authority over machine learning predictions, and any divergence generates an automated clinical audit flag.
- **Rationale**: Restores deterministic clinical safety nets when statistical models fail under out-of-distribution sparse inputs.

---

## 7. Pre-Registered Evaluation Arms & Methodological Protocol

Any future candidate model or remediation contract must be evaluated against the following pre-registered arms:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             PRE-REGISTERED EVALUATION ARMS                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ ARM 1: Frozen Production Baseline                                                      │
│ • Configuration: triage_classifier.pkl + production rules engine                       │
│ • Input Contract: Standard full_input contract                                         │
│ • Role: Controls for baseline performance and historical reference.                    │
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

All future evaluations must compute and report the following standardized aggregate metrics:

### 8.1 Primary Safety Metrics
1. **EMERGENCY Sensitivity (Primary Recall)**:
   $$\text{Sens}_{\text{EMERGENCY}} = \frac{\text{True EMERGENCY Predictions}}{\text{Total True EMERGENCY Reference Cases}}$$
   Reported with exact Wilson 95% score confidence intervals.
2. **EMERGENCY Miss Count & Miss Rate**:
   $$\text{Miss Rate}_{\text{EMERGENCY}} = 1.0 - \text{Sens}_{\text{EMERGENCY}} = \frac{\text{Under-triaged EMERGENCY Cases}}{\text{Total True EMERGENCY Cases}}$$
3. **Critical Two-Tier Drop Rate (EMERGENCY -> ROUTINE)**:
   $$\text{Two-Tier Drop Rate} = \frac{\text{Reference EMERGENCY cases predicted as ROUTINE}}{\text{Total True EMERGENCY Cases}}$$
   *This represents the most severe clinical hazard (catastrophic under-triage).*
4. **Overall Under-Triage Rate**:
   $$\text{Under-Triage Rate} = \frac{\text{Encounters where Predicted Tier} < \text{Reference Tier}}{\text{Total Evaluated Encounters}}$$

### 8.2 Subgroup & Stratified Slices
Every evaluation must report performance stratified across:
- **Age Bands**: Pediatric ($<5$ years, $5–17$ years), Adult ($18–64$ years), Geriatric ($\ge 65$ years).
- **Biological Sex**: Female vs. Male (auditing sex-specific under-triage disparities).
- **Missingness Strata**: $0$ missing vitals, $1$ missing vital, $2$ missing vitals, $\ge 3$ missing vitals.
- **Symptom Availability**: Complete symptoms present vs. zero symptoms recorded.

### 8.3 Calibration & Guardrail Diagnostics
- **Low Confidence Rate**: Percentage of predictions where $\max P(\text{tier}) < 0.60$.
- **NEWS2 Floor Trigger Rate**: Frequency of deterministic NEWS2 overrides.
- **Safety Net Lift**: Difference in emergency sensitivity between the raw ML model and the hybrid safety-net system:
  $$\Delta \text{Sens} = \text{Sens}_{\text{Hybrid}} - \text{Sens}_{\text{Raw ML}}$$

---

## 9. Clinical Governance, Thresholds & Deployment Roadmap

### 9.1 Clinical Acceptance Thresholds Mandate
> [!IMPORTANT]
> **Prohibition on Arbitrary Engineering Thresholds**:
> Engineering teams MUST NOT invent, define, or unilaterally declare clinical pass/fail thresholds for emergency sensitivity or under-triage rates. All clinical acceptance thresholds (e.g., minimum acceptable emergency sensitivity, maximum tolerable under-triage rate) must be formally established and signed off by a **Qualified Medical Doctor / Clinical Governance Committee**.

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
- The software executes in a production or pre-production PHC environment, receiving live de-identified intake streams.
- Predictions and triage recommendations are logged strictly for retrospective audit and are **completely invisible to treating clinicians and patients**.
- Zero influence on clinical decisions, triage routing, or treatment plans is permitted during shadow deployment.

---

## 10. Explicit Limitations & Clinical Non-Claims

To maintain absolute ethical, clinical, and regulatory clarity:

1. **No Clinical Validation Claim**: This document and the associated evaluation harnesses do not constitute clinical validation, medical efficacy proof, or clinical trial evidence.
2. **No Regulatory Clearance**: VitalNet is an investigational software prototype. It has not received Software as a Medical Device (SaMD) clearance, CE mark, or approval from the Central Drugs Standard Control Organisation (CDSCO), US FDA, or any other medical regulatory authority.
3. **No Autonomous Triage**: VitalNet is strictly a clinical decision-support research tool. It does not provide autonomous clinical diagnosis or triage. All triage decisions must be made and verified by licensed human healthcare professionals.
4. **No Rural / ASHA Equivalence in Public Benchmarks**: External evaluations conducted on US hospital ED data (NHAMCS, MIMIC) or South Korean hospital ED data (KTAS) serve solely as algorithmic resilience and proxy physiological benchmarks. Foreign tertiary hospital cohorts do not reflect the disease epidemiology, malnutrition prevalence, baseline vitals, cultural presentation styles, or resource constraints of rural Indian primary care.
