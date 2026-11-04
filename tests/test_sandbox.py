import importlib.util
import json
import os
import shutil
from pathlib import Path
import pytest

from judgment_reserve import sandbox
from judgment_reserve.util import ROOT


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
def test_actual_container_isolation_and_native_cli(tmp_path, provider):
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
    run = sandbox.run(work, tmp_path / "fresh-home", provider, ["python", "-c", code],
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
