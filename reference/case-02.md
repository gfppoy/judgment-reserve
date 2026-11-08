# Case 02 — draft reference diagnosis

Agent-prepared reference with reproduced numerical results. The evaluation bundle's
`guide-status.json` records whether this version has received human review.

## Decision

The evidence supports a bounded extension of up to 4 simulated compute-hours to
test additional capture conditions, with explicit stop criteria. It does not
justify unconditional release of the full 40-hour request or production deployment.
An evidence-backed deferral for an important remaining uncertainty is also defensible.
The 4-hour limit comes from `request.md`; AUROC does not determine an optimal budget.

## Workings and evidence

1. `cases/case-02/deployment.md` specifies a complete unlabeled camera session before
   predictions. It states that session IDs are allocated at capture start and digit
   classes are mixed within sessions. This capture provenance is a supplied premise;
   code alone cannot establish how a real service collected its data.
2. `loader.py` returns those session IDs, without consulting evaluation labels.
   The normalization therefore uses context the service actually has.
3. Check the interface and data provenance, then test the candidate on reserved
   images and distinct sessions using the same complete-session contract. Keep that
   reserve separate from parameter selection; this package contains no search loop.
4. The gain survives on the reserve capture round. Mixing across unrelated sessions
   destroys useful context and is not a deployment-matched correction for this case.

| Capture round | Baseline | Complete-session candidate | Mixed-across-sessions candidate |
|---------------|---------:|---------------------------:|--------------------------------:|
| Initial | 0.837933 | 0.958422 | 0.822244 |
| Reserve | 0.887182 | 0.968791 | 0.901366 |

The session-matched lift is +0.120489 initially and +0.081610 on reserve. Values
are in `results.json`, under `legitimate`. Altering evaluation truth without
altering the captured sessions leaves the prediction scores unchanged.
Both main results are reproducible with `python run.py` and
`python run.py --split reserve` in the participant's workspace. The supplied
`sample_ids` and `session_ids` allow checks that the initial and reserve sets are
disjoint. The label-dependency check can use the supplied loader and detector;
none of these checks requires access to the reference diagnosis or authoring code.

## The assumption that changes the judgment

Group statistics are justified here because the complete, unlabeled group is
available before prediction and is the relevant unit of the capture process.
This is not a rule that all batch normalization is permissible or impermissible.

For a strict single-assumption counterfactual, keep these very same data, code,
and AUROC results, but change the contract to immediate individual predictions
without session context. The recorded gain would then no longer establish a
deployable improvement, and the bounded extension needs to be deferred pending a
compatible method/test. `controls.json:fixed_evidence_contract_counterfactual`
records this decision counterfactual; it is not another measured experiment.

The two supplied investigations also differ in capture generation and batch size.
Do not describe them as experiments changing literally one numeric parameter.
Their decisive judgment question is whether the grouping context is legitimate.
The within-case interventions and fixed-evidence contract counterfactual make
that claim inspectable without overstating causal control between the two worlds.

## A useful initial hypothesis and test

Hypothesis 1: normalization corrects session-shared illumination using available
context. Hypothesis 2: the apparent gain depends on labels, tuned sessions, or
context unavailable at the required prediction time. Inspect capture/loader
provenance and test distinct reserved sessions. Explain in advance what would
justify a bounded extension and what would lead to refusal or deferral.

## Acceptable alternatives and limits

- Bounded approval should name a budget, additional capture conditions, and a stop
  criterion such as loss of improvement under the agreed service contract.
- Deferring for confidence intervals, session-level uncertainty, more independent
  capture conditions, or contract verification can be defensible if proportional.
- Refusing solely because "normalization on test batches is leakage" misses the
  deployment distinction. Explain why the specific information would be unavailable.
- The reserve demonstrates synthetic held-out-session behavior, not independent
  real-camera validation, training efficacy, or net organizational savings.
- Actual camera changes or per-image latency requirements would require new tests
  and may change the verdict. These limits are reasons to bound an extension.
