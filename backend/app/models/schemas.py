from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime
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

    symptoms: List[str] = Field(default_factory=list, max_length=MAX_SYMPTOMS)
    observations: Optional[str] = Field(None, max_length=500)
    known_conditions: Optional[str] = Field(None, max_length=300)
    current_medications: Optional[str] = Field(None, max_length=300)

    # Phase 6 — offline sync metadata
    client_id: Optional[uuid.UUID] = None
    client_submitted_at: Optional[datetime] = None
    created_offline: bool = False   # True when submitted via offline queue sync

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
        "patient_name",
    )
    @classmethod
    def _strip_control_chars(cls, v: Optional[str]) -> Optional[str]:
        """Strip non-printable/control characters that have no clinical
        meaning but can be used to smuggle formatting/instructions into
        the LLM prompt (e.g. embedded newlines mimicking prompt structure)."""
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
