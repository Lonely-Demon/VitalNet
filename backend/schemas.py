from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


class IntakeForm(BaseModel):
    patient_name: str = Field(min_length=1, max_length=100)
    patient_age: int = Field(ge=0, le=120)
    patient_sex: str
    chief_complaint: str
    complaint_duration: str
    location: str

    bp_systolic: Optional[int] = Field(None, ge=30, le=300)
    bp_diastolic: Optional[int] = Field(None, ge=10, le=200)
    spo2: Optional[int] = Field(None, ge=50, le=100)
    heart_rate: Optional[int] = Field(None, ge=10, le=250)
    temperature: Optional[float] = Field(None, ge=25.0, le=45.0)

    symptoms: List[str] = []
    observations: Optional[str] = Field(None, max_length=500)
    known_conditions: Optional[str] = None
    current_medications: Optional[str] = None

    # Phase 6 — offline sync metadata
    client_id: Optional[uuid.UUID] = None
    client_submitted_at: Optional[datetime] = None
    created_offline: bool = False   # True when submitted via offline queue sync


class BriefingOutput(BaseModel):
    triage_level: str
    primary_risk_driver: str
    differential_diagnoses: List[str]
    red_flags: List[str]
    recommended_immediate_actions: List[str]
    recommended_tests: List[str]
    uncertainty_flags: str
    disclaimer: str
