---
type: sop
created: 2026-10-08
updated: 2026-10-08
---
# Setup Procedure

You are reading this because `SETUP_PENDING` exists at the vault root. Run every step below in this session, in order, without asking permission between steps. Ask the user only the questions written here. The order at the end matters: after the keys step, write the completion line, delete `SETUP_PENDING`, land, and only then run the demo, so an interrupted hand-off never restarts setup.

First, know where you are: a **cloud session** runs in a container (home directory `/root`, nothing on the user's computer); a **local session** runs in Claude Desktop on their machine. Step 4, step 6, and step 7 differ by that.

## 1. One opening question

Say: "Welcome. I will set this up now. Do you have the transcript from your Eva interview? Paste it here, or say no and I will ask five questions."

- **Transcript path:** read the transcript and fill the fields below from it. Ask only to confirm anything you could not find, one line each.
- **Interview path (five questions, one at a time):** (1) your name and role; (2) your company and what it does in one sentence; (3) the tools you live in (email, calendar, chat, meetings, tasks: name the apps); (4) the shape of your week (fixed meetings, deep-work time, the day you plan); (5) the two or three things you want this system to carry for you first.

Fields: owner name, role, company, company one-liner, tools, week shape, first three jobs, time zone, and the owner's email address (the address End of Day uses to reach the owner when something needs them). Ask once, in one line each, for any of those the transcript or the five answers did not give.

## 2. Build the vault

- Write `CLAUDE.md` from the skeleton: fill the `## Owner` section (name, role, company, time zone, and `email: <owner email>` on its own line), the company, tools, week shape, and first jobs sections; keep every rule and the `System/` reference intact.
- Create folders: `Work/Clients/`, `Work/Projects/`, `Work/Daily/`, `Work/Monthly/`, `Personal/`, `Resources/Reference/`, `Inbox/`.
- For each client or project the user named, create a page from `Templates/Client Note.md`.
- Set `timezone:` in every file under `System/routines/` to the user's zone as an IANA name (for example `America/New_York`), then edit the three routine sections of `System/Routines.md` in place (the `## End of Day`, `## Vault Hygiene`, `## Monthly Review` sections) to match those files; keep every other section of the file, including "Create a routine by hand" and "If a routine is stale or not live".

## 3. Create the routines

Call `mcp__Claude_Code_Remote__list_triggers` first. For each file in `System/routines/`: if a routine with the same name already exists, reuse it (update it with `update_trigger` if the schedule or prompt differs) instead of creating a duplicate; otherwise create it with `create_trigger`. The tools a cloud session exposes for this are `mcp__Claude_Code_Remote__create_trigger`, `list_triggers`, `get_trigger`, `update_trigger`, and `delete_trigger`. `create_trigger` takes a name, a cron expression (or `run_once_at` for a single run), the prompt, and the connectors. The name, schedule, time zone, prompt, and connectors come from the routine's file.

- Create every routine with `persist_session: false` (each run is a fresh session, so nothing a previous run left in memory is relied on).
- Create each routine with the connectors its definition lists even if they are not connected yet; a run without them degrades and Routine health reports `connector-missing`.
- Pick the **environment**: use the `list_triggers` output to find the environment id other routines use; if none exists, or no environment has the Claude GitHub app on this repository, follow "Create a routine by hand" in `System/Routines.md` (it includes creating the environment and installing the Claude GitHub app) and tell the user you will verify on the next run.
- Record each routine's id and the environment id in `System/Routines.md`.

If these tools are not available in this session (a local session usually has no `Claude_Code_Remote` server), follow "Create a routine by hand" in `System/Routines.md` and tell the user you will verify on the next run. Mark every routine "not live" until its first run reports its keys present.

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
- **Local session:** the pane is the credentials file, `.env` at the vault root. It is a hidden file: in Claude Desktop's file pane turn on hidden files, or on a Mac press Command+Shift+Period in the Open dialog. It contains one `NAME=` line per key with nothing after the `=` until the user pastes. The agent never opens it; the person does. When the user says it is done, run the check again until it exits 0.

Never ask the user to paste a value into the chat.

## 5. Record completion, then release the marker

1. Write one line to `Work/Daily/<today>.md`: "Setup completed <date> in a <cloud|local> session; routines: <names, live or not live>; keys missing: <names or none>."
2. Delete `SETUP_PENDING` now, so an interrupted hand-off never restarts setup.

## 6. Land

- **Cloud session:** landing happens when this turn ends (the Stop hook). Nothing to run.
- **Local session:** run `bash scripts/land-local.sh --final` now.

## 7. Show it working, then step two

Two-minute demo on the user's own data: capture one task they mentioned into `Inbox/`, render one client page, and show today's daily note. Then:

- **Cloud session:** say, in these words: "Tools like email and calendar connect on your call with Dean; ask me any time and I will walk you through it. Next we put this on your computer." Then follow `System/Adding Your Computer.md`.
- **Local session:** say that tools like email and calendar connect on the onboarding call (and you can walk them through any of it now). You are already on their computer, so skip the hand-off: run the first-local-session checks from `System/Adding Your Computer.md` step 4.
