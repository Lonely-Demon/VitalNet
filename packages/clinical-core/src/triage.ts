// The orchestrator — the one function the web app and the API both call.
// triage(form, trees) always returns a result; it never throws for
// well-formed input (mirrors classifier.py::predict_triage's contract).
//
// Two modes (see rules.ts / engine.ts headers for the full rationale):
//   - "rules_first" (default, the target end-state): triage_level comes
//     100% from rules/engine.ts. The ML model, when a tree bundle is
//     supplied, is computed and returned as an ADVISORY opinion only —
//     it never changes the tier. Disagreement between the rules tier and
//     the model's opinion is surfaced via `modelAgreed: false` so callers
//     can fold it into needs_review.
//   - "hybrid": reproduces the CURRENT (pre-migration) production
//     semantics — safety-net override -> ML model is authoritative for
//     everything else -> NEWS2 floor. Exists ONLY for the transition
//     conformance check against the live Python backend (see
//     packages/clinical-core/test/conformance) and must not be used by
//     new callers once the migration completes.

import { checkContraindications, type ContraindicationInput } from "./contraindications.js";
import { buildFeatureMap, orderFeatureVector, type FeatureFormInput } from "./features.js";
import { assignTier, type EngineInput, type Tier } from "./rules/engine.js";
import { checkOverrides, news2ConcerningVital, type FiredRule } from "./rules/rules.js";
import { evaluateTrees, explainPrediction, type TreeJson } from "./treeEvaluator.js";

export type TriageMode = "rules_first" | "hybrid";

/** The mode every new caller should use. Flip this one constant (and its
 * one remaining "hybrid" caller, the conformance harness) once the
 * migration's conformance report is signed off — see DECISIONS §33. */
export const DEFAULT_TRIAGE_MODE: TriageMode = "rules_first";

const TRIAGE_LABELS: readonly Tier[] = ["ROUTINE", "URGENT", "EMERGENCY"];

// Abstention thresholds — mirror classifier.py's LOW_CONFIDENCE_PROBA/MARGIN.
const LOW_CONFIDENCE_PROBA = 0.55;
const LOW_CONFIDENCE_MARGIN = 0.15;

export interface TriageFormInput extends EngineInput, FeatureFormInput, ContraindicationInput {}

export interface ModelOpinion {
  tier: Tier;
  confidence: number;
  lowConfidence: boolean;
  /** Ranked (by |contribution|) feature names behind this prediction —
   * replaces the Python backend's SHAP prose with a directly-computed,
   * always-available attribution. */
  topFactors: Array<{ feature: string; contribution: number }>;
}

export interface TriageResult {
  tier: Tier;
  firedRules: FiredRule[];
  contraindicationFlags: string[];
  /** Present only when a tree bundle was supplied. In rules_first mode this
   * is advisory and never influenced `tier`. */
  model?: ModelOpinion;
  /** True when the model's own opinion matches the authoritative tier.
   * Undefined if no model was run. Feeds needs_review + the ML-agreement
   * analytics (the model-promotion gate, DECISIONS §33). */
  modelAgreed?: boolean;
  mode: TriageMode;
}

function runModel(form: TriageFormInput, trees: TreeJson, featureNames: readonly string[]): ModelOpinion {
  const featureMap = buildFeatureMap(form);
  const vector = orderFeatureVector(featureMap, featureNames);
  const { classIndex, probabilities } = evaluateTrees(trees, vector);
  const tier = TRIAGE_LABELS[classIndex] ?? "ROUTINE";
  const confidence = probabilities[classIndex] ?? 0;
  const sorted = [...probabilities].sort((a, b) => b - a);
  const margin = sorted.length > 1 ? sorted[0]! - sorted[1]! : 1;
  const lowConfidence = confidence < LOW_CONFIDENCE_PROBA || margin < LOW_CONFIDENCE_MARGIN;

  const attributions = explainPrediction(trees, vector, classIndex).slice(0, 5);
  const topFactors = attributions.map((a) => ({
    feature: featureNames[a.featureIndex] ?? `feature_${a.featureIndex}`,
    contribution: a.contribution,
  }));

  return { tier, confidence, lowConfidence, topFactors };
}

export interface TriageOptions {
  mode?: TriageMode;
  /** Tree bundle + canonical feature order, e.g. fetched from
   * /models/triage_trees.json + /models/features_config.json. Omit to skip
   * the advisory model entirely (rules-only triage — always safe). */
  trees?: TreeJson;
  featureNames?: readonly string[];
}

export function triage(form: TriageFormInput, options: TriageOptions = {}): TriageResult {
  const mode = options.mode ?? DEFAULT_TRIAGE_MODE;
  const contraindicationFlags = checkContraindications(form);
  const canRunModel = options.trees && options.featureNames?.length;

  if (mode === "hybrid") {
    // Reproduces classifier.py::predict_triage's CURRENT production order —
    // transition-only, see module header.
    const override = checkOverrides(form);
    if (override) {
      return { tier: "EMERGENCY", firedRules: [override], contraindicationFlags, mode };
    }
    if (!canRunModel) {
      throw new Error("hybrid mode requires a tree bundle — the model is authoritative for the non-override band");
    }
    const model = runModel(form, options.trees!, options.featureNames!);
    let tier = model.tier;
    const firedRules: FiredRule[] = [];
    if (tier === "ROUTINE") {
      const floor = news2ConcerningVital(form);
      if (floor) {
        tier = "URGENT";
        firedRules.push(floor);
      }
    }
    return { tier, firedRules, contraindicationFlags, model, modelAgreed: model.tier === tier, mode };
  }

  // rules_first (default): the rules engine is the ENTIRE authoritative
  // decision. The model, if available, is computed purely as an advisory
  // opinion and never influences `tier`.
  const engineResult = assignTier(form);
  const model = canRunModel ? runModel(form, options.trees!, options.featureNames!) : undefined;

  return {
    tier: engineResult.tier,
    firedRules: engineResult.firedRules,
    contraindicationFlags,
    ...(model ? { model, modelAgreed: model.tier === engineResult.tier } : {}),
    mode,
  };
}
