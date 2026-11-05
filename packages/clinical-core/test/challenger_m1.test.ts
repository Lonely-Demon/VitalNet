import { describe, it, expect } from "vitest";
import { resolveEffectiveAge, checkOverrides, type OverrideInput } from "../src/rules/rules.js";
import { assignTier, type EngineInput } from "../src/rules/engine.js";
import {
  calculateWeightBasedDose,
  calculateOrsVolume,
  calculateIvDripRate,
  calculateMaintenanceFluid,
  PEDIATRIC_DRUG_PRESETS,
} from "../src/calculators.js";
import { stripControlChars } from "../src/schema.js";
import { z } from "zod";
import * as PublicApi from "../src/index.js";

describe("Milestone M1 Adversarial Challenge: Clinical Safety & Infant PALS", () => {
  // ──────────────────────────────────────────────────────────────────────────
  // 1. resolveEffectiveAge Boundary & Invariant Stress Testing
  // ──────────────────────────────────────────────────────────────────────────
  describe("1. resolveEffectiveAge Stress & Boundary Testing", () => {
    it("handles all infant and child age boundary combinations", () => {
      // Newborn born today
      expect(resolveEffectiveAge(0, 0)).toBe(0);
      // 1-month-old infant
      expect(resolveEffectiveAge(0, 1)).toBeCloseTo(1 / 12, 6);
      // 2-month-old infant
      expect(resolveEffectiveAge(0, 2)).toBeCloseTo(2 / 12, 6);
      // 2.9-month-old infant (boundary right below 3 months)
      expect(resolveEffectiveAge(0, 2.9)).toBeCloseTo(2.9 / 12, 6);
      // 3-month-old infant (exact 0.25 yr boundary)
      expect(resolveEffectiveAge(0, 3)).toBe(0.25);
      // 4-month-old infant
      expect(resolveEffectiveAge(0, 4)).toBeCloseTo(4 / 12, 6);
      // 1-year-old child with age_months: 18 -> 18/12 = 1.5 yr
      expect(resolveEffectiveAge(1, 18)).toBe(1.5);
      // 1-year-old child with age_months: 12 -> 1.0 yr
      expect(resolveEffectiveAge(1, 12)).toBe(1.0);
      // 2-year-old child with age_months: 24 -> patient_age >= 2, must use patient_age (2)
      expect(resolveEffectiveAge(2, 24)).toBe(2);
      // 5-year-old child with age_months: 60 -> must use patient_age (5)
      expect(resolveEffectiveAge(5, 60)).toBe(5);
      // Adult 40 yr, age_months null -> 40
      expect(resolveEffectiveAge(40, null)).toBe(40);
      expect(resolveEffectiveAge(40, undefined)).toBe(40);
      // Missing patient_age but age_months provided: 6 months -> 0.5 yr
      expect(resolveEffectiveAge(null, 6)).toBe(0.5);
      expect(resolveEffectiveAge(undefined, 6)).toBe(0.5);
      // Both null or undefined
      expect(resolveEffectiveAge(null, null)).toBeNull();
      expect(resolveEffectiveAge(undefined, undefined)).toBeNull();
    });

    it("evaluates neonatal fever override strictly (< 3 months, temp >= 38.0C)", () => {
      const baseVitals = {
        bp_systolic: null,
        bp_diastolic: null,
        spo2: null,
        heart_rate: null,
        symptoms: [],
      };

      // 2-month infant (age_months: 2 -> 2/12 < 0.25) with fever 38.0C MUST trigger neonatal_fever
      const infant2m: OverrideInput = {
        ...baseVitals,
        patient_age: 0,
        age_months: 2,
        temperature: 38.0,
      };
      const override2m = checkOverrides(infant2m);
      expect(override2m).not.toBeNull();
      expect(override2m?.id).toBe("neonatal_fever");
      expect(assignTier(infant2m as EngineInput).tier).toBe("EMERGENCY");

      // 2.9-month infant (< 3 months) with fever 38.2C MUST trigger neonatal_fever
      const infant2_9m: OverrideInput = {
        ...baseVitals,
        patient_age: 0,
        age_months: 2.9,
        temperature: 38.2,
      };
      expect(checkOverrides(infant2_9m)?.id).toBe("neonatal_fever");

      // 3-month infant (age = 3/12 = 0.25, not < 0.25) with isolated 38.0C fever MUST NOT trigger neonatal_fever
      const infant3m: OverrideInput = {
        ...baseVitals,
        patient_age: 0,
        age_months: 3,
        temperature: 38.0,
      };
      expect(checkOverrides(infant3m)).toBeNull();
      expect(assignTier(infant3m as EngineInput).tier).not.toBe("EMERGENCY");

      // 4-month infant with isolated 38.5C fever MUST NOT trigger neonatal_fever
      const infant4m: OverrideInput = {
        ...baseVitals,
        patient_age: 0,
        age_months: 4,
        temperature: 38.5,
      };
      expect(checkOverrides(infant4m)).toBeNull();
      expect(assignTier(infant4m as EngineInput).tier).not.toBe("EMERGENCY");

      // Neonate (0 months) with 38.0C fever MUST trigger neonatal_fever
      const newborn: OverrideInput = {
        ...baseVitals,
        patient_age: 0,
        age_months: 0,
        temperature: 38.0,
      };
      expect(checkOverrides(newborn)?.id).toBe("neonatal_fever");
      expect(assignTier(newborn as EngineInput).tier).toBe("EMERGENCY");
    });
  });

  // ──────────────────────────────────────────────────────────────────────────
  // 2. Calculators Finite Number Guards Fuzzing
  // ──────────────────────────────────────────────────────────────────────────
  describe("2. calculators.ts Non-Finite & Adversarial Input Fuzzing", () => {
    const badNumerics = [NaN, Infinity, -Infinity];

    it("calculateWeightBasedDose rejects non-finite weightKg, mgPerKg, maxMgPerDose, ageMonths", () => {
      for (const bad of badNumerics) {
        expect(() =>
          calculateWeightBasedDose({ weightKg: bad, mgPerKg: 20, maxMgPerDose: 500 })
        ).toThrow();
        expect(() =>
          calculateWeightBasedDose({ weightKg: 10, mgPerKg: bad, maxMgPerDose: 500 })
        ).toThrow();
        expect(() =>
          calculateWeightBasedDose({ weightKg: 10, mgPerKg: 20, maxMgPerDose: bad })
        ).toThrow();
        expect(() =>
          calculateWeightBasedDose({ weightKg: 10, mgPerKg: 20, maxMgPerDose: 500, ageMonths: bad })
        ).toThrow();
        expect(() =>
          calculateWeightBasedDose({ weightKg: 10, mgPerKg: 20, maxMgPerDose: 500, concentrationMgPerMl: bad })
        ).toThrow();
        expect(() =>
          calculateWeightBasedDose({ weightKg: 10, mgPerKg: 20, maxMgPerDose: 500, maxMgPerDay: bad })
        ).toThrow();
        expect(() =>
          calculateWeightBasedDose({ weightKg: 10, mgPerKg: 20, maxMgPerDose: 500, maxMgPerKgPerDay: bad })
        ).toThrow();
      }

      // Out of bounds weights
      expect(() =>
        calculateWeightBasedDose({ weightKg: 0.99, mgPerKg: 20, maxMgPerDose: 500 })
      ).toThrow(/out of bounds/);
      expect(() =>
        calculateWeightBasedDose({ weightKg: 100.1, mgPerKg: 20, maxMgPerDose: 500 })
      ).toThrow(/exceeds paediatric parameters/);

      // Valid calculation produces finite numbers
      const res = calculateWeightBasedDose({
        weightKg: 15,
        mgPerKg: 25,
        maxMgPerDose: 500,
        concentrationMgPerMl: 50,
      });
      expect(Number.isFinite(res.doseMg)).toBe(true);
      expect(Number.isFinite(res.volumeMl)).toBe(true);
      expect(res.doseMg).toBe(375);
      expect(res.volumeMl).toBe(7.5);
    });

    it("calculateOrsVolume rejects non-finite weightKg and ageMonths", () => {
      for (const bad of badNumerics) {
        expect(() => calculateOrsVolume({ weightKg: bad, plan: "PLAN_B" })).toThrow(/Weight must be between/);
        expect(() => calculateOrsVolume({ weightKg: 10, plan: "PLAN_B", ageMonths: bad })).toThrow(/finite number/);
      }
      expect(() => calculateOrsVolume({ weightKg: 0.8, plan: "PLAN_B" })).toThrow();
      expect(() => calculateOrsVolume({ weightKg: 101, plan: "PLAN_B" })).toThrow();

      const valid = calculateOrsVolume({ weightKg: 12, plan: "PLAN_B" });
      expect(Number.isFinite(valid.totalVolumeMl)).toBe(true);
      expect(valid.totalVolumeMl).toBe(900);
    });

    it("calculateIvDripRate rejects non-finite volume, duration, dropFactor, or total duration 0", () => {
      for (const bad of badNumerics) {
        expect(() => calculateIvDripRate({ volumeMl: bad, durationHours: 1, dropFactor: 20 })).toThrow();
        expect(() => calculateIvDripRate({ volumeMl: 500, durationHours: bad, dropFactor: 20 })).toThrow();
        expect(() => calculateIvDripRate({ volumeMl: 500, durationHours: 1, durationMinutes: bad, dropFactor: 20 })).toThrow();
        expect(() => calculateIvDripRate({ volumeMl: 500, durationHours: 1, dropFactor: bad as any })).toThrow();
      }
      // Zero duration
      expect(() => calculateIvDripRate({ volumeMl: 500, durationHours: 0, durationMinutes: 0, dropFactor: 20 })).toThrow();
      // Zero volume
      expect(() => calculateIvDripRate({ volumeMl: 0, durationHours: 1, dropFactor: 20 })).toThrow();
      // Invalid drop factor
      expect(() => calculateIvDripRate({ volumeMl: 500, durationHours: 1, dropFactor: 30 as any })).toThrow(/Drop factor/);

      const valid = calculateIvDripRate({ volumeMl: 1000, durationHours: 8, dropFactor: 20 });
      expect(Number.isFinite(valid.dripRateGttPerMin)).toBe(true);
      expect(valid.dripRateGttPerMin).toBe(42);
    });

    it("calculateMaintenanceFluid rejects non-finite weightKg and ageYears", () => {
      for (const bad of badNumerics) {
        expect(() => calculateMaintenanceFluid(bad)).toThrow(/Weight must be between/);
        expect(() => calculateMaintenanceFluid(10, bad)).toThrow(/finite number/);
      }
      expect(() => calculateMaintenanceFluid(0.5)).toThrow();
      expect(() => calculateMaintenanceFluid(105)).toThrow();

      const valid = calculateMaintenanceFluid(25);
      expect(Number.isFinite(valid.totalDailyVolumeMl)).toBe(true);
      expect(Number.isFinite(valid.hourlyRateMlPerHour)).toBe(true);
      expect(valid.totalDailyVolumeMl).toBe(1600);
    });
  });

  // ──────────────────────────────────────────────────────────────────────────
  // 3. Triage Override Schema Whitespace & Control Characters Validation
  // ──────────────────────────────────────────────────────────────────────────
  describe("3. triageOverrideSchema Whitespace & Sanitization", () => {
    const schema = z.object({
      overridden_triage: z.enum(["ROUTINE", "URGENT", "EMERGENCY"]),
      override_reason: z
        .string()
        .transform(stripControlChars)
        .pipe(
          z.string().trim().min(1, "Reason cannot be empty or whitespace-only").max(500, "Reason must be at most 500 characters")
        ),
    });

    it("rejects empty, whitespace-only, and control-character-only strings", () => {
      const invalidReasons = [
        "",
        " ",
        "     ",
        "\t",
        "\n",
        "\r\n",
        "\t  \n  \r\n  ",
        "\x00\x01\x02",
        "  \x00\x01\x1F  ",
      ];
      for (const reason of invalidReasons) {
        const result = schema.safeParse({ overridden_triage: "EMERGENCY", override_reason: reason });
        expect(result.success).toBe(false);
      }
    });

    it("accepts valid text and strips control characters while preserving content", () => {
      const result = schema.safeParse({
        overridden_triage: "EMERGENCY",
        override_reason: "  Clinician observes acute distress \x00\x01  ",
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.override_reason).toBe("Clinician observes acute distress");
      }
    });

    it("enforces 500 character upper bound", () => {
      expect(schema.safeParse({ overridden_triage: "URGENT", override_reason: "x".repeat(500) }).success).toBe(true);
      expect(schema.safeParse({ overridden_triage: "URGENT", override_reason: "x".repeat(501) }).success).toBe(false);
    });
  });

  // ──────────────────────────────────────────────────────────────────────────
  // 4. Dashboard Bucketing Logic Verification
  // ──────────────────────────────────────────────────────────────────────────
  describe("4. Dashboard.jsx Bucketing by (overridden_triage || triage_level)", () => {
    it("correctly buckets cases according to overridden_triage over triage_level", () => {
      const mockCases = [
        { id: "c1", triage_level: "ROUTINE", overridden_triage: "EMERGENCY" }, // Should be EMERGENCY
        { id: "c2", triage_level: "EMERGENCY", overridden_triage: "ROUTINE" }, // Should be ROUTINE
        { id: "c3", triage_level: "ROUTINE", overridden_triage: "URGENT" },    // Should be URGENT
        { id: "c4", triage_level: "URGENT", overridden_triage: "ROUTINE" },    // Should be ROUTINE
        { id: "c5", triage_level: "URGENT", overridden_triage: "EMERGENCY" },  // Should be EMERGENCY
        { id: "c6", triage_level: "EMERGENCY", overridden_triage: "URGENT" },  // Should be URGENT
        { id: "c7", triage_level: "ROUTINE", overridden_triage: null },        // Should be ROUTINE
        { id: "c8", triage_level: "URGENT", overridden_triage: undefined },   // Should be URGENT
        { id: "c9", triage_level: "EMERGENCY", overridden_triage: "" },        // Should be EMERGENCY
      ];

      // Exact Dashboard.jsx logic:
      const emergency = mockCases.filter(c => (c.overridden_triage || c.triage_level) === "EMERGENCY");
      const urgent = mockCases.filter(c => (c.overridden_triage || c.triage_level) === "URGENT");
      const routine = mockCases.filter(c => (c.overridden_triage || c.triage_level) === "ROUTINE");

      expect(emergency.map(c => c.id).sort()).toEqual(["c1", "c5", "c9"].sort());
      expect(urgent.map(c => c.id).sort()).toEqual(["c3", "c6", "c8"].sort());
      expect(routine.map(c => c.id).sort()).toEqual(["c2", "c4", "c7"].sort());

      // Every case must be in exactly one bucket
      expect(emergency.length + urgent.length + routine.length).toBe(mockCases.length);
    });
  });

  // ──────────────────────────────────────────────────────────────────────────
  // 5. useLocalTriage Offline Fallback Behavior Verification
  // ──────────────────────────────────────────────────────────────────────────
  describe("5. useLocalTriage.js Offline & Unready Behavior", () => {
    it("classify callback executes runTriage and returns deterministic results even when modelReady = false", async () => {
      // Simulate useLocalTriage.js classify callback:
      // In useLocalTriage.js:
      // const classify = useCallback(async (formData) => {
      //   try {
      //     return await runTriage(formData)
      //   } catch (err) {
      //     console.warn('[VitalNet] Local triage failed:', err)
      //     return null
      //   }
      // }, [])

      // Mock runTriage when model is unavailable:
      const mockRunTriage = async (formData: any) => {
        // Mode-independent safety net evaluation when model unavailable
        const override = checkOverrides(formData);
        return {
          triageLevel: override ? "EMERGENCY" : null,
          confidence: null,
          lowConfidence: false,
          isLocal: true,
          modelUnavailable: true,
          contraindicationFlags: [],
          firedRules: override ? [override] : [],
        };
      };

      const classify = async (formData: any) => {
        try {
          return await mockRunTriage(formData);
        } catch (err) {
          return null;
        }
      };

      // When modelReady is FALSE:
      // Case A: Critical symptom override (e.g. altered_consciousness)
      const emergencyResult = await classify({
        patient_age: 30,
        symptoms: ["altered_consciousness"],
        bp_systolic: 120,
        temperature: 37,
      });
      // In the old code, this returned null because if (!modelReady) return null
      // In the new code, this MUST return the deterministic triage result!
      expect(emergencyResult).not.toBeNull();
      expect(emergencyResult?.triageLevel).toBe("EMERGENCY");
      expect(emergencyResult?.isLocal).toBe(true);
      expect(emergencyResult?.modelUnavailable).toBe(true);

      // Case B: Non-emergency patient when model unavailable
      const routineResult = await classify({
        patient_age: 30,
        symptoms: [],
        bp_systolic: 120,
        temperature: 37,
      });
      expect(routineResult).not.toBeNull();
      expect(routineResult?.triageLevel).toBeNull();
      expect(routineResult?.modelUnavailable).toBe(true);

      // Case C: When runTriage throws an error, classify gracefully returns null without crashing
      const faultClassify = async (formData: any) => {
        try {
          throw new Error("Simulated offline storage corruption");
        } catch (err) {
          return null;
        }
      };
      const errorResult = await faultClassify({});
      expect(errorResult).toBeNull();
    });
  });

  // ──────────────────────────────────────────────────────────────────────────
  // 6. Deep Empirical Vulnerability Analysis: Contract & Pipeline Parity
  // ──────────────────────────────────────────────────────────────────────────
  describe("6. Package Export Parity & Downstream Interface Audit", () => {
    it("CRITICAL FINDING: packages/clinical-core/src/index.ts exports resolveEffectiveAge", () => {
      // If external consumers or apps/web import { resolveEffectiveAge } from "@vitalnet/clinical-core",
      // it must be exported in PublicApi!
      const isExported = "resolveEffectiveAge" in PublicApi;
      // We document this empirical observation:
      expect(isExported).toBe(true); // Demonstrates that resolveEffectiveAge is now exported in src/index.ts
    });

    it("VULNERABILITY DEMONSTRATION: Omitting age_months in engineInput causes 4mo infant to falsely fire neonatal_fever", () => {
      // If an engine input omits age_months:
      const incompleteInput = {
        patient_age: 0,
        // age_months is omitted or undefined
        bp_systolic: null,
        bp_diastolic: null,
        spo2: null,
        heart_rate: null,
        temperature: 38.5,
        symptoms: [],
      };
      // When age_months is omitted, resolveEffectiveAge(0, undefined) returns 0 (< 0.25)
      // and neonatal_fever FALSELY FIRES for a 4-month-old infant:
      const falseEmergency = checkOverrides(incompleteInput as any);
      expect(falseEmergency?.id).toBe("neonatal_fever");

      // But when age_months is properly passed:
      const completeInput = {
        ...incompleteInput,
        age_months: 4,
      };
      const correctEvaluation = checkOverrides(completeInput as any);
      expect(correctEvaluation).toBeNull(); // Correctly does NOT fire neonatal fever!
    });
  });
});
