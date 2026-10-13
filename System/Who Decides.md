---
type: reference
created: 2026-10-13
updated: 2026-10-13
---
# Who Decides

**What it is.** Your system improves itself from its own work. This page says which changes it makes on its own, which it sends to your onboarding contact, and what it will never ask you to decide.

**Our recommendation.** Let it. You are never the approver: nothing in this system waits for you to say yes. Read the one line it leaves in your daily note when it has fixed something, and send along the report it writes when something is beyond it.

## What your system fixes on its own

When the same friction shows up across several sessions (it keeps forgetting a rule, a routine keeps tripping over the same wording, a note keeps landing in the wrong folder), the nightly Vault Hygiene run fixes it the same night. The things it changes on its own are the ones written in plain words:

- a rule in `CLAUDE.md`, its instruction manual,
- a memory file,
- the wording of a command in `.claude/commands/`,
- a guidance page in `System/`,
- its own list of recurring themes in `_generated/Themes.md`.

Every fix is one change, logged with its reason in `_generated/vault-hygiene/audit-log.md` and saved into your vault's history by the same landing that saves your notes, so any one of them can be undone. The next night's run checks whether the fix held; a fix that did not hold is tried again differently, not marked done. This tuning step is part of the nightly run; if your system is older than it, `/update` brings it in.

## What it sends to your contact

Anything technical is never changed on its own and never put to you: scripts, hooks, guard rules, credentials, routines, settings files, and anything that looks like a bug in the system itself. For those, your system writes a short report with names and counts only (which routine, what kind of error, how many times, first and last date, which files) and nothing from your notes. The report is a note in your `Inbox/` folder, written the same way `System/Getting Help.md` describes, and your system leaves one line in your daily note asking you to reach out to your contact for support with that file. It never emails anyone on your behalf. A bug that every system shares is fixed once in the template and reaches you through `/update`.

## What it never asks you

- It never asks you to approve, review, or choose between fixes.
- It never shows you a queue, a card, or a list of pending decisions.
- It never asks you to read a log or run a command to confirm something worked. The next night's run is the confirmation.

The most you will see is one plain line at the end of a run or in `Work/Daily/<date>.md`: "Fixed: it kept forgetting your time zone."

## What changes afterwards

Your system keeps getting better at the things you do with it, without a meeting about it. The record of every change it made is in `_generated/vault-hygiene/audit-log.md`; the record of what it sent on is in `Inbox/` and your daily notes.
