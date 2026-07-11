// Ported from backend/tests/test_classifier_safety.py — asserts the
// guarantees that matter clinically, now against the promoted rules-first
// engine (rules/engine.ts) instead of the Python inference path. Every case
// here is a citable "embedded test vector" per the README's design
// invariant: a rule with no vector is a rule nobody has verified.

import { describe, expect, it } from "vitest";
import { assignTier, type EngineInput } from "../src/rules/engine.js";
import { news2ConcerningVital } from "../src/rules/rules.js";

const BASE: EngineInput = {
  patient_age: 40,
  bp_systolic: 120,
  bp_diastolic: 80,
  spo2: 98,
  heart_rate: 74,
  temperature: 37.0,
  symptoms: [],
};

function withCase(overrides: Partial<EngineInput>): EngineInput {
  return { ...BASE, ...overrides };
}

describe("extreme vitals always EMERGENCY (safety-net override)", () => {
  const cases: Array<Partial<EngineInput>> = [
    { spo2: 84 },
    { spo2: 70 },
    { heart_rate: 34 },
    { heart_rate: 180 },
    { bp_systolic: 65 },
    { bp_systolic: 240 },
    { temperature: 42.0 },
    { temperature: 32.5 },
  ];
  for (const ov of cases) {
    it(`${JSON.stringify(ov)} -> EMERGENCY`, () => {
      const r = assignTier(withCase(ov));
      expect(r.tier).toBe("EMERGENCY");
      expect(r.firedRules.length).toBeGreaterThan(0);
    });
  }
});

describe("critical symptoms always EMERGENCY", () => {
  for (const sym of ["altered_consciousness", "seizure", "severe_bleeding", "swelling_face_throat"]) {
    it(`${sym} -> EMERGENCY`, () => {
      const r = assignTier(withCase({ symptoms: [sym] }));
      expect(r.tier).toBe("EMERGENCY");
    });
  }
});

it("neonatal fever is EMERGENCY", () => {
  const r = assignTier(withCase({ patient_age: 0.1, temperature: 38.5 }));
  expect(r.tier).toBe("EMERGENCY");
});

describe("concerning-but-not-extreme vitals never ROUTINE", () => {
  const cases: Array<Partial<EngineInput>> = [
    { spo2: 92 },
    { spo2: 91 },
    { heart_rate: 122 },
    { heart_rate: 40 },
    { bp_systolic: 98 },
    { bp_systolic: 185 },
    { temperature: 39.3 },
    { temperature: 34.8 },
  ];
  for (const ov of cases) {
    it(`${JSON.stringify(ov)} -> URGENT or EMERGENCY`, () => {
      const form = withCase(ov);
      expect(news2ConcerningVital(form)).not.toBeNull();
      const r = assignTier(form);
      expect(["URGENT", "EMERGENCY"]).toContain(r.tier);
    });
  }
});

it("healthy vitals with no symptoms is ROUTINE", () => {
  const r = assignTier(withCase({}));
  expect(r.tier).toBe("ROUTINE");
});

describe("pregnancy — severe hypertension always EMERGENCY", () => {
  const cases: Array<Partial<EngineInput>> = [
    { bp_systolic: 160, bp_diastolic: 100 },
    { bp_systolic: 150, bp_diastolic: 110 },
    { bp_systolic: 170, bp_diastolic: 115 },
  ];
  for (const ov of cases) {
    it(`${JSON.stringify(ov)} + is_pregnant -> EMERGENCY`, () => {
      const r = assignTier(withCase({ ...ov, is_pregnant: true }));
      expect(r.tier).toBe("EMERGENCY");
    });

    it(`${JSON.stringify(ov)} without is_pregnant -> not this rule`, () => {
      const r = assignTier(withCase(ov));
      expect(r.firedRules.some((f) => f.id.startsWith("preeclampsia"))).toBe(false);
    });
  }
});

describe("pregnancy — moderate hypertension + severe feature is EMERGENCY", () => {
  for (const symptom of ["severe_headache", "severe_abdominal_pain"]) {
    it(`BP 145/95 + ${symptom} + is_pregnant -> EMERGENCY`, () => {
      const r = assignTier(withCase({ bp_systolic: 145, bp_diastolic: 95, is_pregnant: true, symptoms: [symptom] }));
      expect(r.tier).toBe("EMERGENCY");
    });
  }

  it("BP 145/95 + is_pregnant with no severe feature -> not this rule", () => {
    const r = assignTier(withCase({ bp_systolic: 145, bp_diastolic: 95, is_pregnant: true }));
    expect(r.firedRules.some((f) => f.id.startsWith("preeclampsia"))).toBe(false);
  });
});

describe("paediatric fix (v3.1.0/DECISIONS §31) — normal infants are not over-triaged", () => {
  it("6-month-old, HR 140, BP 85/55 (all normal for age) is not EMERGENCY", () => {
    const r = assignTier(withCase({ patient_age: 0.5, heart_rate: 140, bp_systolic: 85, bp_diastolic: 55, spo2: 97 }));
    expect(r.tier).not.toBe("EMERGENCY");
  });

  it("genuinely hypotensive infant for age still escalates", () => {
    // PALS 5th-percentile hypotension for a 6-month-old is SBP<70.
    const r = assignTier(withCase({ patient_age: 0.5, heart_rate: 170, bp_systolic: 60, spo2: 94 }));
    expect(r.tier).toBe("EMERGENCY");
  });

  it("adult with the same absolute BP (60) still triggers the adult extreme-BP override", () => {
    const r = assignTier(withCase({ patient_age: 40, bp_systolic: 60 }));
    expect(r.tier).toBe("EMERGENCY");
  });
});
