# Claude Code Personal Assistant System

An AI-powered personal assistant built on [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and a Git-backed Markdown vault. The vault is the operating system; Claude Code is the brain. Together they handle task management, meeting processing, email triage, time tracking, client work, and daily planning -- replacing a human executive assistant.

This is the **cloud edition**: it runs in [Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web), in your browser. Your vault is a Git repository of Markdown files that Claude reads and writes directly in a cloud workspace -- nothing to install on your own computer.

> **You do not need to be technical.** Claude will walk you through everything step by step.
>
> **What you will need:** A GitHub account (for your vault repository) and a [Claude subscription](https://claude.ai) that includes Claude Code on the web.

## Get Started

1. Create (or pick) a GitHub repository to hold your vault, and open it in [Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web).
2. Add this setup repo's files to that workspace if they are not already there.
3. Type `/onboard` to begin.

**Already have a vault repository?** Drop this setup repo's files into it, then say:

> Set me up

Claude will find the setup files, copy the commands into place, and start the process automatically.

Either way, Claude interviews you in a friendly question-and-answer format (no manual file editing). The full setup has 4 parts:

| Step | Command | What It Does | Time |
|------|---------|-------------|------|
| 1 | `/onboard` | Learn about you, build your vault folders and files | ~20 min |
| 2 | `/train` | Walk through your vault, skills, and the daily loop | ~15 min |
| 3 | `/connect` | Connect each of your tools (calendar, email, tasks, etc.) one by one | ~20 min |
| 4 | `/finish` | Live demo with real data, improvement tips, how to maximize the system | ~10 min |

Each part ends by telling you what to type next. You can pause between parts and pick up later.

> For a detailed reference of what gets set up, see the [Onboarding Guide](docs/onboarding-guide.md).

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         You (Morning Review)                      │
│                    Read Today.md → /morning → Day starts          │
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

**The daily loop:**
1. **End of day** -- Run `/eod` before wrapping up. Claude processes your calls, emails, Slack, and tasks, then builds tomorrow's plan. You can walk away while it runs.
2. **Morning** -- Read `Inbox/Today.md` (pre-built schedule, priorities, meeting prep)
3. **Morning** -- Run `/morning` (3-5 min interactive review: confirm plan, adjust, create calendar blocks)
4. **All day** -- Work with Claude Code as needed (drafting, research, task management, document creation)
5. **End of day** -- Cycle repeats

## What the Setup Creates

By the end of all 4 steps, you will have (see the [Onboarding Guide](docs/onboarding-guide.md) for details):

- **Permissions** configured so Claude can work without interrupting you
- **Notes folder** (a Git-backed Markdown vault) with organized folders for clients, projects, and tasks
- **Instruction manual** (CLAUDE.md) customized with your name, schedule, clients, and preferences
- **Tool connections** to your calendar, email, task manager, and other services
- **Skills** for morning review, end-of-day processing, and other workflows
- **Understanding** of how the system works and how to improve it over time

## Repository Structure

```
ClaudeCodeSystem/
├── CLAUDE.md                           # Bootstrap file (tells Claude how to start setup)
├── README.md                           # This file
├── .claude/commands/                   # ALL Claude Code slash commands (auto-discovered; every one installs during /onboard)
│   ├── onboard.md                      # Part 1: Permissions, interview, build vault
│   ├── train.md                        # Part 2: Learn the system
│   ├── connect.md                      # Part 3: Connect all your tools
│   ├── finish.md                       # Part 4: Live demo, improvement tips
│   ├── handoff.md                      # Save current work state to a named briefing file
│   ├── pickup.md                       # Resume from a named handoff in a fresh session
│   ├── strategy.md / optimize.md       # Decision-making + tool/process improvement
│   ├── build-skill.md / learn.md       # Turn tasks into skills · capture knowledge
│   ├── graph-sync.md / graph-daily.md  # Knowledge graph maintenance
│   ├── morning.md                      # Interactive morning review command
│   ├── eod.md                          # End of day: monolithic (all phases in one)
│   ├── eod-gather.md                   # EOD Phase 1: data gathering
│   ├── eod-sync.md                     # EOD Phase 2: dedup, sync, hygiene
│   ├── eod-time.md                     # EOD Phase 3: time tracking (if configured)
│   ├── eod-note.md                     # EOD Phase 4: daily note generation
│   ├── eod-today.md                    # EOD Phase 5: tomorrow's plan generation
│   ├── monthly-review.md               # Monthly system review
│   ├── brain-dump.md                   # Manual brain dump capture
│   └── daily-note.md                   # Simplified daily note (lightweight EOD)
├── .claude/skills/                     # Skills with scripts/references (folder per skill; every one installs during /onboard)
│   └── drive-screen/                   # Take control of the desktop (Windows/macOS/Linux) when a step must be clicked through
├── cowork-commands/                    # CoWork versions (YAML frontmatter, manual upload)
│   └── *.md                            # Mirror of all commands with YAML frontmatter
├── docs/
│   ├── onboarding-guide.md             # Reference for what /onboard sets up
│   ├── vault-design-guide.md           # How to build the vault (folder structure, inbox, templates)
│   ├── integration-architecture.md     # How Claude connects to your tools
│   └── daily-workflow.md               # Today.md + /morning + EOD pipeline
├── templates/
│   ├── CLAUDE.md                       # Starting CLAUDE.md template (customized by /onboard)
│   └── .env.example                    # All env var names with descriptions
├── examples/                           # Example settings + optional scripts (NOT commands)
│   ├── settings.json                   # Example: baseline vault permissions (installed as the vault's .claude/settings.json)
│   └── scripts/
│       └── md-to-gdoc.py               # Markdown to Google Doc converter
├── .gitignore
└── LICENSE                             # CC BY-NC-ND 4.0
```

## Documentation

| Document | What It Covers |
|----------|---------------|
| [Onboarding Guide](docs/onboarding-guide.md) | Step-by-step setup for new users: permissions, vault structure, CLAUDE.md, first tool connection, workflow discovery |
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
- **Claude CoWork:** Skills require YAML frontmatter (`name:` and `description:` fields in a `---` block) and must be manually uploaded through the **Customize** section in the app settings. The `cowork-commands/` directory contains pre-formatted versions of all skills ready for upload.

### Session Continuity (`/handoff` and `/pickup`)
Every user gets these two commands. They solve the single biggest limitation of working with an AI agent: a session's memory is finite. When the context window fills up, or you run `/clear`, close the window, or the conversation gets compacted, everything that was only "in the chat" is gone.

- **`/handoff <name>`** writes a self-contained briefing to `.handoffs/<name>.md` -- the goal, what's been done, what was tried and rejected, the exact next steps, and which files and commands the next session should reload -- then **commits and pushes it** (cloud sessions start from a fresh clone, so an unpushed handoff would never reach the next one). Run it before `/clear`, before ending a session mid-task, or whenever a long conversation is getting unwieldy. The handoff is written *to the next Claude*, not to you, so it reads like a briefing for a colleague who just walked in.
- **`/pickup [name]`** (in the next session) reads that file, reloads the listed context in parallel, sanity-checks it against the current state of the repo, and reports back where you left off, all without you re-explaining anything. With no argument it lists the available handoffs and asks which to resume.

Because each handoff is a named, persistent file inside the vault, they accumulate into a **track record of in-flight workstreams**: you can keep several open across different projects, and old ones stay put until you delete them. This is better task and context management than holding everything in one long chat. Use it for mid-stream work; `/eod` still handles end-of-day wrap-up and routing items to your task inboxes.

> Named `/pickup` (not `/resume`) so it doesn't shadow Claude Code's built-in `/resume` session picker.

### Tracking Lists (The Manifest Pattern)
Long-running workflows track every extracted item in a tracking list (`/tmp/eod-manifest-TODAY.md`). Each item gets: description, client, type, source, destination, status. This makes sure nothing gets lost during long processes.

### File Writes
Your vault is a Git repository in a cloud workspace -- there is no background file sync racing against Claude's edits, so the built-in editor is safe for reads and writes. Git history is your safety net: commit and push to persist changes and roll back if needed.

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
The default `/eod` flow should run as one command in one Claude session. Claude Code now supports long-context sessions, so the simplest setup is a single `/eod` that gathers, routes, syncs, writes the daily note, and builds tomorrow's plan. If a user's workflow is unusually heavy, or if they want unattended scheduled automation, you can still split EOD into separate phases as an advanced fallback.

## Guardrails

Four hooks in `templates/scripts/hooks/` (installed into your vault's `.claude/settings.json` from `examples/settings.json`) keep the assistant honest: `guard_secrets.py` blocks any attempt to read, print, or search the credentials file or the environment; `log_tool_use.py` writes one masked line per tool call to `_generated/agent-actions/`; `guard_state_writes.py` keeps client profiles to one `## Current State` plus an append-only `## Log`; and `session_context.py` starts each session with the branch, uncommitted work, and the newest handoff. Scripts load credentials themselves through `scripts/envload.py`, and a one-off call goes through `python3 scripts/with-env.py -- <command>`.

Two proof commands, run from the vault root (expect `exit=2`, then `exit=0`):

```bash
echo '{"tool_name":"Read","tool_input":{"file_path":".env"}}' | python3 scripts/hooks/guard_secrets.py; echo "exit=$?"
echo '{"tool_name":"Read","tool_input":{"file_path":"README.md"}}' | python3 scripts/hooks/guard_secrets.py; echo "exit=$?"
```

## Install the System Journal (optional)

The System Journal turns every Claude Code session into a durable, checkable record so a later
review can spot what keeps coming back. It ships in `templates/scripts/system-journal/` (full
reference: that folder's `README.md`). This template ships **capture** only: there is no weekly
reflection command and no Themes writer yet.

In the cloud edition, capture happens through **repo-level hooks** that ship with your vault to
every container:

1. **Wire the hooks.** The hook block is already in `examples/settings.json`, which `/onboard`
   installs as your vault's committed `.claude/settings.json` (a standalone copy is in
   `examples/cloud-hooks.settings.json` if you need to merge it into an existing file by hand).
   The hooks run `scripts/cloud-land.sh` (lands the session's file edits on `main` without the
   agent running git) and `scripts/system-journal/cloud-journal.sh` (writes the evidence record
   and distills one journal line).
2. **Why hooks, not a command.** Hooks bypass the permission classifier, so an unattended cloud
   run never stalls on a prompt. A container keeps its transcript only while it lives, so capture
   has to happen while alive: the `Stop` hook extracts every ~60 s and distills at most every 15
   minutes; `SessionEnd --final` does a last pass.
3. **Push access.** The cloud environment needs push access to your vault's `origin` (main); the
   hooks fast-forward their file onto `main` from a throwaway worktree, never your working branch.
4. **Per-session cost.** The journal line is produced by your own `claude -p` call with the
   default Sonnet distiller: about **nine cents per finished session**. Set `SYSTEM_JOURNAL_MODEL`
   to change the model.
5. **What is kept.** Your words verbatim, the agent's visible words capped, the tool calls it
   made and the errors that came back. **No tool outputs**, no thinking, no attachments. Full
   transcripts are never stored (and a torn-down container keeps none).
6. **Where the files land.** `_generated/system-journal/` in your vault repo: `evidence/<YYYY-MM>/`
   (deterministic, kept forever) and `cloud/<date>.<sid8>.json` (one journal line per session).
7. **Cost guard and privacy.** Before any bulk re-run, read the pending count first
   (`python3 scripts/system-journal/distill.py --dry-run | tail -1`). Everything stays in your own
   vault repo; the audit tier (a work-only projection with personal lines dropped) is **generated
   locally only and shipped nowhere**.

**Also run your vault locally?** Then also install the Mac-side hooks so local sessions are
captured too: `bash scripts/system-journal/install.sh --vault "$VAULT" --write-hooks` (it merges
three hooks into your user-level `~/.claude/settings.json`). See the system-journal README.

**Knowledge graph.** `scripts/graph-render.py` renders `Graph/index.md` and the MOCs from
frontmatter and, when present, the concept index (`_generated/vault-hygiene/vault-index.json`, written by `/vault-audit`); `/graph-daily` and `/graph-sync` drive it. Graph files are
generated, not hand-edited, and links are structural edges only (no inline wiki-link pass).

## FAQ

**Do I need all these tool connections?**
No. Start with Calendar + Email + your meeting transcript service. Add connections as you need them.

**Do I need to install anything?**
No. This is the cloud edition -- it runs in Claude Code on the web, in your browser. There is nothing to install on your own computer; you only need a GitHub account for your vault repository. It works from any Mac, Windows, or Linux machine with a browser.

**How much does this cost?**
Claude Code on the web requires a [Claude subscription](https://claude.ai). Connections to Google, Slack, and similar services are within their free tiers for personal use. Some tools (like meeting transcript services or time trackers) have their own pricing.

**Can I use this for a team?**
The system is designed for one person. You could adapt it for a small team, but it would need significant customization.

**What if the EOD routine fails partway through?**
If you are using the default one-command `/eod`, just run it again after fixing the issue. If you later adopt the advanced phased version, you can re-run only the failed phase.

**Can I automate the EOD to run on a schedule?**
Yes. Create a scheduled [Routine](https://code.claude.com/docs/en/routines) in Claude Code on the web: point it at your vault repository with the prompt `/eod` and a schedule like 11:30 PM on weekdays. It runs in the cloud and pushes the results, so tomorrow's plan is ready when you sit down -- no computer left on, no cron jobs, no terminal setup. Most users still just run `/eod` manually before wrapping up for the day.

## License

[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) — you may share this with attribution, but you may not sell it or distribute modified versions. See [LICENSE](LICENSE) for details.
