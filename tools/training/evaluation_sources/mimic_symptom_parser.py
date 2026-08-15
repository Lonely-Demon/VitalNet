"""
Deterministic Allow-List Symptom Parser for MIMIC-IV-ED Chief Complaints.

Maps unstructured triage chief complaint text deterministically into VitalNet's 12
canonical ALLOWED_SYMPTOMS allow-list.

Enforces:
- 100% deterministic rule-based and regex keyword matching (versioned as mimic_symptom_parser_v1).
- Strictly zero dependence on external network services, cloud LLMs, or post-triage data.
- Standardized normalization and sorting of extracted symptom IDs.
- Aggregate-only parser reporting: raw chief complaint strings are strictly excluded from output containers.
"""

import re
from typing import Any, Dict, Iterable, List, Optional, Set

PARSER_VERSION: str = "mimic_symptom_parser_v1"

# VitalNet's 12 canonical symptom IDs from packages/clinical-core/src/schema.ts
CANONICAL_ALLOWED_SYMPTOMS: Set[str] = {
    "chest_pain",
    "breathlessness",
    "altered_consciousness",
    "severe_bleeding",
    "seizure",
    "high_fever",
    "severe_abdominal_pain",
    "persistent_vomiting",
    "severe_headache",
    "weakness_one_side",
    "difficulty_speaking",
    "swelling_face_throat",
}

# Rule and regex dictionary for deterministic extraction
# Compiled case-insensitively with word boundaries where appropriate
_SYMPTOM_PATTERNS: List[tuple[str, re.Pattern[str]]] = [
    (
        "chest_pain",
        re.compile(
            r"\b(chest\s*(?:pain|tightness|pressure|discomfort|ache)|substernal\s*pain|sternal\s*pain|angina|cp)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "breathlessness",
        re.compile(
            r"\b(shortness\s*of\s*breath|sob|dyspnea|difficulty\s*breathing|trouble\s*breathing|wheezing|asthma\s*attack|respiratory\s*distress|hypoxia|hypoxic|cannot\s*breathe|can'?t\s*breathe)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "altered_consciousness",
        re.compile(
            r"\b(altered\s*mental\s*status|ams|unresponsive|unresponsiveness|unconscious|unconsciousness|syncope|syncopal|passed\s*out|loss\s*of\s*consciousness|loc|coma|comatose|lethargy|lethargic|acute\s*confusion|confused)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "severe_bleeding",
        re.compile(
            r"\b(severe\s*bleeding|active\s*bleeding|massive\s*bleeding|hemorrhage|hemorrhagic|gi\s*bleed|rectal\s*bleeding|hematemesis|vomiting\s*blood|hemoptysis|coughing\s*up\s*blood|epistaxis\s*uncontrolled|profuse\s*bleeding)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "seizure",
        re.compile(
            r"\b(seizure|seizures|status\s*epilepticus|post\s*-?\s*ictal|convulsion|convulsions|fitting)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "high_fever",
        re.compile(
            r"\b(high\s*fever|fever|pyrexia|febrile|chills\s*(?:and|with)\s*fever|temp\s*(?:high|elevated))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "severe_abdominal_pain",
        re.compile(
            r"\b(abdominal\s*pain|abd\s*pain|severe\s*stomach\s*pain|stomach\s*pain|belly\s*pain|acute\s*abdomen|epigastric\s*pain|flank\s*pain|ruq\s*pain|luq\s*pain|rlq\s*pain|llq\s*pain|pelvic\s*pain)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "persistent_vomiting",
        re.compile(
            r"\b(persistent\s*vomiting|intractable\s*vomiting|vomiting|nausea\s*and\s*vomiting|n\s*/\s*v|emesis|hyperemesis|dry\s*heaves)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "severe_headache",
        re.compile(
            r"\b(severe\s*headache|headache|ha|migraine|worst\s*headache|thunderclap\s*headache|head\s*pain)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "weakness_one_side",
        re.compile(
            r"\b(one\s*-?\s*sided\s*weakness|unilateral\s*weakness|facial\s*droop|hemiparesis|hemiplegia|stroke\s*(?:symptoms|like)?|cva|tia|left\s*side\s*weakness|right\s*side\s*weakness|weakness\s*(?:on\s*(?:the\s*)?)?(?:left|right|one)\s*side|arm\s*weakness|leg\s*weakness|sided\s*numbness)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "difficulty_speaking",
        re.compile(
            r"\b(difficulty\s*speaking|trouble\s*speaking|slurred\s*speech|slurring|aphasia|dysarthria|cannot\s*speak|unable\s*to\s*speak|speech\s*difficulty)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "swelling_face_throat",
        re.compile(
            r"\b(facial\s*swelling|throat\s*swelling|lip\s*swelling|tongue\s*swelling|angioedema|anaphylaxis|anaphylactic|allergic\s*reaction\s*(?:with\s*swelling|throat)|stridor|airway\s*swelling)\b",
            re.IGNORECASE,
        ),
    ),
]


def parse_symptoms_from_complaint(complaint: Optional[str]) -> List[str]:
    """
    Deterministically parses a free-text chief complaint string into a sorted list
    of canonical VitalNet allowed symptom IDs.

    Args:
        complaint: Raw string or None from triage.chiefcomplaint.

    Returns:
        Sorted list of matched unique canonical symptom strings.
    """
    if not complaint:
        return []

    text = str(complaint).strip()
    if not text or text.lower() in ("null", "none", "nan", "n/a", "unknown", "?"):
        return []

    matched_symptoms: Set[str] = set()
    for symptom_id, pattern in _SYMPTOM_PATTERNS:
        if pattern.search(text):
            matched_symptoms.add(symptom_id)

    # Return sorted list for strict determinism
    return sorted(matched_symptoms)


def compute_symptom_parser_coverage(
    complaints: Iterable[Optional[str]],
) -> Dict[str, Any]:
    """
    Computes aggregate coverage statistics across a collection of chief complaints.
    Guarantees ZERO raw complaint text is included in the output dictionary.

    Args:
        complaints: Iterable of raw chief complaints.

    Returns:
        Dictionary containing total count, coverage count/pct, and per-symptom frequency.
    """
    total_count = 0
    non_empty_count = 0
    matched_any_count = 0
    symptom_counts: Dict[str, int] = {s: 0 for s in sorted(CANONICAL_ALLOWED_SYMPTOMS)}

    for comp in complaints:
        total_count += 1
        if comp and str(comp).strip():
            non_empty_count += 1
            symptoms = parse_symptoms_from_complaint(comp)
            if symptoms:
                matched_any_count += 1
                for s in symptoms:
                    symptom_counts[s] += 1

    coverage_pct = round((matched_any_count / total_count * 100.0), 2) if total_count > 0 else 0.0
    non_empty_coverage_pct = (
        round((matched_any_count / non_empty_count * 100.0), 2) if non_empty_count > 0 else 0.0
    )

    return {
        "parser_version": PARSER_VERSION,
        "total_complaints_inspected": total_count,
        "non_empty_complaints_count": non_empty_count,
        "complaints_with_mapped_symptoms_count": matched_any_count,
        "overall_coverage_pct": coverage_pct,
        "non_empty_coverage_pct": non_empty_coverage_pct,
        "symptom_frequency_distribution": symptom_counts,
    }
