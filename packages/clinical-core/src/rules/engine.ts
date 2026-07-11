// The rules-first tier-assignment engine — the PRIMARY, authoritative
// source of triage_level. Promotes what was previously a training-label-
// only scorer (backend/scripts/train_classifier.py::assign_triage_label,
// v3.1.0 age-aware) to inference time, and merges it with the always-wins
// override layer (rules.ts, ported from classifier.py::_safety_net_check).
//
// Design (see DECISIONS §33 for the full rationale):
//   1. Override rules (rules.ts::checkOverrides) — unconditional EMERGENCY.
//      Always checked first; if any fires, nothing below runs.
//   2. Aggregate NEWS2/qSOFA/PALS scorer — the nuanced, age-aware tier
//      assignment for everything the overrides don't catch.
//   3. NEWS2 floor (rules.ts::news2ConcerningVital) — a redundant backstop
//      ensuring a concerning single vital is never left ROUTINE (in
//      practice already covered by the aggregate>=2 threshold below, kept
//      as an independently-citable, testable invariant).
//
// The ML model (treeEvaluator.ts) plays NO role in this function — it is
// advisory-only, computed separately by triage.ts and never influences the
// tier this engine returns.

import type { Symptom } from "../schema.js";
import { news2LikeScore, qsofaScore } from "./bands.js";
import { checkOverrides, news2ConcerningVital, type FiredRule, type OverrideInput } from "./rules.js";

export type Tier = "ROUTINE" | "URGENT" | "EMERGENCY";
const TIER_RANK: Record<Tier, number> = { ROUTINE: 0, URGENT: 1, EMERGENCY: 2 };

export interface EngineInput extends OverrideInput {}

export interface EngineResult {
  tier: Tier;
  firedRules: FiredRule[];
  /** Diagnostic detail — the raw aggregate/qSOFA numbers behind the
   * decision, useful for the doctor briefing and for the advisory-model
   * agreement analytics. */
  aggregate: number;
  worstSingle: number;
  qsofa: number;
}

const CONCERNING_SYMPTOMS = new Set<Symptom>([
  "chest_pain",
  "breathlessness",
  "high_fever",
  "severe_abdominal_pain",
  "persistent_vomiting",
  "severe_headache",
  "weakness_one_side",
  "difficulty_speaking",
]);

const STROKE_SIGNS = new Set<Symptom>(["weakness_one_side", "difficulty_speaking"]);
const HYPERTENSIVE_NEURO = new Set<Symptom>([
  "severe_headache",
  "weakness_one_side",
  "difficulty_speaking",
  "altered_consciousness",
]);

function bumpTo(current: Tier, candidate: Tier): Tier {
  return TIER_RANK[candidate] > TIER_RANK[current] ? candidate : current;
}

/**
 * The single authoritative triage decision. Never throws for well-formed
 * input; always returns a tier and the citable rules that produced it.
 */
export function assignTier(form: EngineInput): EngineResult {
  const override = checkOverrides(form);
  if (override) {
    return { tier: "EMERGENCY", firedRules: [override], aggregate: 0, worstSingle: 0, qsofa: 0 };
  }

  const symptoms = new Set(form.symptoms);
  const { patient_age: age, bp_systolic: bpSys, heart_rate: hr, spo2, temperature: temp } = form;

  const { aggregate, worstSingle } = news2LikeScore(age, bpSys, hr, spo2, temp);
  const qsofa = qsofaScore(bpSys, symptoms.has("altered_consciousness"), age);

  const concerningSymptomCount = [...symptoms].filter((s) => CONCERNING_SYMPTOMS.has(s as Symptom)).length;
  const cardiopulmonaryCombo = symptoms.has("chest_pain") && symptoms.has("breathlessness");
  const strokeSigns = [...symptoms].some((s) => STROKE_SIGNS.has(s as Symptom));
  // Redundant with rules.ts::checkOverrides's identical check — kept for 1:1
  // parity with the ported assign_triage_label and as an independent audit
  // trail entry (this branch can only be reached if checkOverrides somehow
  // didn't fire for the same condition, which should never happen; a vitest
  // case asserts this invariant).
  const hypertensiveNeuroEmergency =
    bpSys !== null && bpSys >= 180 && [...symptoms].some((s) => HYPERTENSIVE_NEURO.has(s as Symptom));

  let tier: Tier = "ROUTINE";
  const firedRules: FiredRule[] = [];

  if (aggregate >= 7) {
    tier = bumpTo(tier, "EMERGENCY");
    firedRules.push({ id: "aggregate_score_7plus", citation: "NEWS2 aggregate >=7 = high clinical risk", detail: `aggregate vital-derangement score ${aggregate}` });
  }
  if (worstSingle >= 3) {
    tier = bumpTo(tier, "EMERGENCY");
    firedRules.push({ id: "worst_single_3", citation: "NEWS2 'any red parameter' — a single severely deranged vital", detail: `worst single-parameter score ${worstSingle}` });
  }
  if (qsofa >= 2) {
    tier = bumpTo(tier, "EMERGENCY");
    firedRules.push({ id: "qsofa_2plus", citation: "qSOFA >=2 (Sepsis-3, Singer et al. 2016) — high risk of sepsis mortality", detail: `qSOFA score ${qsofa}` });
  }
  if (cardiopulmonaryCombo) {
    tier = bumpTo(tier, "EMERGENCY");
    firedRules.push({ id: "cardiopulmonary_combo", citation: "Chest pain + breathlessness together — possible ACS/PE regardless of vitals", detail: "chest pain and breathlessness both present" });
  }
  if (age > 70 && strokeSigns) {
    tier = bumpTo(tier, "EMERGENCY");
    firedRules.push({ id: "elderly_stroke_signs", citation: "Focal neurological signs in an elderly patient — high pretest probability of stroke", detail: "weakness on one side or difficulty speaking, age >70" });
  }
  if (hypertensiveNeuroEmergency) {
    tier = bumpTo(tier, "EMERGENCY");
    firedRules.push({ id: "hypertensive_neuro_emergency_aggregate", citation: "Hypertensive crisis (SBP >=180) + neurological symptom", detail: "possible hypertensive encephalopathy/stroke" });
  }

  if (tier !== "EMERGENCY") {
    if (aggregate >= 4) {
      tier = bumpTo(tier, "URGENT");
      firedRules.push({ id: "aggregate_score_4plus", citation: "NEWS2 aggregate >=4 = medium clinical risk", detail: `aggregate vital-derangement score ${aggregate}` });
    }
    if (worstSingle >= 2) {
      tier = bumpTo(tier, "URGENT");
      firedRules.push({ id: "worst_single_2", citation: "NEWS2 single-parameter score of 2 — concerning but not extreme", detail: `worst single-parameter score ${worstSingle}` });
    }
    if (qsofa >= 1) {
      tier = bumpTo(tier, "URGENT");
      firedRules.push({ id: "qsofa_1", citation: "qSOFA >=1 — one sepsis risk criterion present", detail: `qSOFA score ${qsofa}` });
    }
    if (concerningSymptomCount >= 2) {
      tier = bumpTo(tier, "URGENT");
      firedRules.push({ id: "concerning_symptoms_2plus", citation: "Two or more concerning symptoms together", detail: `${concerningSymptomCount} concerning symptoms present` });
    }
    if (strokeSigns) {
      tier = bumpTo(tier, "URGENT");
      firedRules.push({ id: "stroke_signs", citation: "Focal neurological signs warrant urgent assessment regardless of age", detail: "weakness on one side or difficulty speaking" });
    }
    if (concerningSymptomCount >= 1) {
      tier = bumpTo(tier, "URGENT");
      firedRules.push({ id: "concerning_symptom_plus_mild_derangement", citation: "A concerning symptom with any vital derangement", detail: `${concerningSymptomCount} concerning symptom(s), aggregate score ${aggregate}` });
    } else if (aggregate >= 2) {
      tier = bumpTo(tier, "URGENT");
      firedRules.push({ id: "mild_aggregate_derangement", citation: "NEWS2 aggregate >=2 — mild but real vital derangement", detail: `aggregate vital-derangement score ${aggregate}` });
    }
  }

  // Layer 3 — NEWS2 floor: never leave a concerning single vital as ROUTINE.
  // In practice already implied by aggregate>=2 above; kept as an
  // independent, explicitly-citable backstop (floors only ever raise).
  if (tier === "ROUTINE") {
    const floor = news2ConcerningVital(form);
    if (floor) {
      tier = "URGENT";
      firedRules.push(floor);
    }
  }

  return { tier, firedRules, aggregate, worstSingle, qsofa };
}
