# VitalNet Human-Escalation and Insufficient-Information Workflow Design

> **Status:** Research and governance design only. This document does not activate a production workflow, change the frozen model, or authorize deployment.

## 1. Purpose

The completed public-data evaluation identified severe emergency under-triage when symptoms and clinical context are absent. The synthetic remediation study therefore needs a workflow-level design that distinguishes **missing evidence** from **negative evidence** and routes uncertain encounters to human review instead of silently assigning a low-acuity tier.

This document defines the proposed operational contract for a future remediation implementation. It is intentionally written so that a qualified clinical reviewer can approve, reject, or revise each safety decision. Engineering approval alone is insufficient for clinical activation.

## 2. Intended operating principle

> **When the system lacks enough information to support an ordinary triage classification, it must say so explicitly and route the encounter to an accountable human reviewer. It must not convert an empty field into a reassuring negative.**

The system remains advisory. The ASHA worker remains responsible for accurate collection and the PHC clinician remains responsible for clinical judgment and the final care decision. A future implementation must preserve this accountability split rather than treating escalation as an automated clinical decision.

## 3. Input-contract states

The workflow must distinguish the following states for every required clinical context field. A blank value without a state is invalid for a safety-sensitive workflow.

| State | Meaning | Evidence status | Provisional workflow behavior |
|---|---|---|---|
| `positive_symptom` | One or more allow-listed danger signs were actively reported | Positive evidence present | Evaluate through the approved triage and deterministic safety layers; preserve the positive symptom provenance |
| `explicit_negative_screen` | The operator actively screened the defined danger-sign checklist and recorded that none were present | Negative evidence explicitly collected | Ordinary tiering may proceed only if the remaining required fields satisfy the approved completeness policy |
| `unknown_or_not_asked` | The checklist was skipped, bypassed, or not asked | Evidence missing | Do not treat as negative; return `INSUFFICIENT_INFORMATION_FOR_CDS` or the governance-approved equivalent and request human review |
| `declined_or_unavailable` | The patient could not or would not answer, or the operator could not collect the information | Evidence unavailable | Do not treat as negative; return an insufficient-information state and escalate according to the approved human pathway |

The state must be recorded separately from the symptom list. `symptoms: []` is not sufficient to establish an explicit negative screen.

## 4. Required and optional ASHA/PHC fields

The following is a **candidate engineering contract**, not a clinical acceptance decision.

| Field group | Candidate requirement | Missing-field behavior |
|---|---|---|
| Patient age and biological sex | Required for the current feature and rule contract, subject to clinical review | Insufficient-information state; no ordinary tier |
| Temperature, heart rate, systolic BP, diastolic BP, SpO₂ | Required where the approved policy says they are necessary; missingness must be represented explicitly | Severe or critical missingness path depending on the approved vital-specific policy |
| Symptom-screening state | Required; must be one of the four states above | Unknown/unavailable path; never implicit negative |
| Positive structured symptoms | Required when the positive state is selected | Reject inconsistent payloads or return data-quality escalation |
| Chief complaint/free text | Optional research context unless a future governance decision makes it required | Missing text must not erase structured symptom state or be treated as reassurance |
| Observations and current medications | Optional research context until clinical review establishes their role | Record as uncollected rather than empty/negative; do not silently infer safety |
| Pregnancy status, known conditions, and location | Conditional or optional fields requiring clinical ownership | Preserve unknown status; do not invent a default negative |
| Collection provenance and timestamp | Required for any future auditable workflow | No clinically visible result if provenance is absent |

## 5. Candidate policy precedence

The future implementation should use a deterministic precedence order so that a later permissive rule cannot erase an earlier safety condition.

1. **Validate payload and provenance.** Reject impossible values, contradictory state combinations, missing timestamps, and malformed field status.
2. **Detect immediate deterministic danger.** If an approved extreme-vital or critical-symptom rule fires, preserve the emergency safety signal and display the reason. This rule must not be weakened by absent symptoms.
3. **Assess demographic completeness.** If required demographic context is absent, return an insufficient-information state rather than guessing.
4. **Assess vital completeness.** Apply the clinically reviewed vital-specific missingness policy. Do not silently impute an unmeasured vital as normal.
5. **Assess symptom-screening state.** Positive or explicitly negative screening may proceed only if all preceding conditions allow ordinary tiering. Unknown or unavailable screening routes to insufficient information.
6. **Evaluate the approved ordinary triage path.** Only encounters that pass the approved completeness and context policy may receive ROUTINE, URGENT, or EMERGENCY through the approved runtime.
7. **Record disagreements and uncertainty.** Model/rule disagreement, low confidence, contradictory evidence, or unsupported input combinations must remain visible and must trigger the approved review state.

This hierarchy is a research design. A qualified clinical reviewer must confirm the vital-specific thresholds, the definition of immediate danger, and the action associated with each state before implementation.

## 6. Human-escalation pathway

A future user-facing workflow should make the escalation state operationally meaningful rather than presenting it as an unexplained error.

| Step | Accountable role | Required behavior | Audit record |
|---:|---|---|---|
| 1 | ASHA or intake operator | Confirm which required fields were collected, which were unavailable, and whether the symptom screen was actually performed | Field-level provenance, collection time, operator identity or pseudonymous role identifier |
| 2 | System | Display `INSUFFICIENT_INFORMATION_FOR_CDS` or the governance-approved label, the reason code, missing-field categories, and any preserved extreme-vital flag | Candidate policy version, rule IDs, model version if invoked, timestamp |
| 3 | PHC clinician or designated reviewer | Review the original collected information, verify urgent data, and make the clinical decision under local protocol | Reviewer identity, review time, final decision, override or confirmation, rationale category |
| 4 | Escalation coordinator, if required | Handle cases where the designated reviewer is unavailable or the patient requires immediate local escalation under site protocol | Handoff time, recipient role, outcome status, unresolved queue state |
| 5 | Quality and safety owner | Review unresolved, overridden, delayed, or adverse cases in aggregate | Weekly or periodic aggregate metrics, incident link, remediation action |

The software must not claim that a case is clinically safe merely because it was placed in an escalation queue. Escalation is a routing behavior whose safety depends on a real and timely human response.

## 7. Reviewer-unavailable behavior

Reviewer-unavailable behavior is a critical clinical-governance decision and cannot be finalized by engineering. The candidate design must nevertheless make the open decision explicit:

| Situation | Candidate research behavior pending clinical approval |
|---|---|
| No clinician is currently available | Do not emit a reassuring ordinary tier; retain an unresolved insufficient-information state and surface the local escalation instruction approved for the site |
| Extreme deterministic danger is present | Preserve the deterministic danger flag and approved emergency escalation instruction; do not allow missing context to downgrade it |
| Connectivity is unavailable | Store a signed, timestamped pending record locally with no fabricated tier; synchronize only through the approved offline process |
| Reviewer queue is delayed | Track queue age and surface the delay; do not silently expire the case into ROUTINE |
| Patient declines further information | Preserve `declined_or_unavailable`; do not reinterpret it as a negative screen |

The exact wording, urgency, recipient, and timeout behavior require qualified clinical and site governance. This document deliberately does not invent those values.

## 8. Contradictory and malformed inputs

The future workflow must fail closed for contradictions such as a positive symptom list paired with an explicit statement that no danger signs were present, a missing symptom-screening state, impossible vital values, or a timestamp that predates the encounter. The system should return a data-quality or insufficient-information outcome rather than selecting whichever field produces the more reassuring tier.

Every contradiction must produce an aggregateable reason code. Raw free text and patient-level diagnostic output must not be emitted into evaluation reports or logs.

## 9. Safety metrics for the workflow study

The synthetic and later authorized evaluation studies should report the following separately:

| Metric family | Required measures |
|---|---|
| Ordinary tier performance | Emergency sensitivity, emergency miss count, EMERGENCY→ROUTINE drops, under-triage, over-triage, Wilson intervals, and tier distribution among ordinary-tier cases |
| Non-triage routing | Insufficient-information rate, escalation reason counts, emergency cases escalated, reference-tier distribution among escalated cases, and unresolved-case rate |
| Operational burden | Escalation volume per 100 encounters, reviewer queue size, queue age, repeat measurement requests, and proportion requiring manual override |
| Input-contract integrity | Unknown versus explicit-negative separation, contradiction rate, missingness strata, and provenance completeness |
| Safety behavior | Extreme-vital preservation, no silent downgrade during escalation, no fabricated ordinary tier, and zero patient-level leakage |
| Reproducibility | Fixed-seed output identity, protocol version, policy version, model version, and source-code commit |

No engineering threshold in this table is a clinical acceptance threshold. Qualified clinical governance must define which outcomes are acceptable for the intended workflow.

## 10. Implementation boundary

This design does not authorize changes to `backend/app/`, `packages/clinical-core/src/`, APIs, frontend screens, database schemas, model artifacts, thresholds, deployment configuration, or the `test` branch. A future implementation PR must be separate, must identify the governance decision it implements, and must include synthetic tests before any real-data analysis.

The current production behavior remains unchanged until the clinical review gate, implementation review, synthetic evidence review, and any required prospective or shadow evaluation are complete.

## 11. Open governance decisions

A qualified clinical reviewer must resolve at least the following questions before implementation:

1. Which ASHA/PHC fields are truly required before an ordinary tier is permissible?
2. Which single-vital missingness patterns are acceptable for ordinary tiering, if any?
3. What exact action and urgency does each escalation reason require?
4. Who is the accountable reviewer at a PHC, and what happens when that person is unavailable?
5. What queue-age or response-time limit is clinically acceptable?
6. What emergency sensitivity, under-triage, escalation-burden, and subgroup criteria govern acceptance?
7. What prospective or shadow evidence is required before the workflow may influence care?

Until these questions have an accountable clinical owner, the candidate remains a research policy and must not be represented as a clinically accepted workflow.

## References

[1]: https://github.com/Lonely-Demon/VitalNet/blob/dev/docs/evaluation/PUBLIC_DATA_EVALUATION_CLOSURE.md "Public-data evaluation closure"
[2]: https://github.com/Lonely-Demon/VitalNet/blob/dev/docs/evaluation/SAFETY_REMEDIATION_DESIGN.md "Safety-remediation design"
[3]: https://github.com/Lonely-Demon/VitalNet/blob/dev/docs/evaluation/SAFETY_REMEDIATION_CANDIDATE_STUDY.md "Synthetic safety-remediation candidate study"
[4]: https://github.com/Lonely-Demon/VitalNet/blob/dev/docs/CLINICAL_REVIEW.md "Clinical review gate"
[5]: https://github.com/Lonely-Demon/VitalNet/blob/dev/docs/VALIDATION_PROTOCOL.md "Validation protocol"
