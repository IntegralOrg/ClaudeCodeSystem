---
name: eod-gather
description: EOD Phase 1: Data gathering. Triage brain dump, fetch transcripts, calendar, email, and Slack.
---

# EOD Phase 1: Gather

Data gathering phase. Triages Brain Dump first, then fetches call transcripts through the connected notetaker, tomorrow's calendar, email, and Slack. Routes all items to inbox files immediately. Creates the manifest.

**This phase runs independently and writes all state to disk.** Later phases read from the manifest and inbox files, not from conversation context.

**Critical rule: Route-as-you-go.** Every item extracted MUST be routed to the correct client file AND logged to the manifest IMMEDIATELY.

**The vault is a Git repository in your cloud workspace.** There is no background file sync, so the built-in editor is safe for reads and writes -- when editing an Inbox file, read it, modify it, and write it back with the Edit or Write tool. The Write tool is fine for new files (transcripts, manifest).

**Critical rule: Tasks are flat bullets.** Do NOT create `### New from <source>` subsection headers for tasks. Append new tasks directly under `## Open Tasks` as flat bullets. Source context lives in the italic suffix at the end of each task (e.g., `*from Fathom: [Call Name] MM/DD*`). This keeps client files scannable as history accumulates. (`### Notes from <source>` headers under `## Notes` are still fine -- meeting notes benefit from source grouping, tasks do not.)

**Critical rule: EOD deduplication.** Before adding a task from a call recap, check if the same task already exists in the client file. If it does, update the source note (append "*also discussed X/X*") instead of creating a duplicate.

**Critical rule: EOD task ownership.** Team member actions become follow-up items for you (e.g., "Follow up: [Team Member] to deliver X"). Never frame other people's responsibilities as your direct tasks.

---

## Setup

1. Run `date` to get today's date and current time ([Your Timezone])
2. Do not read or source the credentials file. Scripts load credentials themselves (`scripts/envload.py`); for a one-off external call use `python3 scripts/with-env.py -- <command>`
3. Set `TODAY` as the current date in `YYYY-MM-DD` format and `TOMORROW` as the next calendar day
4. **Create the manifest file** at `/tmp/eod-manifest-TODAY.md`:
   ```markdown
   # EOD Manifest -- YYYY-MM-DD

   ## Items

   | # | Item | Client | Type | Source | Routed To | Status |
   |---|------|--------|------|--------|-----------|--------|
   ```

### Manifest Column Definitions
- **#**: Sequential number (1, 2, 3...)
- **Item**: Brief description of the action item
- **Client**: Client name ([Client A], [Client B], etc.) or "Cross-Client"
- **Type**: `action-owner`, `action-other`, `research`, `decision`, `followup`, `email-response`, `note`, plus `COMPLETED` and `CONFIRM` (written only by Section 5: Completion Check)
- **Source**: Where it came from (e.g., "Fathom: [Contact Name] call", "Email: from jack@...", "Slack: [Client A] DM")
- **Routed To**: File path where item was written (e.g., `Inbox/[Client A].md`)
- **Status**: checkmark once routed, `ORPHAN` if couldn't determine destination

---

## Section 0: Brain Dump Triage

Process the Brain Dump section in `Inbox/Today.md`. This is the user's quick-capture area throughout the day. Classify each item, route client-specific items to the correct client file, and clean up the Brain Dump.

1. **Read** `Inbox/Today.md` and extract the Brain Dump section (everything between `## Brain Dump` and the next `##` header).

2. **Parse each item** (bullets and sub-bullets). Skip items that are:
   - Already completed: `- [x]`
   - Already routed: contains `~~` strikethrough + "moved to"
   - Empty lines or section headers (`###`)

3. **Classify each remaining item** by client using these signals (in priority order):
   - **Explicit client name**: "[Client A]", "[Client B]", "[Client C]", "[Client D]", "[Client E]"
   - **Contact names**: Map each contact to their client. Example:
     - [Contact 1]/[Contact 2] = [Client A]
     - [Contact 3]/[Contact 4] = [Client B]
     - [Contact 5]/[Contact 6] = [Client C]
   - **Tool/product names**: Map tools to clients. Example:
     - Klaviyo/SamCart = [Client B]
     - Shopify = [Client A]
   - **Internal context** (hiring, team, SOPs, strategy): route to `Inbox/[YourCompany].md` Open Tasks
   - **Personal items** (health, travel, errands): leave in Brain Dump, do not route
   - **Ideas**: leave in Brain Dump, do not route
   - **Unclassifiable work items**: leave in Brain Dump, log as `ORPHAN` in manifest

4. **For Notes subsections** (e.g., `### Notes from Agency Check-in 3/16`):
   - If the notes contain items for a specific client, extract those bullets and route to that client's `## Notes` section
   - If the notes are cross-client (agency strategy, hiring, general), route to `Inbox/[YourCompany].md` Notes section
   - Meeting notes with mixed clients: split by client, route each subset to the correct file
   - Always route as plain bullets (NOT checkboxes) under a `### Notes from <source>` header in the client file

5. **Route the items** (read each file, modify it, write it back):
   a. For each client file that needs items added:
      - Read the file
      - Tasks (`- [ ]` items): append directly under `## Open Tasks` as flat bullets. Preserve source via the inline italic suffix `*from Brain Dump MM/DD*`. Do NOT create a `### New from Brain Dump MM/DD` subsection header.
      - Notes (plain bullets): insert under `## Notes` section, under a `### Notes from <source>` header
      - Dedup check: if the same task already exists in the client file, skip it (don't duplicate)
      - Write the file back
   b. Mark routed items in `Today.md` Brain Dump:
      - Tasks: change to `- [x] ~~<original text>~~ moved to <Client>.md ✅ TODAY`
      - Notes: remove from Brain Dump entirely (they now live in the client file's Notes section)
      - Personal items and ideas: leave in place (they don't route; they carry forward to tomorrow)
   c. Append a manifest row for each routed item with Source = "Brain Dump"

6. **Summary**: Print count of items routed per client, items left in Brain Dump, orphans.

---

## Section 1: Call Transcripts (through the connected notetaker)

1. Read `System/Tools.md`. Find the notetaker section (Fathom, Fireflies, Granola, tl;dv, Grain, Zoom, Tactiq, Circleback) whose status starts with `connected`. If there is none, hold the line `no notetaker connected; call transcripts skipped` with the Routine health findings from the keys and connectors check in `eod.md` step 1 (the note phase places them) and go to Section 2.

2. List today's meetings with that connector's tools, then fetch each transcript (and summary where the connector has one):

   | Notetaker | List today's meetings | Transcript (and summary) |
   |---|---|---|
   | Fathom | `list_meetings` (today's date range) | `get_meeting_transcript`, `get_meeting_summary` |
   | Fireflies | `get_transcripts` (today) | the transcript text in the same result |
   | Granola | `list_meetings` | `get_meeting_transcript` |
   | tldv | `search-meetings` (today) | `get-meeting-transcript`, `get-meeting-notes` |
   | Grain | `list_meetings` | `fetch_meeting_transcript`, `fetch_meeting_notes` |
   | Zoom | `recordings_list` (today) | `get_meeting_assets` |
   | Tactiq | `list_recent_meetings` | `get_transcript` |
   | Circleback | `SearchMeetings` (today) | `GetTranscriptsForMeetings` |

   The tool names come from the connector's own list in the session (the exact names can differ by version; use the ones the session shows). Save each transcript under `Work/Clients/<Client>/Transcripts/<date> - <title>.md` when the client is known, else `Work/Transcripts/`.

3. For each transcript, extract: action items for you (with deadlines), action items for others (as follow-ups), research items, decisions, follow-ups. Summary-only results are flagged low confidence.

Gather still routes tasks and Inbox notes from each transcript (step 5 below). What it does not do is write transcript takeaways into the client profile: decisions and other durable facts land in the profile's `## Log` (and `## Current State` when a fact changed) during the graph sync phase (`/graph-daily`), under the write-path rule in CLAUDE.md. A decision-only transcript therefore produces a note here and a Log entry there, never two profile writes.

4. Handle each meeting by what came back:
   - A transcript: extract as in step 3.
   - A summary only: extract from it and flag low confidence on the items.
   - Nothing (no transcript or summary): flag the call in the manifest.
   - Already saved by an earlier run today: still read it and extract action items if this is the first EOD run for the day.

   **Task vs. Note distinction**: Only create `- [ ]` items for clear, specific next actions. Meeting recaps without action items, status updates, and finalized decisions are Type `note` (not tasks).

5. **ROUTE IMMEDIATELY** (edit the Inbox files directly):
   a. Determine the client from the client named in the transcript's title or attendees (unknown routes to `Inbox/[YourCompany].md` and is marked ORPHAN)
   b. Tasks -> `Inbox/<Client>.md` under `Open Tasks`; cross-client/agency/hiring/internal -> `Inbox/[YourCompany].md` under `Open Tasks`
   c. Notes/decisions -> `## Notes` section (plain bullets, NOT checkboxes)
   d. Append a row to the manifest for each item
   e. If the client is unknown, route to `Inbox/[YourCompany].md` and mark `ORPHAN`
6. Confirm manifest item count matches extraction count

---

## Section 2: Tomorrow's Calendar

1. Read `System/Tools.md`. Find the calendar section (Google Calendar, or Microsoft 365 for Outlook) whose status starts with `connected`. If there is none, hold the line `no calendar connected; tomorrow's calendar skipped` with the Routine health findings from the keys and connectors check in `eod.md` step 1 (the note phase places them), write `No calendar connected` to `/tmp/eod-calendar-TODAY.md`, and go to Section 3.
2. List tomorrow's events (`TOMORROW`, start to end of day in the owner's time zone) with that connector's tools: the Google Calendar connector's event list, or the Microsoft 365 connector's calendar search. Use the tool names the session shows.
3. Format as readable list with times (your timezone), titles, attendees
4. Flag early meetings (before 9 AM) and back-to-backs
5. Write formatted schedule to `/tmp/eod-calendar-TODAY.md` for later phases

A vault on the full control Google path (the Connecting Tools Appendix, `System/Connecting Tools.md`) reads the calendar the way that Appendix's test does, through `python3 scripts/with-env.py`.

---

## Section 3: Email Check

1. Read `System/Tools.md`. Find the email section (Gmail, or Microsoft 365 for Outlook) whose status starts with `connected`. If there is none, hold the line `no email connected; email check skipped` with the Routine health findings from the keys and connectors check in `eod.md` step 1 and go to Section 4.
2. Search today's mail with that connector's tools: the Gmail connector's search (today's messages, for example `newer_than:1d`), or the Microsoft 365 connector's mail search. Use the tool names the session shows.
3. Get headers (From, To, Subject, Date) and body preview for first 15-20 messages
4. Surface emails requiring response, client/team emails, time-sensitive items

   **Task vs. Note distinction**: Only create tasks for emails needing a specific action. Fathom recaps, calendar acceptances, FYI emails, auto-notifications are NOT tasks.

5. **ROUTE IMMEDIATELY**:
   a. Tasks -> client file `Open Tasks`; Notes -> `## Notes` section
   b. Append manifest rows

A vault on the full control Google path (the Connecting Tools Appendix, `System/Connecting Tools.md`) reads Gmail through `python3 scripts/with-env.py` with the values that Appendix saves.

---

## Section 4: Slack Check

1. Read `System/Tools.md`. If the Slack section's status does not start with `connected`, hold the line `Slack not connected; Slack check skipped` with the Routine health findings from the keys and connectors check in `eod.md` step 1 and go to Section 5.
2. With the Slack connector's tools (the names the session shows), read today's direct messages, group messages, and mentions of you, for each workspace the connector can see
3. Surface unread DMs, mentions, time-sensitive items
4. Skip channels with no activity today
5. **ROUTE IMMEDIATELY**:
   a. Append items to client file `Open Tasks`
   b. Append manifest rows

---

## Section 5: Completion Check

EOD is the one place that checks whether open tasks already got finished. It runs here because Sections 1 to 4 have just read the day's calls, mail, and Slack.

**Skip rule.** Run this section only when the vault tracks tasks: at least one `Inbox/*.md` file has open items under `## Open Tasks`. If none does, print `Completion check skipped (no task lists in use)` and move on. A vault that is not used for task management carries no completion check at all.

**Hard rules.**
- Only two writes are allowed: check off a task on HIGH evidence, or record a `CONFIRM` row. Never delete, defer, reschedule, or reword a task here.
- Match on the exact task line, never on a bare keyword. If two open tasks match the same evidence, treat both as MEDIUM.
- Done by anyone counts: a teammate or the client resolving the request closes the task. Do not require the user's own message.
- When torn between HIGH and MEDIUM, choose MEDIUM.
- Work inline. If you use subagents, wait for every one to finish before continuing.
- A source that errors is noted and skipped; this section never stops the run.

1. **Collect open tasks.** From every `Inbox/*.md` file, read the `## Open Tasks` list. Keep each task's file, exact line, and provenance note (`*from <source>*`) when it has one.
2. **Look for evidence, in two passes.**
   - **Pass A, what this run already read.** Check every open task against the messages, threads, and transcripts Sections 1, 3, and 4 read today. Match by the person, client, subject, or specific identifier in the task (order number, invoice number, document name).
   - **Pass B, targeted lookups.** For open tasks with no Pass A hit whose provenance names a specific email thread or Slack conversation, open it and read the messages since the task was added, both sides, including thread replies. Cap this at 30 lookups per run: the newest tasks first, then the oldest.
   - Completion signals: from the user (sent, done, delivered, shared, scheduled, set up, fixed, approved); from a teammate or client resolving it (added, shipped, deployed, handled, "got it, all set"); or an inbound "never mind / already handled / no longer needed", which is MOOT. A meeting-prep task whose meeting happened today is MEDIUM.
   - A clear resolution in the cited thread is HIGH. Partial or indirect evidence is MEDIUM. No evidence is nothing: do not record or report it.
3. **Act.**
   - **HIGH:** edit the Inbox file the same way the other sections do: change `- [ ]` to `- [x]` on the exact line and append ` -- verified via [source] [HH:MM]`. Append a manifest row with type `COMPLETED` and the evidence.
   - **MEDIUM or MOOT:** append a manifest row with type `CONFIRM`, the task line, its file, and the evidence (for MOOT, quote the inbound message). Do not edit the task. At most 5 `CONFIRM` rows per run, MOOT first, then MEDIUM by most recent evidence.
4. **Hand off.** The Phase 1 summary prints the `COMPLETED` and `CONFIRM` lists. Phase 5 carries the `CONFIRM` rows into `Today.md` so `/morning` can settle each one in a single pass.

---

## Phase 1 Complete

After all sections finish:
1. Read back the manifest and print a summary: total items extracted, routed, orphaned, plus the `COMPLETED` and `CONFIRM` lists from Section 5
2. Print the calendar preview for tomorrow
3. The manifest at `/tmp/eod-manifest-TODAY.md` and all transcript/inbox files on disk are the handoff to Phase 2
