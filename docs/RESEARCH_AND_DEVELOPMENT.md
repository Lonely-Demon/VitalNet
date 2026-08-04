# VitalNet — Research & Development Document

Architecture, Decision Rationale & Technical Analysis

| | |
|---|---|
| Document Type | R&D record — architecture, decisions, tradeoffs, rejected alternatives |
| Project Name | VitalNet — AI-Driven Rural Healthcare Intelligence |
| Domain | HealthTech / Clinical Decision Support / Rural Healthcare Infrastructure |
| Scope | Problem analysis, competitive landscape, architecture, stack decisions, feasibility, impact |
| Status | Living document — current state of a working system, not a proposal |

**Intent:** this document explains *why* VitalNet is built the way it is —
the problem it targets, the alternatives weighed at each decision point,
what was rejected and why, and what the system honestly does and does not
claim. It supersedes an earlier draft written for a hackathon submission;
that framing (build windows, demo risk, judging criteria) has been removed
entirely. Everything described below reflects the system as it exists
today, verified against the current source, not an aspirational roadmap.
For "what exists where," see `CODEBASE_MAP.md`; for the numbered decision
log, see `docs/DECISIONS.md`; for regulatory posture, see
`docs/CLINICAL_GOVERNANCE.md`.

---

# 1. Problem Statement

## 1.1 The Healthcare Reality

India's primary healthcare system is organised around a three-tier
structure: ASHA workers at the village level, Primary Health Centres (PHCs)
at the block level, and Community Health Centres (CHCs) at the sub-district
level.

An ASHA worker — Accredited Social Health Activist — is the first person a
rural patient sees when something goes wrong. She is not a doctor. She has
around 23 days of basic training, a government-issued Android smartphone,
and the trust of her community.

When she sees a patient, she observes symptoms, asks questions in her
regional language, makes a judgment call about referral, and writes a paper
slip. That paper slip — if it survives the journey — is the only clinical
information the receiving doctor will have.

When that patient arrives at the PHC, the doctor receives them with zero
prior context. The paper slip, if it survived, contains a few lines of
handwritten text. The doctor has no vitals, no symptom timeline, no prior
history, and no way to know what was missed or observed at first contact.
Every consultation starts from zero.

This is not a technology failure. It is a documentation failure that
technology can fix.

## 1.2 Quantified Problem Scale

Figures below are drawn from government primary data sources current as of
their publication date; they describe the structural shape of the problem,
not a live dashboard.

| Metric | Data Point | Source |
|---|---|---|
| Active ASHA workers, India | ~9.4 lakh | NHM Annual Report 2023–24 |
| Average training received | ~23 days total | NHM ASHA Training Modules |
| Population per ASHA worker | ~1,000 rural / ~700 tribal | NHM Guidelines |
| PHCs functioning, India | 31,882 | Rural Health Statistics 2022–23, MoHFW |
| Population per PHC | 36,049 average | Rural Health Statistics 2022–23 |
| CHC specialist shortfall | 79.5% overall | Rural Health Statistics 2022–23 |
| Rural wireless teledensity | 57.89% vs 124.31% urban | TRAI, December 2024 |
| Villages with 3G/4G coverage | 95.15% (612,952 of 644,131) | Ministry of Communications, April 2024 |
| Doctors in rural vs urban practice | 27% rural, 73% urban | Health Dynamics of India 2022–23 |
| PHC doctor absenteeism | ~40% on any given day | Health Dynamics of India 2022–23 |
| Out-of-pocket health expenditure | ~70% of per-capita health costs | PMC India Healthcare Review |
| Life expectancy gap (poorest vs wealthiest quintile) | 7.6 years (65.1 vs 72.7) | BMJ Global Health |

The life-expectancy gap reflects structural determinants outside VitalNet's
scope — poverty, nutrition, sanitation, infrastructure. VitalNet addresses
only the documentation-failure component, which is the piece fixable with
software.

## 1.3 The Gap Over Existing Solutions

Three tools occupy adjacent space in Indian rural-health AI. None does what
VitalNet does — the gap is a structural absence, not a missed opportunity.

| Tool | Developer | What It Does | Critical Gap |
|---|---|---|---|
| ASHABot | Khushi Baby + Microsoft Research India | WhatsApp chatbot answering ASHA-worker questions in Hindi/Hinglish/English via GPT-4, trained on public health manuals | No structured patient record. No triage. No doctor-facing output. Entirely ASHA-side. |
| ClinicalPath / DIISHA | Elsevier + NITI Aayog | AI clinical decision support surfacing guidelines from structured patient triggers | Output returns to the ASHA worker, not the doctor. No triage classification. Requires Elsevier licensing. |
| AiSteth (AsMAP) | Ai Health Highway | AI stethoscope detecting cardiac murmurs and valvular disorders, deployed across rural PHCs | Single-domain (cardiac only). Requires proprietary hardware. No structured clinical record created. |

Every existing tool owns one dimension of the problem and discards the
others: ASHABot owns intelligence but discards data and doctor output;
ClinicalPath owns structured intake but routes output back to the ASHA
worker; AiSteth owns a narrow structured signal but is hardware-locked and
single-domain. VitalNet connects all three — structured intake, ML/LLM
reasoning, and doctor-facing output — into one workflow.

## 1.4 The Root Cause — One Failure, Four Downstream Consequences

The documentation gap is not one of four problems; it is the root cause of
all four.

| Downstream Failure | What Goes Wrong | How the Documentation Gap Causes It |
|---|---|---|
| Assessment failure | No structured framework for non-routine conditions | No form guides data collection; knowledge gaps produce under-triage on cardiac, respiratory, and neonatal presentations |
| Documentation failure | A paper slip with name, age, complaint — no format, no retained record | Direct manifestation of the root cause — zero structured data survives the encounter |
| Travel delay | The patient doesn't know how urgently to travel | Without a triage signal, no urgency is communicated before the journey starts |
| Doctor starts blind | Every consultation starts from zero; several minutes per patient across dozens of patients a day | The doctor gets whatever the patient can describe verbally — no history, no vitals trend, no risk flags |

VitalNet does not solve travel distance, doctor shortage, or PHC
absenteeism — those are structural constraints. It solves the documentation
gap, the one failure of the four that software can actually fix.

## 1.5 India-Specific Context

**Connectivity.** 95.15% of India's villages have 3G/4G coverage
(Ministry of Communications, April 2024) — but that headline number
compresses three layers: *coverage* (a nearby tower exists), *subscription*
(rural teledensity is 57.89% — not everyone in a covered village is a
subscriber, and many ASHA workers pay for their own mobile data), and
*quality* (indoor/hilly/peak-hour connectivity is materially worse than
outdoor coverage figures suggest). VitalNet assumes intermittent 4G as the
baseline, not a constant connection — the entire architecture is
offline-first: triage classification runs identically online or fully
offline (§4.8), form data is queued locally, and sync happens on
reconnection.

**Device.** Government-issued Android smartphones distributed to ASHA
workers skew entry-level to mid-range — commonly 2–4 GB RAM. The intake
form and offline triage engine are built for this floor: large tap
targets, dropdown-first inputs, minimal free text, and — critically — no
native app install. It's a PWA reachable from a browser link, installable
if desired, and the offline inference path was deliberately re-architected
(§4.8) specifically to fit a 2 GB RAM device comfortably.

**Language.** Minimum ASHA-worker education is Class 10 (relaxed to Class 8
where unavailable); English literacy for medical terminology is not a safe
assumption. The intake form ships in English, Hindi, and Tamil today
(`react-i18next`, `frontend/src/locales/`), with the field labels in plain
language rather than clinical terms; more regional languages are an
infrastructure-ready addition (add a locale file), not an architecture
change. The doctor-facing briefing renders in English, consistent with PHC
clinical record norms — a separate, LLM-generated plain-language
restatement in the patient's own language is available on demand for the
patient/family (`generate_patient_summary`, see §4.2), without ever
re-deriving the triage decision.

**Incentive.** ASHA workers are compensated through Performance-Linked
Incentives tied to specific NHM-mandated deliverables — ANC registrations,
institutional deliveries, immunisations. Completing a VitalNet form for a
general sick-patient encounter is not currently a PLI item. This creates a
real adoption ceiling that UI design alone cannot remove — comparable
programmes (e.g. ImTeCHO) that achieved high daily-use rates did so with
MoHFW mandate integration, not UX alone. VitalNet's adoption pathway is
therefore two-phase: voluntary adoption where the tool visibly reduces
referral uncertainty and improves PHC feedback, followed by policy
integration where form completion is folded into NHM reporting and PLI
structures — a government-partnership decision, not a software one.

## 1.6 The Golden Hour Argument

For the conditions that kill fastest — cardiac events, stroke, sepsis — the
rural referral chain routinely consumes the entire golden window before a
qualified doctor makes a single informed decision.

| Condition | Golden Window | Typical Rural Referral Chain Time | Consequence of Delay |
|---|---|---|---|
| Cardiac arrest | 4–6 minutes | 30–60 min assessment + 1–3 hr transport | Brain death begins at minute 4 |
| Stroke | 60 minutes | 2–4 hours total, same chain | Every 30-minute delay costs roughly one additional year of disability |
| Sepsis | Ongoing — ~7% mortality increase per hour | Same chain | Untreated sepsis carries 30–50% mortality |

VitalNet does not eliminate travel time. It establishes triage priority at
the moment of first contact, before the patient begins the journey, so an
EMERGENCY case is treated as an emergency from the first interaction — not
from the moment the doctor finally lays eyes on the patient.

---

# 2. What VitalNet Is

## 2.1 Concept

VitalNet is a clinical intelligence bridge — software that sits between the
ASHA worker in the field and the PHC doctor at the clinic, translating an
observed patient encounter into a structured clinical briefing the doctor
can act on.

The governing principle is translation, not replacement. VitalNet speaks
the ASHA worker's language on one side — a simple, regional-language form
on an Android device — and the doctor's language on the other — a
structured clinical card with triage priority, differentials, red flags,
and recommended actions.

*"An ASHA worker describes a patient. A doctor anywhere receives a
structured clinical briefing they can act on — before the patient travels
to the clinic."*

That is the benchmark every architectural decision in this document is
measured against.

## 2.2 The Five-Layer Vision vs. What Exists Today

VitalNet's original vision describes five layers. This is where each one
actually stands.

| Layer | What It Does | Status | Why |
|---|---|---|---|
| **AI Diagnostic Layer** | Multilingual intake, triage classification, LLM briefing, doctor dashboard | **BUILT — this is the whole system today** | Requires no dedicated hardware, proves the intelligence-bridge concept end to end, and is the only layer with no external prerequisite |
| Edge Layer | ESP32 wearables, local sensor inference, offline vitals capture | Not started | Requires hardware outside this project's current scope; manual vitals entry produces an identical data shape for the AI layer to consume — the schema is already wearable-ready |
| Privacy Layer | Federated learning, zk-SNARKs, DID-Comm | Not started | Meaningful only once there's a fleet of devices and real patient data to protect across them; wraps around a working intelligence layer rather than gating it |
| Cloud Layer | Message queues, container orchestration, multi-region deployment | Not started at that scale; current deployment (Railway + Vercel, §5.7) is adequate for the actual traffic this system sees | Infrastructure that scales a service that must exist first — the FastAPI backend is already the service such infrastructure would sit in front of |
| Workflow Layer | Facility workflow automation, bed management, assignment | **Partially built** — doctor dashboard, referral workflow, and self-reported facility capacity all exist | Full bed-management automation needs integration with systems this project doesn't control (hospital information systems) |

The decision to build the AI Diagnostic Layer first, and to make it as
complete as it is today rather than a thin proof of concept, was
deliberate: every other layer either feeds this one or distributes its
output, so none of them are useful without it working first.

## 2.3 Why the AI Layer, Specifically

| Evaluation Factor | AI Layer | Edge Layer | Privacy Layer | Cloud Layer | Workflow Layer |
|---|---|---|---|---|---|
| No hardware dependency | Yes | No | Yes | Yes | Yes |
| Directly targets the root cause (§1.4) | Yes | Partial | No | No | Partial |
| Usable standalone, no other layer required | Yes | No | No | No | No |
| Produces a working, demonstrable system today | Yes | No | Partial | Partial | Partial |

- **Edge Layer** rejected as the first slice: ESP32/BLE sensor integration
  is a hardware-integration project in its own right, and manual vitals
  entry already produces the exact data shape the AI layer needs — nothing
  about the intelligence layer is blocked on it.
- **Privacy Layer** rejected as first: federated learning needs a fleet of
  devices to train across; zk-SNARK proof generation is computationally
  heavy for no benefit until there's real patient data flowing to protect.
- **Cloud Layer** rejected as first: message queues and container
  orchestration scale a service that has to exist and be worth scaling
  first.
- **Workflow Layer** rejected as the *primary* slice: a facility-assignment
  dashboard with no real triage data behind it is a table of names. (Parts
  of it — the doctor dashboard, referrals, capacity signalling — were built
  once the triage/briefing pipeline existed to feed them.)

## 2.4 Current End-to-End Flow

| Step | Action | Technical Implementation | Output |
|---|---|---|---|
| 1 | ASHA input | React 19 PWA form — dropdowns, symptom checklist, vitals fields, voice input. Consent capture is mandatory and enforced server-side, not just in the UI. | Structured `IntakeForm` payload |
| 2 | Input structuring | FastAPI + Pydantic v2 — every field bounded (ranges, enums, max lengths), free text control-character-stripped, symptoms allow-listed | Validated clinical JSON |
| 3 | Feature engineering | `ClinicalFeatureEngineer` expands ~14 raw fields into 43 engineered clinical features (vital-derived scores, symptom-interaction clusters, age-specific adjustments, seasonal/geographic context — §4.2) | 43-dimensional feature vector |
| 4 | Deterministic safety net | Unambiguous extreme presentations (critically low SpO2, extreme HR/BP/temp, neonatal fever, always-critical symptoms) are force-escalated to EMERGENCY *before* the model runs, independent of it | Immediate EMERGENCY where applicable, with a stated deterministic reason |
| 5 | Risk classification | A single `HistGradientBoostingClassifier`, trained once and run identically online (Python) and offline (pure-JS tree evaluator) — no case can classify differently depending on connectivity | `ROUTINE` / `URGENT` / `EMERGENCY` + confidence + a `low_confidence` abstention flag |
| 6 | NEWS2 concerning-vital floor | A milder deterministic rule: any single vital in the NEWS2 "concerning" band can never be left as ROUTINE — floors to URGENT | Guards the model against under-triage on a class of ambiguous-but-concerning vitals |
| 7 | Explain the rationale | Real SHAP `TreeExplainer` attributions on the model's own prediction, translated into plain clinical language | A stated primary risk driver, not a black box |
| 8 | Generate the briefing | 4-tier LLM fallback (Groq Llama-3.3-70B → Groq Llama-3.1-8B → Gemini 2.5 Flash → Gemini 2.5 Flash-Lite), JSON-schema-locked output; the triage tier and disclaimer are hard-enforced server-side and cannot be altered by the LLM under any tier | Structured briefing: differentials, red flags, recommended actions, uncertainty flags |
| 9 | Persist | Supabase/PostgreSQL, Row-Level Security enforced per role, audit-logged | Timestamped, RLS-protected case record |
| 10 | Doctor dashboard | React, real-time (Supabase Realtime) priority queue — EMERGENCY first, then URGENT, then ROUTINE; briefing card; review/override/outcome actions | Doctor sees a structured briefing, typically within a couple of seconds of submission |
| 11 | Notification | EMERGENCY cases fire a Web Push notification to subscribed doctors at the facility as a background task; if the ASHA worker is offline, a one-tap native SMS/`tel:` intent lets them alert the facility over cellular voice/SMS, which needs no data connection at all | The facility is alerted before or as the patient begins travelling |

## 2.5 Why Not Just Give the ASHA Worker a Phone and an LLM

The question sounds dismissive but deserves a real answer: if a
general-purpose LLM can reach strong accuracy on clinical vignettes, why
not simply give every ASHA worker direct access to it?

| Dimension | ASHA Worker + Raw LLM | VitalNet |
|---|---|---|
| Input quality | Whatever the user types — vague, incomplete, in whatever language the model happens to handle well | Structured clinical JSON via a bounded form — a consistent minimum shape every time |
| Output recipient | Returns to the ASHA worker, who has ~23 days of clinical training and no way to evaluate a differential diagnosis | Routes to the doctor — the person actually trained to verify, override, and act |
| Record persistence | Ephemeral — the conversation ends, nothing is stored | Every submission writes a structured, timestamped, RLS-protected case record |
| Triage independence | The LLM's own confidence, generated fresh each call — hallucination risk on a safety-critical output | Triage comes from the deterministic classifier + safety net + NEWS2 floor, entirely independent of any LLM call, and works with zero connectivity |
| Context design | Requires literacy in the model's strongest language and the judgment to evaluate its answer | Regional-language form, offline-resilient, requires no clinical knowledge to fill in, and the ASHA worker never has to evaluate model output at all |

**The core resolution:** a raw LLM gives an ASHA worker an answer she
cannot evaluate. VitalNet gives a doctor a briefing she can act on. This
closes what can be called the *expert–novice gap* in clinical AI — the
person with access to the model lacks the expertise to use it safely, and
the person with the expertise lacks access at the point of first contact.
VitalNet routes the AI's output to the expert instead of trying to train
the novice to use it (expanded in §4.6).

## 2.6 What This Unlocks for Future Layers

| Future Layer | Why It's Currently Blocked | What Today's Schema Already Unlocks |
|---|---|---|
| Edge Layer (wearables) | No structured target existed to write sensor data into | The clinical JSON schema is the exact target — BP/SpO2/HR from a wearable populate the same fields a worker enters manually today |
| Privacy Layer (federated learning, zk-SNARKs) | No real patient data flow existed to protect | Every submission is now a structured, schema-consistent, RLS-protected record — the substrate federated learning trains across and zk-SNARKs would prove properties over |
| Predictive analytics / outcome learning | Needs longitudinal data — multiple records per patient over time | The doctor triage-override + outcome-recording endpoints, and the new patient-continuity key (§4.7), already create exactly this longitudinal shape |
| Cloud Layer (queues, orchestration) | Needs a service worth scaling first | The FastAPI backend is that service; swapping in a message queue in front of it is a deployment change, not a rebuild |
| Workflow automation | Needs to know patient priority before automating around it | Triage tier + facility capacity + open-case-count are exactly the signals a workflow-automation layer would consume — the referral system already uses them today (§4.7) |

## 2.7 Prompt Design and a Real Sample Output

**Three-layer prompt architecture**, unchanged in principle from the
original design and now fully implemented in `app/services/llm.py` and
`prompts/clinical_system_prompt.txt`:

- **Layer 1 — system prompt (fixed):** role, output-schema rules,
  uncertainty-handling instructions, and an explicit instruction that the
  model may not restate or contradict the triage tier it's given.
- **Layer 2 — patient context (dynamic):** the structured intake fields —
  demographics, vitals, symptom checklist, free-text observations
  (sanitised before entering the prompt to resist injection).
- **Layer 3 — output schema (structured JSON):** `triage_level` (passed in
  as already-decided, locked context — never a field the model fills in),
  `primary_risk_driver`, `differential_diagnoses`, `red_flags`,
  `recommended_immediate_actions`, `recommended_tests`,
  `uncertainty_flags`, `disclaimer`.

**A real (illustrative) output shape** — a 55-year-old male, chest
tightness and breathlessness for two hours, BP 160/100, HR 98, SpO2 91%:

```json
{
  "triage_level": "EMERGENCY",
  "primary_risk_driver": "Chest tightness combined with elevated BP and SpO2 at 91% in a male over 50 — possible acute cardiac event",
  "differential_diagnoses": ["Acute coronary syndrome", "Hypertensive urgency", "Pulmonary embolism"],
  "red_flags": ["SpO2 below 94%", "Systolic BP above 160 in a symptomatic patient"],
  "recommended_immediate_actions": ["ECG if available", "Oxygen supplementation", "Urgent PHC transfer"],
  "recommended_tests": ["Troponin", "Chest X-ray"],
  "uncertainty_flags": "No prior cardiac history recorded — risk may be higher than presented",
  "disclaimer": "AI-generated clinical decision support. Requires qualified medical review before action."
}
```

Two things about this output are structural, not stylistic: `triage_level`
is never generated by the LLM (it's echoed from the classifier's already-
final decision, and `_enforce_schema()` overwrites it server-side even if a
tier tries to say otherwise), and `disclaimer` is likewise hard-locked, not
merely requested. JSON — rather than prose — is the output format
specifically because each field maps directly to a doctor-briefing-card UI
component and needs to be independently verifiable and consistently
parseable; prose cannot be reliably mapped to UI state.

## 2.8 Fallback Resilience Map

No single external dependency failure should silently degrade to nothing —
every path has a defined fallback, down to a deterministic floor.

| Component | Primary Path | Fallback Chain | User-Visible Impact |
|---|---|---|---|
| LLM briefing | Groq Llama-3.3-70B | Groq Llama-3.1-8B → Gemini 2.5 Flash → Gemini 2.5 Flash-Lite | Slight latency increase at worst; the triage tier is never affected because it never came from the LLM in the first place |
| Voice transcription | Groq Whisper (`whisper-large-v3-turbo`) | Sarvam AI (`saaras:v3`), only if Groq is unconfigured or a request to it fails | See §5.5 for why the ordering is Groq-first, not Sarvam-first |
| Triage classification | Trained model (online: Python; offline: pure-JS tree evaluator) | A rules-only fallback if the tree data itself fails to load — the deterministic safety net and NEWS2 floor still run | Triage is *never allowed to fail outright* — see §4.8 |
| Malformed LLM JSON | Direct JSON parse | `json-repair` library repairs near-miss JSON before falling back to the next model tier | Briefing degrades gracefully instead of surfacing a raw parse error |
| Database write | Supabase/PostgreSQL, online | Client-side offline queue (IndexedDB), synced on reconnection via an idempotent `client_id` upsert | "Saved offline" banner; no data loss, no duplicate rows on retry |
| Internet connectivity | Full pipeline, all calls live | Offline: pure-JS triage runs locally, form queues locally, one-tap native SMS/`tel:` alert available immediately for EMERGENCY cases (no data connection needed) | Triage is available immediately regardless of connectivity; only the LLM briefing and doctor notification wait for reconnection |

---

# 3. Competitive Landscape

## 3.1 Market Context

The Indian rural-health AI space is nascent but not empty. A small number
of well-resourced tools already exist in adjacent territory. None does what
VitalNet does — the absence is structural, not a gap nobody noticed.

## 3.2 Detailed Competitive Analysis

**ASHABot — Khushi Baby + Microsoft Research India**

| Dimension | Assessment |
|---|---|
| What it does well | Answers ASHA-worker questions in regional language via WhatsApp; validates that ASHA workers will use LLM tools in their own language on a channel they already use |
| Structured patient records | None — every conversation is ephemeral |
| Triage classification | None — it answers questions, it doesn't assess patient risk |
| Doctor-facing output | None — the loop never reaches the doctor |
| VitalNet relationship | Complementary, not competing: ASHABot validates ASHA-worker LLM adoption; VitalNet builds the structured clinical workflow that's missing around it. VitalNet's own protocol/guideline assistant (built directly informed by ASHABot's published design and its own honestly-reported limitation — see §3.3) now covers ASHABot's core use case too, persisting every Q&A as a growing, structured, RLS-protected facility FAQ instead of an ephemeral chat, and replacing ASHABot's ~60h-average synchronous multi-reviewer consensus with async curation. |

**ClinicalPath / DIISHA — Elsevier + NITI Aayog**

| Dimension | Assessment |
|---|---|
| What it does well | Structured intake at point of contact; surfaces Elsevier clinical guidelines based on patient triggers; government-backed pilot |
| Output recipient | The ASHA worker — guidelines return to the person who triggered the query, not the doctor who needs to act |
| Doctor-facing structured briefing | None — no triage badge, no differential list, no red flags formatted for a time-constrained doctor |
| Deployment model | Requires Elsevier licensing and an active government partnership — not open infrastructure |
| VitalNet relationship | ClinicalPath proves structured data collection is solvable; VitalNet solves the output-routing problem it doesn't address |

**AiSteth (AsMAP) — Ai Health Highway**

| Dimension | Assessment |
|---|---|
| What it does well | AI-assisted cardiac/respiratory signal detection deployed across rural PHCs, proven in resource-constrained settings |
| Domain coverage | Cardiac and respiratory only — a rural presentation could equally be neurological, obstetric, or septic |
| Hardware dependency | Requires a proprietary device — exactly the settings where the problem is worst are the ones least able to procure/maintain specialised hardware |
| Structured clinical record | Identifies a flag, not a longitudinal record tied to a patient identity across visits |
| VitalNet relationship | A different problem: AiSteth detects a narrow signal, VitalNet creates a structured record and routes it — potentially complementary in a future integrated stack |

## 3.3 Four Failure Patterns VitalNet Avoids

| Failure Pattern | Which Tool | What Goes Wrong | VitalNet's Answer |
|---|---|---|---|
| Ephemeral output | ASHABot | Nothing survives the interaction | Every interaction writes a structured, timestamped, RLS-protected case record — the database write is the primary output, not an afterthought. VitalNet's own protocol assistant (§6.1) applies the same principle to ASHABot's own use case: every Q&A persists into a shared, growing facility FAQ rather than disappearing after the chat. |
| Wrong recipient | ClinicalPath / DIISHA | Output returns to the person least equipped to evaluate it | Output routes to the doctor; the ASHA worker is the data collector, not the evaluator |
| Hardware lock-in | AiSteth | A resource-constrained setting can't access the tool at all | Runs on hardware already in the field — a standard Android smartphone, no procurement dependency |
| Domain narrowness | AiSteth, ClinicalPath | Optimised for one condition class, blind to the rest | General-purpose reasoning across all presentations, backed by a deterministic safety net that doesn't care which domain the emergency is in |

## 3.4 Why No Direct Equivalent Exists

Building VitalNet's specific slice requires combining three capabilities
usually developed in isolation: structured intake at first contact (the
data layer), ML/LLM clinical reasoning (the intelligence layer), and
doctor-facing structured output (the communication layer).

| Tool | Data Layer | Intelligence Layer | Doctor Output Layer |
|---|---|---|---|
| ASHABot | Ephemeral | LLM reasoning | Returns to ASHA worker |
| ClinicalPath | Structured intake | Guideline retrieval | Returns to ASHA worker |
| AiSteth | Partial (audio signal) | Partial (pattern match) | Partial (cardiac flag only) |
| VitalNet | Structured, RLS-protected JSON record | ML classifier + SHAP + LLM briefing | Structured doctor briefing card |

Every existing tool owns exactly one of these layers — not because the
combination was missed, but because each organisation approached the
problem from its own domain expertise (conversational AI, clinical
guidelines, medical devices) rather than as one connected infrastructure
problem.

---

# 4. AI Layer Design — Analysis & Rationale

## 4.1 General-Purpose LLM vs. a Medical-Specific Model

**Decision:** what model class to use for clinical-briefing reasoning.

| Evaluation Factor | Medical-Specific Model | General-Purpose LLM |
|---|---|---|
| Task match | Optimised for clinical-knowledge retrieval | Optimised for instruction-following and cross-domain reasoning over *observed* patient data — the actual task here |
| Instruction following / JSON schema enforcement | Inconsistent, not trained for strict schema output | A native strength — required for the locked-schema briefing design |
| Uncertainty handling | Tends toward confident output even on sparse data | Can be explicitly instructed to flag missing information rather than estimate around it |
| API availability at this scale | Enterprise-only access for the strongest clinical models, or no hosted inference at all | Groq offers fast, cost-effective hosted inference for exactly this class of task |
| Research grounding | — | The literature on general-domain LLMs applied to clinical reasoning tasks (rather than knowledge recall) supports this choice — e.g. Thirunavukarasu et al., *Nature Medicine* 2023 |

**Decision:** a general-purpose LLM, used for reasoning over already-
structured patient data rather than for clinical-fact recall. The triage
decision itself is never delegated to it (§4.2) — the LLM's job is to
explain and contextualise a decision that's already been made
deterministically.

## 4.2 The Triage Classifier — Current Architecture

The most safety-critical decision in the system is how triage level is
determined. This has been revisited and substantially hardened since the
original prototype; the current design is stricter than "one ML model
decides."

**One unified model, not two divergent ones.** An early iteration of this
project trained separate models for the online (Python/backend) and
offline (browser) paths — which meant the same patient could, in
principle, get a different triage tier depending on connectivity. That was
a real, identified clinical-safety inconsistency. The fix: **exactly one**
`sklearn.ensemble.HistGradientBoostingClassifier` is trained once
(`scripts/train_classifier.py`) and exported to both runtimes from the same
artifact — the backend loads the `.pkl`, the browser evaluates a compact,
dependency-free JSON tree representation in pure JavaScript. A golden-vector
parity test (`npm run test:parity`, CI-enforced) asserts the two produce
identical classifications on every held-out sample. Online and offline
triage cannot silently diverge.

**Why `HistGradientBoostingClassifier` specifically:**

| Criterion | LLM Classification | Rule-Based Thresholds | Gradient-Boosted Trees (selected) |
|---|---|---|---|
| Hallucination risk on the triage decision | High — a language model can produce an inconsistent tier on the same input across calls | Zero — deterministic | Zero — a trained model with fixed, inspectable weights |
| Captures multiplicative vital interactions | Not built for structured tabular input | Limited — AND/OR rules don't capture interaction effects | Strong — boosted trees learn interactions between BP, SpO2, HR, age natively |
| Explainability | Prose, hard to verify the source | Direct but crude | Real per-prediction SHAP feature attributions |
| Works with zero connectivity | No — needs an API | Yes | Yes — the same model runs as a dependency-free JS tree walker offline |
| Exportability to a lightweight browser runtime | N/A | N/A | Natively exportable to ONNX and, from there, to a compact tree-JSON structure a ~120-line JS evaluator can walk — no heavy runtime needed (below) |

**Three deterministic layers wrap every prediction**, in order:

1. **Safety net** (`_safety_net_check`) — force-escalates unambiguous
   extreme presentations (critically low SpO2, extreme heart rate or
   blood pressure, extreme temperature, neonatal fever, a hypertensive-
   crisis-plus-neurological-symptom combination, or any of a fixed set of
   always-critical symptoms) straight to EMERGENCY, independent of the
   trained model. This guarantees these specific cases are never missed
   regardless of any residual model error.
2. **The trained model** — for the nuanced, multi-factor cases that don't
   hit an unambiguous threshold.
3. **NEWS2 concerning-vital floor** (`_news2_concerning_vital`) — a milder
   deterministic rule: any single vital scoring ≥2 on a NEWS2-style scale
   (concerning but not extreme) can never be left as ROUTINE; it floors to
   URGENT. This closes a real gap the safety net alone doesn't cover.

**Abstention, not false confidence.** A `low_confidence` flag is raised
when the top-class probability is below a tuned threshold or the top-two
margin is narrow, surfaced to the doctor as "model uncertain — clinician
review recommended." This is deliberately conservative rather than
optimised purely for accuracy.

**Calibration, validated against two distributions.** Expected Calibration
Error is reported both on the class-balanced training/test split (needed
to learn the rare EMERGENCY class well) *and*, separately, on a
realistic ~85% ROUTINE / 12% URGENT / 3% EMERGENCY prevalence subsampled
from the same held-out set — because a model well-calibrated on a balanced
split is not automatically well-calibrated against the skewed prevalence
it will actually see in the field. Both numbers are reported in
`backend/app/ml/MODEL_CARD.md`, not just the flattering one.

**43 engineered clinical features, not 45 — and that's a fix, not a
regression.** A direct audit of the trained model found that two of the
original contextual features (`time_of_day_risk`, a hardcoded
`epidemic_alert_level` placeholder) were *provably constant* across the
entire synthetic training set — training data is generated in a single
script run, so every example got an identical value, and a gradient-
boosted tree cannot learn a split on a constant feature. Those two
features had **zero** influence on any prediction, ever, despite being
computed on every request. They were removed. The remaining two contextual
features that stood in for real-world signal — `seasonal_risk` and
`geographic_risk` — were rebuilt as genuine, learnable signals: the
training generator now samples a reference month per synthetic patient and
correlates India's monsoon season (June–September) with rural/tribal
location to produce a real dengue/malaria-like symptom-probability bump,
so the model has actual variance and a real label correlation to learn
from, not a placeholder. Full accounting: `docs/DECISIONS.md` §23.

**Monotonic constraints — investigated, verified infeasible, not forced.**
Several engineered features are constructed as unambiguous "higher = worse"
scores (shock index, sepsis-risk score, hemodynamic-instability score).
Constraining the model to respect that monotonically would make its
behaviour in sparse or out-of-distribution feature space *provably* safe
rather than merely probable — a meaningful safety property for a clinical
model, and one worth pursuing. It was verified directly, not assumed, that
the pinned scikit-learn version's `HistGradientBoostingClassifier` does not
support monotonic constraints for a multiclass (3-class) problem. Rather
than force an unplanned scikit-learn upgrade to get this, it's documented
as a known limitation and a candidate for a future pass once the pin
moves — an example of the project's stated preference for honest gaps
over overclaimed guarantees.

## 4.3 Prompt Engineering Strategy

| Design Decision | Options Considered | Decision & Reasoning |
|---|---|---|
| Temperature | 0.0 (fully deterministic) vs. 0.1–0.2 | 0.1–0.2. Fully deterministic sampling produces repetitive, formulaic phrasing on varied clinical input; a small amount of temperature keeps output natural while the *decision content* stays governed by the locked schema, not by sampling |
| Output format | Free prose vs. strict JSON schema | Strict JSON — each field maps directly to a doctor-briefing-card UI component and must be independently verifiable; prose cannot be reliably mapped to UI state |
| Triage level in the prompt | Ask the LLM to confirm/override vs. pass as locked context | Passed as already-decided context; the LLM may not contradict it, and the server enforces this after the fact (`_enforce_schema`) regardless of what a given call returns |
| Uncertainty handling | Trust the model's self-reported confidence vs. a required field | A required `uncertainty_flags` field — the model must state what's missing, not silently estimate around it |
| Few-shot examples | Zero-shot vs. 2–3 worked examples in the prompt | Zero-shot with an explicit schema — few-shot examples risk biasing the model toward the example case types |

## 4.4 LLM Failure Modes and Mitigations

| Failure Mode | How It Manifests | Mitigation |
|---|---|---|
| Hallucinated diagnosis | A confident differential not supported by the presented vitals | The triage tier is never LLM-derived; the doctor sees the raw intake data alongside the briefing for verification |
| Dangerous triage override attempt | A tier suggests "stable" when the classifier returned EMERGENCY | `_enforce_schema()` overwrites `triage_level` and `disclaimer` from the already-decided values regardless of what any tier returns |
| Malformed / partial JSON | A tier returns broken or truncated JSON | `json-repair` attempts a repair first; on genuine failure, falls through to the next tier in the 4-tier chain |
| Verbose, non-actionable output | Paragraphs of caveats instead of a structured card | The system prompt explicitly constrains output to the schema, with per-field limits |
| Rate limit / timeout | A provider returns 429 or times out | 4-tier fallback (Groq 70B → Groq 8B → Gemini Flash → Gemini Flash-Lite) — each tier is an independent API/infrastructure provider |
| Over-confidence on sparse input | Only age and chief complaint given, full differential generated anyway | `uncertainty_flags` is a required field; the system prompt explicitly instructs the model to state what's missing rather than estimate |

## 4.5 Guardrails Architecture

Safety here is a layered system of independent checks, not one feature.
This list is materially larger than the original five-guardrail design —
security and governance hardening added real, load-bearing layers beyond
what the first prototype had.

| # | Guardrail | What It Prevents |
|---|---|---|
| 1 | Bounded input validation (Pydantic, every field ranged/enum/length-limited) | Malformed or absurd input entering the clinical pipeline |
| 2 | Deterministic safety net + NEWS2 floor, LLM-independent | Under-triage on unambiguous or concerning presentations, regardless of any residual ML/LLM error |
| 3 | Hard-enforced triage tier and disclaimer (`_enforce_schema`) | A hallucinated or malformed LLM response ever changing the clinical decision |
| 4 | Mandatory `uncertainty_flags` / `low_confidence` abstention | False confidence — a doctor acting on incomplete or ambiguous information believing it's complete |
| 5 | Non-removable, LLM-uncontrollable disclaimer | Treating decision support as a diagnosis |
| 6 | Human-in-the-loop by design | A doctor reviews every case; ML/LLM output is never the final actor |
| 7 | Row-Level Security on every table, per role | Cross-tenant/cross-facility data exposure at the database layer, independent of application bugs |
| 8 | Rate limiting, CSRF + device-header guard, security response headers | Abuse of the API surface and a class of cross-origin attacks |
| 9 | PHI-scoped audit logging on every create/read/update | Undetected unauthorised access; a reconstructable record of who touched what |
| 10 | Contraindication flags (advisory, deterministic keyword rules — not an ML judgment) | A subset of dangerous medication/condition combinations going unnoticed, without pretending to be a full drug-interaction database |
| 11 | Cross-visit deterioration alert (§4.7) | A repeated severe presentation from the same patient being treated as an isolated, unremarkable visit |

Full detail on 1–6 lives in `backend/app/ml/MODEL_CARD.md`; on 7–9 in
`docs/SECURITY.md`; on regulatory framing for all of this, see
`docs/CLINICAL_GOVERNANCE.md`.

## 4.6 Resolving the Expert–Novice Gap

The hardest adoption problem in AI-assisted healthcare isn't technical — it's
that the person with access to the AI (the ASHA worker) usually lacks the
clinical training to evaluate its output, while the person with that
training (the doctor) usually lacks access at the point of first contact.

| Approach | Typical Model (ASHABot / ClinicalPath-style) | VitalNet |
|---|---|---|
| Who sees AI output | The ASHA worker | The PHC doctor |
| Can the recipient evaluate it? | Not reliably — no training to assess a differential or catch a hallucinated claim | Yes — trained to verify, override, and act, and can cross-check against the raw intake data |
| ASHA worker's role | Interpret AI guidance and decide what to do with it | Collect structured data — that is the entire role |
| Clinical training required to use the system | Effectively required, informally | None — the intake form is a checklist; the ASHA worker never sees model output at all |

VitalNet resolves this not by training the ASHA worker to use AI safely,
but by designing a system where she never has to.

## 4.7 Cross-Visit Continuity (New Since the Original Design)

Two capabilities that didn't exist in the original architecture close a
real gap: recognising a *returning* patient, and noticing a *pattern*
across their visits.

**Patient continuity key.** An opaque, offline-generated `XXXX-XXXX` code
(unambiguous alphabet, excludes visually similar characters), generated
entirely client-side via `crypto.getRandomValues` — no centralised patient
registry, no server round-trip needed even for a brand-new patient's first
visit. Shown as a QR code plus plain text after a first visit; a returning
patient's worker enters the code back in, and a lookup endpoint surfaces
prior visits, scoped by the same per-role visibility every other case view
already enforces.

**Cross-visit deterioration alert.** When a submitted case's continuity key
has had two or more URGENT/EMERGENCY visits (the current one included)
within a trailing seven-day window, the case is flagged and forced into
mandatory review — a repeated severe presentation is worth a clinician's
attention even if today's individual reading looks unremarkable on its
own. Computing this needs authoritative visibility across *all* prior
visits regardless of which worker saw the patient each time, which a
row-level-security-scoped ASHA-worker token structurally cannot provide on
its own — resolved with one narrow, explicitly documented, count-only
exception to the RLS boundary (never returning a row, only an aggregate;
see `docs/DECISIONS.md` §20 and §22 for the governing test applied to that
exception).

## 4.8 Offline-First Architecture — A Deeper Design Than "It Also Works Offline"

The device constraint from §1.5 (2–4 GB RAM Android devices) drove a real
architectural decision, not a footnote: **how** the same model runs in a
browser without a heavy runtime.

The model is a gradient-boosted tree ensemble: inference is a few thousand
`feature <= threshold` comparisons — computationally trivial. Three options
were weighed for the offline runtime:

| Option | Precache size | RAM footprint (2 GB device) | Cold start | Verdict |
|---|---|---|---|---|
| `onnxruntime-web` (WASM) | ~13 MB | Tight — a WASM compile spike risks the tab being killed under memory pressure | Slow — WASM compilation of a multi-MB module on old hardware | Rejected — heaviest and slowest by far for a model this small |
| Model-specific compiled WASM (m2cgen/Rust/C toolchain) | Tens–hundreds of KB | Comfortable | Small compile step remains | Rejected — adds toolchain complexity for no real speed benefit at this model size |
| **Compact JSON + a ~120-line dependency-free JS tree evaluator (selected)** | **~1 MB** | **Comfortable** | **Instant — JSON parse only, no WASM compile** | **Selected** |

The trained model is exported once to a compact JSON tree structure
(`scripts/tree_export.py`) and walked by a small, dependency-free JS
evaluator (`treeEvaluator.js`) — no `onnxruntime-web`, no WASM, ~100× less
precached data than the WASM path. A golden-vector parity test asserts the
JS path is argmax-identical to the server on every held-out sample, and the
same deterministic safety net + NEWS2 floor run on *every* offline
classification too — which is what makes "always return a triage, even for
inputs the model never saw" an actual guarantee rather than an aspiration:
if the tree data itself fails to load, a rules-only fallback still returns
a result. Triage never fails outright, online or off.

---

# 5. Tech Stack Decisions

## 5.0 Current Stack, Summarised

| Layer | Technology | Key Detail | Rationale (one line) |
|---|---|---|---|
| Frontend | React 19 + Vite 7, PWA | `vite-plugin-pwa`, service worker, offline queue, `react-i18next` (en/hi/ta) | Component model fits the form/dashboard complexity; installable PWA avoids app-store distribution friction |
| Backend | FastAPI (Python) | Pydantic v2, async, uvicorn | Native ML integration with zero bridge layer; async-first for variable-latency LLM calls over rural 4G |
| Database / Auth / Realtime | Supabase (PostgreSQL) | Row-Level Security on every table, Supabase Auth (JWT), Realtime subscriptions | One managed service covers persistence, auth, and live updates; RLS is a database-level backstop independent of application code |
| Triage classifier | `HistGradientBoostingClassifier` + real SHAP `TreeExplainer` | 43 engineered features, one model shipped to two runtimes (§4.2) | Best accuracy on structured tabular vitals; natively exportable to a lightweight offline runtime; deterministic and explainable |
| LLM briefing | Groq (Llama 3.3 70B → 3.1 8B) → Gemini (2.5 Flash → Flash-Lite) | 4-tier async fallback, `json-repair` for malformed output | Two independent providers, four independent rate limits — the briefing panel is never simply blank |
| Voice transcription | Groq Whisper (`whisper-large-v3-turbo`) first, Sarvam AI (`saaras:v3`) fallback | Either credential alone covers every supported language | See §5.5 for why the order is Groq-first |
| Hosting | Railway (backend) + Vercel (frontend) | GitHub-integrated auto-deploy | Dockerfile-based, FastAPI-native, adequate free/low-cost tiers for this traffic profile |

## 5.1 Backend Runtime

| Factor | FastAPI (selected) | Flask | Express (Node) | Django REST |
|---|---|---|---|---|
| Native Python ML integration | Yes — no bridge layer | Yes | No — needs a subprocess/bridge to Python | Yes |
| Async support for concurrent, variable-latency LLM calls | First-class (ASGI) | Workarounds needed | First-class | Not the default |
| Schema validation | Pydantic v2 — automatic, type-safe, generates OpenAPI | Manual or an extension | A separate library | Verbose serializers |
| Startup/RAM profile | Light | Light | Light | Heavier |

FastAPI was selected and remains the right call: Python-native integration
with the classifier and SHAP with zero bridge layer, async-first design for
LLM calls that carry real, variable latency, and Pydantic v2 as the actual
data contract between the intake form and the classifier.

## 5.2 Database — Supabase, Not a Local File

The original design used SQLite as a zero-setup prototype database with a
documented migration path to Supabase. That migration is complete, not a
future step — **Supabase/PostgreSQL is the only database this system
uses**, with Row-Level Security policies on `case_records`, `profiles`,
`facilities`, `referrals`, `case_reviews`, `case_outcomes`, and every other
table carrying tenant- or role-scoped data. Every schema change is a
version-controlled, idempotent SQL migration (`backend/supabase/
migrations/`) — there is no "just run the app and it creates tables"
implicit schema anymore.

Why this matters beyond "a bigger database": RLS makes access control a
database-level guarantee, not something that only holds if every API route
remembers to check it. A single narrow, explicitly-documented exception to
that boundary exists (an aggregate-only, RLS-bypassing query for two
specific cross-facility signals — referral load-balancing and the
deterioration alert, §4.7) and is treated as exactly that: an exception,
governed by a written test for any future reuse (`docs/DECISIONS.md`
§20, §22).

## 5.3 LLM API Selection and the 4-Tier Fallback

| Factor | Groq (Llama 3.3 70B / 3.1 8B) | Gemini 2.5 Flash / Flash-Lite |
|---|---|---|
| Response latency | Fastest hosted inference available at this quality | Slower, but a genuinely independent infrastructure provider |
| Independence from Groq | — | Fully independent API and infrastructure — a real fallback, not a second call to the same provider |
| JSON schema enforcement | Strong at 70B/8B scale | Strong |

Fallback order: Groq Llama-3.3-70B → Groq Llama-3.1-8B (same provider,
smaller/faster model, for when the larger model specifically is
unavailable) → Gemini 2.5 Flash → Gemini 2.5 Flash-Lite (a genuinely
independent provider and infrastructure, for when Groq itself is down).
Each tier gets a bounded retry before downgrading. This is the
implementation, not a plan for one.

## 5.4 Entity Extraction — Descoped, and Why That Was the Right Call

An earlier design considered a dedicated clinical-NER model
(Bio_ClinicalBERT / medspaCy) to extract structured entities from free-text
voice transcriptions before handing them to the LLM. **This was never
built, and in hindsight shouldn't be**: the JSON-schema-first design means
the intake *form itself* already produces structured fields (vitals,
symptom checklist, coded chief complaint) — the only free text that
reaches the LLM prompt at all is a bounded, sanitised `observations` /
`known_conditions` string, which the LLM (already doing structured
reasoning over the rest of the patient context) handles directly without a
separate extraction pass. Adding a dedicated NER model would have meant
another dependency, another failure mode, and another asynchronous step
on a path that doesn't need it. This is recorded here specifically because
"we considered this and correctly decided not to build it" is as valid an
R&D finding as anything that shipped.

## 5.5 Voice / Speech-to-Text

Voice input is never on the critical path — the entire intake form can be
completed by typing, and a failed transcription never blocks submission.

Two independent, optional providers, tried in a fixed order:

1. **Groq Whisper (`whisper-large-v3-turbo`)** — tried first, for *every*
   language including Hindi and Tamil.
2. **Sarvam AI (`saaras:v3`)** — specialised Indian-language speech-to-text,
   used *only* as the fallback if Groq is unconfigured or a request to it
   fails.

This ordering is the opposite of the original design, which put Sarvam
first specifically for its Indian-language specialisation. The reversal is
a deliberate, cost-driven decision: Groq carries no metered free-credit
ceiling at this application's request volume, while Sarvam's free tier is
a fixed signup credit — reserving it for a fallback role means it isn't
spent on requests Groq already serves adequately, while still being
available the moment Groq is unavailable. Either credential alone is
sufficient for transcription to work across every supported language; the
full rationale is `docs/DECISIONS.md` §24.

The browser's native `SpeechRecognition` API remains a client-side UX
fallback (real-time "listening" feedback, and a path that still works if
`MediaRecorder`/microphone access or the server call itself is
unavailable) — never the accuracy layer for a clinical record, since
browser STT accuracy on Indic medical speech isn't sufficient to rely on
for that.

## 5.6 Frontend

React 19 + Vite 7 remains the right choice for the same reasons as
originally decided — a component model that fits the complexity of both
the multilingual intake form and a real-time doctor dashboard, and the
fastest iteration loop available. What's changed since the original
design: the app is now a proper installable PWA (`vite-plugin-pwa`, a
service worker, and an IndexedDB-backed offline submission queue with a
capped size and idempotent sync), and internationalisation ships for
three languages today (English, Hindi, Tamil) rather than the six
originally proposed — a deliberate choice to ship fewer languages
correctly (proper `react-i18next` infrastructure, consistent field-level
translation) rather than more languages superficially.

## 5.7 Hosting

Railway (backend, Dockerfile-based) + Vercel (frontend, static build) — the
same combination originally chosen as the fastest path to a publicly
reachable deployment, and it remains the production hosting target today,
not merely a demo option. Both platforms auto-deploy from GitHub pushes.

---

# 6. Feasibility & Current State

## 6.1 What's Actually Built

Nearly everything the original document listed as "roadmap" is now built.
This table reflects the system as of today, not aspirationally.

| Capability | Status |
|---|---|
| Multilingual intake form (en/hi/ta) | Built |
| Structured intake → clinical JSON, server-validated | Built |
| 43-feature clinical engineering, mirrored online/offline | Built |
| Unified triage classifier, safety net, NEWS2 floor, abstention flag | Built |
| Real SHAP explanations | Built |
| 4-tier LLM briefing with hard-enforced triage/disclaimer | Built |
| Offline-first PWA: local queue, pure-JS triage, idempotent sync | Built |
| Supabase persistence with RLS across every table | Built |
| Supabase Auth, hybrid JWT verification, 4-role model (asha_worker/doctor/supervisor/admin) | Built |
| Doctor dashboard, real-time case feed, review/override/outcome recording | Built |
| Supervisor dashboard: facility-scoped, aggregate-only, non-PHI team metrics (modeled on NHM's ASHA Facilitator role) | Built |
| Outbreak early-warning dashboard (CDC EARS C1 aberration detection, informational only) | Built |
| Protocol/guideline lookup assistant (grounded, refuses patient-specific questions, async human curation) | Built |
| Referral workflow between facilities, self-reported facility capacity, predictive load-balancing | Built |
| Web Push notifications for EMERGENCY cases, offline one-tap SMS/`tel:` alert | Built |
| Drug/condition contraindication flags (advisory, deterministic) | Built |
| Patient-facing plain-language summary (LLM restatement, never re-derives triage) | Built |
| Patient continuity key (QR) + cross-visit deterioration alert | Built |
| Admin panel: user/facility management, analytics, CSV export, bulk onboarding, audit log | Built |
| DPDP Act 2023 compliance: consent capture, data-subject-request lifecycle, retention sweep | Built |
| WCAG 2.1 AA accessibility pass | Built |
| Security hardening: rate limiting, CSRF/device guard, security headers, PHI audit logging | Built |
| ML fairness audit + feature-drift monitoring tooling | Built (operator-run diagnostics) |
| SBOM generation, incident-response runbook, load testing | Built |
| Wearable/Edge Layer integration | Not started — schema is ready to receive it |
| Federated learning / zk-SNARK privacy layer | Not started |
| Message-queue / orchestration infrastructure layer | Not started at that scale |
| FHIR / SMART-on-FHIR endpoint | Not started — schema is FHIR-compatible; the endpoint itself is a small addition once needed |
| Protocol/guideline lookup assistant, photo-based visual triage, internal outbreak dashboard, ASHA-worker supervisor dashboard | Explicitly deferred pending a product decision — not built, not scoped in yet |

## 6.2 Incomplete Input Handling

| Scenario | Behaviour |
|---|---|
| Only demographics + chief complaint provided | Classifier still fires; briefing generated with explicit uncertainty flags for missing vitals |
| A vital is missing (e.g. no BP) | Feature engineering treats an unmeasured vital as unmeasured, not as normal — a missing danger is real and is surfaced, not masked. Training data itself simulates this exact pattern (missing-vitals simulation, §4.2) rather than assuming complete vitals |
| A required field is missing | Form submission is blocked client-side and validated again server-side — no clinically meaningless submission reaches the pipeline |
| Voice input fails | Submission proceeds on typed fields; voice is supplementary, never blocking |
| No connectivity at submission | Local pure-JS triage fires immediately; form queues; sync (and the LLM briefing, and doctor notification) happen on reconnection; EMERGENCY cases get an immediate offline SMS/`tel:` path that needs no data connection |

## 6.3 Risk Matrix (Current, Not Hackathon-Era)

| Risk | Mitigation |
|---|---|
| LLM provider rate-limited or down | 4-tier fallback across two independent providers; triage is unaffected regardless, since it never depended on the LLM |
| In-process rate limiter doesn't share state across horizontally-scaled backend instances | Rate-limit storage backend is configurable to a shared store (e.g. Redis) via a setting — documented, not yet required at current traffic |
| Supabase outage | The offline-first design means ASHA-side triage keeps working; doctor-side dashboard and persistence are genuinely dependent on Supabase being up — documented as a real dependency in `docs/DISASTER_RECOVERY.md`, not hidden |
| A future admin route forgets `require_role('admin')` | A regression test asserts every route in every admin-only module carries that dependency — CI-enforced, not a code-review-only convention |
| A future `clinical_features.py` change desyncs the JS mirror | Golden-vector parity tests (tree-level and feature-level) fail CI immediately — this has already caught one real bug during development |
| Model retrained without regenerating the offline JS artifacts together | The training script itself asserts py/ONNX/tree-JSON parity before it will save anything — a parity failure raises, not warns |

## 6.4 What Production-Scale Deployment Would Still Need

| Requirement | Current State |
|---|---|
| Clinical validation against real outcomes | Not done — all reported accuracy is against a synthetic, evidence-informed label generator (NEWS2/qSOFA/PALS-derived), explicitly and repeatedly stated as such in `MODEL_CARD.md`. The doctor override + outcome-recording endpoints already exist specifically to *start* collecting the real-label data a future validation study would need |
| Real (not synthetic) training data | Not available yet; the outcome-recording loop above is the collection mechanism, not a substitute for it |
| Regulatory classification | Not sought — VitalNet plausibly sits in a lower-risk CDSCO SaMD category as decision support with mandatory human review, but this is stated as a working hypothesis for a future formal exercise, not a self-certification (`docs/CLINICAL_GOVERNANCE.md`) |
| Government/PLI integration for adoption at scale | Not started — a policy decision, not a software one (§1.5) |
| FHIR / hospital-EHR integration | Schema-compatible; the integration itself needs institutional partnership agreements this project doesn't control |

## 6.5 The Honest Boundary

VitalNet does not solve, and does not claim to solve:

- **Doctor shortage** — a supply-side problem; VitalNet makes existing
  doctor capacity more effective, it cannot create more doctors.
- **Travel distance** — a geographic reality; VitalNet establishes triage
  priority to inform the urgency of a journey, it doesn't shorten it.
- **Infrastructure gaps** — no electricity, no tower, no device are outside
  scope; the system targets the well over 90% of villages with coverage,
  not the remainder.
- **Diagnostic certainty** — VitalNet produces decision support, not a
  diagnosis. An EMERGENCY classification prioritises a patient; it does
  not diagnose them. The doctor diagnoses.
- **Regulatory certainty** — this is clinical decision support, with
  mandatory human review as an architectural guarantee, not a diagnostic
  system with regulatory clearance.

VitalNet's honest claim: it creates one structured clinical record where
zero existed, delivers it to the person equipped to act on it before the
patient arrives, and establishes triage priority at the moment of first
contact — none of which happens today at any scale in rural India.

---

# 7. Impact Analysis

## 7.1 Per-Interaction Impact

| What Changes | Without VitalNet | With VitalNet |
|---|---|---|
| Structured record created | None — an unstructured paper slip, if it survives | One structured, timestamped, RLS-protected case record with vitals, symptoms, and a full AI briefing |
| Doctor context at consultation | Whatever the patient can describe verbally | A structured briefing with differentials, red flags, and missing-data flags, reviewable before the patient is even in the room |
| Triage priority signal | ASHA judgment alone, unstructured | A deterministic classification established at first contact, before the journey begins |
| ASHA–doctor feedback loop | Effectively nonexistent | The doctor can mark a case reviewed, override the tier with a reason, and record the actual outcome — closing a loop that also becomes real training data over time |

## 7.2 Adoption-Scale Impact

| Adoption Level | ASHA Workers | Population Covered (approx.) |
|---|---|---|
| 1% | ~9,400 | ~9.4 million |
| 5% | ~47,000 | ~47 million |
| 10% | ~94,000 | ~94 million |
| Full (100%) | ~9.4 lakh | ~940 million |

These figures describe the theoretical ceiling of the underlying ASHA
network — they are not a usage projection, and reaching them depends on
the two-phase adoption pathway described in §1.5, most of which is a
policy question, not an engineering one.

---

# 8. References

## 8.1 Government and Policy Data

- Rural Health Statistics 2022–23, Ministry of Health & Family Welfare —
  PHC count, population per PHC, CHC specialist shortfall
- NHM Annual Report 2023–24, National Health Mission — ASHA worker count,
  training duration
- TRAI Telecom Subscription Data Report, December 2024 — rural vs. urban
  teledensity
- Ministry of Communications, April 2024 — village-level 4G coverage
- Health Dynamics of India 2022–23 — doctor urban/rural distribution, PHC
  absenteeism
- Ayushman Bharat Digital Mission (ABDM) — FHIR API standards for Indian
  digital health records

## 8.2 Clinical and Research Grounding

- Thirunavukarasu AJ et al., "Large language models in medicine," *Nature
  Medicine*, 2023 — general-domain LLMs dominate evaluated clinical-LLM
  research instances
- Royal College of Physicians, *National Early Warning Score 2 (NEWS2)*,
  2017 — the aggregate + "any red parameter" escalation principle the
  safety net and NEWS2 floor are grounded in
- Singer M et al. ("Sepsis-3"), *JAMA*, 2016 — qSOFA criteria for
  suspected-infection deterioration
- He J et al., "Gradient boosting vs. deep learning on tabular data,"
  *NeurIPS*, 2023 — boosted trees consistently outperform deep learning on
  structured tabular clinical data
- Kumar A et al., *Critical Care Medicine*, 2006 — mortality increase per
  hour of delayed sepsis treatment
- BMJ Global Health — life-expectancy gap analysis, India, poorest vs.
  wealthiest quintile

## 8.3 Technology References

- Groq documentation — Llama 3.3 70B / 3.1 8B model specs and rate limits
- Google AI Studio — Gemini 2.5 Flash / Flash-Lite model specs
- Sarvam AI documentation — `saaras:v3` speech-to-text API
- Scikit-learn documentation — `HistGradientBoostingClassifier`
- SHAP documentation — `TreeExplainer`
- Supabase documentation — Row-Level Security, Auth, Realtime
- FastAPI documentation — async endpoint design, Pydantic v2 validation

## 8.4 Competitive Landscape Sources

- ASHABot — Khushi Baby + Microsoft Research India
- ClinicalPath India / DIISHA — Elsevier + NITI Aayog
- AiSteth (AsMAP) — Ai Health Highway

---

# 9. Development History (Summary, Not a Changelog)

VitalNet went through several distinct phases: an initial prototype built
around a five-layer vision, of which the AI Diagnostic Layer was chosen as
the buildable slice; a full rebuild replacing the original file-based
database with Supabase/PostgreSQL and Row-Level Security; a security and
reliability hardening round (hybrid JWT auth, rate limiting, audit
logging, DPDP compliance, accessibility); and — most recently — a direct
ML audit that found and fixed dead training features, added a second
calibration validation against realistic class prevalence, and fixed a
real (if rare) floating-point parity bug uncovered during that retrain.

The full, granular history of *why* each of these changes happened lives
in `docs/DECISIONS.md` (numbered ADR-style entries) and
`backend/CLASSIFIER_CHANGELOG.md` (model-specific evolution) — this
document is the narrative and the research grounding; those are the
detailed record.
