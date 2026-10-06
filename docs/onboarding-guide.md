# Onboarding Guide: Setting Up Your Personal Assistant

This guide is a reference for what the setup process covers. **You do not need to follow these steps manually.** Instead, open your vault in [Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web) and type:

```
/onboard
```

Claude will interview you using a friendly question-and-answer format with selectable options (no typing required for most questions). It asks about your name, tools, schedule, and preferences, and builds everything for you in about 20 minutes.

This is the **cloud edition**: it runs in Claude Code on the web, in your browser. Your vault is a Git repository of Markdown files that Claude reads and writes directly in a cloud workspace. There is nothing to install on your own computer.

The setup has 4 parts:

| Step | Command | What It Does | Time |
|------|---------|-------------|------|
| 1 | `/onboard` | Learn about you, build your vault folders and files | ~20 min |
| 2 | `/train` | Walk through your vault, skills, and the daily loop | ~15 min |
| 3 | `/connect` | Connect each of your tools (calendar, email, tasks, etc.) one by one | ~20 min |
| 4 | `/finish` | Live demo with real data, improvement tips, how to maximize the system | ~10 min |

The steps below explain what each part sets up, so you can understand what each piece does or make changes later.

**What you will need:**
- A GitHub account (for your vault repository)
- A [Claude subscription](https://claude.ai) that includes Claude Code on the web

**What you are building:** A personal assistant that lives in your vault. It reads your calendar, processes your email, tracks your tasks, and builds tomorrow's plan while you sleep. By the end of all 4 steps, you will have a working daily system.

---

## Step 1: Open Your Vault in Claude Code on the Web

The setup runs in [Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web): open your vault repository in the browser, and Claude works on the files directly in a cloud workspace. There is no desktop app to install and no terminal to open.

Built-in integrations (like Gmail or Google Calendar) are connected through the **Customize** / connectors section of Claude Code on the web. Claude walks you through this during `/connect`.

## Step 2: Give Claude Permission to Help You

Before Claude can do anything, it needs permission to read and write files, run commands, and connect to your tools. In the cloud edition there is one file that matters: **your vault's `.claude/settings.json`**. It is committed to the vault repository, so every session -- today's and every future one -- starts with the same permissions automatically. (`/onboard` writes it for you; the reference below is for doing it by hand.)

**Important:** direct connections (MCP servers) are configured by you through the **Customize** / connectors section of Claude Code on the web -- Claude cannot set these up itself. Self-configured MCP servers go in the vault's `.mcp.json`. `.env` still works for API-based tools and scripts within a session.

### Vault Settings

This file lives at `.claude/settings.json` inside your vault. Because it travels with the repository, it is the durable copy of your permissions.

Copy and paste this into the file:

```json
{
  "permissions": {
    "allow": [
      "Read",
      "LS",
      "Glob",
      "Grep",
      "Edit",
      "Write",
      "NotebookEdit",
      "Bash(*)",
      "Read(/tmp/**)",
      "WebSearch",
      "WebFetch(*)",
      "mcp__context7__*"
    ],
    "additionalDirectories": [
      "/tmp"
    ]
  },
  "alwaysThinkingEnabled": true,
  "effortLevel": "high"
}
```

**What each permission means:**

| Permission | What it allows |
|---|---|
| `Read` | Claude can read files in your workspace |
| `LS` | Claude can list folders in your workspace |
| `Glob` | Claude can find files by name or pattern |
| `Grep` | Claude can search file contents in your workspace |
| `Edit` | Claude can make changes to existing files |
| `Write` | Claude can create new files |
| `NotebookEdit` | Claude can work with notebook files |
| `Bash(*)` | Claude can run terminal commands |
| `Read(/tmp/**)` | Claude can read temporary files |
| `WebSearch` | Claude can search the web for current information |
| `WebFetch(*)` | Claude can visit web pages to get information |
| `mcp__context7__*` | Claude can look up documentation |

**Adding more tools:** Each tool Claude connects to needs its own permission line. When you run `/connect`, Claude adds these automatically. The pattern is always `mcp__` followed by the tool name and `__*`. For example, if you connect ClickUp, Claude adds `"mcp__clickup__*"` to the allow list. If you connect Gmail or Google Calendar, Claude adds lines like `"mcp__claude_ai_Gmail__*"` and `"mcp__claude_ai_Google_Calendar__*"` to the allow list.

**Additional directories** are folders outside your vault that Claude can access.

### What about the other settings files?

Claude Code documentation also mentions `~/.claude/settings.json` (in the workspace home folder) and `.claude/settings.local.json` (untracked local settings). Both are **session-local in the cloud edition**: the workspace is recycled between sessions, so anything that lives only in them disappears. Keep your permissions in the vault's committed `.claude/settings.json` and you never have to think about it again.

---

### Guardrail hooks

`/onboard` installs four small hooks with `examples/settings.json` (merged into your vault's `.claude/settings.json`). They guarantee that Claude cannot open or print your credentials file or the environment (your scripts still use the logins through `scripts/envload.py` and `scripts/with-env.py`), that every tool call is logged with secrets masked, that a client profile keeps exactly one `## Current State` plus an append-only `## Log`, and that each session starts with the branch, uncommitted work, and latest handoff. To prove they are on, run the two commands in the README "Guardrails" section from the vault root: the first must exit 2 (blocked) and the second exit 0.

## Step 3: Create Your Notes Folder (Vault)

Your vault is a Git repository of plain Markdown files that Claude reads and writes directly in your cloud workspace. Plain text means your notes stay portable and readable for decades, and Git keeps a full history so nothing is ever lost.

The vault gets its **own private GitHub repository** (separate from this setup repo). The repository is what persists: each cloud session opens a fresh copy of it, and commands commit and push your changes back when they finish. `/onboard` walks you through creating the repo and pushes everything at the end of setup -- until that first push, the vault exists only in the temporary workspace.

### Create Your Starter Folders

Inside your vault, create these three folders:

```
Brain/
├── Inbox/       (where new items go)
├── Work/        (professional projects)
└── Resources/   (reference material)
```

You can create more folders later. These three are enough to start.

For a detailed guide on folder structure and how everything fits together, see the [Vault Design Guide](vault-design-guide.md).

---

## Step 4: Create Claude's Instruction Manual

The instruction manual (called `CLAUDE.md`) is the most important file in the system. Claude reads it every session to know how you want things done.

1. Copy the template from `templates/CLAUDE.md` in this repository
2. Paste it into a new file called `CLAUDE.md` at the root of your notes folder
3. Customize it:
   - Replace `[Your Name]` with your name
   - Replace `[Your Timezone]` with your timezone
   - Replace `[YourCompany]` with your company name (or remove those sections if not applicable)
   - Update the client list and priority tiers to match your situation
   - Adjust the daily schedule skeleton to match your routine

**You do not need to fill in everything right now.** Start with your name, timezone, and daily schedule. Add integrations and workflows as you connect tools.

The template includes sections for:
- **What Claude should do first** every session (startup checklist)
- **Where things go** in your notes folder (quick reference)
- **What tools are connected** (integrations)
- **How Claude should behave** (guidelines and preferences)
- **Common workflows** (step-by-step routines)

---

## Step 5: Connect Your Tools (`/connect`)

The `/connect` command walks you through connecting each tool one by one, testing each connection with real data before moving on.

**Recommended first connections:**
- **Google Calendar** -- Know what is coming tomorrow, create time blocks
- **Your task manager** (ClickUp, Asana, Todoist, etc.) -- Track and update tasks
- **Gmail** -- Surface emails needing responses

For Google services, `/connect` offers two paths:
- **Easy way:** Sign in through Claude.ai's settings page (2 minutes, no technical setup)
- **Full control way:** Use the `gws` CLI to set up Google access (recommended for custom Google Drive/Docs workflows). Cloud Console is the fallback if the CLI is unavailable.

Other built-in integrations are added through the **Customize** / connectors section of Claude Code on the web.

See [Integration Architecture](integration-architecture.md) for the full technical reference on how each tool connects, including credential types and API details.

---

## Step 6: Learn the System (`/train`)

The `/train` command gives you a guided tour of everything `/onboard` built: your folder structure, CLAUDE.md instruction manual, skills, and the daily loop. It takes about 15 minutes and is designed as a show-and-tell (not a lecture).

Key things you will learn:
- What each folder is for
- How CLAUDE.md works and how to edit it
- How skills work (they are just text files)
- The daily loop: EOD processing, morning review, day, repeat

---

## Step 7: Take It for a Spin (`/finish`)

The `/finish` command is the payoff. Claude pulls real data from your connected tools and shows you the system working:

- Tomorrow's calendar and schedule
- Emails needing attention
- Open tasks from your task manager
- Meeting prep for upcoming calls
- A generated plan for tomorrow (`Inbox/Today.md`)

It also covers:
- How to add rules when Claude makes a mistake
- How to turn successful tasks into skills
- The monthly review process
- Power tips specific to your setup

---

## What a Typical Day Looks Like

### The Night Before

If you ran `/eod` the day before, Claude has already processed your calls, emails, and messages and built today's plan in `Inbox/Today.md`.

If you did not run `/eod` yet, you can run it now, or start fresh and run it tonight.

### Morning (5 minutes)

1. Open your vault in Claude Code on the web and read `Inbox/Today.md`
2. Type `/morning`
3. Claude walks you through the plan and helps you adjust if needed
4. Confirm the plan. You are ready to start.

### During the Day

Use Claude whenever you need help:
- "Draft a reply to [Contact]'s email about the timeline"
- "What do I have with [Client] this week?"
- "Add a task to follow up with [Name] by Friday"
- "Summarize the notes from yesterday's call with [Client]"

### End of Day

Run `/eod` before wrapping up. Claude processes the day and generates tomorrow's plan while you walk away.

### Over Time

The system improves as you use it:
- When Claude makes a mistake, add a guideline to CLAUDE.md
- When you repeat a process manually, turn it into a skill
- When a tool connection would save time, add it
- Run `/monthly-review` once a month to clean up and improve

---

## Glossary

Plain-language definitions for terms you will see in the documentation.

| Term | What It Means |
|---|---|
| **Vault** | Your notes repository -- a Git repo of Markdown (text) files that Claude Code reads and writes in your cloud workspace. |
| **CLAUDE.md** | Claude's instruction manual. A text file at the root of your notes folder that Claude reads every session. |
| **Skill** | A successful task turned into a repeatable routine. A text file in `.claude/commands/` (or a folder in `.claude/skills/` when it carries scripts) that tells Claude how to run a multi-step process. You type `/name` to run it. Your skills library grows over time from your actual work. |
| **MCP server** | A direct connection between Claude and a tool (like ClickUp or Google Calendar). Once set up, Claude can use the tool without going through a browser. |
| **API** | A way for software to talk to other software. When Claude "calls an API," it is asking another service for information or telling it to do something. |
| **OAuth** | A secure login handshake. Instead of giving Claude your password, OAuth lets you approve access once and Claude gets a special key to use going forward. |
| **.env file** | Your password keychain scratch file. A text file that holds login information for the current session only -- it is never committed to the repository, and it does not survive between sessions. The permanent copies of your credentials are environment variables in your Claude Code environment settings. |
| **Manifest** | A tracking list. During long processes, Claude writes down every item it finds so nothing gets lost. |
| **EOD pipeline** | The end-of-day routine. A multi-step process that collects everything from your day and builds tomorrow's plan. |
| **Sub-agent** | A separate Claude session launched from within your current session. The `/eod` command uses sub-agents so each phase gets a fresh context window. You do not need to do anything special; it happens automatically when you run `/eod`. |
| **Context window** | Claude's working memory for a single conversation. Claude can hold a lot of information at once, but very long sessions may compress older details. That is why important things get written to files. |
