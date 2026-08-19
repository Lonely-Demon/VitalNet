# VitalNet Feature Refinement Execution Plan

**Status:** Active engineering plan on `dev`  
**Scope:** Five roadmap workstreams selected from `FEATURES_ROADMAP.md`  
**Production model:** Frozen; no retraining, threshold changes, or model-artifact changes permitted

> **Health-safety notice:** VitalNet remains a clinical decision-support prototype, not clinically validated software. Any implementation that changes clinical data interpretation or escalation semantics requires qualified clinical governance before it can influence production triage.

## 1. Objective and interpretation of the five workstreams

This plan interprets the user-approved five workstreams as follows:

| Workstream | Roadmap source | Engineering outcome | Clinical behavior status |
|---|---|---|---|
| Confidence-and-acuity review routing | §4.7 | Prioritize doctor attention using existing stored flags and stable cursor pagination | Non-triage workflow change; may proceed with synthetic verification |
| Cross-visit vital trends | §4.5 | Add bounded, privacy-scoped vital history and accessible trend summaries | Display-only; must not change tier or review flags |
| Deterministic SBAR handoff | §4.6 | Generate an editable, provenance-preserving referral draft from stored case data | Communication aid only; no autonomous recommendation or tier change |
| Paediatric safety capture | §§4.1 and 4.4 | Add infant age precision and MUAC/weight capture with explicit validation and advisory outputs | Governance-gated; no production tier change until clinical approval |
| Qualified-language localization | §2.1 and pilot-scope blocker | Replace placeholder Hindi/Tamil resources only through a translation-review workflow | Requires qualified medical-language review before pilot use |

Gestational age (§4.2) is intentionally not included in this five-workstream execution package because it was not part of the selected five in the preceding prioritization. It remains a separate future workstream requiring maternal-health review.

## 2. Dependency order

The work will be delivered in separate, reviewable stages rather than as one large untestable change. The first stage is doctor review routing because it consumes existing fields and does not require a schema migration. Cross-visit trends and SBAR then build on existing patient-key and referral contracts. Paediatric safety capture follows only after the data dictionary, safety semantics, and governance-gated behavior are isolated. Localization is implemented as a content and review workflow, not as an uncontrolled machine-translation replacement.

## 3. Hard boundaries

The following invariants remain mandatory throughout the work:

1. The production model, model artifacts, thresholds, feature engineering, and triage rules remain unchanged unless a later, separately authorized clinical-governance decision explicitly reopens them.
2. New paediatric fields may be captured and persisted only through additive, bounded, consent-covered schema changes. They must not silently alter the existing production tier.
3. MUAC output is an advisory referral signal based on the WHO 6–59-month scope. It must not be presented as a diagnosis or treatment instruction.
4. SBAR text is deterministic, editable, provenance-labeled, and limited to facts already present in the case. It must never invent an assessment, recommendation, or missing vital.
5. Cross-visit trends expose only data already authorized by the existing patient-key visibility rules and must remain bounded in count and fields.
6. Localization preserves stable English wire identifiers. Translated strings are display-only and carry locale, version, source, and review-status metadata.
7. All synthetic tests remain aggregate-only where they exercise clinical behavior. No real patient data may enter Git, CI, logs, cloud APIs, or deployment environments.
8. No work is promoted beyond `dev` during this program.

## 4. Workstream specifications

### 4.1 Confidence-and-acuity review routing

The existing `needs_review` flag already combines model uncertainty, explicit human-review requests, contraindication flags, and deterioration alerts. The first implementation will use that persisted boolean as the stable routing key rather than introducing a second clinical score. The doctor queue will sort by triage priority first, then `needs_review` descending, then creation time descending, then ID descending.

The cursor contract will be extended with the preceding page’s `needs_review` value. The query will preserve keyset pagination and facility scoping. The UI will retain existing flag explanations while making the prioritized status more explicit. No triage tier will be changed.

### 4.2 Cross-visit vital trends

The patient-key history endpoint will return a bounded, explicitly selected set of fields: timestamp, tier, age, and the five available vitals. It will not return briefing JSON, free-text observations, medications, or unrelated PHI. The existing RLS and role/facility scoping will remain authoritative.

The frontend will render dependency-free SVG trends only when at least two historical observations contain a given vital. Every visualization will have a text alternative listing the ordered values and units. The current case will be visually distinguished without changing the case’s clinical status.

### 4.3 Deterministic SBAR handoff

A pure `buildSbar(caseRecord, referral)` function will create four sections:

- **Situation:** age/sex, current complaint, current tier, and the communicating facility.
- **Background:** complaint duration, known conditions, medications, relevant prior-visit count, and available symptoms.
- **Assessment:** stored vitals, existing risk driver, stored flags, and explicit statements for unavailable data. It will not infer a diagnosis.
- **Recommendation/Request:** the referral’s recorded urgency and reason, plus a request for receiving-facility acknowledgement. It will not create a new clinical recommendation.

The draft will be editable before copying or sending, clearly marked as system-generated from recorded fields, and hard-locked to the stored triage tier. It will be persisted only if the existing referral schema can safely carry a versioned deterministic draft; otherwise it will be generated on demand to avoid an unnecessary PHI migration.

### 4.4 Paediatric safety capture

Infant age will be captured as an additive `age_months` value for children under two years, bounded to 0–23 and validated against the existing year field. MUAC will be captured in millimetres for the WHO 6–59-month eligibility band, with optional weight only if a bounded use is defined. The frontend will make these fields conditional and explain their units.

The first implementation stage will persist and display the fields, include them in audit/provenance, and run research-only advisory calculations. Production triage remains unchanged. A later clinical-governance gate may authorize a separate candidate rule study or production integration after reference-label and parity review. The WHO source defines MUAC below 115 mm in children aged 6–59 months as a referral criterion for full assessment, but VitalNet will not convert that source statement into an autonomous diagnosis or treatment command.

### 4.5 Qualified-language localization

The existing i18n architecture will be extended with translation metadata and a review manifest. Each locale will record source version, translator/reviewer identity, review date, and approval state. English remains the fallback and wire-format identifiers remain unchanged.

Because clinical translation errors can alter what a worker believes they are recording, the implementation will not claim Hindi or Tamil production readiness without qualified review. If no qualified reviewer is available, the code will provide the complete review workflow and keep the locale explicitly marked as draft rather than silently treating machine-generated text as approved.

## 5. Verification requirements

Each workstream requires focused tests plus cross-feature regression:

| Workstream | Required verification |
|---|---|
| Review routing | Stable ordering, cursor pagination across priority boundaries, facility scoping, flagged/unflagged fixtures, unchanged triage tiers |
| Vital trends | Bounded field selection, role scoping, missing-vital handling, SVG/text parity, no free-text leakage |
| SBAR | Exact four-section output, deterministic repeatability, no invented values, tier hard-lock, editable/copy-safe rendering |
| Paediatric capture | Schema bounds, age-month edge cases, MUAC eligibility boundaries, advisory-only separation, unchanged production predictions |
| Localization | Stable wire payloads across locales, fallback behavior, string-key completeness, review metadata enforcement, accessibility of translated labels |

The full repository synthetic suite, clinical-core parity suite, frontend build, accessibility checks, bundle checks, and existing security gates remain mandatory before any merge.

## 6. External gates that engineering cannot close autonomously

A qualified clinical owner is required before paediatric advisory logic can influence triage or review routing. A qualified medical translator or clinician-language reviewer is required before Hindi or Tamil can be marked pilot-approved. A real pilot still requires an ethics/data-use route, site owner, rollback plan, incident pathway, and shadow-evaluation approval as defined in the existing governance documents.

## References

[1]: https://www.who.int/tools/elena/interventions/sam-identification "WHO: Identification of severe acute malnutrition in children 6–59 months of age"
[2]: https://www.who.int/publications/i/item/9789241549912 "WHO recommendations on antenatal care for a positive pregnancy experience"
[3]: https://www.who.int/publications/i/item/9789240020306 "WHO Digital Adaptation Kit for Antenatal Care"
[4]: https://www.ahrq.gov/teamstepps-program/curriculum/communication/tools/sbar.html "AHRQ TeamSTEPPS SBAR tool"
[5]: https://www.cdc.gov/health-literacy/php/develop-materials/culture.html "CDC Culture and Language guidance"
[6]: https://digital.gov/resources/multilingual-huddle-designing-for-translation/ "Digital.gov Designing for Translation"
