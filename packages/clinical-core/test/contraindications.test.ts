// Ported from apps/web/tests/contraindications.test.mjs (itself a parity
// guard against backend/app/ml/contraindications.py). Now that both
// mirrors are gone, this is just the direct test of the one remaining
// implementation — kept as flag-COUNT assertions per case, matching the
// original suite's granularity.

import { describe, expect, it } from "vitest";
import { checkContraindications, type ContraindicationInput } from "../src/contraindications.js";

const BASE: ContraindicationInput = {
  current_medications: "",
  known_conditions: "",
  symptoms: [],
  heart_rate: 74,
};

function withCase(overrides: Partial<ContraindicationInput>): ContraindicationInput {
  return { ...BASE, ...overrides };
}

describe("checkContraindications", () => {
  it("no medications -> no flags", () => {
    expect(checkContraindications(withCase({}))).toHaveLength(0);
  });

  it("medication alone, no matching condition/symptom -> no flags", () => {
    expect(checkContraindications(withCase({ current_medications: "ibuprofen 400mg" }))).toHaveLength(0);
  });

  it("NSAID + renal condition -> flagged", () => {
    expect(
      checkContraindications(withCase({ current_medications: "ibuprofen", known_conditions: "chronic kidney disease" })),
    ).toHaveLength(1);
  });

  it("ACE inhibitor + renal condition -> flagged", () => {
    expect(
      checkContraindications(withCase({ current_medications: "lisinopril 10mg", known_conditions: "renal impairment" })),
    ).toHaveLength(1);
  });

  it("metformin + persistent vomiting -> flagged", () => {
    expect(
      checkContraindications(withCase({ current_medications: "metformin 500mg", symptoms: ["persistent_vomiting"] })),
    ).toHaveLength(1);
  });

  it("metformin without vomiting -> no flags", () => {
    expect(checkContraindications(withCase({ current_medications: "metformin 500mg" }))).toHaveLength(0);
  });

  it("anticoagulant + severe bleeding -> flagged", () => {
    expect(
      checkContraindications(withCase({ current_medications: "warfarin", symptoms: ["severe_bleeding"] })),
    ).toHaveLength(1);
  });

  it("beta-blocker + bradycardia -> flagged", () => {
    expect(checkContraindications(withCase({ current_medications: "atenolol 50mg", heart_rate: 48 }))).toHaveLength(1);
  });

  it("beta-blocker + normal heart rate -> no flags", () => {
    expect(checkContraindications(withCase({ current_medications: "atenolol 50mg", heart_rate: 74 }))).toHaveLength(0);
  });

  it("insulin + altered consciousness -> flagged", () => {
    expect(
      checkContraindications(withCase({ current_medications: "insulin glargine", symptoms: ["altered_consciousness"] })),
    ).toHaveLength(1);
  });

  it("multiple medications -> multiple flags", () => {
    expect(
      checkContraindications(
        withCase({ current_medications: "ibuprofen, lisinopril", known_conditions: "chronic kidney disease" }),
      ),
    ).toHaveLength(2);
  });

  it("case-insensitive matching", () => {
    expect(
      checkContraindications(withCase({ current_medications: "IBUPROFEN", known_conditions: "Chronic KIDNEY Disease" })),
    ).toHaveLength(1);
  });
});
