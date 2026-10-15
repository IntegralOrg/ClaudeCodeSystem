import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "tools_health.py"
TODAY = date(2026, 10, 15)


def run_hook(cwd, today=TODAY):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(cwd), TOOLS_HEALTH_TODAY=today.isoformat())
    p = subprocess.run([sys.executable, str(HOOK)], input="{}", capture_output=True, text=True, env=env, timeout=10)
    return p.returncode, (json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"] if p.stdout.strip() else "")


def ledger(root, text):
    (root / "System").mkdir(parents=True, exist_ok=True)
    (root / "System" / "Tools.md").write_text(text, encoding="utf-8")


def section(name, status, essential):
    return f"## {name}\n- status: {status}\n- essential: {'yes' if essential else 'no'}\n- how: connector \"{name}\"\n- updated: 2026-10-14\n\n"


def test_silent_without_a_ledger(tmp_path):
    assert run_hook(tmp_path) == (0, "")


def test_silent_when_everything_is_connected(tmp_path):
    ledger(tmp_path, "# Tools\n\n" + section("Gmail", "connected 2026-10-14", True))
    assert run_hook(tmp_path) == (0, "")


def test_essential_open_tools_are_named_every_session(tmp_path):
    ledger(tmp_path, "# Tools\n\n" + section("Gmail", "not connected", True) + section("Fathom", "not connected", True)
           + section("Slack", "not connected", False))
    rc, text = run_hook(tmp_path)
    assert rc == 0 and text == ("Tell the user first: Gmail and Fathom are not connected yet; say 'connect my tools' "
                                "when you have two minutes. (System/Connecting Tools.md)")
    rc, text2 = run_hook(tmp_path)
    assert text2 == text


def test_non_essential_open_tools_are_named_once_a_week(tmp_path):
    ledger(tmp_path, "# Tools\n\n" + section("Gmail", "connected 2026-10-14", True) + section("Slack", "not connected", False))
    rc, text = run_hook(tmp_path)
    assert text == "Tell the user first: Slack is not connected yet; say 'connect my tools' when you want it. (System/Connecting Tools.md)"
    assert json.loads((tmp_path / "_generated" / "tools-reminder.json").read_text())["last"] == "2026-10-15"
    assert run_hook(tmp_path, TODAY + timedelta(days=3)) == (0, "")
    rc, text = run_hook(tmp_path, TODAY + timedelta(days=7))
    assert "Slack is not connected yet" in text


def test_skipped_and_key_present_are_not_open(tmp_path):
    ledger(tmp_path, "# Tools\n\n" + section("Text messages", "skipped (no route reads it)", False)
           + section("Rize", "key present 2026-10-14", False))
    assert run_hook(tmp_path) == (0, "")


def test_one_essential_uses_singular_wording(tmp_path):
    ledger(tmp_path, "# Tools\n\n" + section("Gmail", "not connected", True))
    assert run_hook(tmp_path)[1] == ("Tell the user first: Gmail is not connected yet; say 'connect my tools' when you "
                                     "have two minutes. (System/Connecting Tools.md)")


def test_an_essential_tool_waiting_for_its_check_is_named(tmp_path):
    ledger(tmp_path, "# Tools\n\n" + section("Gmail", "connected 2026-10-14 (verify next session)", True))
    assert run_hook(tmp_path)[1] == ("Tell the user first: Gmail needs a quick check; say 'connect my tools'. "
                                     "(System/Connecting Tools.md)")


def test_not_connected_comes_before_the_check_in_one_line(tmp_path):
    ledger(tmp_path, "# Tools\n\n" + section("Gmail", "connected 2026-10-14 (verify next session)", True)
           + section("Google Calendar", "connected 2026-10-14 (verify next session)", True)
           + section("Fathom", "not connected", True)
           + section("Slack", "connected 2026-10-14 (verify next session)", False))
    assert run_hook(tmp_path)[1] == (
        "Tell the user first: Fathom is not connected yet; say 'connect my tools' when you have two minutes. "
        "Gmail and Google Calendar need a quick check; say 'connect my tools'. (System/Connecting Tools.md)")
