---
type: reference
created: 2026-10-08
updated: 2026-10-08
---
# Routines

**What it is.** A routine is a scheduled job in your Claude account: at the set time it starts a fresh cloud session on this repository, runs one command, and writes the result back into the vault. Three routines ship with the system; their definitions (schedule, prompt, connectors, keys) are in `System/routines/`. Setup creates them and fills in the sections below. The vault's health hooks read this file, so keep each section's shape: one `## <title>` heading per routine, and the first bullet under it is `- live_since: <date>` or `- live_since: not live`.

A routine is **not live** until its first run has reported its keys present; that run then replaces `not live` with the date. The first run of a routine is also the proof that its schedule, environment, and GitHub app access all work.

## End of Day
- live_since: not live
- schedule: weeknights at 11 PM (`0 23 * * 1-5`), in the time zone set at setup
- needs: connectors Gmail and Google Calendar; optional keys `FATHOM_API_KEY`, `SLACK_TOKEN_WORKSPACE_A`
- routine id: not created yet
- environment id: not created yet

Output: `Work/Daily/<date>.md`, including a **Routine health** section.

## Vault Hygiene
- live_since: not live
- schedule: every night at 1 AM (`0 1 * * *`), in the time zone set at setup
- needs: nothing
- routine id: not created yet
- environment id: not created yet

Output: `_generated/vault-hygiene/audit-log.md` (the newest `## YYYY-MM-DD` heading is the last run).

## Monthly Review
- live_since: not live
- schedule: the 1st of the month at 8 AM (`0 8 1 * *`), in the time zone set at setup
- needs: nothing
- routine id: not created yet
- environment id: not created yet

Output: `Work/Monthly/YYYY-MM-DD Monthly Review.md` (full date of the run).

## How setup creates them

In a cloud session the agent uses the tools `mcp__Claude_Code_Remote__create_trigger`, `list_triggers`, `get_trigger`, `update_trigger`, and `delete_trigger`. `create_trigger` takes a name, a cron expression (or `run_once_at` for a single run), the prompt, and the connectors. Every routine is created with `persist_session: false` (each run is a fresh session) and on an **environment** whose Claude GitHub app covers this repository. If those tools are not available (a local session usually does not have them), use "Create a routine by hand" below.

## Create a routine by hand

Do this once per routine, in a browser on claude.ai.

1. Go to **claude.ai**, open **Routines**, and click **New**.
2. If there is no environment yet, create one when asked (an **environment** is the container each run starts in, and holds the environment variables, your keys). If asked to install the **Claude GitHub app**, install it and grant it this repository (`brain`, or whatever you named it). Without the GitHub app on this repository the routine cannot read or save the vault.
3. Name: copy it from the routine's file in `System/routines/` (`End of Day`, `Vault Hygiene`, or `Monthly Review`).
4. Schedule: the cron expression from that file, in your own time zone.
5. Repository: this vault repository, branch `main`.
6. Prompt: the `prompt:` line from that file (`/eod`, `/vault-audit`, or `/monthly-review`).
7. Connectors: the ones listed under `connectors:` in that file (End of Day: Gmail and Google Calendar).
8. Environment: the one you created or chose. Keys go in its **Environment variables** (see `System/Connecting Tools.md`).
9. Save. Then record the routine's id and the environment id in the matching section above, and leave `live_since: not live` until its first run succeeds.

## If a routine is stale or not live

End of Day's **Routine health** section in `Work/Daily/<date>.md`, and the session-start note from `routine_health.py`, say when a routine has not run when it should. When Gmail is connected the same reason is emailed to you, and otherwise a "Brain needs you: <reason>" all-day event appears on your calendar. A reason is sent at most once a week.

There are two fixes:

1. **Re-create it.** The routine may have been deleted, paused, or lost with an account change. Create it again (the tools above, or "Create a routine by hand") and update its id here.
2. **Add the missing key.** If the message names a key such as `FATHOM_API_KEY`, add it under the environment's **Environment variables** (Routines, the environment, Environment variables). A new value is read when the next run starts its container, and the run after that flips the routine to live.
