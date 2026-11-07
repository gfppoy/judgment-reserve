import json
from pathlib import Path
import re
import pytest
from judgment_reserve import ledger, session
from judgment_reserve.util import read_json, write_json, review_version

REASONING = "I suspect either a useful illumination correction or unavailable context. I will inspect grouping provenance, hold images fixed, and use a deployment-matched test before deciding the spending limit."


def commit_pair(root):
    path = session.create(root)
    for case in ("case-01", "case-02"):
        initial = path / "responses" / f"{case}-initial.md"
        initial.write_text(REASONING)
        session.commit_initial(path, case)
        final = path / "responses" / f"{case}-final.md"
        final.write_text(REASONING + " I defer the larger request and specify a bounded follow-up based on the saved evidence.")
        session.submit(path, case)
    return path


def test_submission_and_diagnosis_gates(repo):
    path = session.create(repo)
    with pytest.raises(ValueError, match="Both final"):
        session.export_evaluation(path, repo, allow_draft=True)
    with pytest.raises(ValueError, match="initial"):
        session.submit(path, "case-01")
    with pytest.raises(ValueError, match="Complete"):
        session.commit_initial(path, "case-01")
    (path / "responses/case-01-initial.md").write_text(REASONING)
    session.commit_initial(path, "case-01")
    with pytest.raises(ValueError, match="already"):
        session.commit_initial(path, "case-01")
    assert not (path / "evaluation").exists()


@pytest.mark.parametrize("legacy_instructions", [False, True])
def test_filled_template_fields_commit_without_deleting_instructions(repo, legacy_instructions):
    path = session.create(repo)
    answer = "My answer records the evidence I inspected and the further work I would choose."
    for part in ("initial", "final"):
        file = path / "responses" / f"case-01-{part}.md"
        text = file.read_text()
        if legacy_instructions:
            text = text.replace("Complete each answer field", "Replace each [write here]")
        # Fill only the answer slots, as a participant following the form would.
        text = re.sub(r"(?m)^\[write here\]$", answer, text)
        file.write_text(text)
        assert session.reasoning(file) == text
        if part == "initial":
            session.commit_initial(path, "case-01")
            saved = path / "committed/case-01/initial.md"
        else:
            session.submit(path, "case-01")
            saved = path / "submitted/case-01/final.md"
        assert saved.read_text() == text
        assert file.read_text() == text


@pytest.mark.parametrize("template", [session.INITIAL, session.FINAL], ids=["initial", "final"])
def test_unfilled_answer_error_identifies_the_file_and_line(tmp_path, template):
    file = tmp_path / "answer.md"
    lines = template.replace("Complete each answer field", "Replace each [write here]").splitlines()
    unfilled = None
    for index, line in enumerate(lines):
        if line == "[write here]":
            if unfilled is None:
                lines[index] = "  [write here]  "
                unfilled = index + 1
            else:
                lines[index] = "My answer to this field is saved here."
    file.write_text("\n".join(lines))
    with pytest.raises(ValueError) as error:
        session.reasoning(file)
    assert str(file) in str(error.value)
    assert f"(lines {unfilled})" in str(error.value)


def test_short_reasoning_error_is_distinct_from_unfilled_fields(tmp_path):
    file = tmp_path / "answer.md"
    file.write_text("x" * 79 + "\n")
    with pytest.raises(ValueError) as error:
        session.reasoning(file)
    assert str(file) in str(error.value)
    assert "79 characters; at least 80" in str(error.value)
    assert "placeholder" not in str(error.value)


def test_complete_pair_exports_guide_only_after_explicit_draft_opt_in(repo):
    path = commit_pair(repo)
    with pytest.raises(ValueError, match="not human-approved"):
        session.export_evaluation(path, repo)
    result = session.export_evaluation(path, repo, allow_draft=True)
    assert "DRAFT" in read_json(result / "guide-status.json")["status"]
    assert (result / "case-01.md").exists()
    assert (result / "submissions/case-02/initial.md").read_text() == REASONING
    # A participant can revise their working copy without altering submitted evidence.
    (path / "work/case-01/deployment.md").write_text("changed after submitting")
    session.validate_record(path, read_json(path / "record.json"))
    with pytest.raises(ValueError, match="already committed"):
        session.submit(path, "case-01")


def test_record_detects_tampering_and_rejects_symlinks(repo, tmp_path):
    path = commit_pair(repo)
    (path / "submitted/case-01/final.md").write_text("replaced")
    with pytest.raises(ValueError, match="Submitted evidence"):
        session.export_evaluation(path, repo, allow_draft=True)
    second = session.create(repo)
    (second / "responses/case-01-initial.md").write_text(REASONING)
    session.commit_initial(second, "case-01")
    (second / "responses/case-01-final.md").write_text(REASONING)
    (second / "work/case-01/answer").symlink_to(repo / "reference/case-01.md")
    with pytest.raises(ValueError, match="Symlinks"):
        session.submit(second, "case-01")


def test_challenge_preserves_original_and_does_not_approve_reference(repo):
    path = commit_pair(repo)
    session.export_evaluation(path, repo, allow_draft=True)
    file = path / "my-challenge.md"
    file.write_text(REASONING + " The reviewer should consider this alternative deployment interpretation.")
    before = read_json(path / "record.json")["cases"]
    session.challenge(path, file)
    after = read_json(path / "record.json")
    assert after["cases"] == before
    assert len(after["challenges"]) == 1
    assert read_json(repo / "reference/approval.json")["status"] == "pending_human_review"


def test_missing_and_corrected_attention_are_not_zero_or_double_counted(repo):
    assert ledger.summary(repo)["reported_preparation_minutes"] is None
    common = dict(activity="Check diagnosis", category="validation", reviewer="test reviewer", root=repo)
    missing = ledger.log(**common, minutes=None, method="missing")
    assert ledger.summary(repo)["missing_reports"] == 1
    first = ledger.log(**common, minutes=12, method="estimated", replaces=missing["id"])
    ledger.log(**common, minutes=9, method="timed", replaces=first["id"])
    ledger.log(activity="Tooling", category="tooling", reviewer="test reviewer", root=repo,
               minutes=40, method="estimated")
    report = ledger.summary(repo)
    assert report["reported_preparation_minutes"] == 9
    assert report["by_category"]["tooling"] == 40
    assert report["missing_reports"] == 0
    assert len(ledger.records(repo)) == 4
    with pytest.raises(ValueError):
        ledger.log(**common, minutes=float("nan"), method="estimated")


def test_approval_binds_the_reviewed_version(repo):
    ledger.approve("test reviewer", 5, "timed", repo)
    assert ledger.summary(repo)["human_approved_current_version"]
    path = commit_pair(repo)
    session.export_evaluation(path, repo)
    (repo / "reference/case-02.md").write_text("Changed expert conclusion")
    assert not ledger.summary(repo)["human_approved_current_version"]
    second = commit_pair(repo)
    with pytest.raises(ValueError, match="not human-approved"):
        session.export_evaluation(second, repo)


def test_session_identifier_rejects_path_traversal(repo):
    with pytest.raises(ValueError, match="Invalid"):
        session.locate("../../reference", repo)


def test_attention_can_reference_the_version_actually_reviewed(repo):
    previous = review_version(repo)
    (repo / "reference/guide.md").write_text("A corrected guide after the original review")
    row = ledger.log(activity="Earlier review", category="validation", reviewer="test reviewer",
                     minutes=7, method="estimated", root=repo, artifact_version=previous)
    assert row["artifact_version"] == previous
    assert row["artifact_version"] != review_version(repo)
