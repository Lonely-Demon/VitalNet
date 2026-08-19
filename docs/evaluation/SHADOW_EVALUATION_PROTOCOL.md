# VitalNet Controlled Shadow-Evaluation Protocol

> **Status:** Research protocol and governance artifact only. This document does not authorize clinical use, patient-data access, prospective recruitment, silent deployment, or any change to the frozen production runtime.
>
> **Protocol version:** `shadow-evaluation-v1.0.0`
>
> **Applies to:** A future, site-governed comparison in which VitalNet runs in parallel with ordinary clinical workflow while its output remains hidden from care teams and cannot influence patient care.

## 1. Purpose and decision question

VitalNet's completed public-data evaluation cycle identified serious emergency under-triage signals when symptoms, complaints, or vital observations are incomplete. The synthetic safety-remediation study showed that a candidate missing-context and human-escalation policy can separate ordinary tiering from insufficient-information routing in a controlled environment. The next evidence question is narrower and more demanding:

> **In an approved clinical setting, does the frozen VitalNet baseline and any separately identified research candidate behave consistently with the pre-registered input contract, safety guardrails, and workflow burden when compared with the clinician's real decision, without influencing care?**

The shadow study is intended to surface failure modes, missingness patterns, disagreement patterns, and operational burden before any output is shown to a clinician for decision support. It is not a clinical validation claim, an efficacy study, a regulatory submission, or permission to deploy.

This protocol extends Part C of `docs/VALIDATION_PROTOCOL.md`, the four-state input contract in `HUMAN_ESCALATION_WORKFLOW_DESIGN.md`, the five-layer guardrail architecture in `docs/CLINICAL_GOVERNANCE.md`, and the aggregate-only controls in `docs/EVALUATION_DATA_BOUNDARY.md`.

## 2. Non-negotiable scope boundaries

The following constraints apply to every preparation, execution, analysis, export, and discussion of a shadow study:

| Boundary | Protocol requirement |
|---|---|
| Clinical influence | VitalNet output is hidden from clinicians and cannot alter triage, referral, treatment, queue order, documentation, or communication. |
| Production freeze | The frozen production model, thresholds, feature engineering, rules, APIs, frontend, database schema, and deployment configuration remain unchanged. |
| Research candidate separation | Any candidate missing-context policy is evaluated as a separately versioned research arm. It must not be silently substituted for the production baseline. |
| Data location | Patient-level data remains inside the approved site-controlled environment. It is not copied to Git, CI, chat, cloud APIs, personal storage, or the public repository. |
| Output boundary | Engineering receives only the minimum approved aggregate report. Patient-level rows, identifiers, raw complaints, free text, dates of birth, contact details, and exact timestamps are prohibited in exported artifacts. |
| Reference standard | The clinician's real decision is recorded independently of VitalNet and is not rewritten to agree with the system. The reference definition, timing, and adjudication plan must be pre-registered. |
| Claims | Results are described as shadow-study observations. They must not be called clinical validation, clinical efficacy, rural equivalence, ASHA equivalence, or regulatory clearance. |
| Promotion | Shadow-evaluation engineering remains confined to `dev` until a separate governance decision authorizes a controlled site workflow. No promotion to `test`, `main`, preproduction, or live deployment is implied. |

## 3. Prerequisites and hard-stop gates

A shadow study must not begin, even in a technically silent mode, until every prerequisite in this section is documented and approved by the accountable governance structure. Engineering cannot waive a missing clinical or ethics prerequisite.

### 3.1 Mandatory prerequisites

| Gate | Required evidence | Hard-stop condition |
|---|---|---|
| Named clinical owner | A named qualified clinician serving as site principal investigator or clinical governance owner, with dated written acceptance of the protocol scope | **No clinical owner → no shadow.** |
| Site and workflow owner | A named site or implementation owner who can describe the actual intake, triage, referral, and reviewer workflow | No accountable workflow owner → no shadow. |
| Data custodian | A named person or institution responsible for lawful access, minimization, retention, deletion, and breach response | No data custodian → no shadow. |
| Ethics route | Institutional Ethics Committee/IRB determination, waiver, exemption, or other documented route appropriate to the study design and jurisdiction | **No ethics route → no shadow.** Public registry information is not approval. |
| Reference standard | Written definition of the clinician decision, timing, allowable overrides, adjudication process, and inter-rater plan | No independent reference standard → no shadow. |
| Input contract | Versioned field dictionary, four-state symptom-screening state, provenance requirements, missingness representation, and contradiction handling | Any blank state that can be interpreted as a negative → no shadow. |
| Incident pathway | Named incident commander, clinical operations lead, security/data-protection contact, severity definitions, notification route, and response timing | No operational incident path → no shadow. |
| Rollback plan | Tested method to stop the shadow process, disable computation, preserve only approved audit evidence, and confirm that care is unaffected | **No rollback plan → no shadow.** |
| Retention and deletion | Site-approved retention duration, deletion trigger, export policy, and proof-of-deletion procedure | No data-lifecycle control → no shadow. |
| Security review | Access control, local execution boundary, encryption/transport decision, audit logging, and credential handling | Uncontrolled access or unreviewed export path → no shadow. |
| Pre-registration | Frozen protocol version, model/policy versions, metrics, subgroup strata, analysis plan, and deviation policy | No pre-registered analysis → no shadow. |

### 3.2 No-go conditions during execution

The study must pause immediately if VitalNet output becomes visible to a clinician or operator, influences care or queueing, is used to generate a patient-facing instruction, escapes the approved data boundary, or cannot be reliably separated from the ordinary clinical record. It must also pause if the independent reference decision is missing at a rate that invalidates the pre-registered denominator, if the site cannot provide the accountable reviewer defined in the protocol, or if a safety or privacy incident is suspected.

A pause is not a failure of the project. It is the required containment action while the clinical owner and incident team determine whether the study can resume, must be amended, or must be terminated.

## 4. Intended shadow design

The study is an observational, parallel-output comparison. The clinical team conducts ordinary care using its normal local protocol. VitalNet receives only the minimum necessary structured intake fields after the ordinary workflow has captured them. The VitalNet output is stored in a segregated research channel and remains unavailable to the care team until the pre-defined study close and governance review.

The system must not request additional measurements, ask a worker to alter the intake, reorder a queue, trigger an alert, or create a visible recommendation. If an input is incomplete, the study records the incompleteness as an input-contract observation; it must not manufacture a value or prompt a clinical action merely to improve model completeness.

The production baseline and a research candidate, if included, must run against the same frozen encounter representation. Reference decisions are captured before any post hoc comparison. If the candidate contains a non-triage state such as `INSUFFICIENT_INFORMATION_FOR_CDS`, that state is not a clinical tier and must be analyzed separately from the ordinary `ROUTINE`/`URGENT`/`EMERGENCY` confusion matrix.

### 4.1 Required temporal ordering

1. The patient receives ordinary site care under the site's approved protocol.
2. The clinician or designated care team records the independent reference decision and any permitted immediate operational outcome.
3. The approved research process captures the minimum necessary input representation and provenance metadata.
4. VitalNet computes hidden outputs in the segregated shadow environment.
5. The system writes only the approved local audit record and aggregate counters.
6. The data custodian produces the approved aggregate export after the pre-registered analysis window.

The exact ordering may be adapted by the clinical owner to avoid delaying care, but the adaptation must be recorded as a protocol deviation and must preserve the central rule: **VitalNet cannot influence care.**

## 5. Input contract and data minimization

The study inherits the four-state symptom taxonomy. A symptom list alone is not evidence that screening occurred.

| State | Meaning | Shadow interpretation |
|---|---|---|
| `positive_symptom` | One or more allow-listed danger signs were actively reported | Structured positive evidence is preserved with its provenance. |
| `explicit_negative_screen` | The operator actively screened the defined checklist and recorded that none were present | Explicit negative evidence; never inferred from an empty symptom list. |
| `unknown_or_not_asked` | The checklist was skipped, bypassed, or not asked | Missing evidence; no silent negative interpretation. |
| `declined_or_unavailable` | The patient could not or would not answer, or the operator could not collect the information | Unavailable evidence; no silent negative interpretation. |

The minimum candidate input dictionary contains only the fields required by the approved model contract: age band or approved age representation, biological sex representation if required, the five canonical vitals with explicit missingness, allow-listed structured symptoms, symptom-screening state, and collection provenance. Chief complaint text, observations, medications, known conditions, location, and other context may be excluded unless the clinical owner and data custodian document a specific necessity and approved handling rule.

Exact patient identifiers are not required by the engineering analysis. The site may retain a local linkage key under its own custody if needed for incident review, but that key must not leave the site and must not appear in the aggregate export. The engineering report must use counts and pre-registered strata only.

## 6. Accountability and reviewer model

The shadow phase does not delegate care to VitalNet. The site clinical owner remains accountable for the reference decision and the study's clinical interpretation. The data custodian controls access and export. Engineering controls versioning, deterministic execution, and leakage tests. The incident commander coordinates containment. A qualified clinical reviewer—not an engineer—decides whether any observed pattern is clinically acceptable, requires protocol amendment, or blocks progression.

| Role | Accountability before launch | Accountability during/after study |
|---|---|---|
| Clinical owner/site PI | Approves intended use, reference standard, ethics route, clinical metrics, and no-go criteria | Reviews safety findings, deviations, incidents, and continuation/termination decision |
| Frontline workflow owner | Confirms that capture does not alter ASHA/PHC work and that reviewer availability is realistic | Reports burden, missingness, language, connectivity, and workflow deviations |
| Data custodian | Approves field minimization, access, retention, deletion, and export | Controls the local dataset, audit trail, aggregate release, and destruction evidence |
| Engineering lead | Freezes code/model/policy versions and verifies synthetic harness and isolation controls | Runs the pre-registered analysis, maintains reproducibility evidence, and never sets clinical thresholds |
| Independent clinical reviewer | Challenges the clinical meaning of labels, escalation states, and safety metrics | Reviews disagreements and determines whether they represent a clinical concern |
| Incident commander | Confirms response contacts and rollback readiness | Leads pause, containment, communication, recovery, and post-incident review |

## 7. Pre-registered safety metrics

All metrics must be specified before the study window begins. Clinical acceptance thresholds are not invented by engineering; the clinical owner and governance body must define them or explicitly classify a metric as descriptive only.

### 7.1 Ordinary-tier performance

For encounters receiving an ordinary tier, report the three-tier confusion matrix, emergency sensitivity with Wilson 95% interval, emergency miss count and miss rate, EMERGENCY-to-ROUTINE drops, under-triage, over-triage, and tier distribution. The denominator must be explicit and must exclude non-triage states.

### 7.2 Non-triage routing

Report insufficient-information and indeterminate rates, reason-code counts, reference-tier distribution among escalated cases, emergency cases escalated, unresolved cases, and the denominator identity:

> `total_reference_emergencies = tiered_reference_emergencies + emergency_cases_escalated`

The combined quantity “emergency retention or escalation” may be shown only as an exploratory operational diagnostic. It must never be relabeled emergency sensitivity or clinical safety.

### 7.3 Operational burden

Report escalation volume per 100 encounters, reviewer queue size, queue age distribution, repeat measurement requests, manual-override proportion, unresolved queue proportion, and the percentage of encounters requiring protocol deviation. These are workflow observations, not clinical acceptance criteria unless the governance body says otherwise.

### 7.4 Input-contract integrity

Report the frequency of each symptom-screening state, the rate at which an empty symptom list is incorrectly paired with an explicit-negative state, contradiction rate, missingness strata for each canonical vital, provenance completeness, and invalid-payload rate. The study must preserve the distinction between unknown, declined, and explicitly negative evidence.

### 7.5 Safety behavior

Report deterministic extreme-vital preservation, hidden-output isolation, no silent downgrade during escalation, no fabricated ordinary tier, reference-label availability, and zero patient-level leakage in every exported artifact. Any violation is a protocol deviation or incident, not an ordinary metric fluctuation.

### 7.6 Reproducibility

Record protocol version, source-code commit, model version, candidate-policy version, input-contract version, analysis seed where synthetic fixtures are used, execution environment identifier, analysis-window identifier, and a cryptographic digest of the aggregate report. The digest is an artifact-integrity control, not a patient identifier.

## 8. Incident pathway and rollback

A clinical-safety concern, privacy concern, unintended visibility, or output-influence event is handled as an incident rather than silently corrected in the analysis. The existing severity model and five-phase response in `docs/INCIDENT_RESPONSE.md` apply, with the clinical owner added to the first triage decision whenever patient-care impact is possible.

### 8.1 Immediate containment

The operator or engineer must stop the shadow computation or disconnect the research channel, preserve the minimum approved audit evidence, prevent further export, notify the incident commander and clinical owner, and document whether any VitalNet output was visible or acted upon. If patient-care influence cannot be excluded, the event is treated as the higher plausible severity until reviewed.

### 8.2 Clinical review

The clinical owner determines whether the event could have changed care, whether affected encounters require site-level review, whether the reference standard remains valid, and whether the study must be terminated. Engineering does not downgrade a clinical concern because an aggregate metric appears acceptable.

### 8.3 Privacy and security review

The data custodian and security lead determine whether unauthorized access, export, retention, or re-identification occurred. The site's legal and data-protection obligations are handled by the accountable institution. No patient-level details are copied into engineering tickets, GitHub issues, chat, or the public repository.

### 8.4 Rollback definition

Rollback means disabling the shadow process and any scheduled invocation, removing the research output from the care-visible path, preserving only approved audit evidence, revoking temporary access, and confirming with the site owner that ordinary care proceeds without VitalNet. Rollback does not mean changing the production model or silently substituting a candidate policy.

### 8.5 Resume or terminate decision

Only the clinical owner and governance body may authorize resumption after root cause, containment, corrective action, and a documented re-verification. An unresolved patient-safety, ethics, privacy, or data-boundary issue terminates the study.

## 9. Aggregate-only reporting contract

The engineering export may contain protocol metadata, version identifiers, cohort counts, pre-registered aggregate metrics, confidence intervals, subgroup counts, reason-code counts, burden summaries, deviation counts, and non-claims. It must not contain patient-level rows, identifiers, raw or transformed free text, exact encounter timestamps, record arrays, individual predictions, individual probabilities, or hidden linkage keys.

The report must include an explicit statement that no patient-level data is present and must pass `assert_zero_patient_leakage()` before it leaves the approved execution boundary. If the output fails the leakage check, the report is destroyed or quarantined locally and the study is paused.

## 10. Reproducibility and deviation handling

The protocol, analysis code, model artifact, candidate-policy implementation, and metric definitions are versioned together for the study record. The frozen production model is copied only through the approved local artifact path; it is not modified. The analysis must be deterministic for synthetic fixtures and must record all non-deterministic site operations as deviations.

Any deviation from the pre-registered protocol records its category, reason, affected denominator, corrective action, and whether the clinical owner considers the result interpretable. Deviations are not hidden by deleting affected cases. An analysis may report a restricted denominator only when the restriction was pre-registered or explicitly approved in the final governance review.

## 11. Progression gates

| Stage | Decision owner | Evidence required |
|---|---|---|
| Protocol readiness | Clinical owner, ethics route, data custodian | All Section 3 prerequisites complete; synthetic harness passes isolation tests |
| Site activation | Site PI and workflow owner | Local dry run, hidden-output verification, rollback rehearsal, staff briefing, and approved data map |
| Shadow continuation | Clinical owner and incident team | No unresolved hard-stop violation; acceptable data quality and operational feasibility |
| Shadow close | Clinical owner and data custodian | Complete aggregate report, deviation/incident review, deletion evidence, and reproducibility package |
| Any visible pilot | Governance body and qualified clinician | Separate prospective protocol, ethics approval, clinical acceptance criteria, risk review, and explicit go/no-go decision |

A successful synthetic harness or a completed shadow comparison does not by itself authorize a visible pilot, production promotion, clinical validation claim, or regulatory submission.

## 12. Explicit non-claims

This protocol does not claim that VitalNet is clinically safe, clinically validated, effective, calibrated for rural India, equivalent to ASHA or PHC judgment, suitable for autonomous triage, or cleared by CDSCO, FDA, CE, or any other authority. The public-data results remain proxy findings, including the documented emergency under-triage signals. The production model remains frozen, and all candidate policies remain research-only until qualified clinical governance decides otherwise.

## References

[1]: https://github.com/Lonely-Demon/VitalNet/blob/dev/docs/VALIDATION_PROTOCOL.md "VitalNet validation protocol"

[2]: https://github.com/Lonely-Demon/VitalNet/blob/dev/docs/evaluation/HUMAN_ESCALATION_WORKFLOW_DESIGN.md "Human-escalation and insufficient-information workflow design"

[3]: https://github.com/Lonely-Demon/VitalNet/blob/dev/docs/CLINICAL_GOVERNANCE.md "VitalNet clinical governance record"

[4]: https://github.com/Lonely-Demon/VitalNet/blob/dev/docs/INCIDENT_RESPONSE.md "VitalNet incident-response runbook"

[5]: https://github.com/Lonely-Demon/VitalNet/blob/dev/docs/EVALUATION_DATA_BOUNDARY.md "VitalNet evaluation data boundary"

[6]: https://github.com/Lonely-Demon/VitalNet/blob/dev/docs/evaluation/CLINICAL_GOVERNANCE_PARTNERSHIP_PATHWAY.md "Clinical governance and partnership pathway"

[7]: https://github.com/Lonely-Demon/VitalNet/blob/dev/docs/evaluation/SAFETY_REMEDIATION_CANDIDATE_STUDY.md "Synthetic safety-remediation candidate study"
