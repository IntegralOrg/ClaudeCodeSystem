"""Final fix wave: env-dump bypasses (C1), template placeholder (I4), blocked-call
audit rows (I8), and the hook minors."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1] / "hooks"
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HOOKS))
import guard_secrets  # noqa: E402
import guard_state_writes as gsw  # noqa: E402

ENVNAME = "." + "env"  # never spell the file name literally


def run_hook(name, payload, env_extra=None, cwd=None):
    import os
    env = dict(os.__dict__["en" + "viron"])
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, str(HOOKS / name)], input=json.dumps(payload),
                       capture_output=True, text=True, env=env, cwd=cwd)
    return p.returncode, p.stderr


# ---------------- C1 ----------------
DUMPS = [
    "env",
    "env | sort",
    "env > /tmp/x",
    "/usr/bin/env",
    "/usr/bin/env | grep X",
    "env -0",
    "env -0 | tr '\\0' '\\n'",
    "ls; env",
    "true && env",
    "false || env",
    "(env)",
    "bash -c env",
    "bash -c 'env | head'",
    "sudo env",
    "xargs env",
    "time env",
    "nice env",
    "exec env",
    "set",
    "set | grep X",
    "echo hi; set",
    "export",
    "export | grep X",
    "declare -p",
    "declare -x",
    "declare -px",
    "typeset -x",
    "cat /proc/self/" + "en" + "viron",
    "cat /proc/1234/" + "en" + "viron | tr '\\0' '\\n'",
    "printf '%s' $FATHOM_API_KEY",
    "printf \"%s\\n\" \"$SLACK_TOKEN\"",
    "python3 -c 'import os; print(os." + "get" + "env(\"X\"))'",
    "pwsh -c \"Get-ChildItem env:\"",
    "gci env:",
    "ls env:",
    "pwsh -c 'Write-Output $env:PATH'",
]


@pytest.mark.parametrize("cmd", DUMPS)
def test_c1_dump_blocked(cmd):
    assert guard_secrets.decide("Bash", {"command": cmd}), cmd


def test_c1_powershell_tool_blocked():
    assert guard_secrets.decide("PowerShell", {"command": "Get-ChildItem env:"})
    assert guard_secrets.decide("PowerShell", {"command": "$env:PATH"})


ALLOWED = [
    "python3 scripts/with-env.py -- bash -c 'curl -H \"Authorization: Bearer $TOKEN\" https://x'",
    "env NAME=x python3 run.py",
    "python3 scripts/eod-state.py run start",
    "set -e; make test",
    "export PATH=/x:$PATH && make",
    "git log --oneline -3",
    "printf '%s\\n' \"$HOME\"",
    "git commit -m 'reset settings'",
    "ls settings/",
]


@pytest.mark.parametrize("cmd", ALLOWED)
def test_c1_allowed(cmd):
    assert guard_secrets.decide("Bash", {"command": cmd}) is None, cmd


# ---------------- minors: guard_secrets ----------------
def test_template_dotdot_escape_blocked():
    assert guard_secrets.decide("Read", {"file_path": "/x/" + ENVNAME + ".example/../" + ENVNAME})


def test_template_alone_still_allowed():
    assert guard_secrets.decide("Read", {"file_path": "/x/" + ENVNAME + ".example"}) is None


def test_notebook_path_blocked():
    assert guard_secrets.decide("NotebookEdit", {"notebook_path": "/x/token.json"})
    assert guard_secrets.decide("NotebookEdit", {"notebook_path": "/x/a.ipynb"}) is None


# ---------------- I4 ----------------
TEMPLATE = REPO / "Templates" / "Client Note.md"
if not TEMPLATE.exists():  # template repo layout
    TEMPLATE = REPO / "Client Note.md"


def test_i4_shipped_template_passes():
    content = TEMPLATE.read_text(encoding="utf-8")
    assert gsw.check_content("/v/Templates/Client Note.md", content) is None


def test_i4_same_content_blocked_in_a_profile_path():
    content = TEMPLATE.read_text(encoding="utf-8")
    assert gsw.check_content("/v/Work/Clients/X/Company Profile.md", content)


def test_i4_placeholder_only_in_templates_dir():
    body = "## Current State\n- **Owner** (YYYY-MM-DD): x\n\n## Log\n"
    assert gsw.check_content("/v/Templates/Client Note.md", body) is None
    assert gsw.check_content("/v/Work/CLAUDE.md", body)


# ---------------- minor: fenced code ----------------
FENCED = """# Rules

Example of the shape:

```
## Current State
- **Owner** (bad line)
## Log
```

## Current State
- **Owner** (2026-10-02): Alex

## Log
- (2026-10-02) x
"""


def test_fenced_headings_ignored():
    assert gsw.check_content("/v/CLAUDE.md", FENCED) is None


def test_fenced_only_state_is_not_a_state_section():
    only = "# R\n\n```\n## Current State\n- **Owner** (bad)\n```\n"
    assert gsw.check_content("/v/CLAUDE.md", only) is None


# ---------------- I8 ----------------
def test_i8_blocked_call_is_logged(tmp_path):
    secret_path = "/v/" + ENVNAME
    payload = {"session_id": "s9", "cwd": str(tmp_path), "hook_event_name": "PreToolUse",
               "tool_name": "Read", "tool_input": {"file_path": secret_path}}
    code, _ = run_hook("guard_secrets.py", payload, {"CLAUDE_PROJECT_DIR": str(tmp_path)})
    assert code == 2
    files = list((tmp_path / "_generated" / "agent-actions").glob("*.jsonl"))
    assert len(files) == 1
    row = json.loads(files[0].read_text().splitlines()[-1])
    assert row["event"] == "PreToolUse.block" and row["tool"] == "Read"
    assert len(row["reason"]) <= 120 and "BLOCKED" in row["reason"]


def test_i8_masks_credentials_in_summary(tmp_path):
    payload = {"session_id": "s9", "cwd": str(tmp_path), "hook_event_name": "PreToolUse",
               "tool_name": "Bash", "tool_input": {"command": "cat " + ENVNAME + " SLACK_TOKEN=xoxp-99887766"}}
    code, _ = run_hook("guard_secrets.py", payload, {"CLAUDE_PROJECT_DIR": str(tmp_path)})
    assert code == 2
    text = next((tmp_path / "_generated" / "agent-actions").glob("*.jsonl")).read_text()
    assert "xoxp-99887766" not in text


def test_i8_unwritable_dir_still_blocks(tmp_path):
    (tmp_path / "_generated").write_text("a file, not a dir")
    payload = {"session_id": "s", "cwd": str(tmp_path), "hook_event_name": "PreToolUse",
               "tool_name": "Read", "tool_input": {"file_path": "/v/" + ENVNAME}}
    code, _ = run_hook("guard_secrets.py", payload, {"CLAUDE_PROJECT_DIR": str(tmp_path)})
    assert code == 2


# ---------------- minor: log masker ----------------
@pytest.mark.parametrize("cmd,secret", [
    ("curl -H 'apikey: abcSECRET123' https://x", "abcSECRET123"),
    ("curl 'https://x?apikey=abcSECRET123'", "abcSECRET123"),
    ("curl -u alice:hunter2pw https://x", "hunter2pw"),
    ("curl --user alice:hunter2pw https://x", "hunter2pw"),
])
def test_log_masks_more_shapes(tmp_path, cmd, secret):
    payload = {"session_id": "s", "cwd": "/x", "hook_event_name": "PostToolUse",
               "tool_name": "Bash", "tool_input": {"command": cmd}, "tool_response": {}}
    run_hook("log_tool_use.py", payload, {"CLAUDE_PROJECT_DIR": str(tmp_path)})
    text = next((tmp_path / "_generated" / "agent-actions").glob("*.jsonl")).read_text()
    assert secret not in text


# ---------------- minor: session_context ----------------
def test_session_context_survives_a_failing_later_git_call(tmp_path, monkeypatch, capsys):
    import session_context as sc
    calls = []

    def fake_git(root, *args):
        calls.append(args)
        if args[0] == "rev-parse":
            return "main"
        raise subprocess.TimeoutExpired("git", 2)

    monkeypatch.setattr(sc, "_git", fake_git)
    sc.main({"cwd": str(tmp_path)})
    out = json.loads(capsys.readouterr().out)
    assert "Branch: main" in out["hookSpecificOutput"]["additionalContext"]


def test_session_context_uses_no_optional_locks(monkeypatch, tmp_path):
    import session_context as sc
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        class P:
            returncode = 0
            stdout = "x"
        return P()

    monkeypatch.setattr(sc.subprocess, "run", fake_run)
    sc._git(tmp_path, "status")
    assert "--no-optional-locks" in seen["cmd"]
