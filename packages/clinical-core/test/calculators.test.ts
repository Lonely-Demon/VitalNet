import { describe, it, expect } from "vitest";
import {
  calculateWeightBasedDose,
  calculateOrsVolume,
  calculateIvDripRate,
  calculateMaintenanceFluid,
  PEDIATRIC_DRUG_PRESETS,
  FREQUENCY_METADATA,
  DURATION_METADATA,
} from "../src/calculators.js";

describe("Pediatric Dose Calculator (calculateWeightBasedDose)", () => {
  it("calculates standard Paracetamol dose for a 12 kg child", () => {
    const result = calculateWeightBasedDose({
      weightKg: 12,
      mgPerKg: 15,
      maxMgPerDose: 1000,
      frequency: "Q6H",
      concentrationMgPerMl: 24, // 120 mg / 5 mL
    });

    expect(result.weightKg).toBe(12);
    expect(result.rawDoseMg).toBe(180);
    expect(result.doseMg).toBe(180);
    expect(result.isCappedSingleDose).toBe(false);
    expect(result.volumeMl).toBe(7.5); // 180 / 24 = 7.5 mL
    expect(result.dosesPerDay).toBe(4);
    expect(result.dailyTotalMg).toBe(720); // 180 * 4 = 720 mg
    expect(result.minimumIntervalHours).toBe(6);
    expect(result.steps.length).toBeGreaterThanOrEqual(4);
  });

  it("enforces single dose cap on an 80 kg patient", () => {
    const result = calculateWeightBasedDose({
      weightKg: 80,
      mgPerKg: 15,
      maxMgPerDose: 1000,
      frequency: "Q6H",
    });

    expect(result.rawDoseMg).toBe(1200); // 80 * 15 = 1200
    expect(result.doseMg).toBe(1000); // Capped at 1000
    expect(result.isCappedSingleDose).toBe(true);
    expect(result.dailyTotalMg).toBe(4000); // 1000 * 4 = 4000
    expect(result.steps.some((s) => s.includes("capped at maximum allowable limit"))).toBe(true);
  });

  it("detects 24-hour cumulative overdose when high frequency exceeds max daily cap", () => {
    // 30 kg child taking Paracetamol Q4H (6 doses/day) @ 15 mg/kg = 450 mg/dose
    // 450 * 6 = 2700 mg/day. Max daily cap = 60 mg/kg/day * 30 kg = 1800 mg/day.
    const result = calculateWeightBasedDose({
      weightKg: 30,
      mgPerKg: 15,
      maxMgPerDose: 1000,
      maxMgPerDay: 4000,
      maxMgPerKgPerDay: 60,
      frequency: "Q4H",
    });

    expect(result.doseMg).toBe(450);
    expect(result.dailyTotalMg).toBe(2700);
    expect(result.isCappedDailyTotal).toBe(true);
    expect(result.warning).toContain("exceeds maximum daily ceiling");
  });

  it("calculates Amoxicillin standard vs high-dose AOM accurately", () => {
    // Standard: 10 kg child @ 13.33 mg/kg Q8H
    const standard = calculateWeightBasedDose({
      weightKg: 10,
      mgPerKg: 13.33,
      maxMgPerDose: 500,
      frequency: "Q8H",
      concentrationMgPerMl: 25, // 125 mg / 5 mL
    });
    expect(standard.rawDoseMg).toBe(133.3);
    expect(standard.doseMg).toBe(133.3);
    expect(standard.volumeMl).toBe(5.33);
    expect(standard.dailyTotalMg).toBe(399.9);

    // High-Dose AOM: 10 kg child @ 45 mg/kg Q12H
    const aom = calculateWeightBasedDose({
      weightKg: 10,
      mgPerKg: 45,
      maxMgPerDose: 1000,
      frequency: "Q12H",
      concentrationMgPerMl: 50, // 250 mg / 5 mL
    });
    expect(aom.rawDoseMg).toBe(450);
    expect(aom.doseMg).toBe(450);
    expect(aom.volumeMl).toBe(9);
    expect(aom.dailyTotalMg).toBe(900);
  });

  it("calculates fixed dose protocol (e.g. Zinc Sulfate)", () => {
    const result = calculateWeightBasedDose({
      weightKg: 8,
      mgPerKg: 0,
      maxMgPerDose: 20,
      frequency: "Q24H",
      concentrationMgPerMl: 4, // 20 mg / 5 mL
    });

    expect(result.rawDoseMg).toBe(20);
    expect(result.doseMg).toBe(20);
    expect(result.volumeMl).toBe(5);
    expect(result.dailyTotalMg).toBe(20);
    expect(result.steps.some((s) => s.includes("Fixed dose protocol"))).toBe(true);
  });

  it("accepts exact boundary weights (1.0 kg and 100.0 kg)", () => {
    const minResult = calculateWeightBasedDose({
      weightKg: 1.0,
      mgPerKg: 15,
      maxMgPerDose: 1000,
    });
    expect(minResult.weightKg).toBe(1.0);
    expect(minResult.rawDoseMg).toBe(15);
    expect(minResult.doseMg).toBe(15);

    const maxResult = calculateWeightBasedDose({
      weightKg: 100.0,
      mgPerKg: 15,
      maxMgPerDose: 1000,
    });
    expect(maxResult.weightKg).toBe(100.0);
    expect(maxResult.rawDoseMg).toBe(1500);
    expect(maxResult.doseMg).toBe(1000); // Capped at 1000 mg
    expect(maxResult.isCappedSingleDose).toBe(true);
  });

  it("strictly refuses off-boundary weights (0.99 kg and 100.01 kg)", () => {
    expect(() =>
      calculateWeightBasedDose({
        weightKg: 0.99,
        mgPerKg: 15,
        maxMgPerDose: 1000,
      })
    ).toThrow(/Specialist neonatal care required/);

    expect(() =>
      calculateWeightBasedDose({
        weightKg: 100.01,
        mgPerKg: 15,
        maxMgPerDose: 1000,
      })
    ).toThrow(/exceeds paediatric parameters/);
  });

  it("caps High-Dose Amoxicillin when a 30 kg child exceeds max single dose limit", () => {
    // 30 kg * 45 mg/kg = 1350 mg -> capped at 1000 mg/dose
    const result = calculateWeightBasedDose({
      weightKg: 30,
      mgPerKg: 45,
      maxMgPerDose: 1000,
      frequency: "Q12H",
    });
    expect(result.rawDoseMg).toBe(1350);
    expect(result.doseMg).toBe(1000);
    expect(result.isCappedSingleDose).toBe(true);
  });

  it("enforces per-drug minWeightKg and minAgeMonths thresholds", () => {
    // Paracetamol: minWeightKg = 2.5
    expect(() =>
      calculateWeightBasedDose({
        weightKg: 2.0,
        mgPerKg: 15,
        maxMgPerDose: 1000,
        minWeightKg: 2.5,
        drugName: "Paracetamol",
      })
    ).toThrow(/below the minimum threshold \(2.5 kg\) for Paracetamol/);

    // Azithromycin: minAgeMonths = 6
    expect(() =>
      calculateWeightBasedDose({
        weightKg: 6.0,
        mgPerKg: 10,
        maxMgPerDose: 500,
        minAgeMonths: 6,
        ageMonths: 4,
        drugName: "Azithromycin",
      })
    ).toThrow(/below the minimum threshold \(6 months\) for Azithromycin/);

    // Allowed when satisfying thresholds
    const valid = calculateWeightBasedDose({
      weightKg: 6.0,
      mgPerKg: 10,
      maxMgPerDose: 500,
      minWeightKg: 5.0,
      minAgeMonths: 6,
      ageMonths: 8,
      drugName: "Azithromycin",
    });
    expect(valid.doseMg).toBe(60);
  });

  it("attaches low weight cautionary warning for neonates under 3 kg", () => {
    const result = calculateWeightBasedDose({
      weightKg: 2.8,
      mgPerKg: 15,
      maxMgPerDose: 1000,
    });
    expect(result.warning).toContain("Low birth weight / neonate");
  });
});

describe("WHO Diarrhoea & ORS Protocol (calculateOrsVolume)", () => {
  it("calculates Plan A ongoing loss replacement correctly with rateMlPerHour = null", () => {
    const result = calculateOrsVolume({ weightKg: 12, plan: "PLAN_A" });
    expect(result.plan).toBe("PLAN_A");
    expect(result.totalVolumeMl).toBe(120); // 12 * 10 = 120 mL per stool
    expect(result.rateMlPerHour).toBeNull(); // Plan A is per-loose-stool, not a continuous hourly rate
    expect(result.reassessmentMinutes).toBe(240);
    expect(result.guidance).toContain("Zinc");
  });

  it("calculates Plan B 4-hour rehydration volume and hourly rates", () => {
    const result = calculateOrsVolume({ weightKg: 8, plan: "PLAN_B" });
    expect(result.plan).toBe("PLAN_B");
    expect(result.totalVolumeMl).toBe(600); // 8 * 75 = 600 mL
    expect(result.durationHours).toBe(4);
    expect(result.rateMlPerHour).toBe(150); // 600 / 4 = 150 mL/hr
    expect(result.reassessmentMinutes).toBe(240);
  });

  it("calculates Plan C IV resuscitation split for infants < 12 months", () => {
    const result = calculateOrsVolume({ weightKg: 8, plan: "PLAN_C", ageMonths: 6 });
    expect(result.plan).toBe("PLAN_C");
    expect(result.totalVolumeMl).toBe(800); // 8 * 100 = 800 mL
    expect(result.durationHours).toBe(6);
    expect(result.steps.some((s) => s.includes("Rapid Bolus 30 mL/kg = 240 mL over 1 hour"))).toBe(true);
    expect(result.steps.some((s) => s.includes("Remainder 70 mL/kg = 560 mL over 5 hours"))).toBe(true);
  });

  it("calculates Plan C IV resuscitation split for older children ≥ 12 months", () => {
    const result = calculateOrsVolume({ weightKg: 15, plan: "PLAN_C", ageMonths: 24 });
    expect(result.totalVolumeMl).toBe(1500); // 15 * 100 = 1500 mL
    expect(result.durationHours).toBe(3);
    expect(result.steps.some((s) => s.includes("Rapid Bolus 30 mL/kg = 450 mL over 30 minutes"))).toBe(true);
    expect(result.steps.some((s) => s.includes("Remainder 70 mL/kg = 1050 mL over 2.5 hours"))).toBe(true);
  });

  it("includes clinical notice when Plan C age is undefined and defaults to weight heuristic", () => {
    const result = calculateOrsVolume({ weightKg: 8, plan: "PLAN_C" });
    expect(result.steps.some((s) => s.includes("Patient age was not provided; protocol schedule was selected based on weight heuristic"))).toBe(true);
  });
});

describe("IV Drip Rate Calculator (calculateIvDripRate)", () => {
  it("calculates standard macrodrip rate for 500 mL over 4 hours (20 gtt/mL)", () => {
    const result = calculateIvDripRate({
      volumeMl: 500,
      durationHours: 4,
      dropFactor: 20,
    });

    expect(result.durationMinutes).toBe(240);
    expect(result.infusionRateMlPerHour).toBe(125); // 500 / 4 = 125 mL/hr
    expect(result.dripRateGttPerMin).toBe(42); // (500 * 20) / 240 = 41.67 -> 42 gtt/min
  });

  it("calculates microdrip rate for 100 mL over 1 hour (60 gtt/mL)", () => {
    const result = calculateIvDripRate({
      volumeMl: 100,
      durationHours: 1,
      dropFactor: 60,
    });

    expect(result.durationMinutes).toBe(60);
    expect(result.infusionRateMlPerHour).toBe(100);
    expect(result.dripRateGttPerMin).toBe(100); // (100 * 60) / 60 = 100 gtt/min (1 mL/hr = 1 gtt/min in microdrip)
  });

  it("rejects invalid volumes, zero durations, and invalid drop factors", () => {
    expect(() =>
      calculateIvDripRate({
        volumeMl: 0,
        durationHours: 1,
        dropFactor: 20,
      })
    ).toThrow();

    expect(() =>
      calculateIvDripRate({
        volumeMl: 500,
        durationMinutes: 0,
        dropFactor: 20,
      })
    ).toThrow();
  });
});

describe("Holliday-Segar Maintenance Fluid (calculateMaintenanceFluid)", () => {
  it("calculates fluid for a 7 kg infant (first tier only)", () => {
    const result = calculateMaintenanceFluid(7);
    expect(result.totalDailyVolumeMl).toBe(700); // 7 * 100 = 700 mL/day
    expect(result.hourlyRateMlPerHour).toBe(28); // 7 * 4 = 28 mL/hr
    expect(result.breakdown).toHaveLength(1);
    expect(result.isAdultAdvisory).toBe(false);
  });

  it("calculates fluid for a 15 kg child (first + second tier)", () => {
    const result = calculateMaintenanceFluid(15);
    // Tier 1: 10 * 100 = 1000 mL/day (40 mL/hr)
    // Tier 2: 5 * 50 = 250 mL/day (10 mL/hr)
    // Total = 1250 mL/day (50 mL/hr)
    expect(result.totalDailyVolumeMl).toBe(1250);
    expect(result.hourlyRateMlPerHour).toBe(50);
    expect(result.breakdown).toHaveLength(2);
    expect(result.isAdultAdvisory).toBe(false);
  });

  it("calculates fluid for a 25 kg child (all three tiers)", () => {
    const result = calculateMaintenanceFluid(25);
    // Tier 1: 10 * 100 = 1000 mL/day (40 mL/hr)
    // Tier 2: 10 * 50 = 500 mL/day (20 mL/hr)
    // Tier 3: 5 * 20 = 100 mL/day (5 mL/hr)
    // Total = 1600 mL/day (65 mL/hr -> calculated 65 from 40+20+5)
    expect(result.totalDailyVolumeMl).toBe(1600);
    expect(result.hourlyRateMlPerHour).toBe(65);
    expect(result.breakdown).toHaveLength(3);
    expect(result.isAdultAdvisory).toBe(false);
  });

  it("attaches adult protocol advisory for patients > 50 kg or > 14 years", () => {
    const result = calculateMaintenanceFluid(60, 16);
    expect(result.isAdultAdvisory).toBe(true);
    expect(result.advisory).toContain("Holliday-Segar is a paediatric rule");
  });
});

describe("Metadata and Presets Registries", () => {
  it("includes all essential paediatric drug presets with citations", () => {
    expect(PEDIATRIC_DRUG_PRESETS.length).toBeGreaterThanOrEqual(8);
    for (const preset of PEDIATRIC_DRUG_PRESETS) {
      expect(preset.id).toBeTruthy();
      expect(preset.drugName).toBeTruthy();
      expect(preset.citation).toBeTruthy();
      expect(preset.maxMgPerDose).toBeGreaterThan(0);
      expect(preset.concentrationOptions.length).toBeGreaterThanOrEqual(1);
    }
  });

  it("defines PRN frequency with minimum 4-hour interval spacing", () => {
    const prn = FREQUENCY_METADATA.PRN;
    expect(prn.code).toBe("PRN");
    expect(prn.minimumIntervalHours).toBe(4);
    expect(prn.dosesPerDay).toBe(4);
  });

  it("covers all standard duration options", () => {
    expect(DURATION_METADATA["14_DAYS"].days).toBe(14);
    expect(DURATION_METADATA["3_DAYS"].days).toBe(3);
  });
});
