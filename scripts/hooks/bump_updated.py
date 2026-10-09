#!/usr/bin/env python3
"""PostToolUse on Edit/MultiEdit/Write: keep a note's `updated:` frontmatter date current.

Acts only on a Markdown file inside the project whose frontmatter already has exactly one
top-level `updated:` key. Never adds the key, never touches the body, preserves line endings
and a trailing comment, and writes a bare date. Skips the template repository itself.
Prints nothing. Fails OPEN: any problem means do nothing."""
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import project_dir, run  # noqa: E402

try:
    from _common import is_template_repo
except ImportError:  # an older _common.py without the helper: same check, kept local
    def is_template_repo(root):
        try:
            import subprocess
            p = subprocess.run(["git", "--no-optional-locks", "-C", str(root), "remote", "get-url", "origin"],
                               capture_output=True, text=True, timeout=2)
            url = p.stdout.strip() if p.returncode == 0 else ""
            m = re.search(r"[/:]([^/:]+)/([^/:]+?)(?:\.git)?/*$", url)
            repo = ("%s/%s" % (m.group(1), m.group(2))).lower() if m else ""
        except Exception:
            return False
        return repo in ("integralorg/claudecodesystem", "integralorg/claudecodesystem-cloud",
                        "stackdev223/claudecodesystem")

SKIP_DIRS = {".git", "_generated", ".claude", "node_modules", ".superpowers", ".handoffs"}
MAX_FRONTMATTER_LINES = 60
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KEY_RE = re.compile(r"^updated[ \t]*:")
LINE_RE = re.compile(r"^(updated:)([ \t]*)(\"[^\"]*\"|'[^']*'|[^\s#\"']*)([ \t]+#.*?)?([ \t]*)(\r?\n|\r)?$",
                     re.DOTALL)


def today():
    override = os.environ.get("BUMP_UPDATED_TODAY", "")
    return override if DATE_RE.match(override) else date.today().isoformat()


def bump(text, new_date):
    """Return the new text, or None when nothing should change."""
    lines = text.splitlines(True)
    if not lines or lines[0].rstrip("\r\n").rstrip() != "---":
        return None
    end = None
    for i in range(1, min(len(lines), MAX_FRONTMATTER_LINES)):
        if lines[i].rstrip("\r\n").rstrip() == "---":
            end = i
            break
    if end is None:
        return None
    hits = [i for i in range(1, end) if KEY_RE.match(lines[i])]
    if len(hits) != 1:
        return None
    i = hits[0]
    m = LINE_RE.match(lines[i])
    if not m:
        return None
    value = m.group(3)
    if value[:1] in ("|", ">"):
        return None
    if value.strip("\"'") == new_date:
        return None
    sep = m.group(2) or " "
    new_line = m.group(1) + sep + new_date + (m.group(4) or "") + (m.group(5) or "") + (m.group(6) or "")
    if new_line == lines[i]:
        return None
    lines[i] = new_line
    return "".join(lines)


def write_atomic(path, data):
    mode = os.stat(path).st_mode
    fd, tmp = tempfile.mkstemp(prefix=".bump_updated.", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, mode & 0o7777)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def eligible(path, root):
    if not path.lower().endswith(".md") or not os.path.isfile(path):
        return False
    try:
        rel = Path(path).relative_to(root)
    except ValueError:
        return False
    return not any(part in SKIP_DIRS for part in rel.parts[:-1])


def main(payload):
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    fp = tool_input.get("file_path")
    if not isinstance(fp, str) or not fp:
        return
    root = os.path.realpath(project_dir(payload))
    if not os.path.isabs(fp):
        fp = os.path.join(root, fp)
    path = os.path.realpath(fp)
    if not eligible(path, root) or is_template_repo(root):
        return
    with open(path, "rb") as f:
        raw = f.read()
    new = bump(raw.decode("utf-8"), today())
    if new is None:
        return
    write_atomic(path, new.encode("utf-8"))


if __name__ == "__main__":
    run(main)
