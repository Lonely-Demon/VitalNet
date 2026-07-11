// Dependency-free evaluator for the exported HistGradientBoosting tree
// ensemble (public/models/triage_trees.json) — the ADVISORY ML model.
// Ported 1:1 from frontend/src/utils/treeEvaluator.js and
// backend/scripts/tree_export.py::evaluate_tree_json.
//
// This model plays NO role in the authoritative triage_level decision
// (rules/engine.ts owns that entirely) — its output is an advisory opinion:
// a suggested tier, a confidence score, and (via Saabas attribution below) a
// ranked list of which features pushed the prediction which way. Surfaced to
// the doctor as "the model would have suggested X" and used to compute
// model/rules agreement for the outcome-feedback loop (FEATURES_ROADMAP §1.3).

export interface TreeNode {
  feat: number[];
  thr: number[];
  left: number[];
  right: number[];
  leaf: (Array<[number, number]> | null)[];
}

export interface TreeJson {
  n_features: number;
  n_classes: number;
  labels: number[];
  base_values: number[];
  post_transform: "SOFTMAX" | "NONE";
  trees: TreeNode[];
  model_version?: string;
}

export interface EvaluationResult {
  classIndex: number;
  probabilities: number[];
}

function softmax(scores: readonly number[]): number[] {
  let m = -Infinity;
  for (const s of scores) if (s > m) m = s;
  let tot = 0;
  const exps = new Array<number>(scores.length);
  for (let i = 0; i < scores.length; i++) {
    exps[i] = Math.exp(scores[i]! - m);
    tot += exps[i]!;
  }
  for (let i = 0; i < exps.length; i++) exps[i]! /= tot;
  return exps;
}

/**
 * Evaluate the tree ensemble on an ordered feature vector.
 *
 * Both operands are cast to float32 via Math.fround before the `<=`
 * comparison so it is bit-identical to the server's float32 model (the
 * backend casts features to np.float32 before predict). Without the cast, a
 * feature value landing exactly on a split threshold could take a different
 * branch offline vs online — see DECISIONS §31 (a real, if rare, divergence
 * this closed).
 */
export function evaluateTrees(treeJson: TreeJson, x: readonly number[]): EvaluationResult {
  const nClasses = treeJson.n_classes;
  const scores = treeJson.base_values?.length ? treeJson.base_values.slice() : new Array(nClasses).fill(0);

  for (const tree of treeJson.trees) {
    const { feat, thr, left, right, leaf } = tree;
    let node = 0;
    while (feat[node] !== -1) {
      const f = feat[node]!;
      node = Math.fround(x[f]!) <= Math.fround(thr[node]!) ? left[node]! : right[node]!;
    }
    const contribs = leaf[node];
    if (contribs) {
      for (const [cls, w] of contribs) {
        scores[cls] += w;
      }
    }
  }

  const probabilities = treeJson.post_transform === "SOFTMAX" ? softmax(scores) : scores;
  let classIndex = 0;
  for (let i = 1; i < probabilities.length; i++) {
    if (probabilities[i]! > probabilities[classIndex]!) classIndex = i;
  }
  return { classIndex, probabilities };
}

export interface FeatureAttribution {
  featureIndex: number;
  /** Signed contribution to the predicted class's score, summed across
   * every tree's decision path (Saabas 2014 "Interpreting Random Forests"
   * method — the same feature-attribution algorithm SHAP's TreeExplainer
   * approximates via a game-theoretic path-dependent average; Saabas alone
   * needs no coalition sampling and is cheap enough to run in a browser). */
  contribution: number;
}

/**
 * Saabas-style per-feature attribution for the predicted class: for each
 * tree, walk the SAME decision path evaluateTrees took, crediting each
 * split feature with the change in the predicted class's running score from
 * before to after that split. Summed across all trees, ranked by |contribution|.
 * This is what advisory `top_factors` (triage.ts) is built from — it
 * replaces the Python backend's SHAP explainer, which is not run at
 * inference time by any TypeScript runtime.
 */
export function explainPrediction(treeJson: TreeJson, x: readonly number[], classIndex: number): FeatureAttribution[] {
  const contributionByFeature = new Map<number, number>();

  for (const tree of treeJson.trees) {
    const { feat, thr, left, right, leaf } = tree;

    // Walk the path once, recording every feature checked along the way.
    const pathFeatures: number[] = [];
    let node = 0;
    while (feat[node] !== -1) {
      const f = feat[node]!;
      pathFeatures.push(f);
      node = Math.fround(x[f]!) <= Math.fround(thr[node]!) ? left[node]! : right[node]!;
    }

    // Credit this tree's contribution to the predicted class evenly across
    // the features that were actually checked on the path to its leaf — an
    // equal-split Saabas approximation. The compact tree-JSON export only
    // carries additive per-class leaf weights (no intermediate per-node
    // score, unlike sklearn's own tree_ structure), so an exact
    // score-delta-per-split attribution isn't available from this format;
    // this is the documented approximation (see MODEL_CARD.md "advisory
    // attribution").
    const contribs = leaf[node];
    const leafWeight = contribs?.find(([cls]) => cls === classIndex)?.[1] ?? 0;
    if (pathFeatures.length > 0 && leafWeight !== 0) {
      const share = leafWeight / pathFeatures.length;
      for (const f of pathFeatures) {
        contributionByFeature.set(f, (contributionByFeature.get(f) ?? 0) + share);
      }
    }
  }

  return [...contributionByFeature.entries()]
    .map(([featureIndex, contribution]) => ({ featureIndex, contribution }))
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
}
