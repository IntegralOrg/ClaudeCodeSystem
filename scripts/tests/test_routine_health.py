import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "routine_health.py"
TODAY = date(2026, 10, 14)  # a Wednesday


def run_hook(cwd, today=TODAY):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(cwd), ROUTINE_HEALTH_TODAY=today.isoformat())
    p = subprocess.run([sys.executable, str(HOOK)], input="{}", capture_output=True, text=True, env=env, timeout=10)
    return p.returncode, (json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"] if p.stdout.strip() else "")


def daily(root, d, body="# Day\n"):
    (root / "Work" / "Daily").mkdir(parents=True, exist_ok=True)
    (root / "Work" / "Daily" / f"{d.isoformat()}.md").write_text(body)


def audit(root, d):
    (root / "_generated" / "vault-hygiene").mkdir(parents=True, exist_ok=True)
    (root / "_generated" / "vault-hygiene" / "audit-log.md").write_text(f"# Audit log\n\n## {d.isoformat()}\nclean\n")


def routines_file(root, text):
    (root / "System").mkdir(parents=True, exist_ok=True)
    (root / "System" / "Routines.md").write_text(text)


def fresh(root):
    daily(root, TODAY - timedelta(days=1))
    audit(root, TODAY)


def test_silent_on_a_fresh_repo(tmp_path):
    assert run_hook(tmp_path) == (0, "")
    fresh(tmp_path)
    assert run_hook(tmp_path) == (0, "")


def test_eod_stale_reports(tmp_path):
    fresh(tmp_path)
    old = TODAY - timedelta(days=7)  # Wednesday a week ago: 5 weekdays elapsed
    for f in (tmp_path / "Work" / "Daily").glob("*.md"):
        f.unlink()
    daily(tmp_path, old)
    rc, text = run_hook(tmp_path)
    assert rc == 0 and text.startswith("Tell the user first:")
    assert "Routine EOD has not run since 2026-10-07 (5 weekdays)" in text


def test_weekend_gap_does_not_report_eod(tmp_path):
    fresh(tmp_path)
    for f in (tmp_path / "Work" / "Daily").glob("*.md"):
        f.unlink()
    daily(tmp_path, date(2026, 10, 9))  # Friday; today Monday 10-12 is 1 weekday later
    audit(tmp_path, date(2026, 10, 11))
    assert run_hook(tmp_path, today=date(2026, 10, 12)) == (0, "")
    daily(tmp_path, date(2026, 10, 9))
    assert run_hook(tmp_path, today=date(2026, 10, 11)) == (0, "")  # Sunday, 2 calendar days


def test_hygiene_stale_reports(tmp_path):
    fresh(tmp_path)
    audit(tmp_path, TODAY - timedelta(days=4))
    rc, text = run_hook(tmp_path)
    assert rc == 0 and "Routine Vault Hygiene has not run since 2026-10-10" in text and "EOD" not in text


def test_monthly_review_stale_reports_and_unknown_is_silent(tmp_path):
    fresh(tmp_path)
    assert run_hook(tmp_path) == (0, "")  # no monthly output at all: unknown, not stale
    (tmp_path / "Work" / "Monthly").mkdir(parents=True)
    (tmp_path / "Work" / "Monthly" / "2026-08-01.md").write_text("# review\n")
    rc, text = run_hook(tmp_path)
    assert "Routine Monthly Review has not run since 2026-08-01" in text


def test_never_run_routine_without_live_since_is_silent(tmp_path):
    routines_file(tmp_path, "# Routines\n")
    assert run_hook(tmp_path) == (0, "")


def test_routine_not_live_after_setup_reports(tmp_path):
    fresh(tmp_path)
    daily(tmp_path, TODAY - timedelta(days=3), "# Day\nSetup complete: vault is ready.\n")
    daily(tmp_path, TODAY - timedelta(days=1))
    routines_file(tmp_path, "# Routines\n\n## End of Day\n- live_since: 2026-10-12\n\n## Vault Hygiene\n- live_since: not live\n\n## Monthly Review\n- live_since: 2026-10-12\n")
    rc, text = run_hook(tmp_path)
    assert "Routine Vault Hygiene is still not live 3 days after setup" in text
    assert "Routine EOD" not in text and "Routine Monthly Review" not in text


def test_not_live_stays_silent_within_two_days_of_setup(tmp_path):
    fresh(tmp_path)
    daily(tmp_path, TODAY - timedelta(days=1), "# Day\nSetup complete: vault is ready.\n")
    routines_file(tmp_path, "# Routines\n\n## Vault Hygiene\n- live_since: not live\n")
    assert run_hook(tmp_path) == (0, "")


def test_template_repo_is_silent(tmp_path):
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin", "https://github.com/IntegralOrg/ClaudeCodeSystem.git"], check=True)
    daily(tmp_path, TODAY - timedelta(days=30))
    assert run_hook(tmp_path) == (0, "")


def setup_and_routines(root, text, days=4):
    fresh(root)
    daily(root, TODAY - timedelta(days=days), "# Day\nSetup complete.\n")
    daily(root, TODAY - timedelta(days=1))
    routines_file(root, text)


def test_heading_with_parenthetical_matches(tmp_path):
    setup_and_routines(tmp_path, "# Routines\n\n## Vault Hygiene (nightly)\n- live_since: not live\n\n## End of Day\n- live_since: 2026-10-11\n\n## Monthly Review\n- live_since: 2026-10-11\n")
    rc, text = run_hook(tmp_path)
    assert "Routine Vault Hygiene is still not live 4 days after setup" in text
    assert "Routine EOD" not in text and "Routine Monthly Review" not in text


def test_numbered_and_marked_up_heading_matches(tmp_path):
    setup_and_routines(tmp_path, "# Routines\n\n## 1. **End of Day**\n- live_since: not live\n\n## 2. `Vault Hygiene`\n- live_since: 2026-10-11\n\n## 3. _Monthly Review_\n- live_since: 2026-10-11\n")
    rc, text = run_hook(tmp_path)
    assert "Routine EOD is still not live 4 days after setup" in text
    assert "Vault Hygiene is still" not in text and "Monthly Review is still" not in text


def test_name_alias_heading_matches(tmp_path):
    setup_and_routines(tmp_path, "# Routines\n\n## eod\n- live_since: not live\n")
    assert "Routine EOD is still not live" in run_hook(tmp_path)[1]


def test_later_routines_bullet_is_not_attributed_to_an_earlier_one(tmp_path):
    setup_and_routines(tmp_path, "# Routines\n\n## Vault Hygiene\n- live_since: not live\n- note: see Monthly Review, live_since: 2026-10-01\n\n## Monthly Review\n- live_since: 2026-10-11\n\n## End of Day\n- live_since: 2026-10-11\n")
    rc, text = run_hook(tmp_path)
    assert "Routine Vault Hygiene is still not live" in text and "Monthly Review is still" not in text
    # a section without its own live_since never borrows from the next section
    setup_and_routines(tmp_path, "# Routines\n\n## Vault Hygiene\n- schedule: nightly\n\n## Monthly Review\n- live_since: 2026-10-11\n\n## End of Day\n- live_since: 2026-10-11\n")
    assert "Routine Vault Hygiene is still not live" in run_hook(tmp_path)[1]


def test_only_the_first_live_since_in_a_section_counts(tmp_path):
    setup_and_routines(tmp_path, "# Routines\n\n## Vault Hygiene\n- live_since: not live\n- live_since: 2026-10-11\n\n## Monthly Review\n- live_since: 2026-10-11\n\n## End of Day\n- live_since: 2026-10-11\n")
    assert "Routine Vault Hygiene is still not live" in run_hook(tmp_path)[1]


def test_month_only_monthly_file_counts_as_the_last_day_of_the_month(tmp_path):
    fresh(tmp_path)
    (tmp_path / "Work" / "Monthly").mkdir(parents=True)
    (tmp_path / "Work" / "Monthly" / "2026-09.md").write_text("# review\n")
    today = date(2026, 11, 5)
    audit(tmp_path, today); daily(tmp_path, today - timedelta(days=1))
    assert "Routine Monthly Review has not run since 2026-09-30" in run_hook(tmp_path, today=today)[1]
    assert run_hook(tmp_path, today=date(2026, 11, 4))[1] == ""


def test_full_date_monthly_file_name_convention(tmp_path):
    fresh(tmp_path)
    (tmp_path / "Work" / "Monthly").mkdir(parents=True)
    (tmp_path / "Work" / "Monthly" / "2026-10-01 Monthly Review.md").write_text("# review\n")
    assert run_hook(tmp_path) == (0, "")
