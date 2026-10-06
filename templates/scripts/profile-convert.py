#!/usr/bin/env python3
"""Convert a Company Profile to the Current State + Log shape. Lossless: bullets are
moved verbatim, never rewritten. Dry-run by default; --apply backs up then writes.
--skip-engagement-seed leaves only the Engagement status line (use when the scraped Engagement bullet is stale or contradicts the status)."""
import argparse
import difflib
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ACTIVITY_HEADINGS = ("recent activity", "recent decisions")
ENGAGEMENT_HEADINGS = ("engagement", "integral engagement", "engagement status", "engagement history")
DATE_BULLET = re.compile(r"^- \*{0,2}(\d{4}-\d{2}-\d{2})\*{0,2}:?\*{0,2}\s*(?:(?:[—–:]+|-+)\s+)?(.*)$")
SUB_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2}):?\s*(?:[—–-]+\s+)?(.*)$")
BARE_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2}|[A-Za-z]+\.? \d{1,2}(st|nd|rd|th)?,? \d{4}|\d{1,2}/\d{1,2}/\d{2,4})\.?$")
CURRENT_STATE_COMMENT = "<!-- One dated line per key. REPLACE a line when its value changes; never add a second line for the same key. -->"
LOG_COMMENT = "<!-- Append-only. Newest first. Never edit or delete an entry. -->"


class AlreadyConverted(Exception):
    pass


def _split(text):
    """Return (frontmatter, body). frontmatter includes both --- fences or is ''."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[: end + 4], text[end + 4:]
    return "", text


def _sections(body):
    """List of (level, title, lines) in order; level 0 is the preamble before any heading."""
    out, cur = [], [0, None, []]
    for line in body.splitlines():
        m = re.match(r"^(#{1,6}) (.+?)\s*$", line)
        if m:
            out.append(cur)
            cur = [len(m.group(1)), m.group(2), []]
        else:
            cur[2].append(line)
    out.append(cur)
    return out


def _log_entry(bullet):
    m = DATE_BULLET.match(bullet)
    if m:
        return m.group(1), f"- ({m.group(1)}) {m.group(2)}"
    return "0000-00-00", "- (undated) " + bullet[2:] if bullet.startswith("- ") else "- (undated) " + bullet


def _junk_seed(line):
    t = line.strip()
    return len(t) < 15 or not re.search(r"[A-Za-z]", t) or bool(BARE_DATE.match(t))


def convert(text, today, engagement, last_change, seed_engagement=True):
    if re.search(r"^## Current State\s*$", text, re.MULTILINE):
        raise AlreadyConverted("already has ## Current State")
    if re.search(r"^## Log\s*$", text, re.MULTILINE):
        raise AlreadyConverted("already has ## Log")
    fm, body = _split(text)
    sections = _sections(body)
    log, removed, kept, engagement_line = [], [], [], None
    i = 0
    while i < len(sections):
        level, title, lines = sections[i]
        i += 1
        if title and title.strip().lower() in ACTIVITY_HEADINGS:
            removed.append(title.strip())
            entries = []  # [date, [lines]]; a bullet or sub-heading starts one, other text continues it
            sub = []
            while i < len(sections) and sections[i][0] > level:  # nested sub-headings belong to this section
                sub.append(sections[i])
                i += 1
            def feed(body_lines, entries):
                for l in body_lines:
                    if DATE_BULLET.match(l):  # a dated bullet is always its own top-level entry
                        d, e = _log_entry(l)
                        entries.append([d, [e]])
                    elif l.strip() and entries:
                        entries[-1][1].append("  " + l)
                    elif l.strip():
                        entries.append(["0000-00-00", ["- (undated) " + l]])

            feed_top = [l for l in lines]
            # top-level undated "- " bullets are their own entries; under a sub-heading they are children
            for l in feed_top:
                if l.startswith("- "):
                    d, e = _log_entry(l)
                    entries.append([d, [e]])
                elif l.strip() and entries:
                    entries[-1][1].append("  " + l)
                elif l.strip():
                    entries.append(["0000-00-00", ["- (undated) " + l]])
            for _lv, stitle, slines in sub:
                m = SUB_DATE.match(stitle.strip())
                d, head = (m.group(1), f"- ({m.group(1)}) {m.group(2)}") if m else ("0000-00-00", "- (undated) " + stitle.strip())
                entries.append([d, [head]])
                feed(slines, entries)
            log.extend((d, "\n".join(ls)) for d, ls in entries)
            continue
        if title and title.strip().lower() in ENGAGEMENT_HEADINGS and engagement_line is None:
            for l in lines:
                if l.startswith("- "):
                    engagement_line = re.sub(r"^- (\*\*[^*]+\*\*:?\s*)?", "", l).strip()
                    break
        kept.append((level, title, lines))
    log.sort(key=lambda e: e[0], reverse=True)
    state = ["## Current State", CURRENT_STATE_COMMENT]
    seeded = []
    if engagement:
        state.append(f"- **Engagement status** ({today}): {engagement}")
        seeded.append("Engagement status")
    if engagement_line and not seed_engagement:
        print("warning: Engagement seed skipped (--skip-engagement-seed)", file=sys.stderr)
    elif engagement_line and (not last_change or last_change == today):
        print("warning: no usable git date (missing or today, the sync touches files daily); Engagement seed skipped", file=sys.stderr)
    elif engagement_line and _junk_seed(engagement_line):
        print(f"warning: Engagement seed looks like junk, skipped: {engagement_line!r}", file=sys.stderr)
    elif engagement_line:
        state.append(f"- **Engagement** ({last_change}): {engagement_line} (verify)")
        seeded.append("Engagement")
    out_lines = []
    inserted = False
    for level, title, lines in kept:
        if title is None:
            out_lines.extend(lines)
            continue
        out_lines.append("#" * level + " " + title)
        out_lines.extend(lines)
        if level == 1 and not inserted:
            out_lines.extend(["", *state, ""])
            inserted = True
    if not inserted:
        out_lines = [*state, "", *out_lines]
    out_lines.extend(["", "## Log", LOG_COMMENT, *[e[1] for e in log], ""])
    new_body = "\n".join(out_lines)
    new_body = re.sub(r"\n{3,}", "\n\n", new_body)
    if engagement and not fm:
        fm = f"---\nengagement: {engagement}\n---"
    elif engagement and fm:
        if re.search(r"^engagement:", fm, re.MULTILINE):
            fm = re.sub(r"^engagement:.*$", f"engagement: {engagement}", fm, flags=re.MULTILINE)
        else:
            fm = fm[:-4].rstrip("\n") + f"\nengagement: {engagement}\n---"
    return fm + ("\n" if fm and not new_body.startswith("\n") else "") + new_body, {
        "log_entries": len(log), "removed_sections": removed, "seeded": seeded}


def _last_change(path):
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", path.resolve().name], capture_output=True, text=True,
                             cwd=path.resolve().parent, timeout=5).stdout.strip()
        return out or None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--engagement", choices=["active", "maintenance", "ending", "retired", "prospect"])
    ap.add_argument("--skip-engagement-seed", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--trash-root", default="_generated/vault-hygiene/audit-trash")
    a = ap.parse_args()
    path = Path(a.file)
    text = path.read_text(encoding="utf-8")
    today = date.today().isoformat()
    try:
        new, rep = convert(text, today, a.engagement, _last_change(path), seed_engagement=not a.skip_engagement_seed)
    except AlreadyConverted as e:
        print(f"error: {path}: {e}", file=sys.stderr)
        sys.exit(1)
    if not a.apply:
        sys.stdout.writelines(difflib.unified_diff(text.splitlines(True), new.splitlines(True), str(path), str(path) + " (converted)"))
        print(f"\n# dry-run: {rep}")
        return
    trash = Path(a.trash_root) / today
    trash.mkdir(parents=True, exist_ok=True)
    (trash / (path.parent.name + "." + path.name)).write_text(text, encoding="utf-8")
    path.write_text(new, encoding="utf-8")
    print(f"converted {path}: {rep}; backup in {trash}")


if __name__ == "__main__":
    main()
