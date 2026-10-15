#!/usr/bin/env python3
"""The tools ledger: System/Tools.md, one `## <tool>` section per tool the owner named, first bullet `- status: ...`.

Status values (first words): not connected | connected <date> | key present <date> | skipped (<reason>).
The hooks read only the status bullet. Stdlib only; used by setup, the connect step, check-keys.py and tools_health.py.
"""
import re
from pathlib import Path

LEDGER = Path("System") / "Tools.md"
STATUS_VALUES = ("not connected", "connected", "key present", "skipped")
HEADER = ("# Tools\n\nOne section per tool the owner named at setup or later. The first bullet under each heading is the "
          "status and is the only line the hooks read.\n")
_BULLET = re.compile(r"^- (?P<key>[a-z ]+?):\s*(?P<value>.*?)\s*$")


def parse(text):
    entries, current = [], None
    for line in text.replace("\r\n", "\n").split("\n"):
        if line.startswith("## "):
            current = {"name": line[3:].strip(), "status": "", "essential": False, "how": "", "used_by": "",
                       "updated": "", "lines": []}
            entries.append(current)
            continue
        if current is None:
            continue
        current["lines"].append(line)
        m = _BULLET.match(line)
        if not m:
            continue
        key, value = m.group("key"), m.group("value")
        if key == "status" and not current["status"]:
            current["status"] = value
        elif key == "essential":
            current["essential"] = value.strip().lower() in ("yes", "true")
        elif key == "how":
            current["how"] = value
        elif key == "used by":
            current["used_by"] = value
        elif key == "updated":
            current["updated"] = value
    return entries


def load(root):
    f = Path(root) / LEDGER
    if not f.is_file():
        return []
    return parse(f.read_text(encoding="utf-8", errors="replace"))


def preamble_of(text):
    """Text before the first `## ` line, or HEADER when there is none."""
    text = text.replace("\r\n", "\n")
    head = text if not text.startswith("## ") else ""
    idx = text.find("\n## ")
    if idx != -1:
        head = text[:idx + 1]
    return head if head.strip() else HEADER


def render(entries, preamble=None):
    out = [(preamble if preamble and preamble.strip() else HEADER).rstrip("\n") + "\n"]
    for e in entries:
        body = "\n".join(e["lines"]).strip("\n")
        out.append(f"\n## {e['name']}\n{body}\n")
    return "".join(out)


def open_items(entries):
    ess = [e["name"] for e in entries if e["essential"] and e["status"].startswith("not connected")]
    other = [e["name"] for e in entries if not e["essential"] and e["status"].startswith("not connected")]
    return ess, other


def set_status(root, name, status, today):
    f = Path(root) / LEDGER
    if not f.is_file():
        return False
    status = " ".join(str(status).split("\r\n")).replace("\n", " ").replace("\r", " ")
    raw = f.read_text(encoding="utf-8", errors="replace")
    entries = parse(raw)
    for e in entries:
        if e["name"].lower() != name.lower():
            continue
        done_status = done_updated = False
        new_lines = []
        for line in e["lines"]:
            m = _BULLET.match(line)
            if m and m.group("key") == "status" and not done_status:
                new_lines.append(f"- status: {status}")
                done_status = True
            elif m and m.group("key") == "updated":
                new_lines.append(f"- updated: {today}")
                done_updated = True
            else:
                new_lines.append(line)
        if not done_status:
            new_lines.insert(0, f"- status: {status}")
        if not done_updated:
            new_lines.append(f"- updated: {today}")
        e["lines"] = new_lines
        e["status"], e["updated"] = status, today
        f.write_text(render(entries, preamble_of(raw)), encoding="utf-8")
        return True
    return False
