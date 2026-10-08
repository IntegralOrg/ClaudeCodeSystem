import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1] / "hooks"
sys.path.insert(0, str(HOOKS))
import guard_secrets  # noqa: E402
import guard_state_writes as gsw  # noqa: E402


def run_hook(name, payload):
    p = subprocess.run([sys.executable, str(HOOKS / name)], input=json.dumps(payload),
                       capture_output=True, text=True)
    return p.returncode, p.stderr


def pre(tool, **tool_input):
    return {"session_id": "t", "cwd": "/x", "hook_event_name": "PreToolUse",
            "tool_name": tool, "tool_input": tool_input}


# --- credential paths ---
def test_read_env_blocked():
    assert guard_secrets.decide("Read", {"file_path": "/v/.env"})

def test_read_env_example_allowed():
    assert guard_secrets.decide("Read", {"file_path": "/v/.env.example"}) is None

def test_read_env_local_blocked():
    assert guard_secrets.decide("Read", {"file_path": "/v/.env.local"})

def test_grep_for_token_in_env_blocked():
    assert guard_secrets.decide("Grep", {"pattern": "TOKEN", "path": "/v/.env"})

def test_glob_ssh_blocked():
    assert guard_secrets.decide("Glob", {"pattern": "**/.ssh/*"})

def test_read_readme_allowed():
    assert guard_secrets.decide("Read", {"file_path": "/v/README.md"}) is None


# --- bash: env dumps and naming .env ---
def test_bash_printenv_blocked():
    assert guard_secrets.decide("Bash", {"command": "printenv | grep SLACK"})

def test_bash_env_pipe_grep_blocked():
    assert guard_secrets.decide("Bash", {"command": "env | grep SLACK_TOKEN"})

def test_bash_source_env_blocked():
    assert guard_secrets.decide("Bash", {"command": 'set -a && source "/v/.env" && set +a'})

def test_bash_cat_env_blocked():
    assert guard_secrets.decide("Bash", {"command": "cat .env"})

def test_bash_split_quote_env_blocked():
    assert guard_secrets.decide("Bash", {"command": "cat '.en''v'"})

def test_bash_echo_token_blocked():
    assert guard_secrets.decide("Bash", {"command": "echo $FATHOM_API_KEY"})

def test_bash_python_os_environ_blocked():
    assert guard_secrets.decide("Bash", {"command": "python3 -c 'import os;print(os.environ)'"})

def test_bash_script_that_loads_env_itself_allowed():
    # Review focus 2: the script loads .env internally; the command never names it.
    assert guard_secrets.decide("Bash", {"command": "python3 scripts/fetch-data.py --date 2026-10-06 --out /tmp/f.json"}) is None

def test_bash_with_env_wrapper_allowed():
    assert guard_secrets.decide("Bash", {"command": "python3 scripts/with-env.py -- curl -s https://api.example.com"}) is None

def test_bash_env_example_allowed():
    assert guard_secrets.decide("Bash", {"command": "cat .env.example"}) is None

def test_bash_env_var_usage_allowed():
    # Using a variable is fine; printing it is not.
    assert guard_secrets.decide("Bash", {"command": 'curl -H "Authorization: Bearer $TOKEN" https://x'}) is None


# --- bash: destructive ---
def test_rm_rf_home_blocked():
    assert guard_secrets.decide("Bash", {"command": "rm -rf ~/projects/foo"})

def test_rm_rf_scratchpad_allowed():
    # Review focus 1.
    assert guard_secrets.decide("Bash", {"command": "rm -rf /private/tmp/session-1000/abc/scratch"}) is None

def test_rm_rf_tmp_allowed():
    assert guard_secrets.decide("Bash", {"command": "rm -rf /tmp/x && echo ok"}) is None

def test_git_push_force_blocked():
    assert guard_secrets.decide("Bash", {"command": "git push --force origin main"})

def test_git_push_force_with_lease_allowed():
    assert guard_secrets.decide("Bash", {"command": "git push --force-with-lease origin feat"}) is None

def test_git_reset_hard_blocked():
    assert guard_secrets.decide("Bash", {"command": "git reset --hard HEAD~3"})

def test_drop_table_blocked():
    assert guard_secrets.decide("Bash", {"command": "psql -c 'DROP TABLE decisions'"})


# --- subprocess behaviour ---
def test_script_blocks_with_exit_2():
    code, err = run_hook("guard_secrets.py", pre("Read", file_path="/v/.env"))
    assert code == 2 and "BLOCKED" in err

def test_script_allows_with_exit_0():
    code, _ = run_hook("guard_secrets.py", pre("Read", file_path="/v/README.md"))
    assert code == 0

def test_script_fails_open_on_garbage():
    # Review focus 4.
    p = subprocess.run([sys.executable, str(HOOKS / "guard_secrets.py")], input="not json",
                       capture_output=True, text=True)
    assert p.returncode == 0 and p.stdout == ""

def test_script_fails_open_on_missing_fields():
    code, _ = run_hook("guard_secrets.py", {"tool_name": "Bash"})
    assert code == 0

def post(tool, event="PostToolUse", **kw):
    return {"session_id": "s1", "cwd": kw.pop("cwd", "/x"), "hook_event_name": event,
            "tool_name": tool, "tool_input": kw.pop("tool_input", {}),
            "tool_response": kw.pop("tool_response", {})}

def test_log_writes_row_and_masks_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    payload = post("Bash", tool_input={"command": "curl -H 'Authorization: Bearer abc123' https://x SLACK_TOKEN=xoxp-999 python3 run.py"})
    code, _ = run_hook("log_tool_use.py", payload)
    assert code == 0
    rows = list((tmp_path / "_generated" / "agent-actions").glob("*.jsonl"))
    assert len(rows) == 1
    row = json.loads(rows[0].read_text().splitlines()[-1])
    assert row["tool"] == "Bash" and row["ok"] is True and row["session_id"] == "s1"
    assert "abc123" not in row["summary"] and "xoxp-999" not in row["summary"]
    assert "python3 run.py" in row["summary"] or "curl" in row["summary"]

def test_log_failure_event_sets_ok_false(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    payload = post("Read", event="PostToolUseFailure", tool_input={"file_path": "/v/a.md"},
                   tool_response={"error": "ENOENT: no such file"})
    run_hook("log_tool_use.py", payload)
    row = json.loads(next((tmp_path / "_generated" / "agent-actions").glob("*.jsonl")).read_text())
    assert row["ok"] is False and row["error_class"] == "ENOENT" and row["summary"] == "/v/a.md"

def test_log_never_writes_env_file_contents(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    payload = post("Read", tool_input={"file_path": "/v/.env"}, tool_response={"content": "KEY=verysecret"})
    run_hook("log_tool_use.py", payload)
    text = next((tmp_path / "_generated" / "agent-actions").glob("*.jsonl")).read_text()
    assert "verysecret" not in text

def test_log_fails_open_without_project_dir(tmp_path, monkeypatch):
    (tmp_path / "afile").write_text("x")
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    code, _ = run_hook("log_tool_use.py", {"tool_name": "Bash", "cwd": str(tmp_path / "afile")})
    assert code == 0


GOOD = """---
type: client-profile
---
# Company Profile: Acme

## Current State
<!-- one dated line per key; REPLACE on change -->
- **Engagement** (2026-09-29): offer moves to a flat monthly retainer or a seat
- **Owner** (2026-10-02): Alex

## Overview
text

## Log
<!-- append-only -->
- (2026-10-02) Dev lead handed to Alex
"""

def test_good_profile_allowed():
    assert gsw.check_content("/v/Work/Clients/Acme/Company Profile.md", GOOD) is None

def test_profile_without_current_state_allowed():
    # Review focus 3: structure is enforced only where it exists.
    legacy = "# Acme\n\n## Recent Activity\n- 2026-01-01 x\n"
    assert gsw.check_content("/v/Work/Clients/Acme/Company Profile.md", legacy) is None

def test_second_current_state_blocked():
    assert "Current State" in gsw.check_content("/v/a/Company Profile.md", GOOD + "\n## Current State\n")

def test_recent_activity_with_current_state_blocked():
    assert "Recent Activity" in gsw.check_content("/v/a/Company Profile.md", GOOD + "\n## Recent Activity\n- x\n")

def test_duplicate_key_blocked():
    bad = GOOD.replace("- **Owner** (2026-10-02): Alex", "- **Owner** (2026-10-02): Alex\n- **owner** (2026-10-03): Sam")
    assert "duplicate" in gsw.check_content("/v/a/Company Profile.md", bad).lower()

def test_undated_state_line_blocked():
    bad = GOOD.replace("- **Owner** (2026-10-02): Alex", "- **Owner**: Alex")
    assert "date" in gsw.check_content("/v/a/Company Profile.md", bad).lower()

def test_out_of_scope_path_ignored():
    assert gsw.check_content("/v/Work/Daily/2026-10-06.md", GOOD + "\n## Current State\n") is None

def test_memory_file_in_scope():
    assert gsw.check_content("/u/.claude/projects/x/memory/project_foo.md", GOOD + "\n## Current State\n")

def test_resulting_content_for_edit(tmp_path):
    f = tmp_path / "Company Profile.md"
    f.write_text(GOOD)
    path, content = gsw.resulting_content("Edit", {"file_path": str(f), "old_string": "Alex", "new_string": "Sam"})
    assert path == str(f) and "- **Owner** (2026-10-02): Sam" in content

def test_resulting_content_for_write():
    path, content = gsw.resulting_content("Write", {"file_path": "/v/Company Profile.md", "content": "x"})
    assert content == "x"

def test_edit_adding_second_recent_activity_blocked_end_to_end(tmp_path):
    f = tmp_path / "Company Profile.md"
    f.write_text(GOOD)
    payload = pre("Edit", file_path=str(f), old_string="## Log", new_string="## Recent Activity\n- y\n\n## Log")
    code, err = run_hook("guard_state_writes.py", payload)
    assert code == 2 and "Recent Activity" in err

def test_edit_missing_file_fails_open(tmp_path):
    payload = pre("Edit", file_path=str(tmp_path / "Company Profile.md"), old_string="a", new_string="b")
    code, _ = run_hook("guard_state_writes.py", payload)
    assert code == 0

def test_session_context_outputs_nested_additional_context(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "a.md").write_text("x")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "first"], check=True)
    (tmp_path / ".handoffs").mkdir()
    (tmp_path / ".handoffs" / "foo.md").write_text("# Foo handoff\nline2\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    p = subprocess.run([sys.executable, str(HOOKS / "session_context.py")], input="{}", capture_output=True, text=True)
    assert p.returncode == 0
    out = json.loads(p.stdout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "first" in ctx and "foo.md" in ctx and "Foo handoff" in ctx
    assert len(ctx) <= 2000

def test_session_context_silent_outside_git(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    p = subprocess.run([sys.executable, str(HOOKS / "session_context.py")], input="{}", capture_output=True, text=True)
    assert p.returncode == 0 and p.stdout.strip() == ""


# ===== fix round 1 =====
def _row(tmp_path):
    f = next((tmp_path / "_generated" / "agent-actions").glob("*.jsonl"))
    return json.loads(f.read_text().splitlines()[-1])


@pytest.mark.parametrize("cmd,secret", [
    ("curl -H 'x: y' sk-ant-api03-AAAA-BBBB", "AAAA-BBBB"),
    ("run api_key=hunter2value now", "hunter2value"),
    ("run token=hunter2value now", "hunter2value"),
    ("run password=hunter2value now", "hunter2value"),
    ("run secret=hunter2value now", "hunter2value"),
    ("curl -H 'X-Api-Key: hunter2value' https://x", "hunter2value"),
    ("curl -H 'Authorization: Basic dXNlcjpwYXNz' https://x", "dXNlcjpwYXNz"),
    ("pay sk_live_abcDEF123456 now", "abcDEF123456"),
    ("pay sk_test_abcDEF123456 now", "abcDEF123456"),
    ("pay pk_live_abcDEF123456 now", "abcDEF123456"),
    ("pay pk_abcDEF123456 now", "abcDEF123456"),
])
def test_log_masks_secret_shapes(tmp_path, monkeypatch, cmd, secret):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    run_hook("log_tool_use.py", post("Bash", tool_input={"command": cmd}))
    text = next((tmp_path / "_generated" / "agent-actions").glob("*.jsonl")).read_text()
    assert secret not in text


def test_log_masks_grep_pattern(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    run_hook("log_tool_use.py", post("Grep", tool_input={"pattern": "sk-ant-api03-AAAA-BBBB"}))
    assert "AAAA-BBBB" not in json.dumps(_row(tmp_path))


def test_log_reads_error_field(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    payload = post("Bash", event="PostToolUseFailure", tool_input={"command": "x"})
    payload["error"] = "TimeoutError: command timed out"
    run_hook("log_tool_use.py", payload)
    row = _row(tmp_path)
    assert row["ok"] is False and row["error_class"] == "TimeoutError"


# --- final-wave masker shapes (log_tool_use._mask / _summary are the single source of masking) ---
import log_tool_use  # noqa: E402


@pytest.mark.parametrize("text,secret,expected", [
    ("postgresql://postgres:hunter2@db.example.com/x", "hunter2", "postgresql://postgres:***@db.example.com/x"),
    ("redis://:hunter2@cache.example.com:6379", "hunter2", None),
    ("curl 'https://api.x.com/v1?key=abc123def'", "abc123def", None),
    ("curl 'https://api.x.com/v1?a=1&access_token=abc123def&b=2'", "abc123def", None),
    ('{"secrets": {"STRIPE_KEY": "sk_live_abc"}}', "sk_live_abc", '{"secrets": {"STRIPE_KEY": "***"}}'),
    ('{"key": "FOO", "value": "s3cret"}', "s3cret", '{"key": "FOO", "value": "***"}'),
    ('{"password": "p@ss w0rd"}', "p@ss w0rd", '{"password": "***"}'),
    ("echo ghp_abcdefghijklmnop1234 | gh auth login --with-token", "abcdefghijklmnop1234", None),
    ("echo abcdefghijklmnop1234xyz | docker login -u me --password-stdin", "abcdefghijklmnop1234xyz", None),
    ("echo abcdefghijklmnop1234xyz | npx some-cli login --stdin", "abcdefghijklmnop1234xyz", None),
])
def test_mask_final_wave_shapes(text, secret, expected):
    out = log_tool_use._mask(text)
    assert secret not in out and "***" in out
    if expected is not None:
        assert out == expected


def test_mask_leaves_plain_commands_unchanged():
    for text in ("git status", "echo hello | gh auth login", "ls -la https://example.com/a?page=2"):
        assert log_tool_use._mask(text) == text


@pytest.mark.parametrize("tool", ["mcp__fly__fly-secrets-set", "create_project_env", "mcp__x__edit_project_env"])
def test_summary_withholds_secret_bearing_tools(tool):
    assert log_tool_use._summary(tool, {"command": "x", "pattern": "p", "file_path": "/a",
                                        "secrets": {"K": "v"}}) == log_tool_use.WITHHELD_TOOL
    assert log_tool_use._summary("Bash", {"command": "git status"}) == "git status"


# --- guard_secrets additions ---
def test_grep_glob_param_blocked():
    assert guard_secrets.decide("Grep", {"pattern": "KEY", "glob": ".env"})
    assert guard_secrets.decide("Glob", {"pattern": "**/.env*"})

def test_grep_credential_name_without_path_allowed():
    assert guard_secrets.decide("Grep", {"pattern": "API_KEY|TOKEN|SECRET|PASSWORD"}) is None

def test_bash_command_substitution_env_blocked():
    assert guard_secrets.decide("Bash", {"command": "echo `cat .env`"})
    assert guard_secrets.decide("Bash", {"command": "x=$(cat .env)"})

def test_rm_second_command_blocked():
    assert guard_secrets.decide("Bash", {"command": "rm -rf /tmp/a; rm -rf ~/x"})

def test_rm_flags_after_target_blocked():
    assert guard_secrets.decide("Bash", {"command": "rm ~/x -rf"})

def test_rm_trailing_comment_allowed():
    assert guard_secrets.decide("Bash", {"command": "rm -rf /tmp/x # note"}) is None

def test_rm_dotdot_escape_blocked():
    assert guard_secrets.decide("Bash", {"command": "rm -rf /tmp/../Users/x"})

def test_rm_newline_second_command_blocked():
    assert guard_secrets.decide("Bash", {"command": "rm -rf /tmp/a\nrm -rf ~/x"})


# --- fail-open on bad stdin, every hook ---
@pytest.mark.parametrize("hook", ["guard_secrets.py", "log_tool_use.py", "guard_state_writes.py", "session_context.py"])
@pytest.mark.parametrize("stdin", ["not json", "", "[]", "null"])
def test_all_hooks_fail_open_on_bad_stdin(hook, stdin, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    p = subprocess.run([sys.executable, str(HOOKS / hook)], input=stdin, capture_output=True, text=True)
    assert p.returncode == 0


# ===== fix round 2: redirections are not rm targets =====
def test_rm_redirect_stderr_allowed():
    assert guard_secrets.decide("Bash", {"command": "rm -rf /tmp/x 2>/dev/null"}) is None

def test_rm_redirect_both_allowed():
    assert guard_secrets.decide("Bash", {"command": "rm -rf /tmp/x >/dev/null 2>&1"}) is None

def test_rm_home_with_redirect_still_blocked():
    assert guard_secrets.decide("Bash", {"command": "rm -rf ~/x 2>/dev/null"})

def test_rm_background_amp_second_rm_blocked():
    assert guard_secrets.decide("Bash", {"command": "rm -rf /tmp/a & rm -rf ~/b"})


@pytest.mark.parametrize("text,secret", [
    ('TOKEN="alpha beta" echo ok', "alpha beta"),
    ("API_KEY='alpha beta' ./run.sh", "alpha beta"),
    ('password="p w" ssh x', "p w"),
    ('{"secret_value": "hunter2"}', "hunter2"),
    ('{"client_credentials": "hunter2"}', "hunter2"),
])
def test_mask_quoted_assignments_and_secret_json_keys(text, secret):
    out = log_tool_use._mask(text)
    assert secret not in out and "***" in out


@pytest.mark.parametrize("tool", ["mcp__vault__set_secret", "mcp__x__create-secret", "put_secrets", "mcp__fly__fly-secrets-set"])
def test_summary_withholds_verb_first_secret_tools(tool):
    assert log_tool_use._summary(tool, {"secret_value": "hunter2"}) == log_tool_use.WITHHELD_TOOL


def test_summary_does_not_withhold_ordinary_tools():
    for tool in ("Bash", "mcp__fly__fly-status", "get_secret_name_list_docs", "Read"):
        assert log_tool_use._summary(tool, {"command": "ls"}) != log_tool_use.WITHHELD_TOOL


@pytest.mark.parametrize("text,leaks", [
    ('TOKEN="alpha\\"beta" echo ok', ["alpha", "beta"]),
    ('TOKEN="alpha \\"beta gamma" echo ok', ["alpha", "beta", "gamma"]),
])
def test_mask_quoted_assignment_with_escaped_quote(text, leaks):
    out = log_tool_use._mask(text)
    assert out == "TOKEN=*** echo ok"
    assert not any(x in out for x in leaks)
