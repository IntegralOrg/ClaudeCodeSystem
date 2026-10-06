#!/usr/bin/env python3
"""PreToolUse gate on Edit/Write/MultiEdit: state-bearing files keep their shape.

Scope: Company Profile.md, CLAUDE.md, MEMORY.md, memory/*.md, Templates/Client Note.md.
Rules apply only when the file (after the edit) has a `## Current State` block:
  one Current State, one Log, no Recent Activity/Decisions beside it,
  every state line is `- **Key** (YYYY-MM-DD): text`, keys unique.
Fails OPEN."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import allow, block, run  # noqa: E402

IN_SCOPE_BASENAMES = {"Company Profile.md", "CLAUDE.md", "MEMORY.md", "Client Note.md"}
HEADING = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
STATE_LINE = re.compile(r"^- \*\*(?P<key>[^*]+)\*\* \((?P<date>\d{4}-\d{2}-\d{2})\): \S")


def in_scope(path):
    p = Path(str(path))
    if p.name in IN_SCOPE_BASENAMES:
        return True
    return p.suffix == ".md" and p.parent.name == "memory"


def _section(content, title):
    m = re.search(r"^## " + re.escape(title) + r"\s*$(.*?)(?=^## |\Z)", content, re.MULTILINE | re.DOTALL)
    return m.group(1) if m else None


def check_content(path, content):
    if not in_scope(path):
        return None
    headings = [h.strip() for h in HEADING.findall(content)]
    n_state = sum(1 for h in headings if h.lower() == "current state")
    n_log = sum(1 for h in headings if h.lower() == "log")
    if n_state > 1:
        return "BLOCKED: this file would have two '## Current State' sections. One section says what is true now; put the lines in the existing block."
    if n_log > 1:
        return "BLOCKED: this file would have two '## Log' sections. Append to the existing Log."
    if n_state == 0:
        return None
    for h in headings:
        if h.lower() in ("recent activity", "recent decisions"):
            return ("BLOCKED: '## " + h + "' cannot coexist with '## Current State'. "
                    "Events go to '## Log' (append, dated); current values replace their line in Current State.")
    body = _section(content, "Current State") or ""
    keys = {}
    for line in body.splitlines():
        if not line.startswith("- "):
            continue
        m = STATE_LINE.match(line)
        if not m:
            return ("BLOCKED: every Current State line must be '- **Key** (YYYY-MM-DD): value' with the date "
                    "the value was verified. Offending line: " + line[:120])
        key = m.group("key").strip().lower()
        if key in keys:
            return "BLOCKED: duplicate Current State key '" + m.group("key").strip() + "'. Replace the existing line instead of adding one."
        keys[key] = True
    return None


def resulting_content(tool_name, tool_input):
    tool_input = tool_input or {}
    path = str(tool_input.get("file_path", ""))
    if not path or not in_scope(path):
        return None
    if tool_name == "Write":
        return path, str(tool_input.get("content", ""))
    if tool_name in ("Edit", "MultiEdit"):
        current = Path(path).read_text(encoding="utf-8")
        edits = tool_input.get("edits") if tool_name == "MultiEdit" else [tool_input]
        for e in edits or []:
            old, new = str(e.get("old_string", "")), str(e.get("new_string", ""))
            if not old:
                continue
            current = current.replace(old, new) if e.get("replace_all") else current.replace(old, new, 1)
        return path, current
    return None


def main(payload):
    res = resulting_content(payload.get("tool_name", ""), payload.get("tool_input") or {})
    if res is None:
        allow()
    path, content = res
    msg = check_content(path, content)
    if msg:
        block(msg)
    allow()


if __name__ == "__main__":
    run(main)
