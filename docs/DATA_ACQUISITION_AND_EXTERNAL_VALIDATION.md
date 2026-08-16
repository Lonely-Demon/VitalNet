# VitalNet — Data Acquisition & External Validation Framework

> **The honest answer to "can we scrape data to get closer to clinically
> safe?"** Short version: **indiscriminate web scraping — no** (it is illegal
> for patient data under DPDP Act 2023 / HIPAA, and unvalidated data makes a
> clinical model *more* dangerous, not safer). **Principled acquisition of
> specific, real, already-labelled public datasets for _external validation_ —
> yes, and it is the single highest-probability way to move VitalNet toward
> clinical safety given that no clinician is available right now.** This document
> formalizes VitalNet's multi-gate external validation framework, data boundary
> rules, and evaluation roadmap.
>
> **Cycle Closure Status**: The public-data external evaluation cycle is officially
> **closed**. Evaluated on Gate 1A (Iran ED inspection), Gate 1B (CDC NHAMCS 2022 proxy),
> Gate 2 (MIMIC-IV-ED deferred pending credentialing), and Gate 3A (Korean KTAS 2019 benchmark).
> Empirical findings across NHAMCS (14.4% emergency sensitivity) and KTAS (25.2% primary / 17.9% vital-only)
> demonstrated severe under-triage when symptoms/complaints are missing.
> The active focus is now **Safety Remediation Design** (`docs/evaluation/SAFETY_REMEDIATION_DESIGN.md`).
>
> Source cards for specific datasets are tracked under `docs/evaluation/`.

Companion to `docs/EVALUATION_DATA_BOUNDARY.md`, `docs/evaluation/SAFETY_REMEDIATION_DESIGN.md`,
`docs/CLINICAL_RISK_MANAGEMENT.md`, `docs/VALIDATION_PROTOCOL.md`, and `backend/app/ml/MODEL_CARD.md`.

---

## 1. The Core Reframe: Real Ground Truth Over Synthetic Volume

VitalNet possesses 36,000 synthetic training rows. Generating more synthetic data changes nothing. The fundamental risk in clinical deployment is hazard **H2** in `docs/CLINICAL_RISK_MANAGEMENT.md` (unquantified external real-patient validation).

The goal of acquiring public real-world datasets is **not** to retrain the classifier on arbitrary web data. It is to **externally validate**: run VitalNet's deployed triage classifier and deterministic safety guardrails on real patient presentations, measuring empirical discrimination, under-triage rates, and safety net performance against real clinician decisions and outcomes.

Ranked hierarchy of public data utility for clinical safety:
1. **External Validation Benchmark** (Highest Value) → Evaluated offline via `tools/training/evaluate_on_real.py`.
2. **Realistic Feature & Missingness Distribution Reference** (High Value) → Auditing clinical missingness patterns (e.g., Gate 1A Iran ED inspection).
3. **Model Retraining** (Lowest Priority, High Risk) → Prohibited until extensive external validation demonstrates clinical necessity, and only with rigorous domain adaptation to avoid overfitting foreign hospital practices.

---

## 2. Multi-Gate Validation Architecture

VitalNet structured external validation into a sequential, multi-gate hierarchy. With the public-data cycle now closed, empirical performance and status across all gates are recorded below:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               VITALNET VALIDATION GATES                                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ GATE 1A: Iran ED Dataset (BaniHassan et al. 2024, CC BY 4.0 Open Access)              │
│  - Role: Inspection-only & sparse-input data quality audit                             │
│  - Status: COMPLETED (Inspection-only; model scoring strictly refused)                 │
│  - Findings: Extreme sparsity (<0.07% complete vitals / 91 complete of 143,582 rows);   │
│    binary published urgency unsuited for 3-tier scoring.                               │
│  - Documentation: docs/evaluation/IRAN_ED_SOURCE_CARD.md                              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ GATE 1B: CDC NHAMCS 2022 ED Component (CDC Public Use Data)                           │
│  - Role: Fixed-width partial-input proxy evaluation                                    │
│  - Status: COMPLETED (Unweighted vital-only proxy triage via nhamcs_immediacy_v1)      │
│  - Findings: Critical safety signal: 14.4% emergency sensitivity, 85.6% miss rate      │
│    (1,848 / 2,159 emergencies missed); vital signs alone fail to drive emergency recall│
│  - Documentation: docs/evaluation/NHAMCS_2022_SOURCE_CARD.md                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ GATE 2: MIMIC-IV-ED v2.2 (PhysioNet Credentialed DUA + CITI Certification)             │
│  - Role: Credentialed triage-time external benchmark (vitals + deterministic NLP)      │
│  - Status: DEFERRED (Credentialing not completed; adapter & synthetic tests staged)    │
│  - Documentation: docs/evaluation/MIMIC_IV_ED_SOURCE_CARD.md                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ GATE 3A: Korean KTAS 2019 Dataset (Moon et al. 2019, PLOS ONE, CC BY 4.0)             │
│  - Role: Multi-center external triage benchmark (bilingual NLP + vitals vs. vital-only)│
│  - Status: COMPLETED (Evaluated under explicit authorization)                          │
│  - Findings: Primary contract (ktas_triage_contract_v1) achieved 25.2% emergency sens.;│
│    vital-only arm (ktas_vital_only_partial_v1) achieved 17.9% emergency sensitivity.   │
│    Complete 5-vital cohort confined to Regional ED (563 records; 0 in Local ED).       │
│  - Documentation: docs/evaluation/KTAS_2019_SOURCE_CARD.md                            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ GATE 3B / 4: Prospective Rural Indian PHC Cohort (Silent / Shadow Deployment)          │
│  - Role: Authoritative clinical safety & regulatory validation (CDSCO SaMD)            │
│  - Status: Future phase; blocked on ethics approval, clinical onboarding & remediation │
│  - Focus: ASHA frontline workflow, local epidemiological conditions, true clinical POC │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Dataset Portfolio & Gate Characterization

| Dataset & Gate | Scope & Setting | Volume | License / Access | Inputs Available | Status & Empirical Role in VitalNet |
|---|---|---|---|---|---|
| **Gate 1A: Iran ED** | Single-center tertiary hospital ED, Iran | 143,582 triage rows | CC BY 4.0 Open Access | Official ED_triage.csv has 28 columns; VitalNet consumes 10 key fields for inspection; extreme sparsity (<0.07% complete vitals) | **Completed inspection-only audit**. Model scoring strictly refused due to binary ground truth and severe missingness. |
| **Gate 1B: CDC NHAMCS 2022** | Nationally representative sample of US hospital EDs | 12,347 evaluated encounters | CDC Public Use Data | Fixed-width vitals, age, sex, arrival immediacy (1–5 scale) | **Completed partial-input proxy evaluation**. Demonstrated severe safety signal (14.4% emergency sensitivity; 85.6% miss rate). |
| **Gate 2: MIMIC-IV-ED** (PhysioNet v2.2) | Urban academic medical center ED (Beth Israel Deaconess, Boston) | ~425,000 ED stays | Credentialed DUA (PhysioNet + CITI training required) | Complete vitals, anchor age, sex, chief complaint, ESI 1–5 | **Deferred**. PhysioNet credentialing was not completed. Staged code-only adapter & synthetic fixtures (Gate M1). |
| **Gate 3A: Korean KTAS 2019** | Multi-center EDs (Local vs Regional), South Korea | 1,267 encounters (563 complete 5-vital rows) | CC BY 4.0 Open Access / PLOS ONE | Five vitals, age, sex, bilingual complaints, expert KTAS 1–5 | **Completed external benchmark**. 25.2% emergency sensitivity on primary contract; 17.9% on vital-only sensitivity arm. |
| **Gate 3B / 4: Prospective Indian PHC** | Frontline Primary Health Centres & Sub-Centres, rural India | Prospective cohort | Institutional Ethics Committee (IEC) approved | Complete ASHA intake: vitals, localized symptoms, Hindi/Tamil notes, clinical outcomes | **Future clinical validation**. Necessary prerequisite for regulatory clearance (CDSCO). Requires shadow-deployment first. |

---

## 4. Hard Data Boundary & Runtime Isolation Guardrails

All external validation activities are governed by `docs/EVALUATION_DATA_BOUNDARY.md`. The core security and compliance mandates include:

1. **Zero Patient Data in Version Control**:
   - `tools/training/data/**` and `tools/training/outputs/**` are strictly gitignored while tracking `.gitkeep`.
   - Never commit, push, or log raw source records, transformed rows, patient IDs, free-text complaints, credentials, or sample rows.
2. **Prohibition of Automated Remote Fetching**:
   - Code must never include automated download scripts, web scrapers, or credential-fetching API calls.
   - All real datasets must be acquired out-of-band under applicable DUAs and manually placed locally on disk.
3. **Production Model Immutability**:
   - Zero modifications to `backend/app/ml/models/triage_classifier.pkl`, `apps/web/public/models/triage_trees.json`, feature configs, rules engines, API routes, or database schemas during evaluation work.
4. **Aggregate-Only Reporting Standard**:
   - Reports (JSON and console) must output aggregate statistics (confusion matrices, sensitivity/specificity with Wilson 95% CIs, under-triage rates, ECE diagnostics, SHA-256 source checksums) and zero patient-level rows.
5. **Prohibition of Survey Weighting on Model Metrics**:
   - Survey design weights (e.g., `PATWT` in NHAMCS) are preserved for high-level demographic metadata only. They are strictly prohibited from weighting model diagnostic metrics.

---

## 5. Evaluation Workflow & Execution Pipeline

```
[Local Dataset Placed Manually in tools/training/data/<source>/]
                           │
                           ▼
          [Modular Evaluation Source Adapter]
          (tools/training/evaluation_sources/)
          ├── Validates headers, offsets, and checksums
          ├── Filters sentinels & impossible readings
          ├── Enforces input mode (partial vs full)
          └── Applies canonical label proxy mapping
                           │
                           ▼
          [Core Evaluation CLI Runner]
          (tools/training/evaluate_on_real.py)
          ├── Executes production predict_triage()
          ├── Reconstructs raw ML model (bypassing guardrails)
          ├── Computes Wilson 95% CIs & safety metrics
          ├── Evaluates deterministic guardrail lift
          └── Generates diagnostic ECE calibration table
                           │
                           ▼
          [Aggregate-Only Reporting]
          (tools/training/outputs/*.json + Console)
          ├── SHA-256 source manifest & provenance
          ├── Cohort flow & exclusion counters
          ├── Aggregate performance & safety metrics
          └── Explicit population limitations & non-claims
```

---

## 6. Schema Mapping & Feature Alignment Reference

| VitalNet Intake Field | Gate 1A: Iran ED | Gate 1B: CDC NHAMCS 2022 | Gate 2: MIMIC-IV-ED | Gate 3A: Korean KTAS 2019 | Target Handling & Conversions |
|---|---|---|---|---|---|
| `patient_age` | Not in primary triage | `AGE` (cols 16–18, slice `[15:18]`) | `patients.anchor_age` | `Age` | Direct integer (0–130; top-coded values preserved) |
| `patient_sex` | Not in primary triage | `SEX` (col 25, slice `[24:25]`) | `patients.gender` | `Sex` | `1`->`female`, `2`->`male` (`M`->`male`, `F`->`female`) |
| `bp_systolic` | `BlooddpressurSystol` | `BPSYS` (cols 58–60, slice `[57:60]`) | `triage.sbp` | `SBP` | Integer mmHg (20–350; Doppler/pulseless sanitized) |
| `bp_diastolic` | `BlooddpressurDiastol` | `BPDIAS` (cols 61–63, slice `[60:63]`) | `triage.dbp` | `DBP` | Integer mmHg (10–250; inverted BP sanitized to `None`) |
| `heart_rate` | `PulseRate` | `PULSE` (cols 52–54, slice `[51:54]`) | `triage.heartrate` | `HR` | Integer bpm (0–350; Doppler 998 sanitized to `None`) |
| `temperature` | `Temperature` | `TEMPF` (cols 48–51, slice `[47:51]`) | `triage.temperature` | `BT` | Converted to Celsius (°F -> °C where needed) |
| `spo2` | `O2Saturation` | `POPCT` (cols 64–66, slice `[63:66]`) | `triage.o2sat` | `Saturation` | Integer percentage (0–100%; severe hypoxia preserved) |
| `chief_complaint` | `ChiefComplaint` | Strict Empty String `""` | `triage.chiefcomplaint` | `Chief_complain` (purged) | Purged to empty string in record construction |
| `symptoms` | Empty List `[]` | Strict Empty List `[]` | Parsed from text | Bilingual parsed | Allow-listed 12 canonical symptoms |
| `reference_acuity` | `TriageGrade` (1–5) | `IMMEDR` (1–5) | `triage.acuity` (ESI 1–5) | `KTAS_expert` (1–5) | Canonical proxy mapping (e.g., `ktas_v1`, `nhamcs_immediacy_v1`) |
| (Metadata only) | `CriticalStatus`, `NeedFastExecute` | `RESPR`, `PATWT`, `CPSU` | `triage.resprate`, `pain` | `Patients number per hour`, `RR`, `Pain`, `Mental` | Recorded in cohort inspection metadata only |

---

## 7. Honest Bottom Line, Safety Failure Modes & Non-Claims

1. **Demonstrated Missing-Context Failure Mode**: External evaluations across CDC NHAMCS 2022 (Gate 1B) and Korean KTAS 2019 (Gate 3A) empirically demonstrated that VitalNet's frozen production classifier **severely under-triages emergency cases when symptoms and clinical narrative context are missing** (14.4% emergency sensitivity in NHAMCS; 17.9% in KTAS vital-only). Vital signs alone are insufficient to trigger emergency classification in the majority of acute presentations under the frozen model.
2. **Public-Data Cycle Closed; Safety Remediation Active**: The public-data external validation cycle is officially closed. The findings necessitate structural safety remediation (`docs/evaluation/SAFETY_REMEDIATION_DESIGN.md`), including mandatory structured symptom capture, explicit indeterminate acuity states, conservative fail-safe escalation, and clinical adjudication pathways.
3. **Proxy Evaluations Are Not Indian Clinical Trials**: Validation against US (NHAMCS, MIMIC), Korean (KTAS), or Iranian (Iran ED) emergency cohorts measures the algorithmic properties of VitalNet's classifier on real human presentations. However, foreign hospital ED cohorts do not match the disease prevalence, nutritional status, baseline vitals, or presentation delays of rural Indian primary care.
4. **No Medical Device or Clinical Validation Claim**: Results from this evaluation framework do not constitute medical device certification, clinical trial validation, or autonomous diagnostic safety clearance under CDSCO, FDA, or CE frameworks. VitalNet remains a decision-support research prototype requiring human clinical oversight for all patient care.
