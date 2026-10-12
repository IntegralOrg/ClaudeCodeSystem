---
type: sop
created: 2026-10-08
updated: 2026-10-10
---
# Setup Procedure

You are reading this because `SETUP_PENDING` exists at the vault root. Run every step below in this session, in order, without asking permission between steps. Ask the user only the questions written here. The order at the end matters: after the keys step, write the completion line, delete `SETUP_PENDING`, land, and only then run the demo, so an interrupted hand-off never restarts setup.

## 0. Where you are

Check, in this order, and go to the first that fits:

- **A cloud session** (home directory `/root`, nothing on the person's computer): skip Part A and Part B; run sections 1 to 7 (the cloud branches).
- **A local session in a folder with no `.git`** (usually inside `Downloads`): this is the downloaded copy. Run **Part A**.
- **A local session in the vault's home** (`~/Brain` on a Mac, `%USERPROFILE%\Brain` on Windows, with `.git`): run **Part B**, then sections 1 to 7 for whatever is not done yet.

Every step below starts with a check and skips itself when the check passes, so any session can pick up where an earlier one stopped. The person never types a command: you run everything and tell them, in one plain sentence, the one thing to click.

## Part A: the first session, in the downloaded folder

**A1. Welcome.** Say, in these words: "Welcome. I'll set up your system now. It takes about twenty minutes, and I'll need you for a few clicks: an installer, two permission switches on a Mac, and one approval on GitHub. Before we start, check the button next to Send says **Auto**; if not, click it and choose Auto." If macOS asks whether Claude Code may access the Downloads folder, tell them to click **Allow**. Hook errors in this first session are expected until the tools are installed; do not mention them unless asked.

**A2. Computer tools.** Check: on a Mac, `xcode-select -p` succeeds; on Windows, `git --version` and `python3 --version` both answer (look in `%LOCALAPPDATA%\Programs\Git\cmd\git.exe` too).
- Mac: run `xcode-select --install` and say: "A box just opened: click **Install**, then **Agree**. It takes five to fifteen minutes; we'll talk while it runs." Then wait in the background (`until xcode-select -p >/dev/null 2>&1; do sleep 15; done`, run in the background, up to 45 minutes).
- Windows (PowerShell): run `winget install --id Git.Git -e --scope user --accept-package-agreements --accept-source-agreements` and `winget install 9PNRBTZXMB4Z --source msstore --accept-package-agreements --accept-source-agreements` (Python 3.13 from the Microsoft Store, which provides `python3`), in the background. If Windows asks "Do you want to allow this app to make changes", tell them to click **Yes**. If `winget` is not found, run `Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe` and retry.

**A3. The questions, while A2 runs.** Check: `_generated/setup/answers.md` exists. Otherwise run section 1 now, during the wait (skip its opening line: A1 already welcomed them), and write every field to `_generated/setup/answers.md` (one `- field: value` line each), so the answers travel with the move.

**A4. Screen permissions (Mac only).** Check, once A2 is done: `python3 .claude/skills/drive-screen/scripts/screenctl.py doctor` prints `DOCTOR_OK`. Otherwise run `python3 .claude/skills/drive-screen/scripts/screenctl.py request` and say: "System Settings just opened. Turn on **Claude Code** in this list, then do the same in Screen Recording. It's listed as Claude Code, not Claude." The grants take effect in the next session, which A6 opens anyway. Windows: nothing to do.

**A5. Move home.** The script does its own checks. Run it with the owner's name and email from the answers:
- Mac: `bash scripts/setup/move-home.sh --name "<name>" --email "<email>" --no-open`
- Windows: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup\move-home.ps1 -Name "<name>" -Email "<email>" -NoOpen`

It prints `HOME_READY <folder>` and `OPEN_URL <link>` (or `ALREADY_HOME` on a rerun). On `DEST_NOT_EMPTY`, ask where to put it instead (offer `Brain-2` beside it) and rerun with `--dest` (Windows: `-Dest`). On `SYNCED_PATH`, choose a folder outside cloud-synced folders. On `GIT_MISSING`, A2 has not finished: wait for it.

**A6. Open the new home.** Say: "I'm opening your Brain in a new Claude window. Click Trust, then press Enter." Then open the `OPEN_URL` link (`open "<link>"` on a Mac, `Start-Process "<link>"` on Windows), and say this session is finished and the new window carries on. If the link does nothing, tell them: "In Claude, choose **Code**, then **Select folder**, pick the **Brain** folder in your home folder, click Trust, and send 'continue'."

## Part B: in the vault's home

**B1. Ready check.** Check: the folder is the home and `.git` exists. On a Mac run `screenctl.py doctor`; if it is not `DOCTOR_OK`, run `screenctl.py request`, give the A4 sentence again, and carry on: screen control is only needed for click-through steps. When macOS asks once whether Claude Code may control System Events, say "Click OK."

**B2. Clean up.** Check: the downloaded copy still exists (a folder in `Downloads` with `SETUP_PENDING` and no `.git`). Compare it with the home (same file list, ignoring `.git` and `_generated`), then move it, and its zip if there is one, to the Trash (Mac: `mv` it into `~/.Trash/`; Windows: `[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory` with `SendToRecycleBin`, after `Add-Type -AssemblyName Microsoft.VisualBasic`). Never delete it outright.

**B3. GitHub.** Check: `python3 scripts/setup/github.py verify` prints `REACHABLE`. Otherwise:
1. Ask whether they have a GitHub account. If not, open github.com/signup and say: "Make a free account on the page that just opened, and tell me when you're in."
2. `python3 scripts/setup/github.py install-gh` (prints `GH_READY`).
3. `python3 scripts/setup/github.py login-start`: it copies a one-time code and opens GitHub; give them its `SAY` sentence exactly. Then run `python3 scripts/setup/github.py login-wait` in the background and wait for `SIGNED_IN`.
4. `python3 scripts/setup/github.py connect`: it creates the private repository `brain` and saves to it (`CONNECTED`). On `REPO_EXISTS` or `REPO_NOT_PRIVATE`, tell them a repository with that name already exists, ask for another name (suggest `brain-2`), and run `python3 scripts/setup/github.py connect --name <that name>`; never push over a repository that has files. On `ORIGIN_UNVERIFIED` (this folder already points at a repository that cannot be confirmed as theirs and private), push nothing and follow "When a step fails".
5. Run the landing script now (`bash scripts/land-local.sh` with the `--final` flag) and confirm the last line of `_generated/landing.log` is "landed on main" or "nothing to push". On Windows, if `bash` is not found in this session, run it through Git's own copy: `& "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe" scripts/land-local.sh` with the `--final` flag (or `$env:ProgramFiles\Git\bin\bash.exe` for a machine-wide Git).

**B4. Claude GitHub app.** Open `https://github.com/apps/claude/installations/new` and say: "Choose your account, pick **Only select repositories**, choose **brain**, and click Install." Routines need it to read and save the vault from the cloud. Its proof is the first routine run (a routine stays "not live" until its first run reports).

Then continue with section 1 (skip its opening line, and skip any field already in `_generated/setup/answers.md`), section 2 (build the vault from the answers), section 3 (routines: in Claude Desktop use the `/schedule` tools when the session has them; otherwise "Create a routine by hand" in `System/Routines.md`, offering to drive the screen through it), and sections 4 to 7. Delete `_generated/setup/answers.md` when you write the completion line.

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

## When a step fails

Retry a failing step once. If it fails again:

1. Say plainly what failed and that it is not their fault, in one or two sentences.
2. With the Write tool, put the exact error line in `_generated/setup/error.txt` and what you tried in `_generated/setup/tried.txt` (never paste error text into a command: a `$(...)` inside it would run). Then run `python3 scripts/setup/help_report.py --step '<step name>' --error-file _generated/setup/error.txt --tried-file _generated/setup/tried.txt` (add `--details-file` with the `doctor` output when screen control is involved). It writes a report into `Inbox/` with any key or token hidden; give them its `SAY` sentence, which asks them to send it to their onboarding contact. Without Python yet (Part A, before A2 finishes), write the same report with the Write tool instead.
3. Keep going with every step that does not depend on the failed one; the next session's checks pick the failed step up again.
4. If you were driving the screen, end with `screenctl.py handback` first, so they are looking at Claude when you tell them.
