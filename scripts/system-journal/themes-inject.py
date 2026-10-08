#!/usr/bin/env python3
"""Inject the Themes relevant to this session's directory (global SessionStart hook).

Themes.md lives in the vault and is written weekly by /system-reflection. Vault sessions read
it through the CLAUDE.md Startup Checklist; every OTHER directory on this Mac (DevProjects repos,
worktrees) gets only the themes whose `Projects:` line names one of its path components, or `all`.
Stdout of a SessionStart hook is added to the session's context. Silent on anything unexpected:
a startup hook must never break or slow a session.

Hook (USER-level ~/.claude/settings.json, so it fires in every directory):
  SessionStart -> python3 ~/scripts/system-journal/themes-inject.py
"""
import json
import os
import re
import sys

HOME = os.path.expanduser("~")
CONFIG_FILE = os.path.join(HOME, ".system-journal", "config.json")
# Where the vault lives: env `SYSTEM_JOURNAL_VAULT`, then the installed config file
# (`install.sh --vault <path>` writes it), then a script-relative fallback (three levels up,
# the vault root when this file sits at `<vault>/scripts/system-journal/`). The installed copy
# under `~/scripts/system-journal/` relies on the config. See README "Configuration".
_FALLBACK_VAULT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resolve_vault():
    v = os.environ.get("SYSTEM_JOURNAL_VAULT")
    if v:
        return os.path.expanduser(v)
    try:
        with open(CONFIG_FILE) as f:
            v = json.load(f).get("vault")
        if v:
            return os.path.expanduser(v)
    except (OSError, ValueError):
        pass
    return _FALLBACK_VAULT


VAULT = resolve_vault()
THEMES = os.path.join(VAULT, "_generated", "Themes.md")


def session_cwd():
    try:
        return json.load(sys.stdin).get("cwd") or os.getcwd()
    except Exception:
        return os.getcwd()


def themes(text):
    """Yield (block_text, projects) for each `## ` block."""
    for block in re.split(r"(?m)^(?=## )", text):
        if not block.startswith("## "):
            continue
        m = re.search(r"(?m)^Projects:\s*(.+)$", block)
        projects = [p.strip().lower() for p in m.group(1).split(",")] if m else []
        yield block.strip(), projects


def main():
    cwd = os.path.realpath(session_cwd())
    vault = os.path.realpath(VAULT)
    # The vault reads Themes itself; temp dirs are headless tool runs (vault-embed, distiller).
    if cwd == vault or cwd.startswith(vault + os.sep):
        return 0
    if cwd.startswith(("/private/var/folders/", "/var/folders/", "/private/tmp", "/tmp")):
        return 0
    try:
        with open(THEMES, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return 0
    parts = {p.lower() for p in cwd.split(os.sep) if p}
    hits = [b for b, projects in themes(text) if "all" in projects or parts & set(projects)]
    if not hits:
        return 0
    print(
        "Recurring cross-session themes that apply to this project (from the vault's weekly "
        "System Journal reflection). If the current task touches one, say so "
        "before doing anything else and avoid repeating the failure.\n"
    )
    print("\n\n".join(hits))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
