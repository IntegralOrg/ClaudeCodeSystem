---
type: sop
created: 2026-10-08
updated: 2026-10-08
---
# Setup Procedure

You are reading this because `SETUP_PENDING` exists at the vault root. Run every step below in this session, in order, without asking permission between steps. Ask the user only the questions written here. Delete `SETUP_PENDING` last.

First, know where you are: a **cloud session** runs in a container (home directory `/root`, nothing on the user's computer); a **local session** runs in Claude Desktop on their machine. Step 4 and step 5 differ by that.

## 1. One opening question

Say: "Welcome. I will set this up now. Do you have the transcript from your Eva interview? Paste it here, or say no and I will ask five questions."

- **Transcript path:** read the transcript and fill the fields below from it. Ask only to confirm anything you could not find, one line each.
- **Interview path (five questions, one at a time):** (1) your name and role; (2) your company and what it does in one sentence; (3) the tools you live in (email, calendar, chat, meetings, tasks: name the apps); (4) the shape of your week (fixed meetings, deep-work time, the day you plan); (5) the two or three things you want this system to carry for you first.

Fields: owner name, role, company, company one-liner, tools, week shape, first three jobs, time zone, and the owner's email address (the address End of Day uses to reach the owner when something needs them). Ask once, in one line each, for any of those the transcript or the five answers did not give.

## 2. Build the vault

- Write `CLAUDE.md` from the skeleton: fill the `## Owner` section (name, role, company, time zone, and `email: <owner email>` on its own line), the company, tools, week shape, and first jobs sections; keep every rule and the `System/` reference intact.
- Create folders: `Work/Clients/`, `Work/Projects/`, `Work/Daily/`, `Personal/`, `Resources/Reference/`, `Inbox/`.
- For each client or project the user named, create a page from `Templates/Client Note.md`.
- Set `timezone:` in every file under `System/routines/` to the user's zone and write `System/Routines.md` from those files, in the exact shape shown at the end of step 3.

## 3. Create the routines

For each file in `System/routines/`: create a scheduled routine in the user's Claude account with that name, schedule, time zone, prompt, and connectors. The tools a cloud session exposes for this are `mcp__Claude_Code_Remote__create_trigger`, `list_triggers`, `get_trigger`, `update_trigger`, and `delete_trigger`. `create_trigger` takes a name, a cron expression (or `run_once_at` for a single run), the prompt, and the connectors. Create every routine with `persist_session: false` (each run is a fresh session, so nothing a previous run left in memory is relied on), on an **environment** that has the Claude GitHub app installed on this repository. Record each routine's id and the environment id in `System/Routines.md`.

If these tools are not available in this session (a local session usually has no `Claude_Code_Remote` server), follow "Create a routine by hand" in `System/Routines.md` (it includes creating the environment and installing the Claude GitHub app) and tell the user you will verify on the next run. Mark every routine "not live" until its first run reports its keys present.

`System/Routines.md` is read by the vault's health hooks, so keep its shape exactly: one `## <title>` heading per routine using the `title:` from its file in `System/routines/` (`End of Day`, `Vault Hygiene`, `Monthly Review`), and the **first** bullet under each heading is `- live_since: not live` (or `- live_since: YYYY-MM-DD` once the first run has reported its keys present). Then bullets for the schedule, what it needs (keys, connectors), the routine id, and the environment id:

```markdown
## End of Day
- live_since: not live
- schedule: 0 23 * * 1-5 (America/New_York)
- needs: connectors Gmail, Google Calendar; optional keys FATHOM_API_KEY, SLACK_TOKEN_WORKSPACE_A
- routine id: <id from create_trigger, or "not created yet">
- environment id: <environment id, or "not created yet">
```

Write the same shape for `## Vault Hygiene` and `## Monthly Review`, in that order after End of Day.

## 4. Keys

Run `python3 scripts/check-keys.py` (local session: `python3 scripts/check-keys.py --init` first, which creates the credentials file with blank values). For every missing name, tell the user: the name, what it is for (from `System/Connecting Tools.md`), where to get it, and where to paste it.

- **Cloud session:** the pane is the environment's settings in Claude (Routines, the environment, Environment variables). Values added there are read when the next container starts, so this session cannot see them: say so, leave the routine "not live", and let the routine's own first run (which starts with the keys check) flip it to "live" in `System/Routines.md`.
- **Local session:** the pane is the credentials file at the vault root, opened in Claude Desktop's file pane (the user opens it there and pastes; you never open it). When the user says it is done, run the check again until it exits 0.

Never ask the user to paste a value into the chat.

## 5. Land

- **Cloud session:** landing happens when this turn ends (the Stop hook). Nothing to run.
- **Local session:** run `bash scripts/land-local.sh --final` now.

## 6. Show it working, then step two

Two-minute demo on the user's own data: capture one task they mentioned into `Inbox/`, render one client page, and show today's daily note. Then say, in these words: "Tools like email and calendar connect on your call with Dean; ask me any time and I will walk you through it. Next we put this on your computer." Then follow `System/Adding Your Computer.md`.

## 7. Finish

Delete `SETUP_PENDING`. Write one line to `Work/Daily/<today>.md`: "Setup completed <date> in a <cloud|local> session; routines: <names, live or not live>; keys missing: <names or none>."
