"""Run native CLIs inside an evidence-only container. Never fall back to the host."""
from __future__ import annotations

from contextlib import contextmanager
import os
import json
from pathlib import Path
import pty
import shutil
import subprocess
import threading
import uuid

from .util import ROOT, digest, manifest, sha256

IMAGE = "localhost/judgment-reserve:0.1"
AUTH_FILES = {
    "codex": (".codex/auth.json",),
    "claude": (".claude/.credentials.json", ".claude/.claude.json"),
}
ASSISTANT_PROMPT = """You are the researcher's assistant in this investigation.
Use only the evidence in /workspace. Read request.md, deployment.md, and the user's
committed initial reasoning in INITIAL.md. Help inspect code and run the tests the
researcher chooses. You have no expert diagnosis. Do not retrieve external answers,
infer a verdict from case names, or claim unrun tests succeeded. Preserve code and
outputs. Distinguish your contributions from the user's reasoning. The human makes
the final spending decision outside this session. Do not attempt to submit it.

Begin by reading INITIAL.md and the case brief. Summarize the researcher's proposed
test briefly, then invite them to choose the next investigation action. Explain
run.py, loader.py, and detector.py when asked. Help implement experiments in
investigation.py and save numerical observations in results.json, or other clearly
named files the researcher chooses. Working Python files may be edited; keep the
provided data, proposal, preliminary report, and INITIAL.md unchanged. Explain
what each change and observation supports and what remains uncertain.
"""


def runtime() -> str:
    requested = os.environ.get("RESERVE_RUNTIME")
    candidates = [requested] if requested else ["docker", "podman"]
    for candidate in candidates:
        if candidate and shutil.which(candidate):
            result = subprocess.run([candidate, "info"], stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            if result.returncode == 0:
                return candidate
    raise ValueError("A running Docker or Podman engine is required. No unrestricted fallback is permitted.")


def ensure_image(engine: str, root: Path = ROOT, force: bool = False):
    version = digest({n: sha256(root / "sandbox" / n) for n in (
        "Dockerfile", "entrypoint.py", "egress_proxy.py", "claude-settings.json", ".dockerignore")})
    result = subprocess.run([engine, "image", "inspect", IMAGE], capture_output=True, text=True)
    labels = {}
    if result.returncode == 0:
        labels = json.loads(result.stdout)[0].get("Config", {}).get("Labels") or {}
    if force or labels.get("org.judgment-reserve.sandbox-sha") != version:
        subprocess.run([engine, "build", "--label", f"org.judgment-reserve.sandbox-sha={version}",
                        "-t", IMAGE, str(root / "sandbox")], check=True)


def credentials(provider: str, home: Path, root: Path = ROOT):
    """Only dedicated login credentials cross contexts, never host agent history."""
    source = root / ".reserve/auth" / provider
    for name in AUTH_FILES[provider]:
        file = source / name
        if file.is_file() and not file.is_symlink():
            dest = home / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, dest)
            dest.chmod(0o600)


def save_credentials(provider: str, home: Path, root: Path = ROOT):
    """Keep refreshed tokens, never session history or updated project metadata."""
    name = AUTH_FILES[provider][0]
    source = home / name
    if source.is_file() and not source.is_symlink():
        destination = root / ".reserve/auth" / provider / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".new-" + uuid.uuid4().hex[:8])
        try:
            shutil.copyfile(source, temporary)
            temporary.chmod(0o600)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)


def agent_command(provider: str, prompt: str, login: bool = False):
    if login:
        return ["codex", "login", "--device-auth"] if provider == "codex" else ["claude", "auth", "login"]
    if provider == "codex":
        return ["codex", "--no-daemon", "--no-alt-screen", "-c", 'web_search="disabled"',
                "-c", "features.apps=false", "-C", "/workspace", prompt]
    # The role flag alone does not send Claude an opening user message.
    return ["claude", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--setting-sources", "", "--settings", "/opt/reserve/claude-settings.json",
            "--tools", "Bash,Read,Edit,Write,Glob,Grep", "--disable-slash-commands",
            "--no-chrome", "--append-system-prompt", prompt, prompt]


@contextmanager
def launch_command(workspace: Path, home: Path, provider: str, command: list[str],
                   root: Path = ROOT, network: bool = True):
    engine = runtime()
    ensure_image(engine, root)
    workspace, home = workspace.resolve(), home.resolve()
    home.mkdir(parents=True, exist_ok=True)
    home.chmod(0o700)
    manifest(workspace)  # No symbolic links to host files.
    suffix = uuid.uuid4().hex[:10]
    net, external, proxy, worker = (f"jr-{kind}-{suffix}" for kind in ("net", "external", "proxy", "worker"))
    created_net = False
    created_external = False
    try:
        network_name = "none"
        if network:
            subprocess.run([engine, "network", "create", "--internal", net], check=True,
                           stdout=subprocess.DEVNULL)
            created_net = True
            subprocess.run([engine, "network", "create", external], check=True, stdout=subprocess.DEVNULL)
            created_external = True
            subprocess.run([engine, "run", "-d", "--name", proxy, "--read-only", "--cap-drop=ALL",
                            "--network", external,
                            "--security-opt=no-new-privileges", "--env", f"RESERVE_PROVIDER={provider}",
                            "--entrypoint", "python", IMAGE, "/opt/reserve/egress_proxy.py"],
                           check=True, stdout=subprocess.DEVNULL)
            subprocess.run([engine, "network", "connect", "--alias", "egress", net, proxy], check=True)
            network_name = net
        args = [engine, "run", "--rm", "--name", worker, "--network", network_name,
                "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                "--memory=2g", "--cpus=2", "--pids-limit=128", "--tmpfs", "/tmp:rw,nosuid,size=256m",
                "--user", f"{os.getuid()}:{os.getgid()}",
                "--mount", f"type=bind,src={workspace},dst=/workspace",
                "--mount", f"type=bind,src={home},dst=/home/researcher",
                "--env", "HOME=/home/researcher", "--env", "TERM=xterm-256color"]
        if Path(engine).name == "podman":
            args += ["--userns=keep-id"]
        if network:
            args += ["--env", "HTTPS_PROXY=http://egress:8080", "--env", "HTTP_PROXY=http://egress:8080"]
        # Environment variable names only: secrets never appear in command arguments.
        for name in (("OPENAI_API_KEY",) if provider == "codex" else ("ANTHROPIC_API_KEY",)):
            if network and os.environ.get(name):
                args += ["--env", name]
        yield engine, worker, args, command
    finally:
        subprocess.run([engine, "rm", "-f", worker, proxy], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        if created_net:
            subprocess.run([engine, "network", "rm", net], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        if created_external:
            subprocess.run([engine, "network", "rm", external], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)


def run(workspace: Path, home: Path, provider: str, command: list[str], *,
        log: Path | None = None, interactive: bool = True, root: Path = ROOT,
        network: bool = True, seconds: int = 1800):
    with launch_command(workspace, home, provider, command, root, network) as (engine, worker, base, cmd):
        timer = threading.Timer(seconds, lambda: subprocess.run(
            [engine, "stop", "--time", "1", worker], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        timer.daemon = True
        timer.start()
        try:
            if not interactive:
                return subprocess.run(base + [IMAGE] + cmd, capture_output=True, text=True,
                                      timeout=seconds + 15)
            if log:
                log.parent.mkdir(parents=True, exist_ok=True)
            with (log.open("ab") if log else open(os.devnull, "wb")) as stream:
                def read(fd):
                    data = os.read(fd, 4096)
                    stream.write(data)
                    stream.flush()
                    return data
                status = pty.spawn(base + ["-it", IMAGE] + cmd, master_read=read)
                return os.waitstatus_to_exitcode(status)
        finally:
            timer.cancel()
