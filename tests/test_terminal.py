"""Exercise interactive terminal sizing, not just captured subprocess output."""
import json
import os
import pty
import select
import signal
import subprocess
import sys
import termios
import time

import pytest

from judgment_reserve.util import ROOT


PROBE = """import json, signal, sys, termios
def report(label):
    print(label + json.dumps(termios.tcgetwinsize(0)), flush=True)
signal.signal(signal.SIGWINCH, lambda *_: report('RESIZED:'))
report('READY:')
line = sys.stdin.readline().strip()
print('INPUT:' + line, flush=True)
sys.exit(7)
"""


@pytest.mark.parametrize("container", [
    False,
    pytest.param(True, marks=[pytest.mark.container, pytest.mark.skipif(
        os.environ.get("RESERVE_TEST_CONTAINERS") != "1",
        reason="Set RESERVE_TEST_CONTAINERS=1 for the interactive container probe")]),
], ids=["terminal", "container"])
def test_interactive_size_resize_input_log_and_terminal_restoration(tmp_path, container):
    work = tmp_path / "work"
    work.mkdir()
    log = tmp_path / "transcript.log"
    result_file = tmp_path / "result.json"
    if container:
        invocation = f"""status = sandbox.run(Path({str(work)!r}), Path({str(tmp_path / 'home')!r}),
    'codex', ['python', '-c', {PROBE!r}], log=Path({str(log)!r}), network=False, seconds=40)
"""
    else:
        invocation = f"""with open({str(log)!r}, 'ab') as transcript:
    def read(fd):
        data = os.read(fd, 4096)
        transcript.write(data)
        transcript.flush()
        return data
    status = os.waitstatus_to_exitcode(sandbox._spawn_interactive(
        [sys.executable, '-c', {PROBE!r}], read))
"""
    driver = f"""import json, os, signal, sys, termios
from pathlib import Path
from judgment_reserve import sandbox
def original_handler(*_):
    pass
signal.signal(signal.SIGWINCH, original_handler)
before = termios.tcgetattr(0)
{invocation}
Path({str(result_file)!r}).write_text(json.dumps({{
    'exit_code': status,
    'terminal_restored': termios.tcgetattr(0) == before,
    'handler_restored': signal.getsignal(signal.SIGWINCH) is original_handler
}}))
"""
    master, slave = pty.openpty()
    termios.tcsetwinsize(slave, (30, 110))
    process = subprocess.Popen([sys.executable, "-c", driver], cwd=ROOT,
                               stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
    received = bytearray()

    def expect(marker):
        deadline = time.monotonic() + 30
        while marker not in received:
            remaining = deadline - time.monotonic()
            assert remaining > 0, received.decode(errors="replace")
            ready, _, _ = select.select([master], [], [], remaining)
            assert ready, received.decode(errors="replace")
            try:
                chunk = os.read(master, 4096)
            except OSError:
                chunk = b""
            assert chunk, received.decode(errors="replace")
            received.extend(chunk)

    try:
        expect(b"READY:[30, 110]")
        termios.tcsetwinsize(master, (42, 155))
        # Popen has no controlling outer TTY; send the window-change notification
        # that a terminal emulator normally sends to the foreground launcher.
        os.kill(process.pid, signal.SIGWINCH)
        expect(b"RESIZED:[42, 155]")
        os.write(master, b"terminal input survives\n")
        expect(b"INPUT:terminal input survives")
        assert process.wait(timeout=15) == 0
        assert json.loads(result_file.read_text()) == {
            "exit_code": 7, "terminal_restored": True, "handler_restored": True,
        }
        transcript = log.read_text()
        assert "READY:[30, 110]" in transcript
        assert "RESIZED:[42, 155]" in transcript
        assert "INPUT:terminal input survives" in transcript
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        os.close(master)
        os.close(slave)


def test_interactive_size_falls_back_when_no_outer_terminal_is_available():
    probe = "import termios; print('SIZE:' + str(termios.tcgetwinsize(0)), flush=True)"
    driver = f"""import os, sys
from judgment_reserve import sandbox
status = sandbox._spawn_interactive([sys.executable, '-c', {probe!r}], lambda fd: os.read(fd, 4096))
sys.exit(os.waitstatus_to_exitcode(status))
"""
    result = subprocess.run([sys.executable, "-c", driver], cwd=ROOT, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert "SIZE:(24, 80)" in result.stdout
