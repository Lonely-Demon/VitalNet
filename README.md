# VitalNet

VitalNet is an offline-first clinical triage and briefing platform designed for rural healthcare in India. It enables ASHA workers to collect structured patient information and helps PHC doctors receive prioritized clinical insights before the patient reaches the health centre.

A local machine-learning classifier categorizes each case as **EMERGENCY**, **URGENT**, or **ROUTINE**, both online and offline. An LLM then generates a structured clinical briefing, including differential diagnoses, red flags, and recommended actions for the reviewing doctor.

The triage level is determined only by the ML classifier and cannot be modified by the LLM.

---

## Documentation

This README provides the information required to set up and run the project locally. Detailed documentation is available in the following files:

| Document | Description |
|---|---|
| **[CODEBASE_MAP.md](./CODEBASE_MAP.md)** | Project structure, architecture, sequence diagrams, and ER diagrams |
| **[docs/API_REFERENCE.md](./docs/API_REFERENCE.md)** | API endpoints, authentication, request/response formats, and rate limits |
| **[docs/DECISIONS.md](./docs/DECISIONS.md)** | Design decisions, trade-offs, and rejected alternatives |
| **[docs/RESEARCH_AND_DEVELOPMENT.md](./docs/RESEARCH_AND_DEVELOPMENT.md)** | Research background, AI design rationale, feasibility, and impact |
| **[FEATURES_ROADMAP.md](./FEATURES_ROADMAP.md)** | Planned features and implementation roadmap |
| **[CONTRIBUTING.md](./CONTRIBUTING.md)** | Contribution workflow and development guidelines |
| **[docs/TESTING_STRATEGY.md](./docs/TESTING_STRATEGY.md)** | Testing approach and coverage |
| **[docs/SECURITY.md](./docs/SECURITY.md)** | Security architecture and vulnerability reporting |
| **[docs/ONBOARDING.md](./docs/ONBOARDING.md)** | Development environment setup and onboarding guide |
| **[docs/GLOSSARY.md](./docs/GLOSSARY.md)** | Healthcare and project terminology |
| **[docs/DISASTER_RECOVERY.md](./docs/DISASTER_RECOVERY.md)** | Backup and recovery procedures |
| **[docs/INCIDENT_RESPONSE.md](./docs/INCIDENT_RESPONSE.md)** | Security incident response process |
| **[docs/CLINICAL_GOVERNANCE.md](./docs/CLINICAL_GOVERNANCE.md)** | Clinical governance and regulatory considerations |
| **[docs/COMPLIANCE_DPDP.md](./docs/COMPLIANCE_DPDP.md)** | DPDP Act 2023 compliance mapping |
| **[docs/ACCESSIBILITY.md](./docs/ACCESSIBILITY.md)** | Accessibility compliance and audit results |
| **[docs/SLO.md](./docs/SLO.md)** | Service Level Objectives and monitoring |
| **[backend/app/ml/README.md](./backend/app/ml/README.md)** & **[MODEL_CARD.md](./backend/app/ml/MODEL_CARD.md)** | ML architecture, model design, and limitations |
| **[CHANGELOG.md](./CHANGELOG.md)** | Version history |
| **[AGENTS.md](./AGENTS.md)** | Guidelines for AI coding agents |

---

## Features

- **Offline ML Triage:** A `HistGradientBoostingClassifier` trained on 43 engineered clinical features classifies patients into **EMERGENCY**, **URGENT**, or **ROUTINE**. The same trained model runs online (Python) and offline (pure JavaScript), ensuring consistent predictions across both environments.

- **Deterministic Safety Rules:** Critical clinical conditions automatically escalate a case to **EMERGENCY**, regardless of the ML prediction, ensuring patient safety.

- **SHAP-based Risk Explanations:** Each ML prediction includes feature-level explanations generated using SHAP and presented in clinical language.

- **AI Clinical Briefings:** An LLM generates differential diagnoses, red flags, and recommended actions. The triage level remains fixed and cannot be altered by the LLM.

- **Offline-first PWA:** Patient data can be collected without internet connectivity. Submissions are stored locally and synchronized automatically when connectivity is restored.

- **Doctor Dashboard:** Doctors receive prioritized cases in real time, review patient history, override triage with justification, record outcomes, and manage referrals.

- **Notifications:** Optional push notifications alert doctors to new emergency cases, with automatic escalation for unattended critical cases.

- **Analytics:** Built-in dashboards provide response-time metrics, ML agreement rates, and reporting tools.

- **Multi-language Support:** The application supports multiple languages through `react-i18next`, with infrastructure ready for reviewed translations.

- **Voice-assisted Data Entry:** Browser-based speech-to-text simplifies patient data collection where supported.

- **Role-based Access Control:** Separate access levels are provided for ASHA workers, doctors, supervisors, and administrators using backend authorization and Supabase Row Level Security.

- **Outbreak Monitoring:** Facility-level symptom trends are monitored to identify potential disease outbreaks.

- **Clinical Protocol Assistant:** Provides quick access to approved healthcare guidelines, referral criteria, and immunization schedules.

- **Production-ready Security:** Includes API rate limiting, structured logging, request validation, prompt sanitization, JWT authentication, and secure error handling.
