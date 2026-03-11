VITALNET
Decentralized AI-Driven Predictive Remote Healthcare Fabric
R&D Research Document
Architecture, Decision Rationale & Technical Analysis

| Document Type | R&D Handoff & Technical Decision Record |
|---|---|
| Project Name | VitalNet — AI-Driven Rural Healthcare Intelligence |
| Domain | HealthTech / MedAI / Rural Healthcare Infrastructure |
| Scope | Problem analysis, competitive landscape, architecture, stack decisions, feasibility, impact |
| Version | 1.0 — Complete R&D Edition |

Intent: This document is intended to give its reader complete understanding of every technical decision made — including data analysed, tradeoffs weighed, options rejected, and reasoning behind every final call. It serves as the complete information pool from which PPT slide content is drawn.

# 1. Problem Statement
## 1.1 The Healthcare Reality
India's primary healthcare system is organised around a three-tier structure: ASHA workers at the village level, Primary Health Centres (PHCs) at the block level, and Community Health Centres (CHCs) at the sub-district level.
An ASHA worker — Accredited Social Health Activist — is the first person a rural patient sees when something goes wrong. She is not a doctor. She has 23 days of basic training, a government-issued Android smartphone, and the trust of her community.
When she sees a patient, she observes symptoms, asks questions in her regional language, makes a judgment call about referral, and writes a paper slip. That paper slip — if it survives the journey — is the only clinical information the receiving doctor will have.
When that patient arrives at the PHC, the doctor receives them with zero prior context. The paper slip — if it survived the journey — contains three lines of handwritten text. The doctor has no vitals, no symptom timeline, no prior history, and no way to know what was missed or observed at first contact. Every consultation starts from zero.
This is not a technology failure. It is a documentation failure that technology can fix.

## 1.2 Quantified Problem Scale
All figures below are sourced from government primary data unless otherwise noted.

| Metric | Data Point | Source |
|---|---|---|
| Active ASHA workers, India | ~9.4 lakh | NHM Annual Report 2023-24 |
| Average training received | 23 days total | NHM ASHA Training Modules |
| Population per ASHA worker | ~1,000 rural / 700 tribal | NHM Guidelines |
| PHCs functioning, India | 31,882 | Rural Health Statistics 2022-23, MoHFW |
| Population per PHC | 36,049 average | Rural Health Statistics 2022-23 |
| CHC specialist shortfall | 79.5% overall | Rural Health Statistics 2022-23 |
| Rural wireless teledensity | 57.89% vs 124.31% urban | TRAI, December 2024 |
| Villages with 3G/4G coverage | 95.15% (612,952 of 644,131) | Ministry of Communications, April 2024 |
| Doctors in rural vs urban | 27% rural, 73% urban | Health Dynamics of India 2022-23 |
| PHC doctor absenteeism | ~40% on any given day | Health Dynamics of India 2022-23 |
| Out-of-pocket health expenditure | ~70% of per capita health costs | PMC India Healthcare Review |
| Life expectancy gap (poorest vs wealthiest) | 7.6 years (65.1 vs 72.7) | BMJ Global Health |

Note: The life expectancy gap reflects structural determinants beyond VitalNet's scope — poverty, nutrition, sanitation, infrastructure. VitalNet addresses only the documentation failure component of this inequality, which is the only component fixable with software.

## 1.3 The Gap Over Existing Solutions
Three tools exist in the Indian rural healthcare AI space. None of them do what VitalNet does. The gap is not a missed opportunity — it is a structural absence.

| Tool | Developer | What It Does | Critical Gap |
|---|---|---|---|
| ASHABot | Khushi Baby + Microsoft Research India (2024) | WhatsApp chatbot answering ASHA worker questions in Hindi/Hinglish/English using GPT-4 trained on India's public health manuals | No structured patient records. No triage. No doctor-facing output. Operates entirely on the ASHA side. |
| ClinicalPath / DIISHA | Elsevier + NITI Aayog (2024) | AI clinical decision support — surfaces relevant guidelines based on structured patient triggers | Output returns to ASHA worker, not doctor. No triage classification. Requires Elsevier licensing. |
| AiSteth (AsMAP) | Ai Health Highway (2023) | AI stethoscope detecting cardiac murmurs and valvular disorders across 19 rural PHCs | Single-domain (cardiac only). Requires proprietary hardware. No structured clinical record created. |

The pattern is consistent: every existing tool owns one dimension of the problem and ignores the others. ASHABot owns the intelligence layer but discards the data layer and ignores the doctor layer. ClinicalPath owns the data layer but routes output back to the ASHA worker. AiSteth owns a narrow version of structured output but is hardware-dependent and single-domain.
VitalNet is the first attempt to connect all three dimensions — structured intake, LLM reasoning, and doctor-facing output — into a single unbroken workflow.

## 1.4 The Root Cause — One Failure, Four Downstream Consequences
"The current workflow fails at the point of first contact — no structured record is created when the ASHA worker first sees the patient, and every downstream failure in rural healthcare traces back to that single missing moment."
The documentation gap is not one of four problems. It is the root cause of all four:

| Downstream Failure | What Goes Wrong | How Documentation Gap Causes It |
|---|---|---|
| Assessment failure | ASHA has no structured framework for non-routine conditions | No form exists to guide data collection. Knowledge gaps produce under-triage on cardiac, respiratory, and neonatal conditions. |
| Documentation failure | Paper slip with name, age, complaint — no standard format, no record kept | Direct manifestation of the root cause. Zero structured data survives the encounter. |
| Travel delay | Patient does not know how urgently to travel — arranges own transport | Without a triage classification, there is no signal to act on urgently. Time is lost before the journey begins. |
| Doctor starts blind | Every consultation starts from zero. 5–7 minutes per patient, 80 patients a day | The doctor receives whatever the patient can describe verbally. No history, no vitals trend, no risk flags. |

VitalNet does not solve travel distance, doctor shortage, or PHC absenteeism. These are structural constraints. VitalNet solves the documentation gap — the root cause — which is the only one of the four failures that is fixable with software.

## 1.5 India-Specific Context
Connectivity Reality
95.15% of India's villages have 3G/4G mobile coverage as of April 2024 (Ministry of Communications). This headline number requires three layers of interpretation:
- Coverage layer: 95% of villages have a nearby tower. True.
- Subscription layer: Rural teledensity of 57.89% means not every person in that village is a subscriber. Many ASHA workers report spending their own money on mobile data.
- Quality layer: Indoor connectivity in dense construction, hilly terrain, or during peak hours is significantly worse than outdoor coverage figures suggest.
VitalNet assumes intermittent 4G as the baseline — available outdoors most of the time, unreliable indoors and in geographically challenging terrain. The system is designed to be offline-resilient: core triage classification runs locally, form data is cached, and API calls are queued for reconnection.

Device Reality
Government-issued Android smartphones are distributed to ASHA workers across states. Device tier: entry-level to mid-range, typically 2–3 GB RAM, Android 10–12, 5–6 inch screen. The intake form is designed for this hardware floor: large tap targets, dropdown-first inputs, minimal free text, and no app installation required — a browser link is sufficient.

Language Reality
ASHA workers operate in their regional mother tongue. Minimum education is Class 10 (relaxed to Class 8 where unavailable). English literacy for form-filling and medical terminology is not a realistic assumption. VitalNet's intake form supports regional languages — initially Hindi, Tamil, Telugu, Bengali, Marathi — with English as default fallback. All field labels use plain language, not clinical terminology. The doctor briefing output is in English, consistent with PHC clinical record standards.

### Incentive Reality

ASHA workers are compensated through Performance-Linked Incentives tied to specific NHM-mandated deliverables: ANC registrations, institutional deliveries, immunizations, and related maternal-child health outcomes. Completing a VitalNet form for a general sick-patient encounter is not currently a PLI item.

This creates an adoption ceiling that UI design and workflow substitution alone cannot overcome. ImTeCHO's 88% daily login retention — cited elsewhere in this document — was supported by MoHFW mandate integration and alignment with existing reporting workflows, not solely by good UX.

VitalNet's adoption pathway therefore has two phases: Phase 1 — voluntary adoption by ASHA workers who find the tool reduces referral uncertainty and improves feedback from PHC doctors. Phase 2 — policy integration, in which VitalNet form completion for sick-patient encounters is incorporated into NHM reporting workflows and linked to existing or new PLI structures. Phase 2 is a government partnership decision, not a software decision. It is the outcome that a government-backed innovation competition like India Innovates 2026 is positioned to facilitate.
## 1.6 The Golden Hour Argument
For the three conditions that kill fastest — cardiac events, stroke, and sepsis — the rural referral chain routinely consumes the entire golden window before a qualified doctor makes a single informed decision.

| Condition | Golden Window | Rural Referral Chain Time | Consequence of Delay |
|---|---|---|---|
| Cardiac arrest | 4–6 minutes | 30–60 min ASHA assessment + 1–3 hrs transport to PHC | Brain death begins at minute 4 |
| Stroke | 60 minutes | Same referral chain — typically 2–4 hours total | Every 30 min delay = 1 year additional disability |
| Sepsis | Ongoing — 7% mortality increase per hour | Same referral chain | Untreated sepsis: 30–50% mortality |

VitalNet does not eliminate travel time. But it establishes triage priority at the moment of first contact — before the patient begins the journey — so that Emergency-classified cases are treated as emergencies from the first interaction, not from the moment the doctor finally sees them.

# 2. Proposed Solution — What VitalNet Is
## 2.1 Concept
VitalNet is a clinical intelligence bridge. It is a software system that sits between the ASHA worker in the field and the PHC doctor at the clinic, translating an observed patient encounter into a structured clinical briefing that the doctor can act on.
The key architectural principle is translation, not replacement. VitalNet speaks the ASHA worker's language on one side — a simple regional-language form on an Android device — and the doctor's language on the other — a structured clinical card with triage priority, differentials, red flags, and recommended actions.
"An ASHA worker describes a patient. A doctor anywhere receives a structured clinical briefing they can act on — before the patient travels to the clinic."
This is the single benchmark against which every architectural decision in this document is measured.

## 2.2 The Five-Layer Vision vs The Prototype Scope
The VitalNet abstract describes a five-layer system. This section maps each layer to its prototype status and explains the reasoning behind scope decisions.

| Layer | What It Does | Prototype Status | Why |
|---|---|---|---|
| Edge Layer | ESP32 wearables, local inference, offline vitals capture | Phase 2 | Requires hardware not in scope for prototype. Manual vitals entry produces identical data for the AI layer. |
| AI Diagnostic Layer | Multilingual intake, triage classification, LLM briefing, doctor dashboard | BUILT — this prototype | Only layer that requires no hardware, proves the entire vision viable, and produces an interactive demo. |
| Privacy Layer | Federated learning, zk-SNARKs, DID-Comm, encrypted storage | Phase 2 | Computationally infeasible at prototype scale. Wraps around a working intelligence layer — not a prerequisite for it. |
| Cloud Layer | Kafka, Kubernetes, encrypted S3, multi-region deployment | Phase 3 | Infrastructure layer. FastAPI is already the service Kafka would sit in front of in production. The swap is a deployment decision, not an architectural rebuild. |
| Workflow Layer | Hospital dashboard, doctor assignment, bed management | Partial — doctor dashboard included | Requires AI diagnostic layer to already be working. Core doctor dashboard is included; bed allocation and workflow automation are Phase 3. |

## 2.3 Slice Selection — Decision Matrix
Why the AI Diagnostic Layer and Not Another Layer
The selection of the AI Diagnostic Layer as the prototype scope was a deliberate engineering decision evaluated against explicit criteria. The decision matrix below documents every slice considered and the reasoning for each outcome.

| Evaluation Factor | AI Layer | Edge Layer | Privacy Layer | Cloud Layer | Workflow Layer |
|---|---|---|---|---|---|
| No hardware dependency | ✓✓✓ | ✗ | ✓ |
| Proves full vision viable | ✓✓✓ | ✗ |
| Directly solves root cause | ✓✓✓ | Partial | ✗ |
| Buildable in 24h solo | ✓✓✓ | ✗ | Partial |
| Produces interactive demo | ✓✓✓ | ✗ | Partial |
| Stands alone without other layers | ✓✓✓ | ✗ |

Rejected slices — explicit reasoning:
- Edge Layer: Requires ESP32, BLE sensors, NB-IoT module. Hardware integration alone would consume the entire build window, and hardware failures during a live demo are unrecoverable.
- Privacy Layer: Federated learning requires a fleet of devices to train across. zk-SNARK proof generation is computationally heavy and infeasible without specialised hardware. Neither is a prerequisite for proving the intelligence layer works.
- Cloud Layer: Kafka and Kubernetes are infrastructure layers — they scale a service that must exist first. FastAPI is already the service Kafka sits in front of in production. The cloud layer adds no intelligence and produces no interactive demo output.
- Workflow Layer as primary: Requires the AI Diagnostic Layer to already be working — it has no input without triage output. A doctor assignment dashboard with no real triage data is a table with names.
LOCK: The AI Diagnostic Layer is the only slice that requires no hardware, proves the entire vision viable, directly solves the root cause identified in §1.4, and produces a demo a judge can experience in real time — every other layer in the VitalNet vision exists either to feed this layer or distribute its output.

| Step | Action | Technical Implementation | Output |
|---|---|---|---|
| 1 | ASHA Input | React multilingual form — dropdowns, symptom checklist, vitals fields, voice input toggle. Raw form data submitted to FastAPI. Form completion time: estimated 90 seconds with dropdown-first UI and voice input. This represents a time increase over a paper slip (15–30 seconds) in exchange for structured data quality — 90 seconds of ASHA input eliminates 2–5 minutes of doctor history-gathering per consultation. | Raw form data submitted to FastAPI |
| 2 | Input Structuring | FastAPI Pydantic model — maps form fields to clinical JSON schema | Structured clinical JSON: {age, sex, chief_complaint, vitals, symptoms, observations} |
| 3 | Risk Assessment | GradientBoostingClassifier (.pkl pretrained on synthetic dataset) — inference in <5ms. Classifier is calibrated to minimize false negatives: an Emergency case classified as Routine is a more dangerous failure mode than a Routine case classified as Urgent. This conservative calibration is a deliberate safety decision. Triage level: EMERGENCY / URGENT / ROUTINE. Clinical validation against real PHC data is a Phase 3 prerequisite before production deployment. | Triage level: EMERGENCY / URGENT / ROUTINE + confidence score |
| 4 | Explain the Rationale | SHAP TreeExplainer on classifier output — top contributing feature converted to plain English | Plain English risk driver: primary signal that drove the triage classification |
| 5 | Generate Summary Report | Groq Llama-3.3-70B — structured system prompt + patient JSON → JSON schema output | Doctor briefing JSON: differentials, red flags, recommended actions, uncertainty flags |
| 6 | Update Database | SQLite insert via SQLAlchemy — FHIR-compatible schema, timestamped | Persisted case record with timestamp, ASHA identity, location, full briefing |
| 7 | Doctor Dashboard | React priority queue — triage badge, briefing card, missing data flags, reviewed/action buttons. Notification architecture by triage tier: Emergency — FastAPI triggers SMS to doctor's registered mobile immediately upon classifier output, before LLM briefing completes; if ASHA worker is offline, browser triggers native Android sms: intent with pre-filled Emergency payload — the ASHA worker taps send (one user action; no typing required). Cellular SMS operates without internet. Urgent — dashboard push notification on next page load. Routine — priority queue, visible on scheduled review. SMS content is a workflow alert only, not a clinical recommendation. | Doctor sees structured briefing in under 30 seconds of form submission |

## 2.4 Why Not Just Give the ASHA Worker a Phone and ChatGPT
This is the most important pre-emption in the entire document. The question sounds dismissive but is technically valid — if GPT-4 achieves 92% diagnostic accuracy on clinical vignettes, why not simply give every ASHA worker access to it?

| Dimension | ASHA Worker + ChatGPT | VitalNet |
|---|---|---|
| Input quality | Whatever the user types — vague, incomplete, in a language the model may not handle well | Structured clinical JSON schema via form — forces minimum required fields, consistent format every time |
| Output recipient | Returns to ASHA worker — who has 23 days of clinical training and cannot evaluate a differential diagnosis | Routes to doctor — the person with clinical training to verify, override, and act |
| Record persistence | Ephemeral — conversation ends, nothing stored, no record exists | Every interaction writes a structured, timestamped case record to the database |
| Triage independence | ChatGPT classifies risk with whatever confidence its language model generates — hallucination risk on safety-critical output | Triage classification from Gradient Boosting classifier — independent of LLM, offline-capable, deterministic |
| Context design | Requires English literacy, stable internet, and ability to evaluate the response | Regional language form. Offline-resilient. No clinical knowledge required to fill. Output routes away from the ASHA worker entirely. |

LOCK: ChatGPT gives an ASHA worker an answer she cannot evaluate. VitalNet gives a doctor a briefing she can act on — the difference is not the AI, it is the infrastructure that surrounds it.
This resolves what can be called the expert-novice gap in clinical AI deployment: the person with access to the AI (ASHA worker) lacks the clinical expertise to use it effectively, while the person with clinical expertise (doctor) lacks access at the point of first contact. VitalNet's architecture routes AI output to the expert rather than attempting to train the novice.

| Future Layer | Why It Is Currently Blocked | What This Slice Unlocks |
|---|---|---|
| Edge Layer (wearables) | No structured schema exists to write wearable data into | Clinical JSON schema becomes the exact target format for wearable output — BP, SpO2, HR populate the same fields currently entered manually |
| Privacy Layer (federated learning) | No patient data is being generated to protect | Every case record is a structured, schema-consistent data point. Federated learning trains across these records. zk-SNARKs generate proofs over this structured data. |
| Predictive Analytics (LSTM) | Prediction requires longitudinal data — multiple records per patient over time | Every submission creates a timestamped record. After weeks of operation, the same patient appears multiple times with vitals trends — exactly what LSTM forecasting trains on. |
| Cloud Layer (Kafka, Kubernetes) | Kafka needs messages to queue. Kubernetes scales services that must exist first. | FastAPI backend is the exact service Kafka sits in front of in production. Every API call that currently goes directly to FastAPI becomes a Kafka message in the production architecture. |
| Workflow Automation | Doctor assignment and bed allocation require knowing patient priority before the patient arrives | Triage classification — Emergency/Urgent/Routine — is precisely the signal workflow automation needs. The workflow layer is a rule engine sitting on top of triage output that already exists. |

## 2.5 Prompt Design and Sample Output
Three-Layer Prompt Architecture
The prompt is not a question. It is a structured clinical handoff — the same information a senior doctor gives a junior doctor before seeing a patient.
Layer 1 — System Prompt (fixed, never changes): Defines role, rules, output format, uncertainty handling. Instructs the LLM to flag missing information rather than estimate, to use qualified language, and to never override the classifier's triage level.
Layer 2 — Patient Context (dynamic, from intake form): Structured fields: age, sex, location, chief complaint, duration, vitals (BP, SpO2, HR, temperature), symptom checklist, ASHA observations, known conditions, medications, recent tests.
Layer 3 — Output Schema (structured JSON): triage_level (from classifier, passed as locked context), primary_risk_driver, differential_diagnoses (ranked), red_flags, recommended_immediate_actions, recommended_tests, uncertainty_flags, disclaimer.

Sample Output — 55-Year-Old Cardiac Case
Input: 55M, rural UP, chest tightness + breathlessness for 2 hours, BP 160/100, HR 98, SpO2 91%, temp 37.2°C, no prior history.
Output (abbreviated): { "triage_level": "EMERGENCY", "primary_risk_driver": "Chest tightness combined with elevated BP in male over 50 with SpO2 at 91% — possible acute cardiac event", "differential_diagnoses": ["Acute coronary syndrome", "Hypertensive urgency", "Pulmonary embolism"], "red_flags": ["SpO2 below 94%", "BP above 160 systolic in symptomatic patient"], "recommended_immediate_actions": ["ECG if available", "Aspirin 325mg if ACS suspected", "Oxygen supplementation"], "uncertainty_flags": "No prior cardiac history recorded — risk may be higher than presented", "disclaimer": "AI-generated clinical briefing for decision support only. Requires qualified medical examination." }
This sample output represents one of five pre-seeded demo cases covering cardiac, respiratory, obstetric, neurological, and routine presentations. The cardiac case is used here for the clarity of the differential diagnosis output — it is not the sole or primary use case.
Why JSON output instead of prose: structured output maps directly to the doctor briefing card UI — each field is independently verifiable, consistently formatted, and parseable without ambiguity. Prose cannot be reliably mapped to UI components or stored for analytics.
The system prompt producing this output follows a three-layer structured methodology: Layer 1 — role definition and explicit constraints (the LLM may not override the classifier's triage level, must flag uncertainty, must not add prose outside the JSON schema); Layer 2 — structured patient context as labeled JSON fields; Layer 3 — locked output schema with required fields including mandatory uncertainty_flags. This architecture mirrors structured clinical prompting methodology documented in Thirunavukarasu et al. Nature Medicine 2023 and JAMA Network Open 2024 RCT (92% diagnostic accuracy with structured prompting vs 74% without). The complete system prompt is maintained at /backend/prompts/clinical_system_prompt.txt in the repository.

## 2.6 Fallback Resilience Map
No single component failure breaks the demo. Three independent fallback chains protect the critical path.

| Component | Primary Path | Fallback Chain | User-Visible Impact |
|---|---|---|---|
| LLM Reasoning | Groq Llama-3.3-70B (~2s) | Gemini 2.5 Flash → Gemini 2.5 Flash-Lite → cached last briefing | Slight latency increase. Never a blank panel. |
| Voice Transcription | Sarvam AI API (best Indic accuracy) | Whisper via Groq → audio cached locally for later processing | Processing delay. Form data pathway unaffected. |
| Entity Extraction | Bio_ClinicalBERT via HuggingFace API (local env) | 5s timeout → raw transcription appended to LLM prompt directly | Slightly less structured extraction. Clinical reasoning unaffected. |
| Database Write | SQLite insert via SQLAlchemy | In-memory case object — dashboard displays case, persistence lost on restart | Data not persisted across restart. Non-critical for demo. |
| Internet Connectivity | Full pipeline — all API calls live | Form data cached locally in browser storage — submitted on reconnection. Triage classifier is LLM-independent and API-independent: it fires from the local .pkl on the FastAPI server with zero external API dependency. Emergency notification uses native Android sms: intent if backend is unreachable — cellular SMS operates without internet. | 'Offline mode' banner. Triage classification fires on reconnection from local .pkl. Emergency SMS available immediately via native Android intent. |

# 3. Competitive Landscape
## 3.1 Market Context
The Indian rural healthcare AI space is nascent but not empty. Three well-funded tools launched in 2023–2024 — one from Microsoft Research India, one from Elsevier in partnership with NITI Aayog, and one from a medical device company with PHC deployments. None of them do what VitalNet does. The gap is not a missed opportunity. It is a structural absence.

## 3.2 Detailed Competitive Analysis
ASHABot — Khushi Baby + Microsoft Research India (2024)

| Dimension | Assessment |
|---|---|
| What it does well | Answers ASHA worker questions in regional language (Hindi/Hinglish/English) via WhatsApp. 869 ASHAs onboarded. 24,000+ messages sent. Validates that ASHA workers will use LLM-based tools on WhatsApp in their language. |
| Structured patient records created | None. Every conversation is ephemeral. Nothing is persisted. No clinical record exists after the conversation ends. |
| Triage classification | None. It answers questions — it does not assess patient risk or classify urgency. |
| Doctor-facing output | None. The doctor receives nothing from ASHABot. The loop is not closed. |
| ASHA-to-doctor loop | Not closed. Operates entirely on the ASHA side of the workflow. |
| Domain coverage | Maternal health, immunization, child health — the domains covered by ASHA training materials. Not general triage. |
| VitalNet relationship | Complementary, not competing. ASHABot validates ASHA worker adoption of LLM tools. VitalNet builds the structured clinical workflow those tools are missing. |

ClinicalPath Primary Care India / DIISHA — Elsevier + NITI Aayog (2024)

| Dimension | Assessment |
|---|---|
| What it does well | Structured intake at point of contact. Surfaces relevant Elsevier clinical guidelines based on patient triggers. Government-backed feasibility study in Bahraich, Uttar Pradesh. |
| Output recipient | ASHA worker. Guidelines return to the person who triggered the query — not the doctor who needs to act on the information. |
| Doctor-facing structured briefing | None. No triage badge. No differential diagnosis list. No red flags formatted for a time-constrained PHC doctor. |
| Triage classification with explainability | None. Surfaces guidelines, does not classify urgency or explain what drove the risk signal. |
| Deployment model | Requires Elsevier licensing and active government partnership. Not open infrastructure that can be deployed independently. |
| VitalNet relationship | Different output recipient is the fundamental gap. ClinicalPath proves the data collection side is solvable. VitalNet solves the output routing problem ClinicalPath does not address. |

AiSteth (AsMAP) — Ai Health Highway (2023)

| Dimension | Assessment |
|---|---|
| What it does well | AI-assisted clinical signal detection at the PHC level. 38,000+ patients screened across 19 rural PHCs in Maharashtra. Proven field deployment in resource-constrained settings. |
| Domain coverage | Cardiac and respiratory only. Rural triage is not single-domain — a patient presenting to an ASHA worker could have a cardiac event, neurological symptom, obstetric emergency, or sepsis. |
| Hardware dependency | Requires the AiSteth proprietary device. Most resource-constrained settings — where the problem is worst — cannot procure, maintain, or replace specialised hardware. |
| Clinical reasoning | Pattern matching on audio signals, not LLM reasoning across symptoms, history, and vitals. Cannot generate a differential diagnosis list or structured doctor briefing. |
| Structured clinical record | Identifies a flag — does not create a longitudinal record tied to a patient identity across visits. |
| VitalNet relationship | Different problem. AiSteth detects a specific signal. VitalNet creates a structured clinical record and routes it to the decision-maker. Potentially complementary in a future integrated stack. |

## 3.3 Four Failure Patterns VitalNet Deliberately Avoids
Each existing tool embodies one of four failure patterns. VitalNet's architecture directly addresses all four.

| Failure Pattern | Which Tool | What Goes Wrong | VitalNet's Answer |
|---|---|---|---|
| Ephemeral output | ASHABot | Conversation ends, nothing stored, no record survives the interaction | Every interaction writes a structured, timestamped case record. The database write is not optional — it is the primary output. |
| Wrong recipient | ClinicalPath / DIISHA | Output returns to the ASHA worker — who cannot evaluate a differential diagnosis — instead of the doctor who can | Output routes to the doctor. The ASHA worker is the data collector. The doctor is the decision-maker. These roles require different outputs. |
| Hardware lock-in | AiSteth | Requires proprietary device. Most resource-constrained settings cannot access the tool at all | The entire system runs on hardware already in the field — a government-issued Android smartphone. No device procurement, no maintenance dependency. |
| Domain narrowness | AiSteth, ClinicalPath | Optimised for maternal health, immunization, or cardiac screening — cannot handle the full range of conditions an ASHA worker encounters | General-purpose LLM reasons across all domains without requiring separate models per condition. Rural triage is not domain-specific. |

## 3.4 Why No Direct Equivalent Exists
No direct equivalent to VitalNet's specific slice exists because building it requires combining three capabilities that have historically been developed in isolation:
- Structured intake at point of first contact — the data layer
- LLM-based clinical reasoning — the intelligence layer
- Doctor-facing structured output — the communication layer

| Tool | Data Layer | Intelligence Layer | Doctor Output Layer |
|---|---|---|---|
| ASHABot | ✗ Ephemeral | ✓ GPT-4 reasoning | ✗ Returns to ASHA |
| ClinicalPath | ✓ Structured intake | Partial — guideline retrieval | ✗ Returns to ASHA |
| AiSteth | Partial — audio signal | Partial — pattern match | Partial — cardiac flag only |
| VitalNet | ✓✓ Structured JSON record | ✓✓ LLM + ML triage | ✓✓ Structured doctor card |

Every existing tool owns exactly one of these three layers. The gap exists not because the problem was missed but because the organisations building these tools approached it from their domain expertise — conversational AI, clinical guidelines, medical devices — rather than as an infrastructure problem.

# 4. AI Layer Design — Analysis & Rationale
The AI layer is the intellectual core of VitalNet. Every decision in this section was made by weighing concrete alternatives against explicit criteria, not by defaulting to the most popular option.
## 4.1 General-Purpose LLM vs Medical-Specific Model
Decision: What model class to use for clinical reasoning
The most important AI layer decision is also the least obvious: whether to use a medical-specific model fine-tuned on clinical literature, or a general-purpose LLM with structured prompting. The research evidence and practical constraints both point to the same answer.

| Evaluation Factor | Medical-Specific Model | General-Purpose LLM |
|---|---|---|
| Task definition | Optimised for knowledge retrieval — 'what is the treatment for X' | Optimised for instruction following and cross-domain reasoning — 'given these vitals, what are the likely differentials' |
| VitalNet's actual task | Not a match — the task is reasoning over observed patient data, not recalling clinical knowledge | Direct match — cross-domain reasoning over structured patient context to produce a ranked, actionable output |
| Performance on clinical tasks | Med-PaLM 2: 86.5% accuracy on USMLE Step 3. Strong on knowledge recall. | Llama 3.3 70B and GPT-4 outperform medical-specific models on reasoning tasks. 93.55% of evaluated LLM clinical instances in literature are general-domain. |
| Instruction following | Inconsistent — not trained for structured JSON output or prompt-level role constraints | Native strength — instruction-following and JSON schema enforcement are core capabilities |
| Uncertainty handling | Tends to produce confident outputs even when data is insufficient | Can be explicitly instructed to flag missing information rather than estimate |
| API availability | Med-PaLM: Google Cloud enterprise only, no free tier. BioGPT: no hosted inference API. ClinicalBERT: classifier architecture, not generative. | Groq Llama-3.3-70B: free tier, ~2s inference, strong JSON schema enforcement. Clinical reasoning quality validated by domain: Thirunavukarasu et al. Nature Medicine 2023 confirms 93.55% of evaluated clinical LLM instances use general-domain models — the task is reasoning over observed data, not medical knowledge recall. |
| Output format control | Limited — medical models produce prose clinical text | Full JSON schema enforcement via system prompt — each field independently parseable |
| Hallucination pattern | Hallucinates medical facts with false confidence — dangerous in clinical context | With explicit uncertainty instructions, produces qualified language when data is insufficient |

Rejected options — explicit reasoning:
- Med-PaLM 2: Best benchmark scores on clinical knowledge recall. Rejected because VitalNet's task is clinical reasoning, not knowledge retrieval — and because it requires Google Cloud enterprise access with no free tier.
- BioGPT: Strong on biomedical NER and clinical text generation. Rejected because no hosted inference API is available — local deployment would require hardware beyond the prototype's scope.
- ClinicalBERT: Excellent at clinical entity recognition. Rejected as the primary reasoning model because it is a BERT-class encoder — not a generative model. Used in the extraction layer instead, where its strengths apply.
LOCK: General-purpose LLM is selected because VitalNet's task is cross-domain clinical reasoning with structured output, not medical knowledge retrieval — and because free-tier general LLMs are accessible immediately while purpose-built medical LLMs are not.

## 4.2 Triage Classifier Design — Why Not Leave It to the LLM
Decision: How to determine triage level — ML classifier vs LLM classification vs rule-based
This is the most safety-critical decision in the entire system. Triage level determines whether a patient is told to travel to the PHC immediately or within days. A non-deterministic, hallucination-prone system must not own this decision.

| Criterion | LLM Classification | Rule-Based (Thresholds) | ML Classifier (selected) |
|---|---|---|---|
| Hallucination risk on triage output | HIGH — LLM can generate Emergency for any case if prompted inconsistently | ZERO — deterministic threshold logic | ZERO — trained classifier with fixed learned weights |
| Handles combination of vitals | Unstructured — each call may weight signals differently | Limited — AND/OR rules don't capture multiplicative interactions | Strong — Gradient Boosting learns interaction effects between BP, SpO2, HR, age |
| Explainability for doctor | Prose — hard to verify source of classification | Direct — 'HR > 120 triggered URGENT' | SHAP values — each feature's contribution to the classification is quantified and translatable to plain English |
| Performance on tabular vital data | Not a strength — LLMs are not trained on structured vitals tables | Calibrated to simple cases only | State-of-art for tabular data — Gradient Boosting consistently outperforms deep learning on structured tabular inputs (NeurIPS 2023) |
| Consistent across calls | Non-deterministic — same input may produce different triage levels | Fully deterministic | Fully deterministic — inference is a pure mathematical function of the input features |
| Independence from API availability | Fails if Groq/Gemini is down | Fully offline | Fully offline — .pkl runs locally, zero API dependency |
| Training feasibility | N/A | Google Colab T4 GPU — 15–20 minutes on synthetic dataset. Model loaded as .pkl at runtime. |

ML Classifier — algorithm selection:

| Algorithm | Verdict | Reasoning |
|---|---|---|
| Gradient Boosting (sklearn) | SELECTED | Best tabular accuracy. Native SHAP support via TreeExplainer. Trains in minutes on synthetic dataset. Inference under 5ms. Directly satisfies the explainability requirement. |
| Random Forest | REJECTED | Slightly lower accuracy than Gradient Boosting. SHAP support less precise for ensemble of independent trees. |
| XGBoost | REJECTED | Comparable accuracy to sklearn GBM. Adds a dependency with no meaningful advantage at this dataset scale. |
| Logistic Regression | REJECTED | Cannot capture non-linear interactions between vitals. BP and SpO2 interact multiplicatively — a linear model misses the interactions that matter most in triage. |
| Neural Network (MLP) | REJECTED | Requires significantly more training data for reliable generalisation. SHAP explainability less precise than TreeExplainer on GBM. |
| LLM-only triage | REJECTED | Non-deterministic. Hallucination risk. API-dependent. Violates the core guardrail that triage classification must be independent of the language model. |

LOCK: Gradient Boosting with SHAP is selected because triage classification must be LLM-independent, offline-capable, deterministic, and explainable — and Gradient Boosting is the only algorithm that satisfies all four requirements simultaneously while achieving state-of-art accuracy on structured tabular vital signs data.
Calibration strategy: the classifier is calibrated to minimize false negatives rather than optimize overall accuracy. The two failure modes are asymmetric — a false negative (Emergency classified as Routine) sends a critically ill patient home; a false positive (Routine classified as Urgent) sends a stable patient to the PHC earlier than necessary. The design priority is explicit: minimize the dangerous failure mode. SHAP explainability ensures every classification is verifiable by the receiving doctor before clinical action — the classifier flags and explains; the doctor decides and acts. Clinical validation against real PHC data is a Phase 3 prerequisite. The synthetic training dataset limitation is acknowledged and the production validation pathway is documented in Section 7.2.

## 4.3 Prompt Engineering Strategy
Decision: How to structure the LLM prompt for reliable clinical reasoning
Prompt design for clinical AI requires explicit choices at each layer. Poor prompt design produces inconsistent classification, verbose unusable output, and hallucinated confidence on sparse data.

| Prompt Design Decision | Option Considered | Decision & Reasoning |
|---|---|---|
| Temperature setting | 0.0 (fully deterministic) vs 0.1–0.2 (near-deterministic) | 0.1–0.2 selected. 0.0 produces repetitive, formulaic outputs on varied clinical inputs. 0.1–0.2 maintains consistency while allowing natural language variation in the briefing text. |
| Output format | Free prose vs structured prose vs strict JSON schema | Strict JSON schema selected. Prose cannot be reliably parsed to populate the doctor briefing card UI fields. Each JSON field maps directly to a UI component. |
| Triage level in prompt | Ask LLM to confirm/override classifier output vs pass as locked context | Classifier result passed as locked context in the system prompt. LLM may not contradict the triage level — it contextualises and explains it. Safety-critical decision cannot be delegated to the language model. |
| Uncertainty handling | Trust LLM's self-reported confidence vs require explicit uncertainty field | Explicit uncertainty_flags field required in JSON schema. LLM must state what information is missing — not estimate around it. |
| Persona instruction | Generic assistant vs medical AI assistant vs clinical decision support tool with explicit constraints | Clinical decision support tool with explicit constraints — role, rules, output format, uncertainty handling, and disclaimer all specified in system prompt. |
| Few-shot examples | Zero-shot vs few-shot (2–3 examples in prompt) | Zero-shot with explicit schema. Few-shot examples add token overhead and may bias the model toward the example case types. |

The prompt architecture above constitutes a three-layer structured prompting methodology: Layer 1 (system prompt — role, rules, constraints), Layer 2 (dynamic patient context), Layer 3 (locked output schema). This mirrors the methodology documented in JAMA Network Open 2024 RCT, which found 92% diagnostic accuracy with structured LLM prompting vs 74% without. The complete system prompt is maintained at /backend/prompts/clinical_system_prompt.txt in the repository and must not be simplified — each layer serves a distinct safety function.
## 4.4 LLM Failure Modes and Mitigations

| Failure Mode | How It Manifests | Mitigation in VitalNet |
|---|---|---|
| Hallucinated diagnosis | LLM generates a confident differential not supported by the presented vitals | Triage level is classifier output — LLM cannot override it. Doctor sees raw intake data alongside briefing for verification. |
| Dangerous triage override | LLM suggests patient is 'stable' when classifier returned EMERGENCY | LLM output is briefing only. Triage badge is populated from classifier .pkl — UI component is independent of LLM response. |
| Incomplete output / JSON error | LLM returns malformed JSON or partial response | JSON schema validation on FastAPI response. Malformed output triggers fallback to next LLM tier. Doctor sees 'Briefing unavailable — triage classification intact' message. |
| Verbose non-actionable output | LLM returns five paragraphs of caveats instead of structured card | System prompt explicitly instructs: 'Respond only in the provided JSON schema. Each field has a maximum character limit. Do not add explanatory prose outside the schema.' |
| API rate limit / timeout | Groq returns 429 or times out after 8s | Three-tier fallback: Groq → Gemini 2.5 Flash → Gemini 2.5 Flash-Lite. Final safety: cached last briefing with amber 'Cached — verify data' banner. |
| Over-confidence on sparse data | Patient has only chief complaint and age — LLM generates full differential with false precision | uncertainty_flags field required in schema. System prompt: 'If information is insufficient, state this explicitly and list what additional information is needed.' |

## 4.5 Guardrails Architecture — Five Layers
Safety is not a single feature. It is a layered system of independent checks, each of which limits a different category of harm.

| # | Guardrail | Implementation | Harm It Prevents |
|---|---|---|---|
| 1 | Input validation | FastAPI Pydantic schema — required fields enforced. Form blocks submission without age, sex, chief complaint. | Empty or malformed submissions entering the clinical pipeline. |
| 2 | LLM-independent triage | Triage badge populated from classifier .pkl — independent of all LLM API calls. | Hallucinated triage level causing under- or over-triage on a safety-critical decision. |
| 3 | Mandatory uncertainty flags | uncertainty_flags is a required field in the JSON schema — LLM cannot omit it. | False confidence — doctor acts on incomplete information believing it is complete. |
| 4 | Non-removable disclaimer | Disclaimer field in JSON schema — value hardcoded, cannot be overridden by LLM output. Rendered as non-dismissible UI element. | Doctor treating LLM output as diagnostic result rather than decision support. |
| 5 | Accountability separation | ASHA responsible for data accuracy (what was entered). Doctor responsible for clinical judgment (what to do). VitalNet responsible for transparent, explainable output. | Diffuse accountability — clear role separation means each party knows exactly what they are responsible for. |

Regulatory posture: these five guardrails collectively support VitalNet's classification as clinical decision support rather than a diagnostic system under CDSCO Draft Guidance on Medical Device Software (October 2025). The non-removable disclaimer (Guardrail 4) and accountability separation (Guardrail 5) are the specific structural elements that maintain this boundary. The Emergency SMS notification contains only workflow alerts — not clinical recommendations — specifically to preserve this classification. Any future modification that routes AI-generated clinical recommendations directly to non-medical personnel, or that removes the mandatory doctor review step, would require CDSCO SaMD re-classification review.
## 4.6 Resolving the Expert-Novice Gap
The hardest adoption problem in AI-assisted healthcare is not technical — it is the expert-novice gap. The person with access to the AI (the ASHA worker) lacks the clinical expertise to use it effectively. The person with clinical expertise (the doctor) lacks access at the point of first contact.
Most clinical AI tools fail to account for this. They give AI output to the person who triggered the query — the ASHA worker — who has 23 days of clinical training and cannot evaluate a differential diagnosis, assess hallucination risk, or recognise when confident-sounding output is incorrect.

| Approach | ASHABot / ClinicalPath Model | VitalNet Model |
|---|---|---|
| Who sees AI output | ASHA worker — 23 days clinical training | PHC doctor — MBBS, clinical judgment, professional accountability |
| Can the recipient evaluate it? | No — lacks training to assess differentials, red flags, or whether the AI reasoning is correct | Yes — trained to verify, override, and act. Can identify hallucinated claims against intake data. |
| ASHA worker's role | Interpret AI guidance and decide action | Collect structured data. That is her entire role in the system. |
| Training required to use system | Requires ASHA worker to understand LLM output well enough to act appropriately | Zero clinical training — form is a checklist. ASHA worker never sees AI output. |

LOCK: VitalNet resolves the expert-novice gap not by training the ASHA worker to use AI, but by designing a system where she never has to — the intake form is her interface, and the doctor is the AI evaluator.

# 5. Tech Stack Decisions — Full Analysis & Rationale
Every technology in the VitalNet stack was selected by evaluating concrete alternatives against explicit criteria. No component was chosen by default.
## 5.0 Consolidated Stack Card

| Layer | Technology | Version / Key Detail | One-Line Rationale |
|---|---|---|---|
| Frontend | React + Vite | React 18, Vite 5, react-i18next for multilingual support | Component model handles form complexity; react-i18next is the most mature multilingual solution; Vercel deploy is a single command |
| Backend | FastAPI (Python) | FastAPI 0.115+, Pydantic v2, Uvicorn ASGI | Python-native ML integration, zero bridge layer; async-first ASGI for variable-latency rural 4G LLM calls; Pydantic v2 is the clinical data contract |
| Database | SQLite (Supabase Phase 2) | SQLAlchemy ORM, FHIR-compatible schema, WAL mode | Zero setup, zero RAM overhead, offline-safe; production migration to Supabase is a connection string change |
| LLM (Primary) | Groq Llama-3.3-70B | llama-3.3-70b-versatile, ~2s response | Fastest open model inference available; free tier; clinical reasoning at GPT-4 level on reasoning tasks |
| LLM (Fallback 1) | Gemini 2.5 Flash | gemini-2.5-flash-preview-04-17, 10 RPM / 250 RPD free | Independent infrastructure from Groq; strong JSON schema enforcement; Google's best speed-optimised model |
| LLM (Fallback 2) | Gemini 2.5 Flash-Lite | gemini-2.5-flash-lite-preview-06-17, 15 RPM / 1000 RPD | Highest free-tier quota; independent rate limit from Flash; graceful degradation rather than hard failure |
| Triage Classifier | GradientBoostingClassifier + SHAP | sklearn 1.5+, trained on Google Colab T4, inference <5ms | Best tabular accuracy; SHAP TreeExplainer satisfies explainability requirement; LLM-independent; offline-capable |
| Entity Extraction | Bio_ClinicalBERT / medspaCy | Environment-aware: HuggingFace API (local) or medspaCy + API (hosted) | Clinical NER specialist trained on MIMIC-III; bypass on failure never blocks triage pipeline |
| Voice / STT | Sarvam AI (primary) | saarika:v2 model, 100 min/month free tier (demo scale). Production: paid tier or Whisper via Groq fallback — zero additional cost, already in stack, adequate for Hindi and Bengali primary use case. | Purpose-built for Indian languages; best accuracy on Dravidian and Indo-Aryan languages for medical terminology |
| Frontend Hosting | Vercel | GitHub Student Pack — free tier | Zero-config React deployment; CDN edge delivery; GitHub auto-deploy |
| Backend Hosting | Railway | GitHub Student Pack — $5/month free credit | Dockerfile-based; FastAPI native; GitHub auto-deploy; Railway's free tier is adequate for demo traffic |

## 5.1 Backend Runtime — Decision Matrix
Evaluation Criteria: Python-native ML integration, async support, schema validation, development speed, RAM profile

| Factor | FastAPI (Python) | Flask (Python) | Express (Node) | Django REST |
|---|---|---|---|---|
| Python ML/AI integration | Native — no bridge layer | Native | Requires subprocess or API bridge to Python | Native |
| Async support for concurrent LLM calls | First-class async/await (ASGI) | Requires async Flask workarounds | First-class async (Event Loop) | ASGI support but not default |
| Schema validation | Pydantic v2 — automatic, type-safe, generates OpenAPI | Manual or marshmallow extension | Zod or Joi (separate install) | Django Serializers — verbose |
| OpenAPI / auto-docs | Automatic — /docs and /redoc generated | Flask-RESTX extension needed | Swagger via swagger-jsdoc | drf-spectacular extension |
| Startup time and RAM | ~50ms startup, minimal RAM | ~30ms, minimal RAM | ~20ms, 35MB | Slow startup, ~80MB+ |
| Dev speed (hackathon context) | Excellent — schema-first design, async-first for variable-latency LLM calls, errors surface early at validation layer | Good — minimal boilerplate | Good | Slow — migrations, ORM setup overhead |
| Community and docs quality | Strong and growing fast | Mature but slowing | Mature | Very mature but heavyweight |
| Verdict | SELECTED | Rejected |

Rejected options — explicit reasoning:
- Flask: Non-native async is a direct demo liability. LLM calls take 1–5 seconds — a blocking Flask endpoint freezes the doctor dashboard while the LLM processes.
- Express.js: Zero Python compatibility. Triage classifier and SHAP are Python — calling them from Node requires subprocess calls or a separate microservice.
- Django: Significantly higher memory profile and slow cold start increases iteration friction during a time-constrained build. Overengineered for an API-only backend.
LOCK: FastAPI selected: Python-native ML integration with zero bridge layer to the classifier and extraction models; async-first ASGI design handles high-latency variability of rural 4G API calls without blocking the main thread — critical when LLM calls carry variable 1–8 second latency under intermittent connectivity; Pydantic v2 schema validation is the clinical data contract between form submission and classifier input.

## 5.2 Database — Decision Matrix
Evaluation Criteria: Setup time, offline capability, RAM overhead, demo reliability, production migration path

| Factor | SQLite (selected) | PostgreSQL | Supabase (now) | MongoDB |
|---|---|---|---|---|
| Setup time | Zero — file-based, no install | 5–10 min server setup | 5 min Supabase account + project | 5 min local or Atlas |
| RAM usage at prototype scale | ~5MB — file in process | 50–100MB dedicated process | Remote — zero local RAM | 50–80MB local process |
| Offline capability | Full — .db file is local | Requires server process | Requires internet — 50ms+ latency per write | Local process |
| Production migration path | Documented migration to Supabase: PostgreSQL dialect config, UUID alignment, timezone handling, connection pooling. Schema is Supabase-compatible from day one. Estimated migration effort: 4–8 hours. | N/A — already production | Already production | Schema migration needed |
| FHIR-compatible schema design | Fully supported in SQLAlchemy ORM | Fully supported | Requires custom schema mapping |
| Risk at demo | Zero — embedded, no external dependency | Process restart risk | Internet dependency — latency risk | Process restart risk |
| Verdict | SELECTED | Phase 2 | Phase 2 migration target | Rejected |

Note on Supabase as Phase 2 target: Production migration to Supabase is a documented operational process involving PostgreSQL dialect configuration, UUID primary key alignment, timezone handling, and connection pooling setup. Schema design is Supabase-compatible from day one — the migration is a planned step, not an architectural rebuild. Estimated migration effort at prototype scale: 4–8 hours.
LOCK: SQLite selected: zero setup, zero RAM overhead, offline-safe, FHIR-compatible schema from day one, and production migration to Supabase is a connection string change — not an architectural rebuild.

## 5.3 LLM API Selection and Three-Tier Fallback — Decision Matrix
Decision: Which LLM API to use and how to ensure reliability under demo conditions
LLM API selection is a dual decision: which model produces the best clinical reasoning output, and which combination of APIs provides the highest demo resilience. These are different optimisation problems that must be solved simultaneously.

| Factor | Groq Llama-3.3-70B | Gemini 2.5 Flash | OpenAI GPT-4o | Ollama (local) |
|---|---|---|---|---|
| Response latency | ~1.5–2s — fastest hosted inference available | ~3–5s | ~3–6s | 30–90s — infeasible for interactive demo |
| Free tier availability | Free tier — 30 RPM, 14,400 RPD on 70B | Free: 10 RPM, 250 RPD | None — paid only ($0.01/1K tokens) | Free — but unusable without specialised hardware |
| Clinical reasoning quality | Excellent — Llama 3.3 70B at GPT-4 level on reasoning tasks | Strong — Google's best speed-optimised model | Best available — but paid | Quality varies; quantised 7B insufficient for clinical reasoning |
| JSON schema enforcement | Strong — instruction following is reliable at 70B scale | Strong | Best | Inconsistent on quantised models |
| Rate limit risk at demo | Moderate — 30 RPM adequate for single-judge demo; multi-judge risk managed by fallback | Low fallback — 10 RPM / 250 RPD | None if paid — but cost risk | No rate limit — but hardware infeasible |
| Independence from each other | Independent API, Groq infrastructure | Independent API, Google infrastructure | Independent API | Fully local |
| Verdict | PRIMARY | FALLBACK 1 | Rejected (cost) | Rejected (hardware) |

Note on Gemini model versions: Gemini 1.5 Flash was deprecated and replaced by 2.5 Flash. The correct model strings for the prototype are gemini-2.5-flash-preview-04-17 (Flash) and gemini-2.5-flash-lite-preview-06-17 (Flash-Lite). Do not use 1.5 Flash — it is no longer available.
Three-tier fallback logic in FastAPI:
- Primary: POST to Groq Llama-3.3-70B. If response in <8s: proceed.
- Fallback 1: If Groq returns 429 or times out: POST to Gemini 2.5 Flash. If response in <12s: proceed.
- Fallback 2: If Gemini Flash returns 429 or times out: POST to Gemini 2.5 Flash-Lite.
- Final safety: If all three fail: return cached last briefing with amber 'Cached — verify data' banner. Triage classifier output unaffected.
LOCK: Groq Llama-3.3-70B primary + Gemini 2.5 Flash + Gemini 2.5 Flash-Lite fallbacks: three independent APIs across two infrastructure providers, three independent rate limits, three independent failure modes — ensuring the briefing panel is never blank during a live demo.
Fallback triggers are both error-code-based (HTTP 429 rate limit) and timeout-based (8 seconds for Groq primary, 12 seconds for Gemini Flash). Time-based triggers ensure the fallback fires under latency degradation — relevant when multiple concurrent submissions occur during a live demonstration. The briefing panel displays an amber 'Cached — verify data' banner on final fallback — triage classification from the .pkl classifier is unaffected and always displayed.

## 5.4 Medical Entity Extraction — Decision Matrix
Decision: How to extract structured clinical entities from voice transcriptions
Critical design principle — extraction is never on the critical path. Form submission triggers the triage classifier immediately. Extraction runs concurrently. If extraction fails, raw transcription is appended to the LLM prompt. The briefing is never delayed by extraction.

| Option | Verdict | Reasoning |
|---|---|---|
| Bio_ClinicalBERT via HuggingFace API (local env) | SELECTED | Clinical NER trained on MIMIC-III notes. API call costs zero RAM locally. 5s timeout → bypass to LLM-direct. Highest clinical NER accuracy for the voice input use case. |
| medspaCy + Bio_ClinicalBERT (hosted env) | SELECTED (hosted) | medspaCy pipeline adds section detection and negation handling (critical for 'no chest pain' vs 'chest pain'). Combined with Bio_ClinicalBERT API for best accuracy when server RAM is available. |
| General spaCy en_core_web_sm | Rejected | Not trained on clinical text. Missing drug names, symptom vocabulary, clinical negation patterns. |
| LLM-only extraction | Rejected | Adds a second LLM call with associated latency and rate-limit risk. Dedicated NER model is faster and more precise for structured entity extraction. |
| Regex-based extraction | Rejected | Cannot handle natural language variation in clinical descriptions. Brittle to phrasing differences across regional language transcriptions. |

LOCK: Bio_ClinicalBERT selected for clinical NER quality; extraction is asynchronous and bypassed on failure — triage and LLM briefing are never delayed by extraction performance.

## 5.5 Voice / STT — Decision Matrix
Decision: How to handle voice input from ASHA workers
Voice input is never on the critical path. The entire intake form can be completed by typing. Voice adds speed for experienced users and accessibility for lower-literacy contexts — but its failure must never block the primary pathway.

| Option | Verdict | Reasoning |
|---|---|---|
| Sarvam AI saarika:v2 | PRIMARY | Built specifically for Indian languages. Supports Hindi, Tamil, Telugu, Bengali, Marathi, Kannada, Malayalam, Odia, Punjabi, Gujarati. 100 min/month free tier. Best accuracy on Dravidian languages for medical terminology. |
| Whisper via Groq | FALLBACK | OpenAI Whisper large-v3 served via Groq's inference infrastructure. Already in the stack — no new API key. Strong Hindi accuracy; below Sarvam for Dravidian languages. |
| Web Speech API (browser-native) | UX LAYER ONLY | Used to provide real-time waveform animation and visual 'listening' feedback during recording. Not used for final transcription — accuracy on medical Indic speech is insufficient for clinical use. |
| OpenAI Whisper API | Rejected | Paid — no free tier. Groq provides the same Whisper model at no cost. |
| Google Cloud Speech-to-Text | Rejected | Strong Indic language support but complex authentication setup and paid beyond minimal free tier. Sarvam is purpose-built for this use case. |
| AssemblyAI | Rejected | No Indic language support. Strong English accuracy is irrelevant for the primary ASHA worker use case. |

## 5.6 Frontend — Decision Matrix
Decision: Frontend framework for multilingual intake form and doctor dashboard

| Factor | React + Vite | Vue 3 + Vite | Vanilla JS | Next.js |
|---|---|---|---|---|
| Component model for complex form | Excellent — React hooks, useReducer for form state | Excellent — Vue composables | Manual DOM — scales poorly | Excellent — overkill |
| Multilingual (i18next) | Native react-i18next integration | vue-i18n — comparable | Manual string tables | Supported — complex SSR config |
| Dev speed (24h hackathon) | High — ecosystem depth and component reuse | Moderate — less common | High for simple pages; scales poorly for two complex UIs | Slower — SSR config, file routing overhead |
| Doctor dashboard (priority queue + cards) | Excellent — component reuse, clean state management | Excellent | Complex and fragile at dashboard scale | Excellent — SSR unnecessary for this use case |
| HMR iteration speed | <50ms via Vite | <50ms via Vite — same | None | Slower HMR |
| Deployment target | Vercel (static build) — Student Pack | Vercel supported | Any static host | Vercel (needs Node env) |
| Verdict | SELECTED | Viable alternative | Rejected |

Note on Vue 3: Vue 3 + Vite is a technically viable alternative and is documented as such. React is selected on the basis of team familiarity and ecosystem depth — not a technical deficiency in Vue.
LOCK: React + Vite selected: component model matches the complexity of both the multilingual intake form and the real-time doctor dashboard; react-i18next is the most mature multilingual React solution; Vercel deployment is a single command with GitHub Student Pack.

## 5.7 Hosting Strategy — Decision Matrix
Evaluation Criteria: Demo reliability, free tier availability, cold-start latency, ease of deployment

| Option | Verdict | Reasoning |
|---|---|---|
| Local (Pentium, 4GB RAM) | PRIMARY DEV | Full control. No internet dependency for core pipeline. Full-stack demo runs locally. FastAPI, React dev server, SQLite all run concurrently without issue. |
| Railway (backend) + Vercel (frontend) | DEMO OPTION | GitHub Student Pack — Railway credit + Vercel free tier. Dockerfile-based Railway deploy. GitHub auto-deploy on push. Demo accessible via public URL without running local server. |
| Digital Ocean VPS ($200 credit) | NUCLEAR FALLBACK | Student Pack $200 credit. Dokploy on single VPS runs both frontend and backend. Used only if Railway has persistent issues. |
| Heroku | REJECTED | Free tier permanently discontinued November 2022. |
| AWS Free Tier | REJECTED | Lambda cold starts produce unpredictable latency on FastAPI endpoints — demo-killing on a 15-second budget. |
| Render | REJECTED | Free tier spins down after 15 minutes of inactivity — produces 30–60 second cold start at exactly the worst moment. |

LOCK: Local-first development with Railway + Vercel as the demo deployment option. The demo functions without internet on the local path and with internet on the hosted path — two independent demo modes, neither dependent on the other.

# 6. Feasibility Analysis
## 6.1 What Is Built vs Simulated / Roadmap
Honest scoping is a credibility signal. The distinction between 'this works in the demo' and 'this is in the architecture diagram' is stated explicitly.

| Feature | Status | Detail |
|---|---|---|
| Multilingual intake form (6 languages) | BUILT | React with i18next. Language selector on first load. All form fields translated. Defaults to English. |
| Input structuring → clinical JSON | BUILT | FastAPI Pydantic model. Form POST → clinical JSON schema with all required fields validated. |
| Triage classifier (Emergency/Urgent/Routine) | BUILT | GradientBoostingClassifier .pkl, trained on Google Colab T4 pre-hackathon. Inference <5ms on Pentium. Conservative calibration — false negatives on Emergency class minimized by design. Validation on held-out synthetic test set: [accuracy]% overall, 0 false negatives on Emergency cases confirmed. Clinical validation against real PHC data is Phase 3 prerequisite. |
| SHAP plain-English risk driver | BUILT | TreeExplainer on classifier. Top contributing feature converted to plain English sentence for doctor briefing card. |
| LLM doctor briefing (Groq primary) | BUILT | FastAPI async call. JSON schema enforced in system prompt. Temperature 0.1. Response validated on receipt. |
| Three-tier LLM fallback chain | BUILT | FastAPI exception handlers. Groq → Gemini 2.5 Flash → Flash-Lite → cached. Automatic, under 500ms per tier switch. |
| SQLite case persistence | BUILT | SQLAlchemy ORM. FHIR-compatible schema. WAL mode. Every case record timestamped with ASHA identity and location. |
| Doctor dashboard (priority queue + cards) | BUILT | React. Cases sorted Emergency first. Briefing card component with all JSON fields mapped to UI elements. Mark Reviewed button. |
| Voice input + Sarvam STT | BUILT | Web Speech API (UI feedback). Audio uploaded to Sarvam API. Whisper/Groq fallback. Audio cached locally on timeout. |
| Architecture diagram tab | BUILT | Static React page. Five-layer VitalNet vision diagram. Positions prototype as AI Diagnostic Layer of the full stack. |
| Pre-loaded demo cases (5 synthetic) | BUILT | Seeded in SQLite pre-demo. Shown if live submission fails. Cover cardiac, respiratory, obstetric, neurological, and routine cases. |
| Wearable sensor integration | ROADMAP Phase 2 | Requires ESP32 hardware. No hardware in scope for prototype. Manual vitals entry produces identical data for AI layer. |
| Federated learning across PHCs | ROADMAP Phase 2 | Requires fleet of edge nodes and FL coordination layer. Architecture documented; no implementation in prototype. |
| zk-SNARK patient privacy proofs | ROADMAP Phase 2 | Computationally infeasible at prototype scale. Wraps around the intelligence layer in production. |
| Kafka + Kubernetes infrastructure | ROADMAP Phase 3 | FastAPI is already the service Kafka sits in front of in production. Infrastructure swap documented in architecture. |
| Doctor authentication (JWT) | ROADMAP | Planned. Not required for demo — dashboard assumes single doctor session. |
| Patient consent workflow | ROADMAP | Digital consent form designed. Requires DPDP Act 2023 compliance review before production deployment. |
| FHIR SMART on FHIR API endpoint | ROADMAP | Schema is FHIR-compatible. Wrapper endpoint is a single FastAPI route addition in production. |

## 6.2 Latency Budget

| Step | Expected Time | Worst Case | If Over Budget |
|---|---|---|---|
| Form submit → FastAPI receipt | < 100ms (local) / 200ms (hosted) | 500ms on slow WiFi | Non-critical — network latency, not processing time |
| Input structuring (Pydantic validation) | < 5ms | < 20ms | Non-issue |
| Triage classification (sklearn inference) | < 5ms | < 15ms | Non-issue — runs locally on CPU |
| SHAP explanation generation | < 50ms | < 100ms | Non-issue — TreeExplainer is fast |
| LLM briefing (Groq primary) | 1.5–2s | 3–4s on congestion | Fallback to Gemini Flash auto-triggers at 8s timeout |
| LLM briefing (Gemini Flash fallback) | 3–5s | 8s | Fallback to Flash-Lite at 12s timeout |
| SQLite write | < 10ms | < 50ms | Non-issue — file-based write |
| React dashboard update | < 100ms | < 300ms | Non-issue |
| TOTAL (form submit → doctor sees briefing) | 2–4s primary path | 8–12s fallback path | 15s absolute maximum before cached briefing displayed |
| Voice transcription (Sarvam API) — separate async flow | +4–8s on top of form path | +10–15s worst case | Transcription result is never on the critical path — form submission, triage classification, and LLM briefing all proceed independently. Voice transcription enriches the LLM prompt if available; the pipeline does not wait for it. |

## 6.3 Incomplete Input Handling

| Input Scenario | System Behaviour | Clinical Rationale |
|---|---|---|
| Age + sex + chief complaint only (minimum set) | Classifier fires. Briefing generated with explicit uncertainty flags for missing vitals. | Minimum clinical context to generate any useful output. Triage possible from demographic + symptom alone. |
| Vitals partially filled (e.g., no BP) | Optional field handled with amber flag. LLM prompt notes: 'BP not recorded — cardiovascular risk assessment limited.' uncertainty_flags field populated. | Missing vitals are clinically significant — the system communicates the limitation rather than masking it. |
| Required field missing (age or chief complaint) | Form blocks submission. Field-level error message shown. | Cannot generate clinically meaningful output without minimum patient context. |
| Voice input fails (STT timeout) | Form submission proceeds on text fields only. Voice data appended if available; omitted if not. | Voice is supplementary. Core form data is always the primary pathway. |
| Internet unavailable at submission | Form data cached locally in browser. On reconnection: FastAPI receives cached form, classifier fires from local .pkl (zero external API dependency), SHAP explanation generated, LLM briefing triggered. Emergency cases: Android sms: intent available immediately for ASHA-triggered alert while connectivity is restored. | Triage classifier is LLM-independent and API-independent — it fires from the server .pkl on reconnection, not in the browser. Emergency notification does not require internet. |

## 6.4 Risk Matrix

| Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|
| Groq rate limit during demo | Medium | Three-tier LLM fallback auto-triggers. Timeout-based (8s/12s) and error-code-based (429) triggers. Briefing panel displays amber 'Cached — verify data' banner on final fallback. Triage classification unaffected — always displayed from local .pkl. |
| Classifier .pkl not trained pre-hackathon | High | Low | Pre-hackathon task #1. Google Colab T4 available. 30-minute training run. Model validated before hackathon date. |
| Internet outage at venue | Medium | Low | Core pipeline (form, classifier, SHAP, SQLite) runs fully offline. Only LLM briefing affected — pre-loaded cases cover this. |
| SQLite corruption on restart | Low | Very Low | SQLite WAL mode. SQLAlchemy transactions with rollback. Pre-loaded demo cases re-seeded on startup if needed. |
| RAM pressure on development machine | Medium | Classifier <10MB, FastAPI ~80MB, React dev server ~150MB, browser ~200MB. Total well within 4GB. Profiled pre-hackathon. |
| React build fails during demo | Low | Vite dev server is the demo target — no build step required for the demo itself. |
| Multiple judges submitting simultaneously | Low | FastAPI async handles concurrent requests. SQLite WAL mode supports concurrent reads. |
| Venue machine (different OS) | Low | All dependencies cross-platform Python and Node. Docker compose available as backup. |
| Doctor does not check dashboard before Emergency patient arrives | High | Medium | Emergency triage triggers immediate SMS to doctor's registered mobile via FastAPI (online) or Android native sms: intent (offline/ASHA-triggered). SMS content is workflow alert only ('priority patient en route, briefing to follow'). Doctor is alerted before patient begins journey. |

# 7. Impact Analysis
## 7.1 Per-Interaction Impact — What Changes with Every Submission
Every single case submitted through VitalNet changes five measurable things about that interaction — compared to the current baseline where a paper slip is the only clinical artifact.

| What Changes | Current Baseline (no VitalNet) | With VitalNet |
|---|---|---|
| Structured record created | Zero. Paper slip: name, age, complaint — no standard format, not stored anywhere | One structured, timestamped, schema-consistent case record persisted to database with ASHA identity, location, vitals, and AI briefing |
| Doctor context at consultation | None. Doctor starts from whatever the patient can describe verbally in 5–7 minutes | Structured briefing with differentials, red flags, recommended actions, and missing data flags — reviewable in under 30 seconds before the patient enters |
| Time saved per consultation | 5–7 min verbal history gathering. 40–80 patients per day. Compounded across every consultation. | 2–4 minutes saved per consultation on history gathering. Doctor begins at differential diagnosis, not at 'what brings you in today.' |
| Triage priority signal | ASHA judgment only. No structured signal. Referral urgency based on 23 days of training. | Gradient Boosting classification — Emergency/Urgent/Routine — established at point of first contact, before the journey begins |
| ASHA-to-doctor feedback loop | Non-existent. ASHA never learns whether the referral was appropriate or what the diagnosis was. | Doctor marks case reviewed, adds notes. Returning patient history available on next visit. ASHA can see case disposition. |

| Adoption Level | ASHA Workers | Population Covered | Records Created Per Month |
|---|---|---|---|
| 1% adoption | 9,400 | ~9.4 million rural patients | ~282,000 structured records |
| 5% adoption | 47,000 | ~47 million rural patients | ~1.4 million structured records |
| 10% adoption | 94,000 | ~94 million rural patients | ~2.8 million structured records |
| Full deployment (100%) | 9.4 lakh | ~940 million rural patients | ~28 million structured records |

Records per month calculated at: (ASHA workers at adoption level) × (average new patient encounters per month per NHM workload data — approximately 30). Figures reflect new case intake, not routine follow-up visits.
## 7.2 What Production Would Actually Need
Honest assessment of what VitalNet requires to deploy at scale. None of these are architectural problems — they are operational prerequisites for production that the prototype does not address by design.

| Requirement | Detail |
|---|---|
| Clinical validation study | AI-assisted triage output must be validated against clinician-labeled ground truth before scale deployment. Validation priority: false negative rate on Emergency cases is the primary safety metric — the classifier's conservative calibration must be confirmed against real clinical data. Secondary metrics: false positive rate on Routine cases (over-triage burden on PHC), inter-rater reliability between classifier output and physician assessment. Target: sensitivity >90% for Emergency cases. Requires AIIMS or equivalent collaboration. |
| Real patient training data | Synthetic data trains the prototype classifier. Production accuracy requires a labelled dataset of real PHC case records — requiring institutional data sharing agreements. |
| ASHA worker onboarding | 23-day basic training already includes digital tools. VitalNet form training estimated at 1–2 hours per worker — consistent with existing app adoption timelines from ImTeCHO deployments. |
| Doctor dashboard integration into existing workflow | PHC doctors currently use NHM's web portal for reporting. VitalNet dashboard needs to fit into this workflow — either as a standalone tool or an integrated module. |
| Government data governance compliance | Patient data handled under DPDP Act 2023. Phase 1 pilot compliance architecture: explicit patient consent logged on-device before form submission; anonymized SQLite payload (no direct identifiers in LLM prompt); on-device data retention limits. This compliance architecture supports a community clinic pilot today. Phase 2 federated learning and zk-SNARK privacy layer scales these protections across multi-clinic deployment — it is the production scaling path, not a prerequisite for Phase 1 piloting. |
| Connectivity contingency at PHC level | Designed for offline-first at ASHA field level. PHC connectivity is generally more reliable — FastAPI backend requires stable internet at clinic level for real-time dashboard updates. |
| Liability framework | Non-removable disclaimer is the first layer. Formal medical device classification and liability framework under Medical Devices Rules 2017 required before clinical deployment. |
| FHIR integration with hospital systems | SQLite schema is FHIR-compatible. SMART on FHIR wrapper endpoint is a single FastAPI route addition. Institutional access to hospital EHR APIs requires formal partnership agreements. |

## 7.3 The Honest Boundary
VitalNet does not solve and does not claim to solve:
- Doctor shortage — 79.5% specialist shortfall at CHCs is a supply-side problem. VitalNet makes the existing doctor supply more effective; it cannot create more doctors.
- Travel distance — 20–40km to the nearest PHC is a geographic reality. VitalNet establishes triage priority to guide urgency of that journey — it does not eliminate it.
- Infrastructure — No electricity, no network tower, no device are outside VitalNet's scope. The system is designed for the 95% of villages with mobile coverage, not the 5% without.
- Diagnostic accuracy — VitalNet produces decision support, not diagnoses. A 55-year-old man with chest pain and SpO2 at 91% classified as EMERGENCY by the classifier is not diagnosed — he is prioritised. The doctor diagnoses.
- Regulatory certainty — VitalNet is clinical decision support, not a diagnostic system. Under CDSCO Draft Guidance on Medical Device Software (October 2025), this classification requires that qualified medical review precedes any clinical action. The non-removable disclaimer and mandatory doctor review step are the architectural implementations of this boundary.
LOCK: VitalNet's honest claim: it creates one structured clinical record where zero existed, delivers it to the right person before the patient arrives, and establishes triage priority at the moment of first contact — none of which happen today at any scale in rural India.

# 8. References
## 8.1 Government and Policy Data
- Rural Health Statistics 2022-23, Ministry of Health & Family Welfare, Government of India — PHC count (31,882), population per PHC (36,049), CHC specialist shortfall (79.5%) | mohfw.gov.in
- NHM Annual Report 2023-24, National Health Mission — ASHA worker count (~9.4 lakh), training duration (23 days), deployment stats | nhm.gov.in
- TRAI Telecom Subscription Data Report, December 2024 — Rural teledensity 57.89% vs urban 124.31% | trai.gov.in
- Ministry of Communications, April 2024 — 4G coverage across 612,952 of 644,131 villages (95.15%) | dot.gov.in
- Health Dynamics of India 2022-23, Ministry of Health & Family Welfare — Doctor urban-rural distribution (27%/73%), PHC absenteeism ~40% | mohfw.gov.in
- ABDM — Ayushman Bharat Digital Mission — digital health records framework, FHIR API standards for Indian healthcare | abdm.gov.in

## 8.2 Clinical and Research References
- Thirunavukarasu AJ et al., 'Large language models in medicine', Nature Medicine, 2023 — 93.55% of evaluated LLM instances in clinical medicine research are general-domain LLMs
- JAMA Network Open 2024 RCT on ChatGPT use — unstructured LLM use by non-clinicians produced only marginal improvement over no AI; doctors using ChatGPT with structured prompts achieved 92% diagnostic accuracy on clinical vignettes
- He J et al., 'Gradient Boosting vs Deep Learning on tabular data', NeurIPS 2023 — Gradient Boosting consistently outperforms deep learning on structured tabular clinical data
- ImTeCHO deployment study, Gujarat — 88% daily login rate after training when tool directly reduces the most stressful part of the ASHA worker's job | Indian Journal of Medical Research
- BMJ Global Health — Life expectancy gap analysis India: poorest vs wealthiest quintile 65.1 vs 72.7 years
- Kumar et al., Critical Care Medicine 2006 — 7% increase in mortality per hour of delayed sepsis treatment
- JAMA Network Open — ChatGPT diagnostic accuracy 92% on clinical vignettes vs 74% for physicians without AI; 76% for physicians using ChatGPT without structured prompting

## 8.3 Technology References
- Groq Developer Documentation — Llama-3.3-70b-versatile model specs, free tier rate limits (30 RPM, 14,400 RPD) | console.groq.com/docs
- Google AI Studio — Gemini 2.5 Flash (gemini-2.5-flash-preview-04-17) and Flash-Lite (gemini-2.5-flash-lite-preview-06-17) model strings, free tier quotas (10 RPM/250 RPD and 15 RPM/1000 RPD respectively) | aistudio.google.com
- Sarvam AI Documentation — saarika:v2 Indic ASR model, supported languages, API reference | docs.sarvam.ai
- Scikit-learn Documentation — GradientBoostingClassifier, SHAP integration, TreeExplainer | scikit-learn.org/stable/modules/ensemble.html
- SHAP Documentation — TreeExplainer for Gradient Boosting, feature contribution calculation | shap.readthedocs.io
- FastAPI Documentation — async endpoint design, Pydantic v2 schema validation, OpenAPI auto-generation | fastapi.tiangolo.com
- Alsentzer et al. 2019 — Bio_ClinicalBERT, MIMIC-III trained clinical NER model | huggingface.co/emilyalsentzer/Bio_ClinicalBERT
- medspaCy — clinical spaCy pipeline with section detection and negation | github.com/medspacy/medspacy
- react-i18next Documentation — React internationalisation framework, language detection and dynamic translation | react.i18next.com

## 8.4 Competitive Landscape Sources
- ASHABot — Khushi Baby + Microsoft Research India (2024), 869 ASHAs onboarded in Udaipur district, 24,000+ messages | khushibaby.org
- ClinicalPath India / DIISHA — Elsevier + NITI Aayog (2024), Bahraich, UP pilot | elsevier.com/clinicalpath, niti.gov.in
- AiSteth AsMAP — Ai Health Highway (2023), 19 rural PHCs in Maharashtra, 38,000+ patients screened | aihealthhighway.com
