#!/usr/bin/env python3
"""Sort a vault's files against a fresh clone of the template so an update only deliberates where it must.

Usage: template-diff.py --template <path to a clone of the template> [--vault <vault root>] [--json]

For every file the template ships (and every file it used to ship), compares the vault's copy with the
template's whole history by git blob hash. Groups:
  add       new in the template, absent from the vault: copy it in.
  take      the vault's copy is an older template version the owner never edited: replace it.
  same      already current.
  changed   the owner edited this file: merge by judgment (System/Updating.md).
  owned     the owner's file that setup or use fills in: change only where a CHANGELOG entry says to.
  retire    the template removed it and the vault's copy is unedited: delete it.
  retire-changed  the template removed it but the owner edited it: judge.
Files that exist only in the vault are never listed and never touched. Read-only; stdlib and git only."""
import argparse
import hashlib
import json
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

OWNED = ("CLAUDE.md", "System/Routines.md", "System/routines/*.md", "Resources/Reference/Local Routines Registry.md")
NEVER = ("SETUP_PENDING",)  # setup deletes it; adding it back would rerun setup


def blob(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def hashes(path):
    """Blob hashes of a file as stored and with CRLF normalized (a Windows checkout)."""
    data = path.read_bytes()
    return {blob(data), blob(data.replace(b"\r\n", b"\n"))}


def git(tpl, *args):
    return subprocess.run(["git", "-C", str(tpl), *args], check=True, capture_output=True, text=True).stdout


def history(tpl):
    """{path: set of every blob hash that path ever had in the template}."""
    seen = {}
    for line in git(tpl, "log", "--format=", "--raw", "--no-abbrev", "--no-renames", "HEAD").splitlines():
        if line.startswith(":") and "\t" in line:
            meta, path = line.split("\t", 1)
            new = meta.split()[3]
            if set(new) != {"0"}:
                seen.setdefault(path, set()).add(new)
    return seen


def classify(tpl, vault):
    current = {}
    for line in git(tpl, "ls-files", "-s").splitlines():
        meta, path = line.split("\t", 1)
        current[path] = meta.split()[1]
    past = history(tpl)
    by_fold = {p.lower(): p for p in current}  # a case-only rename: the old path is the new file on macOS and Windows
    out = {k: [] for k in ("add", "take", "same", "changed", "owned", "retire", "retire-changed")}
    for path in sorted(set(current) | set(past)):
        if path in NEVER:
            continue
        mine = vault / path
        if not mine.is_file():
            if path in current:
                out["add"].append(path)
            continue
        h = hashes(mine)
        if path not in current:
            twin = by_fold.get(path.lower())
            if twin and (vault / twin).is_file():
                continue  # the vault already has the new spelling (or the filesystem folds case): nothing to retire
            out["retire" if h & past.get(path, set()) else "retire-changed"].append(path)
        elif current[path] in h:
            out["same"].append(path)
        elif any(fnmatch(path, p) for p in OWNED):
            out["owned"].append(path)
        elif h & past.get(path, set()):
            out["take"].append(path)
        else:
            out["changed"].append(path)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--template", required=True)
    ap.add_argument("--vault", default=".")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    out = classify(Path(a.template), Path(a.vault))
    if a.json:
        print(json.dumps(out, indent=2))
        return
    for group, paths in out.items():
        if group == "same":
            print(f"same: {len(paths)} files")
            continue
        print(f"{group}: {len(paths)}")
        for p in paths:
            print(f"  {p}")


if __name__ == "__main__":
    sys.exit(main())
