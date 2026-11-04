import shlex
import sys
from unittest.mock import Mock

import pytest

from judgment_reserve import cli, ledger, sandbox, session
from judgment_reserve.util import now, read_json, write_json


REASONING = (
    "I will compare two explanations against the available evidence, choose a test "
    "that distinguishes them, and limit further spending to what its results support."
)


def instructions(capsys):
    output = capsys.readouterr().out
    commands = [cli.parser().parse_args(shlex.split(line.strip())[1:])
                for line in output.splitlines() if line.startswith("  ./reserve ")]
    return output, commands


def test_next_guides_the_human_through_each_stage_without_changing_the_record(repo, capsys):
    path = session.create(repo)
    record_file = path / "record.json"
    before = record_file.read_bytes()
    cli.show_next(path, "claude", repo)
    output, commands = instructions(capsys)
    assert record_file.read_bytes() == before
    assert "40 more compute-hours" in output and "up to 4 hours" in output
    assert "run.py" in output and "loader.py" in output and "detector.py" in output
    assert str(repo / "reference") not in output
    assert [c.command for c in commands] == ["read", "read", "shell", "edit", "edit", "initial"]
    assert commands[0].section == "brief" and commands[1].section == "code"
    assert commands[3].part == "investigation.py" and commands[4].part == "initial"
    assert all(c.case == "case-01" and c.session == path.name for c in commands)

    (path / "responses/case-01-initial.md").write_text(REASONING)
    session.commit_initial(path, "case-01")
    cli.show_next(path, "claude", repo)
    output, commands = instructions(capsys)
    assert [c.command for c in commands] == ["assist"]
    assert "Selected agent: Claude Code" in output
    assert commands[0].agent is None and commands[0].case == "case-01"

    record = read_json(record_file)
    record["cases"]["case-01"]["assistant_runs"].append({
        "role": "assistant", "provider": "claude", "started": now(),
        "finished": now(), "exit_code": 0,
    })
    write_json(record_file, record)
    cli.show_next(path, "claude", repo)
    output, commands = instructions(capsys)
    assert [c.command for c in commands] == ["edit", "submit", "assist"]
    assert commands[0].part == "final"

    (path / "responses/case-01-final.md").write_text(REASONING)
    session.submit(path, "case-01")
    cli.show_next(path, "claude", repo)
    output, commands = instructions(capsys)
    assert [c.command for c in commands] == ["read", "read", "shell", "edit", "edit", "initial"]
    assert all(c.case == "case-02" for c in commands)


@pytest.mark.parametrize("approved", [False, True])
def test_next_selects_evaluation_only_after_both_submissions(repo, capsys, approved):
    path = session.create(repo)
    for case in ("case-01", "case-02"):
        (path / "responses" / f"{case}-initial.md").write_text(REASONING)
        session.commit_initial(path, case)
        (path / "responses" / f"{case}-final.md").write_text(REASONING)
        session.submit(path, case)
    if approved:
        ledger.approve("test reviewer", 1, "timed", repo)
    cli.show_next(path, "codex", repo)
    _, commands = instructions(capsys)
    assert [c.command for c in commands] == ["evaluate"]
    assert commands[0].draft_guide is not approved

    destination = session.export_evaluation(path, repo, allow_draft=not approved)
    if not approved:
        ledger.approve("test reviewer", 1, "timed", repo)
        cli.show_next(path, "codex", repo)
        _, commands = instructions(capsys)
        assert commands[0].draft_guide  # The exported draft keeps its original status.
    (destination / "feedback.md").write_text("Evaluator feedback for this test.")
    cli.show_next(path, "codex", repo)
    output, commands = instructions(capsys)
    assert str(destination / "feedback.md") in output
    assert not commands


@pytest.mark.parametrize("existing", [False, True])
def test_login_explains_how_to_begin_and_preserves_an_existing_attempt(repo, capsys, monkeypatch, existing):
    path = session.create(repo) if existing else None
    before = (path / "record.json").read_bytes() if existing else None
    monkeypatch.setattr(cli, "ROOT", repo)
    launch = Mock(return_value=0)
    monkeypatch.setattr(sandbox, "run", launch)
    cli.run(cli.parser().parse_args(["login", "claude"]))
    output, commands = instructions(capsys)
    assert "Login complete" in output
    assert cli.preferred_agent(repo) == "claude"
    assert launch.call_count == 1  # Login must not also launch a practice assistant.
    if existing:
        assert [c.command for c in commands] == ["read", "read", "shell", "edit", "edit", "initial"]
        assert commands[0].session == path.name
        assert (path / "record.json").read_bytes() == before
    else:
        assert [c.command for c in commands] == ["start"]
        assert commands[0].agent is None
        assert not (repo / ".reserve/latest").exists()


@pytest.mark.parametrize("case", ["case-01", "case-02"])
def test_read_exposes_only_selected_evidence_and_never_changes_the_record(repo, capsys, case):
    path = session.create(repo)
    before = (path / "record.json").read_bytes()
    cli.read_case(path, case, "brief")
    brief = capsys.readouterr().out
    for name in cli.READING_GROUPS["brief"]:
        assert (path / "work" / case / name).read_text() in brief
    assert "def evaluate(" not in brief
    assert f"./reserve read {case} code" in brief
    cli.read_case(path, case, "code")
    code = capsys.readouterr().out
    for name in cli.READING_GROUPS["code"]:
        assert (path / "work" / case / name).read_text() in code
    assert f"./reserve shell {case}" in code
    assert f"./reserve edit {case} investigation.py" in code
    assert f"./reserve edit {case} initial" in code
    assert (repo / "reference" / f"{case}.md").read_text() not in brief + code
    assert (path / "record.json").read_bytes() == before


def test_read_rejects_paths_and_symlinks_to_reference_material(repo):
    path = session.create(repo)
    with pytest.raises(SystemExit):
        cli.parser().parse_args(["read", "case-01", "../../reference/case-01.md"])
    with pytest.raises(ValueError, match="named case evidence"):
        cli.read_case(path, "case-01", "../../reference/case-01.md")
    file = path / "work/case-01/request.md"
    file.unlink()
    file.symlink_to(repo / "reference/case-01.md")
    with pytest.raises(ValueError, match="Symlinks"):
        cli.read_case(path, "case-01", "brief")


def test_editor_opens_correct_answer_and_preserves_commit_boundaries(repo, tmp_path, monkeypatch):
    path = session.create(repo)
    editor = tmp_path / "editor with spaces.py"
    editor.write_text("from pathlib import Path\nimport sys\nPath(sys.argv[1]).write_text(" + repr(REASONING) + ")\n")
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.setenv("EDITOR", shlex.join([sys.executable, str(editor)]))

    with pytest.raises(ValueError, match="initial reasoning"):
        cli.edit_response(path, "case-01", "final")
    cli.edit_response(path, "case-01", "initial")
    initial = path / "responses/case-01-initial.md"
    assert initial.read_text() == REASONING
    assert read_json(path / "record.json")["cases"]["case-01"]["initial"] is None
    assert (path / "responses/case-02-initial.md").read_text() == session.INITIAL

    session.commit_initial(path, "case-01")
    with pytest.raises(ValueError, match="already committed"):
        cli.edit_response(path, "case-01", "initial")
    cli.edit_response(path, "case-01", "final")
    assert (path / "responses/case-01-final.md").read_text() == REASONING
    assert read_json(path / "record.json")["cases"]["case-01"]["submission"] is None
    session.submit(path, "case-01")
    with pytest.raises(ValueError, match="submitted"):
        cli.edit_response(path, "case-01", "final")


@pytest.mark.parametrize("filename", cli.EDITABLE_CODE)
def test_code_editor_allows_independent_work_without_changing_originals_or_notes(repo, tmp_path, monkeypatch, filename):
    monkeypatch.setattr(cli, "ROOT", repo)
    path = session.create(repo)
    before = (path / "record.json").read_bytes()
    original = {f.name: f.read_bytes() for f in (path / "original/case-01").glob("*.py")}
    initial = (path / "responses/case-01-initial.md").read_bytes()
    editor = tmp_path / "editor.py"
    code = "print('Independent experiment')\n"
    editor.write_text("from pathlib import Path\nimport sys\nPath(sys.argv[1]).write_text(" + repr(code) + ")\n")
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.setenv("EDITOR", shlex.join([sys.executable, str(editor)]))

    cli.run(cli.parser().parse_args(["edit", "case-01", filename]))
    assert (path / "work/case-01" / filename).read_text() == code
    assert (path / "record.json").read_bytes() == before
    assert (path / "responses/case-01-initial.md").read_bytes() == initial
    assert {f.name: f.read_bytes() for f in (path / "original/case-01").glob("*.py")} == original

    (path / "responses/case-01-initial.md").write_text(REASONING)
    session.commit_initial(path, "case-01")
    cli.run(cli.parser().parse_args(["edit", "case-01", filename]))
    (path / "responses/case-01-final.md").write_text(REASONING)
    session.submit(path, "case-01")
    assert (path / "submitted/case-01/workspace" / filename).read_text() == code
    with pytest.raises(ValueError, match="submitted"):
        cli.run(cli.parser().parse_args(["edit", "case-01", filename]))


def test_code_editor_rejects_paths_and_links_outside_the_working_case(repo, monkeypatch):
    path = session.create(repo)
    editor = Mock()
    monkeypatch.setattr(cli.subprocess, "run", editor)
    with pytest.raises(SystemExit):
        cli.parser().parse_args(["edit", "case-01", "../../reference/case-01.md"])
    (path / "work/case-01/investigation.py").symlink_to(repo / "reference/case-01.md")
    with pytest.raises(ValueError, match="Symlinks"):
        cli.edit_response(path, "case-01", "investigation.py")
    editor.assert_not_called()


@pytest.mark.parametrize("provider", ["codex", "claude"])
def test_offline_exploration_precedes_initial_note_and_survives_into_assistance(repo, monkeypatch, capsys, provider):
    monkeypatch.setattr(cli, "ROOT", repo)
    path = session.create(repo)
    (repo / ".reserve/preferred-agent").write_text(provider)
    initial = (path / "responses/case-01-initial.md").read_bytes()
    original = (path / "original/case-01/run.py").read_bytes()
    launches = []

    def launch(workspace, home, actual_provider, command, **kwargs):
        launches.append(command)
        if command == ["bash"]:
            assert kwargs["network"] is False
            assert home.name == "offline-shell"
            assert not (workspace / "INITIAL.md").exists()
            assert read_json(path / "record.json")["cases"]["case-01"]["initial"] is None
            (workspace / "run.py").write_text("# Independent modification\n")
            (workspace / "results.txt").write_text("Independent observation\n")
        else:
            assert actual_provider == provider and command[0] == provider
            assert kwargs["network"] is True
            assert (workspace / "INITIAL.md").read_text() == REASONING
            assert (workspace / "run.py").read_text() == "# Independent modification\n"
            assert (workspace / "results.txt").read_text() == "Independent observation\n"
        return 0

    monkeypatch.setattr(sandbox, "run", launch)
    credentials = Mock()
    monkeypatch.setattr(sandbox, "credentials", credentials)
    cli.run(cli.parser().parse_args(["shell", "case-01"]))
    output, commands = instructions(capsys)
    assert "No AI assistant is running" in output
    assert commands[-1].command == "initial"
    assert cli.preferred_agent(repo) == provider
    credentials.assert_not_called()
    assert (path / "original/case-01/run.py").read_bytes() == original
    assert (path / "responses/case-01-initial.md").read_bytes() == initial
    record = read_json(path / "record.json")["cases"]["case-01"]
    assert record["initial"] is None
    assert record["assistant_runs"][0]["role"] == "human_shell"
    assert record["assistant_runs"][0]["provider"] is None
    with pytest.raises(ValueError, match="initial reasoning"):
        cli.run(cli.parser().parse_args(["assist", "case-01"]))
    assert launches == [["bash"]]

    (path / "responses/case-01-initial.md").write_text(REASONING)
    cli.run(cli.parser().parse_args(["initial", "case-01"]))
    cli.run(cli.parser().parse_args(["assist", "case-01"]))
    assert len(launches) == 2
    credentials.assert_called_once()


@pytest.mark.parametrize("provider,override", [
    ("codex", None), ("claude", None), ("codex", "claude"), ("claude", "codex"),
])
def test_agent_choice_drives_both_cases_and_evaluation_without_repeated_flags(repo, monkeypatch, provider, override):
    monkeypatch.setattr(cli, "ROOT", repo)
    selected = override or provider
    launches = []

    def launch(workspace, home, actual_provider, command, **kwargs):
        assert actual_provider == selected
        assert command[0] == selected
        launches.append((workspace.name, home, actual_provider))
        if workspace.name == "evaluation":
            assert (workspace / "EVALUATE.md").is_file()
            assert (workspace / "case-01.md").is_file()
            assert (workspace / "case-02.md").is_file()
            assert all((workspace / "submissions" / case / "final.md").is_file() for case in session.CASE_IDS)
            assert "EVALUATE.md" in command[-1] and "feedback.md" in command[-1]
            (workspace / "feedback.md").write_text("Mock evaluator output for launch-routing verification.")
        else:
            assert (workspace / "INITIAL.md").read_text() == REASONING
            assert not (workspace / "EVALUATE.md").exists()
            assert not (workspace / "case-01.md").exists()
            assert command[-1] == sandbox.ASSISTANT_PROMPT
            (workspace / "investigation.py").write_text("# Mock investigation artifact for this test.\n")
            write_json(workspace / "results.json", {"test_fixture": True})
        if selected == "claude":
            # A system-prompt option alone leaves Claude waiting for its first message.
            assert command[-2] != "--append-system-prompt"
            assert command[command.index("--append-system-prompt") + 1] == command[-1]
        return 0

    monkeypatch.setattr(sandbox, "run", launch)
    cli.run(cli.parser().parse_args(["start", "--agent", provider]))
    path = session.locate(None, root=repo)
    assert cli.preferred_agent(repo) == provider
    for index, case in enumerate(session.CASE_IDS):
        (path / "responses" / f"{case}-initial.md").write_text(REASONING)
        cli.run(cli.parser().parse_args(["initial", case]))
        flags = ["--agent", override] if index == 0 and override else []
        cli.run(cli.parser().parse_args(["assist", case, *flags]))
        assert cli.preferred_agent(repo) == selected
        (path / "responses" / f"{case}-final.md").write_text(REASONING)
        cli.run(cli.parser().parse_args(["submit", case]))
    cli.run(cli.parser().parse_args(["evaluate", "--draft-guide"]))
    assert [name for name, _, _ in launches] == ["case-01", "case-02", "evaluation"]
    assert len({home for _, home, _ in launches}) == 3
    record = read_json(path / "record.json")
    for case in session.CASE_IDS:
        assert record["cases"][case]["assistant_runs"][0]["provider"] == selected
    assert (path / "evaluation/feedback.md").is_file()
