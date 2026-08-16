# VitalNet Public-Data Evaluation Closure and Safety Remediation Decision

> **Status**: Evaluation cycle closed on `dev`; remediation design is the next phase.
> **Model status**: Frozen throughout the evaluation cycle. No retraining, tuning, threshold changes, or classifier modifications were performed.
> **Promotion status**: No evaluation work was promoted to `test`, `main`, preproduction, Render, Vercel, or Supabase.

## Executive conclusion

VitalNet has completed a substantial public-data evaluation cycle across two real public-data scoring benchmarks, one inspection-only real dataset, and a synthetic ASHA input-contract study. The results are not evidence of clinical validation. They consistently identify a safety-critical weakness when symptoms and clinical context are unavailable: the frozen classifier under-triages proxy-emergency encounters at unacceptable rates in the evaluated cohorts.

The next phase is therefore **safety remediation design**, not another dataset hunt. A new dataset is unlikely to change the central finding that VitalNet’s current input contract and missing-context behavior require investigation before any clinical-facing claim or promotion.

## Completed evidence gates

| Evidence source | Role | Result | Decision |
|---|---|---|---|
| Iran ED, BaniHassan et al. (2024) | Gate 1A aggregate inspection | 143,582 records; only 91 complete five-vital records (0.0634%); 99.91% admission-linkage match | Scoring permanently refused because the published labels are binary and vital sparsity makes three-tier scoring scientifically invalid. |
| CDC NHAMCS 2022 ED | Gate 1B partial-input proxy benchmark | One authorized run; `EMERGENCY` sensitivity 14.4%; 85.6% of proxy-emergency cases missed | Serious safety signal. No further NHAMCS scoring authorized in the completed cycle. |
| Synthetic ASHA input-contract study | Synthetic ablation | Removing structured symptoms reduced emergency sensitivity from 99.13% to 86.01%; NHAMCS-like arm reached 84.20%; removing observations/medications caused zero tier changes | Symptoms/context are material input-contract variables; study did not alter the frozen model. |
| Korean KTAS 2019 ED | Gate 3A open external benchmark | 1,267 records; primary emergency sensitivity 25.2%; vital-only sensitivity 17.9%; complete five-vital coverage 44.44% and confined to Regional ED | Serious safety signal. Results are cohort-specific and not clinical validation. |
| MIMIC-IV-ED v2.2 | Deferred Gate 2 | Credentialed access was not completed; no full MIMIC data were downloaded or scored | Deferred, not used as a blocker for closure. Adapter foundation remains governed and local-only. |

## Korean KTAS findings

The KTAS expert labels were mapped under the pre-registered `ktas_v1` contract: KTAS 1–2 to `EMERGENCY`, 3 to `URGENT`, and 4–5 to `ROUTINE`. The primary `ktas_triage_contract_v1` arm used age, sex, five vitals, and deterministic bilingual allow-listed symptoms, with raw complaint text discarded. It achieved 49.49% overall agreement and 25.2% emergency sensitivity (95% Wilson CI 20.2%–31.0%), missing 184 of 246 reference-emergency encounters.

The separately labeled `ktas_vital_only_partial_v1` arm used no symptoms or complaint text. It achieved 46.65% overall agreement and 17.9% emergency sensitivity (95% Wilson CI 13.6%–23.2%), missing 202 of 246 reference-emergency encounters. Relative to the primary arm, emergency sensitivity fell by 7.3 percentage points and overall under-triage rose by 12.5 percentage points.

Only 563 of 1,267 KTAS records had complete five-vital data. Every complete-five-vital record came from Regional ED Group 2; Local ED Group 1 had no numeric oxygen-saturation values. Complete-vital subgroup results must therefore not be generalized to both sites.

## Cross-dataset interpretation

The public-data results should not be averaged into a single “validation score.” The datasets measure different proxies, populations, and input contracts. The correct synthesis is directional:

1. The Iran ED source demonstrates that public-data availability does not guarantee a valid scoring target; label granularity and vital completeness matter.
2. NHAMCS demonstrates poor emergency sensitivity when VitalNet receives only partial vital-sign input and no symptoms/context.
3. KTAS reproduces the emergency under-triage problem in a real ED acuity benchmark, with low emergency sensitivity in both the symptom-inclusive and vital-only arms.
4. The ASHA synthetic study explains part of the cross-dataset pattern: structured symptoms/context materially affect emergency sensitivity, while the tested observation/medication fields did not move tiers.
5. The results do not establish causality, clinical harm in deployment, or a suitable remediation threshold. They establish a high-priority safety risk requiring qualified clinical review and a controlled remediation study.

## Current product and governance posture

VitalNet remains a **supervised decision-support prototype**, not a clinically validated or autonomous triage product. No evaluation result supports promotion to preproduction or deployment. The model and production inference path remain frozen. All real datasets and generated reports remain in gitignored local directories; tracked code and documentation contain no patient-level rows, identifiers, raw complaints, or record-level predictions.

MIMIC-IV-ED remains deferred because credentialing was not completed. Its absence is no longer the immediate blocker for deciding the next engineering action. The KTAS and NHAMCS safety signals are sufficient to justify remediation design.

## Safety Remediation Gate

The next work package should be design-only until approved. It should define:

- A missing-context policy for absent symptoms, complaint text, and structured observations.
- Required versus optional ASHA intake fields and explicit “insufficient information” behavior.
- A safe escalation or human-review path when emergency sensitivity is uncertain.
- Pre-registered safety metrics, subgroup strata, and non-inferiority or minimum-performance criteria defined with qualified clinical input.
- A frozen-baseline comparison protocol for any candidate input-contract or model change.
- Synthetic tests first, followed by separately authorized reruns on already acquired public datasets.
- A prohibition on production activation until clinician review, prospective/shadow evidence, and governance requirements are satisfied.

The remediation design must not silently convert an engineering threshold into a clinical acceptance criterion. A qualified clinician or domain reviewer must participate in defining what “acceptable” emergency sensitivity and under-triage mean for the intended ASHA/PHC use case.

## Next-step decision

The public-data evaluation cycle is closed. VitalNet should now produce a design-only safety-remediation PR on `dev`. That PR must not change the frozen production model, APIs, frontend, deployment configuration, or database. It should create the study design, acceptance-criteria placeholders requiring clinical sign-off, input-contract requirements, and test plan. Any future candidate implementation and real-data rerun requires separate review and explicit authorization.
