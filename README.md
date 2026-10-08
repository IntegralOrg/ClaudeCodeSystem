# Claude Code Personal Assistant System

An AI-powered personal assistant built on [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and a Git-backed Markdown vault. The vault is the operating system; Claude Code is the brain. Together they handle task management, meeting processing, email triage, time tracking, client work, and daily planning -- replacing a human executive assistant.

This is the **cloud edition**: it starts in [Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web), in your browser, and can be added to your own computer later. Your vault is a private Git repository of Markdown files that Claude reads and writes directly. Nothing has to be installed to start.

> **You do not need to be technical.** Claude walks you through everything step by step.
>
> **What you will need:** a GitHub account and a Claude Max plan (routines and cloud sessions need it). The front door for non-technical readers is [the one-page guide](https://integralorg.github.io/ClaudeCodeSystem/).

## Get Started
You need a GitHub account and a Claude Max plan.
1. Click **Use this template** (private, name it `brain`).
2. Open the new repository (`brain`) at claude.ai/code and install the Claude GitHub app on it when asked. Setup starts by itself in that first session.
3. Put it on your computer: `System/Adding Your Computer.md` (Claude Desktop, GitHub Desktop, clone to `~/Brain`).
Questions: ask your agent. It answers from `System/`.

Connection steps for each tool (calendar, email, tasks, calls, chat) are in [Connecting Tools](System/Connecting%20Tools.md).

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                  You: ask your agent (it reads today's note)      │
│                      /morning is optional                         │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                     Claude Code (AI Agent)                        │
│              Reads CLAUDE.md · Executes skills                    │
│              Reads .env · Calls APIs · Writes vault files        │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│   MCP Servers          REST/GraphQL APIs       Custom Scripts     │
│   (your tools)         Gmail                   md-to-gdoc.py      │
│   Google Calendar      Slack (N workspaces)    (your scripts)     │
│   Task Manager         Google Drive/Docs                          │
│   Context7             Transcript Service                         │
│                                                                    │
├──────────────────────────────────────────────────────────────────┤
│                  Git-Backed Vault (Markdown)                      │
│   Inbox/Today.md · Inbox/<Client>.md · Work/Clients/<Client>/    │
│   [YourCompany]/ · Work/Daily/ · Templates/ · Resources/         │
└──────────────────────────────────────────────────────────────────┘
```

## How It Works

**Setup runs itself.** A new vault carries a `SETUP_PENDING` marker. A session-start hook sees it and tells Claude to follow `System/Setup Procedure.md`: it asks for the transcript of your discovery interview (or five short questions), builds your `CLAUDE.md`, folders, and client pages, creates your routines, checks your keys, and then deletes the marker so setup never runs twice.

**The daily loop:**
1. **You work with Claude** (in Claude Desktop, or in a cloud session on the web or your phone): drafting, research, tasks, notes.
2. **Your work is saved for you.** When Claude finishes a turn, a Stop hook lands the changes on `main`: `scripts/cloud-land.sh` in the cloud, `scripts/land-local.sh` on your computer. You never run Git.
3. **Routines run on a schedule** from the definitions in `System/routines/`: End of Day (weeknights), Vault Hygiene (nightly), Monthly Review (the 1st). Which are live is recorded in `System/Routines.md`.
4. **You are told when something is wrong**, even with no connectors: at the start of every session two hooks speak first. `landing_health.py` says when saves have been failing; `routine_health.py` says when a routine has not run when it should.

**Keys are one human step.** Routines name the keys they need; `python3 scripts/check-keys.py` reports which names are missing and never prints a value.

## What the Setup Creates

A vault created from this template ends up with:

- **A `CLAUDE.md` filled in for you** (name, role, company, time zone, tools, week shape, first jobs) that Claude reads every session.
- **Folders** for clients, projects, daily notes, monthly reviews, personal notes, and reference, plus a client page for each client or project you named.
- **Three scheduled routines** (End of Day, Vault Hygiene, Monthly Review) defined in `System/routines/` and recorded in `System/Routines.md`.
- **Guard hooks and an action log** wired in the committed `.claude/settings.json`, the same in the cloud and on your computer.
- **The System Journal** capturing every session, and **session telemetry** showing where the system wastes effort.
- **A guidance library** in `System/` that your agent answers questions from.
- **Slash commands** for morning review, end-of-day processing, handoffs, and other workflows.

## Repository Structure

```
ClaudeCodeSystem/
├── CLAUDE.md                           # The vault's instruction manual (filled in by setup)
├── SETUP_PENDING                       # Marker: setup runs from System/Setup Procedure.md until it is deleted
├── CHANGELOG.md                        # Template change history
├── LICENSE                             # CC BY-NC-ND 4.0
├── README.md                           # This file
├── .env.example                        # Key names with descriptions (never values)
├── .gitattributes                      # Markdown union-merge so parallel sessions never conflict
├── .gitignore                          # Allow-list for .claude/, secrets and local state ignored
├── .claude/
│   ├── settings.json                   # Committed permissions and the guard, landing and session hooks
│   ├── commands/                       # Slash commands (auto-discovered): morning, eod and phases, handoff, pickup, vault-audit, ...
│   └── skills/drive-screen/            # Take control of the desktop when a step must be clicked through
├── .github/workflows/                  # vault-autosync.yml (skipped on the template itself)
├── System/
│   ├── Setup Procedure.md              # What the first session runs, step by step
│   ├── How This Works.md               # The loop, the brakes, what to check when something seems off
│   ├── Connecting Tools.md             # Per-tool connection click paths
│   ├── Routines.md                     # Which routines are live, ids, schedules, how to create one by hand
│   ├── Adding Your Computer.md         # Claude Desktop, GitHub Desktop, clone to ~/Brain
│   ├── Getting Help.md                 # Where to ask, what to send
│   └── routines/                       # Definitions: eod.md, vault-hygiene.md, monthly-review.md
├── Templates/Client Note.md            # Client profile skeleton
├── Resources/Reference/                # Local Routines Registry, How We Think About AI Agents
├── cowork-commands/                    # CoWork versions of the commands (YAML frontmatter, manual upload)
├── docs/
│   ├── index.html                      # The one-page front door (GitHub Pages)
│   ├── DEVELOPING.md                   # Maintainer notes for this template
│   ├── vault-design-guide.md           # How to build the vault (folder structure, inbox, templates)
│   ├── integration-architecture.md     # How Claude connects to your tools
│   └── daily-workflow.md               # Today.md + /morning + EOD pipeline
├── scripts/
│   ├── hooks/                          # guard_secrets, guard_state_writes, guard_vault_path, log_tool_use,
│   │                                   #   setup_pending, landing_health, routine_health, session_context
│   ├── cloud-land.sh                   # Cloud sessions: land edits on main (Stop hook)
│   ├── land-local.sh                   # Local sessions: land edits on main (Stop hook)
│   ├── check-keys.py                   # Which key names each routine needs and which are missing
│   ├── envload.py / with-env.py        # Load credentials for scripts, or for a one-off command
│   ├── vault-audit.py / vault-embed.py # Nightly hygiene and same-subject detection
│   ├── graph-render.py                 # Render the knowledge graph from frontmatter
│   ├── profile-convert.py              # Convert profiles to the Current State / Log shape
│   ├── sanitize_ingest.py              # Clean text before it is written into the vault
│   ├── local-routines-backup.sh        # Mirror local desktop routines into the vault
│   ├── system-journal/                 # Session capture, distill, telemetry
│   └── tests/                          # Unit tests (python -m pytest scripts/tests -q)
├── _generated/                         # Machine-written output (action log, audit state, landing log)
└── examples/scripts/                   # Optional scripts (NOT commands), e.g. md-to-gdoc.py
```

## Documentation

| Document | What It Covers |
|----------|---------------|
| [How This Works](System/How%20This%20Works.md) | The loop, what runs when, the brakes, what to check when something seems off |
| [Routines](System/Routines.md) | Which routines are live, their schedules and ids, how to create one by hand, what to do when one is stale |
| [Connecting Tools](System/Connecting%20Tools.md) | Per-tool connection click paths: Gmail, Google Calendar, Slack, Fathom, ClickUp, and Claude plugins |
| [Adding Your Computer](System/Adding%20Your%20Computer.md) | Claude Desktop, GitHub Desktop, and cloning the vault to `~/Brain` |
| [Vault Design Guide](docs/vault-design-guide.md) | Folder structure, inbox system, CLAUDE.md design, skills, integrations, monthly reviews, step-by-step build guide |
| [Integration Architecture](docs/integration-architecture.md) | How Claude connects to your tools: direct connections, tool credentials, custom scripts, scheduled automation |
| [Daily Workflow](docs/daily-workflow.md) | Today.md structure, /morning interactive review, EOD 5-phase pipeline, scheduled automation, tracking list pattern, carry-forward system |

## Key Concepts

### CLAUDE.md
The instruction file at your vault root. Claude reads it automatically every session. It defines your folder structure, integrations, preferences, workflows, and routing rules. Think of it as Claude's operating manual. Keep it under 30K characters; move detailed content to reference files.

### Skills
Successful tasks turned into repeatable routines. Each skill is a text file that defines a multi-step workflow. Type `/skill-name` and Claude runs the full process. Examples: `/eod-gather` (collect all daily data), `/morning` (interactive morning review), `/audit-deliver` (populate a client portal). Your skills library grows over time as you turn successful one-off tasks into reusable routines.

**Two formats exist for different runtimes:**
- **Claude Code:** Skills live in `.claude/commands/` and are auto-discovered. No special formatting needed.
- **Claude Code, skills with scripts:** A skill that needs scripts or reference files lives in its own folder under `.claude/skills/<name>/` with a `SKILL.md` at the top. `drive-screen` is the first: it lets Claude take real control of the desktop (Windows, macOS, Linux) for steps that can only be clicked through, and only after you hand it the keyboard for that session.
- **Claude CoWork:** Skills require YAML frontmatter (`name:` and `description:` fields in a `---` block) and must be manually uploaded through the **Customize** section in the app settings. The `cowork-commands/` directory contains pre-formatted versions of every slash command ready for upload; skills with scripts (`.claude/skills/`) have no CoWork mirror because their scripts run on the user's own machine.

### Session Continuity (`/handoff` and `/pickup`)
Every user gets these two commands. They solve the single biggest limitation of working with an AI agent: a session's memory is finite. When the context window fills up, or you run `/clear`, close the window, or the conversation gets compacted, everything that was only "in the chat" is gone.

- **`/handoff <name>`** writes a self-contained briefing to `.handoffs/<name>.md` -- the goal, what's been done, what was tried and rejected, the exact next steps, and which files and commands the next session should reload -- then **commits and pushes it** (cloud sessions start from a fresh clone, so an unpushed handoff would never reach the next one). Run it before `/clear`, before ending a session mid-task, or whenever a long conversation is getting unwieldy. The handoff is written *to the next Claude*, not to you, so it reads like a briefing for a colleague who just walked in.
- **`/pickup [name]`** (in the next session) reads that file, reloads the listed context in parallel, sanity-checks it against the current state of the repo, and reports back where you left off, all without you re-explaining anything. With no argument it lists the available handoffs and asks which to resume.

Because each handoff is a named, persistent file inside the vault, they accumulate into a **track record of in-flight workstreams**: you can keep several open across different projects, and old ones stay put until you delete them. This is better task and context management than holding everything in one long chat. Use it for mid-stream work; `/eod` still handles end-of-day wrap-up and routing items to your task inboxes.

> Named `/pickup` (not `/resume`) so it doesn't shadow Claude Code's built-in `/resume` session picker.

### Tracking Lists (The Manifest Pattern)
Long-running workflows track every extracted item in a tracking list (`/tmp/eod-manifest-TODAY.md`). Each item gets: description, client, type, source, destination, status. This makes sure nothing gets lost during long processes.

### File Writes
When Claude finishes a turn, the Stop hook lands your changes on `main`: `scripts/land-local.sh` on your computer, `scripts/cloud-land.sh` in the cloud. You never run Git. Git history is the rollback: every change is recoverable from it.

### Route-As-You-Go
Every extracted item is routed to its destination file immediately, not batched for later. This prevents data loss if a step fails partway through or the process runs long.

### Vault Hygiene and Canonical Detection
`/vault-audit` runs every night (standalone, or as an EOD phase) and keeps the vault matching its own design contract. Each run: **(1) structure** -- walks the tree, refiles misfiled notes, backfills frontmatter, stages removals into `_generated/vault-hygiene/audit-trash/` (never deletes); **(2) index** -- hashes every file and keeps a one-line concept/entities row per note; **(3) embeddings** -- embeds changed notes locally and generates same-subject candidate pairs; **(4) canonical proposals** -- a comparator classifies each pair as a version-fork, a duplicate, or legitimately distinct, a deterministic rule picks the winner, and the proposal lands in `_generated/vault-hygiene/pending-supersession-review.md`; **(5) file-mode review** -- you edit the `decision:` line in each block (`confirm` folds and retires the loser, `confirm-keep` labels only, `reject`, or `swap`), and the next run applies your decisions; **(6) invariant** -- a fail-loud check that no canonical/superseded marker is dangling, chained, or self-contradictory. Nothing is merged or hidden without a human decision; a wrong merge is high-consequence and near-invisible, so the human gate is mandatory.

Run the embedding step directly when you want to inspect candidates:

```
# in the cloud / a scheduled run (self-installs its one dependency at run start):
python3 scripts/vault-embed.py report --vault <path> --install

# locally (installs the embedder into a throwaway env):
uv run --python 3.12 --with fastembed,numpy scripts/vault-embed.py report --vault <path>
```

**Privacy:** the **embedding** step runs in-process with a small local model (`bge-small`) and sends no note content off the machine; its only outbound call is a one-time download of the model weights. (The separate **judging** step hands the candidate pair's text to Claude, the same as any other Claude session that reads your vault.) After a file or folder rename, run `python3 scripts/vault-embed.py migrate --vault <path> --rename "<old>" "<new>"` to re-key the saved state so nothing re-embeds or re-judges. Thresholds, the owner/company exclusion list, and the staleness window are config in the schema's `embedding:` block.

### EOD Command
End of Day is a scheduled routine, created at setup from `System/routines/eod.md` and recorded in `System/Routines.md`. It runs weeknights in the cloud and writes the daily note. `/eod` is the manual re-run when you want it now.

## Guardrails

Hooks in `scripts/hooks/` (wired in the committed `.claude/settings.json`) keep the assistant honest: `guard_secrets.py` blocks any attempt to read, print, or search the credentials file or the environment; `log_tool_use.py` writes one masked line per tool call to `_generated/agent-actions/`; `guard_state_writes.py` keeps client profiles to one `## Current State` plus an append-only `## Log`; `session_context.py` starts each session with the branch, uncommitted work, and the newest handoff; and `landing_health.py` and `routine_health.py` say so at session start when saves are failing or a routine has not run. Scripts load credentials themselves through `scripts/envload.py`, and a one-off call goes through `python3 scripts/with-env.py -- <command>`. The full table is in `scripts/hooks/README.md`.

Two proof commands, run from the vault root (expect `exit=2`, then `exit=0`):

```bash
echo '{"tool_name":"Read","tool_input":{"file_path":".env"}}' | python3 scripts/hooks/guard_secrets.py; echo "exit=$?"
echo '{"tool_name":"Read","tool_input":{"file_path":"README.md"}}' | python3 scripts/hooks/guard_secrets.py; echo "exit=$?"
```

## Knowledge Graph

`scripts/graph-render.py` renders `Graph/index.md` and the MOCs from
frontmatter and, when present, the concept index (`_generated/vault-hygiene/vault-index.json`, written by `/vault-audit`); `/graph-daily` and `/graph-sync` drive it. Graph files are
generated, not hand-edited, and links are structural edges only (no inline wiki-link pass).

## FAQ

**Do I need all these tool connections?**
No. Start with Calendar + Email + your meeting transcript service. Add connections as you need them.

**Do I need to install anything?**
Not to start: setup runs in Claude Code on the web, in your browser, from any Mac, Windows, or Linux machine. To also work from your own computer, follow `System/Adding Your Computer.md` (Claude Desktop, GitHub Desktop, Git, and on Windows Python 3).

**How much does this cost?**
You need a [Claude Max plan](https://claude.ai) (routines and cloud sessions need it) and a free GitHub account. Connections to Google, Slack, and similar services are within their free tiers for personal use. Some tools (like meeting transcript services or time trackers) have their own pricing.

**Can I use this for a team?**
The system is designed for one person. You could adapt it for a small team, but it would need significant customization.

**What if the End of Day routine fails partway through?**
Its next run starts fresh, and `Work/Daily/<date>.md` records which routines ran. See "If a routine is stale or not live" in `System/Routines.md`.

**Can I run the routines on a schedule?**
They already are: setup creates End of Day, Vault Hygiene, and Monthly Review as scheduled routines in your Claude account (definitions in `System/routines/`, status in `System/Routines.md`). They run in the cloud and push their results, so nothing on your computer has to be on. To create or repair one by hand, follow "Create a routine by hand" in `System/Routines.md`.

## License

[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/): you may share this with attribution, but you may not sell it or distribute modified versions. See [LICENSE](LICENSE) for details.
