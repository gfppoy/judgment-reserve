# Judgment Reserve

**Practice a research decision with your own AI assistant, then get feedback on
your reasoning.** Two small image-detection investigations report promising
results. Inspect the evidence, test competing explanations, and decide whether
the work merits more compute. A separate evaluator compares your workings with
the reference diagnoses after you submit both decisions.

This proof of concept accompanies *The Judgment Reserve*: turning resolved
investigations into practice for developing human judgment. For a quick explanation
without installing anything, read the [worked example](docs/walkthrough.md)
**(contains answers)**. To attempt the cases unspoiled, use the instructions below
without reading that page or `reference/`.

**Status:** automated feedback against a provisional reference; not yet
expert-validated. The author estimates **60–90 active minutes** specifying the pair,
checking its evidence, and reviewing/correcting its guide; framework work and
feedback review are reported separately ([cost details](#expert-preparation-cost)).
This prototype demonstrates a workflow; it does not establish improved judgment
or organizational savings.

## Run the practice pair

**Your task is to review a request for 40 more compute-hours.** A team reports an
improved unfamiliar-image detector. Review its evidence and decide what further
work is justified: a bounded follow-up, deferral, refusal, or escalation. You may
authorize up to **4 hours**; larger commitments need senior approval. These are
simulated research-spending decisions.

For each case, the order is:

**Explore independently → record your initial view → investigate with your
assistant → submit your decision.** Independent exploration can include reading,
running, editing, and testing the working code. After both cases, a separate
evaluator compares your reasoning and evidence with the reference diagnoses.

**Your chosen agent powers both roles.** Codex or Claude Code first acts as your
research assistant, then as the system evaluator in a separate session. The
launcher controls which files each role receives:

| Role | Available files | When it runs |
|------|-----------------|--------------|
| Practice assistant | One case's evidence, working code, experiments, and your initial note; no reference diagnosis | `./reserve assist case-01`, after you commit the initial note |
| System evaluator | Both submitted answers and workings, original evidence, reference diagnoses, and assessment guide | `./reserve evaluate`, after both final submissions |

### 1. Build the sandbox and sign in once

You need **Python 3.12+**, a running **Docker or Podman** engine, and an account
for your chosen agent. Use Linux, macOS, or Windows through WSL2.

```bash
git clone https://github.com/gfppoy/judgment-reserve.git
cd judgment-reserve
./reserve setup
```

**`./reserve setup` builds the Docker or Podman sandbox**, including the Codex and
Claude Code CLIs and Python/NumPy. The image contains no cases or diagnoses.
Keep Docker or Podman running while you practice. The launcher starts and stops
the appropriate container for each `login`, `shell`, `assist`, or `evaluate`
command; you do not need to start a container manually.

Run **one** login command and follow its instructions:

| Your agent | Run this command |
|------------|------------------|
| Codex | `./reserve login codex` |
| Claude Code | `./reserve login claude` |

Login uses a separate container with an empty workspace. The launcher remembers
your choice and uses your account for both assistant and evaluator sessions.
**Every practice command below is identical for both agents.** Each agent launch
receives the appropriate workspace, role instructions, and opening task message.
Your provider's normal subscription limits or API charges apply. Codex device
login may require enabling it in your account/workspace settings.

After successful login, you return to your terminal. Create a new attempt:

```bash
./reserve start
```

Already have an attempt? Run `./reserve next` instead. It shows your selected
agent, current stage, and exact next commands. `start` always creates another
attempt. It prepares your local files; no AI agent is running yet. Keep running
`./reserve` commands from the repository directory, and use `assist` or `evaluate`
to launch the agent. Opening Codex or Claude directly in this directory would
give it access to the reference answers.

### 2. Explore the case yourself

In your terminal:

```bash
./reserve read case-01
```

This prints the proposal (`request.md`), intended service conditions
(`deployment.md`), and reported baseline/candidate results (`preliminary.json`).
Determine what is being claimed and what decision is requested.

Then read the research implementation:

```bash
./reserve read case-01 code
```

| File | What to understand |
|------|--------------------|
| `run.py` | How the experiment loads data, invokes the method, and calculates the reported result |
| `loader.py` | How the inputs are arranged for the evaluation |
| `detector.py` | What the baseline scoring and candidate preprocessing compute, and how AUROC is calculated |
| The case's `README.md` and `data/` | The data format, image arrays, reference examples, and experiment commands |

Read any one of these text files with, for example,
`./reserve read case-01 detector.py` or `./reserve read case-01 README.md`.
The files you are reviewing are the supplied research prototype. Your first
view can be provisional; note uncertainties to investigate with your assistant.

**You may run and edit the code before writing your initial note.** Do as much
independent investigation as you find useful; experiments are optional. Keep AI
assistance off until you have recorded that note. This applies equally to Codex
and Claude Code.

To run the supplied experiment, open an offline shell from your repository terminal:

```bash
./reserve shell case-01
```

Inside that shell, you are already in the working case folder (`/workspace`), with
Python and NumPy installed. Type:

```bash
python run.py
exit
```

`exit` returns you to your repository terminal. There, edit any working Python
file, or create a separate experiment:

```bash
./reserve edit case-01 investigation.py
```

Use `run.py`, `loader.py`, or `detector.py` instead of `investigation.py` to edit
those files. Save and close the editor. Reopen `./reserve shell case-01` to run
your changes; inside it, use `python run.py` or, for your new script,
`python investigation.py | tee results.txt`. Type `exit` when finished.

Code edits and saved outputs persist in the case workspace and will be available
to your assistant later. Save the scripts and results you will cite in your
reasoning, using descriptive filenames. These working files can be edited
throughout the investigation. Original evidence is preserved separately. Keep
the supplied data, proposal, deployment notes, and preliminary report intact
throughout both independent and assisted work.

### 3. Write your own initial view

Open the answer template:

```bash
./reserve edit case-01 initial
```

Write short answers to the three prompts already in the file:

1. **Explanations:** what could account for the reported improvement?
2. **Test:** what have you tested, or would you test? What changes, controls, and outcomes distinguish the explanations?
3. **Spending:** what further work would each outcome justify?

Replace each `[write here]`, save, and close the editor. In nano: **Ctrl+O,
Enter** saves; **Ctrl+X** exits. The launcher respects your `VISUAL`/`EDITOR`
setting and otherwise uses nano or vi, printing the relevant instructions.

Include any independent experiments and saved results, distinguishing observations
from planned tests. You can close the draft, explore further, and reopen it.
Opening `edit` does not end independent exploration.

When ready, record your saved note before AI advice:

```bash
./reserve initial case-01
```

Saving in the editor updates your draft. `initial` commits that note as the record
of your reasoning before AI advice; it cannot then be revised. The assistant
becomes available after this step; launch it with the command below.

### 4. Investigate with your chosen assistant

```bash
./reserve assist case-01
```

This launches **Codex or Claude Code inside the practice sandbox**, using the
choice you made at login. Only this case's working folder and its dedicated agent
state are mounted. The agent receives your initial note as `INITIAL.md`, your
working files, and an opening task automatically. The repository's `reference/`,
judge walkthrough, other case, and evaluator files are not mounted. You now type
requests into the agent's chat.

**Continue from your independent work.** Any code edits, `investigation.py`, and
saved results from step 2 are already in this workspace. Review those findings
with your assistant, ask about unclear parts of `run.py`, `loader.py`, or
`detector.py`, and choose tests for the remaining questions. If you have not run
any experiments yet, you can start now. A useful first request is:

> Read INITIAL.md and any experiments and results I have saved. Help me choose
> the next test for my remaining questions. Save its code and results, and
> explain what they establish.

You and your assistant can extend existing scripts or add new experiments.
Save further results under distinct, descriptive filenames so earlier
observations remain available. Keep `INITIAL.md` unchanged as the record of
your earlier reasoning.

Ask follow-up questions and choose further tests as needed. When you have enough
evidence to decide, exit the agent and return to your terminal.

### 5. Write and submit your decision

```bash
./reserve edit case-01 final
```

Complete the four prompts in the template:

1. **Decision:** your action and spending limit.
2. **Workings:** cite the code, tests, saved output files, and numerical results supporting it; explain what changed.
3. **Uncertainty:** what remains unresolved, how your view changed, and where the assistant helped.
4. **Reversal:** what evidence or changed condition would change your decision.

Save and close the editor, then submit:

```bash
./reserve submit case-01
```

The launcher now prints the same sequence for **case 02**, with its exact
commands and answer files. Follow those instructions through its final submission.
Use `./reserve next` whenever you return or lose your place. Both cases belong to
the same attempt. Apply what you learned from case 01, including your assistant's
explanations, to case 02. Save a fresh initial view before assistance on that case;
learning from the earlier case is intended and does not count against independence.

### 6. Get the system evaluation

After both submissions:

```bash
./reserve evaluate
```

The launcher starts your chosen **Codex or Claude Code as the system evaluator
in a separate container and agent context**. It receives a prepared bundle of
your initial notes, investigation records, final decisions, original evidence,
reference diagnoses, and assessment guide. The assistant's agent state is not
reused. This command remains blocked until both final submissions are recorded.

The launcher supplies the comparison task automatically; your agent reads the
bundle and writes the evaluation. Let it save `feedback.md`, then exit and run
`./reserve next` for the command to read it.

Feedback begins with whether your decisions are defensible, then assesses the
reasoning demonstrated by your saved work. It addresses hypotheses, tests,
interpretation, uncertainty, spending, and revision. Choosing and directing a
useful test earns credit even when your assistant implements it; your own
interpretation of its findings is assessed separately. Defensible alternative
decisions receive credit. Missing evidence is distinguished from a contradicted
claim, and there is no overall pass/fail judgment about the person.

The feedback includes one short provenance note: **"Automated feedback against a
provisional reference; not yet expert-validated."** This describes the reference's
status. No human approval is needed to receive or use the demonstration feedback.
An actual review of the reference can be recorded separately. Exported evaluations
retain their original reference version; updates to this repository do not rewrite
an existing attempt's feedback or submitted record.

### Where to type, and where your work is saved

| What you are doing | Where you type |
|-------------------|----------------|
| Reading files, opening a form, launching an agent, or submitting | Your terminal, using `./reserve ...` |
| Writing your initial reasoning or final decision | The text editor opened by `./reserve edit ...` |
| Editing working Python files independently | The text editor opened by e.g. `./reserve edit case-01 detector.py` |
| Running Python yourself, before or after your initial note | The offline shell opened by `./reserve shell ...`; type `exit` before using `./reserve` again |
| Asking questions, directing tests, or discussing results | The Codex or Claude Code chat opened by `./reserve assist ...` |

`read` and `edit` locate your current session automatically. Your files remain
available for inspection in your own editor:

```text
.reserve/sessions/practice-<your-session-id>/
  work/case-01/                 Working evidence, code, and experiments
  work/case-02/                 Working evidence, code, and experiments
  responses/
    case-01-initial.md          Your initial note
    case-01-final.md            Your final decision
    case-02-initial.md          Your initial note
    case-02-final.md            Your final decision
  evaluation/feedback.md       Feedback after both submissions
```

`.reserve` may be hidden in your file browser; `edit` prints the full file
path. To change agents, sign in with the other login command. An explicit
`--agent codex` or `--agent claude` on `assist`, `evaluate`, or `next` also changes
the remembered choice; you need that provider's login or API credentials.

`./reserve status` shows your record; `./reserve shell case-01` opens an offline
terminal; `./reserve challenge your-challenge.md` preserves an evidence-backed
disagreement. `./reserve export-evaluation` exports the completed
evaluator bundle without launching an agent. Session commands accept
`--session practice-…` to select an older attempt.

## How the roles stay separate

The `sandbox/` directory supplies the container image, agent configuration, and
network restrictions used by the launcher. Docker or Podman enforces file access:
the assistant container receives the practice workspace; the evaluator container
receives the evaluation bundle. Role prompts describe the task within that boundary.

Neither container receives the full repository, Git history, normal host home,
or container-engine socket. Only dedicated login files are reused between the
separate agent homes. The evaluator receives saved investigation work and terminal
logs as assessment evidence, while starting with its own native agent state.

An internal network and provider-only HTTPS proxy block ordinary retrieval of the
public answers; native web tools are disabled. Failed isolation setup stops the
launch. This protects the supported practice workflow, but cannot erase prior model
knowledge or prevent a host owner from bypassing it. Each run has two CPU cores,
2 GB memory, and a 30-minute limit. The case's proposed compute spending is simulated.

Committed initial notes and submitted snapshots are stored outside the assistant's
workspace; the assistant receives a copy of the initial note. Changes to the
committed records are detected by hashes. Keep `.reserve/` private: it
contains credentials, transcripts, and personal work. Development checks verified
role isolation on Linux/Podman and Linux/Docker. Feedback reliability still needs human
calibration; other host platforms have not been verified.

## Expert preparation cost

The author supplied these **retrospective estimates of active attention**, including
reading, thinking, substantive instructions, and checking changes. The unit is the
**case pair**, including development of the legitimate contrast.

| Activity | Scope | Estimated active minutes |
|----------|-------|-------------------------:|
| Specifying the cases and intended judgments | Case pair, including the contrast | 20–30 |
| Checking the scientific evidence | Case pair | 10–20 |
| Reviewing and correcting the assessment guide | Pair's assessment guide | 30–40 |
| Setting up, debugging, and checking the workflow | Reusable framework | 40–60 |
| Reviewing generated feedback | Development self-test feedback | 20–30 |

**Specifying the pair, checking its evidence, and working on the guide: 60–90
minutes. All listed activities: 120–180 minutes (2–3 hours).** These sums treat the
guide estimate as additional to the separately reported feedback-review estimate.
The ranges express recollection, not statistical confidence intervals. Some guide
improvements may also be reusable; no finer allocation was reported.

The [attention log](expert/time-log.jsonl) preserves the original approximately
180-minute combined estimate and supersedes it with this breakdown, so it is not
counted twice. Scope, affected artifacts, and outcomes are described in each
entry's notes. The version identifies the material at reporting time; the estimates
span development and review across revisions. No midpoint, exact per-case split,
or unreported remainder is inferred. Run `./reserve expert-summary` for the ranges.

This is a partial account of reported activities by an author familiar with the
material, not a complete cost study or an independent expert review. It measures
human attention, excluding unattended agent runtime. Feedback was reviewed during
prototype development, not a learner study. The figures do not establish a typical
recurring preparation cost, saved senior time, or improved judgment.

## Verify the supplied cases

This repository contains the prepared cases and the code needed to practice,
evaluate, and verify them. Case-generation scripts and authoring templates are
maintained separately. The supplied data, case code, reference results, and
construction metadata let you inspect the practice pair without rebuilding it.

After completing the practice, you can check the supplied files and reproduce the
submitted scores. With [uv](https://docs.astral.sh/uv/) installed:

```bash
uv sync --locked
./reserve check
uv run python -B cases/case-01/run.py
uv run python -B cases/case-01/run.py --split reserve
uv run python -B cases/case-02/run.py
uv run python -B cases/case-02/run.py --split reserve
```

`check` verifies the supplied case files against their recorded hashes. The four
experiment commands recalculate the submitted initial and reserve scores. Further
grouping interventions can use the same supplied code and data. The public GitHub
workflow checks file integrity and builds the sandbox. Changing case or reference
content invalidates approval of the previous version. The sandbox image is rebuilt
when its source changes.

## Sources

These are teaching reconstructions inspired by
[Miyai et al. (2025), §7.2](https://arxiv.org/html/2511.04583v1#S7.SS2), not the
paper's original experiments. They use 8×8 digit images with simulated brightness
shifts. Images: Alpaydin & Kaynak (1998), *UCI Optical Recognition of Handwritten
Digits*, [DOI: 10.24432/C50P49](https://doi.org/10.24432/C50P49),
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), accessed through
`sklearn.datasets.load_digits`; splits, grouping, and brightness conditions are modified.
