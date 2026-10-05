---
name: eod
description: End of day processing: gather data from all sources, process transcripts, sync tasks, and build tomorrow's plan.
---

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

1. Run `date` to get today's date and current time ([Your Timezone])
2. Source the `.env` file at the vault root to load API credentials
3. Set variables:
   - `TODAY` = current date in YYYY-MM-DD format
   - `TOMORROW` = next calendar day in YYYY-MM-DD format
   - `VAULT` = absolute path to the vault root
   - `MANIFEST` = `/tmp/eod-manifest-TODAY.md`
4. Create the manifest file at `$MANIFEST`:
   ```markdown
   # EOD Manifest -- TODAY

   ## Items

   | # | Item | Client | Type | Source | Routed To | Status |
   |---|------|--------|------|--------|-----------|--------|
   ```
5. Check CLAUDE.md for a time tracking integration (look for an uncommented entry mentioning time tracking, Rize, Toggl, or similar). Set `HAS_TIME_TRACKING` = true or false.

---

## 1. Gather

Source "$VAULT/.env" before any API calls. The manifest is at $MANIFEST.

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
5. SLACK CHECK: For each workspace token in `.env` (`SLACK_TOKEN_WORKSPACE_*`), check unread DMs and mentions. Route items to client inbox files. Log to manifest.
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

Source "$VAULT/.env" before any API calls. Read the calendar cache at `/tmp/eod-calendar-$TODAY.md` for cross-referencing.

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

Read the manifest at `$MANIFEST`. Read the calendar cache at `/tmp/eod-calendar-$TODAY.md`. If `/tmp/eod-time-$TODAY.md` exists, read the time tracking summary.

Create the daily note at `$VAULT/Work/Daily/$TODAY.md` with these sections:

1. Date and day of week as the title
2. MEETINGS: List meetings attended today
3. KEY OUTCOMES: Decisions made and important results
4. TASKS COMPLETED: Items marked done today
5. TASKS ADDED: New items routed today
6. TIME SUMMARY: Hours per client and work type, or "Time tracking not configured"
7. SUMMARY: 2-3 sentence narrative of the day

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

## Final Step: Persist to Git

The vault runs in a temporary cloud workspace -- anything not pushed is lost when the session ends. After printing the summary:

1. `git add -A`
2. `git commit -m "EOD close-out $TODAY"`
3. `git push` -- if the push is rejected because the remote moved, run `git pull --rebase`, then push again

If the working tree is clean, say so and skip the commit. If the push still fails after a retry, tell the user plainly: tonight's close-out exists only in this workspace until a push succeeds.
