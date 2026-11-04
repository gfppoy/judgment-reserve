"""Checkout-oriented CLI; practice orchestration uses only the Python stdlib."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from . import ledger, session
from .util import ROOT, CASE_IDS, manifest, now, read_json, review_version, sha256, write_json


READING_GROUPS = {
    "brief": ("request.md", "deployment.md", "preliminary.json"),
    "code": ("run.py", "loader.py", "detector.py"),
}
READABLE_FILES = ("README.md", *READING_GROUPS["brief"], *READING_GROUPS["code"])
EDITABLE_CODE = (*READING_GROUPS["code"], "investigation.py")


def output(value):
    print(json.dumps(value, indent=2, sort_keys=True))


def parser():
    p = argparse.ArgumentParser(description="Judgment Reserve — investigate, decide, then compare.")
    commands = p.add_subparsers(dest="command", required=True)
    for name, help_text in (("start", "Create a new practice attempt and show the first step"),
                            ("next", "Show exactly what to read, edit, or run next"),
                            ("status", "Show the current practice record"),
                            ("setup", "Build the isolated environment"),
                            ("check", "Check supplied case files against their recorded hashes"),
                            ("expert-summary", "Show reported human preparation effort")):
        item = commands.add_parser(name, help=help_text)
        if name in ("status", "next"):
            item.add_argument("--session")
        if name in ("start", "next"):
            item.add_argument("--agent", choices=["codex", "claude"])
    login = commands.add_parser("login", help="Sign in to your unmodified agent CLI in a dedicated container")
    login.add_argument("agent", choices=["codex", "claude"])
    reader = commands.add_parser("read", help="Read the case brief, supplied code, or a named evidence file")
    reader.add_argument("case", choices=CASE_IDS)
    reader.add_argument("section", nargs="?", default="brief", choices=[*READING_GROUPS, *READABLE_FILES])
    reader.add_argument("--session")
    editor = commands.add_parser("edit", help="Open an answer or working Python file in a text editor")
    editor.add_argument("case", choices=CASE_IDS)
    editor.add_argument("part", choices=["initial", "final", *EDITABLE_CODE])
    editor.add_argument("--session")
    for name in ("initial", "submit", "assist", "shell"):
        item = commands.add_parser(name)
        item.add_argument("case", choices=CASE_IDS)
        item.add_argument("--session")
        if name in ("initial", "submit"):
            item.add_argument("--file", type=Path)
        if name == "assist":
            item.add_argument("--agent", choices=["codex", "claude"],
                              help="Override the agent selected at login")
    for name in ("evaluate", "export-evaluation"):
        item = commands.add_parser(name)
        item.add_argument("--session")
        item.add_argument("--draft-guide", action="store_true",
                          help="Explicitly preview an unapproved reference guide")
        if name == "evaluate":
            item.add_argument("--agent", choices=["codex", "claude"],
                              help="Override the agent selected at login")
    item = commands.add_parser("challenge")
    item.add_argument("file", type=Path)
    item.add_argument("--session")
    item = commands.add_parser("expert-log", help="Record a human's reported active minutes; never infer durations")
    item.add_argument("--activity", required=True)
    item.add_argument("--category", choices=ledger.CATEGORIES, required=True)
    item.add_argument("--reviewer", required=True, help="Actual role, e.g. 'gfppoy, author-reviewer'")
    item.add_argument("--minutes", type=float)
    item.add_argument("--method", choices=["timed", "estimated", "missing"], required=True)
    item.add_argument("--notes", default="")
    item.add_argument("--replaces")
    item.add_argument("--review-session", default="review-1")
    item.add_argument("--round", type=int, default=1)
    item.add_argument("--artifact-version", help="Hash of the version actually reviewed; defaults to current version")
    item = commands.add_parser("approve-guide", help="Record an actual human approval of the current pair and guide")
    item.add_argument("--reviewer", required=True)
    item.add_argument("--minutes", required=True, type=float)
    item.add_argument("--method", choices=["timed", "estimated"], required=True)
    item.add_argument("--confirm-reviewed", action="store_true", required=True,
                      help="Confirm you actually reviewed both diagnoses, evidence, and guide")
    return p


def preferred_agent(root: Path = ROOT):
    file = root / ".reserve/preferred-agent"
    provider = file.read_text().strip() if file.exists() else "codex"
    return provider if provider in ("codex", "claude") else "codex"


def session_command(path: Path, name: str, *args: str):
    return shlex.join(["./reserve", name, *args, "--session", path.name])


def read_case(path: Path, case: str, section: str):
    names = READING_GROUPS.get(section, (section,))
    if any(name not in READABLE_FILES for name in names):
        raise ValueError("Choose brief, code, or a named case evidence file")
    work = path / "work" / case
    manifest(work)
    for name in names:
        print(f"\n[{name}]\n")
        print((work / name).read_text())
    entry = read_json(path / "record.json")["cases"][case]
    if not entry["initial"] and section == "brief":
        print("Next: inspect the supplied implementation (run.py, loader.py, detector.py):")
        print("  " + session_command(path, "read", case, "code"))
    elif not entry["initial"] and section == "code":
        show_independent_work(path, case)
        print("\nWhen ready, record what you found, your explanations, and any further tests:")
        print("  " + session_command(path, "edit", case, "initial"))
    else:
        print("Continue your current stage:")
        print("  " + session_command(path, "next"))


def show_independent_work(path: Path, case: str):
    print("\nBefore your initial note, you may read, run, edit, and test the code yourself.")
    print("AI advice begins only after you record that note; independent experiments are optional.")
    print("From your repository terminal, open the offline case shell (Python/NumPy installed):")
    print("  " + session_command(path, "shell", case))
    print("Inside that shell, run: python run.py")
    print("You are in /workspace, the working case folder. Type exit to return here.")
    print("Back here, edit working code or create an experiment in your text editor:")
    print("  " + session_command(path, "edit", case, "investigation.py"))
    print("Use run.py, loader.py, or detector.py instead to edit those working files.")
    print("Reopen the shell to run your script, e.g. python investigation.py | tee results.txt.")
    print("Changes and outputs persist for your later assistant. Original evidence is preserved.")
    print("Keep the supplied data, proposal, deployment notes, and preliminary report intact.")


def edit_response(path: Path, case: str, part: str):
    is_code = part in EDITABLE_CODE
    if part not in ("initial", "final") and not is_code:
        raise ValueError("Choose initial, final, or a named working Python file")
    with session.locked(path):
        record = read_json(path / "record.json")
        session.validate_record(path, record)
        entry = record["cases"][case]
        if entry["submission"]:
            raise ValueError("This case is submitted. Use ./reserve challenge to record a revision.")
        if part == "initial" and entry["initial"]:
            raise ValueError("Your initial reasoning is already committed. Continue with the assistant, then edit final.")
        if part == "final" and not entry["initial"]:
            raise ValueError("Record your initial reasoning with ./reserve initial before writing the final decision.")
        if is_code:
            work = path / "work" / case
            manifest(work)
            file = work / part
            if part == "investigation.py":
                file.touch(exist_ok=True)
        else:
            file = path / "responses" / f"{case}-{part}.md"
        if file.is_symlink() or not file.is_file():
            raise ValueError("The selected file must be a regular file inside your session")
        selected = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        if selected:
            editor = shlex.split(selected)
        else:
            editor = [name for name in ("nano", "vi") if shutil.which(name)][:1]
        if not editor:
            raise ValueError(f"Set VISUAL or EDITOR to a text editor, or open this file yourself: {file}")
        if is_code:
            print(f"Opening working code: {file}")
            print("Edit this copy yourself; the original evidence is preserved separately.")
            if not entry["initial"]:
                print("Keep AI assistance off until you have recorded your initial reasoning.")
            print("Save and close the editor to return.")
        else:
            print(f"Opening your {part} answer: {file}")
            print("Write under the headings and replace each [write here]. Save and close the editor to return.")
            if part == "initial":
                print("You may still close this draft and explore independently before recording it.")
                print("Include what you already ran, changed, and observed, alongside any planned tests.")
        if Path(editor[0]).name == "nano":
            print("In nano: Ctrl+O, Enter to save; Ctrl+X to exit.")
        elif Path(editor[0]).name in ("vi", "vim", "nvim"):
            print("In vi: press i to edit; Esc, then :wq and Enter to save and exit.")
        sys.stdout.flush()
        subprocess.run([*editor, str(file)], check=True)
    if is_code:
        print("Run your working code in the offline case shell:")
        print("  " + session_command(path, "shell", case))
        print("Inside the shell: python " + (part if part == "investigation.py" else "run.py"))
        print("Type exit to return to your repository terminal. Your initial note is unchanged.")
        return
    action = "initial" if part == "initial" else "submit"
    print("When your answers are saved and ready, record them with:")
    print("  " + session_command(path, action, case))


def show_next(path: Path, provider: str | None = None, root: Path = ROOT):
    """Describe the next human action without editing answers or launching a model."""
    provider = provider or preferred_agent(root)
    record = read_json(path / "record.json")

    def command(name, *args):
        return session_command(path, name, *args)

    print(f"\nPractice session: {path.name}")
    print("Selected agent: " + ("Claude Code" if provider == "claude" else "Codex"))
    print("To show your current step again: " + command("next"))
    for case in CASE_IDS:
        entry = record["cases"][case]
        if entry["submission"]:
            continue
        work = path / "work" / case
        if not entry["initial"]:
            print(f"\n{case}: review a research compute request")
            print("A team reports an improvement in detecting unfamiliar images and requests")
            print("40 more compute-hours. Decide what further work the evidence justifies.")
            print("You can authorize up to 4 hours; a larger commitment needs senior approval.")
            print("These compute-hours describe a simulated funding decision.")
            print("Your decision may be a bounded follow-up, deferral, refusal, or escalation.")
            print("The supplied Python files are the research prototype you are reviewing.")
            print("\nOrder of work:")
            print("  1. YOU: read, optionally run/edit/test code yourself, then record your initial reasoning.")
            print(f"  2. YOU + {provider.upper()}: inspect the implementation, run your chosen tests, discuss results.")
            print("  3. YOU: write your final spending decision with workings, evidence, and uncertainty.")
            print("  4. After both cases: a separate evaluator compares your record with the reference guide.")
            print("\nYou are at step 1. Start with the proposal and its reported evidence:")
            print("  request.md        What is being requested and your spending authority")
            print("  deployment.md     The intended service interface and capture record")
            print("  preliminary.json  The reported baseline and candidate AUROC (higher is better)")
            print("  " + command("read", case))
            print("\nThen inspect the supplied implementation:")
            print("  run.py            Loads data, calls the method, and reports evaluation scores")
            print("  loader.py         Prepares the groups used by the evaluation")
            print("  detector.py       Implements the scoring, preprocessing, and AUROC calculation")
            print("  " + command("read", case, "code"))
            print("README.md in the case folder describes the dataset and experiment commands.")
            print(f"All of these evidence files are in: {work}")
            show_independent_work(path, case)
            print("\nWrite a provisional note before AI advice:")
            print("  - What competing explanations could account for the reported result?")
            print("  - What test would distinguish them, and what outcomes do you expect?")
            print("  - How would those outcomes change your spending decision?")
            print("Record what is unclear as well. You will investigate further with your assistant.")
            print("Include any independent code changes, tests, and results; separate findings from plans.")
            print("The answer template repeats these questions; brief bullets are enough.")
            print("Open your answer template in a text editor:")
            print("  " + command("edit", case, "initial"))
            print("Save and close the editor, then record the note:")
            print("  " + command("initial", case))
            print(f"The next step opens {provider} for an interactive investigation with you.")
            print(f"One-time setup is ./reserve setup and ./reserve login {provider}.")
            print("The launcher supplies the case files, your note, and the assistant's role automatically.")
        else:
            assist = command("assist", case)
            completed = any(event["role"] == "assistant" and event.get("finished")
                            and event["exit_code"] == 0 for event in entry["assistant_runs"])
            if not completed:
                print(f"\n{case}, step 2: investigate with your assistant")
                print("Your provisional reasoning is saved. Now work with the agent to understand")
                print("the code, run the tests you choose, and assess what the results justify.")
                print(f"If you have not signed in here yet, first run ./reserve login {provider}.")
                print("This command opens your agent's interactive chat inside the case workspace:")
                print("  " + assist)
                print("The launcher supplies your account login, the case files, your INITIAL.md,")
                print("and the assistant instructions. The reference diagnosis is withheld.")
                print("\nBoth agents receive the opening task automatically. Continue in their chat.")
                print("Review run.py -> loader.py -> detector.py with the agent. You can ask it to:")
                print("  - Explain the implementation and reproduce the submitted calculation.")
                print("  - Run the test from your initial note, then any follow-up tests you choose.")
                print("  - Save experiments in investigation.py and observations in results.json.")
                print("It can edit the working Python files; your original evidence is preserved.")
                print("Record what changed and cite the saved outputs in your final answer.")
                print("For example, tell it: 'Run the test in INITIAL.md and save the code and results.'")
                print("When you have enough evidence for a decision,")
                print("exit the agent to return here; you will write your final decision yourself.")
            else:
                print(f"\n{case}, step 3: make your decision")
                print("Write the spending action and limit you recommend, the tests and saved results")
                print("supporting it, remaining uncertainty, and what would change your decision.")
                print("Cite the code and outputs in the case workspace. Write this answer yourself:")
                print("  " + command("edit", case, "final"))
                print("Save and close the editor, then submit your decision and evidence:")
                print("  " + command("submit", case))
                print("To investigate further before submitting:")
                print("  " + assist)
        return

    feedback = path / "evaluation/feedback.md"
    if record["evaluation"] and feedback.is_file():
        print("Both cases are submitted. Read your evaluator's feedback:")
        print("  " + shlex.join(["cat", str(feedback)]))
        print("You can record a disagreement with ./reserve challenge YOUR_FILE.md --session " + path.name)
        return
    if record["evaluation"]:
        approved = record["evaluation"]["human_approved"]
    else:
        status = read_json(root / "reference/approval.json")
        approved = status["status"] == "approved" and status["review_version"] == review_version(root)
    flags = [] if approved else ["--draft-guide"]
    print("\nStep 4: get feedback on both decisions")
    print("This opens a fresh agent context with your initial notes, investigation record,")
    print("final decisions, and the reference diagnoses. It evaluates the reasoning and")
    print("evidence behind your spending decisions, including defensible alternatives.")
    print("The launcher configures this evaluator role using your same provider account:")
    print("  " + command("evaluate", *flags))
    if not approved:
        print("--draft-guide acknowledges that this guide still awaits human approval.")


def evaluation(path, allow_draft):
    record = read_json(path / "record.json")
    if not record["evaluation"]:
        return session.export_evaluation(path, root=ROOT, allow_draft=allow_draft)
    if not record["evaluation"]["human_approved"] and not allow_draft:
        raise ValueError("This evaluation uses a frozen draft guide. Add --draft-guide to continue that preview.")
    session.validate_record(path, record)
    dest = path / "evaluation"
    for name, checksum in record["evaluation"]["input_manifest"].items():
        file = dest / name
        if file.is_symlink() or not file.is_file() or sha256(file) != checksum:
            raise ValueError(f"Frozen evaluation input has changed: {name}")
    return dest


def run(args):
    command = args.command
    if command == "start":
        path = session.create(root=ROOT)
        if args.agent:
            (ROOT / ".reserve/preferred-agent").write_text(args.agent + "\n")
        print(f"Created {path.name}. This begins with your own reading and written reasoning.")
        show_next(path, args.agent, root=ROOT)
        return
    if command == "check":
        source = read_json(ROOT / "reference/source-manifest.json")
        if manifest(ROOT / "cases") != source["evidence"]:
            raise ValueError("Case files differ from the source manifest")
        print("Supplied case files match their recorded hashes.")
        print("Reference version:", review_version(ROOT))
        return
    if command == "expert-summary":
        output(ledger.summary())
        return
    if command == "expert-log":
        output(ledger.log(activity=args.activity, category=args.category, reviewer=args.reviewer,
                          minutes=args.minutes, method=args.method, notes=args.notes,
                          replaces=args.replaces, session=args.review_session, round_number=args.round,
                          artifact_version=args.artifact_version))
        return
    if command == "approve-guide":
        output(ledger.approve(args.reviewer, args.minutes, args.method))
        return
    if command in ("setup", "login", "assist", "shell", "evaluate"):
        from . import sandbox
    if command == "setup":
        engine = sandbox.runtime()
        sandbox.ensure_image(engine, force=True)
        return
    if command == "login":
        home = ROOT / ".reserve/auth" / args.agent
        workspace = ROOT / ".reserve/login-empty-workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        # Login is separate and is not recorded in a practice/evaluation transcript.
        code = sandbox.run(workspace, home, args.agent, sandbox.agent_command(args.agent, "", login=True))
        if code:
            raise ValueError(f"Agent login exited with status {code}")
        (ROOT / ".reserve/preferred-agent").write_text(args.agent + "\n")
        print("\nLogin complete. Your account is connected; the practice begins separately.")
        if (ROOT / ".reserve/latest").exists():
            show_next(session.locate(None, root=ROOT), args.agent, root=ROOT)
        else:
            print("Start your first case with:")
            print("  ./reserve start")
        return
    path = session.locate(args.session, root=ROOT)
    if getattr(args, "agent", None):
        (ROOT / ".reserve/preferred-agent").write_text(args.agent + "\n")
    if command in ("assist", "evaluate"):
        args.agent = args.agent or preferred_agent(ROOT)
    if command == "status":
        output(read_json(path / "record.json"))
    elif command == "read":
        read_case(path, args.case, args.section)
    elif command == "edit":
        edit_response(path, args.case, args.part)
    elif command == "next":
        show_next(path, args.agent, root=ROOT)
    elif command == "initial":
        session.commit_initial(path, args.case, args.file)
        print("Initial reasoning committed. The assistant can now be started for this case.")
        show_next(path, root=ROOT)
    elif command == "submit":
        session.submit(path, args.case, args.file)
        print(f"{args.case}: final decision and evidence committed.")
        show_next(path, root=ROOT)
    elif command in ("assist", "shell"):
        with session.locked(path):
            record = read_json(path / "record.json")
            session.validate_record(path, record)
            entry = record["cases"][args.case]
            if entry["submission"]:
                raise ValueError("This case is submitted; its practice phase is closed")
            is_assistant = command == "assist"
            if is_assistant and not entry["initial"]:
                raise ValueError("Commit your initial reasoning before receiving assistant advice")
            provider = args.agent if is_assistant else "codex"
            work = path / "work" / args.case
            home = path / "agent-state" / args.case / (provider if is_assistant else "offline-shell")
            if is_assistant:
                sandbox.credentials(provider, home, root=ROOT)
                shutil.copyfile(path / "committed" / args.case / "initial.md", work / "INITIAL.md")
            events = entry["assistant_runs"]
            event = {"started": now(), "role": "assistant" if is_assistant else "human_shell",
                     "provider": provider if is_assistant else None, "exit_code": None}
            events.append(event)
            write_json(path / "record.json", record)
            logfile = path / "logs" / args.case / f"{len(events):02d}-{command}.log"
            try:
                cmd = sandbox.agent_command(provider, sandbox.ASSISTANT_PROMPT) if is_assistant else ["bash"]
                if not is_assistant:
                    print("Offline case shell: you are in /workspace, with Python and NumPy installed.")
                    print("Run python run.py or your own scripts. No AI assistant is running.")
                    print("Type exit to return to your repository terminal and continue with ./reserve commands.")
                    sys.stdout.flush()
                event["exit_code"] = sandbox.run(work, home, provider, cmd, log=logfile, network=is_assistant)
            finally:
                if is_assistant:
                    sandbox.save_credentials(provider, home, root=ROOT)
                event["finished"] = now()
                write_json(path / "record.json", record)
            if event["exit_code"]:
                raise ValueError(f"{command} exited with status {event['exit_code']}; its record was preserved")
        show_next(path, provider if is_assistant else None, root=ROOT)
    elif command in ("evaluate", "export-evaluation"):
        destination = evaluation(path, args.draft_guide)
        print("Evaluation workspace:", destination)
        if command == "evaluate":
            print("The evaluator receives both submissions and the reference guide.")
            print("Its opening task is supplied automatically: read EVALUATE.md and write feedback.md.")
            print("After the feedback is saved, exit the agent and run ./reserve next to read it.")
            sys.stdout.flush()
            with session.locked(path):
                home = path / "evaluator-state" / args.agent
                sandbox.credentials(args.agent, home, root=ROOT)
                prompt = "Read EVALUATE.md and perform the evaluation it specifies. Write feedback.md."
                try:
                    code = sandbox.run(destination, home, args.agent, sandbox.agent_command(args.agent, prompt),
                                       log=path / "evaluator.log")
                finally:
                    sandbox.save_credentials(args.agent, home, root=ROOT)
                evaluation(path, args.draft_guide)  # Ensure input evidence was not rewritten.
                if code:
                    raise ValueError(f"Evaluator exited with status {code}; exported inputs are preserved")
            if (destination / "feedback.md").is_file():
                show_next(path, args.agent, root=ROOT)
            else:
                print("The evaluator exited without saving feedback.md. Run the evaluation again to finish it.")
    elif command == "challenge":
        print("Recorded", session.challenge(path, args.file), "for human review; no guide was changed.")


def main():
    args = parser().parse_args()
    try:
        run(args)
    except (ValueError, FileNotFoundError, ModuleNotFoundError, subprocess.SubprocessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from None
