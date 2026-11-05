import importlib.util
import json
import os
import shutil
from pathlib import Path
import pytest

from judgment_reserve import sandbox, session
from judgment_reserve.util import ROOT, sha256


def test_proxy_allowlist_is_exact_and_rejects_other_ports():
    spec = importlib.util.spec_from_file_location("egress", ROOT / "sandbox/egress_proxy.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.allowed("api.openai.com", 443, "codex")
    assert not module.allowed("api.openai.com.evil.example", 443, "codex")
    assert not module.allowed("api.openai.com", 80, "codex")
    assert not module.allowed("raw.githubusercontent.com", 443, "codex")
    assert not module.allowed("127.0.0.1", 443, "claude")


def test_credentials_do_not_copy_previous_conversations(tmp_path):
    source = tmp_path / ".reserve/auth/codex/.codex"
    source.mkdir(parents=True)
    (source / "auth.json").write_text('{"test": "not a credential"}')
    (source / "sessions").mkdir()
    (source / "sessions/answer.json").write_text("secret diagnosis")
    sandbox.credentials("codex", tmp_path / "fresh", tmp_path)
    assert (tmp_path / "fresh/.codex/auth.json").exists()
    assert not (tmp_path / "fresh/.codex/sessions").exists()
    (tmp_path / "fresh/.codex/auth.json").write_text('{"test": "refreshed placeholder"}')
    sandbox.save_credentials("codex", tmp_path / "fresh", tmp_path)
    assert "refreshed placeholder" in (source / "auth.json").read_text()
    assert (source / "sessions/answer.json").read_text() == "secret diagnosis"


@pytest.mark.container
@pytest.mark.skipif(os.environ.get("RESERVE_TEST_CONTAINERS") != "1", reason="Set RESERVE_TEST_CONTAINERS=1 for live isolation probes")
@pytest.mark.parametrize("provider", ["codex", "claude"])
def test_actual_container_isolation_and_native_cli(tmp_path, repo, provider):
    work = tmp_path / "evidence"
    work.mkdir()
    case = "case-01" if provider == "codex" else "case-02"
    shutil.copytree(ROOT / "cases" / case, work, dirs_exist_ok=True)
    (work / "readme.txt").write_text("available evidence")
    secret = tmp_path / "reference-diagnosis.txt"
    secret.write_text("must not be visible")
    command = sandbox.agent_command(provider, sandbox.ASSISTANT_PROMPT)
    code = f'''import json, pathlib, socket, urllib.request, subprocess
launch = subprocess.run({(command + ['--help'])!r}, capture_output=True, text=True)
out={{'evidence': pathlib.Path('readme.txt').read_text(),
      'host_diagnosis_visible': pathlib.Path({str(secret)!r}).exists(),
      'repository_visible': pathlib.Path({str(ROOT)!r}).exists(),
      'version': subprocess.check_output([{provider!r}, '--version'], text=True).strip(),
      'launch_help_exit': launch.returncode,
      'launch_help_stderr': launch.stderr,
      'metrics': json.loads(subprocess.check_output(['python', 'run.py'], text=True))}}
try:
 urllib.request.urlopen('https://raw.githubusercontent.com/gfppoy/judgment-reserve/main/reference/case-01.md', timeout=5)
 out['retrieval_blocked']=False
except Exception as e:
 out['retrieval_blocked']='403' in str(e)
try:
 connection=socket.create_connection(('1.1.1.1',443),timeout=2);connection.close();out['direct_blocked']=False
except OSError: out['direct_blocked']=True
pathlib.Path('result.txt').write_text('experiment saved')
print(json.dumps(out))
'''
    assistant_home = tmp_path / "assistant-home"
    assistant_home.mkdir()
    (assistant_home / "assistant-only.txt").write_text("Test marker for separate agent state")
    run = sandbox.run(work, assistant_home, provider, ["python", "-c", code],
                      interactive=False, seconds=40)
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["evidence"] == "available evidence"
    assert not result["host_diagnosis_visible"]
    assert not result["repository_visible"]
    assert result["retrieval_blocked"]
    assert result["direct_blocked"]
    assert result["version"]
    assert result["launch_help_exit"] == 0, result["launch_help_stderr"]
    expected = json.loads((ROOT / "cases" / case / "preliminary.json").read_text())
    for metric, value in expected.items():
        assert result["metrics"][metric] == pytest.approx(value, abs=1e-12)
    assert (work / "result.txt").read_text() == "experiment saved"

    # The evaluator uses the same provider with a different bundle and agent home.
    # Probe real container file access without sending test answers to a model.
    attempt = session.create(repo)
    answer = (
        "Container test fixture: I record competing explanations, a distinguishing "
        "test, and a provisional spending decision supported by the supplied evidence."
    )
    with pytest.raises(ValueError, match="Both final"):
        session.export_evaluation(attempt, repo, allow_draft=True)
    for case_id in session.CASE_IDS:
        (attempt / "responses" / f"{case_id}-initial.md").write_text(answer)
        session.commit_initial(attempt, case_id)
        (attempt / "responses" / f"{case_id}-final.md").write_text(answer)
        session.submit(attempt, case_id)
    bundle = session.export_evaluation(attempt, repo, allow_draft=True)
    code = f'''import hashlib, json, pathlib
out = {{
    'diagnoses': {{case: hashlib.sha256(pathlib.Path(case + '.md').read_bytes()).hexdigest()
                  for case in ('case-01', 'case-02')}},
    'answers': {{case: pathlib.Path('submissions', case, 'final.md').read_text()
                for case in ('case-01', 'case-02')}},
    'guide_visible': pathlib.Path('guide.md').is_file(),
    'task_visible': pathlib.Path('EVALUATE.md').is_file(),
    'assistant_state_visible': (pathlib.Path.home() / 'assistant-only.txt').exists(),
    'host_assistant_state_visible': pathlib.Path({str(assistant_home)!r}).exists(),
    'repository_visible': pathlib.Path({str(ROOT)!r}).exists()
}}
print(json.dumps(out))
'''
    run = sandbox.run(bundle, attempt / "evaluator-state" / provider, provider,
                      ["python", "-c", code], interactive=False, seconds=40)
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["diagnoses"] == {case_id: sha256(repo / "reference" / f"{case_id}.md")
                                   for case_id in session.CASE_IDS}
    assert result["answers"] == {case_id: answer for case_id in session.CASE_IDS}
    assert result["guide_visible"] and result["task_visible"]
    assert not result["assistant_state_visible"]
    assert not result["host_assistant_state_visible"]
    assert not result["repository_visible"]
