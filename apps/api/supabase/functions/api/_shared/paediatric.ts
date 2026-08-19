export const PAEDIATRIC_ADVISORY_VERSION = "paediatric_advisory.v1";
export const MUAC_REFERRAL_THRESHOLD_MM = 115;

type PaediatricInput = {
  patient_age: number;
  age_months?: number | null;
  muac_mm?: number | null;
};

export function buildPaediatricAdvisory(
  input: PaediatricInput,
  enabled: boolean,
): Record<string, unknown> {
  if (!enabled) {
    return {
      version: PAEDIATRIC_ADVISORY_VERSION,
      status: "disabled_pending_governance",
      eligible_for_muac_screen: null,
      muac_screen_status: "not_computed",
    };
  }

  const resolvedMonths = input.age_months ?? input.patient_age * 12;
  const eligible = resolvedMonths >= 6 && resolvedMonths <= 59;
  let screenStatus = "out_of_scope";
  if (eligible && input.muac_mm == null) screenStatus = "eligible_missing_muac";
  if (eligible && input.muac_mm != null) {
    screenStatus = input.muac_mm < MUAC_REFERRAL_THRESHOLD_MM
      ? "below_reference_threshold_full_assessment_needed"
      : "at_or_above_reference_threshold";
  }

  return {
    version: PAEDIATRIC_ADVISORY_VERSION,
    status: "research_only",
    eligible_for_muac_screen: eligible,
    age_months_used_for_scope: resolvedMonths,
    muac_screen_status: screenStatus,
    reference_threshold_mm: MUAC_REFERRAL_THRESHOLD_MM,
    clinical_interpretation_required: true,
  };
}
