from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


class IntakeForm(BaseModel):
    patient_age: int = Field(ge=0, le=120)
    patient_sex: str
    chief_complaint: str
    complaint_duration: str
    location: str

    bp_systolic: Optional[int] = Field(None, ge=50, le=250)
    bp_diastolic: Optional[int] = Field(None, ge=30, le=150)
    spo2: Optional[int] = Field(None, ge=70, le=100)
    heart_rate: Optional[int] = Field(None, ge=20, le=220)
    temperature: Optional[float] = Field(None, ge=30.0, le=45.0)

    symptoms: List[str] = []
    observations: Optional[str] = Field(None, max_length=500)
    known_conditions: Optional[str] = None
    current_medications: Optional[str] = None

    # Phase 6 — offline sync metadata
    client_id: Optional[uuid.UUID] = None
    client_submitted_at: Optional[datetime] = None


class BriefingOutput(BaseModel):
    triage_level: str
    primary_risk_driver: str
    differential_diagnoses: List[str]
    red_flags: List[str]
    recommended_immediate_actions: List[str]
    recommended_tests: List[str]
    uncertainty_flags: str
    disclaimer: str
