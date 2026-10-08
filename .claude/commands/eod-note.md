# EOD Phase 4: Daily Note

Generates the permanent daily note at `Work/Daily/YYYY-MM-DD.md`. Pulls from the manifest, calendar cache, client inbox files, and optional Rize time data. Writes one file and confirms.

**This is a short, non-interactive phase.** No user input needed. Read from disk, generate, write, done.

---

## Setup

1. Run `date` to get today's date (`YYYY-MM-DD`) and day of week
2. Read the manifest at `/tmp/eod-manifest-TODAY.md`
   - If missing: stop and tell the user to run Phase 1 first
3. Read today's calendar cache at `/tmp/eod-calendar-TODAY.md`
   - If missing: note "No calendar data available" and continue
4. Read all client inbox files from `Inbox/` to pull Completed sections
5. Check for Rize time summary at `/tmp/rize-summary-TODAY.md`
   - If missing: skip the time tracking section (don't warn)

---

## Generate

Build the daily note with these sections, in order. Omit any section that has no content, except `## Routine health` which is always present (never omitted).

```markdown
# YYYY-MM-DD (Day of Week)

## Meetings
- [Time] [Title] ([Attendees])
- ...

## Key Outcomes & Decisions
- [Decision or outcome from manifest, Type = decision/note]
- ...

## Tasks Completed
- [x] [Task description] ([Client])
- ...

## Tasks Added
- [ ] [Task description] ([Client]) -- Source: [source]
- ...

## Time Tracking
- Total tracked: [X hrs Y min]
- Top categories: [Category1] [time], [Category2] [time], ...

## Routine health
- Vault Hygiene: last ran <date>; <OK if within 2 days, else STALE>
- Keys: <missing key names only, or "none">
- Connectors: <connected / missing, by name>
- Landing: <last line of _generated/landing.log if the file exists; otherwise "cloud session, landing by hook">

## Summary
[2-3 sentence narrative: what the day looked like, what moved forward,
what carries into tomorrow. Write in first person, plain language.]
```

**Section details:**

- **Meetings**: Pull from `/tmp/eod-calendar-TODAY.md`. List each meeting with time, title, and key attendees. Past tense framing ("attended" not "attending").
- **Key Outcomes & Decisions**: Pull manifest rows where Type is `decision`, `note`, or `research`. Group by client if multiple clients are represented.
- **Tasks Completed**: Scan each `Inbox/<Client>.md` for items marked `- [x]` that were completed today. Include the client name in parentheses.
- **Tasks Added**: Pull manifest rows where Type is `action-owner`, `action-other`, or `followup`. Show the source so future-you knows where it came from.
- **Time Tracking**: Parse `/tmp/rize-summary-TODAY.md` for total time and category breakdown. Keep it to one or two lines.
- **Routine health**: Always present. Vault Hygiene's freshness (check for `## YYYY-MM-DD` in `_generated/vault-hygiene/audit-log.md`; if STALE, open System/Routines.md and check the routine is scheduled), missing keys from `check-keys.py --routine eod`, available/missing connectors from the session, and the landing log (read `_generated/landing.log`'s last line or note if the file doesn't exist). Night-one rule: if audit-log does not exist and `System/Routines.md` has no `live_since` for vault-hygiene, write "Vault Hygiene: not yet run" and do NOT treat as STALE.
- **Summary**: Write a brief narrative based on everything above. Mention the biggest win, any blockers, and what's queued for tomorrow.

---

## Write

1. Use the Write tool to create `Work/Daily/YYYY-MM-DD.md` (new file)
2. If the file already exists, warn the user and ask before overwriting

---

## Confirm

Print a short confirmation:

```
Daily note written: Work/Daily/YYYY-MM-DD.md
  Meetings: N | Completed: N | Added: N | Decisions: N
```

Phase 4 complete. Handoff to Phase 5 (Today.md generation).
