"""
Deterministic contraindication/interaction flags — a safety-net module in
the same spirit as classifier.py's _safety_net_check and
_news2_concerning_vital, but a distinct concern with its own small,
curated rule table.

Scope, stated honestly: `known_conditions` and `current_medications`
(app/models/schemas.py::IntakeForm) are FREE TEXT, not coded against
RxNorm/ICD or any structured drug database. This module does NOT attempt
general drug-drug interaction checking — that would require a real
interaction database this project doesn't have, and faking coverage would
be worse than having none. It checks a small, well-established set of
condition/medication/symptom combinations via case-insensitive keyword
matching, the same technique clinical_features.py already uses for
comorbidity risk (_calculate_comorbidity_risk). Anything not on this list
is not checked — this is advisory, not comprehensive.

Firing a flag never changes the triage tier by itself; classifier.py
folds it into `needs_review` (mirrors human_review_requested), forcing a
doctor to look rather than silently escalating or de-escalating.
"""
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ContraindicationRule:
    id: str
    medication_terms: frozenset[str]
    message: str
    condition_terms: frozenset[str] = frozenset()
    symptom_codes: frozenset[str] = frozenset()
    max_heart_rate: Optional[int] = None  # fires if heart_rate is BELOW this (bradycardia-style rules)


RULES: tuple[ContraindicationRule, ...] = (
    ContraindicationRule(
        id="nsaid_renal",
        medication_terms=frozenset({
            "ibuprofen", "diclofenac", "naproxen", "nsaid", "mefenamic", "aceclofenac",
        }),
        condition_terms=frozenset({"kidney", "renal", "ckd", "dialysis"}),
        message="NSAID use with known kidney/renal disease — NSAIDs can worsen renal function; verify before recommending.",
    ),
    ContraindicationRule(
        id="ace_arb_renal",
        medication_terms=frozenset({
            "enalapril", "lisinopril", "ramipril", "captopril",
            "losartan", "telmisartan", "olmesartan", "ace inhibitor",
        }),
        condition_terms=frozenset({"kidney", "renal", "ckd", "dialysis"}),
        message="ACE inhibitor/ARB with known kidney disease — risk of hyperkalemia or worsening renal function; verify before recommending.",
    ),
    ContraindicationRule(
        id="metformin_vomiting",
        medication_terms=frozenset({"metformin", "glucophage"}),
        symptom_codes=frozenset({"persistent_vomiting"}),
        message="Metformin with persistent vomiting — risk of dehydration-related lactic acidosis; verify before continuing metformin.",
    ),
    ContraindicationRule(
        id="anticoagulant_bleeding",
        medication_terms=frozenset({
            "warfarin", "acitrom", "dabigatran", "apixaban", "rivaroxaban", "heparin", "anticoagulant",
        }),
        symptom_codes=frozenset({"severe_bleeding"}),
        message="Anticoagulant use with active severe bleeding — bleeding risk is compounded; flag for urgent clinical attention.",
    ),
    ContraindicationRule(
        id="beta_blocker_bradycardia",
        medication_terms=frozenset({
            "atenolol", "metoprolol", "propranolol", "bisoprolol", "beta blocker", "beta-blocker",
        }),
        message="Beta-blocker use with a low heart rate — may indicate excessive beta-blockade; verify before further heart-rate-lowering treatment.",
        max_heart_rate=55,
    ),
    ContraindicationRule(
        id="hypoglycemia_agent_altered_consciousness",
        medication_terms=frozenset({
            "insulin", "glimepiride", "glipizide", "glyburide", "gliclazide", "sulfonylurea",
        }),
        symptom_codes=frozenset({"altered_consciousness"}),
        message="Insulin/sulfonylurea use with altered consciousness — consider hypoglycemia; verify blood glucose before assuming another cause.",
    ),
)


def check_contraindications(form_data: dict[str, Any]) -> list[str]:
    medications = (form_data.get("current_medications") or "").lower()
    conditions = (form_data.get("known_conditions") or "").lower()
    symptoms = set(form_data.get("symptoms") or [])
    heart_rate = form_data.get("heart_rate")

    if not medications:
        return []

    flags: list[str] = []
    for rule in RULES:
        if not any(term in medications for term in rule.medication_terms):
            continue

        condition_hit = bool(rule.condition_terms) and any(term in conditions for term in rule.condition_terms)
        symptom_hit = bool(rule.symptom_codes) and bool(symptoms & rule.symptom_codes)
        heart_rate_hit = (
            rule.max_heart_rate is not None
            and heart_rate is not None
            and heart_rate < rule.max_heart_rate
        )

        if condition_hit or symptom_hit or heart_rate_hit:
            flags.append(rule.message)

    return flags
