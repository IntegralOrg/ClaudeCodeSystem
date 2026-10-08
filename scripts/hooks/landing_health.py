#!/usr/bin/env python3
"""SessionStart: if local landing has failed since its last success, say so at the start of the
session so a machine never diverges silently from the repo. Reads _generated/landing.log only. Fails open."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import project_dir, run  # noqa: E402

FAILURE_WORDS = ("conflict", "push failed", "fetch failed", "commit failed")
SUCCESS_WORD = "landed on main"


def main(payload):
    log = Path(project_dir(payload)) / "_generated" / "landing.log"
    if not log.is_file():
        return
    lines = [l for l in log.read_text(encoding="utf-8", errors="replace").splitlines()[-200:] if l.strip()]
    failures = []
    for line in lines:
        if SUCCESS_WORD in line:
            failures = []
        elif any(w in line for w in FAILURE_WORDS):
            failures.append(line)
    if not failures:
        return
    first, last = failures[0], failures[-1]
    text = (f"Landing has failed {len(failures)} times since {first[:19]} (latest: {last[20:200]}). The edits on this "
            "computer have not reached the repository. First, tell the user this, then read _generated/landing.log, "
            "run `git status` and `git log origin/main..HEAD --oneline`, and resolve the conflict by hand (never force, never reset --hard).")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}))


if __name__ == "__main__":
    run(main)
