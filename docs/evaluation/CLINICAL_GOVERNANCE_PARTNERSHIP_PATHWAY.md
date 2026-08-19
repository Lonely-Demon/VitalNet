# Clinical Governance and Partnership Pathway

> **Status:** Planning and outreach preparation only. This document does not constitute clinical approval, institutional endorsement, ethics approval, patient-data access, pilot authorization, or deployment permission.

## Why this is the next bottleneck

VitalNet’s completed public-data evaluation and synthetic remediation work are sufficient to identify a serious missing-context safety problem, but they cannot define acceptable clinical thresholds, reviewer workload, or the operational meaning of an insufficient-information state. The next advancement therefore requires a qualified clinical owner and an implementation partner with experience in frontline public-health workflows.

The project should pursue a two-partner model. A clinical-research organization or public medical institution should own protocol review, clinical acceptance criteria, ethics routing, and safety oversight. A frontline implementation organization should challenge ASHA usability, language, supervision, connectivity, and escalation workflow assumptions. Engineering remains responsible for reproducibility, isolation, and aggregate reporting, but not clinical acceptance.

## Evidence-based partnership targets

| Target | Relevant evidence | Appropriate first request | Boundary |
|---|---|---|---|
| **Centre for Chronic Disease Control (CCDC)** | CCDC describes a guideline-based CDSS developed with clinical, public-health, IT, and government experts; it reports multi-setting evaluation, randomized and cluster-randomized studies, scale-up, AIIMS collaboration, and a DHR-registered ethics committee [1] [2] | Request a short methodological conversation or referral regarding the missing-context protocol, human-escalation workflow, and correct ethics route | Do not request endorsement, patient data, clinical sign-off, or deployment |
| **Khushi Baby** | Khushi Baby describes a frontline technology platform, Health Action Centers, and work with governments in Rajasthan, Maharashtra, and Karnataka [3]. The ASHABot case describes ASHA qualitative research, doctor/public-health collaboration, and nurse fallback for unanswered questions [4] | Request feedback on ASHA workflow fit, supervision, language, and human fallback design | Do not ask ASHAs to approve clinical criteria, test an unsafe model, or share patient records |
| **AIIMS or a state public medical college** | AIIMS is identified as a CCDC CDSS supporting organization [1] and can represent a plausible academic clinical-governance route | Seek a faculty or department referral for protocol review and a supervised, non-interventional study pathway | Do not claim affiliation or imply support without written confirmation |
| **DHR/NECRBHR pathway** | ICMR publishes national AI ethics guidance, and DHR maintains the National Ethics Committee Registry for Biomedical and Health Research [5] [6] | Identify the appropriate registered institutional ethics committee before any human-participant or prospective work | Guidance and registry information are not approvals |

## Proposed study ladder

| Stage | Purpose | Data and users | Gate to proceed |
|---|---|---|---|
| 0. Governance consultation | Challenge field requirements, escalation semantics, metrics, and clinical ownership | Synthetic artifacts and documents only | Named qualified clinical owner and written protocol comments |
| 1. Synthetic correction | Freeze full-context labels before masking and compare baseline/candidate arms | Synthetic encounters only | Zero label disagreement, reproducible aggregate results, no leakage |
| 2. Workflow tabletop | Walk through unknown, declined, contradictory, extreme-vital, offline, and reviewer-unavailable cases | Scripted scenarios; no patient data | Approved escalation states and accountability map |
| 3. Retrospective aggregate audit | Answer a distinct question using a lawful public source | Local-only de-identified data; aggregate reports | Source card, rights/data-use basis, approved protocol, leakage controls |
| 4. Silent or shadow evaluation | Compare system output with clinician decisions without influencing care | Approved site data under IEC/IRB oversight | Pre-registered protocol, site PI, data custodian, incident pathway, rollback plan |
| 5. Limited supervised pilot | Evaluate usability, burden, escalation completion, and safety under direct human control | Approved site and minimum necessary data | Explicit clinical go/no-go decision and monitoring plan |

## Minimum governance package

Before any live or human-participant evaluation, the project must have a named site principal investigator, a qualified clinical reviewer, an accountable data custodian, a registered institutional ethics route, a data-minimization and retention plan, a patient/worker consent or waiver decision, an incident-reporting process, a reviewer-unavailable policy, a rollback plan, and pre-registered safety metrics.

The first outreach should contain only a one-page concept note and evidence summary. It should state that VitalNet is an offline-first research prototype; the production model remains frozen; public proxy evaluations exposed serious missing-context under-triage; the next study is synthetic-first; and no live clinical use or patient data is being requested.

## Hard stops

The project must not proceed to live use if no qualified clinical owner can be identified, if the escalation queue has no accountable reviewer, if an ethics/data-use route is unavailable, if patient-level data cannot remain within the approved boundary, if the site cannot document incident response and rollback, or if the candidate policy increases ordinary-tier emergency misses without an approved mitigation.

A partnership conversation is not clinical validation. A successful synthetic study is not clinical acceptance. An organization’s public description of prior work is not an endorsement of VitalNet.

## References

[1]: https://ccdcindia.org/projects/cdss/ "CCDC Clinical Decision Support System project"
[2]: https://ccdcindia.org/collaborations/ "CCDC collaborations"
[3]: https://www.khushibaby.org/ "Khushi Baby official site"
[4]: https://www.microsoft.com/en-us/research/story/how-ashabot-empowers-rural-indias-frontline-health-workers/ "Microsoft Research: ASHABot and rural India’s frontline health workers"
[5]: https://www.icmr.gov.in/ethical-guidelines-for-application-of-artificial-intelligence-in-biomedical-research-and-healthcare "ICMR Ethical guidelines for application of AI in biomedical research and healthcare"
[6]: https://www.dhr.gov.in/offerings/schemes-and-services/details/national-ethics-committee-registry-for-biomedical-and-health-research-necrbhr-UTNyUTMtQWa "DHR National Ethics Committee Registry for Biomedical and Health Research"
