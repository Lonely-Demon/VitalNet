from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class IntakeForm(BaseModel):
    asha_id: str
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


class BriefingOutput(BaseModel):
    triage_level: str
    primary_risk_driver: str
    differential_diagnoses: List[str]
    red_flags: List[str]
    recommended_immediate_actions: List[str]
    recommended_tests: List[str]
    uncertainty_flags: str
    disclaimer: str


class SubmitResponse(BaseModel):
    case_id: int
    triage_level: str
    confidence_score: float
    risk_driver: str
    briefing: Optional[dict] = None
    status: str


class ReviewUpdate(BaseModel):
    reviewed: bool
    review_notes: Optional[str] = None
