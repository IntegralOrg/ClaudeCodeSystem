#!/usr/bin/env python3
"""SessionStart: inject what is true right now (branch, uncommitted count, recent
commits, newest handoff). Rules files hold what is always true; this holds today."""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import project_dir, run  # noqa: E402

LIMIT = 2000
MAX_HANDOFF_BYTES = 64 * 1024


def _git(root, *args):
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=2)
    return p.stdout.strip() if p.returncode == 0 else None


def main(payload):
    root = Path(project_dir(payload))
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch is None:
        return
    status = _git(root, "status", "--porcelain", "--untracked-files=no") or ""
    uncommitted = len([l for l in status.splitlines() if l.strip()])
    log = _git(root, "log", "--oneline", "-3") or ""
    parts = [f"Branch: {branch} | uncommitted: {uncommitted} files",
             "Last commits:\n" + log if log else ""]
    handoffs = root / ".handoffs"
    if handoffs.is_dir():
        files = sorted(handoffs.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            f = files[0]
            when = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
            head = ""
            if f.stat().st_size <= MAX_HANDOFF_BYTES:
                head = "\n" + "\n".join(f.read_text(encoding="utf-8", errors="replace").splitlines()[:12])
            parts.append(f"Newest handoff: {f.name} ({when}){head}")
    text = "\n".join(p for p in parts if p)[:LIMIT]
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}))


if __name__ == "__main__":
    run(main)
