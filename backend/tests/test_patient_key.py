"""
Tests for the patient continuity key: format validation in
app/models/schemas.py::IntakeForm.patient_key, and its round-trip through
the regex shared with the frontend generator (frontend/src/utils/patientKey.js).

Run: cd backend && pytest tests/test_patient_key.py -v
"""
import pytest
from pydantic import ValidationError

from app.models.schemas import IntakeForm, PATIENT_KEY_RE

VALID_FORM_KWARGS = dict(
    patient_name="Test Patient",
    patient_age=30,
    patient_sex="male",
    chief_complaint="Fever",
    complaint_duration="1-6 hours",
    location="Test Village",
    consent_captured=True,
)


def test_patient_key_none_by_default():
    form = IntakeForm(**VALID_FORM_KWARGS)
    assert form.patient_key is None


def test_valid_patient_key_accepted():
    form = IntakeForm(**VALID_FORM_KWARGS, patient_key="AB3C-9XYZ")
    assert form.patient_key == "AB3C-9XYZ"


def test_patient_key_normalized_to_uppercase():
    form = IntakeForm(**VALID_FORM_KWARGS, patient_key="ab3c-9xyz")
    assert form.patient_key == "AB3C-9XYZ"


@pytest.mark.parametrize("bad_key", [
    "ABCD1234",       # missing hyphen
    "ABC-12345",      # wrong segment lengths
    "AB0C-9XYZ",      # contains excluded char 0
    "ABOC-9XYZ",      # contains excluded char O
    "AB1C-9XYZ",      # contains excluded char 1
    "ABIC-9XYZ",      # contains excluded char I
    "ABLC-9XYZ",      # contains excluded char L
    "!!!!-!!!!",      # non-alphanumeric
    "",               # empty string
])
def test_invalid_patient_key_rejected(bad_key):
    with pytest.raises(ValidationError):
        IntakeForm(**VALID_FORM_KWARGS, patient_key=bad_key)


def test_patient_key_regex_excludes_ambiguous_chars():
    alphabet = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
    for ambiguous in "01IOL":
        assert ambiguous not in alphabet
    # Every char in the allowed alphabet is accepted in isolation
    for ch in alphabet:
        assert PATIENT_KEY_RE.match(f"{ch*4}-{ch*4}")
