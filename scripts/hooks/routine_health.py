#!/usr/bin/env python3
"""SessionStart: the connector-free push channel for routine health. Reads repo state only:
the newest daily note (End of Day's output), the newest heading in the Vault Hygiene audit log, the
newest Monthly Review output, and `live_since:` values in System/Routines.md. Prints one line per
stale routine, prefixed "Tell the user first:". A routine that never produced output and has no
live_since is "not yet run" (End of Day's job) and is never reported. Silent when nothing is stale,
silent in the template repository, fails open. ROUTINE_HEALTH_TODAY=YYYY-MM-DD overrides today (tests)."""
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import is_template_repo, project_dir, run  # noqa: E402

EOD_MAX_WEEKDAYS = 3
HYGIENE_MAX_DAYS = 2
MONTHLY_MAX_DAYS = 35
NOT_LIVE_AFTER_DAYS = 2

# slug -> (display name, aliases matched in System/Routines.md)
KNOWN = {
    "eod": ("EOD", ("eod", "end of day", "end-of-day")),
    "vault-hygiene": ("Vault Hygiene", ("vault hygiene", "vault-hygiene")),
    "monthly-review": ("Monthly Review", ("monthly review", "monthly-review")),
}
DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
SETUP_DONE_RE = re.compile(r"setup\b.{0,20}\b(complete|completed|finished|done)\b|\b(completed|finished)\b.{0,20}\bsetup\b", re.I)


def today_date():
    forced = os.environ.get("ROUTINE_HEALTH_TODAY")
    try:
        return date.fromisoformat(forced) if forced else date.today()
    except ValueError:
        return date.today()


def to_date(text):
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def weekdays_between(start, end):
    """Weekdays in (start, end]."""
    n, d = 0, start
    while d < end:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def daily_notes(root):
    out = []
    for f in (root / "Work" / "Daily").glob("*.md"):
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})", f.stem)
        d = to_date(m.group(1)) if m else None
        if d:
            out.append((d, f))
    return sorted(out)


def newest_audit_heading(root):
    f = root / "_generated" / "vault-hygiene" / "audit-log.md"
    if not f.is_file():
        return None
    dates = [to_date(m.group(1)) for m in re.finditer(r"^##\s+(\d{4}-\d{2}-\d{2})", f.read_text(encoding="utf-8", errors="replace"), re.M)]
    dates = [d for d in dates if d]
    return max(dates) if dates else None


def newest_monthly_output(root):
    """Newest Monthly Review output date. Convention: Work/Monthly/YYYY-MM-DD Monthly Review.md; a month-only
    name such as 2026-09.md counts as the last day of that month."""
    files = list((root / "Work" / "Monthly").glob("*.md")) + list((root / "Work").glob("Monthly Review*")) \
        + list((root / "Work").glob("*/Monthly Review*"))
    best = None
    for f in files:
        d = None
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", f.name)
        if m:
            d = to_date(m.group(0))
        else:
            m = re.search(r"(\d{4})-(\d{2})(?!\d)", f.name)
            if m:
                y, mo = int(m.group(1)), int(m.group(2))
                if 1 <= mo <= 12:
                    d = (date(y + (mo == 12), mo % 12 + 1, 1) - timedelta(days=1))
        if d and (best is None or d > best):
            best = d
    return best


def norm_heading(text):
    """Heading text without numbering ('1.'), parentheses and markup, lowercased."""
    t = re.sub(r"\([^)]*\)", " ", text)
    t = re.sub(r"[*_`]", "", t)
    t = re.sub(r"^\s*\d+\s*[.)]\s*", "", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def routine_names(root):
    """slug -> set of lowercase names a heading may start with (slug, title, known aliases)."""
    names = {slug: set(a) for slug, (_, a) in KNOWN.items()}
    for rf in (root / "System" / "routines").glob("*.md"):
        n = names.setdefault(rf.stem, set())
        n.update({rf.stem, rf.stem.replace("-", " ")})
        try:
            m = re.search(r"^title:\s*(.+)$", rf.read_text(encoding="utf-8", errors="replace"), re.M)
        except Exception:
            m = None
        if m:
            n.add(norm_heading(m.group(1).strip().strip("\"'")))
    return names


def parse_routines(root):
    """{slug: live_since date or None} for routines with a `## <title>` section in System/Routines.md; {} when the
    file is absent. A section runs to the next `## ` heading; only its FIRST `live_since:` bullet counts
    (a date, or `not live`), so a later routine's value is never attributed to an earlier one."""
    f = root / "System" / "Routines.md"
    if not f.is_file():
        return {}
    sections = []  # [normalized heading, [body lines]]
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        if re.match(r"^##\s+\S", line):
            sections.append([norm_heading(line[2:]), []])
        elif sections:
            sections[-1][1].append(line)
    found = {}
    for slug, names in routine_names(root).items():
        for heading, body in sections:
            if any(heading.startswith(n) for n in names if n):
                live = None
                for line in body:
                    m = re.match(r"^\s*(?:[-*]\s*)?live_since:\s*(.*)$", line)
                    if m:
                        d = DATE_RE.search(m.group(1))
                        live = to_date(d.group(0)) if d else None
                        break
                found[slug] = live
                break
    return found


def setup_date(notes):
    """Date of the newest daily note carrying a setup-completion line."""
    for d, f in reversed(notes):
        try:
            if any(SETUP_DONE_RE.search(l) for l in f.read_text(encoding="utf-8", errors="replace").splitlines()):
                return d
        except Exception:
            continue
    return None


def display(root, slug):
    if slug in KNOWN:
        return KNOWN[slug][0]
    try:
        text = (root / "System" / "routines" / f"{slug}.md").read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^title:\s*(.+)$", text, re.M)
        if m:
            return m.group(1).strip().strip("\"'")
    except Exception:
        pass
    return slug.replace("-", " ").title()


def problems(root, today):
    out = []
    listed = parse_routines(root)
    notes = daily_notes(root)

    eod_ref = notes[-1][0] if notes else listed.get("eod")
    if eod_ref and weekdays_between(eod_ref, today) > EOD_MAX_WEEKDAYS:
        out.append(f"Routine EOD has not run since {eod_ref.isoformat()} ({weekdays_between(eod_ref, today)} weekdays)")

    hyg_ref = newest_audit_heading(root) or listed.get("vault-hygiene")
    if hyg_ref and (today - hyg_ref).days > HYGIENE_MAX_DAYS:
        out.append(f"Routine Vault Hygiene has not run since {hyg_ref.isoformat()}")

    mon_ref = newest_monthly_output(root) or listed.get("monthly-review")
    if mon_ref and (today - mon_ref).days > MONTHLY_MAX_DAYS:
        out.append(f"Routine Monthly Review has not run since {mon_ref.isoformat()}")

    done = setup_date(notes) if listed else None
    if done and (today - done).days >= NOT_LIVE_AFTER_DAYS:
        for slug, live in listed.items():
            if live is None:
                out.append(f"Routine {display(root, slug)} is still not live {(today - done).days} days after setup")
    return out


def main(payload):
    root = Path(project_dir(payload))
    if is_template_repo(root):
        return
    found = problems(root, today_date())
    if not found:
        return
    text = "\n".join(f"Tell the user first: {p}" for p in found)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}))


if __name__ == "__main__":
    run(main)
