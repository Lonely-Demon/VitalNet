"""
Tree-ensemble → compact JSON exporter + a reference evaluator.

Used only at TRAINING time (not by the running API). Converts the ONNX
TreeEnsembleClassifier produced by skl2onnx for the HistGradientBoosting model
into a small JSON structure that a ~120-line dependency-free JavaScript
evaluator (apps/web/src/utils/treeEvaluator.js) can walk directly — so the PWA
does offline triage with NO onnxruntime-web WASM (see FEATURES_ROADMAP /
CODEBASE_MAP for the rationale: ~12 MB of precached WASM removed, far lighter on
2 GB-class devices and metered rural links).

`evaluate_tree_json` here is a Python reference implementation of the exact
algorithm the JS evaluator runs. train_classifier.py asserts it agrees with the
real model (clf.predict / onnxruntime) on the held-out set, and a golden-vector
fixture lets a frontend test assert the JS matches too — giving full
py-pkl == onnx == JSON == JS parity, enforced by test rather than trusted.

ONNX TreeEnsembleClassifier reference:
  https://onnx.ai/onnx/operators/onnx_aionnxml_TreeEnsembleClassifier.html
"""
import math
from typing import Any, Dict, List

import numpy as np


def _attrs(node) -> Dict[str, Any]:
    import onnx
    out = {}
    for a in node.attribute:
        out[a.name] = onnx.helper.get_attribute_value(a)
    return out


def onnx_to_tree_json(onnx_model, n_features: int) -> Dict[str, Any]:
    """Parse the single TreeEnsembleClassifier node into a compact dict."""
    tree_node = next(
        (n for n in onnx_model.graph.node if n.op_type == "TreeEnsembleClassifier"),
        None,
    )
    if tree_node is None:
        raise RuntimeError("No TreeEnsembleClassifier node found in the ONNX graph.")

    a = _attrs(tree_node)

    def _dec(v):
        return v.decode() if isinstance(v, bytes) else v

    nodes_treeids = list(a["nodes_treeids"])
    nodes_nodeids = list(a["nodes_nodeids"])
    nodes_featureids = list(a["nodes_featureids"])
    nodes_values = [float(x) for x in a["nodes_values"]]
    nodes_modes = [_dec(m) for m in a["nodes_modes"]]
    nodes_true = list(a["nodes_truenodeids"])
    nodes_false = list(a["nodes_falsenodeids"])

    class_treeids = list(a["class_treeids"])
    class_nodeids = list(a["class_nodeids"])
    class_ids = list(a["class_ids"])
    class_weights = [float(x) for x in a["class_weights"]]

    labels = [int(x) for x in a.get("classlabels_int64s", [])]
    n_classes = len(labels) if labels else (max(class_ids) + 1)
    post_transform = _dec(a.get("post_transform", "NONE"))
    base_values = [float(x) for x in a.get("base_values", [])]

    # Group nodes by tree.
    tree_ids = sorted(set(nodes_treeids))
    trees: List[Dict[str, Any]] = []
    tree_index = {t: i for i, t in enumerate(tree_ids)}

    # Per (treeid) -> per nodeid -> record
    per_tree_nodes: Dict[int, Dict[int, Dict[str, Any]]] = {t: {} for t in tree_ids}
    for i in range(len(nodes_nodeids)):
        t = nodes_treeids[i]
        nid = nodes_nodeids[i]
        per_tree_nodes[t][nid] = {
            "mode": nodes_modes[i],
            "feat": int(nodes_featureids[i]),
            "thr": nodes_values[i],
            "left": int(nodes_true[i]),
            "right": int(nodes_false[i]),
        }

    # Attach leaf contributions.
    per_tree_leaf: Dict[int, Dict[int, List[List[float]]]] = {t: {} for t in tree_ids}
    for i in range(len(class_nodeids)):
        t = class_treeids[i]
        nid = class_nodeids[i]
        per_tree_leaf[t].setdefault(nid, []).append([int(class_ids[i]), class_weights[i]])

    for t in tree_ids:
        nodes = per_tree_nodes[t]
        max_nid = max(nodes.keys())
        feat = [-1] * (max_nid + 1)
        thr = [0.0] * (max_nid + 1)
        left = [-1] * (max_nid + 1)
        right = [-1] * (max_nid + 1)
        leaf: List[Any] = [None] * (max_nid + 1)
        for nid, rec in nodes.items():
            if rec["mode"] == "LEAF":
                leaf[nid] = per_tree_leaf[t].get(nid, [])
            else:
                # Only BRANCH_LEQ is produced for these trees; assert to catch
                # any future skl2onnx change that would break the JS evaluator.
                if rec["mode"] != "BRANCH_LEQ":
                    raise RuntimeError(
                        f"Unsupported split mode {rec['mode']!r}; the JS evaluator "
                        "only implements BRANCH_LEQ. Update both if this changes."
                    )
                feat[nid] = rec["feat"]
                # Round to keep the JSON compact. The 9-decimal rounding is NOT
                # relied on for exactness — the evaluators (this reference +
                # treeEvaluator.js) cast BOTH the feature value and the
                # threshold to float32 before the `<=` comparison, exactly
                # mirroring the server's `np.array(..., dtype=np.float32)` cast
                # before predict. A 9-decimal-rounded threshold snaps back to
                # the identical float32 as the unrounded onnx threshold, so the
                # comparison is bit-identical to onnxruntime/sklearn regardless
                # of the rounding. This closes a latent divergence where a
                # feature value landing exactly on a split threshold (common for
                # low-cardinality discrete features like seasonal_risk ∈
                # {1.0,1.1,1.3}) took different branches online vs offline. See
                # docs/DECISIONS.md §23/§31.
                thr[nid] = round(rec["thr"], 9)
                left[nid] = rec["left"]
                right[nid] = rec["right"]
        trees.append({"feat": feat, "thr": thr, "left": left, "right": right, "leaf": leaf})

    return {
        "n_features": int(n_features),
        "n_classes": int(n_classes),
        "labels": labels or list(range(n_classes)),
        "base_values": base_values,
        "post_transform": post_transform,
        "trees": trees,
        "_tree_index": tree_index,  # not needed at eval time; dropped before save
    }


def _softmax(scores: List[float]) -> List[float]:
    m = max(scores)
    exps = [math.exp(s - m) for s in scores]
    tot = sum(exps)
    return [e / tot for e in exps]


def evaluate_tree_json(tree_json: Dict[str, Any], x: List[float]):
    """
    Reference implementation of the exact algorithm the JS evaluator runs.
    Returns (predicted_class_index, probabilities_list).
    Root of every tree is nodeid 0. BRANCH_LEQ: go left (true) if x[feat] <= thr.
    """
    n_classes = tree_json["n_classes"]
    scores = list(tree_json["base_values"]) if tree_json["base_values"] else [0.0] * n_classes

    for tree in tree_json["trees"]:
        feat, thr, left, right, leaf = tree["feat"], tree["thr"], tree["left"], tree["right"], tree["leaf"]
        node = 0
        # Walk until a leaf (feat == -1 marks a leaf node). Cast both operands
        # to float32 so the comparison is bit-identical to the server's float32
        # model (mirrored by Math.fround in treeEvaluator.js). See onnx_to_tree_json.
        while feat[node] != -1:
            node = left[node] if np.float32(x[feat[node]]) <= np.float32(thr[node]) else right[node]
        contribs = leaf[node]
        if contribs:
            for cls, w in contribs:
                scores[cls] += w

    if tree_json["post_transform"] == "SOFTMAX":
        probs = _softmax(scores)
    else:
        probs = scores
    pred = int(np.argmax(probs))
    return pred, probs
