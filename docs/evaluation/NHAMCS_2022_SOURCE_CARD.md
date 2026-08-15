# Evaluation Source Card: CDC NHAMCS 2022 Emergency Department File (Gate 1B)

> **Status**: Tracked Evaluation Specification
> **Gate Role**: Gate 1B — Fixed-Width Partial-Input Proxy Evaluation
> **Input Mode**: Strict `partial_input` (`chief_complaint=""`, `symptoms=[]`, `chief_complaint_available=false`)
> **Label Mapping**: `nhamcs_immediacy_v1`
> **Related Documents**: `docs/EVALUATION_DATA_BOUNDARY.md`, `docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md`, `PROJECT.md`.

---

## 1. Dataset Overview & Provenance

| Property | Value |
|---|---|
| **Dataset Title** | National Hospital Ambulatory Medical Care Survey (NHAMCS) — 2022 Emergency Department Summary |
| **Issuing Authority** | Centers for Disease Control and Prevention (CDC) / National Center for Health Statistics (NCHS) |
| **File Designation** | `ed2022` (Single-record fixed-width ASCII flat file) |
| **License / DUA** | CDC Public Use Data Agreement (100% de-identified public use dataset) |
| **Documentation Gateway** | [https://www.cdc.gov/nchs/nhamcs/documentation/index.html](https://www.cdc.gov/nchs/nhamcs/documentation/index.html) |
| **Direct Dataset Download** | [https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHAMCS/ED2022.zip](https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHAMCS/ED2022.zip) |
| **Technical Documentation** | [https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Dataset_Documentation/NHAMCS/doc22-ed-508.pdf](https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Dataset_Documentation/NHAMCS/doc22-ed-508.pdf) |
| **README / DUA Text** | [https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Dataset_Documentation/NHAMCS/readme2022.txt](https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Dataset_Documentation/NHAMCS/readme2022.txt) |
| **Target Setting** | Nationally representative sample of hospital-based emergency departments across the United States |
| **Access Requirements** | Free public download; manually placed locally under `tools/training/data/nhamcs_2022/ed2022` |

---

## 2. Fixed-Width Column Layout & Offset Specifications

The CDC NHAMCS 2022 ED file (`ed2022`) uses fixed-width ASCII formatting. Below are the official 1-indexed codebook columns, corresponding 0-indexed Python string slices (`line[start:end]`), valid ranges, transformation math, and sentinel handling rules.

### 2.1 Complete Layout Map

| Field Name | CDC Cols (1-idx) | Length | Python Slice `[start:end]` | Raw Type | Valid Raw Range | Transformation / Conversion Formula | Sentinel & Invalid Handling | Destination in VitalNet Schema / Metadata |
|---|---|---|---|---|---|---|---|---|
| `VYEAR` | 1–4 | 4 | `[0:4]` | int | 2022 | Survey year verification | Blank or !=2022 -> validation error | Source Metadata (`survey_year`) |
| `VMONTH` | 5–6 | 2 | `[4:6]` | int | 1–12 | Visit month integer | Blank -> None | Source Metadata (`visit_month`) |
| `VDAYR` | 7 | 1 | `[6:7]` | int | 1–7 | Day of week (1=Sun ... 7=Sat) | Blank -> None | Source Metadata (`visit_day_of_week`) |
| `ARRTIME` | 8–11 | 4 | `[7:11]` | int / str | 0000–2359 | Military arrival time (HHMM) | `-9` (Blank) -> None | Source Metadata (`arrival_time`) |
| `AGE` | 16–18 | 3 | `[15:18]` | int | 0–94 | Direct integer. Note: 94 represents 94+ top-coding | `-9`, `-8`, blanks -> Exclude row (`invalid_age`) | `form_data["patient_age"]` (int) |
| `SEX` | 25 | 1 | `[24:25]` | int | 1, 2 | `1` -> `"female"`, `2` -> `"male"` | `-9`, blanks, non-1/2 -> Exclude row (`invalid_sex`) | `form_data["patient_sex"]` (`Literal["male", "female"]`) |
| `TEMPF` | 48–51 | 4 | `[47:51]` | int | 896–1056 | Tenths of °F (89.6°F to 105.6°F). Formula: `round((raw / 10.0 - 32.0) * 5.0 / 9.0, 1)` | `-9`, blanks, <896, >1056 -> `temperature = None` | `form_data["temperature"]` (`Optional[float]`) |
| `PULSE` | 52–54 | 3 | `[51:54]` | int | 0–240 | Heart rate in beats per minute | `998` (Doppler), `-9`, blanks, >240 -> `heart_rate = None` | `form_data["heart_rate"]` (`Optional[int]`) |
| `RESPR` | 55–57 | 3 | `[54:57]` | int | 0–150 | Respiratory rate (breaths/min) | `-9`, blanks -> None. **STRICT: Never pass to model** | Cohort Metadata ONLY (`respiratory_rate`); omitted from `form_data` |
| `BPSYS` | 58–60 | 3 | `[57:60]` | int | 0 or 43–289 | Systolic BP in mmHg | `0` (pulseless), `-9`, blanks, <43, >289 -> `bp_systolic = None` | `form_data["bp_systolic"]` (`Optional[int]`) |
| `BPDIAS` | 61–63 | 3 | `[60:63]` | int | 0 or 22–190 | Diastolic BP in mmHg | `998` (Doppler), `0`, `-9`, blanks, <22, >190 -> `bp_diastolic = None` | `form_data["bp_diastolic"]` (`Optional[int]`) |
| `POPCT` | 64–66 | 3 | `[63:66]` | int | 0–100 | Pulse oximetry SpO₂ (%) | `-9`, `-8`, blanks, <0, >100 -> `spo2 = None` | `form_data["spo2"]` (`Optional[int]`) |
| `IMMEDR` | 67–68 | 2 | `[66:68]` | int | 1–5 | 1=Immediate, 2=Emergent, 3=Urgent, 4=Semi-urgent, 5=Nonurgent | `-9`, `-8`, `0`, `7` -> **Exclude and track sentinel** | Ground Truth Reference Tier (via `nhamcs_immediacy_v1`) |
| `PATWT` | 179–188 | 10 | `[178:188]` | float | Positive float | CDC national survey expansion weight | Blanks -> None | Cohort Metadata ONLY; **PROHIBITED from model metrics** |

---

## 3. Detailed Slicing, Validation, and Conversion Rules

### 3.1 Age Parsing & Top-Coding (`AGE`)
- **Slice**: `line[15:18].strip()`
- **Logic**:
  - Blanks, empty strings, `-9` (Blank), or `-8` (Unknown) exclude the encounter (`invalid_age`).
  - Integer values between `0` and `94` are valid.
  - Per CDC NCHS codebook specifications, raw age `94` indicates **94+ top-coding** (patients aged 94 years or older aggregated to prevent re-identification). This top-coding is preserved and documented in cohort metadata.

### 3.2 Sex Mapping (`SEX`)
- **Slice**: `line[24:25].strip()`
- **Logic**:
  - `1` maps to `"female"`.
  - `2` maps to `"male"`.
  - Any other value (blanks, `-9`, `8`) excludes the encounter (`invalid_sex`).

### 3.3 Temperature Conversion Math (`TEMPF`)
- **Slice**: `line[47:51].strip()`
- **Logic**:
  - Raw values represent Fahrenheit in tenths (e.g., `0986` = 98.6°F, `1040` = 104.0°F).
  - Valid physiological range: `896 <= raw <= 1056` (89.6°F to 105.6°F).
  - Celsius conversion formula:
    $$\text{temp\_c} = \text{round}\left(\frac{\frac{\text{raw}}{10.0} - 32.0}{1.8}, 1\right)$$
  - Any raw value outside 896–1056, blank, or `-9` is treated as a missing vital (`temperature = None`).

### 3.4 Pulse Rate & Doppler Exclusion (`PULSE`)
- **Slice**: `line[51:54].strip()`
- **Logic**:
  - Raw values `0 <= raw <= 240` are valid integer heart rates in bpm.
  - Code `998` represents "Doppler pulse present, unmeasurable rate" (e.g., severe hypotension, shock, or peripheral vascular collapse). It must be sanitized to `heart_rate = None` and not interpreted as 998 bpm.
  - Blanks and `-9` are sanitized to `heart_rate = None`.

### 3.5 Respiratory Rate Isolation (`RESPR`)
- **Slice**: `line[54:57].strip()`
- **Rule**: VitalNet's intake schema (`IntakeForm`) and clinical feature engineer do not ingest a respiratory rate input.
- **Handling**: `RESPR` is recorded exclusively in cohort quality inspection metadata. It is **strictly omitted from `form_data`** passed to the classifier.

### 3.6 Blood Pressure Validation & Doppler Filtering (`BPSYS`, `BPDIAS`)
- **Systolic Slice**: `line[57:60].strip()`
- **Diastolic Slice**: `line[60:63].strip()`
- **Logic**:
  - Systolic valid range: `43 <= SBP <= 289`. Code `0` indicates unobtainable/pulseless.
  - Diastolic valid range: `22 <= DBP <= 190`. Code `998` indicates Doppler present (sanitized to `None`).
  - **Physiological Consistency Check**: If both `bp_systolic` and `bp_diastolic` are populated, the adapter verifies `bp_systolic > bp_diastolic`. If `bp_diastolic >= bp_systolic` (an inverted or invalid reading), both fields are sanitized to `None` to prevent invalid inference artifacts.

### 3.7 Pulse Oximetry (`POPCT`)
- **Slice**: `line[63:66].strip()`
- **Logic**:
  - Valid range: `0 <= raw <= 100`.
  - Values outside 0–100, `-9`, `-8`, or blanks are sanitized to `spo2 = None`.

---

## 4. Ground Truth Label Proxy Mapping: `nhamcs_immediacy_v1`

NHAMCS assesses emergency arrival immediacy (`IMMEDR`) using a 5-level clinical urgency scale. The canonical `nhamcs_immediacy_v1` proxy mapping aligns these 5 immediacy levels to VitalNet's three clinical tiers:

| IMMEDR Code | CDC Codebook Immediacy Definition | Target VitalNet Tier | Tier Index | Clinical Rationale |
|---|---|---|---|---|
| `1` | Immediate (< 1 minute) | `EMERGENCY` | `2` | Resuscitation required; acute life threat |
| `2` | Emergent (1–14 minutes) | `EMERGENCY` | `2` | High-risk physiological crisis; immediate care required |
| `3` | Urgent (15–60 minutes) | `URGENT` | `1` | Significant acute illness requiring rapid stabilization |
| `4` | Semi-urgent (61–120 minutes) | `ROUTINE` | `0` | Stable presentation; delayed evaluation acceptable |
| `5` | Nonurgent (121 minutes – 24 hours) | `ROUTINE` | `0` | Non-acute complaint; routine outpatient-level presentation |

### 4.1 IMMEDR Sentinel Exclusions
Encounters with sentinel or non-triage `IMMEDR` codes cannot be evaluated for triage agreement. These records are excluded from evaluation batches and tracked in explicit exclusion counters:
- `sentinel_immedr_minus_9` (`-9`): Blank / Not reported.
- `sentinel_immedr_minus_8` (`-8`): Unknown.
- `sentinel_immedr_0` (`0`): No triage performed.
- `sentinel_immedr_7` (`7`): Visit occurred in an ED that does not conduct nursing triage.

---

## 5. Strict Partial-Input Mode Enforcement

Because NHAMCS 2022 records reason-for-visit and ICD-10 diagnostic codes rather than standardized free-text chief complaints or VitalNet's allow-listed structured symptoms, the evaluation MUST execute in strict **`partial_input` mode**:

```python
form_data = {
    "patient_age": patient_age,          # 0-94 (int)
    "patient_sex": patient_sex,          # "male" | "female"
    "bp_systolic": bp_systolic,          # Optional[int]
    "bp_diastolic": bp_diastolic,        # Optional[int]
    "spo2": spo2,                        # Optional[int]
    "heart_rate": heart_rate,            # Optional[int]
    "temperature": temperature,          # Optional[float]
    "symptoms": [],                      # STRICT: Always empty list
    "chief_complaint": "",               # STRICT: Always empty string
    "complaint_duration": "",            # Empty string
    "location": "",                      # Empty string
    "known_conditions": "",              # Empty string
    "current_medications": "",           # Empty string
    "is_pregnant": None,                 # None
}
```

### 5.1 Prohibition on Synthetic Complaint Fabrication
- **No RFV Code Parsing**: Code must NEVER synthesize chief complaint text from Reason for Visit fields (`RFV1`, `RFV2`, `RFV3`).
- **No Symptom Tag Generation**: Code must NEVER synthesize symptom tags from ICD-10-CM diagnosis codes (`DIAG1`, `DIAG2`, etc.).
- **Execution Metadata**: Reports must explicitly declare `chief_complaint_available: false` and `symptoms_available: false`.

---

## 6. Survey Weight Policy & Methodological Rationale

CDC NHAMCS includes survey design variables (`PATWT`, `CPSU`, `CSTRATM`) designed to extrapolate sample visits to national US emergency department encounter totals.

### 6.1 Strict Metric Weighting Prohibition
**Survey sample inflation weights (`PATWT`) MUST NEVER be applied to model diagnostic metrics** (including sensitivity, specificity, PPV, NPV, confusion matrices, under-triage rates, or Expected Calibration Error).

### 6.2 Methodological Rationale
1. **Clinical Decision-Support Evaluation is Observational & Per-Patient**: Model validation evaluates the mathematical discrimination of the classifier across individual patient presentations. Weighting records by national frequency statistics distorts diagnostic performance: inflating the statistical weight of high-frequency, low-acuity presentations masks vital safety failure modes in high-acuity presentations.
2. **Safety-Critical Under-Triage Measurement**: Under-triage rate must reflect the exact empirical proportion of severe clinical cases missed by the classifier within the observed cohort, without artificially deflating severe cases through demographic re-weighting.
3. **Metadata Retention**: Survey weights (`PATWT`) are calculated and reported strictly within high-level demographic metadata for epidemiological characterization.

---

## 7. Explicit Non-Claims & Scope Limitations

1. **Retrospective Cohort Proxy**: CDC NHAMCS 2022 represents hospital-based emergency department visits in the United States. It serves as a proxy benchmark for vital-sign triage discrimination; it does NOT represent primary healthcare centers (PHCs) or community health worker (ASHA) workflows in rural India.
2. **Partial-Input Limitation**: Performance measured in partial-input mode reflects vital-only discrimination and does not measure full multi-modal performance when detailed clinical text and symptom checklists are present.
3. **No Medical Device or Clinical Efficacy Claim**: Results from this evaluation harness do not constitute medical device certification, clinical trial validation, or autonomous diagnostic safety proof under CDSCO or FDA frameworks.
