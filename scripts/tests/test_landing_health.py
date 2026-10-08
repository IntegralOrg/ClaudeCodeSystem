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


def test_untimestamped_git_output_is_not_counted(tmp_path):
    write_log(tmp_path, ["2026-10-08 09:00:00 landed on main (attempt 1)",
                         "hint: Resolve all conflicts manually, mark them as resolved with",
                         "CONFLICT (content): Merge conflict in data.json",
                         "2026-10-08 10:00:00 conflict with origin/main; rebase aborted, working tree untouched, will retry next time"])
    rc, text = run_hook(tmp_path)
    assert rc == 0 and "failed 1 times since 2026-10-08 10:00:00" in text and "hint" not in text
    write_log(tmp_path, ["2026-10-08 09:00:00 landed on main (attempt 1)", "hint: Resolve all conflicts manually", "CONFLICT (content): Merge conflict in x"])
    assert run_hook(tmp_path) == (0, "")


def test_nothing_to_push_clears_earlier_failures(tmp_path):
    write_log(tmp_path, ["2026-10-08 10:00:00 conflict with origin/main; rebase aborted", "2026-10-08 11:00:00 push failed after 3 attempts",
                         "2026-10-08 12:00:00 nothing to land", "2026-10-08 12:00:01 nothing to push"])
    assert run_hook(tmp_path) == (0, "")


def test_mid_merge_skip_is_a_failure(tmp_path):
    write_log(tmp_path, ["2026-10-08 10:00:00 skipped: repository is mid-merge/rebase/cherry-pick/revert"])
    rc, text = run_hook(tmp_path)
    assert rc == 0 and "failed 1 times" in text


def test_repeatedly_locked_reports_disabled(tmp_path):
    write_log(tmp_path, ["2026-10-08 09:00:00 landed on main (attempt 1)"] + [f"2026-10-08 10:0{i}:00 locked: another landing is running" for i in range(3)])
    rc, text = run_hook(tmp_path)
    assert rc == 0 and "Landing appears disabled: the last 3 attempts were locked" in text


def test_repeatedly_on_other_branch_reports_disabled(tmp_path):
    write_log(tmp_path, [f"2026-10-08 10:0{i}:00 on branch feature, not main; skipped" for i in range(4)])
    rc, text = run_hook(tmp_path)
    assert rc == 0 and "Landing appears disabled: the last 4 attempts were on another branch" in text


def test_two_locked_lines_are_not_enough_and_success_resets(tmp_path):
    write_log(tmp_path, ["2026-10-08 10:00:00 locked: another landing is running", "2026-10-08 10:01:00 locked: another landing is running"])
    assert run_hook(tmp_path) == (0, "")
    write_log(tmp_path, [f"2026-10-08 10:0{i}:00 locked: another landing is running" for i in range(3)] + ["2026-10-08 11:00:00 landed on main (attempt 1)"])
    assert run_hook(tmp_path) == (0, "")


def test_fetch_failed_run_is_reported_as_unreachable_not_conflict(tmp_path):
    write_log(tmp_path, ["2026-10-08 09:00:00 landed on main (attempt 1)"] + [f"2026-10-08 10:0{i}:00 fetch failed" for i in range(3)])
    rc, text = run_hook(tmp_path)
    assert rc == 0 and "cannot reach GitHub from this computer (sign-in or network); see System/Adding Your Computer.md step 4" in text
    assert "conflict" not in text.lower().replace("not a conflict", "")
    assert "resolve the conflict" not in text
