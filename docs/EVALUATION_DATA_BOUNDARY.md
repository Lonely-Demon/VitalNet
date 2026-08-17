# VitalNet — Evaluation Data Boundary & Runtime Isolation Policy

> **Status**: Authoritative Governance & Security Specification
> **Applies to**: `tools/training/evaluate_on_real.py`, `tools/training/evaluation_sources/`, local evaluation datasets, CI pipelines, developer workstations, and external validation harnesses.
> **Related Documents**: `docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md`, `docs/evaluation/PUBLIC_DATA_EVALUATION_CLOSURE.md`, `docs/evaluation/SAFETY_REMEDIATION_DESIGN.md`, `docs/CLINICAL_RISK_MANAGEMENT.md`, `docs/SECURITY.md`, `docs/CLINICAL_GOVERNANCE.md`, `AGENTS.md`.

---

## 1. Non-Negotiable Zero Patient Data Leakage Policy

VitalNet is a clinical decision-support system designed for frontline healthcare settings (ASHA community health workers and Primary Health Centre medical officers in rural India). When evaluating VitalNet's triage classifier against external public or research datasets (e.g., CDC NHAMCS, Iran ED, MIMIC-IV-ED), the integrity, confidentiality, and legal boundaries of clinical data must be maintained with absolute zero tolerance for leakage.

### 1.1 Strict Commit and Ingestion Prohibitions
Under no circumstances may any of the following artifacts be committed to Git, pushed to remote branches, staged in repositories, included in CI/CD build artifacts, written to persistent cloud logs, transmitted over networks, or deployed to pre-production/production environments:

1. **Raw Source Files**: Original un-processed dataset files (e.g., `ed2022`, `triage.csv`, `ED_admission.csv`, `mimic_iv_ed.csv`, or any `.csv`, `.dat`, `.txt`, `.parquet`, `.feather`, `.json` data extracts).
2. **Transformed / Intermediate Records**: Intermediate tabular, pickled, or serialized patient-level representations.
3. **Record-Level Predictions**: Per-patient inference results, per-encounter predicted triage categories, class probability vectors, or raw feature attribution vectors linked to real encounter instances.
4. **Patient Identifiers & Keys**: Medical Record Numbers (MRNs), encounter IDs, visit keys, hospital codes, serial numbers, admission IDs, geographic subdivision codes, or dates of service.
5. **Free-Text Clinical Data**: Unstructured chief complaint narratives, triage nurse notes, triage observations, reasons for visit, or clinician commentary.
6. **Authentication Credentials & Tokens**: Physionet credentials, CITI completion tokens, Kaggle API keys, cloud access keys, database connection strings, or bearer tokens.
7. **Source-Derived Sample Rows**: Mock, snippet, or "first 5 rows" examples derived from real patient datasets embedded in code comments, test files, documentation, or commit messages.

### 1.2 Synthetic Test Isolation Principle
All automated unit tests, integration tests, CI checks, and regression suites MUST execute exclusively on **100% synthetic, programmatically generated fixtures** (e.g., `tools/training/tests/fixtures/`). Synthetic test data must be generated with deterministic pseudo-random generators or hand-crafted rule boundaries; it must never be sampled, scraped, or derived from real patient records.

---

## 2. Runtime Isolation & Automated Download Prohibition

### 2.1 Prohibition on Automated Data Fetching
VitalNet code must NEVER attempt to automatically download datasets, scrape web portals, or fetch remote credentials over the internet:
- **No Remote Downloader Scripts**: Code must not contain `requests.get()`, `urllib.request`, `curl`, `wget`, `boto3`, or similar mechanisms to download external patient datasets during build, test, or evaluation execution.
- **Manual Local Placement**: All real datasets must be acquired out-of-band by authorized research personnel under applicable Data Use Agreements (DUAs) and placed locally on disk by human operators into `tools/training/data/<source_id>/`.
- **Offline Execution Guarantee**: The evaluation harness (`tools/training/evaluate_on_real.py`) must operate fully offline without external network dependencies.

### 2.2 Filesystem Boundaries & Git Ignore Enforcement
The repository filesystem enforces strict physical isolation between code, synthetic test fixtures, local raw data, and generated evaluation reports:

```
VitalNet/
├── .gitignore                          # Enforces ignore rules for data and outputs
├── docs/
│   ├── EVALUATION_DATA_BOUNDARY.md     # This policy document
│   ├── evaluation/                     # Tracked source cards & governance specs
│   │   ├── IRAN_ED_SOURCE_CARD.md
│   │   ├── NHAMCS_2022_SOURCE_CARD.md
│   │   ├── MIMIC_IV_ED_SOURCE_CARD.md
│   │   ├── KTAS_2019_SOURCE_CARD.md
│   │   ├── PUBLIC_DATA_EVALUATION_CLOSURE.md
│   │   └── SAFETY_REMEDIATION_DESIGN.md
│   └── DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md
├── tools/training/
│   ├── evaluate_on_real.py             # Evaluation & inspection CLI harness
│   ├── evaluation_sources/             # Modular adapter package
│   │   ├── __init__.py
│   │   ├── base.py                     # Canonical contracts & abstract source interface
│   │   ├── nhamcs_2022.py              # Gate 1B fixed-width adapter
│   │   ├── iran_ed.py                  # Gate 1A inspection adapter (refuses scoring)
│   │   ├── mimic_iv_ed.py              # Gate 2 credentialed benchmark adapter
│   │   ├── mimic_symptom_parser.py     # Deterministic allow-list symptom parser
│   │   ├── ktas_2019.py                # Gate 3A open KTAS adapter
│   │   ├── ktas_symptom_parser.py      # Deterministic bilingual KTAS parser
│   │   ├── generic_csv.py              # Backward-compatible CSV adapter
│   │   └── self_test_source.py         # Synthetic self-test source adapter
│   ├── tests/
│   │   ├── fixtures/                   # 100% SYNTHETIC fixtures ONLY (tracked in Git)
│   │   ├── test_evaluation_sources.py  # Pytest suite using synthetic fixtures
│   │   ├── test_mimic_iv_ed_adapter.py # Gate 2 MIMIC adapter, parser & leakage suite
│   │   ├── test_adversarial_challenge.py # Adversarial parsing, conversion & leakage suite
│   │   └── test_adversarial_cli_m4.py  # Adversarial CLI & refusal semantics suite
│   ├── data/                           # LOCAL ONLY — GITIGNORED (real datasets placed manually)
│   │   └── .gitkeep                    # Tracked empty placeholder
│   └── outputs/                        # LOCAL ONLY — GITIGNORED (generated evaluation reports)
│       └── .gitkeep                    # Tracked empty placeholder
```

#### `.gitignore` Rule Specification:
```gitignore
# Evaluation datasets and outputs (strict data boundary isolation)
tools/training/data/**
!tools/training/data/.gitkeep
tools/training/outputs/**
!tools/training/outputs/.gitkeep
```

---

## 3. Production Model & System Immutability Invariant

Evaluating the triage classifier on external public datasets is an **observational validation exercise** designed to quantify baseline performance and safety characteristics. It is NOT a training or tuning phase.

To ensure evaluation validity and prevent unauthorized system drift, the following components are **strictly immutable** during evaluation work:
1. **Model Weights & Artifacts**:
   - `backend/app/ml/models/triage_classifier.pkl`
   - `apps/web/public/models/triage_trees.json`
   - `apps/web/public/models/features_config.json`
   - No retraining, parameter fine-tuning, or re-export of model files may occur during evaluation.
2. **Inference Contract & Rules Engine**:
   - `backend/app/ml/classifier.py` and `ClinicalFeatureEngineer`
   - `packages/clinical-core/src/rules/**` and deterministic safety guardrails
   - Safety thresholds (e.g., NEWS2 floor, shock index, pediatric fever triggers) must remain untouched.
3. **Application Stack**:
   - Live backend API routes (`backend/app/api/`, `apps/api/`)
   - Frontend application (`apps/web/`)
   - Database migrations (`backend/supabase/migrations/`)
   - Pre-production and production infrastructure configurations.

---

## 4. Standardized Aggregate-Only Reporting Contract

To eliminate any risk of patient data exposure while providing full transparency for clinical audit, all evaluation outputs (console tables and JSON files) must conform to an **aggregate-only reporting schema**.

### 4.1 Required Report Structure
Every evaluation report must include:
1. **Source Manifest**:
   - Dataset identifier, formal name, version/year, and official canonical URL.
   - License and Data Use Agreement terms (e.g., CC BY 4.0, CDC Public Use Agreement).
   - SHA-256 cryptographic checksum of the evaluated local source file.
   - File size in bytes.
2. **Execution Metadata**:
   - Execution mode (`inspection` vs `evaluation`).
   - Input mode (`full_input`, `partial_input`, or `not_scored`).
   - Feature availability flags (e.g., `chief_complaint_available: false`, `symptoms_available: false`).
   - Model version and Git commit hash under test.
3. **Label Configuration**:
   - Label scheme identifier (e.g., `nhamcs_immediacy_v1`, `esi_5level`, `published_binary`).
   - Explicit mapping dictionary from source codes to VitalNet's 3 tiers (`EMERGENCY`, `URGENT`, `ROUTINE`).
4. **Cohort Flow & Exclusion Breakdown**:
   - Total raw records read from disk.
   - Granular exclusion counters (e.g., missing age, invalid sex, sentinel triage codes `-9, -8, 0, 7`, physically impossible vital readings).
   - Final included cohort size.
   - Vital sign completeness statistics (percentage and count of encounters with complete vs partial vitals).
5. **Aggregate Performance Metrics** (Evaluation mode only):
   - Overall cohort agreement rate.
   - 3x3 Confusion Matrix (`ROUTINE`, `URGENT`, `EMERGENCY`).
   - Per-tier sensitivity, specificity, PPV, and NPV with Wilson 95% confidence intervals.
   - Safety under-triage metrics (overall under-triage rate, EMERGENCY missed rate, two-tier drop to ROUTINE rate).
   - Deterministic guardrail lift (raw ML model vs production classifier EMERGENCY sensitivity).
   - Diagnostic Expected Calibration Error (ECE) with explicit diagnostic disclaimer.
   - Subgroup safety slices across age bands, sex, and vital completeness.
6. **Population Limitations & Explicit Non-Claims**:
   - Formal declarations of cohort context (e.g., US tertiary ED vs rural Indian PHC).
   - Partial-input warnings and SaMD decision-support disclaimers.
   - For KTAS, the two-site Korean ED context and the Regional-ED-only complete-five-vital subgroup limitation.
   - No public-data result may be described as clinical validation, regulatory clearance, or rural/ASHA equivalence.

### 4.2 Prohibited Content in Reports
The JSON and text reports MUST NEVER contain:
- Arrays or tables of individual patient encounters or predictions.
- Raw or formatted patient IDs, encounter IDs, or dates.
- Free-text chief complaints, triage notes, or clinician comments.
- Row-level probabilities, SHAP values, or intermediate feature matrices.

---

## 5. Regulatory Alignment & Legal Frameworks

VitalNet's evaluation boundary is designed to adhere to premier international and Indian data privacy and medical software standards.

### 5.1 Indian Digital Personal Data Protection (DPDP) Act 2023 Alignment
1. **Purpose Limitation (§4, §5, §6)**: Real evaluation data acquired under research agreements is processed strictly for the documented purpose of retrospective classifier validation, never repurposed for commercial profiling or training without explicit consent.
2. **Data Minimization (§6(1))**: The evaluation harness ingests only the minimal feature set required to evaluate triage categories. Non-clinical administrative fields (e.g., payment type, insurance, provider IDs) are immediately dropped during parsing.
3. **Local Storage & Processing (§8)**: All evaluation processing occurs locally on secured developer/researcher workstations. No patient data or derived vectors are synced to offshore cloud services or unapproved endpoints.
4. **Storage Limitation & Erasure (§8(7))**: Raw evaluation datasets and generated local outputs remain segregated in gitignored directories, allowing immediate, clean sanitization upon completion of research audits.

### 5.2 HIPAA De-Identification & Privacy Standards (45 CFR §164.514)
1. **Safe Harbor Standard**: Evaluation adapters verify that public datasets are free from all 18 HIPAA direct identifiers (names, geographic subdivisions smaller than state, dates more specific than year, telephone numbers, MRNs, etc.).
2. **Statistical Non-Re-identification**: The evaluation pipeline strictly prohibits joining public datasets with auxiliary external identifiable databases.
3. **Survey Weight Safeguard**: For datasets such as CDC NHAMCS, survey design weights (`PATWT`) are preserved exclusively in high-level cohort metadata and are strictly prohibited from weighting model diagnostic metrics, preventing distorted variance or individual encounter re-identification.

---

## 6. Audit & Verification Checklist

Before running any evaluation or committing code, verify:
- [ ] Every real-data scoring or inspection operation has dataset-specific explicit human authorization recorded outside the codebase.
- [ ] `.gitignore` contains `tools/training/data/**` and `tools/training/outputs/**` rules.
- [ ] `git status` shows zero untracked data files, `.csv`, `.dat`, `.txt`, or `.json` evaluation logs in `tools/training/`.
- [ ] Only synthetic fixtures exist in `tools/training/tests/fixtures/`.
- [ ] No changes have been made to `backend/app/ml/models/*.pkl` or `apps/web/public/models/*.json`.
- [ ] All reports generated under `tools/training/outputs/` contain strictly aggregate counts, matrices, and percentages.
