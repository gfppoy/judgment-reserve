# Case 01 — draft reference diagnosis

Agent-prepared reference with reproduced numerical results. The evaluation bundle's
`guide-status.json` records whether this version has received human review.

## Decision

Do not release the requested 40 compute-hours on the present evidence. A short,
deployment-relevant diagnostic is justified; the large reported gain is not
established for the documented service. Decline this scale-up or defer it pending
a corrected method and new evidence.
This does not establish that every brightness-normalization method is useless.

## Workings and evidence

1. `cases/case-01/loader.py` passes evaluation labels into `make_groups`. Images
   are partitioned into familiar and unfamiliar groups before candidate scoring.
2. `detector.py:normalize` estimates the brightness correction within each group.
   Thus evaluation truth affects a sample's prediction through its companions,
   even though `novelty_scores` does not receive labels directly.
3. `deployment.md` exposes only images at the request interface and says an upload
   can mix capture runs. Neither archive collection identifiers nor familiarity
   labels are supplied. The evaluation's grouping cannot be assumed at prediction time.
4. Hold the images, reference bank, scorer, and maximum batch size of 128 fixed.
   Replace label-conditioned grouping with label-blind mixed batches and recalculate
   AUROC. This changes group membership, the number of groups (six to five), and
   partial-group sizes. It is a useful grouping diagnostic, not a comparison with
   every batch property held fixed. Random mixing is compatible with the images-only
   interface; it does not establish the actual distribution of future arrival batches.

| Capture round | Baseline | Submitted candidate | Mixed-batch candidate |
|---------------|---------:|--------------------:|----------------------:|
| Initial | 0.821989 | 0.958678 | 0.816967 |
| Reserve | 0.835422 | 0.969342 | 0.832839 |

The initial apparent lift is +0.136689 AUROC; the mixed-batch diagnostic gives
-0.005022. In the recorded reserve run, +0.133920 becomes -0.002583.
Source values are in `results.json`, under `leaky`.
These mixed-batch values use seeds 24 and 1024. Other label-independent groupings
can give different results, including a smaller positive reserve gain. Compare the
participant's actual method and results; exact agreement with these numbers is not
required. The relevant question is what gain the deployment evidence establishes.

For a separate label-dependency check, permute the labels passed to the loader
using `np.random.default_rng(91).permutation(labels)`, while keeping the original
labels for AUROC. Images, reference bank, scoring parameters, and the full set of
group sizes remain fixed. Some initial scores change by 2.522597, as recorded in
`controls.json`. Candidate AUROC becomes 0.799200 initially and 0.826124 on reserve.
This establishes sensitivity to the labels supplied to grouping even without the
six-to-five group-count change. It is a diagnostic intervention, not a proposed
deployment method or an estimate of future performance.

These checks can be implemented using only the supplied `loader.py`, `detector.py`,
and data. The additional equal-batch-size construction checks in `controls.json`
are author validation material; they are not required evidence from a participant.

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
