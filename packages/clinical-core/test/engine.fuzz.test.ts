// Ported from backend/tests/test_classifier_fuzz.py. Property/fuzz
// robustness tests for triage()/assignTier() — distinct from "the rules
// are clinically correct" (engine.test.ts): this checks the engine NEVER
// crashes and NEVER breaks its output contract on any schema-reachable
// input, and that the safety-net invariant holds under randomized noise,
// not just hand-picked cases. Deterministic (seeded) so a failure
// reproduces.

import { describe, expect, it } from "vitest";
import { ALLOWED_SYMPTOMS } from "../src/schema.js";
import { assignTier } from "../src/rules/engine.js";
import { triage, type TriageFormInput } from "../src/triage.js";

const TIERS = new Set(["ROUTINE", "URGENT", "EMERGENCY"]);
const SYMPTOMS = [...ALLOWED_SYMPTOMS];
const COMPLAINTS = ["Fever", "Chest pain / tightness", "Weakness / fatigue", "Other", ""];
const DURATIONS = ["Less than 1 hour", "1-6 hours", "6-24 hours", "1-3 days", "More than 3 days", ""];
const LOCATIONS = ["Rural District", "Mumbai City", "", "Remote Tribal Area"];
const CONDITIONS = ["", "diabetes", "hypertension, heart disease"];
const MEDICATIONS = ["", "metformin", "warfarin, atenolol"];
const SEX: Array<"male" | "female" | "other" | null> = ["male", "female", "other", null];

// Schema-reachable value pools, including null (optional vitals are often
// absent in the field) and the exact inclusive bounds from schema.ts.
const AGES = [0, 0.08, 0.25, 0.5, 1, 2, 5, 12, 17, 18, 40, 65, 90, 120];
const BP_SYS = [null, 30, 60, 70, 90, 100, 120, 160, 180, 220, 300];
const BP_DIA = [null, 30, 50, 70, 80, 110, 120, 200];
const SPO2 = [null, 50, 70, 84, 85, 88, 91, 92, 95, 100];
const HR = [null, 10, 34, 35, 40, 74, 120, 130, 170, 171, 250];
const TEMP = [null, 25.0, 32.5, 33.0, 35.0, 37.0, 38.0, 39.1, 41.5, 45.0];

// Deterministic mulberry32 PRNG so failures reproduce without a runtime dep.
function makeRng(seed: number) {
  let a = seed >>> 0;
  return function rng() {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function pick<T>(rng: () => number, arr: readonly T[]): T {
  return arr[Math.floor(rng() * arr.length)]!;
}
function sample<T>(rng: () => number, arr: readonly T[], n: number): T[] {
  const pool = [...arr];
  const out: T[] = [];
  for (let i = 0; i < n && pool.length > 0; i++) {
    const idx = Math.floor(rng() * pool.length);
    out.push(pool.splice(idx, 1)[0]!);
  }
  return out;
}

function randomCase(rng: () => number): TriageFormInput {
  const nSym = Math.floor(rng() * Math.min(SYMPTOMS.length, 6) + 1) - 1;
  return {
    patient_age: pick(rng, AGES),
    patient_sex: pick(rng, SEX),
    bp_systolic: pick(rng, BP_SYS),
    bp_diastolic: pick(rng, BP_DIA),
    spo2: pick(rng, SPO2),
    heart_rate: pick(rng, HR),
    temperature: pick(rng, TEMP),
    symptoms: sample(rng, SYMPTOMS, Math.max(0, nSym)),
    chief_complaint: pick(rng, COMPLAINTS),
    complaint_duration: pick(rng, DURATIONS),
    location: pick(rng, LOCATIONS),
    known_conditions: pick(rng, CONDITIONS),
    current_medications: pick(rng, MEDICATIONS),
    is_pregnant: pick(rng, [null, false, true] as const),
  };
}

function assertValidResult(r: ReturnType<typeof triage>) {
  expect(TIERS.has(r.tier)).toBe(true);
  expect(Array.isArray(r.firedRules)).toBe(true);
  expect(Array.isArray(r.contraindicationFlags)).toBe(true);
  expect(r.model).toBeUndefined(); // no tree bundle supplied in this suite
}

describe("triage() fuzz: never crashes, output contract always holds", () => {
  it("6000 randomized schema-reachable cases", () => {
    const rng = makeRng(20260710);
    for (let i = 0; i < 6000; i++) {
      const c = randomCase(rng);
      const r = triage(c); // must not throw
      assertValidResult(r);
    }
  });
});

describe("fuzz: extreme single vital is always EMERGENCY", () => {
  it("2000 randomized cases with an extreme vital overridden", () => {
    const rng = makeRng(11);
    const extreme: Array<Partial<TriageFormInput>> = [
      { spo2: 84 },
      { spo2: 60 },
      { heart_rate: 34 },
      { heart_rate: 200 },
      { bp_systolic: 60 },
      { bp_systolic: 240, bp_diastolic: 120 },
      { temperature: 42.0 },
      { temperature: 32.0 },
    ];
    for (let i = 0; i < 2000; i++) {
      const base = randomCase(rng);
      const ov = pick(rng, extreme);
      const c = { ...base, ...ov };
      // Don't let a random low systolic invalidate the diastolic<systolic rule.
      if ("bp_systolic" in ov && c.bp_diastolic !== null && c.bp_diastolic >= (c.bp_systolic ?? Infinity)) {
        c.bp_diastolic = null;
      }
      const r = assignTier(c);
      expect(r.tier, `extreme ${JSON.stringify(ov)} not EMERGENCY: ${JSON.stringify(c)}`).toBe("EMERGENCY");
    }
  });
});

describe("fuzz: critical symptom is always EMERGENCY", () => {
  it("2000 randomized cases with a critical symptom added", () => {
    const rng = makeRng(22);
    const critical = ["altered_consciousness", "seizure", "severe_bleeding", "swelling_face_throat"];
    for (let i = 0; i < 2000; i++) {
      const base = randomCase(rng);
      const symptoms = [...new Set([...base.symptoms, pick(rng, critical)])];
      const r = assignTier({ ...base, symptoms });
      expect(r.tier, `critical symptom case not EMERGENCY: ${JSON.stringify(symptoms)}`).toBe("EMERGENCY");
    }
  });
});

describe("fuzz: all vitals missing still classifies", () => {
  it("1000 randomized cases with every optional vital null", () => {
    const rng = makeRng(33);
    for (let i = 0; i < 1000; i++) {
      const base = randomCase(rng);
      const c: TriageFormInput = {
        ...base,
        bp_systolic: null,
        bp_diastolic: null,
        spo2: null,
        heart_rate: null,
        temperature: null,
      };
      const r = triage(c); // must not throw
      assertValidResult(r);
    }
  });
});
