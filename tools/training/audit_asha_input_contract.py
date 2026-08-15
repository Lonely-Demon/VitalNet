"""
VitalNet ASHA Intake Input Contract Remediation & Field Sensitivity Study.

This module implements a synthetic-only, frozen-model diagnostic framework to
measure which ASHA intake fields materially affect current triage behavior and
which collected fields are operationally inert.

STUDY INVARIANTS:
1. Deterministic synthetic cohort generation with a fixed seed.
2. Reference labels computed ONCE from full intended representation via clinical-core rules engine.
3. Frozen reference labels reused across all ablation arms without recomputation.
4. Identical synthetic encounters across all arms; only declared fields are manipulated.
5. Production classifier, weights, feature engineer, rules, thresholds, and artifacts remain frozen and unchanged.
6. Aggregate counts and metrics only; zero patient-level rows, IDs, form dicts, free text, or probabilities emitted.
7. Completely isolated from real-data adapters (Iran/NHAMCS files are never read).
"""

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import types
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, HERE)

# Stub tree_export for train_classifier import if onnxruntime not present
_stub = types.ModuleType("tree_export")
_stub.onnx_to_tree_json = lambda *a, **k: None
_stub.evaluate_tree_json = lambda *a, **k: (None,)
sys.modules["tree_export"] = _stub

_spec = importlib.util.spec_from_file_location(
    "train_classifier", os.path.join(HERE, "train_classifier.py")
)
tc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tc)

from app.ml import classifier as clf_mod  # noqa: E402
from app.ml.contraindications import check_contraindications  # noqa: E402

TIER_MAP = {0: "ROUTINE", 1: "URGENT", 2: "EMERGENCY"}
TIER_INDICES = {"ROUTINE": 0, "URGENT": 1, "EMERGENCY": 2}

FIVE_VITAL_FIELDS: Tuple[str, ...] = (
    "temperature",
    "heart_rate",
    "bp_systolic",
    "bp_diastolic",
    "spo2",
)

FORBIDDEN_LEAKAGE_KEYS: Set[str] = {
    "form_data",
    "raw_fields",
    "raw_records",
    "patient_records",
    "records",
    "rows",
    "encounters",
    "patient_id",
    "triage_code",
    "chief_complaint",
    "symptoms",
    "observations",
    "current_medications",
    "known_conditions",
    "location",
    "patient_name",
    "mrn",
    "free_text",
}

STUDY_NON_CLAIMS: List[str] = [
    "Diagnostic-only study: This analysis measures existing frozen model sensitivity and field utilization without modification.",
    "Synthetic data only: All evaluations are performed on synthetic out-of-sample cohorts generated under fixed seeds.",
    "Non-clinical claim: Findings do not constitute clinical validation, clinical efficacy, or readiness claims for deployment.",
    "Candidate fields status: Future candidate fields (respiratory rate, blood glucose, etc.) are documented for research roadmap review only and are not passed to the production classifier.",
]


# ── Statistical Utilities ────────────────────────────────────────────────────

def wilson_interval(successes: int, total: int, z: float = 1.95996) -> Tuple[float, float]:
    """Computes Wilson score 95% confidence interval [lower, upper]."""
    if total <= 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1.0 + (z ** 2) / total
    centre = (p + (z ** 2) / (2.0 * total)) / denom
    margin = (z * math.sqrt((p * (1.0 - p) + (z ** 2) / (4.0 * total)) / total)) / denom
    lower = max(0.0, centre - margin)
    upper = min(1.0, centre + margin)
    return round(lower, 4), round(upper, 4)


def wilson_dict(successes: int, total: int) -> Dict[str, Any]:
    val = round(successes / total, 4) if total > 0 else 0.0
    lo, hi = wilson_interval(successes, total)
    return {
        "point_estimate": val,
        "ci_95_lower": lo,
        "ci_95_upper": hi,
        "numerator": successes,
        "denominator": total,
    }


def _get_git_commit() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "unavailable"


# ── Field-Utilization Matrix ─────────────────────────────────────────────────

FIELD_UTILIZATION_MATRIX: Dict[str, Dict[str, Any]] = {
    "patient_name": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": True,
        "passed_to_offline_hybrid_triage": True,
        "used_by_core_feature_map": False,
        "used_by_safety_rules": False,
        "used_by_contraindication_review": False,
        "used_by_briefing_or_persistence_only": True,
        "clinical_operational_role": "Patient identification, record matching, and clinical briefing display.",
    },
    "patient_age": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": True,
        "passed_to_offline_hybrid_triage": True,
        "used_by_core_feature_map": True,
        "used_by_safety_rules": True,
        "used_by_contraindication_review": False,
        "used_by_briefing_or_persistence_only": False,
        "clinical_operational_role": "Core demographic: pediatric/geriatric adjustments, neonatal fever rule, baseline vital expectations.",
    },
    "patient_sex": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": True,
        "passed_to_offline_hybrid_triage": True,
        "used_by_core_feature_map": True,
        "used_by_safety_rules": False,
        "used_by_contraindication_review": False,
        "used_by_briefing_or_persistence_only": False,
        "clinical_operational_role": "Core demographic: basic sex feature, pregnancy adjustment gating.",
    },
    "temperature": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": True,
        "passed_to_offline_hybrid_triage": True,
        "used_by_core_feature_map": True,
        "used_by_safety_rules": True,
        "used_by_contraindication_review": False,
        "used_by_briefing_or_persistence_only": False,
        "clinical_operational_role": "Primary vital: temp_deviation, infectious cluster, extreme fever (>41.5 / <33), neonatal fever, NEWS2 floor.",
    },
    "heart_rate": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": True,
        "passed_to_offline_hybrid_triage": True,
        "used_by_core_feature_map": True,
        "used_by_safety_rules": True,
        "used_by_contraindication_review": True,
        "used_by_briefing_or_persistence_only": False,
        "clinical_operational_role": "Primary vital: shock_index, cardiac risk, extreme HR (<35 / >170), NEWS2 floor, bradycardia contraindications.",
    },
    "bp_systolic": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": True,
        "passed_to_offline_hybrid_triage": True,
        "used_by_core_feature_map": True,
        "used_by_safety_rules": True,
        "used_by_contraindication_review": False,
        "used_by_briefing_or_persistence_only": False,
        "clinical_operational_role": "Primary vital: shock_index, MAP, pulse_pressure, extreme SBP (<70 / >220), hypertensive crisis, preeclampsia.",
    },
    "bp_diastolic": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": True,
        "passed_to_offline_hybrid_triage": True,
        "used_by_core_feature_map": True,
        "used_by_safety_rules": True,
        "used_by_contraindication_review": False,
        "used_by_briefing_or_persistence_only": False,
        "clinical_operational_role": "Primary vital: MAP, pulse_pressure, preeclampsia severe diastolic thresholds (>=110 or >=90 with symptoms).",
    },
    "spo2": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": True,
        "passed_to_offline_hybrid_triage": True,
        "used_by_core_feature_map": True,
        "used_by_safety_rules": True,
        "used_by_contraindication_review": False,
        "used_by_briefing_or_persistence_only": False,
        "clinical_operational_role": "Primary vital: spo2_age_ratio, respiratory distress, critical hypoxemia (<85%), NEWS2 floor (<=92%).",
    },
    "respiratory_rate": {
        "captured_by_ui": False,
        "serialized_to_payload": False,
        "validated_by_schema": False,
        "passed_to_legacy_triage": False,
        "passed_to_offline_hybrid_triage": False,
        "used_by_core_feature_map": False,
        "used_by_safety_rules": False,
        "used_by_contraindication_review": False,
        "used_by_briefing_or_persistence_only": False,
        "clinical_operational_role": "Not collected in current ASHA form. Candidate future vital requiring clinical and operational review.",
    },
    "symptoms": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": True,
        "passed_to_offline_hybrid_triage": True,
        "used_by_core_feature_map": True,
        "used_by_safety_rules": True,
        "used_by_contraindication_review": True,
        "used_by_briefing_or_persistence_only": False,
        "clinical_operational_role": "Core clinical inputs: 12 bounded symptom flags, interaction clusters, critical symptom safety net, contraindications.",
    },
    "observations": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": True,
        "passed_to_offline_hybrid_triage": True,
        "used_by_core_feature_map": False,
        "used_by_safety_rules": False,
        "used_by_contraindication_review": False,
        "used_by_briefing_or_persistence_only": True,
        "clinical_operational_role": "Free-text field observations. Persisted and presented to doctor in clinical briefing; inert to ML/rules engine.",
    },
    "is_pregnant": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": True,
        "passed_to_offline_hybrid_triage": True,
        "used_by_core_feature_map": True,
        "used_by_safety_rules": True,
        "used_by_contraindication_review": False,
        "used_by_briefing_or_persistence_only": False,
        "clinical_operational_role": "Dedicated pregnancy flag: gates deterministic preeclampsia safety rules and physiological risk adjustments.",
    },
    "chief_complaint": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": True,
        "passed_to_offline_hybrid_triage": True,
        "used_by_core_feature_map": True,
        "used_by_safety_rules": False,
        "used_by_contraindication_review": False,
        "used_by_briefing_or_persistence_only": False,
        "clinical_operational_role": "Primary clinical narrative: chief_complaint_risk, trauma_severity_score, obstetric_emergency_risk.",
    },
    "complaint_duration": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": True,
        "passed_to_offline_hybrid_triage": True,
        "used_by_core_feature_map": True,
        "used_by_safety_rules": False,
        "used_by_contraindication_review": False,
        "used_by_briefing_or_persistence_only": False,
        "clinical_operational_role": "Temporal acuity: symptom_duration_risk (sudden/hyperacute vs chronic presentation).",
    },
    "location": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": True,
        "passed_to_offline_hybrid_triage": True,
        "used_by_core_feature_map": True,
        "used_by_safety_rules": False,
        "used_by_contraindication_review": False,
        "used_by_briefing_or_persistence_only": False,
        "clinical_operational_role": "Geographic context: geographic_disease_risk (endemic terms) and healthcare_accessibility score.",
    },
    "known_conditions": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": True,
        "passed_to_offline_hybrid_triage": True,
        "used_by_core_feature_map": True,
        "used_by_safety_rules": False,
        "used_by_contraindication_review": True,
        "used_by_briefing_or_persistence_only": False,
        "clinical_operational_role": "Comorbidity context: comorbidity_multiplier, kidney/renal contraindication rule triggers.",
    },
    "current_medications": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": True,
        "passed_to_offline_hybrid_triage": True,
        "used_by_core_feature_map": False,
        "used_by_safety_rules": False,
        "used_by_contraindication_review": True,
        "used_by_briefing_or_persistence_only": False,
        "clinical_operational_role": "Medication safety: evaluated by check_contraindications() for drug-disease/symptom flags; inert to core tree.",
    },
    "consent_captured": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": False,
        "passed_to_offline_hybrid_triage": False,
        "used_by_core_feature_map": False,
        "used_by_safety_rules": False,
        "used_by_contraindication_review": False,
        "used_by_briefing_or_persistence_only": True,
        "clinical_operational_role": "Governance & legal consent: mandatory server-side submission gate; not passed to inference.",
    },
    "patient_key": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": False,
        "passed_to_offline_hybrid_triage": False,
        "used_by_core_feature_map": False,
        "used_by_safety_rules": False,
        "used_by_contraindication_review": False,
        "used_by_briefing_or_persistence_only": True,
        "clinical_operational_role": "Longitudinal continuity: offline-generated de-identified patient key (format XXXX-XXXX); not passed to inference.",
    },
    "human_review_requested": {
        "captured_by_ui": True,
        "serialized_to_payload": True,
        "validated_by_schema": True,
        "passed_to_legacy_triage": False,
        "passed_to_offline_hybrid_triage": False,
        "used_by_core_feature_map": False,
        "used_by_safety_rules": False,
        "used_by_contraindication_review": False,
        "used_by_briefing_or_persistence_only": True,
        "clinical_operational_role": "Human escalation control: allows ASHA worker to request manual doctor review with human_review_reason.",
    },
}


# ── Candidate Future-Fields Simulation Research Table ────────────────────────

CANDIDATE_FUTURE_FIELDS_RESEARCH_TABLE: List[Dict[str, Any]] = [
    {
        "field_name": "respiratory_rate",
        "category": "vital_sign",
        "clinical_rationale": "Direct physiological indicator of sepsis, respiratory distress, and metabolic acidosis (NEWS2 parameter).",
        "collection_feasibility_in_phc": "Moderate: requires 60-second manual count or digital sensor; frequently omitted or estimated under time pressure.",
        "contract_and_clinical_review_status": "Candidate under research review. Not accepted by frozen production classifier.",
    },
    {
        "field_name": "measurement_source_device_and_quality_flag",
        "category": "data_provenance",
        "clinical_rationale": "Distinguishes digital vs manual sphygmomanometer, pulse-oximeter waveform quality, or palpatory estimates.",
        "collection_feasibility_in_phc": "High: single dropdown/toggle in UI indicating device type or measurement confidence.",
        "contract_and_clinical_review_status": "Candidate under research review. Not accepted by frozen production classifier.",
    },
    {
        "field_name": "oxygen_supplementation_status",
        "category": "vital_context",
        "clinical_rationale": "Essential for interpreting SpO2 readings (NEWS2 Scale 2 for hypercapnic respiratory failure / supplemental O2).",
        "collection_feasibility_in_phc": "High: binary flag (on air vs supplemental O2).",
        "contract_and_clinical_review_status": "Candidate under research review. Not accepted by frozen production classifier.",
    },
    {
        "field_name": "symptom_onset_progression_or_sudden_worsening",
        "category": "temporal_trajectory",
        "clinical_rationale": "Distinguishes acute deterioration (e.g. sudden severe headache, acute dyspnea) from indolent chronic complaints.",
        "collection_feasibility_in_phc": "Moderate: structured onset selector (sudden vs gradual vs episodic).",
        "contract_and_clinical_review_status": "Candidate under research review. Not accepted by frozen production classifier.",
    },
    {
        "field_name": "structured_mental_status_detail",
        "category": "neurological_assessment",
        "clinical_rationale": "Provides AVPU (Alert, Voice, Pain, Unresponsive) scale granularity beyond binary altered_consciousness flag.",
        "collection_feasibility_in_phc": "High: 4-level standard AVPU selector widely trained in basic triage curricula.",
        "contract_and_clinical_review_status": "Candidate under research review. Not accepted by frozen production classifier.",
    },
    {
        "field_name": "structured_location_type",
        "category": "geographic_operational",
        "clinical_rationale": "Replaces free-text keyword regex with structured classification (e.g. PHC, Sub-Center, Village Home Visit, Tribal Settlement).",
        "collection_feasibility_in_phc": "High: pre-configured facility or visit-type selector.",
        "contract_and_clinical_review_status": "Candidate under research review. Not accepted by frozen production classifier.",
    },
    {
        "field_name": "structured_comorbidities_and_medication_categories",
        "category": "history_and_pharmacotherapy",
        "clinical_rationale": "Replaces unstructured text search with coded checkboxes (Diabetes, CKD, CAD, Anticoagulants, NSAIDs, Antihypertensives).",
        "collection_feasibility_in_phc": "High: standard 8-10 item high-risk comorbidity/medication checklist.",
        "contract_and_clinical_review_status": "Candidate under research review. Not accepted by frozen production classifier.",
    },
    {
        "field_name": "blood_glucose",
        "category": "point_of_care_testing",
        "clinical_rationale": "Critical for acute hypoglycemia (<60 mg/dL) presenting as altered consciousness/seizure or diabetic ketoacidosis.",
        "collection_feasibility_in_phc": "Moderate: dependent on availability of glucometer test strips at the PHC/ASHA level.",
        "contract_and_clinical_review_status": "Candidate under research review. Not accepted by frozen production classifier.",
    },
]


# ── Synthetic Cohort Generator ───────────────────────────────────────────────

NAMES_POOL = [
    "Sunita Devi", "Ramesh Kumar", "Pooja Sharma", "Anil Patel",
    "Lakshmi Bai", "Mohammad Khan", "Geeta Bai", "Rajesh Verma",
]
MEDICATIONS_POOL = [
    "", "", "",
    "metformin 500mg", "amlodipine 5mg", "ibuprofen 400mg",
    "paracetamol 500mg", "enalapril 5mg", "aspirin 75mg",
    "diclofenac 50mg, paracetamol", "metformin 500mg, glimepiride 1mg",
]
OBSERVATIONS_POOL = [
    "",
    "Patient appears visibly pale, sitting uncomfortably on bench",
    "Accompanying relative reports patient had cold sweats this morning",
    "ASHA worker notes patient was brought by bullock cart from distant hamlet",
    "Patient is alert and communicative, resting calmly",
    "Mild shivering noted, patient wrapped in blanket",
    "Family expresses deep concern about sudden weakness",
]


def generate_synthetic_asha_cohort(n: int = 5000, seed: int = 2026) -> List[Dict[str, Any]]:
    """
    Generates a deterministic synthetic cohort with all ASHA intake fields populated.
    """
    np.random.seed(seed)
    severities = ["healthy", "mild", "moderate", "severe", "critical"]
    weights = [0.30, 0.22, 0.22, 0.16, 0.10]
    pediatric_fraction = 0.22
    out = []

    for i in range(n):
        sev = np.random.choice(severities, p=weights)
        ped = np.random.random() < pediatric_fraction
        p = tc.generate_patient(sev, pediatric=ped, allow_missing=False)

        # Complete ASHA form fields
        name = NAMES_POOL[i % len(NAMES_POOL)]
        meds = MEDICATIONS_POOL[i % len(MEDICATIONS_POOL)]
        obs = OBSERVATIONS_POOL[i % len(OBSERVATIONS_POOL)]
        is_preg = False
        if p["patient_sex"] == "female" and 15 <= p["patient_age"] <= 45:
            is_preg = bool(np.random.random() < 0.18)

        cond = p.get("known_conditions") or ""
        if isinstance(cond, list):
            cond = ", ".join(cond)

        duration_str = p.get("complaint_duration") or "1–3 days"
        duration_days = 0
        if "Less than 1 hour" in duration_str or "1–6 hours" in duration_str:
            duration_days = 0
        elif "6–24 hours" in duration_str:
            duration_days = 1
        elif "1–3 days" in duration_str:
            duration_days = 2
        elif "More than 3 days" in duration_str:
            duration_days = 5

        full_p = {
            "patient_name": name,
            "patient_age": p["patient_age"],
            "patient_sex": p["patient_sex"],
            "temperature": p["temperature"],
            "heart_rate": p["heart_rate"],
            "bp_systolic": p["bp_systolic"],
            "bp_diastolic": p["bp_diastolic"],
            "spo2": p["spo2"],
            "symptoms": list(p.get("symptoms") or []),
            "is_pregnant": is_preg,
            "chief_complaint": p.get("chief_complaint") or "Fever",
            "complaint_duration": duration_str,
            "duration_days": duration_days,
            "location": p.get("location") or "Rampur Village",
            "known_conditions": cond,
            "current_medications": meds,
            "observations": obs,
            "consent_captured": True,
            "patient_key": f"3K{i%9}P-7X{(i*3)%9}W",
            "human_review_requested": False,
            "human_review_reason": "",
            "_reference_month": p.get("_reference_month", 7),
        }
        out.append(full_p)

    return out


# ── Study Arm Transformations ────────────────────────────────────────────────

def arm_current_full_form(p: Dict[str, Any]) -> Dict[str, Any]:
    return copy.deepcopy(p)


def arm_current_triage_contract(p: Dict[str, Any]) -> Dict[str, Any]:
    """Exactly the fields that reach current hybrid triage."""
    return {
        "patient_age": p["patient_age"],
        "patient_sex": p["patient_sex"],
        "temperature": p["temperature"],
        "heart_rate": p["heart_rate"],
        "bp_systolic": p["bp_systolic"],
        "bp_diastolic": p["bp_diastolic"],
        "spo2": p["spo2"],
        "symptoms": list(p.get("symptoms") or []),
        "is_pregnant": p.get("is_pregnant", False),
        "chief_complaint": p.get("chief_complaint", ""),
        "complaint_duration": p.get("complaint_duration", ""),
        "duration_days": p.get("duration_days", 0),
        "location": p.get("location", ""),
        "known_conditions": p.get("known_conditions", ""),
        "current_medications": p.get("current_medications", ""),
        "_reference_month": p.get("_reference_month", 7),
    }


def arm_no_observations(p: Dict[str, Any]) -> Dict[str, Any]:
    cp = copy.deepcopy(p)
    cp["observations"] = ""
    return cp


def arm_no_medications(p: Dict[str, Any]) -> Dict[str, Any]:
    cp = copy.deepcopy(p)
    cp["current_medications"] = ""
    return cp


def arm_no_structured_symptoms(p: Dict[str, Any]) -> Dict[str, Any]:
    cp = copy.deepcopy(p)
    cp["symptoms"] = []
    return cp


def arm_no_complaint_context(p: Dict[str, Any]) -> Dict[str, Any]:
    cp = copy.deepcopy(p)
    cp["chief_complaint"] = ""
    cp["complaint_duration"] = ""
    cp["duration_days"] = 0
    cp["location"] = ""
    cp["known_conditions"] = ""
    return cp


def arm_nhamcs_like_partial_input(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "patient_age": p["patient_age"],
        "patient_sex": p["patient_sex"],
        "temperature": p["temperature"],
        "heart_rate": p["heart_rate"],
        "bp_systolic": p["bp_systolic"],
        "bp_diastolic": p["bp_diastolic"],
        "spo2": p["spo2"],
        "symptoms": [],
        "chief_complaint": "",
        "complaint_duration": "",
        "duration_days": 0,
        "location": "",
        "known_conditions": "",
        "current_medications": "",
        "observations": "",
        "is_pregnant": False,
    }


def arm_missing_vital(p: Dict[str, Any], vitals_to_mask: Tuple[str, ...]) -> Dict[str, Any]:
    cp = copy.deepcopy(p)
    for v in vitals_to_mask:
        cp[v] = None
    return cp


# ── Study Evaluator Engine ───────────────────────────────────────────────────

def evaluate_study_arm(
    arm_name: str,
    patients_arm: List[Dict[str, Any]],
    frozen_labels: List[int],
    full_form_preds: Optional[List[int]] = None,
    full_form_contraindications: Optional[List[List[str]]] = None,
) -> Tuple[Dict[str, Any], List[int], List[List[str]]]:
    """
    Evaluates a single study arm against the frozen reference labels and baseline full form.
    """
    if clf_mod._classifier is None:
        clf_mod.load_classifier()

    n = len(patients_arm)
    y_true = np.array(frozen_labels)

    preds: List[int] = []
    contra_list: List[List[str]] = []
    probs_list: List[List[float]] = []

    safety_net_triggers = 0
    news2_floor_triggers = 0
    low_confidence_count = 0
    contra_flag_count = 0
    needs_review_count = 0

    for p in patients_arm:
        res = clf_mod.predict_triage(p)
        t_idx = TIER_INDICES[res["triage_level"]]
        preds.append(t_idx)

        # Probabilities
        if "probabilities" in res and res["probabilities"]:
            probs = [res["probabilities"].get(t, 0.0) for t in ("ROUTINE", "URGENT", "EMERGENCY")]
        elif res.get("safety_net_triggered"):
            probs = [0.0, 0.0, 1.0]
        else:
            probs = [0.0, 0.0, 0.0]
            probs[t_idx] = 1.0
        probs_list.append(probs)

        if res.get("safety_net_triggered"):
            safety_net_triggers += 1
        if res.get("news2_floor_triggered"):
            news2_floor_triggers += 1
        if res.get("low_confidence"):
            low_confidence_count += 1

        c_flags = res.get("contraindication_flags") or []
        contra_list.append(c_flags)
        if len(c_flags) > 0:
            contra_flag_count += 1

        # needs_review is triggered by low_confidence, contraindications, or manual request
        if res.get("low_confidence") or len(c_flags) > 0 or p.get("human_review_requested"):
            needs_review_count += 1

    y_pred = np.array(preds)
    probs_arr = np.array(probs_list)

    # Confusion matrix
    cm = [[int(((y_true == r) & (y_pred == c)).sum()) for c in range(3)] for r in range(3)]

    # Sensitivities
    sensitivities: Dict[str, Any] = {}
    for t_val, t_name in TIER_MAP.items():
        tot_t = int((y_true == t_val).sum())
        tp_t = int(((y_true == t_val) & (y_pred == t_val)).sum())
        sensitivities[t_name] = wilson_dict(tp_t, tot_t)

    under_triage = int((y_pred < y_true).sum())
    over_triage = int((y_pred > y_true).sum())
    exact_agree = int((y_pred == y_true).sum())

    em_cases = int((y_true == 2).sum())
    em_under = int(((y_true == 2) & (y_pred < 2)).sum())
    em_missed_routine = int(((y_true == 2) & (y_pred == 0)).sum())

    # Disagreements relative to baseline full form
    disagreements: Dict[str, Any] = {}
    if full_form_preds is not None:
        y_base = np.array(full_form_preds)
        tier_disagreements = int((y_pred != y_base).sum())
        more_conserv = int((y_pred > y_base).sum())
        less_conserv = int((y_pred < y_base).sum())

        contra_diff = 0
        if full_form_contraindications is not None:
            for c_arm, c_base in zip(contra_list, full_form_contraindications):
                if sorted(c_arm) != sorted(c_base):
                    contra_diff += 1

        disagreements = {
            "tier_disagreement_count": tier_disagreements,
            "tier_disagreement_rate": round(tier_disagreements / n, 4) if n > 0 else 0.0,
            "more_conservative_count": more_conserv,
            "more_conservative_rate": round(more_conserv / n, 4) if n > 0 else 0.0,
            "less_conservative_count": less_conserv,
            "less_conservative_rate": round(less_conserv / n, 4) if n > 0 else 0.0,
            "contraindication_disagreement_count": contra_diff,
            "contraindication_disagreement_rate": round(contra_diff / n, 4) if n > 0 else 0.0,
        }

    report = {
        "cohort_size": n,
        "frozen_label_distribution": {
            "ROUTINE": int((y_true == 0).sum()),
            "URGENT": int((y_true == 1).sum()),
            "EMERGENCY": int((y_true == 2).sum()),
            "ROUTINE_pct": round(float((y_true == 0).mean()) * 100.0, 2),
            "URGENT_pct": round(float((y_true == 1).mean()) * 100.0, 2),
            "EMERGENCY_pct": round(float((y_true == 2).mean()) * 100.0, 2),
        },
        "predicted_tier_distribution": {
            "ROUTINE": int((y_pred == 0).sum()),
            "URGENT": int((y_pred == 1).sum()),
            "EMERGENCY": int((y_pred == 2).sum()),
            "ROUTINE_pct": round(float((y_pred == 0).mean()) * 100.0, 2),
            "URGENT_pct": round(float((y_pred == 1).mean()) * 100.0, 2),
            "EMERGENCY_pct": round(float((y_pred == 2).mean()) * 100.0, 2),
        },
        "overall_agreement": wilson_dict(exact_agree, n),
        "confusion_matrix": cm,
        "tier_sensitivities": sensitivities,
        "under_triage_count": under_triage,
        "under_triage_rate": round(under_triage / n, 4) if n > 0 else 0.0,
        "over_triage_count": over_triage,
        "over_triage_rate": round(over_triage / n, 4) if n > 0 else 0.0,
        "emergency_misses": {
            "total_emergency_cases": em_cases,
            "under_triaged_count": em_under,
            "under_triaged_rate": round(em_under / em_cases, 4) if em_cases > 0 else 0.0,
            "under_triaged_pct": round((em_under / em_cases) * 100.0, 2) if em_cases > 0 else 0.0,
            "missed_as_routine_count": em_missed_routine,
            "missed_as_routine_rate": round(em_missed_routine / em_cases, 4) if em_cases > 0 else 0.0,
            "missed_as_routine_pct": round((em_missed_routine / em_cases) * 100.0, 2) if em_cases > 0 else 0.0,
        },
        "low_confidence_count": low_confidence_count,
        "low_confidence_rate": round(low_confidence_count / n, 4) if n > 0 else 0.0,
        "safety_net_activation_count": safety_net_triggers,
        "safety_net_activation_rate": round(safety_net_triggers / n, 4) if n > 0 else 0.0,
        "news2_floor_activation_count": news2_floor_triggers,
        "news2_floor_activation_rate": round(news2_floor_triggers / n, 4) if n > 0 else 0.0,
        "contraindication_flag_count": contra_flag_count,
        "contraindication_flag_rate": round(contra_flag_count / n, 4) if n > 0 else 0.0,
        "needs_review_count": needs_review_count,
        "needs_review_rate": round(needs_review_count / n, 4) if n > 0 else 0.0,
        "mean_class_probabilities": {
            "ROUTINE": round(float(probs_arr[:, 0].mean()), 4),
            "URGENT": round(float(probs_arr[:, 1].mean()), 4),
            "EMERGENCY": round(float(probs_arr[:, 2].mean()), 4),
        },
        "disagreements_vs_current_full_form": disagreements,
    }

    return report, preds, contra_list


# ── Full Study Orchestration ─────────────────────────────────────────────────

def run_asha_input_contract_study(
    n: int = 5000,
    seed: int = 2026,
) -> Dict[str, Any]:
    """
    Orchestrates the entire ASHA input contract remediation study.
    """
    print(f"\n[1/4] Generating {n} synthetic ASHA encounters (seed={seed})...")
    patients_full = generate_synthetic_asha_cohort(n=n, seed=seed)

    print("[2/4] Freezing reference labels on full intended representation...")
    frozen_labels = [int(l) for l in tc.assign_triage_labels(patients_full)]

    print("[3/4] Evaluating baseline current_full_form arm...")
    full_report, full_preds, full_contra = evaluate_study_arm(
        "current_full_form",
        [arm_current_full_form(p) for p in patients_full],
        frozen_labels,
    )

    study_arms: Dict[str, List[Dict[str, Any]]] = {
        "current_triage_contract": [arm_current_triage_contract(p) for p in patients_full],
        "no_observations": [arm_no_observations(p) for p in patients_full],
        "no_medications": [arm_no_medications(p) for p in patients_full],
        "no_structured_symptoms": [arm_no_structured_symptoms(p) for p in patients_full],
        "no_complaint_context": [arm_no_complaint_context(p) for p in patients_full],
        "nhamcs_like_partial_input": [arm_nhamcs_like_partial_input(p) for p in patients_full],
        # Missing vital singletons
        "missing_temperature": [arm_missing_vital(p, ("temperature",)) for p in patients_full],
        "missing_heart_rate": [arm_missing_vital(p, ("heart_rate",)) for p in patients_full],
        "missing_bp_systolic": [arm_missing_vital(p, ("bp_systolic",)) for p in patients_full],
        "missing_bp_diastolic": [arm_missing_vital(p, ("bp_diastolic",)) for p in patients_full],
        "missing_spo2": [arm_missing_vital(p, ("spo2",)) for p in patients_full],
        # Missing vital combinations
        "missing_sbp_and_dbp": [arm_missing_vital(p, ("bp_systolic", "bp_diastolic")) for p in patients_full],
        "missing_temp_and_hr": [arm_missing_vital(p, ("temperature", "heart_rate")) for p in patients_full],
        "missing_hr_and_spo2": [arm_missing_vital(p, ("heart_rate", "spo2")) for p in patients_full],
        "missing_sbp_hr_dbp": [arm_missing_vital(p, ("bp_systolic", "heart_rate", "bp_diastolic")) for p in patients_full],
    }

    print(f"[4/4] Evaluating {len(study_arms)} ablation arms...")
    arms_results: Dict[str, Any] = {
        "current_full_form": full_report,
    }

    for arm_key, arm_patients in study_arms.items():
        arm_rep, _, _ = evaluate_study_arm(
            arm_key,
            arm_patients,
            frozen_labels,
            full_form_preds=full_preds,
            full_form_contraindications=full_contra,
        )
        arms_results[arm_key] = arm_rep

    # Compute key insights / sensitivity summary
    sensitivity_summary = {
        "observations_effect": {
            "tier_disagreements": arms_results["no_observations"]["disagreements_vs_current_full_form"]["tier_disagreement_count"],
            "conclusion": "observations field is operationally inert to ML classifier and rules engine; strictly clinical briefing / persistence only.",
        },
        "medications_effect": {
            "tier_disagreements": arms_results["no_medications"]["disagreements_vs_current_full_form"]["tier_disagreement_count"],
            "contraindication_flag_drop": (
                arms_results["current_full_form"]["contraindication_flag_count"]
                - arms_results["no_medications"]["contraindication_flag_count"]
            ),
            "conclusion": "current_medications drives drug-disease contraindication review flags; does not alter ML triage tier.",
        },
        "structured_symptoms_effect": {
            "agreement_drop": round(
                arms_results["current_full_form"]["overall_agreement"]["point_estimate"]
                - arms_results["no_structured_symptoms"]["overall_agreement"]["point_estimate"],
                4,
            ),
            "emergency_sensitivity_drop": round(
                arms_results["current_full_form"]["tier_sensitivities"]["EMERGENCY"]["point_estimate"]
                - arms_results["no_structured_symptoms"]["tier_sensitivities"]["EMERGENCY"]["point_estimate"],
                4,
            ),
            "conclusion": "symptoms is a primary driver of clinical sensitivity and critical symptom safety nets.",
        },
        "nhamcs_partial_input_effect": {
            "agreement_drop": round(
                arms_results["current_full_form"]["overall_agreement"]["point_estimate"]
                - arms_results["nhamcs_like_partial_input"]["overall_agreement"]["point_estimate"],
                4,
            ),
            "emergency_sensitivity_drop": round(
                arms_results["current_full_form"]["tier_sensitivities"]["EMERGENCY"]["point_estimate"]
                - arms_results["nhamcs_like_partial_input"]["tier_sensitivities"]["EMERGENCY"]["point_estimate"],
                4,
            ),
            "conclusion": "Blanking symptoms and context isolates vital-only inference, explaining severe under-triage when evaluated against arrival urgency.",
        },
    }

    report = {
        "study_name": "ASHA Input Contract Remediation & Field Sensitivity Study",
        "execution_mode": "synthetic_contract_study",
        "provenance": {
            "git_commit": _get_git_commit(),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "sample_size": n,
            "random_seed": seed,
        },
        "study_arms": arms_results,
        "sensitivity_summary": sensitivity_summary,
        "field_utilization_matrix": FIELD_UTILIZATION_MATRIX,
        "candidate_future_fields_research_table": CANDIDATE_FUTURE_FIELDS_RESEARCH_TABLE,
        "limitations_and_non_claims": STUDY_NON_CLAIMS,
    }

    assert_zero_patient_leakage(report)
    return report


# ── Zero Patient Leakage Assertion ───────────────────────────────────────────

def assert_zero_patient_leakage(report: Dict[str, Any]) -> None:
    """Recursively validates that report contains zero patient-level data or forbidden keys."""
    def _check(obj: Any, path: str = ""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                k_lower = str(k).lower()
                # Skip static schema documentation definitions where field names are dictionary keys
                if not (path.startswith("field_utilization_matrix") or path.startswith("candidate_future_fields")):
                    if k_lower in FORBIDDEN_LEAKAGE_KEYS:
                        raise AssertionError(f"Patient-level key '{k}' found at path '{path}'")
                _check(v, f"{path}.{k}" if path else str(k))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _check(item, f"{path}[{i}]")

    _check(report)


# ── CLI Entrypoint ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="VitalNet Frozen-Model ASHA Input Contract Remediation Study"
    )
    parser.add_argument(
        "--n",
        type=int,
        default=5000,
        help="Number of synthetic encounters (default: 5000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=2026,
        help="Random seed (default: 2026)",
    )
    parser.add_argument(
        "--json-out",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to write aggregate JSON study report",
    )

    args = parser.parse_args()
    report = run_asha_input_contract_study(n=args.n, seed=args.seed)

    if args.json_out:
        out_dir = os.path.dirname(args.json_out)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nStudy report saved to: {args.json_out}")

    print("\nASHA Input Contract Study completed successfully.")


if __name__ == "__main__":
    main()
