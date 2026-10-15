#!/usr/bin/env python3
"""SessionStart: one line while a tool on the ledger (System/Tools.md) is still not connected, or an essential one
is `connected <date> (verify next session)` and still needs the check that "connect my tools" runs first.
Essential tools (email, calendar, the notetaker) are named every session; the rest at most once every 7 days
(last date in _generated/tools-reminder.json). Silent when the ledger is absent or complete, silent in the template
repository, fails open. TOOLS_HEALTH_TODAY=YYYY-MM-DD overrides today (tests)."""
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import is_template_repo, project_dir, run  # noqa: E402
import tools_ledger  # noqa: E402

WEEK = 7


def today_date():
    forced = os.environ.get("TOOLS_HEALTH_TODAY")
    try:
        return date.fromisoformat(forced) if forced else date.today()
    except ValueError:
        return date.today()


def join(names):
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def verb(names):
    return "is" if len(names) == 1 else "are"


def reminder_due(root, today):
    f = root / "_generated" / "tools-reminder.json"
    try:
        last = date.fromisoformat(json.loads(f.read_text(encoding="utf-8"))["last"])
    except Exception:
        return True
    return (today - last).days >= WEEK


def record_reminder(root, today):
    try:
        d = root / "_generated"
        d.mkdir(parents=True, exist_ok=True)
        (d / "tools-reminder.json").write_text(json.dumps({"last": today.isoformat()}), encoding="utf-8")
    except Exception:
        pass


def needs_verify(entries):
    return [e["name"] for e in entries if e["essential"] and e["status"].startswith("connected")
            and "(verify next session)" in e["status"]]


def line_for(root, today):
    entries = tools_ledger.load(root)
    ess, other = tools_ledger.open_items(entries)
    check = needs_verify(entries)
    parts = []
    if ess:
        parts.append(f"{join(ess)} {verb(ess)} not connected yet; say 'connect my tools' when you have two minutes.")
    if check:
        parts.append(f"{join(check)} {'needs' if len(check) == 1 else 'need'} a quick check; say 'connect my tools'.")
    if parts:
        return " ".join(parts)
    if other and reminder_due(root, today):
        record_reminder(root, today)
        return f"{join(other)} {verb(other)} not connected yet; say 'connect my tools' when you want it."
    return ""


def main(payload):
    root = Path(project_dir(payload))
    if is_template_repo(root):
        return
    text = line_for(root, today_date())
    if not text:
        return
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                             "additionalContext": "Tell the user first: " + text
                                                                  + " (System/Connecting Tools.md)"}}))


if __name__ == "__main__":
    run(main)
