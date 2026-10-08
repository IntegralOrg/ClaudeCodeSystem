import json
import os
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / "hooks"


def run_hook(name, cwd):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(cwd))
    p = subprocess.run([sys.executable, str(HOOKS / name)], input=json.dumps({"hook_event_name": "SessionStart", "cwd": str(cwd)}),
                       capture_output=True, text=True, env=env, timeout=10)
    return p.returncode, p.stdout, p.stderr


def context_of(stdout):
    return json.loads(stdout)["hookSpecificOutput"]["additionalContext"] if stdout.strip() else ""


def git_repo(path, origin=None):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    if origin:
        subprocess.run(["git", "-C", str(path), "remote", "add", "origin", origin], check=True)
    return path


def test_marker_triggers_on_any_session_start(tmp_path):
    v = git_repo(tmp_path / "v", "https://github.com/someone/brain.git")
    (v / "SETUP_PENDING").write_text("delete me when setup is done\n")
    (v / "System").mkdir(); (v / "System" / "Setup Procedure.md").write_text("# Setup\n")
    rc, out, err = run_hook("setup_pending.py", v)
    assert rc == 0 and err == ""
    text = context_of(out)
    assert "not set up" in text and "System/Setup Procedure.md" in text and "do not wait" in text


def test_marker_ignored_in_template_repo(tmp_path):
    for i, origin in enumerate(("https://github.com/IntegralOrg/ClaudeCodeSystem.git", "git@github.com:IntegralOrg/ClaudeCodeSystem-Cloud.git",
                   "https://github.com/StackDev223/ClaudeCodeSystem")):
        v = git_repo(tmp_path / f"t{i}", origin)
        (v / "SETUP_PENDING").write_text("x"); (v / "System").mkdir(); (v / "System" / "Setup Procedure.md").write_text("#")
        rc, out, _ = run_hook("setup_pending.py", v)
        assert rc == 0 and out.strip() == "", origin


def test_no_marker_prints_nothing(tmp_path):
    rc, out, _ = run_hook("setup_pending.py", git_repo(tmp_path / "v"))
    assert rc == 0 and out.strip() == ""


def test_marker_without_procedure_says_so(tmp_path):
    v = git_repo(tmp_path / "v"); (v / "SETUP_PENDING").write_text("x")
    rc, out, _ = run_hook("setup_pending.py", v)
    text = context_of(out)
    assert rc == 0 and "Setup Procedure.md" in text and "is missing" in text


def test_synced_folder_warning_names_the_fix(tmp_path):
    bad = tmp_path / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Brain"; bad.mkdir(parents=True)
    rc, out, _ = run_hook("guard_vault_path.py", bad)
    text = context_of(out)
    assert rc == 0 and "iCloud" in text and "~/Brain" in text and "GitHub Desktop" in text


def test_plain_folder_prints_nothing(tmp_path):
    rc, out, _ = run_hook("guard_vault_path.py", tmp_path / "Brain")
    assert rc == 0 and out.strip() == ""


def test_other_sync_services_detected(tmp_path):
    for part, label in (("OneDrive", "OneDrive"), ("Dropbox", "Dropbox"), ("Google Drive", "Google Drive"), ("GoogleDrive-me@x.com", "Google Drive")):
        d = tmp_path / part / "Brain"; d.mkdir(parents=True)
        _, out, _ = run_hook("guard_vault_path.py", d)
        assert label in context_of(out), part


def test_lookalike_folder_names_are_not_synced(tmp_path):
    for part in ("icloud-tools", "dropboxfan", "my-onedrive-notes", "cloudstorage-docs"):
        d = tmp_path / part / "Brain"; d.mkdir(parents=True)
        rc, out, _ = run_hook("guard_vault_path.py", d)
        assert rc == 0 and out.strip() == "", part


def test_template_origin_match_is_exact(tmp_path):
    for i, origin in enumerate(("https://github.com/IntegralOrg/ClaudeCodeSystem-Foo.git", "git@github.com:IntegralOrg/ClaudeCodeSystem2.git",
                                "https://github.com/someone/IntegralOrg/ClaudeCodeSystem-x", "https://github.com/Other/ClaudeCodeSystem.git")):
        v = git_repo(tmp_path / f"n{i}", origin)
        (v / "SETUP_PENDING").write_text("x"); (v / "System").mkdir(); (v / "System" / "Setup Procedure.md").write_text("#")
        rc, out, _ = run_hook("setup_pending.py", v)
        assert rc == 0 and "not set up" in context_of(out), origin
