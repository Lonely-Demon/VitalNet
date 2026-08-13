from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Literal
from datetime import datetime
import re
import uuid

# Allow-list of symptom IDs the frontend can send. Keeps the ML feature
# pipeline's input space bounded — free-form symptom strings would let a
# caller inject arbitrary tokens into engineered features and the LLM prompt.
ALLOWED_SYMPTOMS = {
    "chest_pain", "breathlessness", "altered_consciousness", "severe_bleeding",
    "seizure", "high_fever", "severe_abdominal_pain", "persistent_vomiting",
    "severe_headache", "weakness_one_side", "difficulty_speaking",
    "swelling_face_throat",
}

MAX_SYMPTOMS = 20  # generous ceiling — real forms send at most ~12

# Unambiguous alphabet for patient continuity keys — excludes 0/O/1/I/L so a
# key read aloud or handwritten from a QR-code printout is never mis-copied.
# Exported for reuse by the by-patient-key lookup route (app/api/routes/cases.py).
PATIENT_KEY_RE = re.compile(r"^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}$")


class IntakeForm(BaseModel):
    patient_name: str = Field(min_length=1, max_length=100)
    patient_age: int = Field(ge=0, le=120)
    patient_sex: Literal["male", "female", "other"]
    chief_complaint: str = Field(min_length=1, max_length=200)
    complaint_duration: str = Field(min_length=1, max_length=50)
    location: str = Field(min_length=1, max_length=200)

    bp_systolic: Optional[int] = Field(None, ge=30, le=300)
    bp_diastolic: Optional[int] = Field(None, ge=10, le=200)
    spo2: Optional[int] = Field(None, ge=50, le=100)
    heart_rate: Optional[int] = Field(None, ge=10, le=250)
    temperature: Optional[float] = Field(None, ge=25.0, le=45.0)

    # Structured pregnancy flag — feeds a dedicated safety-net rule for
    # severe hypertension in pregnancy (docs/DECISIONS.md §30). Deliberately
    # a real field rather than relying on free-text known_conditions/
    # chief_complaint keyword matching (which already exists as a soft ML
    # feature signal, clinical_features.py::_pregnancy_adjustment, but is
    # not reliable enough to gate a deterministic safety guarantee on).
    is_pregnant: Optional[bool] = None

    symptoms: List[str] = Field(default_factory=list, max_length=MAX_SYMPTOMS)
    observations: Optional[str] = Field(None, max_length=500)
    known_conditions: Optional[str] = Field(None, max_length=300)
    current_medications: Optional[str] = Field(None, max_length=300)

    # Phase 6 — offline sync metadata
    client_id: Optional[uuid.UUID] = None
    client_submitted_at: Optional[datetime] = None
    created_offline: bool = False   # True when submitted via offline queue sync

    # Lets the submitting ASHA worker flag a case for human (doctor) review
    # with a reason, independent of what tier the classifier assigned.
    human_review_requested: bool = False
    human_review_reason: Optional[str] = Field(None, max_length=500)

    # Patient (or guardian) consent to data collection and AI-assisted triage.
    # Enforced server-side, not just as a frontend UX gate.
    consent_captured: bool = False
    consent_captured_at: Optional[datetime] = None

    # Opaque, offline-generated patient continuity key (format XXXX-XXXX, no
    # PII encoded) — lets a worker recognize a returning patient across
    # visits without a centralized patient registry. Optional.
    patient_key: Optional[str] = Field(None, min_length=9, max_length=9)

    @field_validator("patient_key")
    @classmethod
    def _validate_patient_key(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().upper()
        if not PATIENT_KEY_RE.match(v):
            raise ValueError("patient_key must match format XXXX-XXXX (no 0/O/1/I/L)")
        return v

    @model_validator(mode="after")
    def _validate_bp_pair(self):
        if self.bp_systolic is not None and self.bp_diastolic is not None:
            if self.bp_diastolic >= self.bp_systolic:
                raise ValueError("Diastolic BP must be lower than systolic BP")
        return self

    @model_validator(mode="after")
    def _require_consent(self):
        if not self.consent_captured:
            raise ValueError("Patient consent is required before submission")
        return self

    @field_validator("symptoms")
    @classmethod
    def _validate_symptoms(cls, v: List[str]) -> List[str]:
        unknown = set(v) - ALLOWED_SYMPTOMS
        if unknown:
            raise ValueError(f"Unrecognised symptom id(s): {sorted(unknown)}")
        return v

    @field_validator(
        "chief_complaint", "complaint_duration", "location",
        "observations", "known_conditions", "current_medications",
        "patient_name", "human_review_reason",
    )
    @classmethod
    def _strip_control_chars(cls, v: Optional[str]) -> Optional[str]:
        """Strip non-printable/control characters that have no clinical
        meaning but can be used to smuggle formatting/instructions into
        the LLM prompt (e.g. embedded newlines mimicking prompt structure)."""
        if v is None:
            return v
        return "".join(ch for ch in v if ch == "\n" or ch == "\t" or ch.isprintable()).strip()


class TriageOverride(BaseModel):
    """A doctor's correction of the ML triage tier, with a required reason.
    Feeds the outcome-retraining loop (FEATURES_ROADMAP §1.3, §1b.1)."""
    overridden_triage: Literal["ROUTINE", "URGENT", "EMERGENCY"]
    override_reason: str = Field(min_length=1, max_length=500)

    @field_validator("override_reason")
    @classmethod
    def _strip_control_chars(cls, v: str) -> str:
        return "".join(ch for ch in v if ch == "\n" or ch == "\t" or ch.isprintable()).strip()


class CaseOutcomeInput(BaseModel):
    """A doctor's record of what actually happened to a patient after triage —
    the real-outcome label the retraining loop (FEATURES_ROADMAP §1.3) reads."""
    actual_severity: Literal["ROUTINE", "URGENT", "EMERGENCY"]
    patient_disposition: Literal[
        "treated_discharged", "admitted", "referred_higher_facility", "deceased", "unknown"
    ]
    outcome_notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("outcome_notes")
    @classmethod
    def _strip_control_chars(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return "".join(ch for ch in v if ch == "\n" or ch == "\t" or ch.isprintable()).strip()


class BriefingOutput(BaseModel):
    triage_level: str
    primary_risk_driver: str
    differential_diagnoses: List[str]
    red_flags: List[str]
    recommended_immediate_actions: List[str]
    recommended_tests: List[str]
    uncertainty_flags: str
    disclaimer: str
    llm_status: str = "generated"
    needs_review: bool = False
