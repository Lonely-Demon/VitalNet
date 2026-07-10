# VitalNet — Data Acquisition & External Validation Strategy

> **The honest answer to "can we scrape data to get closer to clinically
> safe?"** Short version: **indiscriminate web scraping — no** (it is illegal
> for patient data, and unvalidated data makes a clinical model *more*
> dangerous, not safer). **Principled acquisition of specific, real,
> already-labelled public datasets for _external validation_ — yes, and it is
> the single highest-probability way to move VitalNet toward clinical safety
> given that no clinician is available right now.** This document says exactly
> which datasets, how to use them legally, and how they plug into the
> evaluation harness.

Companion to `MODEL_CARD.md`, `CLINICAL_RISK_MANAGEMENT.md`, and
`VALIDATION_PROTOCOL.md`.

## 1. The reframe: you don't need more data, you need real ground truth

VitalNet already has 36,000 training rows. More synthetic rows change nothing.
The thing it has *never* had is **a real patient with a real acuity label and a
real outcome.** That gap is hazard **H2** in the risk file, currently
`UNQUANTIFIED` — and it is the dominant open risk.

So the goal of acquiring public data is **not** to retrain on more data. It is
to **externally validate**: run VitalNet's existing engine on real patients and
measure, for the first time, how its triage compares to real clinician acuity
and real outcomes. That single act converts H2 from "unknown" to "measured on a
proxy population" — real, defensible progress you can do *tonight's-plan* style,
without a clinician.

Ranked uses of public data, most to least valuable for safety:

1. **External validation set** (highest value) → `scripts/evaluate_on_real.py`.
2. **Realistic input distribution** for robustness/drift reference (real vitals
   distributions, missingness patterns).
3. **Real training data** (lowest priority, highest risk): only after (1) shows
   it's warranted, and only with explicit domain-adaptation handling — a US/Korean
   ED distribution is *not* a rural Indian PHC.

## 2. What "scraping / reverse-engineering" can and cannot do

| Idea | Verdict | Why |
|---|---|---|
| Scrape websites/forums for patient data | **No** | Illegal (privacy law/DPDP), unethical, and unlabelled/unvalidated → injects uncontrolled bias. A clinical model's safety comes from *validated ground truth*, not volume. |
| Download curated public **research** datasets (PhysioNet/Kaggle/HF) under their licence | **Yes** | These are de-identified, ethically-released, and *labelled by clinicians* — exactly the ground truth you lack. |
| "Reverse-engineer" open clinical **models** | **Partial** | You can't extract safety from weights. But you *can* run an open triage model as an **external comparator** on the same inputs and measure agreement. Treat it as a second opinion, never as ground truth. |
| Use published **validated scoring rules** (ESI, KTAS, NEWS2, SATS, WHO ETAT/IMCI) | **Yes — do this** | This is "reverse-engineering clinical knowledge" done right: peer-reviewed, validated distilled rules. Grounds your labels and gives reference thresholds. |

## 3. The dataset shortlist (concrete, with the catches)

| Dataset | What it gives | Access / licence | Population caveat | Schema fit to VitalNet |
|---|---|---|---|---|
| **MIMIC-IV-ED** (PhysioNet v2.2) | ~425k real ED stays; `triage` table = temperature, heartrate, resprate, o2sat, sbp, dbp, pain, **acuity (ESI 1–5)**, chiefcomplaint; linkable to MIMIC-IV for outcomes (admission, mortality) | **Credentialed**: free, but requires PhysioNet account + **CITI "Data or Specimens Only Research" training** + signed DUA (~a few days). **Redistribution prohibited.** | US, urban academic ED (Beth Israel, 2011–2019) — **not** rural India | **Near 1:1.** Almost every VitalNet field maps directly; only respiratory rate is extra and altitude/pregnancy differ. Best external-validation target by far. |
| **eICU-CRD** (PhysioNet) | Multi-center US ICU vitals/outcomes | Credentialed (as above) | US ICU, sicker population | Partial (ICU, not triage) |
| **Kaggle KTAS** ("ER triage", ~1,267 patients, Korea 2016–17) | age, sex, vitals, complaint, **KTAS 1–5** clinician label | Kaggle account; **check the dataset's licence page before use** | Korean urban ED, small n | Good; quick sanity check while MIMIC credentialing is pending |
| **Hugging Face** clinical sets | Mostly clinical **NLP** (MIMIC-derived text, MedQA, i2b2) | Per-dataset licence; MIMIC mirrors **still require PhysioNet credentialing** | varies | Useful for the **LLM/chief-complaint** side, not the tabular triage classifier |
| **Validated instruments** (ESI handbook, KTAS, NEWS2, MEWS, **SATS**, **WHO ETAT/IMCI**) | Reference thresholds + mappings | Public literature | — | Grounds labels (Validation Protocol A5) and gives comparator rules |

## 4. Hard guardrails (non-negotiable)

- **Never commit patient data to this repo** — even "de-identified". Add a
  gitignored `backend/data/` dir; provide a **downloader script + a datasheet**,
  never the rows. PhysioNet's DUA explicitly prohibits redistribution and any
  re-identification attempt.
- **Licence-check every dataset** individually and record it in the datasheet.
- **Treat all acquired data under the same DPDP posture** as production PHI.
- **State the population mismatch on every result.** "Sensitivity 0.94 on
  MIMIC-IV-ED (US ED)" is *not* "safe for rural India" — it is one external
  validation on a proxy population. Over-claiming here would repeat the exact
  synthetic-data honesty failure the model card warns against.

## 5. The workflow (how a dataset becomes a safety result)

```
acquire (credentialed/licensed)
  └─ map to VitalNet schema  ────────────►  datasheet + schema-map table (§6)
       └─ run scripts/evaluate_on_real.py  ─►  sens/spec/PPV/NPV+CIs, calibration,
            │                                   subgroup, UNDER-TRIAGE safety analysis
            └─ report to TRIPOD+AI  ────────►  update CLINICAL_RISK_MANAGEMENT.md H2
                                                (UNQUANTIFIED → measured-on-proxy)
```

The harness (`scripts/evaluate_on_real.py`, added in this PR) already maps the
5-level ESI/KTAS acuity scales to VitalNet's 3 tiers with documented,
overridable rules, runs the real production `predict_triage()` per row, and
computes the safety-critical **EMERGENCY under-triage rate with a confidence
interval** — the number that actually matters. It runs today in `--self-test`
mode (synthetic, proves the machinery) and against a real CSV the moment you
have one.

## 6. Schema map (VitalNet ← dataset) and datasheet template

**Schema map to fill per dataset** (example: MIMIC-IV-ED):

| VitalNet field | MIMIC-IV-ED `triage` field | Notes |
|---|---|---|
| patient_age | (from `patients.anchor_age`) | join on subject_id |
| patient_sex | `patients.gender` | map M/F |
| bp_systolic / bp_diastolic | sbp / dbp | |
| spo2 | o2sat | |
| heart_rate | heartrate | |
| temperature | temperature | **°F → °C convert** |
| chief_complaint | chiefcomplaint | free text |
| (n/a) | resprate | VitalNet has no RR field |
| **reference_acuity** | acuity (ESI 1–5) | maps 1–2→EMERGENCY, 3→URGENT, 4–5→ROUTINE (overridable) |
| outcome (optional) | linked admission/mortality | strongest ground truth |

**Datasheet** (per *Datasheets for Datasets*, Gebru et al.): record source,
licence, collection period, population, de-identification method, class
prevalence, known biases, and the exact schema mapping used. Keep it in
`backend/data/<dataset>/DATASHEET.md` (the data itself stays gitignored).

## 7. Honest bottom line

External validation on MIMIC-IV-ED is the **highest-probability, do-it-without-a-
clinician** step available, and it directly attacks the dominant hazard (H2). It
gives you the first real-patient signal VitalNet has ever had. But be clear-eyed:
it validates on a **US ED proxy population**, not rural Indian primary care.
It **raises** the floor of your safety case; it does **not** clear the deployment
gate, which still requires a rural-population prospective study and clinical
sign-off (`VALIDATION_PROTOCOL.md` "Definition of done"). Do it — and report it
with the same honesty as everything else here.
