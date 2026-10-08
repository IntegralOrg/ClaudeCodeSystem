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
LIVE_RE = re.compile(r"live_since:\s*[\"']?(\d{4}-\d{2}-\d{2})")
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
    files = list((root / "Work" / "Monthly").glob("*.md")) + list((root / "Work").glob("Monthly Review*")) \
        + list((root / "Work").glob("*/Monthly Review*"))
    best = None
    for f in files:
        m = DATE_RE.search(f.name)
        if not m:
            continue
        d = to_date(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
        if d and (best is None or d > best):
            best = d
    if best:
        return best
    months = []
    for f in files:
        m = re.search(r"(\d{4})-(\d{2})(?!\d)", f.name)
        if m:
            d = to_date(f"{m.group(1)}-{m.group(2)}-01")
            if d:
                months.append(d)
    return max(months) if months else None


def parse_routines(root):
    """Return {slug: live_since date or None} for routines listed in System/Routines.md; {} when the file is absent."""
    f = root / "System" / "Routines.md"
    if not f.is_file():
        return {}
    names = {slug: set(a) for slug, (_, a) in KNOWN.items()}
    for rf in (root / "System" / "routines").glob("*.md"):
        names.setdefault(rf.stem, set()).update({rf.stem, rf.stem.replace("-", " ")})
    blocks = []  # (label text, body text)
    cur = None
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith("#"):
            cur = [s.lstrip("#").strip().lower(), ""]
            blocks.append(cur)
        elif s.startswith("|") or s.startswith(("-", "*")):
            if s.startswith("|"):
                cells = [c.strip() for c in s.strip("|").split("|")]
                label = (cells[0] if cells else "").lower()
            else:
                label = re.split(r"[:\u2014]", s.lstrip("-* "), 1)[0].strip().lower()
            blocks.append([label.strip("`* "), s])
            if cur is not None:
                cur[1] += s + "\n"
        elif cur is not None:
            cur[1] += s + "\n"
    found = {}
    for slug, aliases in names.items():
        for label, body in blocks:
            if label in aliases:
                m = LIVE_RE.search(body)
                live = to_date(m.group(1)) if m else None
                if found.get(slug) is None:
                    found[slug] = live
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
