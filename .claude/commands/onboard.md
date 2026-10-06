# Onboard: Set Up Your Personal Assistant

You are setting up the Claude Code Personal Assistant system for a new user. This is Part 1 of a 4-part setup process:

1. **`/onboard`** (you are here) -- Permissions, learn about the user, build the vault and all files
2. **`/train`** -- Learn how the system works (vault, skills, daily loop)
3. **`/connect`** -- Connect all your tools (calendar, email, task manager, etc.)
4. **`/finish`** -- Take it for a spin, learn how to improve it over time

**Voice:** Friendly, patient, non-technical. Explain everything in plain language. Use technical terms only in parentheses after the plain version.

**Important:** Use `AskUserQuestion` for EVERY question. Present 2-4 options with descriptions. Allow free-text input only when truly necessary (like entering a name). Never dump a wall of text -- keep each step short and focused.

---

## Phase 0: Detect Environment

Before doing anything, figure out where you are running.

1. **Check if this is the repo folder or a vault.** Look for `templates/CLAUDE.md` and `docs/` in the current directory or its children.
   - If found in the current directory: you are inside the setup repo. Note the repo path. **But before assuming the vault needs to be created elsewhere, check parent directories** (up to 3 levels) for vault indicators (like an existing `CLAUDE.md` with vault content, `Inbox/`, `Work/`). If a parent vault is found, set `VAULT_PATH` to that parent directory and treat this like the subfolder case below (the user opened Claude inside the repo folder instead of the vault root). Only if no parent vault is found should you defer to Phase 6A.
   - If found in a subfolder (e.g., `ClaudeCodeSystem/` or `ClaudeCodeSystem-main/`): the user dropped the repo inside their vault (or a folder that will become their vault). Note the repo subfolder path. The current directory is the vault root. Set `VAULT_PATH` to the current directory immediately.

2. **Locate the reference files.** Set `REPO_PATH` to wherever `templates/CLAUDE.md` lives. All template reads, example reads, and file copies will reference this path.

3. **If the setup commands aren't at the project root yet** (i.e., you are running from a vault and the commands are in a subfolder): This means the user probably said "set me up" and Claude read this file from the repo's CLAUDE.md. The commands are already loaded. Proceed normally.

Proceed to Phase 1.

---

## Phase 1: Permissions

You are running in **Claude Code on the web**. Your vault is a Git repository of Markdown files in your cloud workspace, and Claude Code reads and writes those files directly.

Before anything else, set up permissions so you can work without asking the user to approve every small action.

Tell the user:
"Before we get started, I need to set up permissions so I can work without asking you to approve every little thing. I am going to update your Claude Code settings now."

**Action:** Read `~/.claude/settings.json` (it may not exist yet).

- If the file does not exist, create it with the contents from `examples/settings.json` in this repository.
- If it exists, **merge** permissions: add any missing entries from `examples/settings.json` to the existing `allow` array and `additionalDirectories` array without removing anything. Preserve any other settings (like `mcpServers`).

**Note:** `~/.claude/settings.json` lives in the temporary workspace, so it only covers the current session. That is fine for setup -- the durable copy is written into the vault itself in Phase 6D, and every future session picks it up from the repository automatically.

After writing: "Done. Permissions are set. You will not see approval prompts during setup."

---

Give a brief welcome:
- What this system does (2-3 sentences, plain language: "I am going to build you a personal assistant that lives in a notes vault -- a Git repository of Markdown files in your cloud workspace. It connects to your calendar, email, and task manager, and runs daily routines to keep you organized.")
- That setup has 4 parts and the first part takes about 20 minutes
- They can stop at any point and come back

---

## Phase 1B: Install Wispr Flow

Now that they know what the system is, check if they have Wispr Flow (voice-to-text dictation). This makes the rest of setup easier because they can speak their answers instead of typing.

AskUserQuestion: "One quick thing before we dive in. Do you have Wispr Flow installed? It is a voice dictation tool that lets you speak instead of type. It makes this setup easier and it is great for working with Claude day-to-day."
Options:
- Yes, I already have it
- No, what is it?
- No, and I do not want it

**If "No, what is it?":**
"Wispr Flow is a small app that turns your voice into text anywhere on your computer. Instead of typing answers to my questions, you just talk. It also works great during your day -- dictate emails, notes, task descriptions, anything. It is like having a stenographer built into your computer."

AskUserQuestion: "Want to install it now? It takes about 2 minutes."
Options:
- Yes, let us do it
- I will install it later
- No thanks, I prefer typing

**If they want to install:**
1. "Open your browser and go to **wispr.com** (or search 'Wispr Flow download')."

AskUserQuestion: "Are you on the Wispr Flow website?"
Options:
- Yes
- I cannot find it

2. "Click **Download** and install the app. It is a small download."

AskUserQuestion: "Is it installed?"
Options:
- Yes, I see it in my menu bar
- Still downloading / installing
- I ran into an issue

3. "Open Wispr Flow and go through the quick setup. It will ask for microphone permission -- click **Allow**."

4. "Try it out: click on this text input area and press the Wispr hotkey (usually Option+Space on Mac or Ctrl+Space on Windows) and say something."

AskUserQuestion: "Did it work? Did your spoken words appear as text?"
Options:
- Yes, it is working!
- The hotkey did not do anything
- It picked up my voice but the text was wrong

If working: "Great! From now on, you can speak your answers to any of my questions instead of typing. Just press the Wispr hotkey and talk."

If issues: Help troubleshoot (microphone permissions, hotkey conflicts), or let them skip and come back to it.

---

## Phase 2: Who Are You?

### 2A: Name
Ask: "What should I call you?"
- Free text input

### 2B: Company Name
Ask: "What is the name of your company or business?"
- Free text input

### 2C: Research

**Before asking more questions, research the user and their company.** Use WebSearch to look up:
- The company name (website, what they do, industry, size)
- The person's name + company (LinkedIn, role, bio)
- Relevant context: what the company sells/does, who their clients are, team size

**Present findings for verification:**

"Here is what I found about you and [Company Name]:
- [Company] appears to be a [description]
- Your role seems to be [role/title if found]
- [Other relevant details]"

AskUserQuestion: "How accurate is this?"
Options:
- That is spot on
- Mostly right, let me correct a few things
- Pretty far off, let me explain

Use corrections and research to inform the rest of the interview. If you found their actual clients, services, or team members, reference them by name later.

### 2D: Timezone
Ask: "What timezone are you in?"
Options:
- US Eastern (New York)
- US Central (Chicago)
- US Mountain (Denver)
- US Pacific (Los Angeles)

Note: "Type your timezone if it is not listed."

### 2E: Work Type
If research already reveals this, confirm instead of asking from scratch.

Otherwise ask: "What best describes your work?"
Options:
- I run my own business or consultancy (solo or small team)
- I work at a company and manage my own workload
- I manage a team and need to track their work too
- Something else (let me describe it)

---

## Phase 3: Your Tools

Collect which tools they use. We are NOT connecting them yet -- just finding out what they have. Connections happen in `/connect`.

### 3A: Calendar
Ask: "What calendar do you use?"
Options:
- Google Calendar (Gmail/Google Workspace)
- Outlook / Microsoft 365
- Apple Calendar
- I do not use a digital calendar

### 3B: Email
Ask: "What email do you use for work?"
Options:
- Gmail / Google Workspace
- Outlook / Microsoft 365
- Apple Mail
- Other

### 3C: Task Manager
Ask: "Do you use a task or project management tool?"
Options:
- ClickUp
- Asana
- Trello
- Todoist
- I do not use one (I will use this system instead)
- Something else

### 3D: Meeting Recordings
Ask: "Do you record your meetings or get automatic transcripts?"
Options:
- Yes, I use Fathom
- Yes, I use another tool (Otter, Fireflies, etc.)
- No, but I would like to start
- No, and I do not need this

### 3E: Team Chat
Ask: "Do you use a team chat app?"
Options:
- Slack (ask how many workspaces if selected)
- Microsoft Teams
- Discord
- I do not use team chat

### 3F: Time Tracking
Ask: "Do you track your time?"
Options:
- Yes, I use Rize
- Yes, I use another tool (Toggl, Harvest, etc.)
- No, but I would like to start
- No, and I do not need this

---

## Phase 4: Your Schedule

### 4A: Work Hours
Ask: "When does your workday typically start?"
Options:
- Around 7:00 AM
- Around 8:00 AM
- Around 9:00 AM
- Different time (let me specify)

### 4B: End of Day
Ask: "When do you typically wrap up?"
Options:
- Around 4:00 PM
- Around 5:00 PM
- Around 5:30 PM
- Around 6:00 PM
- Different time

### 4C: Meeting Preferences
Ask: "When do you prefer to have meetings?"
Options:
- Mornings (before lunch)
- Afternoons (after lunch)
- A specific window (e.g., 1:00-3:00 PM)
- Spread throughout the day

### 4D: Protected Time
Ask: "Do you want to protect any time for focused work (no meetings)?"
Options:
- Yes, mornings are for deep work
- Yes, I want a specific block protected (let me specify)
- No, I am flexible
- Fridays should be meeting-free

### 4E: Lunch
Ask: "When do you usually take lunch?"
Options:
- Around 12:00 PM
- Around 12:30 PM
- Around 1:00 PM
- It varies / I eat at my desk

---

## Phase 5: Your Workflow Preferences

### 5A: Morning Routine
Ask: "How do you want to start your workday with Claude?"
Options:
- Full morning review: summary of tasks, meetings, and priorities with options to adjust (recommended)
- Quick check: just tell me the one most important thing
- Meeting prep only: just prepare me for today's meetings
- No morning routine

### 5B: End-of-Day Routine
Ask: "How do you want to end your workday?"
Options:
- Full processing: Run one command before wrapping up. Claude processes calls, emails, messages, and builds tomorrow's plan while you walk away. (recommended)
- Simple daily note: Claude writes a summary of what happened today
- Manual brain dump: I tell Claude what to capture
- No end-of-day routine

### 5C: Client Structure
If your research revealed clients, pre-populate: "It looks like you work with clients like [Client A] and [Client B]. Are these your current active clients?"

Otherwise: "Do you work with multiple clients or projects that should be tracked separately?"
Options:
- Yes, I have multiple clients (ask for names)
- Yes, I have multiple projects but they are all internal
- No, I mainly do one type of work

If they have clients, confirm the list (free text, comma-separated). Pre-fill with any names from research.

### 5D: Client Tiers (if applicable)
If they listed clients: "Are some clients higher priority than others?"
Options:
- Yes, let me rank them (then ask Tier 1 vs Tier 2)
- They are all roughly equal
- It changes week to week

---

## Phase 6: Build Everything

Tell the user what you are about to create before creating it.

### 6A: Vault Folder Structure

**If Phase 0 detected the user is already inside a vault** (repo is a subfolder of the current directory):
- The current directory IS the vault. Do not ask where to create it.
- Set `VAULT_PATH` to the current directory if it is not already set.
- Tell the user: "I see you are already in a notes folder. I will build the system right here."
- Skip the location question.

**If running from the repo folder** (no vault detected):

The vault must live in its own Git repository with a GitHub remote. The cloud workspace is temporary -- the repository is the only thing that persists between sessions, so "where should the vault live" means "which repository," not "which folder."

AskUserQuestion: "Your vault needs its own GitHub repository (that is what makes it permanent). How do you want to set that up?"
Options:
- Create a new private GitHub repo for it now (recommended)
- I already have an empty repo for it
- Build it here for now; I will connect it to GitHub before we finish

**If "create a new repo":** Walk them through it, one step at a time: "Go to **github.com/new**, name the repository (something like `Brain`), set it to **Private**, and click **Create repository**. Do not add a README." (If a GitHub tool is connected in this session, offer to create the repo for them instead.) Then in the workspace: create the vault folder (`Brain/` next to the setup files), run `git init` in it, and `git remote add origin <their repo URL>`. Set `VAULT_PATH` to that folder.

**If "existing repo":** Ask for the repository URL (or name, if it is already available in this session). Clone it into the workspace, or if the workspace cannot reach it yet, initialize the folder locally and add the remote. Set `VAULT_PATH` accordingly.

**If "build here":** Create `Brain/` next to the setup files, run `git init` in it, and set `VAULT_PATH` to it. Tell them clearly: "Heads up -- until we connect this to GitHub and push, your vault only exists in this temporary workspace. We will fix that at the end of setup, before you close anything." Phase 7 must not complete without resolving this.

Create the structure at `VAULT_PATH`:
```
<vault root>/
├── Inbox/
├── [CompanyName]/  (if provided)
│   ├── Hiring/
│   ├── SOPs/
│   └── Transcripts/
├── Work/
│   ├── Clients/    (with subfolders per client)
│   │   └── <ClientName>/
│   │       ├── Transcripts/
│   │       └── Archive/
│   ├── Transcripts/
│   ├── Sales Leads/
│   └── Daily/
├── Projects/
│   └── Personal/
├── Resources/
│   ├── API Keys/
│   ├── Concepts/
│   ├── People/
│   ├── Reference/
│   └── Health/
├── Graph/
├── Templates/
├── Archive/
└── Attachments/
```

Skip folders that do not apply based on their answers.

**Give the vault a schema.** `/vault-audit` (installed in 6E) keeps the vault tidy every night, but it needs a design contract to enforce. `mkdir -p VAULT_PATH/.claude VAULT_PATH/scripts VAULT_PATH/_generated/vault-hygiene` first -- a fresh vault has neither yet, and both are about to be written to. Write `VAULT_PATH/_generated/vault-hygiene/vault-schema.md` now, while the folder structure is still fresh from the answers above. Its format is documented in `.claude/commands/vault-audit.md`'s Init section -- a YAML block with `version`, `root_whitelist` (the files allowed to sit at vault root, e.g. `CLAUDE.md`, `CHANGELOG.md`, `README.md`), `protected`, `folders` (one entry per folder above with a one-line purpose, `naming` for dated records, `no_merge: true` for folders that should be filed but never merged or rewritten, including any batch/generated one-file-per-item output folder), `frontmatter_required` (usually `[type, created]`), and an `embedding:` block (`owners:` = the person's name and their company's name so those are dropped from entity overlap; `gate_high`, `gate_fallback`, `stale_days`, `canonical_home_dirs` default sensibly). The `vault-audit.md` Init section documents every field.

Derive `protected` by convention, do not interrogate the user for it: `Archive/`, `Attachments/`, `Templates/`, `.claude/` and any other dot-folder, `.handoffs/`, and any generated-output file the system overwrites wholesale (e.g. `Inbox/Today.md`). That covers nearly every vault. The only thing worth asking is one plain-language question, folded into this phase rather than a separate interrogation:

AskUserQuestion: "Are there any folders I should never reorganize, like a private journal? I will still keep them tidy if you want, just never merge or rewrite them."
Options:
- No, nothing like that
- Yes, keep it tidy but never rewrite it (they name the folder)
- Yes, never touch it at all (they name the folder)

Map the answer: "keep tidy but never rewrite" -> mark that folder `no_merge: true` in the schema (filed and indexed, never merged or rewritten). "Never touch it at all" -> add it to `protected` (skipped entirely). Everything else about the schema -- folder purposes, naming patterns -- write from the structure above and correct it later; `/vault-audit`'s own Step 5 self-amends the schema when it sees the same misfile pattern 3+ nights running, so an imperfect first draft is fine.

Also copy the audit scripts into the vault: `mkdir -p VAULT_PATH/scripts && cp REPO_PATH/templates/scripts/vault-audit.py REPO_PATH/templates/scripts/vault-embed.py VAULT_PATH/scripts/`. (`vault-embed.py` is the semantic layer `/vault-audit` Step 4b uses to detect same-subject forks; it imports `vault-audit.py`, so ship both.)

Also copy the local-routines backup script and registry template: first `cp REPO_PATH/templates/scripts/local-routines-backup.sh VAULT_PATH/scripts/local-routines-backup.sh && chmod 755 VAULT_PATH/scripts/local-routines-backup.sh && mkdir -p "VAULT_PATH/Resources/Reference"` (stop and report if this fails), then as a SEPARATE command `if [ ! -f "VAULT_PATH/Resources/Reference/Local Routines Registry.md" ]; then cp "REPO_PATH/templates/Local Routines Registry.md" "VAULT_PATH/Resources/Reference/Local Routines Registry.md"; fi`. Keep the two commands separate: chaining the guard onto the install line with `&& ... ||` would run the copy whenever an earlier step failed. The `if [ ! -f ]` guard matters: on a repeat setup of an existing vault the registry already holds hand-recorded task settings that exist nowhere else, so it is never overwritten (the script copy is safe to refresh). When the registry was just created, set the `created` date in its frontmatter to today. This is the backup for any scheduled task the user later creates as a LOCAL routine in the Claude Desktop app (Guideline "Local routines are backed up in the vault" in CLAUDE.md).

Also create `VAULT_PATH/.gitignore` with at least:
```gitignore
.env
.DS_Store
```
(Everything else in the vault -- including `.claude/settings.json`, `.claude/commands/`, and `.handoffs/` -- is meant to be committed. Do NOT ignore the `.claude/` folder.)

Also create `VAULT_PATH/.gitattributes` with:
```gitattributes
# Parallel sessions append to the same Markdown files. Union merge keeps
# both sides instead of raising a conflict the user would have to see.
*.md merge=union
```

Then install the autosync safety net. Copy `templates/vault-autosync.yml` from this repo into the vault:
```
mkdir -p VAULT_PATH/.github/workflows
cp REPO_PATH/templates/vault-autosync.yml VAULT_PATH/.github/workflows/vault-autosync.yml
```
This GitHub Action keeps the vault converged on `main` without the user ever touching GitHub: any side branch a session leaves behind (cloud sessions often work on `claude/...` branches) gets merged into `main` and deleted automatically -- on every push, when a PR is opened, and in an hourly sweep. Install it unconditionally and do not ask the user about it; together with the Git Autopilot rules in CLAUDE.md, it is what makes version control invisible to them.

### 6B: CLAUDE.md

Read `templates/CLAUDE.md` from this repo as the base. Customize with everything from the interview and web research:

- Replace all placeholders (`[Your Name]`, `[Your Timezone]`, `[YourCompany]`) with real values
- Replace `[Claude Runtime]` with `Claude Code on the web`
- Fill in company context from research
- Update daily schedule skeleton with their hours, lunch, meeting window
- Update integrations section: remove unused tools, add tools they mentioned
- Use actual client names (not `[Client A]`) in priority tiers and examples
- Adjust meeting window and protected time based on preferences

Write to `VAULT_PATH/CLAUDE.md`.

### 6C: Secrets

Two rules for credentials in the cloud edition:
1. **Never commit secrets to the vault repository** (`.env` is in `.gitignore` for this reason).
2. **A plain `.env` file does not survive between cloud sessions** -- the workspace is temporary. The durable home for secrets is the **Claude Code environment settings** (environment variables configured for the environment, injected into every session).

Do this:

1. Create `VAULT_PATH/.env` as a commented template with only the services they selected (values get filled in during `/connect`):
```bash
# Password keychain file for Claude (untracked -- never committed)
# Filled in during /connect. The permanent copies of these values live in
# your Claude Code environment settings as environment variables.

# (only include sections for tools they selected)
```
2. Tell the user (plain language): "When we connect your tools later, each password or key gets saved as an environment variable in your Claude Code environment settings. That way it is available every time you open a session, without ever being stored in your notes. The `.env` file here is just a scratch copy for this session."

### 6D: Vault Settings (persist across sessions)

Write `VAULT_PATH/.claude/settings.json` -- the vault's **committed** settings file -- using the permissions from `examples/settings.json` as the base, plus any MCP permissions for tools they selected. Because this file is checked into the vault repository, every future cloud session starts with the right permissions automatically.

Do NOT put these in `VAULT_PATH/.claude/settings.local.json` -- local settings are untracked by convention and would evaporate with the workspace. (The `~/.claude/settings.json` from Phase 1 also only covers the current session.)

### 6E: Skills

**Golden rule: install EVERY command, no exceptions.** Every `.md` command in this repo's `.claude/commands/` is a skill we want every user to have. They are NOT optional. Do not pick a subset, do not gate installation on the user's workflow answers, and do not skip a command because it "looks unused." A user who never picked "full EOD" still gets `/eod`; a user who picked "quick check" still gets `/morning`. Workflow preferences (Phase 5) only decide which command you *recommend as their daily driver* and how you *customize* the tool-specific ones -- they never decide what gets installed.

This is the historical failure mode of this setup: commands kept getting dropped during onboarding because the install list was hand-enumerated and conditional. The fix is to copy the whole folder, not a list.

Claude Code on the web auto-discovers `.claude/commands/` files, so installing means copying the whole folder into the vault -- no manual upload step.

1. **Copy every command file, unconditionally.** Create `VAULT_PATH/.claude/commands/` and copy the complete contents of the repo's command folder into it:
   ```
   mkdir -p VAULT_PATH/.claude/commands
   cp REPO_PATH/.claude/commands/*.md VAULT_PATH/.claude/commands/
   rm -f VAULT_PATH/.claude/commands/onboard.md   # setup is done; the rest stay
   ```
   This is a glob copy on purpose: any command added to the repo later is installed automatically, with no list to keep in sync. After copying, verify the count -- the vault should contain every `.md` from the repo's `.claude/commands/` (minus `onboard.md`). If any are missing, copy them; never leave a command behind.

   The full set this installs, for reference (not a checklist to enumerate manually -- the copy above already covers it):
   - **Setup:** `train.md`, `connect.md`, `finish.md`
   - **Session continuity (the backbone of context/task management):** `handoff.md`, `pickup.md`. A single Claude session has a finite context window; once it fills (or the user runs `/clear`, closes the window, or hits compaction), everything not written down is lost. `/handoff` checkpoints the live thread of work into `VAULT_PATH/.handoffs/<name>.md`; `/pickup` reloads it in the next session. They double as a track record of in-flight workstreams.
   - **Decision-making + improvement:** `strategy.md`, `optimize.md`, `build-skill.md`, `learn.md`
   - **Knowledge graph:** `graph-sync.md`, `graph-daily.md`
   - **Daily drivers + EOD pipeline:** `morning.md`, `eod.md`, and the phase-split EOD commands `eod-gather.md`, `eod-sync.md`, `eod-time.md`, `eod-note.md`, `eod-today.md` (`/eod` and the phase commands reference each other -- shipping only some of them breaks the pipeline mid-run, which is exactly how commands "disappear after the user runs a slash command"). `vault-audit.md` belongs here too -- `/eod` Phase 5.5 invokes it every night, and its `init` mode is what wrote `_generated/vault-hygiene/vault-schema.md` back in 6A.
   - **Other utilities:** `daily-note.md`, `brain-dump.md`, `monthly-review.md`

2. **Then customize the tool-specific ones in place** with their specific tools, clients, and schedule. Customization happens *after* installation and never affects whether a file is installed:
   - `eod.md` and the `eod-*` phase commands -- wire to their actual tools; if they do not use a time tracker, soften `eod-time.md` to a no-op note rather than deleting it.
   - `morning.md` -- their schedule, meeting window, clients.
   - Use actual client names and their real toolset throughout.

3. **Create the handoff storage directory:** `VAULT_PATH/.handoffs/` (where `/handoff` stores named handoff files).

3b. **If the user also uses Claude Cowork:** copy `REPO_PATH/cowork-commands/` into `VAULT_PATH/cowork-commands/` (all of it -- same golden rule). These are the same commands with the YAML frontmatter Cowork needs; the user uploads them through Cowork's **Customize** section whenever they want a skill available there. Do not walk through uploads during onboarding -- just tell them the folder exists and every file in it is upload-ready.

4. **Install the Superpowers plugin (the USER runs this, not you).** Superpowers is a community plugin that adds a library of high-leverage skills (brainstorming an idea into a spec, systematic debugging, writing plans, test-driven development, and more). It installs as a custom Claude Code plugin.

   **You cannot install it for them.** `/plugin` is an interactive slash command that only works when the user types it into the Claude Code chat input themselves; it is not a tool you can call, and it does not run from `/onboard`. Your job here is to hand them the exact commands, explain the trust note, and confirm it worked, not to run anything.

   **Give them this trust note first:** plugins can run code on their machine with their user permissions, so they should only add marketplaces from a source they trust. Superpowers (`obra/superpowers-marketplace`) is the one we recommend and use. If their company restricts which plugins or marketplaces can be installed, they should get sign-off first.

   Then tell the user to type these two commands themselves, one at a time, directly into the chat input (as slash commands, not as a message to you):
   ```text
   /plugin marketplace add obra/superpowers-marketplace
   /plugin install superpowers@superpowers-marketplace
   ```
   The first registers the plugin's GitHub repo as a marketplace; the second installs the plugin from it. After it installs, have them restart Claude Code (or run `/reload-plugins`) so the skills load. It installs at the user level (`~/.claude/plugins/`), so it is available in every project, not just this vault.

   **The general pattern (for adding any custom plugin later):** `/plugin marketplace add <github-owner/repo>` registers a *marketplace* (the repo must be a plugin marketplace, meaning it contains a `.claude-plugin/marketplace.json`), then `/plugin install <plugin-name>@<marketplace-name>` installs a plugin from that marketplace (the `<marketplace-name>` comes from the marketplace's manifest and can differ from the repo name). Whenever we publish a plugin, we will give them the exact marketplace repo, plugin name, and marketplace name to use. Only ever add marketplaces you trust.

   Confirm with the user that the skills show up after restart. If `/plugin` is not available in the interface they are using (it is a Claude Code feature; Desktop/CoWork may differ), or the install fails, note it as a task in `Inbox/[YourCompany].md` and continue. Do not block setup on this.

The daily graph sync is already included as Phase 6 of `/eod`; the standalone `/graph-daily` is available for manual runs.

### 6F: Knowledge Graph Setup

Create the Graph folder and starter files at `VAULT_PATH/Graph/`:

1. **entity-registry.md** -- Pre-populate with entries for each client from Phase 5C and the user's company:

```markdown
# Entity Registry

Master lookup table for the knowledge graph. Maps searchable terms to wiki-link targets.

## How This Works
When the graph sync runs, it searches vault files for these terms and automatically creates wiki-links on first mention. Aliases are alternative terms that resolve to the same target.

Add new entries as you create entity pages (people, concepts, clients, projects).

## Clients

| Term | Page | Aliases |
|------|------|---------|
| [ClientName] | Work/Clients/[ClientName]/Company Profile | [abbreviations, alternate names] |

## People

| Term | Page | Aliases |
|------|------|---------|

## Concepts

| Term | Page | Aliases |
|------|------|---------|

## SOPs & Guides

| Term | Page | Aliases |
|------|------|---------|
```

2. **index.md** -- Empty starter with header:

```markdown
# Vault Index

Alphabetical directory of all pages in the vault.

*Run `/graph-sync` to populate this index.*

*Last updated: [today's date]*
```

Do not create MOC files yet. Those are generated by `/graph-sync` based on actual vault content.

### 6H: Integral Methodology Document

Copy `templates/integral-methodology.md` from the setup repo into the vault at `VAULT_PATH/Resources/Reference/How We Think About AI Agents.md`.

This document contains Integral's philosophy on context engineering, progressive trust, skills, the daily loop, and how to get the most out of the system. It ships with every vault and gives the user a reference they can revisit as they learn the system.

Do not customize this file. It is the same for every user.

### 6I: Inbox Starter Files

Create a starter task file for each client: `VAULT_PATH/Inbox/ClientName.md`. Each file should use the standard structure: Open Tasks, Pending from Others, Key Dates, Notes, Reference, Completed.

Also create `VAULT_PATH/Inbox/[YourCompany].md` (use the actual company name) for cross-client, agency, hiring, and internal tasks. It uses the same structure as a client file, plus a `## Brain Dump` section near the top for loose captures.

Create `VAULT_PATH/Inbox/Personal.md` with the same structure for personal tasks.

Create `VAULT_PATH/Inbox/Today.md` with a simple first-day message. Today.md is the daily entry point; it gets regenerated nightly by the EOD pipeline.

---

## Phase 7: Wrap Up and Restart

### 7A: Push the Vault (do this FIRST)

Everything built so far exists only in this temporary workspace until it is pushed. Before any wrap-up talk:

1. In `VAULT_PATH`: `git add -A && git commit -m "Initial vault setup"`
2. `git branch -M main` (a fresh `git init` can leave the repo on a different default branch -- normalize it first), then `git push -u origin main`
3. **If there is no remote yet** (the user chose "build it here" in 6A): stop and resolve it now. Walk them through creating the private GitHub repo (github.com/new), run `git remote add origin <URL>`, and push. Do not end onboarding with an unpushed vault -- if the user insists on skipping, warn in the strongest plain terms that their new vault will be gone when this workspace is recycled.
4. **If the push is rejected because the token cannot write workflow files** (some GitHub App tokens lack the `workflows` scope and refuse pushes touching `.github/workflows/`): do not surface Git jargon or give up. First try creating `.github/workflows/vault-autosync.yml` on GitHub directly with the session's GitHub tools (e.g., the file-creation tool), then remove the file from the local commit and push the rest. If no path works, push everything else, note the missed workflow in CLAUDE.md's Update Log as a TODO for a future session, and move on -- the vault still works; it just lacks the branch-cleanup safety net until the file lands.
5. Confirm: "Your vault is safely on GitHub now. Every session from here on starts by cloning it and pushes your changes back up automatically -- you never need to touch GitHub yourself."

### 7B: Wrap Up

Tell the user what was created (list every folder and file).

Then explain what happens next:

"Your notes folder is built and your instruction manual is customized. Before we continue, start a fresh Claude Code session in your vault so it picks up your new files and permissions."

Walk them through it step by step:

1. "Your vault is the **[repo name]** repository on GitHub. All your notes live there as Markdown files, and every Claude Code session opens a fresh copy of it in a cloud workspace."
2. "Take a moment to browse the folders -- Inbox, Work, Resources, and the rest. These are all just text files Claude Code reads and writes for you."

AskUserQuestion: "Can you see your folders?"
Options:
- Yes, I can see Inbox, Work, Resources, etc.
- I do not see them yet
- Something does not look right

4. Walk through the session handoff explicitly. This is a common sticking point, so be very literal:

   - "Here is exactly what to do next. I will walk you through it one step at a time."
   - "Step 1: Start a fresh Claude Code session on your vault repository (**[repo name]**)."
   - "Step 2: Once the new session opens, type exactly this: `/train`"
   - "That is it. `/train` is the next step and it will walk you through how the system works."

   AskUserQuestion: "Do you know what to do next?"
   Options:
   - Yes, open a new session in my vault, then type /train
   - Can you repeat that?
   - I am confused

   If confused or repeat: Re-explain with even simpler language. Offer to stay in the conversation until they confirm they have the new session open.

**Important final note:** "When you start the new session, Claude will automatically read your CLAUDE.md file. That is the instruction manual we just built together. It has everything about you, your tools, your schedule, and how you like things done. You do not need to explain anything again. `/train` will walk you through it."

---

## Error Handling

- If the user seems confused, back up and explain in simpler terms
- If they want to skip a section, let them and note what was skipped
- If a file already exists (ran `/onboard` before), ask before overwriting
- If running from the repo directory, the vault gets its own repository (see 6A) -- never build it inside the setup repo
- Never hardcode `Brain/` when `VAULT_PATH` is known. All generated files should be written relative to `VAULT_PATH`.
