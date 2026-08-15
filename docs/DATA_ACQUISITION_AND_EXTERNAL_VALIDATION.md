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
> **Updated for the Evaluation Foundation**: points to `tools/training/evaluate_on_real.py`
> and `tools/training/evaluation_sources/`, governed by `docs/EVALUATION_DATA_BOUNDARY.md`.
> Source cards for specific datasets are tracked under `docs/evaluation/`.

Companion to `docs/EVALUATION_DATA_BOUNDARY.md`, `docs/CLINICAL_RISK_MANAGEMENT.md`,
`docs/VALIDATION_PROTOCOL.md`, and `backend/app/ml/MODEL_CARD.md`.

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

VitalNet structures external validation into a sequential, multi-gate hierarchy spanning public uncredentialed inspection, public proxy evaluation, credentialed full-input validation, and prospective clinical trials:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               VITALNET VALIDATION GATES                                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ GATE 1A: Iran ED Dataset (Kashani et al. 2024, CC BY 4.0 Open Access)                  │
│  - Role: Inspection-only & sparse-input data quality audit                             │
│  - Status: Implemented in adapter; model scoring strictly refused                      │
│  - Focus: Auditing severe clinical missingness (91 complete rows / 143k total)         │
│  - Documentation: docs/evaluation/IRAN_ED_SOURCE_CARD.md                              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ GATE 1B: CDC NHAMCS 2022 ED Component (CDC Public Use Data)                           │
│  - Role: Fixed-width partial-input proxy evaluation                                    │
│  - Status: Implemented (unweighted vital-only proxy triage via nhamcs_immediacy_v1)    │
│  - Focus: Vital-only triage resilience, unweighted under-triage, guardrail lift        │
│  - Documentation: docs/evaluation/NHAMCS_2022_SOURCE_CARD.md                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ GATE 2: MIMIC-IV-ED v2.2 (PhysioNet Credentialed DUA + CITI Certification)             │
│  - Role: Full-input external validation (vitals + free text + ESI 1-5 + outcomes)      │
│  - Status: Pre-data harness ready; blocked on researcher credentialing & DUA           │
│  - Focus: Multi-modal triage agreement, clinical NLP complaint evaluation, admission   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ GATE 3: Prospective Rural Indian PHC Cohort (Silent / Shadow Deployment)               │
│  - Role: Authoritative clinical safety & regulatory validation (CDSCO SaMD)            │
│  - Status: Blocked on institutional ethics approval & clinical partner onboarding      │
│  - Focus: ASHA frontline workflow, local epidemiological conditions, true clinical POC │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Dataset Portfolio & Gate Characterization

| Dataset & Gate | Scope & Setting | Volume | License / Access | Inputs Available | Target Role in VitalNet |
|---|---|---|---|---|---|
| **Gate 1A: Iran ED** | Single-center tertiary hospital ED, Iran | 143,582 triage rows | CC BY 4.0 Open Access | Published 10 headers; extreme sparsity (<0.07% complete vitals) | **Inspection-only audit**. Scoring strictly refused due to binary ground truth and severe missingness. |
| **Gate 1B: CDC NHAMCS 2022** | Nationally representative sample of US hospital EDs | ~25,000 encounters / year | CDC Public Use Data | Fixed-width vitals, age, sex, arrival immediacy (1–5 scale) | **Partial-input proxy evaluation**. Unweighted discrimination on vital-only presentations. |
| **Gate 2: MIMIC-IV-ED** (PhysioNet v2.2) | Urban academic medical center ED (Beth Israel Deaconess, Boston) | ~425,000 ED stays | Credentialed DUA (PhysioNet + CITI training required) | Complete vitals, age, sex, pain, free-text chief complaints, ESI 1–5, linkable outcomes | **Full-input multi-modal validation**. Measures end-to-end classifier + NLP text features. |
| **Gate 3: Prospective Indian PHC** | Frontline Primary Health Centres & Sub-Centres, rural India | Prospective cohort | Institutional Ethics Committee (IEC) approved | Complete ASHA intake: vitals, localized symptoms, Hindi/Tamil notes, clinical outcomes | **True clinical validation**. Necessary prerequisite for regulatory clearance (CDSCO). |

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

| VitalNet Intake Field | Gate 1A: Iran ED | Gate 1B: CDC NHAMCS 2022 | Gate 2: MIMIC-IV-ED | Target Handling & Conversions |
|---|---|---|---|---|
| `patient_age` | Not published in primary triage | `AGE` (cols 16–18, slice `[15:18]`) | `patients.anchor_age` | Direct integer (0–94; 94 represents 94+ top-coding) |
| `patient_sex` | Not published in primary triage | `SEX` (col 25, slice `[24:25]`) | `patients.gender` | `1`->`female`, `2`->`male` (`M`->`male`, `F`->`female`) |
| `bp_systolic` | `BlooddpressurSystol` | `BPSYS` (cols 58–60, slice `[57:60]`) | `triage.sbp` | Integer mmHg (43–289; 0=pulseless) |
| `bp_diastolic` | `BlooddpressurDiastol` | `BPDIAS` (cols 61–63, slice `[60:63]`) | `triage.dbp` | Integer mmHg (22–190; Doppler 998 rejected) |
| `heart_rate` | `PulseRate` | `PULSE` (cols 52–54, slice `[51:54]`) | `triage.heartrate` | Integer bpm (0–240; Doppler 998 rejected) |
| `temperature` | `Temperature` | `TEMPF` (cols 48–51, slice `[47:51]`) | `triage.temperature` | Converted to Celsius (°F tenths -> °C) |
| `spo2` | `O2Saturation` | `POPCT` (cols 64–66, slice `[63:66]`) | `triage.o2sat` | Integer percentage (0–100%) |
| `chief_complaint` | `ChiefComplaint` | Strict Empty String `""` | `triage.chiefcomplaint` | Free text NLP evaluation (Gate 2 only) |
| `symptoms` | Empty List `[]` | Strict Empty List `[]` | Parsed from text | Allow-listed symptoms list |
| `reference_acuity` | `TriageGrade` (1–5) | `IMMEDR` (1–5) | `triage.acuity` (ESI 1–5) | Canonical proxy mapping (e.g., `nhamcs_immediacy_v1`) |
| (Metadata only) | `CriticalStatus`, `NeedFastExecute` | `RESPR`, `PATWT`, `CPSU` | `triage.resprate`, `pain` | Recorded in cohort inspection metadata only |

---

## 7. Honest Bottom Line & Regulatory Disclaimers

1. **Proxy Evaluations Are Not Indian Clinical Trials**: Validation against US (NHAMCS, MIMIC) or Iranian (Iran ED) emergency cohorts measures the fundamental physiological discrimination and safety properties of VitalNet's algorithms on real human presentations. However, foreign hospital ED cohorts do not match the disease prevalence, nutritional status, baseline vitals, or presentation delays of rural Indian primary care.
2. **Partial-Input Testing Is a Resilience Benchmark**: Partial-input evaluation in Gate 1B verifies that VitalNet's classifier degrades gracefully and maintains high safety recall even when clinical text and structured symptom checklists are missing. It does not replace comprehensive multi-modal validation.
3. **Mandatory Human Clinical Oversight**: VitalNet is a clinical decision-support prototype. It does not provide autonomous clinical diagnosis, and all triage recommendations must be reviewed and confirmed by trained human healthcare professionals.
