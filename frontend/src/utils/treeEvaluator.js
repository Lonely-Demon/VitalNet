// frontend/src/utils/treeEvaluator.js
//
// Dependency-free evaluator for the HistGradientBoosting tree ensemble exported
// by backend/scripts/tree_export.py to /models/triage_trees.json. This replaces
// onnxruntime-web entirely: no ~12 MB WASM runtime, no WASM compile on cold
// start — just JSON walked in plain JS. On the 2 GB-class Android tablets ASHA
// workers use, and over metered rural links, that is the single biggest
// efficiency win in the app.
//
// This is a 1:1 port of `evaluate_tree_json` in scripts/tree_export.py. The two
// MUST stay in lockstep; a golden-vector parity test
// (frontend/tests/treeParity.test.mjs) asserts this JS produces the same class
// as the server model on a held-out sample, so drift fails CI rather than
// silently diverging patients' triage.
//
// Tree JSON shape:
//   { n_features, n_classes, labels:[...], base_values:[...]|[],
//     post_transform:"SOFTMAX"|"NONE",
//     trees:[ { feat:[], thr:[], left:[], right:[], leaf:[ null|[[cls,w],...] ] } ] }
// Node semantics: root is nodeid 0; feat[node] === -1 marks a leaf; internal
// nodes are BRANCH_LEQ — go left (true) if x[feat] <= thr, else right (false).

function softmax(scores) {
  let m = -Infinity
  for (const s of scores) if (s > m) m = s
  let tot = 0
  const exps = new Array(scores.length)
  for (let i = 0; i < scores.length; i++) {
    exps[i] = Math.exp(scores[i] - m)
    tot += exps[i]
  }
  for (let i = 0; i < scores.length; i++) exps[i] /= tot
  return exps
}

/**
 * Evaluate the tree ensemble on an ordered feature vector.
 * @param {object} treeJson - parsed triage_trees.json
 * @param {number[]} x - feature vector in the canonical (features_config) order
 * @returns {{ classIndex: number, probabilities: number[] }}
 */
export function evaluateTrees(treeJson, x) {
  const nClasses = treeJson.n_classes
  const scores = treeJson.base_values && treeJson.base_values.length
    ? treeJson.base_values.slice()
    : new Array(nClasses).fill(0)

  const trees = treeJson.trees
  for (let t = 0; t < trees.length; t++) {
    const { feat, thr, left, right, leaf } = trees[t]
    let node = 0
    // Walk until a leaf (feat === -1).
    while (feat[node] !== -1) {
      node = x[feat[node]] <= thr[node] ? left[node] : right[node]
    }
    const contribs = leaf[node]
    if (contribs) {
      for (let k = 0; k < contribs.length; k++) {
        scores[contribs[k][0]] += contribs[k][1]
      }
    }
  }

  const probabilities = treeJson.post_transform === 'SOFTMAX' ? softmax(scores) : scores
  let classIndex = 0
  for (let i = 1; i < probabilities.length; i++) {
    if (probabilities[i] > probabilities[classIndex]) classIndex = i
  }
  return { classIndex, probabilities }
}
