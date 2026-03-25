# VitalNet PPT — Complete Audit Record
## Original Structure + All Holes, Concerns, and Fixes
### India Innovates 2026 | HealthTech Domain

---

> **Purpose of this document**
> This is the complete adversarial audit record of the VitalNet PPT blueprint. It documents the original slide structure, every hole and concern raised by Claude, Gemini, ChatGPT, and Perplexity, and the proposed fix for each. It exists so that no patch is lost, no concern is forgotten, and every design decision has a traceable rationale.

---

## ORIGINAL SLIDE STRUCTURE (Pre-Audit)

The original structure was produced by Claude based on the VitalNet R&D document and the India Innovates 2026 competition requirements. Seven slides in fixed order per competition template.

### Slide 1 — Problem Statement
- Opening scene: 55-year-old man with chest tightness, breathlessness, rural UP
- Three statistics: CHC specialist shortfall (79.5%), PHC absenteeism (40%), life expectancy gap (7.6 years)
- Root cause statement: "This is not a technology failure. It is a documentation failure. And documentation failures are fixable with software."
- Single photograph visual of ASHA worker in field

### Slide 2 — Solution
- Capability matrix: Data Layer / Intelligence Layer / Doctor Output Layer checkboxes per competitor
- Three-node workflow: ASHA Worker → AI Diagnostic Layer → PHC Doctor
- Five-layer vision diagram (all five layers visible, AI Diagnostic highlighted as "This Submission")
- Thesis: "Every existing tool owns exactly one dimension. VitalNet connects all three."

### Slide 3 — Architecture
- Seven-node pipeline: Form → FastAPI → GBM Classifier → SHAP → Groq LLM (fallback chain) → SQLite → Doctor Dashboard
- Annotation: "Triage classification runs locally on device — offline-capable, deterministic, zero API dependency"
- Annotation: "Three independent APIs. Two infrastructure providers. Demo never fails."
- Annotation: "FHIR-compatible schema. Supabase-ready on connection string change."
- Dark background on this slide only

### Slide 4 — Technology Used
- Four-column decision table: Component / Technology / Why This / Why Not (naming specific competing products)
- Claimed: "Llama-3.3-70B at GPT-4 level on reasoning tasks"
- FastAPI reasoning: "Django cold start kills demo iteration speed"
- Sarvam AI: "No alternative offers comparable Indic accuracy"

### Slide 5 — Features / USP
- Four USPs: Expert-Novice Gap, Triage Independence, Hardware Floor Reality, Structured Record as Foundation
- Adoption framing: "VitalNet form replaces the paper slip — it does not add a new step"
- ImTeCHO reference for adoption validation
- WhatsApp comparison: "If her phone can run WhatsApp, it can run VitalNet"

### Slide 6 — References / Links
- Three sections: Government Data, Clinical Research, Technical Documentation
- Citations floating without connection to specific design decisions
- GitHub repo link, demo video link, live URL

---

## COMPLETE HOLE AND CONCERN REGISTER

---

### SECTION A — HOLES RAISED BY CLAUDE (Self-Identified)

---

#### A1 — Connectivity Paradox
**Slide affected:** Slide 3
**Severity:** Lethal
**Description:** Slide 1 establishes offline-first capability as a core premise. Slide 3 shows a synchronous Groq API call as the core intelligence layer. A technical judge reads this as an architectural contradiction — the system claims offline capability but its primary intelligence depends on a cloud API.
**Status:** Patched — then further refined by Perplexity (see B1)

---

#### A2 — "Demo Never Fails" Hubris
**Slide affected:** Slide 3
**Severity:** High
**Description:** Writing "Demo never fails" on an architecture slide invites every judge in the room to mentally construct the scenario where it does. The word "never" is a hostage to fortune. It is a boast, not a technical claim.
**Fix:** Replace with: *"Briefing panel is never blank — three independent APIs across two infrastructure providers, final safety is cached output with amber verification banner."*

---

#### A3 — "Supabase-Ready on Connection String Change" Is Technically Imprecise
**Slide affected:** Slide 3
**Severity:** Medium
**Description:** SQLite to Supabase migration involves PostgreSQL syntax differences, UUID vs autoincrement ID handling, timezone normalization, SQLAlchemy dialect changes, and connection pooling configuration. A senior engineer will know this. The annotation was chosen for impact and is not precise.
**Fix:** Replace with: *"FHIR-compatible schema from day one. Production migration path to Supabase documented — configuration change, not architectural rebuild."*

---

#### A4 — 55-Year-Old Cardiac Case Appears Twice
**Slide affected:** Slides 1 and 3
**Severity:** Medium
**Description:** The emotional opening scene and the demo output both use a 55-year-old male cardiac presentation. A pattern-matching judge reviewing 80 PPTs will notice the setup-payoff structure. The emotional authenticity of Slide 1 retroactively collapses when the demo output uses the same patient.
**Fix:** Use different cases. Opening scene: neonatal sepsis. Demo output: cardiac case. Or invert. Never the same patient for both.

---

#### A5 — Doctor Dashboard Assumes Pull Behavior
**Slide affected:** Slide 3
**Severity:** High
**Description:** PHC doctors seeing 80 patients a day do not check dashboards between patients. A briefing that sits in a priority queue may not be seen until the patient has already arrived. The system generates output but has no push mechanism for the doctor.
**Fix:** Tiered notification architecture — Emergency: SMS; Urgent: dashboard push + audio; Routine: priority queue. (Later found to have its own holes — see B5 and B10)

---

#### A6 — Adoption Mechanism Assumed, Not Demonstrated
**Slide affected:** Slide 5
**Severity:** High
**Description:** The system depends on ASHA workers filling the form consistently and completely. No incentive mechanism is explained. ImTeCHO's 88% retention was backed by MoHFW mandates and financial incentives — not just substitution design.
**Fix:** Own the friction. Reframe as explicit trade-off: 90 seconds of ASHA input for 5 minutes of saved doctor consultation time. (See Gemini Landmine 2 for further refinement)

---

#### A7 — Classifier Trained on Synthetic Data, False Negative Rate Unknown
**Slide affected:** Slide 3, Slide 5
**Severity:** Lethal
**Description:** The triage classifier is trained on synthetic data. At prototype scale, the false negative rate — classifying an Emergency as Routine — is unknown. A clinical judge will ask directly. Claiming accuracy without real patient validation is a credibility risk.
**Fix:** Reframe the classifier's role. It is not claimed to be medically accurate — it is calibrated to be conservative. False negatives minimized by design. SHAP explainability ensures doctor verifies before acting. Clinical validation on real PHC data is a Phase 3 prerequisite stated explicitly.

---

#### A8 — DPDP Act 2023 Exposure Unaddressed
**Slide affected:** Slide 2 (or absent)
**Severity:** High
**Description:** The system collects patient age, sex, vitals, symptoms, location, and ASHA identity and stores it in SQLite. Under DPDP Act 2023, this creates data fiduciary obligations. Penalties up to ₹250 crore per contravention. A government official on the panel will ask.
**Fix:** Regulatory Posture box on Slide 2. (Later refined — see Gemini Landmine 4)

---

#### A9 — CDSCO SaMD Awareness Absent
**Slide affected:** Slide 2 (or absent)
**Severity:** High
**Description:** CDSCO released Draft Guidance on Medical Device Software in October 2025. VitalNet's AI Diagnostic Layer almost certainly qualifies as Software as a Medical Device. Any judge with healthcare industry background will ask about the regulatory pathway. Silence reads as naivety or recklessness.
**Fix:** Explicit SaMD awareness in Regulatory Posture box. Frame as deliberate architectural positioning, not deferral. (Later refined — see Perplexity B5)

---

#### A10 — JAMA Citation Decoupled from System Prompt
**Slide affected:** Slide 4, Slide 6
**Severity:** Medium-High
**Description:** Citing the JAMA Network Open 2024 RCT on structured prompting while the actual system prompt may be three lines creates an academic dishonesty risk. A judge who checks the repository and finds a basic prompt will question the precision of every other citation.
**Fix:** System prompt must reflect three-layer structured methodology. Annotation on Slide 4 must name the specific file path in the repository. Slide 6 citation must be annotated with the design decision it informs.

---

#### A11 — Notification Architecture Covers Emergency Only
**Slide affected:** Slide 3
**Severity:** Medium
**Description:** The SMS fix for Emergency cases was introduced but Urgent and Routine cases remained on pull behavior. Two-thirds of case volume had no notification mechanism.
**Fix:** Full three-tier notification table covering all triage levels with explicit doctor behavior requirement per tier.

---

#### A12 — Capability Matrix Is Definitionally Fragile
**Slide affected:** Slide 2
**Severity:** High
**Description:** The three-column capability matrix (Data Layer / Intelligence Layer / Doctor Output Layer) is Claude's analytical framework, not a neutral one. If a judge disputes the definition of "data layer," the entire competitive analysis collapses.
**Fix:** Replace capability matrix with failure pattern table. Failure patterns are observable behaviors — ephemeral output, wrong recipient, hardware lock-in. Cannot be refuted by definitional argument.

---

#### A13 — Five-Layer Diagram Visual Dominance
**Slide affected:** Slide 2
**Severity:** Medium
**Description:** If the five-layer vision diagram dominates Slide 2, judges' eyes go to zk-SNARKs and ESP32. First impression: scope creep. The AI Diagnostic Layer must be the dominant visual element.
**Fix:** Five layers as small grey list at bottom of slide. AI Diagnostic Layer highlighted. Other four labeled "Roadmap."

---

#### A14 — Dark Background on Slide 3 Only
**Slide affected:** Slide 3
**Severity:** Low-Medium
**Description:** Inconsistent backgrounds across slides signal reactive design choices rather than intentional ones. A single dark slide in a light-background deck reads as a template change, not a design decision.
**Fix:** Maintain consistent background treatment across all seven slides.

---

#### A15 — FastAPI Reasoning Is Hackathon-Brain
**Slide affected:** Slide 4
**Severity:** Medium
**Description:** "Django cold start kills demo iteration speed" is a development convenience argument, not an industrial architecture argument. Judges don't care about iteration speed.
**Fix:** Frame as: *"Async-first design handles high-latency variability in rural 4G networks without blocking the main thread — critical when LLM API calls carry variable 1–8 second latency."*

---

#### A16 — Four USPs Exceeds Retention Limit
**Slide affected:** Slide 5
**Severity:** Low-Medium
**Description:** Human cognitive retention under fatigue caps at three items. A fourth USP means one will not be remembered.
**Fix:** Cut "Structured Record as Foundation" — it answers "why does this matter for Phase 2" not "why does this matter right now." Keep three: Expert-Novice Gap, Triage Independence, Hardware Floor Reality.

---

---

### SECTION B — HOLES RAISED BY GEMINI

---

#### B1 — Offline Emergency Paradox (Landmine 1)
**Slide affected:** Slide 3
**Severity:** Lethal
**Description:** The notification table states Emergency SMS fires "immediately." But if the ASHA worker is offline — the core premise of the hardware floor argument — she cannot reach FastAPI on Railway. The browser cannot silently send a server-triggered SMS without internet. A dying baby triggers an Emergency triage classification locally. The doctor receives nothing. The golden hour burns.
**Fix:** Split notification table into online and offline states.
- Online: FastAPI triggers server-side SMS immediately
- Offline: Browser triggers native Android `sms:` URI intent with pre-filled doctor number and Emergency payload. No server required. No app required. Cellular SMS works independently of internet.

*Exact annotation:* `sms:+91XXXXXXXXXX?body=EMERGENCY+triage+flag+patient+en+route+VitalNet`

---

#### B2 — The Substitution Lie (Landmine 2)
**Slide affected:** Slide 5
**Severity:** High
**Description:** Writing "baby sick" on a paper slip takes 15 seconds. A structured form with vitals, symptoms, observations, and regional language takes 2-3 minutes. That is a 10x increase in documentation time per patient. An ASHA worker seeing 40 patients a day feels this acutely. Claiming the form "replaces" the slip implies equivalent time cost. It does not.
**Fix:** Own the friction explicitly. Replace substitution framing with:
*"VitalNet trades 90 seconds of ASHA worker input time for 5 minutes of saved doctor consultation time. Dropdown-first UI and Sarvam AI voice input keep intake under 2 minutes. The cognitive load shifts from the PHC bottleneck — 80 patients a day, 5 minutes each — to the distributed edge where time pressure is lower. This is not zero friction. It is friction in the right place."*

---

#### B3 — ₹0 Is a Mixed Metaphor (Landmine 3)
**Slide affected:** Slide 1
**Severity:** Medium
**Description:** Using currency to measure information is a mixed metaphor. It reads as marketing to an engineer or data scientist. It breaks the clinical, analytical tone established by the rest of the presentation.
**Fix:** Replace *"₹0 structured clinical data surviving the ASHA-patient encounter"* with *"0 structured records created per ASHA-patient encounter under current workflow."* Same emotional force. Correct unit of measurement.

---

#### B4 — Regulatory Cop-Out (Landmine 4)
**Slide affected:** Slide 2
**Severity:** High
**Description:** The original DPDP framing — "real patient data collection does not begin until the federated privacy layer is deployed" — makes Phase 2 a prerequisite for any pilot. A judge hears: this system is too legally dangerous to use until you build zk-SNARKs. That is an undeployable toy.
**Fix:** Reframe Phase 2 as a scaling path, not a prerequisite.
*"Phase 1 pilot compliance: explicit patient consent logged on-device before form submission, anonymized SQLite payload transmission, no PII in LLM prompt. Pilot-ready today under current data fiduciary guidelines. Phase 2 federated privacy layer scales these guarantees mathematically across multi-clinic deployment."*

---

---

### SECTION C — HOLES RAISED BY PERPLEXITY

---

#### C1 — Classifier Offline Claim Is Architecturally Incorrect
**Slide affected:** Slide 3
**Severity:** Lethal
**Description:** The `.pkl` classifier runs inside FastAPI on Railway. If the ASHA worker loses internet, she cannot reach Railway. She cannot reach FastAPI. The classifier does not run on her device — it runs on the server. "Runs locally on device" is a hardware claim that cannot be made for a cloud-deployed backend. "LLM-independent" and "offline-capable" are not the same property.
**Two options:**
- Option A (tonight): Correct annotation to *"LLM-independent and API-independent — classifier fires from local .pkl on FastAPI server. Form data queues in browser cache. Triage fires within seconds of reconnection. Zero external API dependency."*
- Option B (before March 28): Convert GBM to ONNX, run via onnxruntime-web in browser. True on-device inference. Closes the hole permanently. GBM on vital signs data is under 5MB — feasible on 2GB RAM Android.

---

#### C2 — Closing Math Is Wrong by Factor of 4
**Slide affected:** Closing verbal statement
**Severity:** Medium-High
**Description:** "75,000 structured records per month at 1% adoption" implies 0.27 patients per ASHA per day. 1% of 9.4 lakh = 9,400 ASHAs. At one new patient per day: 9,400 × 30 = 282,000 records per month. A judge who does this arithmetic in the room will leave skeptical of every number in the deck.
**Fix:** Replace 75,000 with 280,000. Or use weekly figure: *"9,400 ASHA workers × 5 new patients per week = over 47,000 structured records every week — from zero."*

---

#### C3 — Neonatal Scene Contradicts Workflow Claim
**Slide affected:** Slide 1
**Severity:** Medium-High
**Description:** The scene shows: ASHA sees baby → writes paper slip → family walks 20km → doctor starts from zero. VitalNet's value proposition requires the ASHA to fill the form while the patient is still present. The scene does not show the intervention moment. A public health judge will ask: "When does the form get filled if the family left immediately?"
**Fix:** Rewrite scene to show before and after within the same narrative. Show the intervention moment explicitly:
*"Today, she opens a browser link and fills a structured form — 90 seconds. Emergency SMS reaches the PHC doctor before the family begins the walk. Without VitalNet: she writes 'baby sick.' The family walks 20km. The doctor starts from zero."*

---

#### C4 — Sarvam Free Tier Collapses at Scale
**Slide affected:** Slide 4
**Severity:** Medium
**Description:** 100 minutes/month is a demo tier. 10 ASHA workers × 5 patients/day × 2-minute voice inputs = 100 minutes/day. Free tier exhausted in 24 hours. Any product-focused judge will calculate this.
**Fix:** Acknowledge limit in technology table. Add: *"Free tier sufficient for prototype demonstration. Production voice budget is an operational cost line — Whisper via Groq provides zero-cost fallback with adequate Indic language support."*

---

#### C5 — Notification SMS Creates SaMD Classification Tension
**Slide affected:** Slide 3
**Severity:** High
**Description:** An SMS saying "EMERGENCY" sent to a doctor about a patient not yet examined is a direct clinical action trigger. This pushes VitalNet toward Class B or Class C SaMD under CDSCO Draft Guidance — exactly the classification boundary the Regulatory Posture box claims to sit below.
**Fix:** Change SMS content from clinical recommendation to workflow alert.
- SMS content: *"VitalNet Alert: Priority patient en route to [PHC name]. Full briefing to follow on dashboard. — VitalNet System"*
- Add to Regulatory Posture box: *"Emergency SMS triggers logistical preparation — not clinical action. Clinical recommendation is delivered only through the full structured briefing requiring qualified medical review. This maintains the decision support boundary under CDSCO SaMD Draft Guidance."*

---

---

### SECTION D — HOLES RAISED BY CHATGPT

---

#### D1 — Neonatal Story "Sepsis Requires Labs" Attack Vector
**Slide affected:** Slide 1
**Severity:** Medium
**Description:** A clinician judge could say "sepsis detection requires vitals, labs, and clinical exam — a form wouldn't have saved that baby." This reframes the emotional scene as a medical argument the presenter cannot defend on Slide 1.
**Status:** Resolved by Perplexity C3 scene rewrite. VitalNet does not claim to diagnose sepsis. It flags a high-risk neonate for Emergency triage. The rewritten scene makes this explicit. No additional fix required.

---

#### D2 — ₹0 Statistic Too Absolute
**Slide affected:** Slide 1
**Severity:** Medium
**Description:** ASHAs maintain register books in some districts. Government apps digitize some data. The "₹0" framing is too absolute and too easy to dispute.
**Status:** Resolved by Gemini B3 fix. "0 structured records" is more precise and harder to refute.

---

#### D3 — Competitor Comparison Risky
**Slide affected:** Slide 2
**Severity:** Low (given failure pattern approach)
**Description:** Naming Microsoft, Elsevier, NITI Aayog, and Ai Health Highway invites challenges on accuracy of characterization.
**Status:** Not a live concern given failure pattern table approach. Failure patterns are observable behaviors, not capability assessments. No fix required beyond the table redesign already in place.

---

#### D4 — SMS Operational Questions
**Slide affected:** Slide 3
**Severity:** Medium
**Description:** Who registers doctor phone numbers? What if doctor changes? Multiple doctors at one PHC? Who pays for SMS? What if doctor ignores it?
**Fix:** One footnote sentence: *"Doctor mobile numbers registered at PHC level by block health officer — same administrative process as existing NHM reporting system. SMS cost: ₹0.15 per message via Twilio India, under ₹500/month at 1% adoption scale."*

---

#### D5 — "GPT-4 Level Reasoning" Is Marketing Language
**Slide affected:** Slide 4
**Severity:** Medium
**Description:** An ML-background judge will immediately think this is unsupported. Benchmark comparisons to competitor products invite fact-checking.
**Fix:** Replace with: *"Llama-3.3-70B outperforms purpose-built medical LLMs on cross-domain clinical reasoning tasks — Thirunavukarasu et al. Nature Medicine 2023 found 93.55% of evaluated clinical LLM instances use general-domain models."*

---

#### D6 — Sarvam "No Alternative" Too Absolute
**Slide affected:** Slide 4
**Severity:** Low-Medium
**Description:** Whisper, Google Speech, and OpenAI Whisper will immediately be raised as counterexamples.
**Fix:** Replace with: *"Purpose-built for Dravidian and Indo-Aryan medical terminology — highest published accuracy on regional Indian languages for clinical vocabulary. Whisper via Groq serves as the in-stack fallback."*

---

#### D7 — ASHA Competence Framing Risk
**Slide affected:** Slide 5
**Severity:** Low (noise)
**Description:** The USP framing that ASHA workers never see AI output could be read as undervaluing ASHA competence.
**Status:** Noise. Role separation (data collector vs clinical evaluator) is organizational design, not a statement about competence. No fix required.

---

#### D8 — WhatsApp Comparison Logical Trap
**Slide affected:** Slide 5
**Severity:** Low-Medium
**Description:** "If phone can run WhatsApp, it can run VitalNet" invites: "Does it work on Android 6 with 1GB RAM?"
**Fix:** Add qualifier: *"If her phone can run WhatsApp on Android 8 or above — which covers 94% of government-issued devices currently in distribution — it can run VitalNet."*

---

#### D9 — Missing Builder Credibility
**Slide affected:** Slide 6 (or absent)
**Severity:** Medium
**Description:** No signal of execution trust. Judges shortlist teams based on confidence the team can actually build what they claim.
**Fix:** One line under GitHub link on Slide 6: *"Solo developer. Prior: 1st place, 24-hour hackathon, SSN College of Engineering 2025 — on-site problem statement, no prior preparation."*

---

#### D10 — Missing Prototype Validation Metrics
**Slide affected:** Slide 3
**Severity:** Medium
**Description:** Even synthetic validation numbers increase credibility. An untested classifier is a weaker claim than a tested one.
**Fix:** Add annotation near classifier node: *"Classifier validation on synthetic dataset: [X]% accuracy, 0 false negatives on Emergency cases in held-out test set — conservative calibration confirmed."*
Run confusion matrix on Colab before PPT finalization. Takes 10 minutes.

---

#### D11 — Deck May Be Too Sophisticated for 15-Second Scan
**Slide affected:** All
**Severity:** Low
**Description:** Winning competition decks are often simpler. Sophistication can make the key idea harder to find under time pressure.
**Status:** Low concern. The sophistication is in reasoning, not visual complexity. Each slide is designed for one idea readable in three seconds. Senior designer must enforce: if font size must reduce to fit content, cut the content. No structural fix required.

---

---

## MASTER FIX SUMMARY

| ID | Source | Severity | Fix Status |
|---|---|---|---|
| A1 | Claude | Lethal | Superseded by C1 |
| A2 | Claude | High | Fixed — "never blank" language |
| A3 | Claude | Medium | Fixed — "not architectural rebuild" |
| A4 | Claude | Medium | Fixed — different cases for scene and demo |
| A5 | Claude | High | Fixed — tiered notification table |
| A6 | Claude | High | Fixed — own the friction framing |
| A7 | Claude | Lethal | Fixed — conservative calibration reframe |
| A8 | Claude | High | Fixed — Regulatory Posture box |
| A9 | Claude | High | Fixed — SaMD awareness in Regulatory Posture |
| A10 | Claude | Medium-High | Fixed — system prompt file path annotation |
| A11 | Claude | Medium | Fixed — full three-tier table |
| A12 | Claude | High | Fixed — failure pattern table |
| A13 | Claude | Medium | Fixed — five layers small and grey |
| A14 | Claude | Low-Medium | Fixed — consistent backgrounds |
| A15 | Claude | Medium | Fixed — async-first industrial framing |
| A16 | Claude | Low-Medium | Fixed — three USPs only |
| B1 | Gemini | Lethal | Fixed — `sms:` URI offline fallback |
| B2 | Gemini | High | Fixed — own the friction |
| B3 | Gemini | Medium | Fixed — "0 structured records" |
| B4 | Gemini | High | Fixed — Phase 2 as scaling path |
| C1 | Perplexity | Lethal | Fixed — Option A annotation tonight, Option B ONNX before finale |
| C2 | Perplexity | Medium-High | Fixed — 280,000 or weekly figure |
| C3 | Perplexity | Medium-High | Fixed — scene rewrite with intervention moment |
| C4 | Perplexity | Medium | Fixed — acknowledge limit, Whisper fallback |
| C5 | Perplexity | High | Fixed — workflow alert not clinical recommendation |
| D1 | ChatGPT | Medium | Resolved by C3 |
| D2 | ChatGPT | Medium | Resolved by B3 |
| D3 | ChatGPT | Low | Not live concern — failure pattern table |
| D4 | ChatGPT | Medium | Fixed — SMS operational footnote |
| D5 | ChatGPT | Medium | Fixed — Nature Medicine citation |
| D6 | ChatGPT | Low-Medium | Fixed — soften Sarvam claim |
| D7 | ChatGPT | Low | Noise — no fix required |
| D8 | ChatGPT | Low-Medium | Fixed — Android 8+ qualifier |
| D9 | ChatGPT | Medium | Fixed — one line under GitHub link |
| D10 | ChatGPT | Medium | Fixed — run confusion matrix, add annotation |
| D11 | ChatGPT | Low | Not structural — enforce via design discipline |

---

---

### SECTION E — SECOND ROUND: PERPLEXITY (Round 2)

---

#### E1 — C1 Option B Still Pending (ONNX Browser Inference)
**Slide affected:** Slide 3
**Severity:** Medium — build task, not a tonight fix
**Description:** Option B (converting GBM classifier to ONNX for onnxruntime-web browser deployment) is a before-finale build task. Option A's annotation is correct for tonight's submission. However at the live demo on March 28, a technical judge can ask: "Does the classifier actually run on the device or on your server?" Option A requires a clear verbal clarification. Option B removes the question entirely.
**Fix:** Not a slide change. Build task before March 28. If ONNX conversion is completed, update Slide 3 classifier annotation from Option A to: *"ONNX classifier runs in-browser — true on-device inference, zero server dependency, fires offline."* If not completed, verbal answer is: *"Classifier runs server-side on FastAPI with zero external API dependency — LLM-independent, not device-independent. ONNX browser conversion is on the build list."*
**Status:** Pending — build task

---

#### E2 — D10 Placeholder Numbers Still Brackets
**Slide affected:** Slide 3
**Severity:** High — tonight fix, non-negotiable
**Description:** The classifier validation annotation still reads "[X]% accuracy, 0 false negatives on Emergency cases." A bracket on a slide claiming methodological rigor is a visible credibility inconsistency. Synthetic numbers are categorically stronger than placeholders.
**Fix:** Run confusion matrix on Colab before PPT submission tonight. Takes 10 minutes. Replace [X] with real numbers. The three numbers that matter: classifier accuracy on held-out synthetic test set, false negative rate on Emergency cases (must be 0 or near-zero), end-to-end pipeline latency on primary path. Latency is a stopwatch measurement, not a Colab run.
**Status:** Must fix tonight — hard deadline

---

#### E3 — PLI Incentive Architecture Unaddressed (The Thing All Four AIs Missed)
**Slide affected:** Slide 5
**Severity:** High — new hole, not previously identified
**Description:** ASHA workers are paid on Performance-Linked Incentives for specific NHM-mandated deliverables — ANC registrations, immunizations, institutional deliveries. Filling a VitalNet form for a sick patient is not a PLI item. There is no financial incentive to use the system. The B2 fix addressed time friction honestly but not the deeper behavioral economics problem. ImTeCHO's 88% retention cited in the deck was backed by MoHFW mandates and integration with existing reporting workflows — not just substitution design and good UX. A public health expert or NHM program officer on the panel will raise this.
**Fix:** Add one sentence to adoption framing on Slide 5: *"Long-term adoption requires alignment with ASHA PLI incentive structures — integration with NHM reporting workflow converts VitalNet from a voluntary tool into a mandated deliverable. This is the policy integration outcome this competition is positioned to facilitate."* This sentence shows PLI awareness, frames the ceiling honestly, and repositions the ask — you are not pitching to users, you are pitching to the people who set the mandates.
**Status:** Fixed — Slide 5 adoption paragraph updated

---

---

### SECTION F — SECOND ROUND: CHATGPT (Round 2)

---

#### F1 — Reasoning Invisible to Judge (Cognitive Compression Problem)
**Slide affected:** All
**Severity:** Low — design execution note, not structural
**Description:** 90% of the reasoning that makes the design robust lives in blueprint documents and audit records. Judges only see the slides. Conservative classifier calibration, SaMD boundary positioning, offline notification fallback — these disappear unless each has a visible one-sentence manifestation on the slide.
**Fix:** Not a structural change. Design execution instruction for senior: every reasoning decision in the blueprint must have a visible one-sentence manifestation on its slide. If the reasoning does not appear on the slide, it does not exist for the judge.
**Status:** Design execution note — not a slide change

---

#### F2 — Option A "Offline-Capable" Psychological Danger
**Slide affected:** Slide 3
**Severity:** Low-Medium — resolved by correct language implementation
**Description:** Even a technically correct claim can read as overstatement if a judge's mental model of "offline" doesn't match the architecture. A judge who later realizes "offline-capable" meant server-side with no external API calls — not device-side — may interpret this as perceived exaggeration. Competitions punish perceived exaggeration, not just factual errors.
**Fix:** Already resolved if blueprint language is implemented correctly. Annotation says "LLM-independent and API-independent" not "offline-capable." If senior implements the exact language from the blueprint, the psychological danger is neutralized. This is a design execution note.
**Status:** Resolved by correct language implementation

---

#### F3 — Neonatal Scene Triggers Policy Defensiveness
**Slide affected:** Slide 1
**Severity:** Medium — tonight fix
**Description:** A government official who funds maternal-child health programs may read a neonatal death scene and feel implicitly blamed for that death. Defensive evaluators tend to reject rather than support. The tragedy of a death outcome is unnecessary when the tragedy of an information gap achieves the same emotional weight without triggering blame attribution.
**Fix:** Change the neonatal scene ending from death outcome to information gap outcome. Replace the current ending with: *"The doctor has no vitals, no symptom timeline, no prior history. He makes the best decision he can with what he has. He never knows if it was enough."* Same emotional weight. No death. No blame. The tragedy is absence of information, not body count. A health ministry official reads this and thinks "we need to fix this" rather than "are they blaming us?"
**Status:** Fixed — Slide 1 scene ending updated

---

#### F4 — Naming Government-Partnered Organizations Creates Friction
**Slide affected:** Slide 2
**Severity:** Low — noise for this context
**Description:** Naming Microsoft, Elsevier, and NITI Aayog in a government-backed national competition could create friction even with accurate failure pattern characterizations. In startup pitches this is standard. In a government competition, criticizing programs that government officials may be proud of is a political risk.
**Assessment:** Noise. The failure pattern table describes observable behaviors, not policy failures. "ASHABot conversations are ephemeral — zero structured records persist" is not a criticism of Microsoft or NITI Aayog — it is a description of architectural scope. The characterization is accurate and verifiable. No fix required.
**Status:** Noise — no fix required

---

#### F5 — Adoption Explanation Incomplete — PLI Gap
**Slide affected:** Slide 5
**Severity:** High — same as E3
**Description:** Same as Perplexity E3. The adoption framing owns time friction but doesn't address the incentive structure that actually governs ASHA worker behavior.
**Status:** Resolved by E3 fix

---

#### F6 — SMS Fallback Requires Human Action, Not Automatic
**Slide affected:** Slide 3
**Severity:** Medium — tonight fix
**Description:** The `sms:` URI intent opens the Android SMS app with a pre-filled message. The ASHA worker must tap send. It is not automatic. If the slide or verbal description implies it fires automatically, a technical judge will catch it. The system becomes dependent on human action — acceptable, but must be framed honestly.
**Fix:** Change offline Emergency notification annotation from *"Browser triggers native Android `sms:` intent"* to *"Browser opens Android SMS app with pre-filled doctor number and Emergency payload — ASHA worker taps send. One tap, zero typing required."* "One tap, zero typing" is honest about requiring human action and frames the friction accurately.
**Status:** Fixed — Slide 3 notification table updated

---

#### F7 — SaMD Boundary Still Delicate
**Slide affected:** Slide 2
**Severity:** Low — competition context, verbal answer sufficient
**Description:** Triage classification and Emergency labeling could push toward Class B SaMD under CDSCO Draft Guidance even with the workflow-alert SMS framing. Regulatory posture is correctly positioned but a regulatory expert might still push.
**Assessment:** Low concern for competition context. Verbal answer if pushed: *"We know this sits in a grey zone and have scoped the prototype to stay below the clinical deployment line. CDSCO formal classification is a Phase 3 milestone alongside clinical validation."* No slide change required.
**Status:** Verbal answer sufficient — no fix required

---

#### F8 — Need Three Concrete Numbers from Prototype
**Slide affected:** Slide 3
**Severity:** High — same as E2
**Description:** Same as Perplexity E2. Judges need numbers produced by the prototype, even on synthetic data.
**Status:** Resolved by E2 fix — three numbers: classifier accuracy, Emergency false negative rate, end-to-end latency

---

#### F9 — Builder Signal: Show Prototype Exists
**Slide affected:** Slide 6
**Severity:** Medium
**Description:** The hackathon win line was added. But the prototype's existence should be visible in the repository before tonight's submission. A repo with three commits signals abandonment. A repo with active commits, a README, and the system prompt file at the named path signals a team actively building.
**Fix:** Before submitting tonight: ensure repo has meaningful commits, README describes what the prototype does, system prompt file exists at `/backend/prompts/clinical_system_prompt.txt`. The repo does not need to be complete — it needs to look like someone is building something, not a placeholder.
**Status:** Build/repo task — not a slide change

---

---

## UPDATED MASTER FIX SUMMARY

| ID | Source | Severity | Fix Status |
|---|---|---|---|
| A1 | Claude | Lethal | Superseded by C1 |
| A2 | Claude | High | Fixed — "never blank" language |
| A3 | Claude | Medium | Fixed — "not architectural rebuild" |
| A4 | Claude | Medium | Fixed — different cases for scene and demo |
| A5 | Claude | High | Fixed — tiered notification table |
| A6 | Claude | High | Fixed — own the friction framing |
| A7 | Claude | Lethal | Fixed — conservative calibration reframe |
| A8 | Claude | High | Fixed — Regulatory Posture box |
| A9 | Claude | High | Fixed — SaMD awareness in Regulatory Posture |
| A10 | Claude | Medium-High | Fixed — system prompt file path annotation |
| A11 | Claude | Medium | Fixed — full three-tier table |
| A12 | Claude | High | Fixed — failure pattern table |
| A13 | Claude | Medium | Fixed — five layers small and grey |
| A14 | Claude | Low-Medium | Fixed — consistent backgrounds |
| A15 | Claude | Medium | Fixed — async-first industrial framing |
| A16 | Claude | Low-Medium | Fixed — three USPs only |
| B1 | Gemini | Lethal | Fixed — `sms:` URI offline fallback |
| B2 | Gemini | High | Fixed — own the friction |
| B3 | Gemini | Medium | Fixed — "0 structured records" |
| B4 | Gemini | High | Fixed — Phase 2 as scaling path |
| C1 | Perplexity | Lethal | Option A fixed for tonight — Option B pending before March 28 |
| C2 | Perplexity | Medium-High | Fixed — 280,000 records figure |
| C3 | Perplexity | Medium-High | Fixed — scene rewrite with intervention moment |
| C4 | Perplexity | Medium | Fixed — acknowledge limit, Whisper fallback |
| C5 | Perplexity | High | Fixed — workflow alert not clinical recommendation |
| D1 | ChatGPT | Medium | Resolved by C3 |
| D2 | ChatGPT | Medium | Resolved by B3 |
| D3 | ChatGPT | Low | Not live concern — failure pattern table |
| D4 | ChatGPT | Medium | Fixed — SMS operational footnote |
| D5 | ChatGPT | Medium | Fixed — Nature Medicine citation |
| D6 | ChatGPT | Low-Medium | Fixed — soften Sarvam claim |
| D7 | ChatGPT | Low | Noise — no fix required |
| D8 | ChatGPT | Low-Medium | Fixed — Android 8+ qualifier |
| D9 | ChatGPT | Medium | Fixed — one line under GitHub link |
| D10 | ChatGPT | Medium | **Must fix tonight — run Colab, replace brackets** |
| D11 | ChatGPT | Low | Design execution note — no structural fix |
| E1 | Perplexity R2 | Medium | Pending — ONNX build task before March 28 |
| E2 | Perplexity R2 | High | **Must fix tonight — run Colab, replace brackets** (same as D10) |
| E3 | Perplexity R2 | High | Fixed — PLI sentence on Slide 5 |
| F1 | ChatGPT R2 | Low | Design execution note — no structural fix |
| F2 | ChatGPT R2 | Low-Medium | Resolved by correct language implementation |
| F3 | ChatGPT R2 | Medium | Fixed — Slide 1 scene ending changed to information gap |
| F4 | ChatGPT R2 | Low | Noise — no fix required |
| F5 | ChatGPT R2 | High | Resolved by E3 |
| F6 | ChatGPT R2 | Medium | Fixed — "one tap, zero typing" framing |
| F7 | ChatGPT R2 | Low | Verbal answer sufficient — no fix required |
| F8 | ChatGPT R2 | High | Resolved by E2/D10 |
| F9 | ChatGPT R2 | Medium | Repo task — ensure commits, README, system prompt file exist |

---

### TONIGHT'S HARD DEADLINE ACTIONS (Before PPT Submission)

1. **Run Colab confusion matrix** — replace [X]% with real numbers on Slide 3
2. **Measure end-to-end pipeline latency** — stopwatch, add to Slide 3
3. **Update Slide 1 scene ending** — information gap, not death outcome
4. **Update Slide 3 notification table** — "one tap, zero typing" for offline Emergency
5. **Update Slide 5 adoption paragraph** — PLI sentence added
6. **Ensure GitHub repo** — meaningful commits, README, system prompt file at named path

---

*Document version: Post second adversarial review round — all rounds incorporated*
*Prepared for India Innovates 2026 — VitalNet HealthTech Submission*
*PPT Submission Deadline: March 10, 2026, 11:59 PM IST*
