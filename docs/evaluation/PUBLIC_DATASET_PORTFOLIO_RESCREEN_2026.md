# Public Dataset Portfolio Rescreen — 2026-08-19

## Purpose and boundary

This document records a focused rescreen of public emergency-department data sources after VitalNet’s public-data evaluation cycle was closed. It is a **portfolio and access assessment**, not a new evaluation authorization. No dataset described here was downloaded, transformed, scored, or used for inference as part of this rescreen.

The current evidence already establishes a serious missing-context safety signal. New data should therefore be acquired only when it answers a distinct question, has a defensible reference standard, and can be handled under the repository’s local-only and aggregate-only boundary. No source in this document supports clinical validation, regulatory clearance, rural/ASHA equivalence, or deployment readiness.

## Rescreened candidates

| Candidate | Verified characteristics | Access and provenance status | Appropriate VitalNet role | Decision |
|---|---|---|---|---|
| Yale ED admission-at-triage dataset | 560,486 × 972 de-identified ED dataframe; triage fields, ESI, chief complaint, demographics, and admission outcome are described by the repository and source paper | Public repository exists, but the reviewed repository page did not expose a clear SPDX license; rights should be clarified before acquisition | Separate admission-risk and input-contract analysis; ESI must be excluded if used as a target | **Do not download or score until rights clarification** |
| MC-MED v1.0.1 | Multimodal ED monitoring resource with triage reports, free-text notes, continuous vital signs, and physiologic waveforms | PhysioNet restricted access; requires credentialing, CITI training, and a project DUA | Possible future multimodal or monitoring study, not an open benchmark | **Not immediately available; no bypass or unofficial copy** |
| MIETIC v1.0.0 | 9,629 structured ESI triage cases derived from MIMIC-IV v3.1, MIMIC-IV-ED v2.2, and MIMIC-IV-Note v2.2; includes generated instruction data and a 50-case expert-validated sample | PhysioNet-hosted extension derived from credentialed MIMIC sources; not an independent cohort and not a clean substitute for full MIMIC-IV-ED | Parser, contract, and corpus-quality inspection; possibly a separate synthetic/LLM-corpus audit | **Do not treat as independent external validation** |
| Malta Mater Dei ED dataset | 653,546 ED visits from 2017–2022; paper reports ESI, admission, and admitting-ward prediction tasks, with stage-specific triage and laboratory inputs | The reviewed open paper did not expose a direct downloadable dataset or sufficiently explicit standalone data-use statement | Potential ESI/input-contract benchmark if a direct, lawful data release is located and verified | **Lead only; rights and file availability unresolved** |
| FedMML ED Triage | Synthetic encounters with ESI 1–5, complaints, notes, vitals, labs, and simulated missingness | Dataset card describes CC BY 4.0 but access requires contact-sharing acceptance | Synthetic missingness and contract ablation only | **Separate synthetic study; not real external validation** |
| Official MIMIC-IV-ED Demo | Small official demonstration release with ED triage and vital-sign tables | Official PhysioNet demo license; distinct from credentialed full MIMIC | Adapter and parser smoke test only | **Optional demo-only operation; no benchmark claim** |

## Findings

The rescreen did not identify a new immediately open, independent emergency-acuity dataset that is clearly superior to the completed KTAS benchmark for VitalNet’s current question. The Yale dataset is large but its primary target is admission rather than emergency severity and its rights statement requires clarification. MC-MED remains credentialed. MIETIC is derived from the same MIMIC ecosystem that is already deferred and includes generated instruction content, so it cannot be treated as a new independent benchmark. The Malta dataset is promising but not yet operationally downloadable under a verified data-use path.

The practical conclusion is that **more dataset hunting is no longer the primary bottleneck**. The highest-value next work is to finish the corrected canonical-label synthetic study, quantify the escalation-workload tradeoff, and prepare a qualified clinical-governance review package. A later Yale or Malta operation may be justified for a distinct admission or ESI question, but neither should be used to avoid the clinical-governance gap.

## Acquisition rules for any future candidate

Before any future local acquisition, the source card must record the official provenance URL, exact file URL, release/version, checksum after local placement, rights or DUA basis, field schema, label semantics, post-triage leakage risks, intended input contract, exclusion rules, and non-claims. Any real-data adapter must fail closed by default, emit aggregate-only output, assert zero patient-level leakage, and remain outside production code.

## References

[1]: https://github.com/yaleemmlc/admissionprediction "Yale admission-at-triage repository"
[2]: https://doi.org/10.1371/journal.pone.0201016 "Hong et al. (2018), Predicting hospital admission at emergency department triage using machine learning"
[3]: https://physionet.org/content/mc-med/1.0.1/ "PhysioNet MC-MED v1.0.1"
[4]: https://physionet.org/content/mietic/1.0.0/ "PhysioNet MIMIC-IV-Ext Triage Instruction Corpus"
[5]: https://link.springer.com/article/10.1186/s12911-025-02941-9 "Agius et al. (2025), Malta ED ESI and admission dataset paper"
[6]: https://huggingface.co/datasets/olaflaitinen/fedmml-ed-triage "FedMML ED Triage dataset card"
[7]: https://physionet.org/content/mimic-iv-ed-demo/2.2/ "Official MIMIC-IV-ED Demo"
[8]: https://github.com/Lonely-Demon/VitalNet/blob/dev/docs/EVALUATION_DATA_BOUNDARY.md "VitalNet evaluation data boundary"
