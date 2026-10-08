#!/usr/bin/env python3
"""SessionStart: if local landing has failed since its last success, or has been skipping for a
structural reason, say so at the start of the session so a machine never diverges silently from the
repo. Reads _generated/landing.log only, and only its timestamped lines. Fails open."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import project_dir, run  # noqa: E402

STAMPED = re.compile(r"^\d{4}-\d{2}-\d{2} \d\d:\d\d:\d\d ")
FAILURE_WORDS = ("conflict", "push failed", "fetch failed", "commit failed", "mid-merge")
CLEARING_WORDS = ("landed on main", "nothing to push")  # HEAD equals origin/main: nothing is stranded
DISABLED_RUN = 3


def disabled_note(lines):
    """When the last DISABLED_RUN or more lines are all `locked` or all `on branch`, landing is effectively off."""
    for word, reason in (("locked", "locked"), ("on branch", "on another branch")):
        n = 0
        for line in reversed(lines):
            if line[20:].startswith(word):
                n += 1
            else:
                break
        if n >= DISABLED_RUN:
            return f"Landing appears disabled: the last {n} attempts were {reason}. Tell the user, then read _generated/landing.log to see why."
    return ""


def main(payload):
    log = Path(project_dir(payload)) / "_generated" / "landing.log"
    if not log.is_file():
        return
    lines = [l for l in log.read_text(encoding="utf-8", errors="replace").splitlines()[-2000:] if STAMPED.match(l)]
    failures = []
    for line in lines:
        if any(w in line for w in CLEARING_WORDS):
            failures = []
        elif any(w in line for w in FAILURE_WORDS):
            failures.append(line)
    parts = []
    fetch_fails = [l for l in failures if "fetch failed" in l]
    failures = [l for l in failures if "fetch failed" not in l]
    if fetch_fails:
        parts.append(f"Landing could not fetch from GitHub {len(fetch_fails)} times since {fetch_fails[0][:19]}: cannot reach GitHub from this "
                     "computer (sign-in or network); see System/Adding Your Computer.md step 4. The edits on this computer have not "
                     "reached the repository. Tell the user this first; this is not a conflict.")
    if failures:
        first, last = failures[0], failures[-1]
        parts.append(f"Landing has failed {len(failures)} times since {first[:19]} (latest: {last[20:200]}). The edits on this "
                     "computer have not reached the repository. First, tell the user this, then read _generated/landing.log, "
                     "run `git status` and `git log origin/main..HEAD --oneline`, and resolve the conflict by hand (never force, never reset --hard).")
    note = disabled_note(lines)
    if note:
        parts.append(note)
    if parts:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": " ".join(parts)}}))


if __name__ == "__main__":
    run(main)
