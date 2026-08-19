"""
Deterministic Bilingual Allow-List Symptom Parser for Korean KTAS 2019 Chief Complaints.

Maps unstructured triage chief complaint text (Korean Hangul and English clinical terms)
deterministically into VitalNet's 12 canonical ALLOWED_SYMPTOMS allow-list.

Enforces:
- 100% deterministic rule-based and regex keyword matching (versioned as ktas_symptom_parser_v1).
- Comprehensive Korean (Hangul) clinical terms and English emergency triage descriptors.
- Robust negation detection (e.g. "두통 없음", "발열 없음", "no fever", "denies chest pain").
- Standardized normalization, deduplication, and sorting of extracted canonical symptom IDs.
- Streaming accumulator with ZERO raw chief complaint retention in memory or report artifacts.
"""

import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

PARSER_VERSION: str = "ktas_symptom_parser_v1"

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

# Negation patterns in Korean and English
_NEGATION_PREFIX_PATTERN = re.compile(
    r"\b(?:no|denies|without|ruled?\s*out|r/o)\b",
    re.IGNORECASE,
)
_NEGATION_SUFFIX_PATTERN = re.compile(
    r"(?:없음|안함|부정|소실|호전|minus|-)",
    re.IGNORECASE,
)

# Bilingual regex patterns mapping Korean & English terms to the 12 canonical symptoms
_KTAS_SYMPTOM_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    (
        "chest_pain",
        re.compile(
            r"(?:흉통|가슴\s*통증|가슴\s*답답|흉부\s*통증|가슴통증|흉부불편감|심장\s*통증|"
            r"\b(?:chest\s*(?:pain|tightness|pressure|discomfort|ache)|substernal\s*pain|sternal\s*pain|angina|cp)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "breathlessness",
        re.compile(
            r"(?:호흡\s*곤란|숨\s*참|숨이\s*참|숨차|호흡곤란|숨가쁨|천식\s*발작|"
            r"\b(?:shortness\s*of\s*breath|sob|dyspnea|difficulty\s*breathing|trouble\s*breathing|wheezing|asthma|hypoxia|cannot\s*breathe)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "altered_consciousness",
        re.compile(
            r"(?:의식\s*저하|의식저하|의식\s*불명|실신|기절|혼미|혼수|의식\s*소실|"
            r"\b(?:altered\s*mental\s*status|ams|unresponsive|unresponsiveness|unconscious|unconsciousness|syncope|syncopal|passed\s*out|loss\s*of\s*consciousness|loc|coma|comatose|lethargy|lethargic|confusion)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "severe_bleeding",
        re.compile(
            r"(?:대량\s*출혈|과다\s*출혈|토혈|혈변|객혈|심한\s*출혈|활동성\s*출혈|"
            r"\b(?:severe\s*bleeding|active\s*bleeding|massive\s*bleeding|hemorrhage|gi\s*bleed|rectal\s*bleeding|hematemesis|hemoptysis|profuse\s*bleeding)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "seizure",
        re.compile(
            r"(?:경련|발작|간질|"
            r"\b(?:seizure|seizures|status\s*epilepticus|post\s*-?\s*ictal|convulsion|convulsions|fitting|epilepsy)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "high_fever",
        re.compile(
            r"(?:고열|발열|열감|오한\s*동반|체온\s*상승|"
            r"\b(?:high\s*fever|fever|pyrexia|febrile|high\s*temp)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "severe_abdominal_pain",
        re.compile(
            r"(?:복통|배\s*아픔|배\s*통증|복부\s*통증|심한\s*복통|위통|명치\s*통증|측복부\s*통증|하복부\s*통증|"
            r"\b(?:abdominal\s*pain|abd\s*pain|severe\s*stomach\s*pain|stomach\s*pain|belly\s*pain|acute\s*abdomen|epigastric\s*pain|flank\s*pain)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "persistent_vomiting",
        re.compile(
            r"(?:지속적\s*구토|반복적\s*구토|심한\s*구토|구토\s*지속|오심\s*구토|"
            r"\b(?:persistent\s*vomiting|intractable\s*vomiting|frequent\s*vomiting|emesis|hyperemesis)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "severe_headache",
        re.compile(
            r"(?:심한\s*두통|두통|머리\s*아픔|편두통|극심한\s*두통|벼락\s*두통|"
            r"\b(?:severe\s*headache|headache|ha|migraine|worst\s*headache|thunderclap\s*headache)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "weakness_one_side",
        re.compile(
            r"(?:편마비|편측\s*마비|편측\s*약화|한쪽\s*마비|한쪽\s*힘빠짐|안면\s*마비|반신\s*마비|뇌졸중|"
            r"\b(?:one\s*-?\s*sided\s*weakness|unilateral\s*weakness|facial\s*droop|hemiparesis|hemiplegia|stroke|cva|tia|sided\s*numbness)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "difficulty_speaking",
        re.compile(
            r"(?:언어\s*장애|말\s*어눌|발음\s*곤란|실어증|말하기\s*힘듦|"
            r"\b(?:difficulty\s*speaking|trouble\s*speaking|slurred\s*speech|slurring|aphasia|dysarthria|cannot\s*speak)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "swelling_face_throat",
        re.compile(
            r"(?:얼굴\s*부종|목\s*부종|안면\s*부종|후두\s*부종|기도\s*부종|아나필락시스|입술\s*부종|"
            r"\b(?:facial\s*swelling|throat\s*swelling|lip\s*swelling|tongue\s*swelling|angioedema|anaphylaxis|airway\s*swelling|stridor)\b)",
            re.IGNORECASE,
        ),
    ),
]


def parse_ktas_symptoms(complaint: Optional[str]) -> List[str]:
    """
    Deterministically parses a raw Korean or English chief complaint string into a
    sorted list of canonical VitalNet allowed symptom IDs.

    Args:
        complaint: Raw chief complaint string (or None).

    Returns:
        Sorted list of matched unique canonical symptom strings. If none match or if negated, returns [].
    """
    if not complaint:
        return []

    text = str(complaint).strip()
    if not text or text.lower() in ("null", "none", "nan", "n/a", "unknown", "?", "#null!", "측불"):
        return []

    # Check for whole-sentence negation
    if text.startswith("no ") or text.startswith("denies ") or text.endswith(" 없음") or text.endswith(" 부정"):
        # If the entire complaint is a negation of a symptom, handle cleanly
        pass

    matched: Set[str] = set()
    for symptom_id, pattern in _KTAS_SYMPTOM_PATTERNS:
        match = pattern.search(text)
        if match:
            # Check for local negation context around matched term
            start, end = match.span()
            prefix = text[max(0, start - 15) : start].strip()
            suffix = text[end : min(len(text), end + 15)].strip()

            is_negated = bool(
                _NEGATION_PREFIX_PATTERN.search(prefix)
                or _NEGATION_SUFFIX_PATTERN.search(suffix)
            )

            if not is_negated:
                matched.add(symptom_id)

    return sorted(matched)


class StreamingKTASSymptomCoverageAccumulator:
    """
    Streaming accumulator that computes symptom parsing coverage for Korean KTAS chief complaints.
    Guarantees ZERO raw chief complaint retention in memory or report containers.
    """

    def __init__(self) -> None:
        self.total_count = 0
        self.non_empty_count = 0
        self.matched_any_count = 0
        self.symptom_counts: Dict[str, int] = {s: 0 for s in sorted(CANONICAL_ALLOWED_SYMPTOMS)}

    def update(self, complaint: Optional[str]) -> List[str]:
        """
        Processes a single complaint string, increments counters, and returns parsed symptoms.
        The raw string is never stored on self or buffered in memory.
        """
        self.total_count += 1
        if complaint and str(complaint).strip():
            self.non_empty_count += 1
            symptoms = parse_ktas_symptoms(complaint)
            if symptoms:
                self.matched_any_count += 1
                for s in symptoms:
                    self.symptom_counts[s] += 1
            return symptoms
        return []

    def finalize(self) -> Dict[str, Any]:
        """
        Returns aggregate coverage dictionary with zero raw strings.
        """
        coverage_pct = (
            round((self.matched_any_count / self.total_count * 100.0), 2)
            if self.total_count > 0
            else 0.0
        )
        non_empty_coverage_pct = (
            round((self.matched_any_count / self.non_empty_count * 100.0), 2)
            if self.non_empty_count > 0
            else 0.0
        )

        return {
            "parser_version": PARSER_VERSION,
            "total_complaints_inspected": self.total_count,
            "non_empty_complaints_count": self.non_empty_count,
            "complaints_with_mapped_symptoms_count": self.matched_any_count,
            "overall_coverage_pct": coverage_pct,
            "non_empty_coverage_pct": non_empty_coverage_pct,
            "symptom_frequency_distribution": self.symptom_counts,
        }


def compute_ktas_symptom_parser_coverage(
    complaints: Iterable[Optional[str]],
) -> Dict[str, Any]:
    """
    Computes aggregate coverage statistics across a collection of KTAS chief complaints.
    Guarantees ZERO raw complaint text is included in output dictionary or retained in memory.
    """
    accumulator = StreamingKTASSymptomCoverageAccumulator()
    for comp in complaints:
        accumulator.update(comp)
    return accumulator.finalize()
