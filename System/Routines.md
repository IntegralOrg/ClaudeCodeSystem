---
type: reference
created: 2026-10-08
updated: 2026-10-08
---
# Routines

**What it is.** A routine is a scheduled job in your Claude account: at the set time it starts a fresh cloud session on this repository, runs one command, and writes the result back into the vault. Three routines ship with the system; their definitions (schedule, prompt, connectors, keys) are in `System/routines/`. Setup creates them and fills in the sections below. The vault's health hooks read this file, so keep each section's shape: one `## <title>` heading per routine, and the first bullet under it is `- live_since: <date>` or `- live_since: not live`.

**Schedules are in UTC.** Routine cron expressions run in UTC, not in your time zone. Setup converts each definition's local schedule (the `timezone:` in `System/routines/<name>.md`) to UTC when it creates the routine, using the offset in force that day. Example: 11 PM Monday to Friday in America/New_York is `0 3 * * 2-6` in daylight time and `0 4 * * 2-6` in standard time. The fire time therefore shifts by an hour at the daylight-saving change (11 PM becomes midnight, or 10 PM) until someone updates the routine's cron; End of Day computes its dates in your own zone, so its notes stay correct either way.

A routine is **not live** until its first run has reported its keys present; that run then replaces `not live` with the date. The first run of a routine is also the proof that its schedule, environment, and GitHub app access all work.

## End of Day
- live_since: not live
- schedule: weeknights at 11 PM your time (`0 23 * * 1-5` local; created as the UTC equivalent, for example `0 3 * * 2-6` in New York daylight time)
- needs: connectors Gmail and Google Calendar; optional keys `FATHOM_API_KEY`, `SLACK_TOKEN_WORKSPACE_A`
- routine id: not created yet
- environment id: not created yet

Output: `Work/Daily/<date>.md`, including a **Routine health** section.

## Vault Hygiene
- live_since: not live
- schedule: every night at 1 AM your time (`0 1 * * *` local; created as the UTC equivalent)
- needs: nothing
- routine id: not created yet
- environment id: not created yet

Output: `_generated/vault-hygiene/audit-log.md` (the newest `## YYYY-MM-DD` heading is the last run).

## How setup creates them

In a cloud session the agent uses the tools `mcp__Claude_Code_Remote__create_trigger`, `list_triggers`, `get_trigger`, `update_trigger`, and `delete_trigger`. `create_trigger` takes a name, a cron expression (or `run_once_at` for a single run), the prompt, and a repository source. Two facts matter: the `connectors` parameter is refused for some organizations, so connectors are attached by hand afterwards (see `System/Connecting Tools.md`); and a routine created without a repository source runs in an empty container with no vault, so setup passes this repository's URL and then calls `get_trigger` to confirm the repository is listed as a source (under `session_request.config`); the same check applies to a routine that already existed and is reused. If a source is missing and cannot be repaired with `update_trigger`, setup deletes that routine and uses the by-hand steps below, noting "created by hand" in its section. Every routine is created with `persist_session: false` (each run is a fresh session) and on an **environment** whose Claude GitHub app covers this repository. If those tools are not available (a local session usually does not have them), use "Create a routine by hand" below.

## Create a routine by hand

Do this once per routine, in a browser on claude.ai.

1. Go to **claude.ai**, open **Routines**, and click **New**.
2. If there is no environment yet, create one when asked (an **environment** is the container each run starts in, and holds the environment variables, your keys). If asked to install the **Claude GitHub app**, install it and grant it this repository (`brain`, or whatever you named it). Without the GitHub app on this repository the routine cannot read or save the vault.
3. Name: copy it from the routine's file in `System/routines/` (`End of Day` or `Vault Hygiene`).
4. Schedule: the cron expression from that file, converted to UTC for your time zone (see "Schedules are in UTC" above).
5. Repository: choose `brain` (this vault repository, whatever you named it), branch `main`. A routine with no repository runs in an empty container, so do not skip this step.
6. Prompt: the `prompt:` line from that file (`/eod` or `/vault-audit`).
7. Connectors: the ones listed under `connectors:` in that file (End of Day: Gmail and Google Calendar).
8. Environment: the one you created or chose. Keys go in its **Environment variables** (see `System/Connecting Tools.md`).
9. Save. Then record the routine's id and the environment id in the matching section above, and leave `live_since: not live` until its first run succeeds.

## If a routine is stale or not live

There are two channels. The session-start note from `routine_health.py` says, with no connector needed, when End of Day has not run when it should. End of Day's **Routine health** section in `Work/Daily/<date>.md` records Vault Hygiene staleness and any missing keys or connectors (a missing connector shows as `connector-missing`), and the same reasons are pushed outside the vault: emailed to you when Gmail is connected, otherwise a "Brain needs you: <reason>" all-day event on your calendar. A reason is sent at most once a week.

There are two fixes:

1. **Re-create it.** The routine may have been deleted, paused, or lost with an account change. Create it again (the tools above, or "Create a routine by hand") and update its id here.
2. **Add the missing key.** If the message names a key such as `FATHOM_API_KEY`, add it under the environment's **Environment variables** (Routines, the environment, Environment variables). A new value is read when the next run starts its container, and the run after that flips the routine to live.
