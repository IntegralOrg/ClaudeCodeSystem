---
type: sop
created: 2026-10-08
updated: 2026-10-15
---
# Setup Procedure

You are reading this because `SETUP_PENDING` exists at the vault root. Run every step below in this session, in order, without asking permission between steps. Ask the user only the questions written here. The order at the end matters: after the keys step, write the completion line, delete `SETUP_PENDING`, land, and only then the first win, so an interrupted hand-off never restarts setup.

## 0. Where you are

Check, in this order, and go to the first that fits:

- **A session with no vault** (no `CLAUDE.md` in the folder you are in, usually the home folder, because the person pressed the start button or pasted the start line): follow `System/Start.md` instead of this file. Download it with `curl -L` (`Invoke-WebRequest` on Windows) from `https://raw.githubusercontent.com/IntegralOrg/ClaudeCodeSystem/main/System/Start.md` into a temporary folder and read the whole file (a summarising fetch can change its commands), or read `Brain/System/Start.md` once the download in its step 2 is done. Come back to this file in the session it opens.
- **A cloud session** (home directory `/root`, nothing on the person's computer): skip Part A and Part B; run sections 1 to 8 (the cloud branches).
- **A local session in a folder with no `.git`** (usually inside `Downloads`): this is the downloaded copy. Run **Part A**.
- **A local session in the vault's home** (`~/Brain` on a Mac, `%USERPROFILE%\Brain` on Windows, with `.git`): run **Part B**, then sections 1 to 8 for whatever is not done yet.

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

Two rules for every browser step in this part (the GitHub sign-in, the Claude GitHub app, later a connector page). **Every "did you do it" question offers two answers**: the done answer (for example **Installed**) and **It did not work**, which goes to "When a step fails"; a card with one button leaves a person whose step failed with nothing to press. **When they say they are done, bring Claude back to the front** before the next sentence: `python3 .claude/skills/drive-screen/scripts/screenctl.py handback --text "Back to setup"` (on a Mac before Python exists, `open -b com.anthropic.claudefordesktop`), so they are looking at Claude and not at the browser they just finished in.

**B1. Ready check.** Check: the folder is the home and `.git` exists. On a Mac run `screenctl.py doctor`; if it is not `DOCTOR_OK`, run `screenctl.py request`, give the A4 sentence again, and carry on: screen control is only needed for click-through steps. When macOS asks once whether Claude Code may control System Events, say "Click OK."

**B2. Clean up.** Check: the downloaded copy still exists (a folder in `Downloads` with `SETUP_PENDING` and no `.git`). Compare it with the home (same file list, ignoring `.git` and `_generated`), then move it, and its zip if there is one, to the Trash (Mac: `mv` it into `~/.Trash/`; Windows: `[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory` with `SendToRecycleBin`, after `Add-Type -AssemblyName Microsoft.VisualBasic`). Never delete it outright.

**B3. GitHub.** Check: `python3 scripts/setup/github.py verify` prints `REACHABLE`. Otherwise:
1. Ask whether they have a GitHub account. If not, open github.com/signup and say: "Make a free account on the page that just opened, and tell me when you're in. If GitHub says the email already belongs to an account, sign in to that account instead."
2. `python3 scripts/setup/github.py install-gh` (prints `GH_READY`).
3. `python3 scripts/setup/github.py login-start`: it copies a one-time code and opens GitHub; give them its `SAY` sentence exactly. Then run `python3 scripts/setup/github.py login-wait` in the background and wait for `SIGNED_IN <login>`. Bring Claude back to the front (the Part B rule), then confirm the account before anything is created, with the question tool: "You are signed in to GitHub as **<login>**. Is that the account you want your vault on?" Options: Yes; No, a different account. On No, run `python3 scripts/setup/github.py logout` (prints `SIGNED_OUT`) and repeat this step from `login-start`; the browser may need to sign out of GitHub first, so say "Sign out of GitHub in your browser, then paste the code." A repository created on the wrong account is the one mistake this part cannot undo by itself.
4. **Where the vault lives.** Check: the `github owner` field in `_generated/setup/answers.md` (a prepared brief may name the company's GitHub organization). Otherwise run `python3 scripts/setup/github.py orgs`. If it prints bare `ORGS` (no organization), the vault goes on their own account; ask nothing. If it lists one to three, ask once with the question tool: "Where should your vault live on GitHub?" Options: their own account; each organization by name. If it lists more than three (the question tool holds four options), or prints `ORGS_UNKNOWN` (the lookup failed; never read that as "none"), ask the same question as plain text, listing the names you have, and take the answer typed back. Add one line: "In your company's organization the vault stays with the company if you change roles and its owners can open it; on your own account it is yours alone. If your company set up an organization for these vaults, choose it." Record the answer as `github owner`.
5. `python3 scripts/setup/github.py connect` (own account: the private repository `brain`) or `python3 scripts/setup/github.py connect --owner <organization>` (the private repository `brain-<their GitHub username>` in that organization, so each person's vault has its own name there; an empty private repository an admin already created under that name is reused). It saves to it and prints `CONNECTED`. On `REPO_EXISTS` or `REPO_NOT_PRIVATE`, tell them a repository with that name already exists, ask for another name (suggest `brain-2`), and run `connect --name <that name>` (with the same `--owner`); never push over a repository that has files. On `ORIGIN_UNVERIFIED` (this folder already points at a repository that cannot be confirmed as theirs and private), push nothing and follow "When a step fails". On `ORG_POLICY`, do not retry; which message depends on the step: with `--owner`, the organization has not allowed it yet, so say "Your company's GitHub organization has not allowed this yet. Ask one of its owners to approve the GitHub CLI under the organization's third-party access settings, or to create an empty private repository called `brain-<username>` there and make you its admin, then tell me," (the organization checklist is in `System/Company GitHub Organization.md`); without `--owner`, the account itself is company-managed, so say "This GitHub account is managed by a company and does not allow this. If your company has a GitHub organization for these vaults, tell me its name; otherwise sign in with a personal GitHub account, or ask your admin to allow it." Either way follow "When a step fails" for the report and keep going with what does not need GitHub.
6. Run the landing script now (`bash scripts/land-local.sh` with the `--final` flag) and confirm the last line of `_generated/landing.log` is "landed on main" or "nothing to push". On Windows, if `bash` is not found in this session, run it through Git's own copy: `& "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe" scripts/land-local.sh` with the `--final` flag (or `$env:ProgramFiles\Git\bin\bash.exe` for a machine-wide Git).
**B4. Claude GitHub app.** Say, once, before this page (it is the first page that needs the browser signed in to Claude, which a Desktop-only person has not done): "Your browser will ask you to sign in to Claude once; use the same email as the app." Then open `https://github.com/apps/claude/installations/new` and say: "Choose your account (or your company's organization, if the vault lives there), pick **Only select repositories**, choose your vault repository, and click Install." Ask "Did you install it?" with the two answers from the Part B rule, **Installed** and **It did not work**, and bring Claude back to the front when they answer. In an organization where they are not an owner, GitHub turns the install into a request and emails the owners; say so, and that routines stay "not live" until an owner approves it. Routines need the app to read and save the vault from the cloud. Its proof is the first routine run (a routine stays "not live" until its first run reports).

Then continue with section 1 (skip its opening line, and skip any field already in `_generated/setup/answers.md`), section 2 (build the vault from the answers), section 3 (connect the tools they named), section 4 (routines: in Claude Desktop use the `/schedule` skill and `RemoteTrigger` when the session has them; otherwise "Create a routine by hand" in `System/Routines.md`, offering to drive the screen through it), and sections 5 to 8. Delete `_generated/setup/answers.md` when you write the completion line.

## 1. Open, then learn who this is for

Whatever the person's first message says (a greeting, a question, or a pasted brief), setup starts with it. Open with one short message, in these words: "Welcome. I will set up your system now. It takes about ten minutes: a few quick questions, most of them a click, then I build everything and show it working. You can talk instead of typing: press the microphone next to the message box."

**If the first message is a prepared brief.** Your onboarding team may give the person a prompt to paste as their first message (interview notes, a company summary, a list of answers). Read it, fill every field below that it covers, and ask only for the fields it leaves out. Never ask whether they have a brief: a person who has one pastes it.

**Otherwise, ask, in three rounds.** Use the question tool (`AskUserQuestion`: up to four questions per call, two to four options each, and it always adds "Other" for a typed answer) wherever the answer is likely one of a few, and plain text for the rest. Skip any question an earlier answer already settled.

1. **Plain text, one message:** "First, tell me your name and role, your company and what it does in one sentence, and the email address I should use when something needs you. Type your answers below and press Enter."
2. **Two `AskUserQuestion` calls (the tool holds four questions each).** Say first, once: "These are the inputs: pick every place information reaches you; that's what we connect, so your brain hears what you hear. Picking a tool means we connect it. Skipping one means your brain won't see it until you come back to it."
   First call:
   - "Which email and calendar do you use?" Options: Google (Gmail and Google Calendar); Microsoft (Outlook and Teams).
   - "Where does information come in day to day?" (multi-select) Options: Email; Calendar; Slack; Files (Google Drive or OneDrive).
   - "Do you record your meetings?" Options: Yes; No.
   - "Where does your team chat?" (multi-select) Options: Slack; Microsoft Teams; Neither.
   Second call (skip the first question when they do not record meetings):
   - "Which tool records them?" Options: Fathom; Fireflies; Granola. (Typed answers such as tl;dv, Grain, Zoom, Tactiq and Circleback all have connectors.)
   - "Where do you keep tasks today?" Options: Asana; ClickUp; Notion; Nowhere yet. (Typed answers such as Linear and monday are accepted.)
   - "Anything else you live in?" (multi-select) Options: HubSpot or another CRM; QuickBooks; Nothing else. (Typed answers welcome.)
   - "Which time zone are you in?" Put the zone you detect first, marked "(Recommended)": in a local session read it from the computer (`readlink /etc/localtime` on a Mac, `tzutil /g` on Windows); a cloud session cannot see it, so offer Eastern, Central, and Pacific. Record the answer as an IANA name (for example `America/New_York`).
3. **One `AskUserQuestion` call, three questions:**
   - "How does your week usually run?" Options: Meetings in the morning, focus in the afternoon; Focus in the morning, meetings in the afternoon; Meetings scattered all week; Mostly focus time.
   - "When do you plan your week?" Options: I do not plan the week (first, so it is the quiet default; only a chosen day changes rule 13); Monday morning; Sunday evening; Friday afternoon.
   - "What should this system carry for you first?" (multi-select) Options: My task list, from email and meetings; Prep before each meeting; Notes on each client; Process automation (a repeated chore handed to the system). The evening summary is not an option because End of Day writes it every weeknight whatever they choose.

If the question tool is not available in this session, ask the same three rounds as plain text, one message per round.

Fields: owner name, role, company, company one-liner, tools, week shape (including the planning day), first jobs (every one they picked, in the order they rank them; ask which comes first only if they picked more than one), time zone, and the owner's email address (the address End of Day uses to reach the owner when something needs them). `tools` is the full list of named tools with, for each, whether it is essential (email and calendar always; the notetaker when they record). Ask once, in one line each, for any of those the brief or the answers did not give. One more field, `github owner`, is filled only from a prepared brief that names the company's GitHub organization for these vaults; it is never asked here (B3 asks it, only when the account belongs to an organization).

## 2. Build the vault

- Write `CLAUDE.md` from the skeleton: fill the `## Owner` section (name, role, company, time zone as an IANA name, and `email: <owner email>` on its own line), then replace the placeholder line under each of `## Company`, `## Tools I live in`, `## The shape of my week`, and `## First jobs for this system`; keep every rule and the `System/` reference intact. Then replace every remaining placeholder in the file: every `[Your Name]`, `[YourCompany]`, `[Your Role]`, `[Your Timezone]`, and `[Your Task Manager]` becomes the answer (the company's folder name is the company name), so that no bracketed placeholder is left anywhere in `CLAUDE.md`. Rewrite rule 12 (Meeting Window) and rule 13 (Daily Schedule Skeleton) from the week shape and planning day answers: the meeting window and the deep-work blocks follow the shape they chose, and the planning line names their planning day, or is dropped when they said they do not plan the week; keep the rule numbers.
- Create folders: `Work/Clients/`, `Work/Projects/`, `Work/Daily/`, `Personal/`, `Resources/Reference/`, `Inbox/`.
- Write `System/Tools.md`, the tools ledger, from the answers: the header (the first line `# Tools`, a blank line, then the sentence "One section per tool the owner named at setup or later. The first bullet under each heading is the status and is the only line the hooks read."), then one `## <tool>` section per tool named, in this order: email, calendar, the notetaker, then the rest. A tool named in more than one answer (Slack as an input and as team chat; Microsoft for mail and for Teams) gets one section. Each section's first bullet is `- status: not connected`, then `- essential: yes` (email, calendar, and the notetaker when they record) or `- essential: no`, `- how: connector "<registry name>"` (or `key <NAME>` for a tool whose ruling in `System/Connecting Tools.md` is a key), `- used by: <routine and what for>`, `- updated: <today>`. A tool nothing can read (text messages, WhatsApp) gets `- status: skipped (no route reads it today)` and is never asked about again. The hooks read only the status bullet, so keep that shape.
- Text messages and WhatsApp are not offered: no route reads them today; when the person names one, say so in one sentence and move on.
- For each client or project the user named, create a page from `Templates/Client Note.md`.
- Set `timezone:` in every file under `System/routines/` to the user's zone as an IANA name (for example `America/New_York`), then edit the two routine sections of `System/Routines.md` in place (the `## End of Day` and `## Vault Hygiene` sections) to match those files; keep every other section of the file, including "Create a routine by hand" and "If a routine is stale or not live".

## 3. Connect your tools

The tools you named are on the ledger, `System/Tools.md`. This step connects the essential ones (email, calendar, and the notetaker when they record) now, and never blocks: one try per tool during setup, then setup moves on and the ledger keeps the item open. The person hears one reminder line per session until the essential ones are done (the `tools_health.py` hook), and "connect my tools" in any session runs this step again for whatever is open.

Start each run by settling every `(verify next session)` entry with `session_connectors_status` (step 3 says how). Then, for each essential tool whose status is `not connected`, do steps 1 to 3. Then step 4, once. On now, do steps 1 to 3 for each of the others; on later, stop.

1. **Find its connector.** Call `search_mcp_registry` with the tool's name (for example `["gmail"]`) and take the `directoryUuid` of the matching result; the ruling for known tools is the table in `System/Connecting Tools.md` (a tool whose ruling is a key skips to section 5). If this session has no registry tools (a cloud session, or an older Desktop), it has none of the other connector tools either, so use the Desktop page for steps 2 and 3. Step 2 is the why sentence, then "In Claude, open **Customize**, then **Connectors**, find **<tool>** and click **Connect**, sign in, click **Allow**, then tell me" (for example, find **Gmail**), with the same **Connected** and **Later** answers; offer to drive the screen after the first one, and the last resort is the browser at claude.ai/customize/connectors, with the one-time sign-in sentence from B4. Step 3, on Connected, writes `- status: connected <today> (verify next session)`, because nothing in that session can check.
2. **Say why, then show the button.** One sentence ("Gmail, so End of Day can read what came in today"), then call `suggest_connectors` with that uuid and a one-word keyword (`email`, `calendar`, `meetings`, `messages`, `tasks`, `files`): the Connect button appears in the chat. Say: "Click Connect, sign in, click Allow, then tell me." Offer two answers: **Connected** and **Later**. A failed sign-in counts as Later here, so the card never needs a third button.
3. **Check, then record.** On Connected, call `session_connectors_status` and find the connector's row. When its status is `connected`, write `- status: connected <today>` in its ledger section (replace the status bullet; never add a second). When it is `disabled`, call `set_session_connector_enabled` for it, then write the same. `needs_auth`, `failed` or `pending` count as Later. When there is no row (a session started before the connector was added may not see it yet), write `- status: connected <today> (verify next session)`; the next run of the connect step (any session, when the person says "connect my tools") checks `session_connectors_status` first and settles every `(verify next session)` entry. On Later, leave `not connected` and move on. One try per tool during setup.
4. **After the essential tools**, when others are open: "Those are the ones tonight's routine needs. You also named <the other tools>; connect them now, two minutes each, or later?" (for example "You also named Slack and ClickUp"). On now, do steps 1 to 3 for each of them; on later, stop here; setup never asks about a non-essential tool twice.

For every connector that is now connected, add `"<prefix>__*"` to `permissions.allow` in `.claude/settings.json`, where `<prefix>` is the prefix of that connector's tool names in this session, everything before the second `__` (it starts with `mcp__`; on claude.ai connectors the part after it is an id, not the name).

## 4. Create the routines

There is one routine per file in `System/routines/`; the name, local schedule, time zone, model, and prompt come from that file. Two tool paths do the same job; use whichever this session has, local first.

**Local session (Claude Desktop): the `/schedule` skill and the `RemoteTrigger` tool** (actions `list`, `create`, `get`, `update`). This is the path that runs on a person's computer. Call `RemoteTrigger` `list` first. For each routine file: if a routine with the same name already exists, reuse it (`update` it when the schedule, model, or prompt differs) instead of creating a duplicate; otherwise `create` it with this body, filled from the file:

```json
{"name": "End of Day", "cron_expression": "7 3 * * 2-6", "enabled": true, "persist_session": false,
 "job_config": {"ccr": {"environment_id": "<the environment id>",
   "session_context": {"model": "claude-opus-5-5", "sources": [{"git_repository": {"url": "https://github.com/<owner>/<repo>"}}]},
   "events": [{"data": {"uuid": "<a fresh UUID>", "session_id": "", "type": "user", "parent_tool_use_id": null,
                        "message": {"role": "user", "content": "/eod"}}}]}}}
```

`cron_expression` is the file's schedule converted to UTC (below); `session_context.model` is the `model:` line from the routine's file (`claude-opus-5-5` for both End of Day and Vault Hygiene), never the skill's default; `sources[0].git_repository.url` is this vault's repository (`git remote get-url origin`); the `events` message is the file's `prompt:`. `environment_id` is the person's cloud environment: `/schedule` or the `RemoteTrigger` `list` result names it (every account has a default one); if none exists yet, "Create a routine by hand" in `System/Routines.md` makes it. After every `create`, and for every routine you reuse, call `get` and confirm the result shows this repository under `sources`, the model from the file, and the UTC cron; fix a wrong field with `update`.

**Cloud session: the `Claude_Code_Remote` tools.** Call `mcp__Claude_Code_Remote__list_triggers` first. For each file in `System/routines/`: if a routine with the same name already exists, reuse it (update it with `update_trigger` if the schedule, model, or prompt differs) instead of creating a duplicate; otherwise create it with `create_trigger`. The tools a cloud session exposes for this are `mcp__Claude_Code_Remote__create_trigger`, `list_triggers`, `get_trigger`, `update_trigger`, and `delete_trigger`. `create_trigger` takes a name, a cron expression (or `run_once_at` for a single run), the prompt, a model, and a repository source. The name, schedule, time zone, model, and prompt come from the routine's file.

Rules for both paths:

- **The cron expression is in UTC.** The routine files give the schedule in the owner's local time, with `timezone:` set to their IANA zone. Convert it to UTC before creating, using the offset in force today. Example: 11:07 PM Monday to Friday in America/New_York is `7 3 * * 2-6` in UTC during daylight time (EDT) and `7 4 * * 2-6` in standard time (EST); the weekday field moves by one because 3 AM UTC is the next day. The schedules sit at seven minutes past the hour on purpose: a routine set for :00 can start minutes late. Write the UTC expression and the local intent in `System/Routines.md` (the fire time shifts by an hour at each daylight-saving change, see that file).
- **Pass `model` from the routine's file** and verify it in `get` (or `get_trigger`): a routine created from a skill's template default runs on the wrong model every night.
- Create every routine with `persist_session: false` (each run is a fresh session, so nothing a previous run left in memory is relied on).
- **Pass the connected connectors.** Read `session_connectors_status` when the session has it; otherwise use the ledger's connected entries. For End of Day, the create body's `connectors` field carries every connected ledger tool whose `- used by:` names End of Day (email, calendar, the notetaker when they record), when the tool accepts it (try once; a refusal names the parameter, and some organizations refuse it). The routine file's `connectors:` stays the required set. When it is refused, create without, then tell the person the one by-hand step: "In Claude, open Routines, End of Day, the arrow by its name, Edit, Advanced settings, the **Connectors** tab, and tick <the connectors it should carry>." (for example "tick Gmail and Google Calendar") Either way verify with `get` that the routine lists them, and write which connectors it carries in its `System/Routines.md` section (`- connectors: Gmail, Google Calendar`); a run without them reports `connector-missing` in Routine health.
- **Attach this repository to every routine.** A routine created without a repository source runs in an empty container with no vault. In a cloud session, before creating, read the `create_trigger` tool's input schema and find the field that names the repository or sources (the name varies: `repository`, `sources`, `git_repository`, `repo_url`). Pass this repository's HTTPS URL in it.
- **Verify each routine, created or reused.** After every `create_trigger`, and for every routine you reuse, call `get_trigger` and confirm the result lists this repository as a source (it appears under `session_request.config`, as `sources`). If a reused routine's source is missing, repair it with `update_trigger` when the tool has a field for it. If the tool has no such field, or the source list is still empty, call `delete_trigger` on that routine and use "Create a routine by hand" in `System/Routines.md` for it instead; write "created by hand" in its section.
- **Environment:** create the routine on the current session's environment when the tool reports one, or without naming an environment when the tool allows. Use "Create a routine by hand" in `System/Routines.md` (it includes creating the environment and installing the Claude GitHub app) only when creation fails, or when a routine's first run reports no repository access; tell the user you will verify on the next run.
- Record each routine's id, model, and the environment id in `System/Routines.md`.

If neither tool set is available in this session, follow "Create a routine by hand" in `System/Routines.md` (in Claude the page is Routines, and the sidebar may say Scheduled) and tell the user you will verify on the next run. Mark every routine "not live" until its first run reports its keys present.

`System/Routines.md` is read by the vault's health hooks, so keep its shape exactly: one `## <title>` heading per routine using the `title:` from its file in `System/routines/` (`End of Day`, `Vault Hygiene`), and the **first** bullet under each heading is `- live_since: not live` (or `- live_since: YYYY-MM-DD` once the first run has reported its keys present). Then bullets for the schedule, the model, the connectors it carries, what it needs (keys, connectors), the routine id, and the environment id:

```markdown
## End of Day
- live_since: not live
- schedule: 11:07 PM Monday to Friday America/New_York, cron `7 3 * * 2-6` UTC (EDT; `7 4 * * 2-6` in standard time)
- model: claude-opus-5-5
- connectors: <the ones attached, or none yet>
- needs: connectors Gmail, Google Calendar; optional keys FATHOM_API_KEY, SLACK_TOKEN_WORKSPACE_A
- routine id: <id from create, or "not created yet">
- environment id: <environment id, or "not created yet">
```

Write the same shape for `## Vault Hygiene`, after End of Day.

## 5. Keys

Only for a ledger tool whose ruling in `System/Connecting Tools.md` is a key, or a gap that table names. Run `python3 scripts/check-keys.py --where`: it lists, by name, each key a routine needs that is missing, and where each one goes (never a value). Two places, both needed for a key a routine uses:

- **On this computer:** run `python3 scripts/set-key.py NAME --label "<what it is, for example Fathom API key>"`. A box opens on their screen with a hidden field; say "Paste your Fathom API key in the box that opened and click Save." It prints `SAVED NAME` and nothing else. On `CANCELLED` or `EMPTY`, ask once more or move on; the ledger keeps the tool open. (Windows: the same script opens a Windows box.) In a cloud session skip the pop-up; the computer copy is added in `System/Adding Your Computer.md` step 4. On `NO_PROMPT`, `FAILED` or `BAD_NAME`, follow "When a step fails". Never ask the person to paste a value into the chat, and never open or name the file the script writes.
- **For the nightly routines:** the same key goes on the routine's cloud environment as a **network secret**, which the session never sees: say "In Claude, open Routines, End of Day, the arrow by its name, Edit, Advanced settings, the Cloud environment button, hover over the environment and click the gear. Under **Network secrets** click **Add secret**: Name `Fathom`, Credential type Bearer, Allowed websites `api.fathom.ai`, and under Custom headers set the name to `X-Api-Key` with no prefix and paste the key as the value, then click Connect." The `--where` output gives the host and header for each key. For a key whose `--where` line says prefix "Bearer" (Slack), set Credential type Bearer and add no custom header; the secret's Name is the tool's name. Network secrets exist on Pro and Max; on a Team plan say the cloud copy is not available yet and the tool is local-only.

Then run `python3 scripts/check-keys.py` again: a key whose probe answers is reported present (locally through the pop-up's file, in the cloud through the secret); write `- status: key present <today>` in that tool's ledger section. A key the probe could not check (network) is reported as such and does not block; the routine's first run checks again.

## 6. Record completion, then release the marker

1. Write one line to `Work/Daily/<today>.md`: "Setup completed <date> in a <cloud|local> session; routines: <names, live or not live>; tools connected: <names, or none>; still to connect: <names, or none>; keys missing: <names or none>; session journal: <not asked yet|installed|declined>." (the session journal answer is recorded here so it is never asked twice; the Adding Your Computer step reads it). The journal is offered after this step (section 8 in a local session, `System/Adding Your Computer.md` after a cloud one), so write `not asked yet` in that field now and change it in the same line to `installed` or `declined` once the person answers.
2. Delete `SETUP_PENDING` now, so an interrupted hand-off never restarts setup.

## 7. Land

- **Cloud session:** landing happens when this turn ends (the Stop hook). Nothing to run.
- **Local session:** run `bash scripts/land-local.sh --final` now.

## 8. Show it working, then step two

- **Cloud session:** say, in these words: "We connected your tools earlier in this session; `System/Tools.md` lists any that are still open, and your call with Dean finishes those. Ask me any time and I will walk you through it. Next we put this on your computer." Then follow `System/Adding Your Computer.md`.
- **Local session: the first win.** You are already on their computer, so skip the hand-off. Run the first-local-session checks from `System/Adding Your Computer.md` step 4 (the session journal sentence, Superpowers through the bundled CLI, the ledger line) as before, and do these three in full, not in passing: (a) the ledger line: read `System/Tools.md` and say, by name, which tools are still not connected; (b) before installing the session journal, say in one sentence that its end-of-session step runs `claude -p`, a paid call against their Claude account, and skip it on no; (c) install Superpowers through the bundled CLI first: `python3 scripts/setup/claude_cli.py` prints `CLI <path>` or `CLI_MISSING`; with a path, run `python3 scripts/setup/claude_cli.py -- plugin marketplace add obra/superpowers-marketplace`, then `-- plugin install superpowers@superpowers-marketplace`, then `-- plugin list`; only on `CLI_MISSING` fall back to the Settings, Plugins screen drive. Then the first win, in three steps, each skipped with one sentence when its connector is missing (the ledger line reminds later):
  1. **See it read.** With email connected, run this yourself and show the result: "Summarize the key takeaways from my email over the past week." Three bullets, from their real mail. With calendar connected, the same for the week ahead. Say: "Before the connection it had nothing. Now it reads what you read."
  2. **Run the sweep once, live.** With email and calendar connected, run `/eod` in this session. It reads the connected tools, writes today's daily note, and its keys and connector check flips `live_since` for End of Day in `System/Routines.md` when everything the routine needs is present. Say: "Your brain is current. End of Day runs on its own at 11:07 PM, every weeknight."
  3. **Task one.** Ask: "What's something you'd get done today, and how would you go about it?" Do it from the vault and the connected tools (a draft, a summary, a list), save the output under `Inbox/`, and say what you read to produce it. They review; nothing is sent.

  Then offer voice input by name, once: "Many people talk to this system rather than type. Wispr Flow (wisprflow.ai) turns speech into text anywhere on your computer. Want me to install it?" On yes, open wisprflow.ai, download the installer, and drive the install with the drive-screen skill (its blackout message first); on no, move on and never ask again.

## Ask the person only when

Setup decides everything it can without asking. The person hears from you only for:

- a permission only they can grant (the Mac privacy switches, a one-time "control System Events" prompt);
- a sign-in, an account creation, a consent screen, or a code sent to their email or phone;
- an administrator password or a "Do you want to allow this app to make changes" prompt, which the system shows on a screen software cannot click;
- a step that failed twice (then "When a step fails");
- a connector or tool that is missing from their workspace, or a choice only they can make (a folder name, a GitHub repository name that is taken).

Everything else (which plugin to install, which version to take, where files go, what to call things) you decide and mention in passing. Before each sign-in or consent, say in one sentence why it is needed ("Gmail, so End of Day can read what came in today"). Never ask whether to start, whether to continue, or which of two technical choices they prefer.

## When a step fails

Retry a failing step once. If it fails again:

1. Say plainly what failed and that it is not their fault, in one or two sentences.
2. With the Write tool, put the exact error line in `_generated/setup/error.txt` and what you tried in `_generated/setup/tried.txt` (never paste error text into a command: a `$(...)` inside it would run). Then run `python3 scripts/setup/help_report.py --step '<step name>' --error-file _generated/setup/error.txt --tried-file _generated/setup/tried.txt` (add `--details-file` with the `doctor` output when screen control is involved). It writes a report into `Inbox/` with any key or token hidden; give them its `SAY` sentence, which asks them to send it to their onboarding contact. Without Python yet (Part A, before A2 finishes), write the same report with the Write tool instead.
3. Keep going with every step that does not depend on the failed one; the next session's checks pick the failed step up again.
4. If you were driving the screen, end with `screenctl.py handback` first, so they are looking at Claude when you tell them.

If Claude shows **Message flagged** instead of a reply, that is not a failed step: the person sends "Continue setup" again, in a new session if it repeats, and every step above checks what is already done and skips it. Keep each setup turn to one thing (one file read, one explanation) so a long turn is less likely to be withheld.
