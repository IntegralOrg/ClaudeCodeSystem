# End of Day

Run this before wrapping up for the day. It processes everything that happened today and builds tomorrow's plan.

Default mode: run the full EOD in this one command. Claude Code can handle long sessions, so do not split this into sub-agents unless this specific vault proves too large in practice.

---

## Core Rules

Follow these rules exactly:

1. Work in one session unless there is a concrete reason not to.
2. Write important state to disk as you go: manifest, inbox files, temp files in `/tmp/`.
3. Route items immediately when you extract them. Do not hold large batches in memory.
4. If time tracking is not configured, skip that section entirely.
5. If one external integration fails, continue with the rest and report the failure at the end.
6. Keep the final output user-focused: what was gathered, what changed, and what tomorrow looks like.

Advanced fallback:
- If this vault later proves too heavy for one run, split `/eod` into `gather`, `sync`, `time`, `note`, and `plan` phases.
- Pass state through files on disk, not conversation memory.

---

## Setup

1. Run `python3 scripts/check-keys.py --routine eod` and list the connectors available in this session (name each; note any of Gmail, Google Calendar that is absent). Hold the findings (missing keys, missing connectors) for Section 4 to include in the daily note under `## Routine health`. If this run's keys check exits 0, then in `System/Routines.md`, under this routine's `## <title>` heading, if the first bullet reads `- live_since: not live` (or is missing), change that same bullet to `- live_since: <today's date>`; never add a second live_since bullet. If the script exits 1 or a required connector is absent, continue with what is available.
2. Compute today's date and time in the owner's time zone, never the container's clock (cloud containers run on UTC, so a bare `date` can already be tomorrow at 11 PM Eastern): read the IANA zone from `## Owner` in `CLAUDE.md`, then run `TZ=<that zone> date +%F` for the date and `TZ=<that zone> date` for the time
3. Do not read or source the credentials file. Scripts load credentials themselves (`scripts/envload.py`); for a one-off external call use `python3 scripts/with-env.py -- <command>`
4. Set variables:
   - `TODAY` = current date in YYYY-MM-DD format
   - `TOMORROW` = next calendar day in YYYY-MM-DD format
   - `VAULT` = absolute path to the vault root
   - `MANIFEST` = `/tmp/eod-manifest-TODAY.md`
5. Create the manifest file at `$MANIFEST`:
   ```markdown
   # EOD Manifest -- TODAY

   ## Items

   | # | Item | Client | Type | Source | Routed To | Status |
   |---|------|--------|------|--------|-----------|--------|
   ```
6. Check CLAUDE.md for a time tracking integration (look for an uncommented entry mentioning time tracking, Rize, Toggl, or similar). Set `HAS_TIME_TRACKING` = true or false.
7. Read `_generated/vault-hygiene/audit-log.md` to find the newest date of the form `## YYYY-MM-DD` (Vault Hygiene's last run). If it is more than 2 days old, flag it as `STALE` for the push channel later.

Cloud-workspace note: in an ephemeral cloud container, credentials usually arrive as exported environment variables rather than a logins file. Scripts read them through `scripts/envload.py`, and a one-off call goes through `python3 scripts/with-env.py -- <command>`; never read or source a logins file, and never create a stub one to satisfy a script. Also expect that some raw third-party APIs return 503s when called from datacenter IPs -- prefer an MCP connector for those services in the cloud, and do not retry the raw endpoint in a loop.

---

## 1. Gather

Credentials are loaded inside scripts (`scripts/envload.py`); for a one-off call use `python3 scripts/with-env.py -- <command>`. Never read or source the credentials file. The manifest is at $MANIFEST.

Continuity check first: look at the newest note in `Work/Daily/` and the date on the current `Inbox/Today.md`. If the newest daily note is not from the previous calendar day, one or more days have no note. Say so explicitly at the top of the run and name the missing dates before proceeding. Date-scoped API fetches only cover the day you run for, so a silent gap means those days are never captured. Do not backfill mid-run; just surface it.

Critical rules:
- Route-as-you-go: route every item and log it to the manifest immediately.
- Dedup: before adding a task, check if it already exists in the target file.
- Only create `- [ ]` tasks for clear next actions. Recaps and status updates are notes, not tasks.
- No empty section headers.

Execute these steps in order:

1. BRAIN DUMP TRIAGE: Read `Inbox/[YourCompany].md`. Extract the `## Brain Dump` section. Classify each item by client. Route work items to the correct client inbox file. Remove routed items from the Brain Dump. Leave personal items and ideas in place. Log every routed item to the manifest.
2. CALL TRANSCRIPTS: If a transcript fetcher script exists (for example `scripts/fathom-fetch.py`), run it and parse the results. For each call, extract action items, decisions, and follow-ups. Route to client inbox files. Log to manifest. If no transcript service is configured, skip this step.
3. TOMORROW'S CALENDAR: Get a Google OAuth access token using the refresh token. Fetch $TOMORROW's events from Google Calendar API. Format as a readable schedule. Write to `/tmp/eod-calendar-$TODAY.md`.
4. EMAIL CHECK: Reuse the Google OAuth token. Fetch today's emails via Gmail API (first 15-20 messages). Surface emails needing response. Route actionable items to client inbox files. Log to manifest.
5. SLACK CHECK: For each workspace token available to the scripts (`SLACK_TOKEN_WORKSPACE_*`), check unread DMs and mentions. Route items to client inbox files. Log to manifest.
6. COMPLETION CHECK: Only if at least one `Inbox/*.md` file has open items under `## Open Tasks`. Check every open task against what steps 2 to 5 just read, plus up to 30 targeted lookups of the thread or conversation a task cites. Clear evidence that it is finished (by anyone): check it off and log a `COMPLETED` manifest row. Partial evidence, or an inbound "no longer needed": log a `CONFIRM` row (at most 5) and leave the task alone. No evidence: nothing. Full rules: `eod-gather.md` Section 5.

When done, read back `$MANIFEST` and confirm it exists and has entries. Report totals by source and client.

---

## 2. Sync

Read the manifest at `$MANIFEST` for context on what was gathered.

Execute these steps:

1. DEDUPLICATION: Read each client inbox file in `Inbox/`. Find duplicate tasks (same or very similar text). When found, merge source notes and remove the duplicate. Count merges.
2. COMPLETED TASK CLEANUP: Find all checked items (`- [x]`) in client files. Move them to the Completed section of the same file with today's date. Count moved items.
3. TASK SYNC: For new `action-owner` items in the manifest, create corresponding tasks in your task manager using MCP tools. For tasks marked done today, update their status. Count synced items.
4. VAULT HYGIENE: Flag items in Open Tasks older than 14 days with a `(stale)` marker. If today is Monday, archive all Completed sections to `Archive/Completed Week of $TODAY.md` and clear them from client files.

Report: items deduped, completed moved, tasks synced, stale items flagged.

---

## 3. Time Tracking (Optional)

Only run this section if `HAS_TIME_TRACKING` is true.

Credentials are loaded inside scripts (`scripts/envload.py`); for a one-off call use `python3 scripts/with-env.py -- <command>`. Never read or source the credentials file. Read the calendar cache at `/tmp/eod-calendar-$TODAY.md` for cross-referencing.

Execute these steps:

1. FETCH SESSIONS: Query the time tracking API for today's sessions. Convert local timezone start/end of day to UTC for the query.
2. GAP DETECTION: Compare sessions against calendar events. Flag untracked periods longer than 15 minutes during work hours.
3. CLASSIFICATION: Classify each session on two axes:
   - Client: which client is the time for
   - Work type: delivery, sales, meeting, admin, internal
4. Write the classified session summary to `/tmp/eod-time-$TODAY.md` with a table: session, start, end, hours, client, work type.

Report: total hours tracked, hours per client, hours per work type, number of gaps.

---

## 4. Daily Note

Read the manifest at `$MANIFEST`. Read the calendar cache at `/tmp/eod-calendar-$TODAY.md`. If `/tmp/eod-time-$TODAY.md` exists, read the time tracking summary. Read the keys-check findings from Setup step 1 and the connectors list from Setup step 1. Read `_generated/vault-hygiene/audit-log.md` to find the newest `## YYYY-MM-DD` heading (Vault Hygiene's last run date). If the audit-log does not exist and `System/Routines.md` shows `live_since: not live` (or no date) under `## Vault Hygiene`, note "Vault Hygiene: not yet run" for the health section (not STALE). If the audit-log does not exist but `System/Routines.md` shows a `live_since` date under `## Vault Hygiene`, that is STALE (the log vanished after the routine went live; open System/Routines.md and check the routine is scheduled). Otherwise, if the newest date in audit-log is more than 2 days old, flag it as STALE (open System/Routines.md and check the routine is scheduled). If `_generated/landing.log` exists, read its last line; otherwise note "cloud session, landing by hook".

Create the daily note at `$VAULT/Work/Daily/$TODAY.md` with these sections:

1. Date and day of week as the title
2. MEETINGS: List meetings attended today
3. KEY OUTCOMES: Decisions made and important results
4. TASKS COMPLETED: Items marked done today
5. TASKS ADDED: New items routed today
6. TIME SUMMARY: Hours per client and work type, or "Time tracking not configured"
7. ROUTINE HEALTH: Vault Hygiene freshness (OK or STALE, with date), missing keys (names only, or "none"), connectors (connected/missing by name), landing (last line or default)
8. SUMMARY: 2-3 sentence narrative of the day, ending with `Routine status: <ok | needs you: reason>`

Report: file path and brief stats.

---

## 5. Tomorrow's Plan

Tomorrow is `$TOMORROW`.

Read the manifest at `$MANIFEST`. Read the calendar at `/tmp/eod-calendar-$TODAY.md`. Read CLAUDE.md for the daily schedule skeleton, client priority tiers, and meeting window.

Generate `$VAULT/Inbox/Today.md` with these sections:

1. TITLE: `# Today -- [Day of week], [Month DD, YYYY]` using tomorrow's date
2. SCHEDULE TABLE: Build the day's skeleton from CLAUDE.md preferences and insert tomorrow's calendar events
3. MORNING EXCEPTIONS: Flag meetings before the preferred meeting window
4. TASKS: Select top 5-7 tasks from client inbox files, prioritized by tier, deadline, and freshness
5. CARRY FORWARD: Read today's `Inbox/Today.md`, detect unchecked tasks, and carry forward what still matters
6. MEETING PREP: Pull context for each meeting from profiles, transcripts, and open tasks
7. DEADLINE RADAR: Scan all client inbox files for deadlines in the next 7 days
8. NORTH STAR GOALS: Read strategic goals from client Company Profiles
9. TEAM PRIORITIES: Generate a copy/paste Slack message with primary focus, secondary tasks, and blockers
10. FOOTER: `*Generated by /eod at [current time] [timezone]*`

Overwrite the file completely using the Write tool.

Report: tomorrow's date, number of meetings, number of tasks selected, any carry-forward flags.

---

## 5.5 Vault Audit

Safety checkpoint first: `git add -A && git commit -m "pre-audit checkpoint"` (skip if the tree is clean). Then read `.claude/commands/vault-audit.md` and execute the nightly run. Every removal it makes goes to `_generated/vault-hygiene/audit-trash/` (kept 7 days), so any surprise is recoverable.

Report: `Vault audit: N moved, N merged, N staged, N amendments`

---

## 6. Graph Sync (Incremental)

Run the daily incremental graph sync on files that changed today. This keeps the knowledge graph current without a full rebuild.

Execute the process from `/graph-daily`:

1. CHANGED FILES: Find markdown files modified today.
2. FRONTMATTER: Add or complete frontmatter on changed files.
3. WIKI-LINKS: Add wiki-links for unlinked entity mentions in changed files.
4. TRANSCRIPT KNOWLEDGE: Extract key takeaways from any new transcripts and push to entity pages.
5. INDEX UPDATES: Add new files to `Graph/index.md` and relevant MOCs.

If the Graph folder does not exist or `/graph-sync` has never been run, skip this section and note: "Graph sync skipped -- run `/graph-sync` first to initialize."

Write sync report to `/tmp/eod-graph-$TODAY.md`.

Report: files synced, links added, takeaways extracted, index entries added.

---

## Summary

After all sections complete, print the final summary:

1. Read `$MANIFEST` and count total items by status
2. Report:
   - Gathered: [N] items from [sources]
   - Synced: [N] deduped, [N] tasks synced to task manager
   - Time: [N] hours tracked across [N] clients, or "skipped"
   - Daily note: `Work/Daily/$TODAY.md` created
   - Tomorrow's plan: `Inbox/Today.md` generated for `$TOMORROW`
   - Errors: list any integration or section failures
3. Print tomorrow's top 3 priorities from the generated `Today.md`

---

## Final Step: Status and Push Channel

End the daily note with one status line: `Routine status: <ok | needs you: <reason>>`. If Vault Hygiene is stale (marked STALE in Section 4), or any required keys or connectors are missing, build a list of stable dedupe keys:
- `vault-hygiene-stale` if Vault Hygiene's last run is more than 2 days old
- `key-missing:<NAME>` for each missing required key
- `connector-missing:<NAME>` for each missing required connector (Gmail, Google Calendar)

For each key, check `_generated/routine-alerts.json` (create if missing; treat malformed or missing as `{}`). Send a push (outside the vault) only if the key is absent from the JSON or its ISO date is 7 or more days ago. After sending, write today's date only for the keys actually sent, merge them into the JSON, and write it back. "Vault Hygiene: not yet run" never produces a push.

To send: read CLAUDE.md's Owner section and extract the owner's email address. If absent, skip email and use the calendar fallback.

Email route (preferred): Use the Gmail connector's send tool. Subject: `Brain needs you: <reason>` (the first missing item). Body (3 lines):
- What is stale or missing (Vault Hygiene, names of keys, names of connectors)
- The fix (from System/Routines.md or System/Connecting Tools.md)
- "reply not needed"

If the Gmail connector can only draft (does not send), create the draft AND proceed to calendar fallback.

Calendar fallback: Use Google Calendar connector. All-day event tomorrow. Title: `Brain needs you: <reason>`. Description: the fix from System/Routines.md or System/Connecting Tools.md.

Record which channel was used in the daily note after the status line: `(sent via Gmail | sent via calendar)`.

---

## Persist to Git

The vault runs in a temporary cloud workspace -- anything not committed and pushed is lost when the session ends. After printing the summary:

1. **Final render check.** If any task state changed after you generated tomorrow's plan (a late correction, a task marked done), re-run the render so the file you commit reflects the final state, not a stale mid-run snapshot.
2. **Set the commit identity first.** An ephemeral container has no configured author, so an unset identity produces malformed or misattributed commits: `git config user.name "<your name>"` and `git config user.email "<your git email>"`.
3. **Stage everything you wrote -- and verify it.** Run `git add -A`, then diff the staged list against the files you actually created this session. A `.gitignore` rule can silently exclude a new file; because the container is ephemeral, any written-but-unstaged file is lost permanently, not "synced some other way." Force-add (`git add -f <path>`) anything you intentionally created that the ignore rules block. Never stage secrets (`.env`, `*.pem`/`*.key`), large binaries, or backup directories.
4. `git commit -m "EOD close-out $TODAY"`. If the tree is clean, say so and skip.
5. **Rebase, then push.** `git fetch`, `git rebase origin/<base>`, then push.
   - Scoped conflict resolution: if the rebase conflicts *only* in regenerated files (the tomorrow's-plan render, `Graph/index.md`, `Graph/entity-registry.md`), keep this session's version and continue -- those always differ between machines and are safe to overwrite with the current run's output. If it conflicts in *authored* content (daily notes, transcripts, docs), `git rebase --abort` and stop; never auto-resolve authored content.
6. **If the harness restricts direct pushes to a `claude/...` branch** (common in cloud sessions), do not fight it with git. Push that branch, then land the base branch with a server-side PR merge: the GitHub MCP tools (create a PR base `<base>` head `<branch>`, then merge it), or `gh pr create --fill && gh pr merge --merge` where the CLI is available. A server-side merge honors the push restriction.
7. **A stranded branch is a loud failure, not "done."** If the work cannot reach the base branch (no PR tool available, merge rejected, or an authored-content conflict), leave it on the branch and report that at the TOP of the summary with the one-line command to land it locally. Never force-push.

If the working tree is clean, say so and skip the commit. If the push still fails, tell the user plainly: tonight's close-out exists only in this workspace until it lands.
