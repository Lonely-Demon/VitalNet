# Design proposal — rules-primary triage (ML demoted to advisory)

> **Status: IMPLEMENTED (Round 6 rebuild), pending clinician sign-off before
> production use.** This document originally proposed the design below; it
> has since been built as `rules_first` mode in
> `packages/clinical-core/src/triage.ts` (`docs/DECISIONS.md` §33). The
> implementation is **stricter** than this document's original proposal —
> see §3a. It is **not live**: every endpoint in
> `apps/web/src/api/base.js`'s `ENDPOINT_BACKEND` map is `'legacy'`, and
> `backend/app/ml/classifier.py` (model-primary) remains what patients
> actually experience. Wiring `rules_first` into production requires the
> validation gate in §5 (unchanged) — specifically `docs/CLINICAL_REVIEW.md`'s
> clinician sign-off of the 51 EMERGENCY→URGENT delta quantified below. This
> file is kept as the historical record of the proposal and its rationale;
> read `docs/DECISIONS.md` §33 and `docs/CLINICAL_REVIEW.md` for the current,
> living status.

## 1. Why (the evidence)

The model-vs-rule ablation (`tools/training/ablation_model_vs_rule.py`,
`CLINICAL_RISK_MANAGEMENT.md §3`) established:

- The trained model reproduces the deterministic evidence-based scorer the
  large majority of the time — it is largely a **distillation** of that rule
  (see `CLINICAL_RISK_MANAGEMENT.md §3b/3c` for the exact, reference-standard-
  dependent numbers, and the caveat on comparing them across the Round 6
  migration).
- Its deviations are **net-negative on safety** in the production path: 191
  cases still ship *below* the evidence-based rule after all guardrails,
  including two-tier EMERGENCY→ROUTINE drops in the 60k-sample run; 130 of
  16,264 rule-EMERGENCY cases (0.80%) ship below EMERGENCY — each an
  **unvalidated** de-escalation.
- Independently, `packages/clinical-core/test/conformance/report.md`
  quantifies exactly what adopting `rules_first` would change relative to
  today's production behaviour: **88/10,000 (0.88%) tier changes**, 51 of
  them EMERGENCY→URGENT.

There is no ground truth to justify those de-escalations, and an opaque model
is not clinician-reviewable. So the model should not be allowed to set a tier
*lower* than the transparent rule.

## 2. Prior architecture (still live today — `backend/app/ml/`, model-primary)

```
T_final = model.predict()          # opaque, primary
          then safety_net()        # can only escalate the UNAMBIGUOUS extremes
          then news2_floor()       # can only lift ROUTINE→URGENT on one vital
```

The deterministic rules are a *partial* wrap that catches only the unambiguous
subset. The model owns the decision everywhere else — including the ambiguous
band where its unvalidated de-escalations live. This is exactly what
`packages/clinical-core/src/triage.ts`'s `hybrid` mode reproduces (byte-for-
byte, per its own 100%-agreement conformance test), for the transition period.

## 3. Implemented architecture (`rules_first` mode, `packages/clinical-core`)

`packages/clinical-core/src/rules/engine.ts::assignTier()` — promoted from
what was previously `train_classifier.py::assign_triage_label`,
a training-label-only function — is now the **full, inference-time-capable**
rules engine: override checks, the NEWS2/qSOFA aggregate scorer, and the
NEWS2 floor, all in one place. `triage.ts`'s `rules_first` mode:

```ts
export function triage(form, options): TriageResult {
  // rules_first (default): the rules engine is the ENTIRE authoritative
  // decision. The model, if available, is computed purely as an advisory
  // opinion and never influences `tier`.
  const engineResult = assignTier(form);
  const model = canRunModel ? runModel(form, trees, featureNames) : undefined;
  return {
    tier: engineResult.tier,                              // T_final = T_rule, always
    firedRules: engineResult.firedRules,                  // citable, e.g. "aggregate_score_7plus"
    ...(model ? { model, modelAgreed: model.tier === engineResult.tier } : {}),
  };
}
```

### 3a. Stricter than originally proposed

The original proposal below (§3, unmodified since) suggested
`T_final = max(T_rule, T_model)` — letting the model still **escalate** the
tier above what the rules alone would say, preserving some of its "safe-
direction" value. The actual implementation is stricter: `T_final = T_rule`
**unconditionally** — the model can never change the tier in *either*
direction. Disagreement, in either direction, is instead captured as
`modelAgreed: false` and folded into `needs_review`
(`apps/api/supabase/functions/api/_shared/cases.ts::computeNeedsReview`,
tested — a case where the model says EMERGENCY and the rules-authoritative
tier is lower cannot silently sink out of the review queue, since the rules
engine's own decision is deterministic and therefore never "low confidence"
about itself).

This is a **safer** posture than the original proposal: it makes the "black
box never touches the decision" property absolute rather than asymmetric,
and it converts *every* disagreement (not just de-escalations) into a
research signal for eventual model promotion, per §6/§7 below.

### 3b. What stays true from the original proposal

- **`T_rule` is the primary, auditable decision** — a clinician can read,
  sign off on, and a regulator can inspect it. It is deterministic and
  mirrors 1:1 between the browser and the (eventual) server, because it is
  now literally the same compiled TypeScript running in both — see
  `CLINICAL_RISK_MANAGEMENT.md` H7.
- **The disagreement becomes a research signal, not a silent risk**: every
  `modelAgreed === false` case is logged (`case_records.model_tier`,
  `rules_fired`, `model_agreed` — `phase29_events_and_advisory_model.sql`)
  so that, once real outcome data exists, the model's disagreements can be
  evaluated for whether they'd have been correct — the principled way to
  later *promote* the model on evidence, not assertion.

## 4. Implementation (as built)

1. Extracted the scorer into `packages/clinical-core/src/rules/`
   (`bands.ts` + `rules.ts` + `engine.ts`), used by **both**
   `tools/training/train_classifier.py` (via `packages/clinical-core/cli.mjs`,
   a JSONL subprocess bridge) and the (future) inference path — single
   source of truth, no drift. This is the mechanism `CLINICAL_RISK_MANAGEMENT.md`
   H12 documents a real, previously-undiscovered consequence of: the
   inference-time NEWS2 floor is now also applied during *training-label*
   generation, which the old two-function Python split never did.
2. `triage()` computes `T_rule` (`assignTier`) and, when a tree bundle is
   supplied, `T_model` (the advisory opinion) — `modelAgreed`,
   `decision_source`-equivalent provenance (`firedRules`), all present in
   `TriageResult`.
3. Mirrored in exactly one place (`apps/web`'s offline path calls the same
   `triage()` function `apps/api` would) — the four-parity-suite apparatus
   this design set out to eliminate is gone (`docs/DECISIONS.md` §33).
4. `MODEL_CARD.md`, `CLINICAL_RISK_MANAGEMENT.md`, and UI copy
   (`apps/web/src/pages/IntakeForm.jsx`) updated to show the rule as primary,
   the model as a second opinion — including an honest `PENDING`/null state
   when only the rules-only fallback ran offline (see `triageClassifier.js`).
5. The ablation (`tools/training/ablation_model_vs_rule.py`) was re-run
   post-migration; under-triage-below-rule in the **production path**
   remains at the same order of magnitude as pre-migration (191/60,000) —
   expected, since `backend/app/ml/`'s production path is unchanged; it is
   `rules_first`, once live, that is expected to bring this to zero by
   construction.

## 5. Validation gate (before wiring `rules_first` into any live traffic)

Unchanged from the original proposal, and **not yet satisfied**:

- Run `tools/training/evaluate_on_real.py` on a real external dataset
  **before and after** the cutover; confirm EMERGENCY sensitivity does not
  regress and quantify the over-triage change (see §6).
- **Clinician review of `packages/clinical-core/src/rules/**`** — now
  concretely actionable via `docs/CLINICAL_REVIEW.md`'s checklist and the
  named 51-case delta, rather than an abstract ask. This is the single
  blocking item.
- Update the risk file (`CLINICAL_RISK_MANAGEMENT.md`) and model card in the
  same change that flips the `ENDPOINT_BACKEND` map.

## 6. Tradeoff (state it honestly)

`T_final = T_rule` (unconditional) removes the model's ability to add
safe-direction value via escalation, which the original `max()` proposal
would have preserved — trading a small amount of theoretical model upside for
a strictly simpler, fully rule-auditable decision. Given §1's evidence that
the model's deviations are net-negative on safety and the model has never
been validated against real outcomes, this trade is the right one *for now*.
The counter-argument — that the boosted trees capture interactions the
additive rule misses — remains **unvalidated**; §3b's logging is exactly what
would let that be tested empirically once real data exists, rather than
assumed either way.

Separately: `rules_first` increases over-triage relative to today's
production path (35/10,000 upgraded per the conformance report) — the safe
direction, but with real costs (clinician load, alarm fatigue — itself a
hazard, `CLINICAL_RISK_MANAGEMENT.md` H3). `evaluate_on_real.py` measures
this precisely on real data when available, rather than leaving it a guess.

## 7. Recommendation

Unchanged: adopt `rules_first`. It has now been built, in a stricter form
than originally proposed, and is a documented single commit
(`docs/DECISIONS.md` §33) away from being wired into production once
`docs/CLINICAL_REVIEW.md`'s sign-off clears. It removes the entire class of
unvalidated under-triage by construction, preserves a path to promote the
model on future evidence rather than assertion, and — critically — turned
"would you review our triage logic" from an abstract ask into a concrete,
reviewable, 51-case artifact. That last point is arguably the highest-value
outcome of this whole design: it is the thing most likely to actually get a
clinician's attention.
