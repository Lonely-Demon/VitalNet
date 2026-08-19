import { assertEquals } from "@std/assert";
import { buildPaediatricAdvisory } from "../_shared/paediatric.ts";

Deno.test("paediatric advisory is disabled by default semantics", () => {
  const advisory = buildPaediatricAdvisory(
    { patient_age: 1, age_months: 8, muac_mm: 110 },
    false,
  );
  assertEquals(advisory.status, "disabled_pending_governance");
  assertEquals(advisory.eligible_for_muac_screen, null);
});

Deno.test("enabled advisory remains research-only and explicit", () => {
  const advisory = buildPaediatricAdvisory(
    { patient_age: 1, age_months: 8, muac_mm: 110 },
    true,
  );
  assertEquals(advisory.status, "research_only");
  assertEquals(advisory.eligible_for_muac_screen, true);
  assertEquals(advisory.muac_screen_status, "below_reference_threshold_full_assessment_needed");
  assertEquals(advisory.clinical_interpretation_required, true);
});
