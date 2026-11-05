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
  /** Optional v3.2+ ternary routing flag per node: 1 or true = go left on missing/NaN/-1, 0 or false = go right. */
  defaultLeft?: (number | boolean)[];
  /** Optional v3.2+ per-node expected class values [nodeId][classIdx] for exact Saabas deltas. */
  nodeVal?: number[][];
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
  hasNaN: boolean;
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
  let hasNaN = false;

  for (const tree of treeJson.trees) {
    const { feat, thr, left, right, leaf, defaultLeft } = tree;
    let node = 0;
    while (feat[node] !== -1 && feat[node] !== undefined) {
      const f = feat[node]!;
      const rawVal = x[f]!;
      const isMissing = Number.isNaN(rawVal) || rawVal === null || rawVal === undefined || rawVal === -1;
      if (Number.isNaN(rawVal)) {
        hasNaN = true;
      }
      if (isMissing && defaultLeft && defaultLeft[node] !== undefined) {
        node = (defaultLeft[node] === 1 || defaultLeft[node] === true) ? left[node]! : right[node]!;
        continue;
      }
      node = Math.fround(rawVal) <= Math.fround(thr[node]!) ? left[node]! : right[node]!;
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
  return { classIndex, probabilities, hasNaN };
}

export interface NodeEvaluationResult {
  isLeaf: boolean;
  leafVal?: Array<[number, number]> | null;
  nextNode?: number;
  splitFeature?: number;
  defaultLeftUsed?: boolean;
}

/**
 * Evaluates a single tree node using ternary missing routing (defaultLeft).
 * If raw feature value is null, undefined, or NaN, routes via defaultLeft.
 * If measured, uses standard float32 comparison against threshold.
 */
export function evaluateNodeTernary(
  tree: TreeNode,
  nodeId: number,
  featureVector: readonly number[]
): NodeEvaluationResult {
  const featIdx = tree.feat[nodeId];
  if (featIdx === -1 || featIdx === undefined) {
    return { isLeaf: true, leafVal: tree.leaf[nodeId] };
  }
  const rawVal = featureVector[featIdx];
  const thr = tree.thr[nodeId]!;
  const defaultLeftVal = tree.defaultLeft ? tree.defaultLeft[nodeId] : undefined;
  const isMissing = rawVal === null || rawVal === undefined || Number.isNaN(rawVal) || rawVal === -1;

  let nextNode: number;
  let defaultLeftUsed = false;
  if (isMissing && defaultLeftVal !== undefined) {
    defaultLeftUsed = true;
    nextNode = (defaultLeftVal === 1 || defaultLeftVal === true) ? tree.left[nodeId]! : tree.right[nodeId]!;
  } else {
    const fVal = Math.fround(rawVal as number);
    const fThr = Math.fround(thr);
    nextNode = fVal <= fThr ? tree.left[nodeId]! : tree.right[nodeId]!;
  }
  return { isLeaf: false, nextNode, splitFeature: featIdx, defaultLeftUsed };
}

/**
 * Traverses a tree to a leaf using ternary routing, recording the path of node IDs.
 */
export function traverseTreeTernary(tree: TreeNode, featureVector: readonly number[]) {
  let curr = 0;
  const path = [curr];
  while (tree.feat[curr] !== -1 && tree.feat[curr] !== undefined) {
    const step = evaluateNodeTernary(tree, curr, featureVector);
    if (step.isLeaf || step.nextNode === undefined) break;
    curr = step.nextNode;
    path.push(curr);
  }
  return { leafIndex: curr, leafValue: tree.leaf[curr], path };
}

/**
 * Computes exact Saabas Node-Expectation Delta Attribution across a tree:
 * Δ_u(c) = nodeVal[child][c] - nodeVal[node][c]
 * Features in unmeasuredFeatureSet are suppressed (attribution = 0).
 */
export function computeSaabasAttributions(
  tree: TreeNode,
  featureVector: readonly number[],
  featureNames: readonly string[],
  unmeasuredFeatureSet: ReadonlySet<string> = new Set()
): Record<string, number[]> {
  const traversal = traverseTreeTernary(tree, featureVector);
  const path = traversal.path;
  const nClasses = tree.nodeVal ? tree.nodeVal[0]?.length ?? 3 : 3;

  const attributions: Record<string, number[]> = {};
  for (const name of featureNames) {
    attributions[name] = new Array(nClasses).fill(0);
  }
  if (!tree.nodeVal) return attributions;

  for (let i = 0; i < path.length - 1; i++) {
    const u = path[i]!;
    const v = path[i + 1]!;
    const featIdx = tree.feat[u]!;
    if (featIdx < 0 || featIdx >= featureNames.length) continue;

    const featName = featureNames[featIdx]!;
    if (unmeasuredFeatureSet.has(featName)) continue;

    const attrArr = attributions[featName];
    if (!attrArr) continue;
    for (let c = 0; c < nClasses; c++) {
      const delta = (tree.nodeVal[v]?.[c] ?? 0) - (tree.nodeVal[u]?.[c] ?? 0);
      attrArr[c] = (attrArr[c] ?? 0) + delta;
    }
  }
  return attributions;
}

export interface FeatureAttribution {
  featureIndex: number;
  /** Signed contribution to the predicted class's score. */
  contribution: number;
}

export interface ExplainOptions {
  /** Indices of features that were unmeasured (imputed as -1 or textbook default). */
  unmeasuredIndices?: ReadonlySet<number>;
}

/**
 * Saabas-style per-feature attribution for the predicted class.
 * When nodeVal is present, computes exact node-to-node expectation deltas.
 * When nodeVal is absent (v3.1.0 JSON), falls back to path-length division
 * while strictly suppressing unmeasured features when options.unmeasuredIndices is provided.
 */
export function explainPrediction(
  treeJson: TreeJson,
  x: readonly number[],
  classIndex: number,
  options?: ExplainOptions
): FeatureAttribution[] {
  const contributionByFeature = new Map<number, number>();
  const unmeasured = options?.unmeasuredIndices;

  for (const tree of treeJson.trees) {
    const { feat, thr, left, right, leaf, defaultLeft, nodeVal } = tree;
    const pathFeatures: number[] = [];
    let node = 0;

    while (feat[node] !== -1 && feat[node] !== undefined) {
      const f = feat[node]!;
      const rawVal = x[f]!;
      let nextNode: number;
      const isMissing = Number.isNaN(rawVal) || rawVal === null || rawVal === undefined || rawVal === -1;
      if (isMissing && defaultLeft && defaultLeft[node] !== undefined) {
        nextNode = (defaultLeft[node] === 1 || defaultLeft[node] === true) ? left[node]! : right[node]!;
      } else {
        nextNode = Math.fround(rawVal) <= Math.fround(thr[node]!) ? left[node]! : right[node]!;
      }

      if (nodeVal && nodeVal[node] && nodeVal[nextNode]) {
        const delta = (nodeVal[nextNode]![classIndex] ?? 0) - (nodeVal[node]![classIndex] ?? 0);
        if (!unmeasured || !unmeasured.has(f)) {
          contributionByFeature.set(f, (contributionByFeature.get(f) ?? 0) + delta);
        }
      } else {
        pathFeatures.push(f);
      }
      node = nextNode;
    }

    if (!nodeVal) {
      const contribs = leaf[node];
      const leafWeight = contribs?.find(([cls]) => cls === classIndex)?.[1] ?? 0;
      const measuredPath = unmeasured
        ? pathFeatures.filter((f) => !unmeasured.has(f))
        : pathFeatures;
      if (measuredPath.length > 0 && leafWeight !== 0) {
        const share = leafWeight / measuredPath.length;
        for (const f of measuredPath) {
          contributionByFeature.set(f, (contributionByFeature.get(f) ?? 0) + share);
        }
      }
    }
  }

  return [...contributionByFeature.entries()]
    .map(([featureIndex, contribution]) => ({ featureIndex, contribution }))
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
}

export type FeatureCompletenessStatus = "COMPLETE" | "PARTIAL_VITALS" | "SPARSE_CONTEXT";
export type CompletenessState = FeatureCompletenessStatus;

export interface FeatureCompletenessResult {
  status: FeatureCompletenessStatus;
  state: FeatureCompletenessStatus;
  missingCriticalVitals: string[];
  missingVitals: string[];
  lowConfidence: boolean;
}

export const CORE_VITALS = [
  "bp_systolic",
  "bp_diastolic",
  "heart_rate",
  "spo2",
  "temperature",
] as const;

/**
 * Assesses completeness of vital measurements on an intake form.
 * - COMPLETE: All 5 core vitals measured.
 * - PARTIAL_VITALS: 1–2 missing vitals, or >=3 missing vitals with at least 1 symptom.
 * - SPARSE_CONTEXT: >=3 missing vitals AND zero symptoms (forces lowConfidence = true).
 */
export function assessFeatureCompleteness(formData: {
  bp_systolic?: number | null;
  bp_diastolic?: number | null;
  heart_rate?: number | null;
  spo2?: number | null;
  temperature?: number | null;
  symptoms?: readonly string[] | null;
}): FeatureCompletenessResult {
  const missingVitals: string[] = [];
  for (const v of CORE_VITALS) {
    const val = formData[v];
    if (val === null || val === undefined || val <= 0) {
      missingVitals.push(v);
    }
  }

  const symptoms = Array.isArray(formData.symptoms) ? formData.symptoms : [];
  const missingCount = missingVitals.length;

  let status: FeatureCompletenessStatus;
  if (missingCount === 0) {
    status = "COMPLETE";
  } else if (missingCount <= 2 || symptoms.length >= 1) {
    status = "PARTIAL_VITALS";
  } else {
    status = "SPARSE_CONTEXT";
  }

  return {
    status,
    state: status,
    missingCriticalVitals: missingVitals,
    missingVitals,
    lowConfidence: status === "SPARSE_CONTEXT",
  };
}

export const assessCompleteness = assessFeatureCompleteness;
