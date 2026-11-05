import { describe, expect, it } from "vitest";
import {
  evaluateNodeTernary,
  traverseTreeTernary,
  computeSaabasAttributions,
  assessFeatureCompleteness,
  explainPrediction,
  evaluateTrees,
  type TreeNode,
  type TreeJson,
} from "../src/treeEvaluator.js";
import { getUnmeasuredFeatureSet } from "../src/features.js";

describe("Ternary Tree Routing & Saabas Delta Attribution (ADR §48)", () => {
  it("routes NaN to left child when defaultLeft is 1", () => {
    const tree: TreeNode = {
      feat: [0, -1, -1],
      thr: [90.0, 0, 0],
      left: [1, -1, -1],
      right: [2, -1, -1],
      defaultLeft: [1, 0, 0],
      leaf: [null, [[0, 0.1], [1, 0.2], [2, 0.7]], [[0, 0.8], [1, 0.1], [2, 0.1]]],
    };

    const step = evaluateNodeTernary(tree, 0, [NaN]);
    expect(step.nextNode).toBe(1);
    expect(step.defaultLeftUsed).toBe(true);

    const traversal = traverseTreeTernary(tree, [NaN]);
    expect(traversal.leafIndex).toBe(1);
  });

  it("routes NaN to right child when defaultLeft is 0", () => {
    const tree: TreeNode = {
      feat: [0, -1, -1],
      thr: [90.0, 0, 0],
      left: [1, -1, -1],
      right: [2, -1, -1],
      defaultLeft: [0, 0, 0],
      leaf: [null, [[0, 0.1], [1, 0.2], [2, 0.7]], [[0, 0.8], [1, 0.1], [2, 0.1]]],
    };

    const step = evaluateNodeTernary(tree, 0, [NaN]);
    expect(step.nextNode).toBe(2);
    expect(step.defaultLeftUsed).toBe(true);

    const traversal = traverseTreeTernary(tree, [NaN]);
    expect(traversal.leafIndex).toBe(2);
  });

  it("routes measured values via standard float32 threshold split", () => {
    const tree: TreeNode = {
      feat: [0, -1, -1],
      thr: [92.5, 0, 0],
      left: [1, -1, -1],
      right: [2, -1, -1],
      defaultLeft: [1, 0, 0],
      leaf: [null, [[0, 0.1], [1, 0.9]], [[0, 0.9], [1, 0.1]]],
    };

    expect(evaluateNodeTernary(tree, 0, [91.0]).nextNode).toBe(1);
    expect(evaluateNodeTernary(tree, 0, [95.0]).nextNode).toBe(2);
  });

  it("computes exact Saabas node-to-node expectation deltas with nodeVal", () => {
    const tree: TreeNode = {
      feat: [0, 1, -1, -1, -1],
      thr: [100.0, 38.0, 0, 0, 0],
      left: [1, 3, -1, -1, -1],
      right: [2, 4, -1, -1, -1],
      defaultLeft: [1, 1, 0, 0, 0],
      leaf: [null, null, [[0, 0.1], [1, 0.8], [2, 0.1]], [[0, 0.05], [1, 0.15], [2, 0.8]], [[0, 0.7], [1, 0.2], [2, 0.1]]],
      nodeVal: [
        [0.33, 0.33, 0.34], // root node 0
        [0.20, 0.30, 0.50], // node 1 (left child of 0)
        [0.10, 0.80, 0.10], // node 2 (right child of 0)
        [0.05, 0.15, 0.80], // leaf 3 (left child of 1)
        [0.70, 0.20, 0.10], // leaf 4 (right child of 1)
      ],
    };

    const featureNames = ["heart_rate", "temperature"];
    // HR = 90 <= 100 -> node 1; Temp = 37.5 <= 38.0 -> leaf 3
    const featureVector = [90.0, 37.5];

    const attributions = computeSaabasAttributions(tree, featureVector, featureNames);
    // Delta for heart_rate at node 0 -> node 1:
    // Class 0: 0.20 - 0.33 = -0.13
    // Class 1: 0.30 - 0.33 = -0.03
    // Class 2: 0.50 - 0.34 = +0.16
    expect(attributions["heart_rate"]![0]).toBeCloseTo(-0.13, 4);
    expect(attributions["heart_rate"]![1]).toBeCloseTo(-0.03, 4);
    expect(attributions["heart_rate"]![2]).toBeCloseTo(0.16, 4);

    // Delta for temperature at node 1 -> leaf 3:
    // Class 2: 0.80 - 0.50 = +0.30
    expect(attributions["temperature"]![2]).toBeCloseTo(0.30, 4);
  });

  it("suppresses unmeasured features from clinician attribution", () => {
    const tree: TreeNode = {
      feat: [0, 1, -1, -1, -1],
      thr: [100.0, 38.0, 0, 0, 0],
      left: [1, 3, -1, -1, -1],
      right: [2, 4, -1, -1, -1],
      defaultLeft: [1, 1, 0, 0, 0],
      leaf: [null, null, [[0, 0.1], [1, 0.8], [2, 0.1]], [[0, 0.05], [1, 0.15], [2, 0.8]], [[0, 0.7], [1, 0.2], [2, 0.1]]],
      nodeVal: [
        [0.33, 0.33, 0.34],
        [0.20, 0.30, 0.50],
        [0.10, 0.80, 0.10],
        [0.05, 0.15, 0.80],
        [0.70, 0.20, 0.10],
      ],
    };

    const featureNames = ["heart_rate", "temperature"];
    const featureVector = [NaN, 37.5];
    const unmeasuredSet = new Set(["heart_rate"]);

    const attributions = computeSaabasAttributions(tree, featureVector, featureNames, unmeasuredSet);
    expect(attributions["heart_rate"]![2]).toBe(0);
    expect(attributions["temperature"]![2]).toBeCloseTo(0.30, 4);
  });

  it("getUnmeasuredFeatureSet correctly identifies raw missing vitals and derived ratios", () => {
    const form = {
      patient_age: 40,
      patient_sex: "female" as const,
      bp_systolic: null,
      bp_diastolic: undefined,
      heart_rate: 80,
      spo2: 98,
      temperature: 37.0,
      chief_complaint: "fever",
    };

    const unmeasured = getUnmeasuredFeatureSet(form);
    expect(unmeasured.has("bp_systolic")).toBe(true);
    expect(unmeasured.has("bp_diastolic")).toBe(true);
    expect(unmeasured.has("pulse_pressure")).toBe(true);
    expect(unmeasured.has("mean_arterial_pressure")).toBe(true);
    expect(unmeasured.has("shock_index")).toBe(true);
    expect(unmeasured.has("heart_rate")).toBe(false);
    expect(unmeasured.has("spo2")).toBe(false);
    expect(unmeasured.has("temperature")).toBe(false);
  });

  it("assessFeatureCompleteness correctly classifies COMPLETE, PARTIAL_VITALS, and SPARSE_CONTEXT", () => {
    // 1. COMPLETE: 0 missing vitals
    const complete = assessFeatureCompleteness({
      bp_systolic: 120,
      bp_diastolic: 80,
      heart_rate: 72,
      spo2: 98,
      temperature: 36.8,
      symptoms: [],
    });
    expect(complete.status).toBe("COMPLETE");
    expect(complete.state).toBe("COMPLETE");
    expect(complete.missingCriticalVitals.length).toBe(0);
    expect(complete.lowConfidence).toBe(false);

    // 2. PARTIAL_VITALS: 2 missing vitals
    const partial1 = assessFeatureCompleteness({
      bp_systolic: null,
      bp_diastolic: null,
      heart_rate: 72,
      spo2: 98,
      temperature: 36.8,
      symptoms: [],
    });
    expect(partial1.status).toBe("PARTIAL_VITALS");
    expect(partial1.state).toBe("PARTIAL_VITALS");
    expect(partial1.missingCriticalVitals).toEqual(["bp_systolic", "bp_diastolic"]);
    expect(partial1.lowConfidence).toBe(false);

    // 3. PARTIAL_VITALS: 3 missing vitals with >=1 symptom
    const partial2 = assessFeatureCompleteness({
      bp_systolic: null,
      bp_diastolic: null,
      heart_rate: null,
      spo2: 98,
      temperature: 36.8,
      symptoms: ["chest_pain"],
    });
    expect(partial2.status).toBe("PARTIAL_VITALS");
    expect(partial2.state).toBe("PARTIAL_VITALS");
    expect(partial2.missingCriticalVitals.length).toBe(3);
    expect(partial2.lowConfidence).toBe(false);

    // 4. SPARSE_CONTEXT: >=3 missing vitals AND zero symptoms
    const sparse = assessFeatureCompleteness({
      bp_systolic: null,
      bp_diastolic: null,
      heart_rate: null,
      spo2: 98,
      temperature: null,
      symptoms: [],
    });
    expect(sparse.status).toBe("SPARSE_CONTEXT");
    expect(sparse.state).toBe("SPARSE_CONTEXT");
    expect(sparse.missingCriticalVitals.length).toBe(4);
    expect(sparse.lowConfidence).toBe(true);
  });
});
