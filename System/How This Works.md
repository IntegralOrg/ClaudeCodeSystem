---
type: reference
created: 2026-10-08
updated: 2026-10-08
---
# How This Works

**What it is.** This vault is a folder of Markdown files that lives in a Git repository, and Claude is the assistant that reads and writes those files for you. You talk to Claude; Claude changes files; the changes are saved to the repository automatically; scheduled routines read the repository every night and write down what they found. The files are the memory. Nothing important lives only in a conversation.

## The loop

1. **You talk to Claude** (in Claude Desktop, or in a cloud session on the web or your phone).
2. **Files change.** A task goes into `Inbox/`, a client page gets a new line, the daily note grows.
3. **The landing hook saves the work.** When Claude finishes a turn, a hook commits the changes and puts them on `main`, the one branch that counts. In a cloud session the cloud landing script does it; on a computer, `scripts/land-local.sh` does it. A local session also pulls the latest from GitHub when it starts (fast-forward only, never over your unsaved edits). You never see Git.
4. **Routines read the repository on a schedule** (below) and write their results back as files.
5. **The record is files too:** the daily note in `Work/Daily/`, and the hygiene report in `_generated/vault-hygiene/`.

## What runs when

| Routine | When | What it touches |
|---|---|---|
| End of Day | Weeknights, 11 PM your time | Reads your calendar and email (and calls and Slack when connected), writes `Work/Daily/<date>.md`, updates client pages, checks that the other routines ran, and reaches you outside the vault when something needs you |
| Vault Hygiene | Every night, 1 AM your time | Backfills missing frontmatter, reports repeated frontmatter keys, finds duplicate subjects, marks canonical files, writes `_generated/vault-hygiene/audit-log.md` |

Their definitions are in `System/routines/`; whether each is live is in `System/Routines.md`.

## Where things live

- `Work/`: clients, projects, and daily notes.
- `Personal/`: anything private to you.
- `Resources/`: reference material, how-tos, notes worth keeping.
- `System/`: these guidance files and the routine definitions. Claude answers questions about the system from here.
- `_generated/`: files the machinery writes (hygiene reports, the landing log, alert state). Read them; do not hand-edit them.

## The brakes, stated plainly

The committed settings let Claude run every Bash command without asking first, so a session can work without stopping at each step. The only brake on that is the **guard** hook (`scripts/hooks/guard_secrets.py`). It blocks reading the credentials file, force pushes, hard resets, recursive force deletes outside temporary folders, and SQL drops. It is not a sandbox: a plain `rm -r` passes, and so does anything the guard was not written to recognise. Your protection against a bad day is the Git history (everything is recoverable from it) plus your own attention to what Claude says it is about to do.

## What a merge conflict looks like here

Markdown files use `merge=union`, which means that when two sessions change the same lines of the same file, Git keeps both versions instead of stopping. You never get a blocked save, and you never lose a line. The cost is that you can see a repeated line, and a file's frontmatter (the block between the `---` lines at the top) can gain a duplicate line such as two `updated:` entries. The autosync workflow repairs those duplicates when it merges branches. A duplicate left by a local rebase is not repaired automatically: Vault Hygiene's frontmatter check reports it, and it is fixed by hand.

## When something seems off

- `Work/Daily/<today>.md`, the **Routine health** section: End of Day writes whether each routine ran and which keys or connectors are missing.
- `_generated/vault-hygiene/audit-log.md`: the newest `## YYYY-MM-DD` heading tells you when Vault Hygiene last ran.
- `_generated/landing.log`: one line per attempt to save your work. A line saying `on branch` means the session was on a side branch, where landing deliberately does nothing (landing only runs on `main`); a line saying `locked` means another save was in progress.

## How you are told, even with no connectors

Two small hooks run at the start of every session (cloud or local) and speak first, without needing Gmail or a calendar:

- `landing_health.py` reads `_generated/landing.log` and says so when saves have been failing, or when landing appears to be switched off (several `on branch` or `locked` lines in a row).
- `routine_health.py` says when a routine has not run when it should (End of Day or Vault Hygiene), using the daily notes, the hygiene log, and the `live_since` lines in `System/Routines.md`.

When Gmail or Google Calendar is connected, End of Day adds a push outside the vault: an email to the address in the `## Owner` section of `CLAUDE.md`, or, if it cannot send, an all-day calendar event titled "Brain needs you: <reason>". It sends a given reason at most once a week.

## Getting a new version

Type `/update` (or paste the prompt in the template's README). The agent takes the newest version of the system in full, keeps what you have built, and reports in a few lines. Details: `System/Updating.md`.
