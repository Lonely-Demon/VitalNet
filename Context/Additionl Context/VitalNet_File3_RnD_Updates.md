# VitalNet R&D Document — Required Updates
## Post-Adversarial Audit Change Record
### India Innovates 2026 | HealthTech Domain

---

> **Purpose of this document**
> This document identifies every place in the original VitalNet R&D document that is inconsistent with conclusions reached through the adversarial audit process. It is structured by R&D document section. Each entry names the original claim, why it needs updating, and the replacement language or architectural decision that supersedes it.
>
> This document does not rewrite the R&D document — it tells you exactly what to change and why, so the R&D document accurately reflects the current architecture and remains a credible technical record if reviewed by a judge, investor, or technical collaborator.

---

## SECTION 1 — Problem Statement

---

### 1.1 / 1.2 — Opening Scene and Statistics

**Original:** The R&D document uses a 55-year-old male cardiac case (BP 160/100, SpO2 91%, chest tightness) as the primary sample patient throughout — it appears in Section 2.5 as the sample output and is implicitly the reference case used across architecture examples.

**Why this needs updating:** The PPT opening scene uses a neonatal sepsis case. If the R&D document is reviewed alongside the PPT, the cardiac case appearing in the demo output but not in the opening narrative is fine. However, if the document is read standalone, it should acknowledge that the sample output case (55M cardiac) is one of five pre-seeded demo cases and is not the only representative use case.

**Update required:** In Section 2.5, add a note after the sample output: *"This sample output represents one of five pre-seeded demo cases covering cardiac, respiratory, obstetric, neurological, and routine presentations. The cardiac case is used here for the clarity of the differential diagnosis output — it is not the sole or primary use case."*

---

### 1.2 — Statistics Table

**Original:** Life expectancy gap (poorest vs wealthiest) — 7.6 years (65.1 vs 72.7) — cited from BMJ Global Health.

**Why this needs updating:** This statistic was removed from the PPT as causally overreaching. VitalNet does not address the causes of a 7.6-year life expectancy gap (poverty, nutrition, sanitation, generational health). The R&D document includes it in a statistics table — that is appropriate context. However, the document should not use it as a direct impact claim for VitalNet.

**Update required:** The statistic can remain in Section 1.2's data table as context for the severity of rural health inequality. Add one line after the table: *"Note: The life expectancy gap reflects structural determinants beyond VitalNet's scope — poverty, nutrition, sanitation, infrastructure. VitalNet addresses only the documentation failure component of this inequality, which is the only component fixable with software."*

---

## SECTION 2 — Proposed Solution

---

### 2.3 — Step 1 (ASHA Input)

**Original:** *"React multilingual form — dropdowns, symptom checklist, vitals fields, voice input toggle. Raw form data submitted to FastAPI."*

**Why this needs updating:** The document does not address the time cost of the form relative to the paper slip. The PPT was attacked on this point (Gemini Landmine 2). The R&D document should acknowledge the time trade-off explicitly as a deliberate design decision.

**Update required:** Add after Step 1 description: *"Form completion time: estimated 90 seconds with dropdown-first UI and voice input. This represents a time increase over a paper slip (15–30 seconds) in exchange for structured data quality. The cognitive load trade-off is deliberate: 90 seconds of ASHA input eliminates 2–5 minutes of doctor history-gathering per consultation."*

---

### 2.3 — Step 3 (Triage Classifier)

**Original:** *"GradientBoostingClassifier (.pkl pretrained on synthetic dataset) — inference in <5ms. Triage level: EMERGENCY / URGENT / ROUTINE + confidence score."*

**Why this needs updating:** Two issues. First, the document does not mention calibration strategy — conservative vs neutral. Second, it does not address what "pretrained on synthetic dataset" means for real-world validity.

**Update required:** Replace with: *"GradientBoostingClassifier (.pkl pretrained on synthetic dataset) — inference in <5ms. Classifier is calibrated to minimize false negatives: an Emergency case classified as Routine is a more dangerous failure mode than a Routine case classified as Urgent. This conservative calibration is a deliberate safety decision, not a performance limitation. Triage level: EMERGENCY / URGENT / ROUTINE. Validation on held-out synthetic test set: [X]% accuracy, 0 false negatives on Emergency cases. Clinical validation against real PHC data is a Phase 3 prerequisite before production deployment."*

---

### 2.3 — Step 7 (Doctor Dashboard)

**Original:** *"React priority queue — triage badge, briefing card, missing data flags, reviewed/action buttons. Doctor sees structured briefing in under 30 seconds of form submission."*

**Why this needs updating:** The document assumes pull behavior — the doctor checks the dashboard. It does not address the notification mechanism that alerts the doctor a new case has arrived.

**Update required:** Expand Step 7 description: *"Doctor Dashboard — React priority queue with triage badge, briefing card, missing data flags, reviewed/action buttons. Notification architecture by triage tier: Emergency — FastAPI triggers SMS to doctor's registered mobile immediately upon classifier output (fires before LLM briefing completes); if ASHA worker is offline, browser triggers native Android `sms:` intent with pre-filled Emergency payload — cellular SMS operates independently of internet connectivity. Urgent — dashboard push notification with audio alert on next page load. Routine — priority queue, visible on scheduled dashboard review. SMS content is a workflow alert only ('priority patient en route, briefing to follow') — not a clinical recommendation, maintaining the clinical decision support boundary."*

---

### 2.4 — ASHA Worker + ChatGPT Comparison

**Original:** *"Routes to doctor — the person with clinical training to verify, override, and act."*

**Why this needs updating:** The document does not address the expert-novice gap directly as a named concept. The PPT uses it as USP 1. The R&D document should name the pattern it resolves for consistency.

**Update required:** Add one sentence after the LOCK statement: *"This resolves what can be called the expert-novice gap in clinical AI deployment: the person with access to the AI (ASHA worker) lacks the clinical expertise to use it effectively, while the person with clinical expertise (doctor) lacks access at the point of first contact. VitalNet's architecture routes AI output to the expert rather than attempting to train the novice."*

---

### 2.5 — Sample Output

**Original:** The sample output is functional and well-structured. No change to the output itself.

**Why this needs noting:** The sample output uses the 55M cardiac case. The note added to Section 1.2 covers this. Additionally, the document should confirm that the system prompt producing this output follows the three-layer methodology cited in the PPT.

**Update required:** Add after the JSON sample output: *"The system prompt producing this output follows a three-layer structured methodology: Layer 1 — role definition and explicit constraints (the LLM may not override the classifier's triage level, must flag uncertainty rather than estimate, must not add prose outside the JSON schema); Layer 2 — structured patient context as labeled JSON fields; Layer 3 — locked output schema with required fields including mandatory uncertainty_flags. This architecture mirrors structured clinical prompting methodology documented in Thirunavukarasu et al. Nature Medicine 2023 and JAMA Network Open 2024 RCT (92% diagnostic accuracy with structured prompting vs 74% without)."*

---

### 2.6 — Fallback Resilience Map

**Original:** *"Internet Connectivity — Full pipeline — all API calls live / Form data cached locally in browser storage — submitted on reconnection. Triage classifier runs offline."*

**Why this needs updating:** "Triage classifier runs offline" is technically imprecise. The classifier runs on the FastAPI server. It does not run in the browser. "Runs offline" implies the ASHA worker can execute triage classification without any server connectivity — she cannot.

**Update required:** Replace the Internet Connectivity row: *"Internet Connectivity — Full pipeline — all API calls live / Form data cached locally in browser storage — submitted on reconnection. Triage classifier is LLM-independent and API-independent: it fires from a local .pkl on the FastAPI server with zero external API dependency. Emergency notification uses native Android `sms:` intent if backend is unreachable — cellular SMS operates without internet."*

**Future option to note:** *"Phase 2 architecture consideration: converting GBM classifier to ONNX format for onnxruntime-web browser deployment would enable true on-device inference — independent of FastAPI server connectivity entirely. Model size at current feature set is under 5MB, feasible on 2GB RAM Android devices."*

---

## SECTION 4 — AI Layer Design

---

### 4.1 — General-Purpose LLM vs Medical-Specific Model

**Original:** *"Groq (free tier, fast), Gemini 2.5 Flash (free tier), multiple fallback options available immediately."*

**Why this needs updating:** The document lists these as strengths of general-purpose LLMs. It should also note that "GPT-4 level reasoning" is not a valid benchmark comparison claim — the correct claim is that general-domain LLMs outperform medical-specific models on reasoning tasks, supported by the Nature Medicine citation.

**Update required:** In the API Availability row, remove any implied benchmark comparison to GPT-4. Replace with: *"Groq Llama-3.3-70B: free tier, ~2s inference, strong JSON schema enforcement. Clinical reasoning quality validated by domain: Thirunavukarasu et al. Nature Medicine 2023 confirms 93.55% of evaluated clinical LLM instances use general-domain models — the task is reasoning over observed data, not medical knowledge recall."*

---

### 4.2 — Triage Classifier Design

**Original:** The section explains why ML classifier was selected over LLM classification and rule-based approaches. Comprehensive and well-reasoned.

**Why this needs updating:** The section does not address calibration strategy (conservative vs neutral) or what to say when asked about false negative rates on synthetic data.

**Update required:** Add after the LOCK statement: *"Calibration strategy: the classifier is calibrated to minimize false negatives rather than optimize overall accuracy. The two failure modes are asymmetric — a false negative (Emergency classified as Routine) sends a critically ill patient home; a false positive (Routine classified as Urgent) sends a stable patient to the PHC earlier than necessary. The design priority is explicit: minimize the dangerous failure mode. SHAP explainability ensures every classification is verifiable by the receiving doctor before clinical action — the classifier flags and explains; the doctor decides and acts. Clinical validation against real PHC data is a Phase 3 prerequisite. The synthetic training dataset limitation is acknowledged and the production pathway to real-data validation is documented in Section 7.2."*

---

### 4.3 — Prompt Engineering Strategy

**Original:** The temperature decision (0.1–0.2), output format (strict JSON), triage in prompt (locked context), uncertainty handling, and persona instruction are well-documented.

**Why this needs updating:** The section does not name the three-layer architecture explicitly as a methodology mirroring the JAMA structured prompting research. It also does not state where the system prompt can be found in the repository.

**Update required:** Add after the table: *"The prompt architecture above constitutes a three-layer structured prompting methodology: Layer 1 (system prompt — role, rules, constraints), Layer 2 (dynamic patient context), Layer 3 (locked output schema). This mirrors the methodology documented in JAMA Network Open 2024 RCT, which found 92% diagnostic accuracy with structured LLM prompting vs 74% without. The complete system prompt is maintained at `/backend/prompts/clinical_system_prompt.txt` in the repository and must not be simplified — each layer serves a distinct safety function."*

---

### 4.5 — Guardrails Architecture

**Original:** Five guardrails: input validation, LLM-independent triage, mandatory uncertainty flags, non-removable disclaimer, accountability separation.

**Why this needs updating:** The section does not address the regulatory posture. The guardrails exist partly to support the clinical decision support classification under CDSCO SaMD Draft Guidance. That connection should be explicit.

**Update required:** Add after the five-guardrail table: *"Regulatory posture: these five guardrails collectively support VitalNet's classification as clinical decision support rather than a diagnostic system under CDSCO Draft Guidance on Medical Device Software (October 2025). The non-removable disclaimer (Guardrail 4) and accountability separation (Guardrail 5) are the specific structural elements that maintain this boundary. The Emergency SMS notification (doctor dashboard layer) contains only workflow alerts — not clinical recommendations — specifically to preserve this classification boundary. Any future modification that routes AI-generated clinical recommendations directly to non-medical personnel, or that removes the mandatory doctor review step, would require CDSCO SaMD re-classification review."*

---

## SECTION 5 — Tech Stack Decisions

---

### 5.0 — Consolidated Stack Card

**Original:** Sarvam AI listed as *"saarika:v2 model, 100 min/month free tier."*

**Why this needs updating:** 100 min/month is a demo-scale tier. Listing it in a consolidated stack card without acknowledging the limitation implies it is a production-viable tier.

**Update required:** Change Sarvam AI entry: *"saarika:v2 model, 100 min/month free tier (demo scale). Production: paid tier or Whisper via Groq fallback (zero additional cost, already in stack, adequate for Hindi and Bengali primary use case). Free tier is sufficient for prototype demonstration and competition demo."*

---

### 5.1 — Backend Runtime

**Original:** FastAPI selected for *"Python-native ML integration; async-first for concurrent LLM calls; Pydantic v2 schema validation."*

**Why this needs updating:** The rationale is correct but the demo-speed framing should be removed. The industrial argument is stronger.

**Update required:** Revise the FastAPI verdict rationale: *"FastAPI selected: Python-native ML integration with zero bridge layer to the classifier and extraction models; async-first ASGI design handles high-latency variability of rural 4G API calls without blocking the main thread — critical when LLM calls carry variable 1–8 second latency under intermittent connectivity; Pydantic v2 schema validation is the clinical data contract."* Remove any reference to demo iteration speed or cold start as the primary rationale.

---

### 5.2 — Database

**Original:** Note on Supabase: *"migration is a configuration change."*

**Why this needs updating:** This overclaims. SQLite to Supabase involves PostgreSQL syntax differences, UUID handling, timezone normalization, SQLAlchemy dialect changes, and connection pooling. A senior engineer will catch this.

**Update required:** Replace migration claim: *"Production migration to Supabase is a documented process involving PostgreSQL dialect configuration, UUID primary key alignment, timezone handling, and connection pooling setup. Schema design is Supabase-compatible from day one — the migration is a planned operational step, not an architectural rebuild. Estimated migration effort at prototype scale: 4–8 hours."*

---

### 5.3 — LLM API Selection

**Original:** The fallback logic is documented. No major issues.

**Why this needs noting:** The document should confirm that the three-tier fallback includes handling for the demo venue scenario — multiple concurrent judges submitting simultaneously — and that the fallback triggers are time-based, not just error-code-based.

**Update required:** Add after the three-tier fallback logic: *"Fallback triggers are both error-code-based (429 rate limit) and timeout-based (8 seconds for Groq primary, 12 seconds for Gemini Flash). Time-based triggers ensure the fallback fires under latency degradation — relevant when multiple concurrent submissions occur during a live demonstration. The briefing panel displays an amber 'Cached — verify data' banner on final fallback — triage classification from the .pkl classifier is unaffected and always displayed."*

---

## SECTION 6 — Feasibility Analysis

---

### 6.1 — What Is Built vs Simulated

**Original:** The table is comprehensive and honest. Minimal change needed.

**Why this needs updating:** One entry needs precision. *"Internet Connectivity — Triage classifier runs offline"* — same issue as Section 2.6. Classifier runs on server, not device.

**Update required:** Change Internet Connectivity row in the fallback behavior column: *"Form data cached locally in browser. Triage classifier is LLM-independent and API-independent — fires on server from local .pkl on reconnection. Emergency alert uses Android native `sms:` intent if backend unreachable. Offline resilience operates at the data collection and emergency notification layers."*

---

### 6.2 — Latency Budget

**Original:** Comprehensive and well-structured. The end-to-end latency budget is realistic.

**Why this needs noting:** The Sarvam STT latency note should acknowledge the async flow more explicitly given the offline/online architecture discussion.

**Update required:** In the Voice transcription row, add: *"Transcription result is never on the critical path — form submission, triage classification, and LLM briefing all proceed independently. Voice transcription enriches the LLM prompt if available; the pipeline does not wait for it."*

---

### 6.3 — Incomplete Input Handling

**Original:** The table handles five scenarios well. One scenario needs revision.

**Why this needs updating:** The "Internet unavailable at submission" row says "Triage classifier runs offline from .pkl." Same precision issue.

**Update required:** Replace that row: *"Internet unavailable at submission — Form data cached locally in browser. On reconnection: FastAPI receives cached form, classifier fires from local .pkl (zero external API dependency), SHAP explanation generated, LLM briefing triggered. Emergency cases: Android `sms:` intent available immediately for manual ASHA-triggered alert while connectivity is restored."*

---

### 6.4 — Risk Matrix

**Original:** Comprehensive. Two risks need updating.

**Update required — Row 1 (Groq rate limit):** Change mitigation from *"Three-tier LLM fallback auto-triggers. Groq → Gemini Flash → Flash-Lite → cached. Verbal talking point prepared."* to *"Three-tier LLM fallback auto-triggers. Timeout-based (8s/12s) and error-code-based (429) triggers. Briefing panel displays amber 'Cached — verify data' banner on final fallback. Triage classification unaffected."*

**Update required — new row:** Add risk row: *"Risk: Doctor does not check dashboard before Emergency patient arrives. Severity: High. Likelihood: Medium. Mitigation: Emergency triage triggers immediate SMS to doctor's registered mobile via FastAPI (online) or Android native `sms:` intent (offline). SMS content is workflow alert only. Doctor is alerted before patient begins journey."*

---

## SECTION 7 — Impact Analysis

---

### 7.1 — Adoption Level Table

**Original:** The table shows adoption levels from 1% to 100% with records created per month. The 1% row shows "~75,000 structured records."

**Why this needs updating:** The math does not hold. 1% of 9.4 lakh = 9,400 ASHA workers. At one new patient encounter per day × 30 days = 282,000 records/month. The 75,000 figure implies 0.27 patients per ASHA per day — inconsistent with NHM workload data.

**Update required:** Correct the 1% row to show 282,000 records/month. Add a footnote to the table: *"Records per month calculated at: (ASHA workers at adoption level) × (average new patient encounters per month per NHM workload data — approximately 30). Figures reflect new case intake, not routine follow-up visits."*

Corrected table:

| Adoption Level | ASHA Workers | Population Covered | Records Per Month |
|---|---|---|---|
| 1% | 9,400 | ~9.4 million rural patients | ~282,000 structured records |
| 5% | 47,000 | ~47 million rural patients | ~1.4 million structured records |
| 10% | 94,000 | ~94 million rural patients | ~2.8 million structured records |
| Full (100%) | 9.4 lakh | ~940 million rural patients | ~28 million structured records |

---

### 7.2 — Production Requirements

**Original:** *"Clinical validation study — AI-assisted triage output must be validated against clinician ground-truth on a real patient dataset."* Well-stated.

**Why this needs a small addition:** The document should connect the conservative calibration decision to the validation study requirements — what specifically needs to be validated.

**Update required:** Add after the clinical validation study row: *"Validation priority: false negative rate on Emergency cases is the primary safety metric. The classifier's conservative calibration (minimizing false negatives) must be validated against clinician-labeled ground truth. Secondary metrics: false positive rate on Routine cases (over-triage burden on PHC), inter-rater reliability between classifier output and physician assessment."*

---

### 7.2 — DPDP and Regulatory

**Original:** *"Patient data handled under IT Act 2000 and DPDP Act 2023. Privacy layer (federated learning, zk-SNARKs) is Phase 2 infrastructure addressing this requirement."*

**Why this needs updating:** This framing implies Phase 2 is required before any real data can be collected — making the system undeployable as a pilot until federated learning is built. This was identified as the "regulatory cop-out" issue (Gemini B4).

**Update required:** Replace with: *"Patient data handled under DPDP Act 2023. Phase 1 pilot compliance architecture: explicit patient consent logged on-device before form submission; anonymized SQLite payload (no direct identifiers in LLM prompt); on-device data retention limits. This compliance architecture supports a community clinic pilot today. Phase 2 federated learning and zk-SNARK privacy layer scales these protections mathematically across multi-clinic deployment — it is the production scaling path, not a prerequisite for Phase 1 piloting."*

---

### 7.3 — Honest Boundary

**Original:** Well-stated. No substantive changes needed.

**Why this needs a small addition:** The SaMD regulatory boundary should be named explicitly in the honest boundary section.

**Update required:** Add one item to the "VitalNet does not solve and does not claim to solve" list: *"Diagnostic certainty — VitalNet is clinical decision support, not a diagnostic system. Under CDSCO Draft Guidance on Medical Device Software (October 2025), this classification requires that qualified medical review precedes any clinical action. The non-removable disclaimer and mandatory doctor review step are the architectural implementations of this boundary."*

---

## SECTION 8 — References

---

### Missing References to Add

The following references are used in the PPT but do not appear in the R&D document's reference section:

**8.2 Clinical and Research References — add:**
- He J et al., *NeurIPS 2023* — Gradient Boosting vs deep learning on tabular data (referenced in triage classifier algorithm selection rationale — should appear in Section 4.2 and references)

**8.1 Government and Policy Data — verify:**
- The 40% PHC doctor absenteeism figure appears in the statistics table. Confirm it is cited to Health Dynamics of India 2022-23, MoHFW — not to a secondary source.

**8.4 Competitive Landscape Sources — no changes needed.**

---

## SECOND ROUND UPDATES — POST PERPLEXITY AND CHATGPT REVIEW

---

### Section 1.4 — Root Cause Narrative (Slide 1 Scene Update)

**Original:** R&D document does not contain the PPT opening scene directly but references the 55M cardiac case as the primary demonstration case throughout.

**Why this needs updating:** The PPT opening scene was changed from a death outcome to an information gap outcome (ChatGPT F3 fix). The R&D document's language around case outcomes should reflect the same framing — the tragedy is absence of information, not body count. This matters if the R&D document is reviewed alongside the PPT.

**Update required:** In any section where a patient outcome is described to illustrate the documentation gap, frame it as information gap rather than mortality. Example: replace "the patient did not survive" framing with "the doctor started from zero — with no vitals, no symptom timeline, no prior history, and no way to know what had been missed."

---

### Section 2.3 Step 7 (Dashboard) — Notification Human Action Clarity

**Original:** The dashboard step does not address whether the Emergency SMS fires automatically or requires human action.

**Why this needs updating:** ChatGPT F6 identified that the `sms:` URI intent requires one human action — the ASHA worker taps send. The R&D document must be explicit that the offline Emergency notification is semi-automated (one tap by ASHA worker) not fully automated, to maintain technical accuracy.

**Update required:** In the expanded notification architecture added in the first round of updates, add the following to the offline Emergency SMS entry: *"The Android `sms:` intent requires one user action — the ASHA worker taps send. The form pre-fills the doctor's number and message body automatically; no typing is required. This is a deliberate design constraint: browser-based PWAs cannot send background SMS without user interaction on Android. One tap is the minimum friction achievable without a native app."*

---

### Section 1.3 / Section 3 — ASHA Incentive Structure

**Original:** R&D document discusses ASHA worker adoption in Section 1.5 (India-Specific Context) and references ImTeCHO's 88% retention rate. It does not address the PLI incentive structure that actually governs ASHA behavior.

**Why this needs updating:** Perplexity E3 identified that ASHA workers are paid on Performance-Linked Incentives for specific NHM-mandated deliverables. Filling a VitalNet form is not a PLI item. The R&D document's adoption analysis is incomplete without acknowledging this structural constraint. A reviewer with public health background will notice the omission.

**Update required:** Add to Section 1.5 (India-Specific Context) under a new subsection "Incentive Reality":

*"ASHA workers are compensated through Performance-Linked Incentives tied to specific NHM-mandated deliverables: ANC registrations, institutional deliveries, immunizations, and related maternal-child health outcomes. Completing a VitalNet form for a general sick-patient encounter is not currently a PLI item.*

*This creates an adoption ceiling that UI design and workflow substitution alone cannot overcome. ImTeCHO's 88% daily login retention — cited elsewhere in this document — was supported by MoHFW mandate integration and alignment with existing reporting workflows, not solely by good UX.*

*VitalNet's adoption pathway therefore has two phases: Phase 1 — voluntary adoption by ASHA workers who find the tool reduces referral uncertainty and improves feedback from PHC doctors. Phase 2 — policy integration, in which VitalNet form completion for sick-patient encounters is incorporated into NHM reporting workflows and linked to existing or new PLI structures. Phase 2 is a government partnership decision, not a software decision. It is the outcome that a government-backed innovation competition like India Innovates 2026 is positioned to facilitate."*

---

### Section 6.1 — Feature Status Table: Classifier Validation

**Original:** Triage classifier listed as BUILT with note "Trained on Google Colab T4 pre-hackathon. Inference <5ms. SHAP TreeExplainer loaded alongside."

**Why this needs updating:** The classifier validation annotation on the PPT (Slide 3) now includes real numbers from the Colab confusion matrix. The R&D document feature status table should reflect the same validation results for consistency.

**Update required:** After running the Colab confusion matrix, update the triage classifier row to include: *"Validation on held-out synthetic test set: [real accuracy]% overall accuracy, [real FN rate] false negative rate on Emergency cases. Conservative calibration confirmed — false negatives on Emergency class minimized by design."* Replace brackets with real numbers after the Colab run.

---

## UPDATED SUMMARY OF REQUIRED CHANGES BY PRIORITY

### Must Fix Before Any External Review

| Section | Change | Reason |
|---|---|---|
| 2.6 Fallback Resilience Map | Classifier offline claim — precision fix | Architecturally incorrect as written |
| 6.3 Incomplete Input Handling | Same offline claim | Same issue |
| 6.4 Risk Matrix | Add Emergency notification risk row | Hole in coverage |
| 7.1 Adoption Table | Fix 75,000 → 282,000 records/month | Arithmetic error — embarrassing if caught |
| 7.2 DPDP Framing | Phase 2 as scaling path, not prerequisite | Currently implies system is undeployable |
| 2.3 Step 7 Dashboard | Add human action note to offline SMS | Technical accuracy — SMS is not fully automatic |

### Should Fix Before Finale (March 28)

| Section | Change | Reason |
|---|---|---|
| 2.3 Step 3 (Classifier) | Add calibration strategy and real validation numbers | Closes clinical judge attack vector |
| 2.3 Step 7 (Dashboard) | Add full notification architecture | Closes doctor pull behavior hole |
| 4.2 Triage Classifier | Add calibration strategy and false negative framing | Closes clinical judge attack vector |
| 4.3 Prompt Engineering | Add three-layer methodology name and repo file path | Connects citations to implementation |
| 4.5 Guardrails | Add regulatory posture connection | Strengthens SaMD boundary argument |
| 5.0 Stack Card | Sarvam free tier limitation note | Prevents scale calculation attack |
| 5.2 Database | Soften Supabase migration claim | Prevents senior engineer challenge |
| 1.5 India-Specific Context | Add PLI incentive structure section | Incomplete adoption analysis without it |
| 6.1 Feature Status | Update classifier row with real validation numbers | Consistency with PPT Slide 3 annotation |

### Good to Have Before Final R&D Document Submission

| Section | Change | Reason |
|---|---|---|
| 1.2 Statistics | Life expectancy gap scope note | Prevents causal overreach accusation |
| 1.4 Root Cause | Frame outcomes as information gap, not mortality | Consistency with PPT Slide 1 scene |
| 2.5 Sample Output | Multi-case context note | Prevents single-case tunnel vision impression |
| 2.4 ASHA vs ChatGPT | Name expert-novice gap explicitly | Consistency with PPT terminology |
| 5.1 Backend | Remove demo speed framing | Industrial framing is stronger |
| 7.3 Honest Boundary | Add SaMD boundary item | Regulatory completeness |
| 8.2 References | Add NeurIPS 2023 He et al. | Missing citation for documented decision |

---

*Document version: Post second adversarial review round — all rounds incorporated*
*Prepared for India Innovates 2026 — VitalNet HealthTech Submission*
*PPT Submission Deadline: March 10, 2026, 11:59 PM IST*
*Finale: March 28, 2026 — Bharat Mandapam, New Delhi*
