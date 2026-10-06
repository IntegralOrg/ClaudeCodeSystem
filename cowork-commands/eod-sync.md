---
name: eod-sync
description: EOD Phase 2: Cleanup, deduplication, and external sync with task manager.
---

# EOD Phase 2: Sync

Cleanup, deduplication, and external sync phase. Reads state from disk (manifest + inbox files written by Phase 1) in a fresh context. Reconciles the vault, updates client boards, and syncs with your task manager (if configured).

**This phase runs in a fresh Claude context.** It reads from the manifest and inbox files on disk. No conversation state carries over from Phase 1.

**The vault is a Git repository in your cloud workspace.** There is no background file sync, so the built-in editor is safe for reads and writes -- read a file, modify it, and write it back with the Edit or Write tool.

**Critical rule: Route-as-you-go.** Every change (dedup merge, completed-task move, archive) MUST be written to disk immediately. Do not batch changes in memory across multiple files.

---

## Setup

1. Run `date` to get today's date and current time ([Your Timezone])
2. Do not read or source the credentials file. Scripts load credentials themselves (`scripts/envload.py`); for a one-off external call use `python3 scripts/with-env.py -- <command>`
3. Set `TODAY` as the current date in `YYYY-MM-DD` format
4. Set `DOW` to the current day of the week (for Monday archive logic)
5. **Read the manifest** from `/tmp/eod-manifest-TODAY.md`. Confirm it exists and contains at least one item row. If missing, abort with a clear error: "No manifest found. Run Phase 1 first."
6. Initialize counters: `SYNCED_BACK=0`, `DEDUPED=0`, `CLEANED=0`, `SYNCED=0`

---

## Step 1: Today.md Reverse Sync

Sync task completions from today's `Inbox/Today.md` back to their source inbox files. This closes the loop: tasks checked off during the day in Today.md get marked complete in the client file they came from, so the rest of Phase 2 can move them to Completed normally.

1. **Read `Inbox/Today.md`**. If the file is missing or has a stale date header, skip this step (nothing to sync).
2. **Find all checked tasks** (`- [x]`) that have a source tag: `<!-- src:path/to/file.md|fingerprint -->`
3. **Skip meetings** (`<!-- type:meeting -->`). Meeting checkboxes are attendance tracking, not task completion.
4. **For each completed task** (edit each source file directly):
   - Parse the source file path and fingerprint from the `<!-- src:... -->` tag
   - Read the source file
   - Search for the matching task by substring-matching the fingerprint against `- [ ]` lines
   - If found: change `- [ ]` to `- [x]` for that line
   - If not found (task was already completed, moved, or reworded): skip silently
   - Increment `SYNCED_BACK`
5. **Batch by file**: if multiple completed tasks point to the same source file, apply all changes in a single write to that file.
6. Log: `"Synced {SYNCED_BACK} completions from Today.md back to inbox files"`

---

## Step 2: Deduplication

Scan all client inbox files for duplicate tasks. Two tasks are duplicates if their text matches after stripping checkbox prefix, whitespace, and trailing source notes.

1. **Read each client file** (`Inbox/[Client A].md`, `Inbox/[Client B].md`, `Inbox/[YourCompany].md`, etc.)
2. **Extract all `- [ ]` items** from each file's `## Open Tasks` section
3. **Compare within each file** using fuzzy matching:
   - Normalize: lowercase, strip leading `- [ ] `, strip trailing parenthetical source notes
   - Match threshold: strings that are identical after normalization, or differ only by date references or source annotations
4. **When a duplicate is found** (edit the file directly):
   - Keep the first occurrence
   - Merge source notes from the duplicate into the kept item (append `*also from <source>*`)
   - Remove the duplicate line
   - Increment `DEDUPED`
5. Do NOT deduplicate across different client files. Only within the same file.

---

## Step 3: Completed Task Cleanup

Find checked items (`- [x]`) in each client file and move them to that file's Completed section.

1. **For each client file** (edit each file directly):
   - Read the file
   - Find all `- [x]` items in `## Open Tasks`
   - Move them to `## Completed` (create the section if it does not exist, insert before `## Notes`)
   - Add a date stamp: append `(completed TODAY)` to each moved item
   - Remove the items from `## Open Tasks`
   - Remove any `###` subsection headers left behind (both empty headers and any legacy `### New from <source>` headers; tasks should be flat bullets under `## Open Tasks`)
   - Increment `CLEANED` for each item moved
---

## Step 4: Task Manager Sync

**Skip this step if no task manager is configured.** Check CLAUDE.md for a task manager entry (e.g., ClickUp, Asana, Todoist). If none, skip to Step 5.

Sync new and completed tasks with the configured task manager using its MCP tools or API.

1. **New tasks** (from manifest): for each manifest row added today with Type `action-owner`:
   - Create a task in the matching client list/project in the task manager
   - Set the task name to the Item text, description to the Source note
   - Set due date if one was captured
   - Log the external task ID back into the manifest's Status column
   - Increment `SYNCED`

2. **Completed tasks**: for each item moved to Completed in Step 3:
   - Search the task manager for a matching task by name
   - If found, update its status to done/complete
   - Increment `SYNCED`

3. If task manager API calls fail, log the error and continue. Do not abort the phase for sync failures.

---

## Step 5: Vault Hygiene

1. **Stale item flagging**: for each client file, find `- [ ]` items in `## Open Tasks` older than 14 days based on the date in the task's italic source note (e.g., `*from Fathom: [Call Name] 4/3*`). Prepend a flag: `- [ ] **STALE** <original text>`
2. **Monday archive** (only if `DOW` = Monday):
   - For each client file, read the `## Completed` section
   - If non-empty, append its contents to `Archive/Completed Week of YYYY-MM-DD.md` (use the Monday date). Create the archive file if it does not exist.
   - Clear the `## Completed` section in the client file (leave the header, remove all items)
   - Write both the archive file and the client file

---

## Phase 2 Complete

After all steps finish:
1. Read back the manifest and update any remaining Status fields
2. Print summary:
   ```
   Phase 2 complete.
   - Today.md completions synced back: {SYNCED_BACK}
   - Duplicates merged: {DEDUPED}
   - Completed tasks cleaned: {CLEANED}
   - Tasks synced to task manager: {SYNCED}
   - Stale items flagged: {count}
   - Monday archive: {yes/no, file path if yes}
   ```
3. The updated manifest and clean inbox files are the handoff to Phase 3
