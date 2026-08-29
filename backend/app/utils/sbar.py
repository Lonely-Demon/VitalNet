"""Deterministic, provenance-preserving SBAR referral drafts."""

from collections.abc import Mapping


SBAR_VERSION = "sbar.v1"


def _value(value: object, fallback: str = "Not recorded") -> str:
    if value is None or value == "" or value == []:
        return fallback
    return str(value)


def _vitals(case: Mapping[str, object]) -> str:
    fields = (
        ("BP", case.get("bp_systolic"), case.get("bp_diastolic"), "mmHg"),
        ("SpO₂", case.get("spo2"), None, "%"),
        ("Heart rate", case.get("heart_rate"), None, "bpm"),
        ("Temperature", case.get("temperature"), None, "°C"),
    )
    values: list[str] = []
    for label, first, second, unit in fields:
        if first is None and second is None:
            continue
        if second is not None:
            values.append(f"{label} {first}/{second} {unit}")
        else:
            values.append(f"{label} {first} {unit}")
    return "; ".join(values) if values else "No vital signs recorded"


def build_sbar(case: Mapping[str, object], referral: Mapping[str, object]) -> str:
    """Return a deterministic editable handoff draft.

    The function never diagnoses, invents a missing measurement, or changes the
    stored triage tier. It is intentionally pure so the same input always
    yields the same draft in tests and in the API route.
    """
    symptoms = case.get("symptoms") or []
    symptom_text = ", ".join(str(item) for item in symptoms) if symptoms else "No structured symptoms recorded"
    flags = case.get("contraindication_flags") or []
    flag_text = "; ".join(str(item) for item in flags) if flags else "None recorded"
    triage = _value(case.get("triage_level"))
    urgency = _value(referral.get("urgency"))
    reason = _value(referral.get("reason"))

    return "\n".join(
        (
            "SITUATION",
            f"Patient age: {_value(case.get('patient_age'), 'Not recorded')} years; sex: {_value(case.get('patient_sex'))}.",
            f"Presenting problem: {_value(case.get('chief_complaint'))}.",
            f"Stored VitalNet triage tier: {triage} (clinician verification required).",
            "",
            "BACKGROUND",
            f"Complaint duration: {_value(case.get('complaint_duration'))}.",
            f"Known conditions: {_value(case.get('known_conditions'))}.",
            f"Current medications: {_value(case.get('current_medications'))}.",
            f"Structured symptoms: {symptom_text}.",
            "",
            "ASSESSMENT",
            f"Recorded vital signs: {_vitals(case)}.",
            f"Stored risk driver: {_value(case.get('risk_driver'))}.",
            f"Recorded contraindication flags: {flag_text}.",
            f"Deterioration alert recorded: {'Yes' if case.get('deterioration_alert') else 'No' }.",
            "This section reports recorded data only; it does not establish a diagnosis.",
            "",
            "RECOMMENDATION / REQUEST",
            f"Referral urgency selected by clinician: {urgency}.",
            f"Referral reason: {reason}.",
            "Please acknowledge receipt and complete local clinical assessment on arrival.",
        )
    )
