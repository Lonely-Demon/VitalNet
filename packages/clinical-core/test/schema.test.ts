import { describe, expect, it } from "vitest";
import { validateIntakeForm } from "../src/schema.js";

const BASE_VALID_FORM = {
  patient_name: "QA Phase42 Patient",
  patient_age: 30,
  patient_sex: "female" as const,
  location: "QA Synthetic Village",
  chief_complaint: "Fever",
  complaint_duration: "Less than 1 hour",
  consent_captured: true,
  consent_captured_at: new Date().toISOString(),
  patient_key: "2345-6789",
  symptoms: [],
};

describe("IntakeForm schema validation (human_review_reason and consent)", () => {
  it("Scenario 1: valid required fields, consent true, human_review_requested: false, undefined review reason passes validation", () => {
    const payload = {
      ...BASE_VALID_FORM,
      human_review_requested: false,
      human_review_reason: undefined,
    };
    const result = validateIntakeForm(payload);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.human_review_reason).toBeUndefined();
    }
  });

  it("rejection on null: human_review_reason as null fails validation with invalid input (proves schema requires string | undefined)", () => {
    const payload = {
      ...BASE_VALID_FORM,
      human_review_requested: false,
      human_review_reason: null,
    };
    const result = validateIntakeForm(payload);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.errors.human_review_reason).toBeDefined();
    }
  });

  it("Scenario 2: valid required fields, consent true, human_review_requested: true, nonblank review reason passes validation", () => {
    const payload = {
      ...BASE_VALID_FORM,
      human_review_requested: true,
      human_review_reason: "Patient appears lethargic and pale",
    };
    const result = validateIntakeForm(payload);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.human_review_reason).toBe("Patient appears lethargic and pale");
    }
  });

  it("Scenario 3: valid required fields, consent true, human_review_requested: true, blank/undefined review reason fails validation", () => {
    const payload = {
      ...BASE_VALID_FORM,
      human_review_requested: true,
      human_review_reason: undefined,
    };
    const result = validateIntakeForm(payload);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.errors.human_review_reason).toBe(
        "human_review_reason is required when review is requested",
      );
    }
  });

  it("un-captured consent is blocked by schema boundary", () => {
    const payload = {
      ...BASE_VALID_FORM,
      consent_captured: false,
    };
    const result = validateIntakeForm(payload);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.errors.consent_captured).toBe("Patient consent is required before submission");
    }
  });
});
