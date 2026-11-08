"""Only provider configuration is installed here; no cases or answers in the image."""
import os
from pathlib import Path
import sys

home = Path.home()
(home / ".codex").mkdir(parents=True, exist_ok=True)
(home / ".claude").mkdir(parents=True, exist_ok=True)
(home / ".codex/config.toml").write_text('''web_search = "disabled"
approval_policy = "never"
sandbox_mode = "danger-full-access"
cli_auth_credentials_store = "file"
check_for_update_on_startup = false

[features]
apps = false
''')
os.environ["CODEX_HOME"] = str(home / ".codex")
os.environ["CLAUDE_CONFIG_DIR"] = str(home / ".claude")
os.environ["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
os.environ["DISABLE_AUTOUPDATER"] = "1"
os.environ["NODE_USE_ENV_PROXY"] = "1"
os.environ["NO_PROXY"] = "localhost,127.0.0.1"
if len(sys.argv) < 2:
    raise SystemExit("Expected a command")
os.execvp(sys.argv[1], sys.argv[1:])
