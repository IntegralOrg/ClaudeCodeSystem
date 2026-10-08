import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "landing_health.py"


def run_hook(cwd):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(cwd))
    p = subprocess.run([sys.executable, str(HOOK)], input="{}", capture_output=True, text=True, env=env, timeout=10)
    return p.returncode, (json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"] if p.stdout.strip() else "")


def write_log(cwd, lines):
    (cwd / "_generated").mkdir(parents=True, exist_ok=True)
    (cwd / "_generated" / "landing.log").write_text("\n".join(lines) + "\n")


def test_no_log_prints_nothing(tmp_path):
    assert run_hook(tmp_path) == (0, "")


def test_success_last_prints_nothing(tmp_path):
    write_log(tmp_path, ["2026-10-08 10:00:00 conflict with origin/main; rebase aborted", "2026-10-08 10:05:00 landed on main (attempt 2)"])
    assert run_hook(tmp_path) == (0, "")


def test_landing_health_reports_repeated_failures(tmp_path):
    write_log(tmp_path, ["2026-10-08 09:00:00 landed on main (attempt 1)",
                         "2026-10-08 10:00:00 conflict with origin/main; rebase aborted, working tree untouched, will retry next time",
                         "2026-10-08 11:00:00 push failed after 3 attempts"])
    rc, text = run_hook(tmp_path)
    assert rc == 0 and "failed 2 times" in text and "2026-10-08 10:00:00" in text and "push failed" in text and "tell the user" in text


def test_throttle_and_lock_lines_are_not_failures(tmp_path):
    write_log(tmp_path, ["2026-10-08 09:00:00 landed on main (attempt 1)", "2026-10-08 09:00:30 throttled (30s since last run)", "2026-10-08 09:01:00 locked: another landing is running"])
    assert run_hook(tmp_path) == (0, "")
