"""
External-validation harness — run VitalNet's real triage engine against a
labelled patient dataset and report the metrics that actually decide clinical
safety.

This is the machinery that turns an acquired real dataset (MIMIC-IV-ED,
Kaggle KTAS, etc. — see docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md) into
a safety result: discrimination (sensitivity/specificity/PPV/NPV with 95% CIs),
calibration (ECE + reliability), the SAFETY-CRITICAL under-triage rate for
reference-EMERGENCY patients, subgroup slices, and the real-data lift the
deterministic guardrails add over the raw model.

It evaluates the LIVE, model-primary `predict_triage()` in
backend/app/ml/classifier.py — unaffected by the Round 6 rebuild's
clinical-core migration, which only rewired training-time labeling/feature
generation (see train_classifier.py), not this still-deployed backend path.
When apps/api eventually cuts over to `rules_first` (docs/RULES_PRIMARY_DESIGN.md,
docs/CLINICAL_REVIEW.md), this harness should gain a second mode evaluating
clinical-core's `assignTier` directly (via the same cli.mjs bridge
train_classifier.py uses) so real data can validate the rules engine on its
own, not just the model wrapped in it — tracked as a follow-up, not done here.

It is dataset-agnostic: point it at a CSV with the documented schema and it maps
the 5-level ESI/KTAS acuity scales to VitalNet's 3 tiers (overridable), runs the
production `predict_triage()` per row, and reports. It also has a `--self-test`
mode (synthetic patients, rules-engine reference) that PROVES THE MACHINERY only —
those numbers are NOT clinical validation (the reference there is the very rule
the model was trained on).

CSV columns (aliases accepted):
    patient_age|age, patient_sex|sex|gender,
    bp_systolic|sbp, bp_diastolic|dbp, spo2|o2sat, heart_rate|heartrate,
    temperature|temp, chief_complaint|chiefcomplaint,
    symptoms            (optional; '|' or ',' separated allow-listed ids),
    reference_tier      (ROUTINE|URGENT|EMERGENCY)   -- OR --
    reference_acuity|acuity (1-5, with --acuity-scale esi|ktas)

Run:
    cd backend && pip install -r requirements.txt
    PYTHONPATH=backend python tools/training/evaluate_on_real.py --self-test
    PYTHONPATH=backend python tools/training/evaluate_on_real.py --csv data/mimic_ed.csv \
        --acuity-scale esi --temp-fahrenheit

(--self-test additionally needs `pnpm --filter @vitalnet/clinical-core build`
first — it labels its synthetic sample via the same cli.mjs bridge
train_classifier.py uses. --csv mode does not touch clinical-core at all.)
"""
import argparse
import csv
import importlib.util
import math
import os
import sys
import types
import warnings

import numpy as np

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
sys.path.insert(0, BACKEND_DIR)

from app.ml import classifier as clf_mod  # noqa: E402
from app.models.schemas import ALLOWED_SYMPTOMS  # noqa: E402

TIER = {"ROUTINE": 0, "URGENT": 1, "EMERGENCY": 2}
TIER_NAME = {0: "ROUTINE", 1: "URGENT", 2: "EMERGENCY"}

# 5-level acuity -> VitalNet 3-tier. Documented, overridable clinical mapping.
# ESI: 1 resuscitation / 2 emergent -> EMERGENCY; 3 urgent -> URGENT; 4-5 -> ROUTINE.
# KTAS: 1 resuscitation / 2 emergency -> EMERGENCY; 3 urgent -> URGENT; 4-5 -> ROUTINE.
ACUITY_MAPS = {
    "esi": {1: 2, 2: 2, 3: 1, 4: 0, 5: 0},
    "ktas": {1: 2, 2: 2, 3: 1, 4: 0, 5: 0},
}


# ── small stats helpers ──────────────────────────────────────────────────────

def wilson(k: int, n: int, z: float = 1.96):
    """Wilson score interval for a binomial proportion. Returns (p, lo, hi)."""
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


def _fmt_ci(k, n):
    p, lo, hi = wilson(k, n)
    if n == 0:
        return "   n/a   "
    return f"{p:5.3f} [{lo:.3f}-{hi:.3f}]"


def expected_calibration_error(conf: np.ndarray, correct: np.ndarray, n_bins: int = 10):
    ece, n = 0.0, len(conf)
    rows = []
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        mask = (conf > lo) & (conf <= hi)
        m = int(mask.sum())
        if m == 0:
            continue
        acc, avg_conf = float(correct[mask].mean()), float(conf[mask].mean())
        ece += (m / n) * abs(acc - avg_conf)
        rows.append((lo, hi, m, avg_conf, acc))
    return ece, rows


# ── row -> VitalNet form_data ────────────────────────────────────────────────

def _get(row, *names, default=None):
    for nm in names:
        if nm in row and str(row[nm]).strip() != "":
            return row[nm]
    return default


def _num(v, cast=float):
    if v is None or str(v).strip() == "":
        return None
    try:
        return cast(float(v))
    except (ValueError, TypeError):
        return None


def _sex(v):
    s = str(v or "").strip().lower()
    if s in ("m", "male", "1"):
        return "male"
    if s in ("f", "female", "0"):
        return "female"
    return "other"


def row_to_formdata(row, temp_fahrenheit=False):
    temp = _num(_get(row, "temperature", "temp"))
    if temp is not None and temp_fahrenheit:
        temp = round((temp - 32) * 5 / 9, 1)
    raw_symptoms = _get(row, "symptoms", default="") or ""
    symptoms = [s.strip() for s in raw_symptoms.replace("|", ",").split(",") if s.strip()]
    symptoms = [s for s in symptoms if s in ALLOWED_SYMPTOMS]
    return {
        "patient_age": _num(_get(row, "patient_age", "age"), int) or 0,
        "patient_sex": _sex(_get(row, "patient_sex", "sex", "gender")),
        "bp_systolic": _num(_get(row, "bp_systolic", "sbp"), int),
        "bp_diastolic": _num(_get(row, "bp_diastolic", "dbp"), int),
        "spo2": _num(_get(row, "spo2", "o2sat"), int),
        "heart_rate": _num(_get(row, "heart_rate", "heartrate"), int),
        "temperature": temp,
        "symptoms": symptoms,
        "chief_complaint": str(_get(row, "chief_complaint", "chiefcomplaint", default="") or ""),
        "complaint_duration": str(_get(row, "complaint_duration", default="") or ""),
        "location": str(_get(row, "location", default="") or ""),
        "known_conditions": str(_get(row, "known_conditions", default="") or ""),
        "current_medications": "",
        "is_pregnant": None,
    }


def reference_tier(row, acuity_scale):
    rt = _get(row, "reference_tier")
    if rt is not None:
        rt = str(rt).strip().upper()
        if rt in TIER:
            return TIER[rt]
    acuity = _num(_get(row, "reference_acuity", "acuity"), int)
    if acuity is not None and acuity_scale:
        return ACUITY_MAPS[acuity_scale].get(int(acuity))
    return None


# ── evaluation core (operates on arrays) ─────────────────────────────────────

def evaluate(formdatas, y_ref, source_label):
    n = len(y_ref)
    y_prod = np.empty(n, dtype=int)
    y_raw = np.empty(n, dtype=int)
    conf = np.empty(n, dtype=float)
    guardrail = np.zeros(n, dtype=bool)

    engineer = clf_mod._feature_engineer
    if engineer is None:
        from app.ml.clinical_features import ClinicalFeatureEngineer
        engineer = ClinicalFeatureEngineer()
        clf_mod._feature_engineer = engineer

    for i, fd in enumerate(formdatas):
        res = clf_mod.predict_triage(fd)
        y_prod[i] = TIER[res["triage_level"]]
        guardrail[i] = bool(res.get("safety_net_triggered") or res.get("news2_floor_triggered"))
        probs = res.get("probabilities")
        conf[i] = max(probs.values()) if probs else float(res.get("confidence_score", 1.0))
        # raw model tier (no guardrails) for the lift analysis
        fv = np.array([[engineer.engineer_features(fd)[nm] for nm in clf_mod._feature_names]],
                      dtype=np.float32)
        y_raw[i] = int(np.argmax(clf_mod._classifier.predict_proba(fv)[0]))

    _report(y_ref, y_prod, y_raw, conf, guardrail, formdatas, source_label)


def _confusion(y_ref, y_pred):
    cm = np.zeros((3, 3), dtype=int)
    for r, p in zip(y_ref, y_pred):
        cm[r, p] += 1
    return cm


def _report(y_ref, y_prod, y_raw, conf, guardrail, formdatas, source_label):
    n = len(y_ref)
    print("=" * 74)
    print(f"EXTERNAL VALIDATION REPORT  —  {source_label}")
    print(f"n = {n}   reference mix: " +
          ", ".join(f"{TIER_NAME[t]}={int((y_ref == t).sum())}" for t in (0, 1, 2)))
    print("=" * 74)

    cm = _confusion(y_ref, y_prod)
    print("\nConfusion matrix (rows = reference, cols = VitalNet production):")
    print("               pred:ROUTINE  URGENT  EMERGENCY")
    for t in (0, 1, 2):
        print(f"  ref {TIER_NAME[t]:9} {cm[t,0]:9d} {cm[t,1]:8d} {cm[t,2]:10d}")
    acc = float((y_prod == y_ref).mean())
    print(f"\nOverall agreement with reference: {acc:.4f}")

    print("\nPer-tier discrimination (one-vs-rest, Wilson 95% CI):")
    print(f"  {'tier':10} {'sensitivity':>22} {'specificity':>22} {'PPV':>22} {'NPV':>22}")
    for t in (0, 1, 2):
        tp = int(((y_ref == t) & (y_prod == t)).sum())
        fn = int(((y_ref == t) & (y_prod != t)).sum())
        fp = int(((y_ref != t) & (y_prod == t)).sum())
        tn = int(((y_ref != t) & (y_prod != t)).sum())
        print(f"  {TIER_NAME[t]:10} {_fmt_ci(tp, tp+fn):>22} {_fmt_ci(tn, tn+fp):>22} "
              f"{_fmt_ci(tp, tp+fp):>22} {_fmt_ci(tn, tn+fn):>22}")

    # ── SAFETY: under-triage relative to reference ───────────────────────────
    print("\n*** SAFETY — under-triage (VitalNet shipped BELOW the reference) ***")
    under = int((y_prod < y_ref).sum())
    over = int((y_prod > y_ref).sum())
    print(f"  overall under-triage: {_fmt_ci(under, n)}   (over-triage: {over/n:.3f})")
    em = y_ref == 2
    em_miss = int((em & (y_prod < 2)).sum())
    em_to_routine = int((em & (y_prod == 0)).sum())
    print(f"  EMERGENCY missed (ref=EMERGENCY, pred<EMERGENCY): "
          f"{_fmt_ci(em_miss, int(em.sum()))}   (of which two-tier ->ROUTINE: {em_to_routine})")
    urg = y_ref == 1
    print(f"  URGENT ->ROUTINE (ref=URGENT, pred=ROUTINE):      "
          f"{_fmt_ci(int((urg & (y_prod == 0)).sum()), int(urg.sum()))}")

    # ── guardrail lift on real data ──────────────────────────────────────────
    print("\nDeterministic guardrail contribution (real-data lift):")
    raw_em_recall = _fmt_ci(int((em & (y_raw == 2)).sum()), int(em.sum()))
    prod_em_recall = _fmt_ci(int((em & (y_prod == 2)).sum()), int(em.sum()))
    print(f"  EMERGENCY sensitivity — raw model : {raw_em_recall}")
    print(f"  EMERGENCY sensitivity — production : {prod_em_recall}")
    print(f"  cases where a guardrail fired      : {guardrail.mean():.3f}")

    # ── calibration ──────────────────────────────────────────────────────────
    correct = (y_prod == y_ref).astype(float)
    ece, rows = expected_calibration_error(conf, correct)
    print(f"\nCalibration (predicted-class confidence vs correctness): ECE = {ece:.4f}")
    for lo, hi, m, avg_conf, a in rows:
        print(f"    conf [{lo:.1f}-{hi:.1f}]  n={m:6d}  mean_conf={avg_conf:.3f}  accuracy={a:.3f}")

    # ── subgroup: EMERGENCY sensitivity by age band, sex, vital completeness ──
    ages = np.array([fd["patient_age"] for fd in formdatas])
    sexes = np.array([fd["patient_sex"] for fd in formdatas])
    incomplete = np.array([any(fd[k] is None for k in
                               ("bp_systolic", "spo2", "heart_rate", "temperature"))
                           for fd in formdatas])
    print("\nSubgroup — EMERGENCY sensitivity (the equity/safety slice that matters):")

    def _band(a):
        return ("<1" if a < 1 else "1-4" if a < 5 else "5-17" if a < 18
                else "18-64" if a < 65 else "65+")

    band = np.array([_band(a) for a in ages])
    for label, mask in (
        *[(f"age {b}", band == b) for b in ("<1", "1-4", "5-17", "18-64", "65+")],
        ("sex male", sexes == "male"), ("sex female", sexes == "female"),
        ("vitals complete", ~incomplete), ("vitals incomplete", incomplete),
    ):
        sub_em = mask & em
        k = int((sub_em & (y_prod == 2)).sum())
        print(f"  {label:18} n(EMERGENCY)={int(sub_em.sum()):5d}   sensitivity={_fmt_ci(k, int(sub_em.sum()))}")

    print("\n" + "=" * 74)
    print("Report complete. Population-mismatch caveat applies — see "
          "docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md §7.")
    print("=" * 74)


# ── inputs ───────────────────────────────────────────────────────────────────

def load_csv(path, acuity_scale, temp_fahrenheit):
    formdatas, y_ref, dropped = [], [], 0
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            ref = reference_tier(row, acuity_scale)
            if ref is None:
                dropped += 1
                continue
            formdatas.append(row_to_formdata(row, temp_fahrenheit))
            y_ref.append(ref)
    if dropped:
        print(f"[note] dropped {dropped} row(s) with no usable reference label")
    return formdatas, np.array(y_ref, dtype=int)


def self_test(n=8000):
    """Harness self-test on synthetic patients — PROVES THE MACHINERY ONLY.
    The reference here is clinical-core's rules engine (the same one the
    model was trained to reproduce — see train_classifier.py), labelled via
    its cli.mjs bridge, so the numbers are meaningless as clinical
    validation (they will look great). Its only purpose is to show the
    report runs and the metrics are sane."""
    stub = types.ModuleType("tree_export")
    stub.onnx_to_tree_json = lambda *a, **k: None
    stub.evaluate_tree_json = lambda *a, **k: (None,)
    sys.modules["tree_export"] = stub
    spec = importlib.util.spec_from_file_location(
        "train_classifier", os.path.join(HERE, "train_classifier.py"))
    tc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tc)

    np.random.seed(2026)
    sevs, w = ["healthy", "mild", "moderate", "severe", "critical"], [0.30, 0.22, 0.22, 0.16, 0.10]
    formdatas = [
        tc.generate_patient(np.random.choice(sevs, p=w), pediatric=np.random.random() < 0.22)
        for _ in range(n)
    ]
    y_ref = np.array(tc.assign_triage_labels(formdatas), dtype=int)
    print("\n" + "!" * 74)
    print("!! SELF-TEST MODE — reference = clinical-core's rules engine (the same")
    print("!! rule the model was trained on). This validates the HARNESS, not the")
    print("!! model. These numbers are NOT clinical validation.")
    print("!" * 74 + "\n")
    return formdatas, y_ref


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", help="Path to a labelled patient CSV (see module docstring).")
    ap.add_argument("--acuity-scale", choices=["esi", "ktas"], default="esi",
                    help="How to map a 1-5 reference_acuity column to 3 tiers (default esi).")
    ap.add_argument("--temp-fahrenheit", action="store_true",
                    help="Convert a Fahrenheit temperature column to Celsius (e.g. MIMIC).")
    ap.add_argument("--self-test", action="store_true",
                    help="Run the harness on synthetic data (machinery check only).")
    args = ap.parse_args()

    clf_mod.load_classifier()

    if args.self_test:
        fds, y = self_test()
        evaluate(fds, y, "SELF-TEST (synthetic, rules-engine reference)")
    elif args.csv:
        fds, y = load_csv(args.csv, args.acuity_scale, args.temp_fahrenheit)
        evaluate(fds, y, f"{os.path.basename(args.csv)} (acuity={args.acuity_scale})")
    else:
        ap.error("provide --csv PATH or --self-test")


if __name__ == "__main__":
    main()
