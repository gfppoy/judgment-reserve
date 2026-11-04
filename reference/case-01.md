# Case 01 — draft reference diagnosis

**Status: agent-prepared draft; awaiting human review.** The numbers below are
reproduced, but the diagnosis and assessment guidance are not yet human-approved.

## Decision

Do not release the requested 40 compute-hours on the present evidence. A short,
deployment-matched diagnostic is justified; after the reported gain disappears,
decline this scale-up or defer it pending a corrected method and new evidence.
This does not establish that every brightness-normalization method is useless.

## Workings and evidence

1. `cases/case-01/loader.py` passes evaluation labels into `make_groups`. Images
   are partitioned into familiar and unfamiliar groups before candidate scoring.
2. `detector.py:normalize` estimates the brightness correction within each group.
   Thus evaluation truth affects a sample's prediction through its companions,
   even though `novelty_scores` does not receive labels directly.
3. `deployment.md` says incoming batches are arbitrary mixtures and lack the
   archive collection identifiers and familiarity labels. Those grouping conditions
   cannot be assumed at prediction time.
4. Hold the images, reference bank, scorer, and batch size fixed. Replace the
   label-conditioned grouping with label-blind mixed batches and recalculate AUROC.
   This isolates the evaluation grouping intervention within this investigation.

| Capture round | Baseline | Submitted candidate | Mixed-batch candidate |
|---------------|---------:|--------------------:|----------------------:|
| Initial | 0.821989 | 0.958678 | 0.816967 |
| Reserve | 0.835422 | 0.969342 | 0.832839 |

The initial apparent lift is +0.136689 AUROC; the deployment-matched change is
-0.005022. The reserve round repeats the failure: +0.133920 becomes -0.002583.
Source values are in `results.json`, under `leaky`.

The initial label intervention in `controls.json` changes the supplied grouping
labels while holding image content fixed and changes some scores by 2.522597.
This is a code-path sensitivity diagnostic, not a change in the evaluation truth
used to calculate a reported deployment metric. Equal-batch-size runs retain the
failure pattern; batch size alone does not explain the contrast.

## A useful initial hypothesis and test

Hypothesis 1: group centering corrects a nuisance shift that deployment batches share.
Hypothesis 2: the evaluation loader supplies useful grouping absent from the service.
Propose the fixed-image mixed-batch intervention before seeing its result. State that
a surviving gain would justify further validation, whereas its disappearance would
block the current extension and motivate a corrected evaluation.

An equivalent direct code dependency analysis, or a carefully designed label
intervention combined with a deployment argument, can be informative. A label
intervention alone is insufficient to establish the magnitude of deployable gain.

## Acceptable alternatives and limits

- A refusal justified by the information mismatch can be defensible before running
  the mixed test; explain what the missing test prevents you from concluding.
- A deferral for a small corrective experiment is defensible. Specify the test and
  spending limit; do not approve 40 hours merely because the preliminary AUROC is high.
- A newly proposed per-image or differently grouped correction is a new method. If
  measured validly, its evidence may support another decision. It does not retroactively
  validate this submitted evaluation.
- Do not require the exact phrase "data leakage". Require an evidence-backed account
  of how unavailable information enters scoring and what the diagnostic distinguishes.
- Synthetic capture shifts are deliberately confounded with collection/familiarity.
  These are teaching measurements, not estimates for real images or real camera fleets.
