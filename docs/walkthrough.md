# A worked example of the Judgment Reserve

**Contains both resolutions.** This page is for readers evaluating the idea, not
for researchers beginning an unspoiled attempt. Automated feedback uses a
provisional reference, not yet expert-validated; the numerical results are reproduced.

A research team has more promising experimental results than senior scientists can
closely review. The essay proposes using resolved investigations to develop more
people able to decide what those results justify. This repository demonstrates the
practice and feedback step, and records the additional human effort to prepare it.
It does not implement the later grant of decision authority.

## The decision

A researcher receives a request for 40 additional compute-hours to investigate an
unfamiliar-image detector. They can authorize a bounded 4-hour follow-up; the full
request requires senior approval. These are illustrative spending constraints.

They receive the proposal, service contract, dataset, preliminary metrics, and
working evaluation code. Before AI advice they save competing explanations, a
distinguishing test, and how outcomes would change spending. Their own coding agent
then helps investigate. It has the same evidence and no answer key. Finally the
researcher submits their workings and a decision.

## Two impressive results

AUROC measures how well the novelty scores rank unfamiliar images above familiar
ones. Higher is better. These are measured values from the preserved seed, not
claimed results from the cited paper.

| Investigation | Initial baseline | Submitted candidate | Initial lift |
|---------------|-----------------:|--------------------:|-------------:|
| Case 01 | 0.821989 | 0.958678 | +0.136689 |
| Case 02 | 0.837933 | 0.958422 | +0.120489 |

Both improvements look substantive. A good decision requires understanding what
information produced them and whether the proposed service has that information.

## Case 01: what supplied the useful grouping?

The evaluation loader groups images by their true familiar/unfamiliar status.
The candidate estimates and removes a brightness shift separately within those
groups. The archive also associates familiarity with different capture campaigns.
Consequently, information in the evaluator's labels affects predictions indirectly
through group statistics.

The proposed deployment supplies arbitrary mixed batches without those labels or
collection identifiers. A useful test holds the images and detector fixed and
replaces the label-conditioned groups with label-blind mixed batches.

| Round | Baseline | Label-separated candidate | Mixed-batch candidate |
|-------|---------:|--------------------------:|----------------------:|
| Initial | 0.821989 | 0.958678 | 0.816967 |
| Reserve | 0.835422 | 0.969342 | 0.832839 |

In these recorded runs, the apparent gain disappears. Other label-blind grouping
seeds can leave a smaller positive reserve gain; the conclusion concerns the large
advertised improvement under the proposed service conditions, not a claim that
every correction must produce zero gain. The draft reference decision is to decline the
requested scale-up, or defer it pending a corrected method and evaluation.
Commissioning the cheap diagnostic was justified. Declining every possible future
normalization method would go beyond the evidence.

## Case 02: when group context is legitimate

The service supplies complete unlabeled camera sessions before predictions are
required. Session identifiers come from capture, independently of familiarity,
and images in a session share an illumination condition. The loader uses those
identifiers; it does not read evaluation labels when constructing groups.

The right test preserves this deployment interface and evaluates distinct reserved
images and sessions. The result is **0.887182 → 0.968791**, a lift of **0.081610**.
Mixing unrelated sessions would discard context available to this service.

The draft reference supports a bounded 4-hour extension to examine additional
capture conditions, with a stated stop criterion. It does not support unconditional
40-hour spending or prove real-camera generalization. A justified deferral for an
important remaining uncertainty may also be defensible.

## One decisive assumption, stated precisely

**Is the group context used for normalization legitimately available before prediction?**

The supplied seed's two investigations also differ in capture generation and batch
size. They are not a laboratory comparison where literally one numeric variable
changes. We preserve that fact rather than making a stronger causal claim.

Three controls make the intended lesson testable:

1. On the same images, changing the evaluation labels changes case 01 scores and
   leaves case 02 predictions unchanged.
2. Equalizing batch sizes to 32 or 128 preserves the different outcomes.
3. A strict **decision counterfactual** keeps case 02's images, method, and measured
   AUROC fixed, but changes the service to immediate individual predictions without
   complete-session context. The same evidence would then fail to establish a
   deployable improvement, changing the justified decision to deferral and further
   testing. This is a contract counterfactual, not a newly measured experiment.

All numbers and controls are available in [results](../reference/results.json) and
[controls](../reference/controls.json). Detailed workings are in the draft
[case 01](../reference/case-01.md) and [case 02](../reference/case-02.md) resolutions.

## What the system compares

After both submissions, a separate evaluator gets the participant's record and
the versioned reference guide. It considers hypotheses, test discrimination,
interpretation, uncertainty, justified spending, and the distinction between
initial human reasoning and subsequent assistant contributions. Feedback must
cite saved evidence. It can accept a decision different from the reference's
preferred decision if the workings support it.

Choosing and directing an informative test earns human credit even when the
assistant implements it. The evaluator assesses the human's interpretation
separately. Learning from the first assisted investigation is intended preparation
for the second; independence concerns the initial note before assistance within
each case. Feedback distinguishes missing evidence from contradicted claims and
does not assign an overall pass/fail judgment about the person.

The reference's provisional status appears once as a short provenance note.
Running the demonstration does not require human approval of individual feedback.

An evidence-backed challenge is preserved for human review. No learner's original
submission is overwritten to make the outcome look better. The system does not
automatically promote a researcher or grant spending authority.

## What this demonstrates, and what remains to measure

The prototype makes the evidence, reasoning record, assistant boundary, feedback
process, and preparation-cost accounting concrete. Its source case construction
is simulated. The author estimates 60–90 active minutes specifying the pair,
checking evidence, and reviewing/correcting its assessment guide, plus 40–60
minutes on the reusable framework and 20–30 minutes reviewing development feedback.
These are retrospective ranges for the listed activities. See the
[preparation-cost account](../README.md#expert-preparation-cost). The reference
remains provisional; recording effort does not establish expert validation.

The proposed organizational benefit is that repeated use could distribute the
ability to make sound decisions while saving scarce senior attention. Establishing
that benefit requires unfamiliar unaided assessments, live decision-quality
measurement, and a comparison with equally resourced mentoring. One runnable
case pair establishes none of those outcomes by itself.
