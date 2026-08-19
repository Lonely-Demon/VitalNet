"""Governance-gated paediatric capture and advisory metadata."""

from collections.abc import Mapping

PAEDIATRIC_ADVISORY_VERSION = "paediatric_advisory.v1"
MUAC_REFERRAL_THRESHOLD_MM = 115


def build_paediatric_advisory(
    case: Mapping[str, object],
    *,
    enabled: bool,
) -> dict[str, object]:
    """Return bounded metadata; never produce a diagnosis or treatment command.

    The helper is deliberately disabled by default. When enabled by a future
    qualified governance decision, it can support a research-only candidate
    study without being wired into triage or review flags.
    """
    age_years = case.get("patient_age")
    age_months = case.get("age_months")
    muac_mm = case.get("muac_mm")

    if not enabled:
        return {
            "version": PAEDIATRIC_ADVISORY_VERSION,
            "status": "disabled_pending_governance",
            "eligible_for_muac_screen": None,
            "muac_screen_status": "not_computed",
        }

    if not isinstance(age_years, int):
        return {
            "version": PAEDIATRIC_ADVISORY_VERSION,
            "status": "insufficient_age_data",
            "eligible_for_muac_screen": None,
            "muac_screen_status": "not_computed",
        }

    resolved_months = age_months if isinstance(age_months, int) else age_years * 12
    eligible = 6 <= resolved_months <= 59
    if not eligible:
        screen_status = "out_of_scope"
    elif not isinstance(muac_mm, int):
        screen_status = "eligible_missing_muac"
    elif muac_mm < MUAC_REFERRAL_THRESHOLD_MM:
        screen_status = "below_reference_threshold_full_assessment_needed"
    else:
        screen_status = "at_or_above_reference_threshold"

    return {
        "version": PAEDIATRIC_ADVISORY_VERSION,
        "status": "research_only",
        "eligible_for_muac_screen": eligible,
        "age_months_used_for_scope": resolved_months,
        "muac_screen_status": screen_status,
        "reference_threshold_mm": MUAC_REFERRAL_THRESHOLD_MM,
        "clinical_interpretation_required": True,
    }
