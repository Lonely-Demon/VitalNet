# VitalNet R&D — Answers Log
### Running record of all settled decisions and answers
> This file exists to preserve context across long conversations. Every answer here is locked unless explicitly reopened.

---

## STATUS TRACKER

| Group | Questions | Status |
|---|---|---|
| Group 1 — Problem Depth | Q1, Q16, Q17, Q18, Q29, Q30 | Q1/Q16 LOCKED — Q17 LOCKED — Q18 LOCKED — Q29 LOCKED — Q30 DEFERRED |
| Group 2 — Slice Definition | Q2, Q3, Q19, Q20, Q21 | ALL LOCKED ✓ |
| Group 3 — Competitive Landscape | Q4, Q5, Q6, Q7 | ALL LOCKED ✓ |
| Group 4 — How Doctors Use AI | Q31, Q32, Q33, Q35, Q36 | ALL LOCKED ✓ |
| Group 5 — AI Layer Design | Q22, Q23, Q24, Q25, Q34 | ALL LOCKED ✓ |
| Group 6 — Trust & Adoption | Q37, Q38, Q39 | ALL LOCKED ✓ |
| Group 7 — India-Specific Reality | Q40, Q41, Q42, Q43 | ALL LOCKED ✓ |
| Group 8 — Tech Stack | Q8–Q15 | ALL LOCKED ✓ |
| Group 9 — Feasibility & Honesty | Q26, Q27, Q28, Q44, Q45 | ALL LOCKED ✓ |
| Group 10 — Output & Delivery Design | Q46, Q47, Q48 | ALL LOCKED ✓ |
| Group 11 — Impact | Q29, Q30 | ALL LOCKED ✓ |

---

## CORE IDENTITY (LOCKED)

**Project Name:** VitalNet

**Design Philosophy (R&D Document opener):**
> "VitalNet isn't a new AI — it builds the missing infrastructure layer that puts existing AI in the hands of an ASHA worker in a village that has never seen a specialist."

**Pitch Hook (Presentation opener):**
> "A village that has never seen a specialist now has access to the same AI a doctor at Apollo uses. VitalNet didn't build new AI — it built the infrastructure that was always missing."

**Single Core Benchmark (everything serves this):**
> An ASHA worker describes a patient. A doctor anywhere receives a structured clinical briefing they can act on — before the patient travels to the clinic.

---

## GROUP 1 — PROBLEM DEPTH

---

### Q1 / Q16 — Who exactly is the end user? (LOCKED)

**End User 1 — ASHA Worker (Input Side)**

- ~9.4 lakh ASHA workers active across India under NHM (National Health Mission)
- One ASHA per ~1000 rural population
- Female, aged 25–45, from the same village she serves
- Education: Class 8–10 minimum (Class 10 preferred, relaxed where unavailable)
- Receives only 23 days of basic training across 5 phases — not a medical professional
- Device: government-issued basic Android smartphone (entry-level, 2-3GB RAM)
- Already uses government apps — ASHA Soft for recording visits and reporting
- Language: operates in regional language — Hindi, Tamil, Telugu, Bengali etc. English literacy is low to minimal
- Connectivity: 95% of villages technically have 3G/4G coverage but reliability is inconsistent indoors and in dense rural terrain. Rural wireless teledensity is only 57.89% vs 124.31% urban — coverage ≠ reliable connectivity
- Compensation: performance-based, ~₹10,000/month average — not salaried, incentivised per task

**Key constraint derived from this profile:**
The intake UI cannot require English literacy. It cannot assume stable connectivity. It cannot be complex enough to require training beyond one session. It must feel like a form, not a tool.

**End User 2 — PHC/CHC Doctor (Output Side)**

- PHC (Primary Health Centre) or CHC (Community Health Centre) doctor
- English literate, comfortable with clinical terminology
- Severely overloaded — a typical PHC doctor sees 40–80+ patients per day
- Device: personal Android or iOS smartphone, possibly desktop at the clinic
- Connectivity: reliable at PHC level
- Key need: a structured, scannable briefing — not a chat conversation, not raw data dumps
- Time available per patient review: under 2 minutes before seeing the next patient

**Key constraint derived from this profile:**
The output cannot be a paragraph of AI text. It must be a structured clinical card — triage priority, key symptoms, vitals, red flags, recommended tests — scannable in under 30 seconds.

**Input Design Decision (LOCKED):**

- **Primary input:** Typed multilingual structured form
  - Eliminates speech-to-text dependency from the critical path
  - Typed input is a reviewable record — ASHA worker can verify before submitting
  - Works on any Android with zero additional model dependency
- **Secondary input:** Voice note with local audio caching
  - Audio captured locally on device
  - Processed via API (Sarvam AI or Whisper) when connectivity available
  - If offline: audio stored temporarily, processed when connection returns
- **Why voice is secondary (three compounding reasons, not just accuracy):**
  1. **Accuracy** — Indic language STT unreliable for medical terminology at required precision. Mishearing "chest pain" vs "chest strain" in a clinical context is not acceptable
  2. **Latency** — Audio files are large. On weak 3G, uploading 30-second audio adds unacceptable delay to a time-sensitive workflow
  3. **Accountability** — Typed input is a verifiable record. Voice transcription creates ambiguity about what was actually said. In a medical context, that ambiguity has consequences

---

### Q17 — Current manual workflow step by step, and where it breaks (IN PROGRESS)

**Verified current workflow (from NHM guidelines + field evidence):**

**Step 1 — Patient contact**
ASHA worker visits a household or is approached by a community member with a complaint. She observes symptoms visually, asks questions verbally in the local language.

**Step 2 — Assessment with no structured tool**
She applies the basic training she received across 23 days — which covers maternal health, immunization, common ailments. For anything beyond minor ailments (fever, diarrhoea, first aid), she has no structured diagnostic framework. Knowledge gaps are documented — studies show poor ASHA knowledge on referral conditions for severe diarrhoea, respiratory tract infections, neonatal infections.

**Step 3 — Referral decision made manually**
She decides whether to refer or not based on judgment alone. If she refers:
- She fills out a paper referral slip
- She may or may not accompany the patient to the PHC
- The slip contains: patient name, age, complaint — written in local language, handwritten, no standard format

**Step 4 — Patient travels to PHC**
PHC may be 20–40km away. Travel requires arranging transport — often the patient's own cost and effort. For serious conditions, delay here can be fatal.

**Step 5 — Doctor receives patient blind**
The PHC doctor sees the patient with:
- A handwritten slip (if the ASHA sent one)
- Verbal history from the patient (often incomplete, inaccurate, or in a dialect the doctor may not speak fluently)
- Zero prior health records
- Zero context on what the ASHA observed

Every consultation starts from zero. There is no continuity, no prior data, no risk context.

**Step 6 — No feedback loop**
After the doctor sees the patient, no information returns to the ASHA worker. She doesn't know the diagnosis, the treatment, or whether the referral was appropriate. She cannot learn from outcomes.

**Where it breaks — four specific failure points:**

| Failure Point | What Goes Wrong | Consequence |
|---|---|---|
| Assessment | ASHA has no structured framework for non-routine conditions | Conditions misidentified or under-triaged |
| Documentation | Paper slip, no standard format, no record kept | Doctor receives no useful context |
| Travel delay | PHC 20–40km away, patient arranges own transport | Hours lost — critical for cardiac, stroke, sepsis |
| Doctor starts blind | No history, no vitals trend, no risk flags | Consultation quality depends entirely on patient's verbal account |

**One-sentence lock for Q17:**
> *The current workflow fails at the point of first contact — no structured record is created when the ASHA worker first sees the patient, and every downstream failure in rural healthcare traces back to that single missing moment.*

**STATUS: LOCKED**

---

### Q18 — Cost of the current failure: in time, in lives, in missed diagnoses (LOCKED)

**In numbers — verified from government and peer-reviewed sources:**

| Metric | Data | Source |
|---|---|---|
| Specialist shortage at CHCs | 83% shortage of required specialists | Rural Health Statistics 2021-22, MoHFW |
| Doctor density gap | 1 doctor per 10,000+ in rural vs 1 per 1,500 in urban | NASSCOM / DocBox 2024 |
| Population without specialist access | 70% of India's population has no access to specialist care | PMC peer-reviewed, 2024 |
| Infrastructure concentration | 75% of health infrastructure in urban areas serving only 27% of population | Ballard Brief, BYU 2025 |
| PHC coverage per doctor | One PHC covers avg 36,049 rural individuals | RHS 2021-22 |
| Life expectancy gap | 65.1 years (poorest 20%) vs 72.7 years (wealthiest 20%) — 7.6 year gap | BMJ Global Health |
| Out-of-pocket health expenditure | ~70% of per capita health expenses paid out of pocket | PMC India healthcare review |
| Rural patients pushed below poverty | 3x more than urban patients due to healthcare costs | Ballard Brief, BYU 2025 |

**In time — what the delay actually costs:**

A patient in rural India experiencing a cardiac event, stroke, or sepsis onset follows this timeline:
- ASHA worker observes symptoms → judgment call with no structured framework → **30–60 min lost**
- Patient arranges own transport to PHC 20–40km away → **1–3 hours lost**
- PHC doctor sees patient with zero prior context → consultation starts from zero → **additional 20–40 min lost**
- If referral to CHC/district hospital needed → another 20–60km → **2–4 more hours**

For cardiac arrest: brain death begins within 4–6 minutes of oxygen loss. The golden hour for stroke is 60 minutes. Sepsis mortality increases 7% per hour of delayed treatment. The rural referral chain routinely consumes the entire golden window before a qualified doctor makes a single informed decision.

**In missed diagnoses:**

- There is minimal infrastructure for maintaining patient health records in rural areas, resulting in a lack of long-term data that hinders accurate diagnosis and treatment
- Every consultation starts from zero — no history, no trends, no prior context
- Conditions that require pattern recognition across visits — hypertension, diabetes, early-stage TB — are routinely missed because no visit-to-visit record exists
- Rural healthcare facilities face an 83% shortage of specialists at CHCs, leading to long wait times, delayed diagnoses, and inadequate treatment

**The compounding effect:**

The cost is not just individual lives. Approximately 75% of health infrastructure and resources are concentrated in urban areas, where only 27% of the population resides — meaning the majority of India's population operates in a system where delayed diagnosis is not an exception. It is the default.

**One-sentence lock for Q18:**
> *The documentation gap costs India not just lives lost in the golden hour — it costs the entire primary care system its ability to learn, because no record of what was observed at first contact ever survives long enough to inform the next decision.*

**STATUS: LOCKED**

---

### KEY RESEARCH FINDING — ASHABot (Critical for Group 3)

**Source:** Microsoft Research India + Khushi Baby NGO (launched early 2024)

ASHABot is an LLM-powered WhatsApp chatbot trained on India's public health manuals, immunization guidelines, and family planning protocols. It accepts voice notes and text in Hindi, English, and Hinglish.

**What it does:** Answers ASHA workers' questions about patient care — "what's the ideal weight for a baby this age", contraception guidance, maternal health queries.

**What it does NOT do:**
- It does not generate structured patient briefings for doctors
- It does not perform triage classification
- It does not create a clinical record
- It does not close the loop between ASHA worker and doctor
- It is an information assistant for the ASHA worker, not a clinical workflow tool

**Why this matters for VitalNet:**
ASHABot validates that ASHA workers can and will use LLM-based tools on WhatsApp in their regional language. It proves the adoption model. But it operates entirely on the ASHA side — VitalNet operates across the ASHA-to-doctor bridge. These are complementary, not competing.

This finding will be central to Group 3 (Competitive Landscape) answers.

---

---

### Q29 — Scale of the problem: real-world data (LOCKED)

**The ASHA workforce — scale of the entry point:**

- ~9.4 lakh ASHA workers deployed across India, one per ~1000 rural population, selected and accountable to the gram panchayat
- Each ASHA undergoes only 23 days of training conducted under health department guidance — covering maternal health, immunization, child health. Complex triage for cardiac, respiratory, or neurological conditions is not in the curriculum
- ASHA serves a population of 700 in tribal areas or 1000 in rural villages

**The PHC infrastructure — scale of the bottleneck:**

- As of March 2023: 31,882 PHCs and 6,359 CHCs functioning across India, supported by 40,583 doctors/medical officers at PHCs and 26,280 specialists at CHCs
- One PHC covers an average rural population of 36,049 individuals. One CHC covers 164,027 individuals
- CHCs face an overall shortfall of 79.5% specialists — including 83.2% shortage of surgeons, 74.2% of obstetricians/gynaecologists, 79.1% of physicians, and 81.6% of paediatricians

**The workforce distribution gap:**

- 66.91% of all health workers serve in urban areas where only 33.48% of the population lives. 33.09% serve in rural areas where 66.52% of the population resides
- Only 27% of doctors are available in rural areas despite almost two-thirds of India's population living there
- India's doctor-patient ratio is approximately 1:1456, below the WHO recommended ratio of 1:1000 — and significantly worse in rural areas

**The absenteeism reality:**

- Average absenteeism of doctors appointed to PHCs was 43% in 2003 and 40% in 2010 — meaning on any given day, nearly half of assigned PHC doctors are not present
- More than 8% of PHCs had no doctor at all; 38% had no laboratory technician; 22% had no pharmacist

**What this means in human terms:**

A single PHC doctor — when present — is the sole medical officer for 36,049 people. If that doctor sees 60 patients per day, each patient gets approximately 5-7 minutes of attention. In that window, the doctor receives a patient with no prior records, no ASHA intake notes, no vitals history, no triage context. Every consultation starts from zero.

VitalNet's entry point — 9.4 lakh ASHA workers — represents 9.4 lakh first contacts per day where structured clinical data is currently created nowhere and lost immediately.

**One-sentence lock for Q29:**
> *9.4 lakh ASHA workers make first contact with rural patients every day and produce zero structured clinical data — while the PHC doctors they refer to are absent 40% of the time, covering 36,000 people each, with 5 minutes per patient and no prior context for any of them.*

**STATUS: LOCKED**

---

---

## GROUP 2 — SLICE DEFINITION

---

### Q2 — Why are we building this specific slice out of the entire VitalNet vision? (LOCKED)

**The full VitalNet vision has five layers:**

| Layer | What it does |
|---|---|
| Edge layer | ESP32 wearables, local inference, offline vitals capture |
| AI diagnostic layer | Multimodal input, triage classification, explainable output |
| Privacy layer | Federated learning, zk-SNARKs, decentralized identity |
| Cloud layer | Kafka, Kubernetes, encrypted S3, IPFS |
| Workflow layer | Hospital dashboard, doctor assignment, bed management |

**Why the AI diagnostic layer is the slice we build:**

**Reason 1 — No hardware dependency**
The edge layer needs ESP32, BLE sensors, NB-IoT modules. None available. The AI layer needs only a browser, a backend, and API calls. It is the only layer that is fully buildable on available hardware.

**Reason 2 — It proves the entire vision viable**
Every other layer exists to feed data into the AI diagnostic layer or act on its output. Wearables feed it. The privacy layer protects it. The workflow layer distributes its output. If the AI layer doesn't work, none of the other layers have a reason to exist. Proving this layer works is proving the entire concept is viable.

**Reason 3 — It directly solves the root cause**
Q17 locked the root cause as: no structured clinical record created at point of first contact. The AI diagnostic layer is precisely what creates that record — it takes ASHA worker input and produces a structured clinical briefing. This is not a supporting layer. It is the root cause solution.

**Reason 4 — It produces a demo a judge can experience in real time**
A working AI diagnostic layer is something a judge can interact with — type a patient case, watch triage fire, read the doctor briefing. A Kubernetes cluster or federated learning setup produces nothing a judge can experience in 90 seconds.

**One-sentence lock:**
> *The AI diagnostic layer is the only slice that requires no hardware, proves the entire vision viable, directly solves the root cause we identified, and produces a demo a judge can experience in real time — every other layer in the VitalNet vision exists either to feed this layer or distribute its output.*

**STATUS: LOCKED**

---

### Q3 — Why is this slice better than other possible slices? (LOCKED)

**Rejected slices — explicit reasoning:**

**Slice 1 — Edge Layer (ESP32 wearables + local inference)**

| Factor | Assessment |
|---|---|
| Hardware requirement | Requires ESP32, BLE sensors, NB-IoT module — none available |
| Build time | Hardware integration alone would consume the entire 24 hours |
| Demo risk | Hardware failures during live demo are unrecoverable |
| Root cause relevance | Captures vitals but doesn't create structured clinical records or briefings |
| Verdict | REJECTED — hardware dependency makes it impossible solo in 24 hours |

**Slice 2 — Privacy Layer (federated learning, zk-SNARKs, DID)**

| Factor | Assessment |
|---|---|
| Compute requirement | Federated learning requires a fleet of devices. zk-SNARK proof generation is computationally heavy — impossible on 4GB RAM Pentium |
| Build time | Each of these is a PhD-level engineering problem independently |
| Demo risk | Nothing a judge can see or interact with — invisible infrastructure |
| Root cause relevance | Protects data but creates none — doesn't address the documentation gap |
| Verdict | REJECTED — computationally infeasible on available hardware, invisible in a demo |

**Slice 3 — Cloud Layer (Kafka, Kubernetes, IPFS)**

| Factor | Assessment |
|---|---|
| Hardware requirement | Kubernetes on a 4GB RAM Pentium will consume all available memory before a single pod runs |
| Build time | Kafka + Kubernetes setup alone is a full day of DevOps work |
| Demo risk | Distributed systems have the most failure modes under demo conditions |
| Root cause relevance | Transport and storage infrastructure — creates no intelligence, solves no clinical problem |
| Verdict | REJECTED — infrastructure layer with no clinical value demonstrable in a hackathon |

**Slice 4 — Workflow Layer (hospital dashboard, doctor assignment, bed management)**

| Factor | Assessment |
|---|---|
| Dependency | Requires the AI diagnostic layer to already be working — has no input without triage output |
| Build time | Feasible UI-wise but hollow without the intelligence layer behind it |
| Demo risk | A doctor assignment dashboard with no real triage data is just a table with names |
| Root cause relevance | Distributes output but creates none — downstream of the actual fix |
| Verdict | REJECTED as primary slice — retained as supporting UI element around the AI layer |

**The pattern across all four rejections:**
Every other slice is either impossible on available hardware or hollow without the AI layer already working.

**One-sentence lock:**
> *Every other slice in the VitalNet vision is either computationally infeasible on available hardware, requires physical components we don't have, or is hollow without the AI diagnostic layer already working — making the AI layer not just the best slice but the only viable slice for a solo 24-hour build.*

**STATUS: LOCKED**

---

### Q19 — What does "working" look like in 24 hours? (LOCKED)

**The complete functional loop:**

```
ASHA Input
    ↓
Input Structuring (form data → clinical JSON schema)
    ↓
Risk Assessment (triage classifier → Emergency/Urgent/Routine)
    ↓
Explain the Rationale (SHAP-style plain English explanation)
    ↓
Generate Summary Report (LLM → structured doctor briefing)
    ↓
Update Database (case record persisted)
    ↓
Doctor Dashboard (priority queue, briefing card, red flags visible)
```

**Why Input Structuring is an explicit step:**
The triage classifier and LLM both need input in a specific format. Raw form data needs to be converted into a consistent clinical JSON schema before either model processes it. This is the actual infrastructure VitalNet builds — the AI is the reasoning engine sitting on top of a structured data layer.

**Must work — demo fails without these:**
1. ASHA worker intake form loads, accepts patient data, submits successfully
2. Input structuring converts form data to clinical JSON schema
3. Triage classifier fires — returns Emergency/Urgent/Routine with SHAP-style plain English rationale
4. LLM generates structured doctor briefing within 15 seconds of submission
5. Case persisted to database
6. Doctor dashboard displays case with triage badge, patient summary, AI briefing

**Should work — demo is stronger with these:**
7. Voice input — records audio, caches locally, transcribes on submission
8. Multiple cases in queue — doctor dashboard shows priority ordering across cases
9. Architecture tab — full VitalNet vision diagram positioning the demo as one layer of a larger system

**Roadmap only — mentioned in pitch, not built:**
Federated learning, wearable integration, zk-SNARKs, Kafka, Kubernetes — every infrastructure claim from the abstract

**The single benchmark for "working":**
> A judge types: *"55 year old male, rural UP, chest tightness and breathlessness for 2 hours, BP 160/100, no prior history"* — and within 15 seconds sees: **EMERGENCY** — *"Primary risk driver: chest tightness combined with elevated BP in male over 50 — possible acute cardiac event"* — followed by a structured doctor briefing with differential diagnosis, red flags, and recommended immediate tests.

**One-sentence lock:**
> *"Working" means a complete unbroken flow from ASHA input through structured triage, explainable rationale, LLM-generated doctor briefing, database persistence, and live dashboard update — demonstrable end-to-end in under 15 seconds for a single patient case.*

**STATUS: LOCKED**

---

### Q20 — What does the slice NOT do, and why is that a conscious decision? (LOCKED)

**What this slice deliberately does not do:**

**1. Does not collect vitals from hardware**
Wearables, ESP32, BLE sensors are not part of this build. Vitals are manually entered by the ASHA worker on the intake form.
*Conscious reason:* Hardware integration introduces the highest demo failure risk of any component. A single loose connection kills the demo. Manual entry produces identical data for the AI layer with zero failure risk. The intelligence layer does not care whether BP 160/100 came from a wearable or a typed field — it processes the value identically.

**2. Does not implement real federated learning or privacy infrastructure**
No TensorFlow Federated, no zk-SNARKs, no DID-Comm, no IPFS.
*Conscious reason:* Federated learning requires a fleet of edge devices to train across. zk-SNARK proof generation is computationally infeasible on 4GB RAM. These are production infrastructure concerns — not prototype concerns. The prototype demonstrates that the intelligence layer works. Privacy infrastructure wraps around a working system, it does not precede one.

**3. Does not automate hospital workflow**
No bed allocation, no doctor load balancing, no appointment scheduling.
*Conscious reason:* Workflow automation is downstream of the intelligence layer. You cannot automate a workflow that has no structured data to act on. VitalNet creates that structured data first. Workflow automation is Phase 2 — it has no foundation until Phase 1 works.

**4. Does not connect to live hospital systems or real EHR**
No FHIR integration, no hospital database connections, no live PHC records.
*Conscious reason:* Real hospital system integration requires institutional access, data sharing agreements, and regulatory compliance — none available in a 24-hour hackathon. The prototype uses a local SQLite database with a schema designed to be FHIR-compatible, making real integration a configuration task in production, not a rebuild.

**5. Does not provide real-time teleconsultation**
No video call, no live chat between ASHA worker and doctor.
*Conscious reason:* Teleconsultation is a solved problem — WhatsApp, eSanjeevani, and dozens of platforms already do it. VitalNet is not competing with teleconsultation. It solves the problem that exists before teleconsultation — the absence of structured clinical context that makes teleconsultation actually useful.

**The unifying principle across all five:**
> *VitalNet does not build infrastructure that wraps around intelligence — it builds the intelligence that infrastructure will eventually wrap around.*

**One-sentence lock:**
> *This slice does not build wearable integration, privacy infrastructure, hospital workflow automation, EHR connectivity, or teleconsultation — not because these are beyond scope, but because every one of them is either a wrapper around the intelligence layer or a scaling concern that has no foundation until the intelligence layer works.*

**STATUS: LOCKED**

---

### Q21 — How does this slice enable the rest of the vision — what does it unlock for future phases? (LOCKED)

**Core principle:**
> *Every layer in the VitalNet vision is blocked until there is structured clinical data to operate on. This slice creates that data. Therefore this slice unblocks everything.*

**What each future phase needs from this slice:**

**Phase 2 — Edge Layer (wearables + local inference)**
Currently blocked because: no structured schema exists to write wearable data into.
Unlocked by this slice: the clinical JSON schema defined in Input Structuring becomes the exact target format for wearable output. A wearable sending BP, SpO2, and heart rate populates the same fields the ASHA worker currently types manually. The AI layer receives identical input regardless of source.

**Phase 2 — Privacy Layer (federated learning, zk-SNARKs)**
Currently blocked because: no patient data is being generated to protect.
Unlocked by this slice: every case record created by the AI diagnostic layer is a structured, schema-consistent data point. Federated learning trains on these records across distributed nodes. zk-SNARKs generate proofs over this structured data. The privacy layer has nothing to wrap around until structured records exist.

**Phase 3 — Predictive Analytics (LSTM forecasting, population-level risk)**
Currently blocked because: prediction requires longitudinal patient data — multiple records per patient over time.
Unlocked by this slice: every case submitted creates a timestamped record. After weeks of operation, the same patient appears multiple times with vitals trends. That time-series is exactly what LSTM forecasting trains on.

**Phase 3 — Cloud Layer (Kafka, Kubernetes)**
Currently blocked because: Kafka needs messages to queue. Kubernetes scales services that need to exist first.
Unlocked by this slice: the FastAPI backend is the exact service Kafka sits in front of in production. Every API call that currently goes directly to FastAPI becomes a Kafka message in the production architecture. The swap is infrastructural, not architectural.

**Phase 4 — Hospital Workflow Automation**
Currently blocked because: doctor assignment and bed allocation require knowing patient priority before the patient arrives.
Unlocked by this slice: triage classification — Emergency/Urgent/Routine — is precisely the signal workflow automation needs. Emergency triggers automatic ICU alert. Urgent triggers specialist queue. Routine triggers standard appointment. The workflow layer is a rule engine sitting on top of triage output that already exists.

**The dependency map:**

```
AI Diagnostic Layer (Phase 1 — this slice)
        ↓ produces structured clinical records
        ↓
┌───────────────────────────────────────┐
│  Wearable integration  (Phase 2)      │ ← writes into same schema
│  Privacy layer         (Phase 2)      │ ← wraps around this data
│  Predictive analytics  (Phase 3)      │ ← trains on this time-series
│  Kafka / Kubernetes    (Phase 3)      │ ← scales this service
│  Workflow automation   (Phase 4)      │ ← acts on triage output
└───────────────────────────────────────┘
```

**One-sentence lock:**
> *This slice is the keystone — it produces the structured clinical records that every other VitalNet layer either feeds into, wraps around, learns from, or acts on — meaning nothing else in the vision is buildable until this works.*

**STATUS: LOCKED**

---

---

## GROUP 3 — COMPETITIVE LANDSCAPE

---

### Q4 — Is there any existing solution similar to the slice we are working on? (LOCKED)

**Yes. Three tools exist in the Indian rural healthcare AI space. None of them do what VitalNet does.**

| Tool | Developer | Launched | What it does |
|---|---|---|---|
| ASHABot | Khushi Baby + Microsoft Research India | Early 2024 | WhatsApp chatbot answering ASHA worker questions in Hindi/Hinglish/English using GPT-4 trained on India's public health manuals |
| ClinicalPath Primary Care India (DIISHA) | Elsevier + NITI Aayog | July 2024 | AI clinical decision support tool for ASHA workers — guideline-based screening and assessment |
| AiSteth (AsMAP) | Ai Health Highway | 2023 | AI stethoscope platform detecting cardiac murmurs and valvular disorders, deployed across 19 rural PHCs in Maharashtra |

---

### Q5 — What are their capabilities and what do they not cover? (LOCKED)

**ASHABot — Khushi Baby + Microsoft Research India**

Capabilities:
- GPT-4 based WhatsApp chatbot trained on ~40 curated documents including India's public health manuals, immunization guidelines, and family planning protocols
- Accepts voice notes and text in Hindi, English, and Hinglish — responds within seconds
- Answers ASHA worker questions: ideal baby weight, immunization schedules, breastfeeding guidance, contraception
- 869 ASHAs onboarded, 24,000+ messages sent since early 2024 — currently operating only in Udaipur district, Rajasthan

Critical gaps:
- **Does not generate structured patient records** — every conversation is ephemeral, nothing is persisted
- **Does not perform triage classification** — it answers questions, it does not assess patient risk
- **Does not produce doctor-facing output** — the doctor receives nothing from ASHABot
- **Does not close the ASHA-to-doctor loop** — operates entirely on the ASHA side
- Operates only in specific domains: maternal health, immunization, child health — not general triage

**ClinicalPath Primary Care India / DIISHA — Elsevier + NITI Aayog**

Capabilities:
- AI clinical decision support tool aimed at "bringing expert-level screening and assessment capabilities to the most remote corners of the country"
- Guideline-based — uses Elsevier's Arezzo system to select relevant clinical guidelines based on patient triggers
- Uses AI to select which guidelines might be useful depending on the particular patient or set of triggers
- Feasibility study conducted in Bahraich district, Uttar Pradesh — sponsored by NITI Aayog

Critical gaps:
- **Guideline retrieval, not clinical reasoning** — surfaces relevant protocols rather than generating a clinical assessment
- **No doctor-facing structured briefing** — outputs guidelines for the ASHA worker, not a briefing for the doctor
- **No triage classification with explainability** — does not produce Emergency/Urgent/Routine with rationale
- **Institutional tool** — requires Elsevier licensing and government partnership, not open infrastructure
- Pilot-stage only, limited geographic coverage

**AiSteth (AsMAP) — Ai Health Highway**

Capabilities:
- Detects murmurs and screens for valvular heart disorders — deployed across 19 primary healthcare clinics in rural Maharashtra
- Over 38,000 patients screened in 18 months since launch
- Used by MBBS doctors, nurses, and ASHA workers for cardiac screening

Critical gaps:
- **Single-domain tool** — cardiac/respiratory only, not general triage
- **Hardware-dependent** — requires the AiSteth device, not deployable on a standard smartphone
- **No LLM reasoning layer** — pattern matching on audio signals, not clinical reasoning across symptoms and history
- **No doctor briefing generation** — identifies a flag, does not create a structured clinical record

---

### Q6 — If no direct equivalent exists, why? (LOCKED)

No direct equivalent to VitalNet's specific slice exists because building it requires combining three things that have historically been developed in isolation:

1. **Structured intake at point of first contact** — the data layer
2. **LLM-based clinical reasoning** — the intelligence layer
3. **Doctor-facing structured output** — the communication layer

Every existing tool owns one of these three:
- ASHABot owns the intelligence layer (LLM reasoning) but discards the data layer and ignores the doctor layer
- ClinicalPath owns the data layer (structured intake) but outputs back to the ASHA worker, not the doctor
- AiSteth owns a narrow version of structured output but is hardware-dependent and single-domain

The gap exists because the organisations building these tools approached the problem from their own domain expertise — Microsoft Research from conversational AI, Elsevier from clinical guidelines, AiSteth from medical devices. None of them approached it as an infrastructure problem: how do you create a structured clinical record at first contact and deliver it to the right person?

VitalNet approaches it exactly that way. The intelligence is the means, not the end.

---

### Q7 — If something existed and failed, why did it fail? What can we learn? (LOCKED)

No direct equivalent has publicly failed — because no direct equivalent has been fully built yet. However, the partial tools above reveal failure patterns we can learn from:

**Failure Pattern 1 — Ephemeral output (ASHABot)**
ASHABot produces answers that are consumed in the moment and leave no persistent record. The ASHA worker gets an answer, the conversation ends, nothing is written anywhere. Every patient interaction remains undocumented.
*What VitalNet learns:* Every interaction must produce a persisted structured record. The database write is not optional infrastructure — it is the primary output.

**Failure Pattern 2 — Wrong recipient (ClinicalPath)**
ClinicalPath surfaces guidelines back to the ASHA worker — the person who already triggered the query. The doctor, who needs to act on the information, receives nothing.
*What VitalNet learns:* The output must be designed for the doctor, not the ASHA worker. The ASHA worker is the data collector. The doctor is the decision maker. These are different roles requiring different outputs.

**Failure Pattern 3 — Hardware lock-in (AiSteth)**
AiSteth requires proprietary hardware — the AI stethoscope. This limits deployment to clinics that can afford and maintain the device, excluding the most resource-constrained settings where the problem is worst.
*What VitalNet learns:* The entire system must run on hardware that already exists in the field — a basic Android smartphone. No proprietary hardware, no device procurement, no maintenance dependency.

**Failure Pattern 4 — Domain narrowness (AiSteth, ClinicalPath)**
Both tools address specific domains — cardiac screening, maternal health, immunization. Rural healthcare triage is not domain-specific. A patient presenting to an ASHA worker could have a cardiac event, a respiratory infection, a neurological symptom, or a gynaecological emergency.
*What VitalNet learns:* The reasoning engine must be general-purpose. This is precisely why a general-purpose LLM is the right choice over a purpose-built medical model — it reasons across domains without requiring separate models per condition.

**The pattern across all four failure modes:**
Every existing tool optimised for one dimension of the problem and ignored the others. VitalNet is the first attempt to connect all three dimensions — structured intake, LLM reasoning, and doctor-facing output — into a single unbroken workflow.

**STATUS: Q4, Q5, Q6, Q7 ALL LOCKED**

---

---

## GROUP 4 — HOW DOCTORS USE AI

---

### Q31 — How do doctors use existing AIs? (LOCKED)

Doctors use AI in five distinct ways, validated by peer-reviewed research and AMA surveys:

**1. Clinical documentation and summarization (most common)**
- Ambient AI scribes transcribe patient encounters and auto-generate structured clinical notes
- AI summarizes patient chart history before each visit — reducing chart review time
- Microsoft Dax Copilot saves clinicians an average of 5 minutes per patient encounter (Source: Microsoft, via TechTarget 2024)
- Oracle Health Clinical AI Agent reduces documentation time by nearly 30% (Source: Oracle, via TechTarget 2024)
- NYU Langone Health deployed GPT-4 via Epic EHR — average chart review time dropped from 3:22 to 3:04 minutes per visit (Source: PMC, 2024)

**2. Diagnostic reasoning assistance**
- Doctors feed patient case details — symptoms, history, labs, exam findings — to ChatGPT/Claude and request differential diagnoses
- Used as a second opinion or sanity check, especially for unusual presentations
- Randomized controlled trial at UVA, Stanford, and Harvard: ChatGPT alone achieved 92% diagnostic accuracy on clinical vignettes vs 76% for doctors using ChatGPT and 74% for doctors using traditional resources (Source: JAMA Network Open, 2024)

**3. Clinical decision support**
- 72% of physicians believe AI could help with diagnostic ability (Source: AMA Survey, 2024)
- Used for drug interaction checks, dosage guidance, and treatment protocol selection
- Elsevier's guideline-based systems surface relevant clinical protocols based on patient triggers

**4. Patient communication and discharge documentation**
- AI generates patient-friendly discharge instructions from complex clinical notes
- Drafts referral letters, lab work requests, and shift handover reports
- Translates discharge summaries into patient's native language

**5. Administrative burden reduction**
- 66% of US physicians were already using some form of AI at work in 2024 — a 78% jump from 2023 (Source: AMA Survey, 2024)
- 62% of physicians cited bureaucratic/documentation tasks as the main driver of burnout (Source: Medscape Physician Burnout Report 2024)
- 72% of AI-using clinicians rely on AI specifically for documentation support, reporting 1–4 hours saved per day (Source: Practice survey via topflightapps.com, 2024)

---

### Q32 — How effective are existing AIs that doctors use? (LOCKED)

**Diagnostic accuracy — peer-reviewed evidence:**
- ChatGPT alone: 92% median diagnostic accuracy on standardised clinical vignettes (Source: JAMA Network Open, 2024 — UVA/Stanford/Harvard RCT)
- Doctors using ChatGPT: 76.3% median accuracy; doctors without AI: 73.7% accuracy
- Claude AI outperforms ChatGPT, Google Bard, and Perplexity in relevance (avg score 3.64) and completeness (avg score 3.43) across complex medical decision-making scenarios (Source: PMC comparative study, 2024)
- Claude and Manus demonstrate higher diagnostic performance and response stability compared to ChatGPT in dental clinical scenarios, though differences did not reach statistical significance (Source: PMC, 2025)

**Critical finding — the human-AI collaboration paradox:**
- Adding a human physician to ChatGPT actually *reduced* diagnostic accuracy compared to ChatGPT alone, though it improved efficiency
- Primary reason: doctors were not trained to use AI effectively — many treated ChatGPT as a search engine rather than a reasoning partner
- Conclusion from JAMA study authors: *"We need formal training in how best to use AI"* — structured prompts dramatically improve AI diagnostic output

**Documentation effectiveness:**
- AI clinical summarization reduces chart review time measurably across multiple real-world deployments
- LLM-generated discharge summaries rated high on comprehensiveness and conciseness by physicians
- 100% of primary care physicians surveyed agreed AI discharge summary system met their needs; 70% felt comfortable and 30% felt *very* comfortable with AI-generated summaries reviewed by doctors (Source: PMC, 2025)

**Known limitations:**
- LLMs can hallucinate — generating plausible but factually incorrect clinical statements
- High variability in text consistency across AI models (median range 26–68%) (Source: PMC cross-sectional study, 2024)
- Performance degrades in real-world scenarios with incomplete, noisy, or ambiguous patient data
- AI performs better on structured inputs — unstructured verbal descriptions reduce accuracy

---

### Q33 — For what specific tasks do doctors use existing AIs? (LOCKED)

Ranked by adoption frequency based on AMA survey and deployment evidence:

| Task | AI Used | Evidence |
|---|---|---|
| Clinical note generation / ambient scribing | DAX Copilot, Nuance, Abridge, Epic AI | 66% of physicians using AI in 2024 (AMA) |
| Chart summarization before patient visit | GPT-4 via Epic EHR, Claude | NYU Langone deployment, 2024 |
| Differential diagnosis generation | ChatGPT, Claude, Perplexity | JAMA RCT, 2024 |
| Discharge summary drafting | GPT-4, LLaMA3, Mistral | Multiple PMC studies, 2024-25 |
| Drug interaction and dosage checks | ChatGPT, clinical LLMs | AMA survey data |
| Patient message responses | GenAI in EHR portals | JAMA Network Open quality study, 2024 |
| Referral letter drafting | GenAI in EHR systems | TechTarget clinical AI review, 2024 |
| Shift handover report generation | GenAI | TechTarget, 2024 |

---

### Q35 — When doctors use LLMs, what information do they feed it — and how does that inform VitalNet's intake form design? (LOCKED)

**What doctors feed into LLMs — from the JAMA RCT and clinical studies:**

The cases used in the Stanford/UVA/Harvard trial included:
- Patient demographics (age, sex)
- Chief complaint
- History of present illness
- Physical examination findings
- Laboratory test results
- Vital signs

This is precisely the information structure that produces 92% diagnostic accuracy in ChatGPT alone.

**What this tells us about VitalNet's intake form:**

The intake form must capture the same information structure that produces accurate LLM reasoning — but simplified for an ASHA worker with Class 8-10 education:

| Clinical field | ASHA worker equivalent |
|---|---|
| Patient demographics | Age, sex, village, known conditions |
| Chief complaint | "Main problem today" — dropdown + free text |
| History of present illness | "How long has this been happening?" + symptom checklist |
| Vital signs | BP, temperature, SpO2, heart rate — manually entered |
| Physical findings | Simplified observation checklist (conscious/unconscious, breathing difficulty, visible swelling etc.) |
| Lab results | "Any recent tests?" — optional field |

The critical design insight: the intake form is not a medical form filled by a doctor. It is a structured data collection tool designed to produce input that a medical LLM can reason on accurately. Every field maps directly to what the LLM needs — nothing more, nothing less.

---

### Q36 — What do doctors say is missing from current LLM medical tools? (LOCKED)

From peer-reviewed literature and clinical deployment feedback:

**1. Structured input discipline**
Doctors using ChatGPT informally treat it like a search engine — typing vague questions rather than providing structured clinical context. The JAMA study found that unstructured use significantly underperforms structured prompting. What's missing: a forcing function that ensures complete, structured input before the LLM reasons.
*VitalNet's answer:* The intake form is that forcing function. The ASHA worker cannot submit incomplete data — the form ensures the LLM always receives the minimum viable clinical context.

**2. Hallucination detection**
LLMs can generate confident-sounding but factually incorrect clinical statements. NEJM AI published VeriFact in 2024 specifically to address this — an AI system that verifies LLM-generated clinical documents against EHR records.
*VitalNet's answer:* The explainability layer — SHAP-style rationale — shows what drove each output. A doctor reading "primary risk driver: SpO2 below 90% in patient over 60" can immediately verify whether that aligns with the intake data. Transparency is the partial substitute for automated verification.

**3. Continuity across visits**
Current LLM tools have no memory — each conversation starts fresh. A doctor using ChatGPT for a follow-up patient gets no benefit from prior interactions.
*VitalNet's answer:* The database layer. Every case is persisted. Future visits retrieve prior records. The LLM briefing for a returning patient includes prior triage history — something no existing consumer LLM tool provides.

**4. Output formatted for clinical workflow**
LLM responses are paragraphs of prose. Doctors operating under 5-minute consultation constraints need scannable structured output — not a wall of text.
*VitalNet's answer:* The doctor briefing is a structured card — triage badge, key symptoms, vitals, differentials, red flags, recommended tests — scannable in under 30 seconds.

**STATUS: Q31, Q32, Q33, Q35, Q36 ALL LOCKED**

---

---

## GROUP 5 — AI LAYER DESIGN

---

### Q22 — Why is a general-purpose LLM the right reasoning engine — why not a purpose-built medical model? (LOCKED)

**The landscape of medical vs general-purpose LLMs:**

LLMs in healthcare fall into two categories: general-purpose models fine-tuned for medical applications, and specialized models developed specifically for healthcare contexts. General-purpose models such as ChatGPT have demonstrated surprising proficiency in medical knowledge despite not being explicitly trained for healthcare applications.

Among 1,534 LLM instances evaluated in clinical medicine research from 2019-2025, the vast majority — 93.55% — were general-domain LLMs. Medical-domain LLMs accounted for only 6.45% of evaluated instances.

**Performance comparison — general vs medical-specific:**

- The best open base models as of January 2024 (Yi-34b and Qwen-72b) outperform Med-PaLM despite no specific training for medical tasks — demonstrating that general model capability correlates strongly with medical performance.
- Commercial models like GPT-4 and Med-PaLM-2 consistently achieve high accuracy across various medical datasets, demonstrating strong performance across different medical domains.

**Why general-purpose LLMs win for VitalNet specifically — four reasons:**

**Reason 1 — Availability and cost**
Purpose-built medical LLMs (Med-PaLM 2, Medical-LLM-78B, BioMedLM) are either proprietary, require significant compute to run locally, or are not accessible via free-tier APIs. Llama-3.3-70B on Groq is free, fast, and available right now. The performance gap between a well-prompted general LLM and a medical-specific LLM is narrower than the accessibility gap.

**Reason 2 — Domain breadth**
Medical-specific LLMs are typically fine-tuned on biomedical literature, clinical notes, and exam questions — optimised for answering structured medical knowledge questions. VitalNet's task is different: reasoning across symptoms, vitals, and patient history in plain language to produce a structured briefing for a rural doctor. This is a reasoning and summarisation task, not a knowledge retrieval task. General-purpose LLMs are better at this.

**Reason 3 — Prompt engineering compensates for domain gap**
Research from 2024 shows that even open-source LLMs can approach GPT-4's QA performance when augmented with retrieval of trusted information. The best results often combine the model's reasoning with retrieval of trusted information. VitalNet's structured clinical JSON prompt is the equivalent — it feeds the LLM exactly the context it needs to reason accurately, compensating for the absence of medical fine-tuning.

**Reason 4 — Generalisation across conditions**
Rural triage is not single-domain. A patient presenting to an ASHA worker could have a cardiac event, respiratory infection, neurological symptom, or obstetric emergency. Medical-specific LLMs fine-tuned on narrow corpora may underperform on edge cases outside their training distribution. A general-purpose LLM with broad world knowledge handles cross-domain reasoning more reliably.

**One-sentence lock:**
> *A general-purpose LLM with a structured clinical prompt outperforms a purpose-built medical model for VitalNet's use case because the task is cross-domain clinical reasoning, not medical knowledge retrieval — and because free-tier general LLMs are accessible now while purpose-built medical LLMs are not.*

**STATUS: LOCKED**

---

### Q23 — What are the failure modes of LLM-based medical reasoning — and how does the system handle them? (LOCKED)

**Known failure modes from peer-reviewed evidence:**

**Failure Mode 1 — Hallucination**
LLMs can generate plausible but factually incorrect clinical statements with high confidence. In a medical context, a confidently stated incorrect differential diagnosis could lead to harmful clinical decisions.
*VitalNet's mitigation:* The explainability layer shows what data drove the output. A doctor reading "primary risk driver: SpO2 below 90% in patient over 60" can immediately verify that against the intake form. Transparency forces human verification before action.

**Failure Mode 2 — Degraded performance on incomplete input**
The nature of evaluation is adapting — beyond just accuracy, there is interest in qualitative assessments like consistency and lack of hallucination. LLM performance degrades in real-world scenarios with incomplete, noisy, or ambiguous patient data.
*VitalNet's mitigation:* The intake form enforces minimum required fields before submission. The system cannot send incomplete data to the LLM — the form is the quality gate.

**Failure Mode 3 — High variability across responses**
The same clinical input can produce meaningfully different outputs across LLM calls — inconsistency is a documented problem in clinical LLM deployment.
*VitalNet's mitigation:* Temperature is set low (0.1–0.2) for the diagnostic reasoning call — forcing deterministic, consistent output. The triage classifier is a separate scikit-learn model, not an LLM, providing a stable classification independent of LLM variability.

**Failure Mode 4 — Overconfidence without uncertainty communication**
LLMs do not natively communicate uncertainty — they generate text at the same confidence level regardless of how ambiguous the clinical picture is.
*VitalNet's mitigation:* The prompt explicitly instructs the LLM to flag uncertainty — "if information is insufficient to determine risk level, state this explicitly and list what additional information is needed." This is prompt-level uncertainty handling.

**Failure Mode 5 — Misuse of output as definitive diagnosis**
The biggest systemic risk: ASHA workers or doctors treating LLM output as a final diagnosis rather than a decision support tool.
*VitalNet's mitigation:* Every output card carries a fixed disclaimer — "This is an AI-generated clinical briefing for decision support only. Final diagnosis requires qualified medical examination." This is non-removable UI text, not a popup that can be dismissed.

**STATUS: LOCKED**

---

### Q24 — What is the prompt engineering strategy? (LOCKED)

**Core principle:**
The prompt is not a question. It is a structured clinical handoff — the same information a senior doctor would give a junior doctor before seeing a patient.

**Prompt architecture — three layers:**

**Layer 1 — System prompt (fixed, never changes)**
```
You are a clinical decision support assistant operating in rural Indian 
primary healthcare. You receive structured patient intake data collected 
by an ASHA worker. Your task is to generate a structured doctor briefing 
that a PHC physician can review in under 30 seconds.

Rules:
- Never provide a definitive diagnosis. Provide differential diagnoses ranked by likelihood.
- Always flag red flags explicitly.
- Always state what additional information or tests would improve assessment.
- If input data is insufficient, state this explicitly — do not guess.
- Output must follow the exact JSON schema provided.
- Communicate uncertainty where it exists. Do not project false confidence.
```

**Layer 2 — Patient context (dynamic, built from intake form)**
```
Patient: {age}yr {sex}, {location}
Chief complaint: {chief_complaint}
Duration: {duration}
Vital signs: BP {bp}, Temp {temp}°C, SpO2 {spo2}%, HR {hr}bpm
Symptoms: {symptom_checklist}
Observations: {asha_observations}
Known conditions: {prior_conditions}
Current medications: {medications}
Recent tests: {recent_tests}
```

**Layer 3 — Output schema (structured JSON, not prose)**
```json
{
  "triage_level": "EMERGENCY | URGENT | ROUTINE",
  "primary_risk_driver": "plain English explanation of main risk signal",
  "differential_diagnoses": ["ranked list"],
  "red_flags": ["list of immediate warning signs"],
  "recommended_immediate_actions": ["list"],
  "recommended_tests": ["list"],
  "uncertainty_flags": "what information is missing that would improve assessment",
  "disclaimer": "AI-generated decision support only — requires qualified medical review"
}
```

**Why JSON output instead of prose:**
- Structured output maps directly to the doctor briefing card UI — no parsing ambiguity
- Each field is independently verifiable against the intake data
- Consistent schema enables database storage and future analytics
- Eliminates the "wall of text" failure mode from Q36

**STATUS: LOCKED**

---

### Q25 — What guardrails exist to prevent dangerous outputs? (LOCKED)

**Five-layer guardrail architecture:**

| Layer | Guardrail | Implementation |
|---|---|---|
| Input | Minimum required fields enforced | Form cannot submit without chief complaint, age, sex, and at least two vitals |
| Input | Range validation on vitals | BP, SpO2, HR, Temp validated against physiologically plausible ranges — outliers flagged before LLM call |
| Model | Temperature set to 0.1 | Forces deterministic, conservative output — minimises hallucination variance |
| Prompt | Explicit uncertainty instruction | System prompt instructs LLM to state insufficient data rather than guess |
| Output | Non-removable disclaimer | Every briefing card displays fixed disclaimer — AI decision support only, requires medical review |
| Output | Triage classifier is independent | Triage classification comes from scikit-learn model, not LLM — LLM cannot override the classifier |
| UI | Doctor confirmation required | Doctor must mark case as "reviewed" before it is archived — prevents passive acceptance of AI output |

**The critical architectural guardrail — triage independence:**
The triage classifier (Emergency/Urgent/Routine) is a separate scikit-learn model trained on structured vitals and symptom data. It operates independently of the LLM. The LLM explains and contextualises the triage decision — it does not make it. This means LLM hallucination cannot produce a dangerously incorrect triage level.

**STATUS: LOCKED**

---

### Q34 — What is the difference between how a trained doctor uses an LLM vs how an untrained ASHA worker would — and why does that gap matter? (LOCKED)

**How a trained doctor uses an LLM:**
- Provides complete, structured clinical context — symptoms, vitals, duration, history, exam findings
- Knows which differential diagnoses to probe — asks follow-up questions to narrow the list
- Evaluates LLM output critically — cross-references against clinical training
- Treats output as a second opinion, not a verdict
- Recognises when LLM output is plausible but wrong

**How an untrained ASHA worker would use an LLM without VitalNet:**
- Types a vague description — "patient has fever and chest pain"
- Cannot provide structured context — doesn't know what clinical details matter
- Cannot evaluate output quality — no clinical training to cross-reference against
- Likely to treat confident LLM output as definitive
- Cannot follow up intelligently — doesn't know which question narrows the differential

**Why this gap matters — and why it defines VitalNet's architecture:**
The JAMA RCT found that doctors using ChatGPT without structured prompting performed only marginally better than doctors without AI. The gap between expert and novice AI use is not the model — it is the quality of the input and the ability to evaluate the output.

VitalNet closes this gap with two mechanisms:
1. **The intake form** replaces the ASHA worker's clinical knowledge with a structured data collection protocol — she doesn't need to know what to ask, the form tells her
2. **The doctor as the evaluator** — the ASHA worker never sees the LLM output directly. The output goes to the doctor, who has the clinical training to evaluate it. The ASHA worker is the data collector. The doctor is the decision maker.

This separation of roles is the architectural answer to the gap. The ASHA worker doesn't need to understand AI — she needs to fill a form. The doctor doesn't need to trust AI blindly — she receives a structured briefing with explicit uncertainty flags and a disclaimer.

**One-sentence lock:**
> *VitalNet resolves the expert-novice AI usage gap not by training the ASHA worker to use AI, but by designing a system where she never has to — the intake form is her interface, and the doctor is the AI evaluator.*

**STATUS: Q22, Q23, Q24, Q25, Q34 ALL LOCKED**

---

---

## GROUP 6 — TRUST & ADOPTION

---

### Q37 — Why would a doctor trust an AI-generated patient briefing? (LOCKED)

**The trust problem stated honestly:**
Doctors are trained to be skeptical of unverified clinical information. An AI-generated briefing from an unknown system, based on data collected by a non-clinical worker, has every reason to be distrusted by default.

**What makes VitalNet's output credible enough to act on:**

**1. Transparency of source data**
The doctor briefing card always shows the raw intake data alongside the AI output — the patient's age, vitals, symptoms, and ASHA observations are visible. The doctor is not asked to trust the AI blindly. She is asked to review the AI's reasoning against the data that produced it. This is the same workflow as reviewing a junior doctor's case note.

**2. Explainability of the reasoning**
The primary risk driver is always stated in plain English — "SpO2 below 90% in patient over 60 with reported breathlessness." The doctor can immediately verify whether that claim matches the intake data. If it does, the briefing is credible. If it doesn't, the doctor overrides it. Either way, the doctor is in control.

**3. Triage classification is model-independent**
The triage level (Emergency/Urgent/Routine) comes from a separate scikit-learn classifier trained on structured vitals data — not from the LLM. Doctors reviewing the output know that the triage level is not a language model's opinion — it is a statistical model's output based on measurable clinical signals.

**4. Evidence from real-world deployments**
ASHAs logged into the ImTeCHO mobile application on 88% of working days, and all ASHAs demonstrated sufficient competency and expressed high acceptability of the mHealth intervention. When the tool demonstrably improves clinical workflow, trust follows utility.

**5. The briefing reduces cognitive load, not clinical autonomy**
The doctor is not being asked to outsource judgment. She is being given a structured pre-read that eliminates the blank-slate start. Every doctor intuitively understands the value of arriving at a consultation with context rather than without it. The briefing is a tool that makes the doctor faster and better informed — not one that replaces her.

**One-sentence lock:**
> *A doctor trusts the VitalNet briefing not because it is AI-generated but because every claim in it is traceable to source data she can verify in under 30 seconds — and because the triage classification that drives her priority decision comes from a statistical model, not a language model.*

**STATUS: LOCKED**

---

### Q38 — Why would an ASHA worker use this tool consistently? (LOCKED)

**The adoption failure pattern from research:**
While technology is often celebrated as a solution to healthcare inefficiencies, its impact on ASHAs tells a more complex story — digital tools both improve work processes and create new burdens and inequities. Tools that add work without adding value are abandoned. Tools that require training in a language the ASHA doesn't speak are abandoned. Tools that surveil rather than support are actively resisted.

**Four reasons VitalNet avoids these failure modes:**

**Reason 1 — It reduces her cognitive burden, not increases it**
Currently the ASHA worker must decide — with 23 days of training — whether a patient needs emergency referral, urgent referral, or routine care. That decision carries personal accountability and significant uncertainty. VitalNet's triage output gives her a structured recommendation she can act on and cite. The tool takes the weight of the ambiguous decision off her shoulders.

**Reason 2 — It fits her existing workflow**
ASHAs were already using WhatsApp and YouTube. The ASHABot team saw an inflection point — new digital users ready for something more. ASHA workers are not technology-averse — they are form-averse when forms add work without visible benefit. VitalNet's intake form produces an immediate output — triage classification — that the ASHA worker sees before the doctor does. She gets value from the tool in real time, not just the doctor.

**Reason 3 — It is designed for her literacy level**
The most challenging aspect of training is addressing the language issue — for those who understand Khasi, keep one session for them; for Hindi speakers, a separate session. VitalNet's intake form is in the ASHA worker's regional language. Every field uses plain language, not clinical terminology. The form is designed to be completable with zero medical training.

**Reason 4 — Evidence of high ASHA app adoption when tools are genuinely useful**
The ImTeCHO mHealth intervention achieved 88% daily login rate among ASHAs, with all workers demonstrating sufficient competency and expressing high acceptability. ASHA workers adopt tools that make their job easier and more credible within their community. VitalNet does both — it makes triage decisions faster and gives the ASHA worker a structured record that demonstrates her professionalism.

**One-sentence lock:**
> *An ASHA worker uses VitalNet consistently because it reduces the most stressful part of her job — the ambiguous referral decision — while fitting her existing digital habits, operating in her language, and giving her immediate visible value before the output ever reaches the doctor.*

**STATUS: LOCKED**

---

### Q39 — What happens when the AI is wrong — who is accountable and how does the system communicate uncertainty? (LOCKED)

**Stated honestly — this is the hardest question in Group 6.**

LLMs will produce incorrect outputs. The triage classifier will misclassify edge cases. The question is not whether the system will be wrong — it will be. The question is what happens when it is.

**Accountability architecture:**

| Role | Responsibility | What they cannot delegate |
|---|---|---|
| ASHA worker | Accurate data collection | She is accountable for what she enters — not for the AI's interpretation of it |
| VitalNet system | Transparent, explainable output with uncertainty flags | Cannot make clinical decisions — outputs are labeled decision support, not diagnosis |
| Doctor | Clinical judgment and final decision | She reviews the briefing, verifies against her examination, and decides. The AI output does not bind her |

**The fundamental accountability principle:**
VitalNet does not diagnose. It briefs. The distinction is not semantic — it is architectural. Every output is labeled "AI-generated clinical briefing for decision support only." The doctor's examination and judgment supersede the briefing in every case. If the AI is wrong and the doctor catches it — the system worked as designed. If the doctor does not catch it — that is a failure of clinical workflow, not uniquely a failure of AI.

**How the system communicates uncertainty:**

**1. Uncertainty flags in every output**
The JSON output schema includes a mandatory `uncertainty_flags` field — "what information is missing that would improve this assessment." A briefing generated from incomplete vitals will always flag what was missing.

**2. Confidence-correlated language in LLM output**
The system prompt instructs the LLM to use qualified language when data is insufficient — "insufficient data to determine cardiac risk — SpO2 not provided" rather than generating a confident-sounding but unsupported claim.

**3. Triage classifier confidence score**
The scikit-learn classifier outputs a probability alongside the classification — Emergency (87% confidence) vs Emergency (52% confidence) communicate very different levels of certainty to a reviewing doctor.

**4. Non-removable disclaimer on every briefing card**
"This is an AI-generated clinical briefing for decision support only. Final diagnosis requires qualified medical examination." This cannot be dismissed, minimized, or removed by the user.

**One-sentence lock:**
> *When the AI is wrong, the doctor is the safeguard — VitalNet is designed so that every output is transparent enough to be verified, every uncertainty is flagged explicitly, and no clinical decision can be made without a qualified human reviewing and overriding the AI's output.*

**STATUS: Q37, Q38, Q39 ALL LOCKED**

---

---

## GROUP 7 — INDIA-SPECIFIC REALITY

---

### Q40 — What connectivity can we realistically assume in rural India? (LOCKED)

**The headline number vs the ground reality:**

- As of April 2024, 612,952 out of 644,131 villages have 3G/4G mobile connectivity — 95.15% of villages have internet access (Source: Ministry of Communications, Government of India, 2024)
- Rural wireless teledensity is just 57.89% compared to 124.31% in urban areas as of December 2024 (Source: TRAI, via LightReading, 2025)

**Coverage ≠ reliable connectivity. The three-layer problem:**

1. **Coverage layer** — 95% of villages have a tower nearby. True.
2. **Subscription layer** — Rural teledensity of 57.89% means not every person in that village is a subscriber. Many ASHA workers report spending their own money on mobile data — a documented grievance in 2024 protests.
3. **Quality layer** — In a typical village, one might have only 1–2 mobile operators with a strong signal, often just 4G. If too many users share a single cell tower, speeds can be slow. Indoor connectivity in dense construction or hilly terrain is significantly worse than outdoor coverage figures suggest.

**VitalNet's connectivity assumption:**

VitalNet assumes **intermittent 4G** as the baseline — available most of the time outdoors, unreliable indoors and in geographically challenging terrain. The system is designed accordingly:

| Scenario | VitalNet behaviour |
|---|---|
| 4G available | Full flow — form submits, triage fires, LLM generates briefing, doctor dashboard updates in real time |
| Weak 3G | Form submits with delay — triage classifier runs first (local-weight model), LLM call queued |
| Offline | Form data saved locally in browser storage — submitted automatically when connection returns |
| Voice note offline | Audio cached locally — transcribed via API when connectivity returns |

**Why offline-first matters for the demo:**
Hackathon venue WiFi is notoriously unreliable. The offline-first architecture is not just a rural India design decision — it is a demo resilience decision. The core triage classification must work without internet.

**STATUS: LOCKED**

---

### Q41 — What language does an ASHA worker operate in? (LOCKED)

**The linguistic reality of rural India:**

India has 22 scheduled languages and hundreds of dialects. ASHA workers operate in their regional mother tongue — not Hindi, not English. The most common languages by ASHA worker population:

| State | Primary language | ASHA worker concentration |
|---|---|---|
| Uttar Pradesh | Hindi / Awadhi / Bhojpuri | Largest ASHA workforce in India |
| Bihar | Hindi / Maithili / Bhojpuri | High concentration |
| Madhya Pradesh | Hindi / Bundeli | Significant |
| Rajasthan | Hindi / Marwari | Significant |
| Maharashtra | Marathi | Large |
| Tamil Nadu | Tamil | Significant |
| West Bengal | Bengali | Significant |
| Odisha | Odia | Growing |

**English literacy among ASHA workers:**
Minimum education requirement is Class 10 (relaxed to Class 8 where needed). English is taught in schools but functional English literacy for form-filling and medical terminology is not a realistic assumption for the majority of ASHA workers.

**VitalNet's language design decision:**

- **Intake form:** Built in regional language with a language selector at launch — initially supporting Hindi, Tamil, Telugu, Bengali, Marathi. English as default fallback.
- **Field labels:** Plain language, zero medical terminology — "Main complaint today" not "Chief presenting complaint"
- **Voice input:** Sarvam AI as primary STT for Indic languages — Whisper as fallback for Hindi/English
- **Doctor briefing output:** English — PHC doctors are English-literate and clinical English is the standard for medical records in India

**The asymmetry is intentional:**
Input in the ASHA worker's language. Output in the doctor's language. The translation layer sits inside VitalNet's processing pipeline — the LLM receives structured JSON regardless of what language the ASHA worker used to fill the form.

**STATUS: LOCKED**

---

### Q42 — What device does an ASHA worker actually carry? (LOCKED)

**Verified device reality:**

- State governments distribute free smartphones to ASHA workers — Himachal Pradesh distributed smartphones enabling workers to use apps like Himarogya, TB Mukt Himachal App, and RCH Portal (Source: Tribune India, 2020)
- ASHA workers across India have been demanding a smartphone with internet connectivity to enter data, calling it a crucial part of their work — many currently spend their own money on mobile data (Source: Missing Perspectives, October 2024)
- Device tier: government-issued Android smartphones — entry-level to mid-range, typically 2-3GB RAM, Android 10-12, small to medium screen (5–6 inch)
- Not all states have issued devices — in states without government-issued phones, ASHA workers use personal devices of equivalent or lower spec

**VitalNet's device design constraint:**

The intake form must run reliably on:
- 2GB RAM Android device
- Android 10 minimum
- Chrome Mobile browser — no app installation required
- Screen size: 5 inch minimum
- Slow touch response — large tap targets, no small UI elements
- No keyboard assumed — form uses dropdowns, checkboxes, and number inputs wherever possible over free text

**Why a web app, not a native Android app:**
- No Play Store installation required — zero friction adoption
- Works on any Android with Chrome — no device-specific compatibility issues
- Updates deploy instantly — no app update required
- Runs within existing NHM app ecosystem via browser link

**STATUS: LOCKED**

---

### Q43 — How does the prototype handle patient data privacy? (LOCKED)

**The honest position for a hackathon prototype:**

VitalNet's abstract promises zk-SNARKs, federated learning, and decentralized identity. None of these are in the prototype. The prototype handles patient data as follows — and this must be stated honestly in the R&D document:

**What the prototype does:**
- Patient data entered in the intake form is transmitted over HTTPS to the FastAPI backend
- Data is stored in a local SQLite database on the demo machine
- No data is transmitted to any third party except the LLM API (Groq/Gemini) for reasoning
- LLM API calls contain anonymised clinical data — no patient name, no Aadhaar, no personally identifying information beyond age, sex, and location (village level, not address)
- Data is not persisted beyond the demo session in the prototype

**What the prototype does not do:**
- No encryption at rest
- No access control beyond the demo session
- No audit log of who accessed patient records
- No patient consent mechanism

**How this is framed in the R&D document:**
The privacy layer is Phase 2 infrastructure. The prototype demonstrates the intelligence layer — the part that must work before privacy infrastructure has anything to protect. The clinical JSON schema used in the prototype is designed to be privacy-compatible — no PII fields that cannot be replaced with anonymised identifiers in production. The swap from demo privacy to production privacy is a configuration change, not an architectural rebuild.

**STATUS: Q40, Q41, Q42, Q43 ALL LOCKED**

---

---

## GROUP 8 — TECH STACK

---

### Layer 2 — Backend Framework (LOCKED)

**Evaluation factors (in order of weight):**
1. Development speed — solo build, 24 hours
2. Python compatibility — classifier, SHAP, HuggingFace all Python
3. Async support — LLM calls take 1–5 seconds, blocking is unacceptable
4. RAM footprint — 4GB total, shared with browser, VSCode, frontend dev server
5. Community and documentation — debugging at 3am
6. Cold start time — iteration speed during development

**Options evaluated:**

| Option | Dev Speed | Python | Async | RAM | Community | Cold Start |
|---|---|---|---|---|---|---|
| FastAPI | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★☆ | ★★★★☆ | ★★★★★ |
| Flask | ★★★★☆ | ★★★★★ | ★★☆☆☆ | ★★★★★ | ★★★★★ | ★★★★★ |
| Express.js | ★★★☆☆ | ✗ | ★★★★★ | ★★★★☆ | ★★★★★ | ★★★★★ |
| Django | ★★☆☆☆ | ★★★★★ | ★★★☆☆ | ★★☆☆☆ | ★★★★★ | ★★☆☆☆ |
| Hono | ★★★☆☆ | ✗ | ★★★★★ | ★★★★★ | ★★☆☆☆ | ★★★★★ |

**Rejected options — explicit reasoning:**

- **Flask:** Non-native async is a direct demo liability. LLM calls take 1–5 seconds — a blocking Flask endpoint freezes the doctor dashboard while the LLM processes. Unacceptable demo risk.
- **Express.js:** Zero Python compatibility. Triage classifier and SHAP are Python — calling them from Node requires subprocess calls or a separate microservice. Doubles architecture complexity for zero benefit.
- **Django:** 120–200MB idle RAM on a 4GB machine is a meaningful cost. 3–5 second cold start slows development iteration. Vastly overengineered for an API-only backend.
- **Hono:** Same Python boundary problem as Express. Thin community means debugging edge cases at 3am during the hackathon is high-risk.

**Verdict: FastAPI**

**Rationale:**
FastAPI is the most flexible and lightweight framework for AI/ML and LLM workloads with pure API endpoint architecture. It is the only option that is simultaneously Python-native, async-first, lightweight enough for 4GB RAM, fast to develop with, and well-documented. Auto-generated interactive API docs at `/docs` eliminates the need for Postman during development — every endpoint is immediately testable.

**One-sentence lock:**
> *FastAPI is the only backend option that is Python-native, async-first, lightweight enough for 4GB RAM, and fast enough to iterate on in 24 hours — Flask's non-native async is a direct demo liability when every LLM call blocks for 1–5 seconds.*

**STATUS: LOCKED**

---

### Layer 3 — Database (LOCKED)

**Evaluation factors (in order of weight):**
1. Zero setup time — no installation or server process
2. RAM footprint — shared with everything else on 4GB
3. Python compatibility — clean FastAPI integration
4. Demo resilience — must work without internet
5. Persistence — survives server restarts
6. Future FHIR and production compatibility

**Options evaluated:**

| Factor | SQLite | PostgreSQL | MongoDB | Firebase | Supabase |
|---|---|---|---|---|---|
| Zero setup | ★★★★★ | ★★☆☆☆ | ★★★☆☆ | ★★★★☆ | ★★★★☆ |
| RAM footprint | ★★★★★ | ★★★☆☆ | ★★☆☆☆ | ★★★★★ | ★★★★★ |
| Python compatibility | ★★★★★ | ★★★★★ | ★★★★☆ | ★★★☆☆ | ★★★★☆ |
| Demo resilience | ★★★★★ | ★★★★★ | ★★★★☆ | ★★☆☆☆ | ★★☆☆☆ |
| FHIR compatibility | ★★★★☆ | ★★★★★ | ★★☆☆☆ | ★★☆☆☆ | ★★★★★ |

**Rejected options — explicit reasoning:**

- **Firebase & Supabase:** Internet dependency for every database operation. If venue WiFi drops during demo, the entire data layer becomes unreachable. Single point of failure that cannot be accepted in a live demo environment.
- **MongoDB:** Schemaless flexibility is a feature we don't need — the clinical JSON schema is already defined. RAM cost of 100–200MB for mongod process is a liability we can't afford.
- **PostgreSQL:** Everything it offers over SQLite is relevant in production, none of it is relevant in a 24-hour prototype. Setup cost and RAM overhead are unjustifiable.

**On the dual DB architecture (SQLite + Supabase):**
Technically sound as a production pattern — write locally always, sync to Supabase when connectivity available. Rejected for the hackathon build because it introduces two failure modes, sync conflict logic, and extra setup time for zero visible benefit to judges. Supabase is documented as Phase 2 infrastructure — the schema is designed Supabase-compatible from day one, making migration a connection string change, not an architectural rebuild.

**Verdict: SQLite**

**One-sentence lock:**
> *SQLite is the correct database for this prototype — zero setup, zero RAM overhead, ships with Python, survives venue WiFi failure, and the schema designed today migrates to Supabase and PostgreSQL in production with a single connection string change.*

**Phase 2 note:** Supabase integration enables real-time multi-clinic sync, cloud persistence, and FHIR API compatibility — documented in roadmap, not built in prototype.

**STATUS: LOCKED**

---

### Layer 4 — LLM API (LOCKED)

**Evaluation factors (in order of weight):**
1. Speed — response latency directly affects demo experience
2. Free tier reliability — rate limits and quota under demo conditions
3. Model quality — clinical reasoning and structured JSON output
4. API stability — uptime and predictability
5. Fallback viability — independent failure modes
6. JSON output support — native structured output mode

**Options evaluated:**

| Factor | Groq | Gemini | OpenRouter | HuggingFace | Groq+Gemini |
|---|---|---|---|---|---|
| Speed | ★★★★★ | ★★★★☆ | ★★★☆☆ | ★★☆☆☆ | ★★★★★ |
| Free tier reliability | ★★★★☆ | ★★★★☆ | ★★★☆☆ | ★★★☆☆ | ★★★★★ |
| Model quality | ★★★★★ | ★★★★☆ | ★★★☆☆ | ★★★☆☆ | ★★★★★ |
| API stability | ★★★★☆ | ★★★★★ | ★★★☆☆ | ★★★☆☆ | ★★★★★ |
| Fallback viability | ★★★☆☆ | ★★★★☆ | ★★☆☆☆ | ★★☆☆☆ | ★★★★★ |
| JSON output | ★★★★★ | ★★★★★ | ★★★☆☆ | ★★★☆☆ | ★★★★★ |

**Rejected options — explicit reasoning:**

- **OpenRouter:** Two independent failure points — OpenRouter itself and the underlying model. Unpredictable latency. Free tier models are smaller and older. Not reliable enough for a live demo.
- **HuggingFace as primary LLM:** Cold start latency of 10–30 seconds on free tier is demo-killing. Retained for specific tasks only — Bio_ClinicalBERT for medical entity extraction where cold start is tolerable.
- **Groq alone:** Single point of failure. Rate limits documented under heavy usage — multiple rapid demo requests can trigger throttling.
- **Gemini alone:** Free tier quotas tightened significantly in December 2025. 250 RPD on Gemini 2.5 Flash makes it unreliable as a sole primary.

**Current Gemini model landscape (verified March 2026):**
- Gemini 1.5 Flash — DEPRECATED, do not use
- Gemini 2.5 Flash — current stable production model, 10 RPM / 250 RPD free tier
- Gemini 2.5 Flash-Lite — highest free quota, 15 RPM / 1000 RPD, slightly lower quality

**Three-tier fallback architecture:**

```
Primary    → Groq (Llama-3.3-70B)     — fastest, ~2s response, 14,400 req/day
Fallback 1 → Gemini 2.5 Flash         — 10 RPM / 250 RPD free, stable quality
Fallback 2 → Gemini 2.5 Flash-Lite    — 15 RPM / 1000 RPD free, graceful degradation
```

Key rotation logic: on 429 rate limit or timeout from primary → automatically retry with Fallback 1 → on second failure → Fallback 2. Implementation is ~15 lines of retry logic in FastAPI backend. Quality degrades gracefully — never fails completely.

**Verdict: Groq (Llama-3.3-70B) primary + Gemini 2.5 Flash fallback 1 + Gemini 2.5 Flash-Lite fallback 2**

**One-sentence lock:**
> *Groq's Llama-3.3-70B is the primary LLM — fastest free tier available at under 2 seconds per response — with Gemini 2.5 Flash and Gemini 2.5 Flash-Lite as sequential fallbacks on rate limit or failure, giving VitalNet three independent API options and graceful quality degradation rather than total failure during a live demo.*

**STATUS: LOCKED**

---

### Layer 5 — Triage Classifier (LOCKED)

**Evaluation factors (in order of weight):**
1. Explainability — abstract explicitly promises explainable AI output
2. Training speed — must be trainable on synthetic dataset quickly
3. Inference speed — fires before LLM call, must return in milliseconds
4. Accuracy on structured tabular data — vitals and symptom flags are tabular
5. LLM independence — triage level must not be LLM-generated (guardrail from Q25)
6. Pre-trainability — trainable before hackathon, saved as .pkl, loaded at runtime

**Options evaluated:**

| Factor | Gradient Boost | Random Forest | Logistic Reg | LLM-only | Rule-based |
|---|---|---|---|---|---|
| Explainability | ★★★★★ | ★★★★☆ | ★★★★★ | ★★★☆☆ | ★★★★★ |
| Training speed | ★★★★☆ | ★★★★★ | ★★★★★ | N/A | N/A |
| Inference speed | ★★★★★ | ★★★★★ | ★★★★★ | ★★☆☆☆ | ★★★★★ |
| Accuracy | ★★★★★ | ★★★★☆ | ★★★☆☆ | ★★★☆☆ | ★★★☆☆ |
| LLM independence | ★★★★★ | ★★★★★ | ★★★★★ | ✗ | ★★★★★ |
| Abstract alignment | ★★★★★ | ★★★★☆ | ★★★☆☆ | ★★★☆☆ | ★★☆☆☆ |

**Rejected options — explicit reasoning:**

- **LLM-only:** Violates critical guardrail from Q25. A patient with SpO2 of 82% classified Routine because the LLM misread the JSON is an unacceptable failure mode. Triage must be independent of the LLM.
- **Rule-based:** Cannot generalise to unseen vital sign combinations. Directly contradicts the ML-based triage claim in the abstract.
- **Logistic Regression:** Clinical risk is non-linear. BP and SpO2 interact multiplicatively — a linear model misses the interactions that matter most in triage.
- **Random Forest:** Viable but Gradient Boosting wins on accuracy and SHAP precision. Training time difference on a 5000-row synthetic dataset is negligible.

**Training strategy — Google Colab free tier:**

The 4GB Pentium never trains anything. Training runs entirely on Google Colab free tier pre-hackathon:

- Colab free tier provides NVIDIA T4 GPU (16GB VRAM), ~12 hours session
- Synthetic dataset generated locally (lightweight Python script, runs on Pentium)
- Dataset uploaded to Colab → GradientBoostingClassifier trained → SHAP explainer computed on T4 GPU
- `triage_model.pkl` + `shap_explainer.pkl` saved and downloaded to local machine
- At hackathon: model loads and runs inference in under 5ms — zero training time, zero RAM overhead for training

**Colab additional capability (noted, not prioritised):**
If a local fallback is needed when all APIs fail, Colab also enables fine-tuning a smaller medical LLM (e.g. Mistral-7B on clinical triage data) as a pre-hackathon option. Not in scope for the prototype but a viable Phase 2 path.

**Verdict: Gradient Boosting (sklearn GradientBoostingClassifier) + SHAP, trained on Google Colab free tier**

**One-sentence lock:**
> *Gradient Boosting with SHAP is the only classifier that simultaneously achieves state-of-the-art accuracy on structured tabular vitals data, produces precise feature attribution satisfying the abstract's explainability requirement, and operates completely independently of the LLM — trained on Google Colab's free T4 GPU pre-hackathon so the Pentium only runs inference at under 5ms.*

**STATUS: LOCKED**

---

### Layer 6 — Medical Entity Extraction (LOCKED)

**Context — why this layer exists:**
Primary input is a structured form — data arrives pre-structured. This layer exists exclusively for the secondary voice input path — transcribed voice notes need entity extraction before merging into the clinical JSON schema.

**Evaluation factors (in order of weight):**
1. RAM footprint on constrained hardware — 4GB Pentium shared with everything else
2. Clinical NLP accuracy — correctly identifies symptoms, conditions, severity, body parts
3. API availability — cold start risk on free tier
4. Bypass gracefully — failure must never block the triage pipeline
5. Environment adaptability — behaviour must differ between local and hosted deployment

**Options evaluated:**

| Factor | Bio_ClinicalBERT (API) | medspaCy (local) | scispaCy (local) | LLM-direct |
|---|---|---|---|---|
| RAM footprint | ★★★★★ | ★★★☆☆ | ★★★☆☆ | ★★★★★ |
| Clinical accuracy | ★★★★★ | ★★★★☆ | ★★★★☆ | ★★★★☆ |
| API availability | ★★★☆☆ | ★★★★★ | ★★★★★ | ★★★★★ |
| Bypass gracefully | ★★★★★ | N/A | N/A | N/A |
| Environment adapt | ★★★★★ | ★★★☆☆ | ★★★☆☆ | ★★★★★ |

**Architecture — environment-aware extraction layer:**

Deployment environment detected via single `.env` flag — `DEPLOYMENT_ENV=local` or `DEPLOYMENT_ENV=hosted`. Extraction layer initialises accordingly at startup:

```
DEPLOYMENT_ENV detected at startup
        ↓
    ┌─────────────────────────────────────────┐
    │ LOCAL (Pentium, 4GB RAM)                │
    │ Bio_ClinicalBERT via HuggingFace API    │
    │ → Zero local RAM cost                   │
    │ → 5s timeout → bypass to LLM-direct     │
    ├─────────────────────────────────────────┤
    │ HOSTED (Railway / Digital Ocean)        │
    │ medspaCy (local, instant) runs first    │
    │ + Bio_ClinicalBERT API augments result  │
    │ → Combined extraction, best accuracy    │
    │ → Bio_ClinicalBERT timeout → medspaCy   │
    │   result used alone                     │
    └─────────────────────────────────────────┘
        ↓ (both paths)
Extracted entities merged into clinical JSON schema
        ↓
If extraction fails entirely → raw transcription
appended to LLM prompt as "ASHA voice note: {text}"
        ↓
LLM reasoning call proceeds — never blocked
```

**Indic language handling:**
Bio_ClinicalBERT and medspaCy are English-only. Indic language transcriptions are translated to English via a single Groq call (already in stack) before extraction. Translation adds ~1 second — acceptable for secondary input path.

**Rejected options — explicit reasoning:**
- **scispaCy alone:** Optimised for scientific/biomedical text rather than conversational clinical language an ASHA worker uses. Same RAM problem as medspaCy without the clinical conversation advantage.
- **LLM-direct as dedicated layer:** Rejected in favour of dedicated extraction — structured extraction produces cleaner JSON schema population than LLM free-form extraction. LLM-direct retained as final bypass only.

**Production upgrade path (Phase 2):**
When server-grade infrastructure is available, replace keyword matching with full medspaCy + Bio_ClinicalBERT pipeline across all deployment environments. Add fine-tuned Indic clinical NER model when training data becomes available through clinic partnerships.

**Verdict: Environment-aware — Bio_ClinicalBERT API (local) + medspaCy + Bio_ClinicalBERT combined (hosted), with LLM-direct bypass on all failure paths**

**One-sentence lock:**
> *The extraction layer is environment-aware — local deployment uses Bio_ClinicalBERT via HuggingFace API to avoid RAM overhead on the Pentium, hosted deployment activates the full medspaCy + Bio_ClinicalBERT pipeline for maximum accuracy, and both paths share identical bypass logic ensuring voice input never blocks triage regardless of extraction outcome.*

**STATUS: LOCKED**

---

### Layer 1 — Frontend Framework (LOCKED)

**Evaluation factors (in order of weight):**
1. Development speed — solo, 24 hours, two distinct UIs needed
2. Multilingual form support — regional language switching core requirement
3. Real-time updates — doctor dashboard needs live case updates
4. RAM footprint — dev server competes with FastAPI, browser, VSCode on 4GB
5. Build complexity — zero config preferred
6. Component reusability — intake form and dashboard share UI patterns
7. Deployment simplicity — local AND Vercel/Netlify compatible

**Options evaluated:**

| Factor | React+Vite | Next.js | Vanilla JS | Svelte | Vue+Vite | Preact+Vite |
|---|---|---|---|---|---|---|
| Dev speed | ★★★★★ | ★★★☆☆ | ★★★☆☆ | ★★★★☆ | ★★★★☆ | ★★★★★ |
| Multilingual | ★★★★★ | ★★★★☆ | ★★★☆☆ | ★★★☆☆ | ★★★★★ | ★★★★★ |
| Real-time updates | ★★★★☆ | ★★★★★ | ★★★☆☆ | ★★★★★ | ★★★★☆ | ★★★★☆ |
| RAM footprint | ★★★☆☆ | ★★☆☆☆ | ★★★★★ | ★★★★☆ | ★★★☆☆ | ★★★★☆ |
| Build complexity | ★★★★☆ | ★★★☆☆ | ★★★★★ | ★★★★☆ | ★★★★☆ | ★★★★☆ |
| Familiarity risk | None | Low | None | High | Medium | None |
| Deployment | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★☆ | ★★★★☆ | ★★★★☆ |

**Rejected options — explicit reasoning:**

- **Next.js:** Overkill for a form and dashboard. Server component complexity, hydration concerns, and App Router cognitive overhead cost hours in a solo 24-hour build. SSR benefits irrelevant here.
- **Vanilla JS:** Building a multilingual form with validation AND a real-time priority dashboard in Vanilla JS solo in 24 hours is significantly more work than React. State management becomes manual and error-prone. TabVolt used Vanilla JS successfully because it was a single-page extension with no complex state — VitalNet has two distinct UIs, language switching, real-time polling, and form validation.
- **Svelte:** Viable but unfamiliar. Learning Svelte's reactivity model during a 24-hour hackathon is an unnecessary risk.
- **Vue + Vite:** Familiar but React is the stronger choice for component ecosystem depth and i18next integration maturity.
- **Preact + Vite:** Identical developer experience to React at lower RAM, but smaller ecosystem creates library compatibility risk. Not worth the uncertainty when React is already familiar.

**Verdict: React + Vite**

**One-sentence lock:**
> *React + Vite is the correct frontend choice — familiar enough to build fast under pressure, component-based architecture handles both the multilingual intake form and real-time doctor dashboard cleanly, and first-party Vercel support means deployment is a single command if hosting is needed.*

**STATUS: LOCKED**

---

### Layer 7 — Voice / STT (LOCKED)

**Evaluation factors (in order of weight):**
1. Indic language accuracy — primary use case is Hindi, Tamil, Telugu, Bengali voice notes
2. Latency — voice processing adds to an already multi-step pipeline
3. Free tier availability
4. Offline capability — consistent with offline-first architecture
5. Integration complexity — must wire cleanly into existing stack

**Options evaluated:**

| Factor | Web Speech | Sarvam AI | Whisper/Groq | Whisper Local | Web Speech+Sarvam |
|---|---|---|---|---|---|
| Indic accuracy | ★★☆☆☆ | ★★★★★ | ★★★★☆ | ★★★★☆ | ★★★★★ |
| Latency | ★★★★★ | ★★★★☆ | ★★★★★ | ★★☆☆☆ | ★★★★★ |
| Free tier | ★★★★★ | ★★★☆☆ | ★★★★★ | ★★★★★ | ★★★★☆ |
| Offline capability | ✗ | ✗ | ✗ | ✓ | ✗ |
| Already in stack | ✓ | ✗ | ✓ | ✗ | Partial |

**Rejected options — explicit reasoning:**

- **Whisper local:** 5–30 second latency on Pentium CPU is unacceptable for a voice note that should process quickly. Eliminated by hardware constraint.
- **Web Speech API alone:** Hidden internet dependency to Google's servers. Poor Indic language accuracy for Dravidian languages — unreliable for the primary use case.
- **Whisper via Groq alone:** Good Hindi accuracy but below Sarvam for Tamil, Telugu, Bengali. Retained as fallback since it requires no new API key or account.

**Three-tier STT architecture:**

```
ASHA worker records voice note
        ↓
Web Speech API → real-time visual feedback only
(waveform animation, "listening..." state)
NOT used for final transcription
        ↓
Sarvam AI API → primary transcription
(purpose-built for Indian languages, 100 min/month free)
        ↓
On Sarvam failure/timeout →
Whisper via Groq → fallback transcription
(already in stack, no new API key)
        ↓
On both failures → audio cached locally
Processed when connectivity returns
        ↓
Transcription → Indic→English translation if needed (Groq)
        ↓
Entity extraction layer (Layer 6)
```

**Key design decision — Web Speech API role:**
Web Speech is used exclusively as a visual UX layer — the ASHA worker sees real-time transcription feedback while recording. The actual transcription that enters the clinical JSON always comes from Sarvam or Whisper. Web Speech accuracy never affects clinical output.

**Verdict: Sarvam AI (primary) + Whisper via Groq (fallback) + Web Speech API (visual feedback only)**

**One-sentence lock:**
> *Sarvam AI is the primary STT engine — the only model purpose-built for rural Indian speech patterns across Dravidian and Indo-Aryan languages — with Whisper via Groq as automatic fallback using an already-present API key, and Web Speech API used exclusively for real-time visual feedback without contributing to the final transcription.*

**STATUS: LOCKED**

---

## GROUP 8 COMPLETE — FULL STACK SUMMARY

| Layer | Decision | Rationale |
|---|---|---|
| Layer 1 — Frontend | React + Vite | Familiar, component-based, multilingual i18next, Vercel-ready |
| Layer 2 — Backend | FastAPI (Python) | Python-native, async-first, lightweight, AI/ML workload optimised |
| Layer 3 — Database | SQLite (Supabase Phase 2) | Zero setup, zero RAM, offline-safe, FHIR-compatible schema |
| Layer 4 — LLM API | Groq primary + Gemini 2.5 Flash + Flash-Lite fallbacks | Speed + three-tier redundancy, zero single point of failure |
| Layer 5 — Classifier | Gradient Boosting + SHAP (Colab-trained) | Best tabular accuracy, explainable, LLM-independent, pre-trained |
| Layer 6 — Extraction | Environment-aware: HuggingFace API (local) / medspaCy+BERT (hosted) | RAM-adaptive, bypass on failure, never blocks triage |
| Layer 7 — Voice/STT | Sarvam AI + Whisper/Groq fallback + Web Speech UX | Best Indic accuracy, stack-native fallback, graceful degradation |

**Hosting strategy:**
- **Local-first** — entire stack runs on Pentium during development and as primary hackathon build
- **Demo option** — Railway (backend) + Vercel (frontend) via GitHub Student Pack
- **Nuclear fallback** — Digital Ocean VPS ($200 student credit) with Dokploy if Railway has issues

**STATUS: GROUP 8 ALL LOCKED ✓**

---

---

## GROUP 9 — FEASIBILITY & HONESTY

---

### Q26 — What is being simulated or mocked vs genuinely working? (LOCKED)

**Genuinely working — judges can interact with these:**

| Component | What actually happens |
|---|---|
| ASHA intake form | Real multilingual form, real validation, real submission |
| Input structuring | Real clinical JSON schema built from form data |
| Triage classification | Real Gradient Boosting model, real SHAP values, real prediction |
| LLM diagnostic briefing | Real Groq API call, real Llama-3.3-70B reasoning, real structured JSON output |
| Database persistence | Real SQLite write, real case record created |
| Doctor dashboard | Real case queue, real triage badges, real briefing display |
| Three-tier LLM fallback | Real key rotation logic, genuinely fires on rate limit |
| Voice recording | Real audio capture in browser |
| Web Speech visual feedback | Real real-time transcription display |

**Simulated or mocked — honest acknowledgment:**

| Component | Reality |
|---|---|
| Wearable vitals | Manually entered on form — no hardware |
| Federated learning | Architecture diagram only |
| zk-SNARKs / DID | Architecture diagram only |
| Kafka / Kubernetes | FastAPI directly — no message queue |
| IPFS / encrypted storage | SQLite locally — no decentralised storage |
| Multi-clinic deployment | Single local instance — no distributed nodes |
| FHIR integration | Schema FHIR-compatible but no live hospital system connected |
| Sarvam AI transcription | May fall back to Whisper/Groq depending on API warmth |
| Bio_ClinicalBERT extraction | May fall back to LLM-direct depending on HuggingFace cold start |
| Doctor authentication | No login system — demo assumes single doctor session |
| Patient consent mechanism | Not implemented — noted as production requirement |

**One-sentence lock:**
> *Everything a judge can interact with is genuinely working — form submission, triage classification, LLM briefing, database persistence, and dashboard updates are all real. Everything in the abstract that isn't interactable — federated learning, wearables, zk-SNARKs, Kafka — is represented in the architecture diagram and roadmap, not in the prototype.*

**STATUS: LOCKED**

---

### Q27 — What is the single most likely point of failure during the demo — and what is the fallback? (LOCKED)

**The single most likely failure: Groq rate limit during a multi-patient demo sequence.**

A judge watching the demo will ask to see multiple patient cases processed rapidly. Three LLM calls in under 2 minutes will hit Groq's per-minute rate limit. This is more likely than any other failure because it is triggered by demo success — the better the demo goes, the more the judge wants to see.

**Fallback chain:**

```
Groq returns 429
        ↓ automatic, under 500ms
Retry with Gemini 2.5 Flash
        ↓ if also rate limited
Retry with Gemini 2.5 Flash-Lite
        ↓ if all three fail (extremely unlikely)
Display last cached briefing with "Refreshing..." indicator
+ verbal: "Three-tier fallback activated —
  this is the resilience architecture working as designed"
```

The last fallback turns a failure into a demo talking point — the resilience architecture demonstrating itself live in front of judges.

**One-sentence lock:**
> *The single most likely failure is Groq rate limiting during a multi-patient demo sequence — mitigated by automatic fallback to Gemini 2.5 Flash then Flash-Lite, with a cached briefing display as the final safety net that turns the failure into a live demonstration of the resilience architecture.*

**STATUS: LOCKED**

---

### Q28 — What would a real production version need that this prototype doesn't have? (LOCKED)

1. **Patient authentication and identity management** — Aadhaar-linked or PHC-issued patient ID for longitudinal records
2. **Doctor authentication and role-based access** — login, role separation, audit logs of record access
3. **End-to-end encryption** — AES-256 at rest, encrypted PHI transmission throughout
4. **Patient consent mechanism** — DPDP Act 2023 compliant informed consent before data collection
5. **Real wearable integration** — BLE wearables for automated vitals capture via Edge layer
6. **Federated learning infrastructure** — distributed training across edge nodes without centralising patient data
7. **FHIR API integration** — FHIR R4 bidirectional data exchange with PHC and CHC EHR systems
8. **Regulatory and clinical validation** — outcomes-tracked clinical trials, Medical Devices Rules 2017 compliance for AI diagnostic tools

**One-sentence lock:**
> *Production requires patient and doctor authentication, encryption at rest, DPDP Act consent compliance, wearable integration, federated learning infrastructure, FHIR API connectivity, and formal clinical validation — none of which are prerequisites for proving the intelligence layer works, which is the prototype's sole objective.*

**STATUS: LOCKED**

---

### Q44 — How does the system behave when vitals or symptoms are incomplete? (LOCKED)

**Three-tier incomplete input handling:**

**Tier 1 — Required fields missing (form cannot submit)**
Age, sex, and chief complaint are mandatory. Submit button disabled until filled.

**Tier 2 — Optional vitals missing (system proceeds with flags)**
BP, SpO2, temperature, heart rate are important but not mandatory. If missing:
- Triage classifier receives null values — trained on synthetic data that includes incomplete records
- LLM prompt explicitly notes missing vitals: "SpO2 not recorded — respiratory risk assessment limited"
- Output includes uncertainty flag in the `uncertainty_flags` JSON field
- Doctor briefing card shows missing vitals in amber

**Tier 3 — Voice note transcription fails (bypass activated)**
Structured form data alone proceeds. Voice input is secondary — its failure never blocks the primary pathway.

**One-sentence lock:**
> *Missing required fields block submission — missing optional vitals are handled gracefully with explicit uncertainty flags in both the classifier output and the LLM briefing, ensuring incomplete data produces a calibrated uncertain output rather than a false confident one.*

**STATUS: LOCKED**

---

### Q45 — What is the latency budget — and is it achievable with free-tier APIs? (LOCKED)

**Full workflow latency breakdown:**

| Step | Component | Realistic latency |
|---|---|---|
| Form submission | Frontend → FastAPI | <100ms |
| Input structuring | FastAPI JSON builder | <10ms |
| Triage classification | GradientBoostingClassifier | <5ms |
| SHAP explanation | SHAP TreeExplainer | <50ms |
| LLM briefing call | Groq Llama-3.3-70B | 1,500–2,500ms |
| Database write | SQLite insert | <10ms |
| Dashboard update | FastAPI → React poll | <200ms |
| **Total end-to-end** | | **~2–3 seconds** |

**Fallback path latencies:**
- Gemini 2.5 Flash fallback: 3–5 seconds total
- Gemini 2.5 Flash-Lite fallback: 4–6 seconds total
- Voice note path (additional): +4–11 seconds

All paths comfortably within the 15-second benchmark defined in Q19.

**One-sentence lock:**
> *The full workflow completes in 2–3 seconds on the primary path — Groq's LPU speed makes the LLM call the dominant cost at 1.5–2.5 seconds — with Gemini fallback paths staying within 6 seconds and voice input adding at most 8 seconds, all comfortably within the 15-second demo benchmark.*

**STATUS: Q26, Q27, Q28, Q44, Q45 ALL LOCKED**

---

---

## GROUP 10 — OUTPUT & DELIVERY DESIGN

---

### Q46 — How does the AI briefing get delivered to the doctor? (LOCKED)

**Options evaluated:**

| Option | Critical problem |
|---|---|
| SMS / WhatsApp | Structured cards don't render as plain text. No priority queue. No doctor confirmation. WhatsApp Business API requires paid account |
| Push notification alone | Requires service worker + FCM server + notification permissions. Significant complexity for secondary delivery |
| Dashboard (primary) | Correct — structured card renders fully, priority queue maintained, doctor confirmation captured |
| Browser push notification (secondary) | ~10 lines additional code once dashboard exists — notifies doctor without requiring dashboard open |

**Verdict: Doctor dashboard as primary + browser push notification as secondary**

Three reasons dashboard wins:
1. Only channel that renders structured briefing cards correctly
2. Only channel that maintains Emergency-first priority ordering
3. Only channel that captures doctor "reviewed" confirmation — closing the loop and creating an audit trail

**One-sentence lock:**
> *The doctor dashboard is the primary delivery channel — it is the only channel that renders structured briefing cards, maintains a triage priority queue, and captures doctor confirmation — with a browser push notification as a secondary alert requiring minimal additional implementation.*

**STATUS: LOCKED**

---

### Q47 — What does the triage output actually look like? (LOCKED)

**The doctor briefing card — full layout:**

```
┌─────────────────────────────────────────────┐
│ [EMERGENCY]  Case #042  •  12 mins ago      │
│ 55M • Rural UP • Submitted by ASHA: Meena   │
├─────────────────────────────────────────────┤
│ CHIEF COMPLAINT                             │
│ Chest tightness + breathlessness, 2 hours  │
├─────────────────────────────────────────────┤
│ VITALS                                      │
│ BP: 160/100  HR: 98  SpO2: 91%  Temp: 37.2°│
├─────────────────────────────────────────────┤
│ PRIMARY RISK DRIVER                         │
│ Elevated BP + chest tightness in male       │
│ over 50 — possible acute cardiac event      │
├─────────────────────────────────────────────┤
│ DIFFERENTIALS                               │
│ 1. Acute coronary syndrome                  │
│ 2. Hypertensive urgency                     │
│ 3. Pulmonary embolism                       │
├─────────────────────────────────────────────┤
│ RED FLAGS                                   │
│ ⚠ SpO2 below 94% — monitor closely         │
│ ⚠ BP above 160 systolic                    │
├─────────────────────────────────────────────┤
│ RECOMMENDED IMMEDIATE ACTIONS               │
│ • ECG if available                          │
│ • Aspirin 325mg if ACS suspected            │
│ • Oxygen supplementation                    │
├─────────────────────────────────────────────┤
│ MISSING DATA                                │
│ No prior cardiac history recorded           │
├─────────────────────────────────────────────┤
│ ⚠ AI-generated decision support only.      │
│ Requires qualified medical examination.     │
├─────────────────────────────────────────────┤
│ [Mark Reviewed]        [Request More Info]  │
└─────────────────────────────────────────────┘
```

**Design rationale — every field:**
- **Triage badge first** — urgency understood before reading anything else
- **Vitals in one line** — scannable without parsing a paragraph
- **Primary risk driver in plain English** — a sentence the doctor verifies against the vitals above it in 5 seconds
- **Differentials ranked** — most likely first, AI commits to an ordering
- **Red flags visually separated** — cannot be missed on a quick scan
- **Missing data explicit** — doctor knows what they don't know before deciding
- **Non-removable disclaimer** — every card, every time, cannot be dismissed
- **Two actions only** — Mark Reviewed closes the loop. Request More Info queries the ASHA worker. No other actions — interface stays unambiguous

**One-sentence lock:**
> *The briefing card is structured as a clinical handoff document — triage badge, vitals, risk driver, ranked differentials, red flags, recommended actions, and missing data all in fixed sections — designed to be fully understood in under 30 seconds by a doctor seeing 80 patients a day.*

**STATUS: LOCKED**

---

### Q48 — What stops this from being just another chatbot — why not give the ASHA worker a phone and ChatGPT? (LOCKED)

**Five structural differences — not capability differences:**

**1. Structured input vs unstructured conversation**
ChatGPT receives whatever the user types. VitalNet receives a structured clinical JSON schema assembled by a form designed around what clinical reasoning needs. The JAMA RCT found unstructured ChatGPT use produced only marginal improvement over no AI. VitalNet's form is the forcing function that makes LLM reasoning reliable.

**2. Output goes to the right person**
ChatGPT output returns to the ASHA worker — who has 23 days of clinical training and cannot evaluate a differential diagnosis. VitalNet output goes to the doctor — the person with clinical training to verify, override, and act. Routing output to the correct decision-maker is an architectural decision, not a feature.

**3. Every interaction creates a persistent record**
ChatGPT conversations are ephemeral — nothing stored, no record exists. VitalNet writes every case to the database. A returning patient's third visit includes prior visit context. ChatGPT has none.

**4. Triage classification is independent of the LLM**
ChatGPT answers "is this an emergency?" with whatever confidence its language model generates — including hallucination risk. VitalNet's triage comes from a Gradient Boosting classifier trained on structured vitals. The LLM cannot override it. Triage is a statistical model's output, not a language model's opinion.

**5. Designed for the ASHA worker's actual context**
ChatGPT requires English literacy, stable internet, and ability to evaluate the response. VitalNet's form works in regional languages, caches offline, requires no clinical knowledge to fill, and routes output away from the ASHA worker entirely.

**The one sentence a judge remembers:**
> *"ChatGPT gives an ASHA worker an answer she cannot evaluate. VitalNet gives a doctor a briefing she can act on — the difference is not the AI, it is the infrastructure that surrounds it."*

**One-sentence lock:**
> *VitalNet is not a better chatbot — it is a structured clinical workflow that uses an LLM as one component among several: a forcing-function intake form, an independent triage classifier, a persistent record layer, and a doctor-facing output channel — none of which exist when an ASHA worker opens ChatGPT on her phone.*

**STATUS: Q46, Q47, Q48 ALL LOCKED**

---

---

## GROUP 11 — IMPACT

---

### Q29 — Real-world scale data
*Already locked in Group 1. See Q29 entry above.*

---

### Q30 — What measurable difference does VitalNet make per patient interaction? (LOCKED)

**Baseline — what happens today without VitalNet:**
- ASHA worker judgment call → paper slip → doctor receives patient with zero prior context
- Consultation starts from zero — 5–7 minutes per patient, 80 patients a day
- No record survives the encounter
- No feedback returns to the ASHA worker
- For time-critical conditions, the referral chain routinely consumes the entire golden window before a qualified doctor makes a single informed decision

**Five measurable differences per interaction:**

**Difference 1 — Time to clinical context: 0 minutes vs 3–5 minutes saved**
Without VitalNet: Doctor spends first 3–5 minutes establishing basic clinical context the ASHA worker already observed but never documented.
With VitalNet: Doctor receives structured briefing before patient arrives. Consultation begins at differential diagnosis, not at "what brings you in today."
*Conservative estimate: 2–4 minutes saved per consultation on context gathering.*

**Difference 2 — Triage accuracy: judgment-based vs model-assisted**
Without VitalNet: Referral decision based on 23 days of training — documented poor knowledge on referral conditions for respiratory, diarrhoeal, and neonatal conditions.
With VitalNet: Gradient Boosting classifier on structured vitals data. JAMA RCT found AI-assisted diagnosis at 92% accuracy vs 74% without AI. ASHA worker baseline is significantly lower than a trained doctor — making the accuracy gain proportionally larger.

**Difference 3 — Structured record created: 0 vs 1 per interaction**
Without VitalNet: Zero structured records. Every encounter undocumented.
With VitalNet: Every interaction creates a structured, timestamped clinical record — chief complaint, vitals, triage level, AI briefing, ASHA identity, location. For 9.4 lakh ASHA workers each seeing multiple patients per day, this compounds into a longitudinal dataset that has never existed in rural India.

**Difference 4 — Doctor pre-read: zero context vs sub-30-second briefing**
Without VitalNet: Doctor sees patient blind — no pre-read possible.
With VitalNet: Structured briefing card scannable in under 30 seconds — triage badge, vitals, differentials, red flags, recommended actions. For a doctor seeing 80 patients a day, arriving informed rather than blind is the difference between reactive and informed practice.

**Difference 5 — Feedback loop: none vs closed**
Without VitalNet: ASHA worker never learns whether referral was appropriate or what the diagnosis was. No feedback loop. She cannot improve.
With VitalNet: Doctor disposition recorded on case review. Returning patient history available on next visit. System accumulates a record that benefits every subsequent interaction.

**The honest caveat:**
VitalNet does not reduce travel distance, increase doctor numbers, or solve 40% PHC absenteeism. These are structural problems no software prototype solves. VitalNet measures the quality of the clinical interaction that happens when the patient does reach the doctor — and the quality of the triage decision that determines whether and how urgently that journey happens.

**One-sentence lock:**
> *Per patient interaction, VitalNet creates one structured clinical record where zero existed, saves 2–4 minutes of baseline context-gathering for the receiving doctor, replaces a judgment-based referral decision with a model-assisted triage classification, and closes the ASHA-to-doctor feedback loop for the first time — none of which happen today at any scale in rural India.*

**STATUS: LOCKED**

---

## ═══════════════════════════════════════
## ALL GROUPS COMPLETE — FULL STATUS
## ═══════════════════════════════════════

| Group | Questions | Status |
|---|---|---|
| Group 1 — Problem Depth | Q1, Q16, Q17, Q18, Q29, Q30 | ALL LOCKED ✓ |
| Group 2 — Slice Definition | Q2, Q3, Q19, Q20, Q21 | ALL LOCKED ✓ |
| Group 3 — Competitive Landscape | Q4, Q5, Q6, Q7 | ALL LOCKED ✓ |
| Group 4 — How Doctors Use AI | Q31, Q32, Q33, Q35, Q36 | ALL LOCKED ✓ |
| Group 5 — AI Layer Design | Q22, Q23, Q24, Q25, Q34 | ALL LOCKED ✓ |
| Group 6 — Trust & Adoption | Q37, Q38, Q39 | ALL LOCKED ✓ |
| Group 7 — India-Specific Reality | Q40, Q41, Q42, Q43 | ALL LOCKED ✓ |
| Group 8 — Tech Stack | Q8–Q15 + 7 layers | ALL LOCKED ✓ |
| Group 9 — Feasibility & Honesty | Q26, Q27, Q28, Q44, Q45 | ALL LOCKED ✓ |
| Group 10 — Output & Delivery | Q46, Q47, Q48 | ALL LOCKED ✓ |
| Group 11 — Impact | Q29, Q30 | ALL LOCKED ✓ |

**R&D document is ready to be written.**

*Log completed. All questions answered, all decisions locked, all sources cited.*
