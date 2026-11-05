// Ported from backend/tests/test_classifier_safety.py — asserts the
// guarantees that matter clinically, now against the promoted rules-first
// engine (rules/engine.ts) instead of the Python inference path. Every case
// here is a citable "embedded test vector" per the README's design
// invariant: a rule with no vector is a rule nobody has verified.

import { describe, expect, it } from "vitest";
import { assignTier, type EngineInput } from "../src/rules/engine.js";
import { news2ConcerningVital, resolveEffectiveAge } from "../src/rules/rules.js";

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
  expect(r.firedRules.some((rule) => rule.id === "neonatal_fever")).toBe(true);
});

describe("resolveEffectiveAge & infant fever safety (CRITICAL-2)", () => {
  it("resolves fractional years when patient_age < 2 and age_months is provided", () => {
    expect(resolveEffectiveAge(0, 4)).toBeCloseTo(4 / 12, 5);
    expect(resolveEffectiveAge(0, 2)).toBeCloseTo(2 / 12, 5);
    expect(resolveEffectiveAge(1, 14)).toBeCloseTo(14 / 12, 5);
  });

  it("does not override with age_months when patient_age >= 2", () => {
    expect(resolveEffectiveAge(3, 36)).toBe(3);
    expect(resolveEffectiveAge(5, 60)).toBe(5);
  });

  it("handles nullish inputs gracefully", () => {
    expect(resolveEffectiveAge(40, null)).toBe(40);
    expect(resolveEffectiveAge(40, undefined)).toBe(40);
    expect(resolveEffectiveAge(null, 6)).toBeCloseTo(6 / 12, 5);
    expect(resolveEffectiveAge(undefined, 6)).toBeCloseTo(6 / 12, 5);
    expect(resolveEffectiveAge(null, null)).toBeNull();
    expect(resolveEffectiveAge(undefined, undefined)).toBeNull();
  });

  it("triggers neonatal fever override for 2-month-old infant with fever", () => {
    // 2-month-old infant (2/12 ≈ 0.167 yr < 0.25 yr): fever >= 38.0C is neonatal emergency
    const r = assignTier(withCase({ patient_age: 0, age_months: 2, temperature: 38.5 }));
    expect(r.tier).toBe("EMERGENCY");
    expect(r.firedRules.some((rule) => rule.id === "neonatal_fever")).toBe(true);
  });

  it("does NOT trigger neonatal fever for 4-month-old infant with fever", () => {
    // 4-month-old infant (4/12 ≈ 0.333 yr >= 0.25 yr): NOT a neonate (<3 mo)
    // Stable infant vitals: HR 120 (normal 100-160), BP 80 (normal >=70)
    const r = assignTier(withCase({
      patient_age: 0,
      age_months: 4,
      temperature: 38.5,
      heart_rate: 120,
      bp_systolic: 80,
      spo2: 98,
    }));
    // Should NOT trigger neonatal_fever override
    expect(r.firedRules.some((rule) => rule.id === "neonatal_fever")).toBe(false);
  });
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

describe("hypertensive_neuro_emergency_aggregate is unreachable (redundant with checkOverrides)", () => {
  // engine.ts's own header comment on this branch claims a test asserts
  // the invariant; this is that test. checkOverrides (rules.ts) checks the
  // identical BP>=180 + neuro-symptom condition and returns EARLY —
  // assignTier never reaches its own aggregate-scorer copy of the same
  // check. If this ever fires, either checkOverrides regressed or the two
  // conditions have drifted out of sync.
  //
  // altered_consciousness is excluded here even though it's also in
  // HYPERTENSIVE_NEURO: it's checked earlier still, in checkOverrides'
  // CRITICAL_SYMPTOMS_OVERRIDE clause, so it fires "critical_symptom_override"
  // rather than "hypertensive_neuro_emergency" — a different override, but
  // the same point (assignTier's own copy is still never reached).
  for (const symptom of ["severe_headache", "weakness_one_side", "difficulty_speaking"]) {
    it(`BP 185 + ${symptom} fires via the override, not the aggregate-scorer's own copy`, () => {
      const r = assignTier(withCase({ bp_systolic: 185, symptoms: [symptom] }));
      expect(r.tier).toBe("EMERGENCY");
      const firedIds = r.firedRules.map((f) => f.id);
      expect(firedIds).toContain("hypertensive_neuro_emergency");
      expect(firedIds).not.toContain("hypertensive_neuro_emergency_aggregate");
      // The override short-circuits assignTier entirely — exactly one rule fires.
      expect(r.firedRules.length).toBe(1);
    });
  }

  it("BP 185 + altered_consciousness fires the earlier critical-symptom override (composite rule)", () => {
    const r = assignTier(withCase({ bp_systolic: 185, symptoms: ["altered_consciousness"] }));
    expect(r.tier).toBe("EMERGENCY");
    const firedIds = r.firedRules.map((f) => f.id);
    expect(firedIds.some((id) => id.includes("critical_symptom_override"))).toBe(true);
    expect(firedIds).not.toContain("hypertensive_neuro_emergency_aggregate");
  });

  it("multiple overrides fire together with composite ID (VN-2026-08-C6-02)", () => {
    const r = assignTier(withCase({ heart_rate: 190, bp_systolic: 230, symptoms: ["altered_consciousness"] }));
    expect(r.tier).toBe("EMERGENCY");
    expect(r.firedRules.length).toBe(1);
    expect(r.firedRules[0]!.id).toBe("critical_symptom_override+extreme_hr+extreme_bp+hypertensive_neuro_emergency");
  });

  describe("PALS-aligned vital threshold age bands (VN-2026-08-C6-01)", () => {
    it("infant (0.5yr) with HR 175 is NOT extreme HR override", () => {
      const r = assignTier(withCase({ patient_age: 0.5, heart_rate: 175 }));
      expect(r.firedRules.some((f) => f.id.includes("extreme_hr"))).toBe(false);
    });

    it("toddler (2yr) with HR 185 IS extreme HR override", () => {
      const r = assignTier(withCase({ patient_age: 2, heart_rate: 185 }));
      expect(r.tier).toBe("EMERGENCY");
      expect(r.firedRules.some((f) => f.id.includes("extreme_hr"))).toBe(true);
    });

    it("10-year-old with SBP 85 is NOT extreme hypotension", () => {
      const r = assignTier(withCase({ patient_age: 10, bp_systolic: 85 }));
      expect(r.firedRules.some((f) => f.id.includes("extreme_bp"))).toBe(false);
    });

    it("10-year-old with SBP 75 IS extreme hypotension (PALS 5th percentile is 80)", () => {
      const r = assignTier(withCase({ patient_age: 10, bp_systolic: 75 }));
      expect(r.tier).toBe("EMERGENCY");
      expect(r.firedRules.some((f) => f.id.includes("extreme_bp"))).toBe(true);
    });
  });
});
