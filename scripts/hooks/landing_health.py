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
FAILURE_WORDS = ("conflict", "push failed", "fetch failed", "commit failed", "mid-merge", "rebase skipped")
UNION_RULE = ("Resolve it by Git Autopilot rule 6 in CLAUDE.md: in Markdown keep both sides (union) and then make the "
              "frontmatter valid, the newest side wins in generated files, and structured config merges keys, keeping "
              "main's value when the two sides cannot be ordered.")
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


REFUSAL_DAYS = 3


def cloud_refusals(root):
    """Markers that cloud-land.sh landed when it refused part or all of a cloud session's edits
    (_generated/landing/cloud-refusals/<YYYY-MM-DD>-<sid8>.json), at most REFUSAL_DAYS old. The
    marker is the only trace of edits that never reached main, so it is reported on every machine."""
    import os
    from datetime import date, timedelta
    d = Path(root) / "_generated" / "landing" / "cloud-refusals"
    if not d.is_dir():
        return []
    forced = os.environ.get("LANDING_HEALTH_TODAY")
    today = date.fromisoformat(forced) if forced else date.today()
    out = []
    for p in sorted(d.glob("*.json")):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})-([0-9a-f]{8})\.json$", p.name)
        if not m:
            continue
        try:
            when = date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if not (timedelta(0) <= today - when <= timedelta(days=REFUSAL_DAYS)):
            continue
        reason, n = "see the marker", ""
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
            reason = str(rec.get("reason") or reason)
            n = f"{int(rec.get('refused_deletions', 0)) + int(rec.get('refused_changes', 0))} "
        except Exception:
            pass
        out.append(f"Cloud session {m.group(2)} on {m.group(1)} could not save {n}change(s) to main ({reason}). Those edits are "
                   f"not on main. Tell the user this first; the record is _generated/landing/cloud-refusals/{p.name}.")
    return out


def main(payload):
    root = Path(project_dir(payload))
    refusals = cloud_refusals(root)
    log = root / "_generated" / "landing.log"
    if not log.is_file():
        if refusals:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": " ".join(refusals)}}))
        return
    lines = [l for l in log.read_text(encoding="utf-8", errors="replace").splitlines()[-2000:] if STAMPED.match(l)]
    failures = []
    for line in lines:
        if any(w in line for w in CLEARING_WORDS):
            failures = []
        elif any(w in line for w in FAILURE_WORDS):
            failures.append(line)
    parts = list(refusals)
    fetch_fails = [l for l in failures if "fetch failed" in l]
    synced_skips = [l for l in failures if "rebase skipped: synced folder" in l]
    failures = [l for l in failures if "fetch failed" not in l and "rebase skipped: synced folder" not in l]
    if synced_skips:
        parts.append(f"Landing skipped {len(synced_skips)} time(s) since {synced_skips[0][:19]} because this vault sits in a synced folder "
                     "(iCloud, Dropbox, OneDrive or Google Drive), where updating from GitHub would rewrite files and leave copies. "
                     "The edits are saved on this computer but have not reached the repository. Tell the user this first; the fix is "
                     "to move the vault out of the synced folder (System/Adding Your Computer.md, step 2).")
    if fetch_fails:
        parts.append(f"Landing could not fetch from GitHub {len(fetch_fails)} times since {fetch_fails[0][:19]}: cannot reach GitHub from this "
                     "computer (sign-in or network); see System/Adding Your Computer.md step 4. The edits on this computer have not "
                     "reached the repository. Tell the user this first; this is not a conflict.")
    if failures:
        first, last = failures[0], failures[-1]
        parts.append(f"Landing has failed {len(failures)} times since {first[:19]} (latest: {last[20:200]}). The edits on this "
                     "computer have not reached the repository. First, tell the user this, then read _generated/landing.log, "
                     "run `git status` and `git log origin/main..HEAD --oneline`, and resolve the conflict by hand (never force, never reset --hard). " + UNION_RULE)
    note = disabled_note(lines)
    if note:
        parts.append(note)
    if parts:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": " ".join(parts)}}))


if __name__ == "__main__":
    run(main)
