#!/usr/bin/env python3
"""Fence external text (transcripts, Slack, email, web) so it is data, not instructions.
Deterministic: wraps the text in a visible boundary and prefixes instruction-shaped lines."""
import argparse
import re
import sys

PATTERNS = [re.compile(p, re.IGNORECASE) for p in (
    r"ignore (all |the )?(previous|prior|above) instructions",
    r"^\s*(\[\d\d:\d\d:\d\d\]\s*)?(\*\*)?(system|assistant|user)\s*(\*\*)?\s*:",
    r"\byou are (now )?(a|an|the) ",
    r"\bdisregard\b",
    r"\bdo not tell\b",
    r"<\s*/?(system|instructions|tool_call|function)",
    r"BEGIN (SYSTEM|ADMIN)",
    r"\bclaude,? (please )?(run|execute|delete|send)\b",
)]
OPEN = '<!-- external-content source="{source}" trust="untrusted" flagged={n} -->'
CLOSE = "<!-- /external-content -->"


OPEN_RE = re.compile(r'^<!-- external-content source="([^"]*)" trust="untrusted" flagged=(\d+) -->\n')
TS_RE = re.compile(r"^(\[\d\d:\d\d:\d\d\])\s*")
MARKER = "[flagged]"
NEUTRALIZED_CLOSE = "<!-- [neutralized] /external-content -->"


def flag_lines(text):
    return [i for i, line in enumerate(text.splitlines()) if any(p.search(line) for p in PATTERNS)]


def _mark(line):
    """Prefix the marker; a leading [HH:MM:SS] stamp stays at column 0."""
    m = TS_RE.match(line)
    if m:
        return m.group(1) + " " + MARKER + " " + line[m.end():]
    return MARKER + " " + line


def _is_marked(line):
    m = TS_RE.match(line)
    rest = line[m.end():] if m else line
    return rest.startswith(MARKER + " ") or rest == MARKER


def _clean_source(source):
    """One-line label that cannot close the HTML comment or the attribute."""
    s = " ".join(str(source).split()).replace('"', "&quot;")
    return s.replace("--", "- -").replace(">", "&gt;").replace("<", "&lt;")


def _is_fenced(text, expected_source=None):
    """True only for output this module produced: exact open tag, close marker as the
    one and only close and the last non-empty line, every instruction-shaped line marked,
    and the declared count equal to the number of markers."""
    m = OPEN_RE.match(text)
    if not m:
        return False
    if expected_source is not None and m.group(1) != _clean_source(expected_source):
        return False
    lines = text.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines or lines[-1] != CLOSE or lines.count(CLOSE) != 1:
        return False
    inner = lines[1:-1]
    if any(CLOSE in l for l in inner):
        return False
    marked = sum(1 for l in inner if _is_marked(l))
    unmarked_bad = [l for l in inner if not _is_marked(l) and any(p.search(l) for p in PATTERNS)]
    return not unmarked_bad and marked == int(m.group(2))


def fence(text, source):
    if _is_fenced(text, source):
        return text
    text = text.replace(CLOSE, NEUTRALIZED_CLOSE)
    source = _clean_source(source)
    flagged = set(flag_lines(text))
    lines = [(_mark(l) if i in flagged else l) for i, l in enumerate(text.splitlines())]
    return "\n".join([OPEN.format(source=source, n=len(flagged)), *lines, CLOSE]) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    a = ap.parse_args()
    sys.stdout.write(fence(sys.stdin.read(), a.source))


if __name__ == "__main__":
    main()
