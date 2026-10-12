---
type: sop
created: 2026-10-08
updated: 2026-10-10
---
# Setup Procedure

You are reading this because `SETUP_PENDING` exists at the vault root. Run every step below in this session, in order, without asking permission between steps. Ask the user only the questions written here. The order at the end matters: after the keys step, write the completion line, delete `SETUP_PENDING`, land, and only then run the demo, so an interrupted hand-off never restarts setup.

First, know where you are: a **cloud session** runs in a container (home directory `/root`, nothing on the user's computer); a **local session** runs in Claude Desktop on their machine. Step 4, step 6, and step 7 differ by that.

## 1. Open, then learn who this is for

Whatever the person's first message says (a greeting, a question, or a pasted brief), setup starts with it. Open with one short message, in these words: "Welcome. I will set up your system now. It takes about ten minutes: a few quick questions, most of them a click, then I build everything and show it working."

**If the first message is a prepared brief.** Your onboarding team may give the person a prompt to paste as their first message (interview notes, a company summary, a list of answers). Read it, fill every field below that it covers, and ask only for the fields it leaves out. Never ask whether they have a brief: a person who has one pastes it.

**Otherwise, ask, in three rounds.** Use the question tool (`AskUserQuestion`: up to four questions per call, two to four options each, and it always adds "Other" for a typed answer) wherever the answer is likely one of a few, and plain text for the rest. Skip any question an earlier answer already settled.

1. **Plain text, one message:** "First, tell me your name and role, your company and what it does in one sentence, and the email address I should use when something needs you."
2. **One `AskUserQuestion` call, four questions:**
   - "Which email and calendar do you use?" Options: Google (Gmail and Google Calendar); Microsoft (Outlook).
   - "Where does your team chat?" (multi-select) Options: Slack; Microsoft Teams; Text messages; WhatsApp.
   - "Do you record your meetings?" Options: Fathom; Zoom; Another notetaker; No.
   - "Where do you keep tasks today?" Options: Asana; ClickUp; Notion; Nowhere yet.
3. **One `AskUserQuestion` call, four questions:**
   - "Which time zone are you in?" Put the zone you detect first, marked "(Recommended)": in a local session read it from the computer (`readlink /etc/localtime` on a Mac, `tzutil /g` on Windows); a cloud session cannot see it, so offer Eastern, Central, and Pacific. Record the answer as an IANA name (for example `America/New_York`).
   - "How does your week usually run?" Options: Meetings in the morning, focus in the afternoon; Focus in the morning, meetings in the afternoon; Meetings scattered all week; Mostly focus time.
   - "When do you plan your week?" Options: Monday morning; Sunday evening; Friday afternoon; I do not plan the week.
   - "What should this system carry for you first?" (multi-select) Options: My task list, from email and meetings; Prep before each meeting; A summary of my day every evening; Notes on each client.

If the question tool is not available in this session, ask the same three rounds as plain text, one message per round.

Fields: owner name, role, company, company one-liner, tools, week shape (including the planning day), first jobs (every one they picked, in the order they rank them; ask which comes first only if they picked more than one), time zone, and the owner's email address (the address End of Day uses to reach the owner when something needs them). Ask once, in one line each, for any of those the brief or the answers did not give.

## 2. Build the vault

- Write `CLAUDE.md` from the skeleton: fill the `## Owner` section (name, role, company, time zone as an IANA name, and `email: <owner email>` on its own line), then replace the placeholder line under each of `## Company`, `## Tools I live in`, `## The shape of my week`, and `## First jobs for this system`; keep every rule and the `System/` reference intact.
- Create folders: `Work/Clients/`, `Work/Projects/`, `Work/Daily/`, `Personal/`, `Resources/Reference/`, `Inbox/`.
- For each client or project the user named, create a page from `Templates/Client Note.md`.
- Set `timezone:` in every file under `System/routines/` to the user's zone as an IANA name (for example `America/New_York`), then edit the two routine sections of `System/Routines.md` in place (the `## End of Day` and `## Vault Hygiene` sections) to match those files; keep every other section of the file, including "Create a routine by hand" and "If a routine is stale or not live".

## 3. Create the routines

Call `mcp__Claude_Code_Remote__list_triggers` first. For each file in `System/routines/`: if a routine with the same name already exists, reuse it (update it with `update_trigger` if the schedule or prompt differs) instead of creating a duplicate; otherwise create it with `create_trigger`. The tools a cloud session exposes for this are `mcp__Claude_Code_Remote__create_trigger`, `list_triggers`, `get_trigger`, `update_trigger`, and `delete_trigger`. `create_trigger` takes a name, a cron expression (or `run_once_at` for a single run), the prompt, and a repository source. The name, schedule, time zone, and prompt come from the routine's file.

- **The cron expression is in UTC.** The routine files give the schedule in the owner's local time, with `timezone:` set to their IANA zone. Convert it to UTC before calling `create_trigger`, using the offset in force today. Example: 11 PM Monday to Friday in America/New_York is `0 3 * * 2-6` in UTC during daylight time (EDT) and `0 4 * * 2-6` in standard time (EST); the weekday field moves by one because 3 AM UTC is the next day. Write the UTC expression and the local intent in `System/Routines.md` (the fire time shifts by an hour at each daylight-saving change, see that file).

- Create every routine with `persist_session: false` (each run is a fresh session, so nothing a previous run left in memory is relied on).
- **Do not pass `connectors`.** The parameter is refused for some organizations ("not available for this organization"). The user attaches each routine's connectors by hand afterwards (see `System/Connecting Tools.md`); a run without them degrades and Routine health reports `connector-missing`.
- **Attach this repository to every routine.** A routine created without a repository source runs in an empty container with no vault. Before creating, read the `create_trigger` tool's input schema and find the field that names the repository or sources (the name varies: `repository`, `sources`, `git_repository`, `repo_url`). Pass this repository's HTTPS URL in it.
- **Verify each routine, created or reused.** After every `create_trigger`, and for every routine you reuse, call `get_trigger` and confirm the result lists this repository as a source (it appears under `session_request.config`, as `sources`). If a reused routine's source is missing, repair it with `update_trigger` when the tool has a field for it. If the tool has no such field, or the source list is still empty, call `delete_trigger` on that routine and use "Create a routine by hand" in `System/Routines.md` for it instead; write "created by hand" in its section.
- **Environment:** create the routine on the current session's environment when the tool reports one, or without naming an environment when the tool allows. Use "Create a routine by hand" in `System/Routines.md` (it includes creating the environment and installing the Claude GitHub app) only when creation fails, or when a routine's first run reports no repository access; tell the user you will verify on the next run.
- Record each routine's id and the environment id in `System/Routines.md`.

If these tools are not available in this session (a local session usually has no `Claude_Code_Remote` server), follow "Create a routine by hand" in `System/Routines.md` and tell the user you will verify on the next run. Mark every routine "not live" until its first run reports its keys present.

`System/Routines.md` is read by the vault's health hooks, so keep its shape exactly: one `## <title>` heading per routine using the `title:` from its file in `System/routines/` (`End of Day`, `Vault Hygiene`), and the **first** bullet under each heading is `- live_since: not live` (or `- live_since: YYYY-MM-DD` once the first run has reported its keys present). Then bullets for the schedule, what it needs (keys, connectors), the routine id, and the environment id:

```markdown
## End of Day
- live_since: not live
- schedule: 11 PM Monday to Friday America/New_York, cron `0 3 * * 2-6` UTC (EDT; `0 4 * * 2-6` in standard time)
- needs: connectors Gmail, Google Calendar; optional keys FATHOM_API_KEY, SLACK_TOKEN_WORKSPACE_A
- routine id: <id from create_trigger, or "not created yet">
- environment id: <environment id, or "not created yet">
```

Write the same shape for `## Vault Hygiene`, after End of Day.

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
