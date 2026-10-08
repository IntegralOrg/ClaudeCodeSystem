# Integration Architecture: How the Brain System Connects Everything

> **You do not need to understand every detail in this document.** Claude can walk you through setting up any connection. This is a reference for when you want to know how things work under the hood.

This document explains the technical architecture behind the Brain personal assistant system. It covers how a `.env` file, MCP servers, REST/GraphQL API calls, custom scripts, and skills work together to turn a Git-backed Markdown vault into an automated operations hub.

---

## The Five Integration Layers

The system connects to external platforms through five layers, each serving a different purpose:

```
┌─────────────────────────────────────────────────┐
│                  Claude Code (AI Agent)          │
│          Reads CLAUDE.md for instructions        │
│          Reads .env for credentials              │
│          Executes skills                           │
├─────────────────────────────────────────────────┤
│                                                   │
│  Layer 1: .env File                              │
│  Where your login information is stored          │
│  → Passwords, keys, and tokens in one place     │
│                                                   │
│  Layer 2: Direct Connections (MCP Servers)       │
│  Tools Claude can use directly, like built-in    │
│  apps                                            │
│  Task Manager, Google Calendar, etc.              │
│  → No extra steps needed, they just work         │
│                                                   │
│  Layer 3: Tool Connections (REST/GraphQL APIs)   │
│  Tools Claude accesses using your saved          │
│  passwords                                       │
│  Gmail, Slack, Google Drive, Transcripts          │
│  → Claude runs commands using credentials        │
│    from .env                                     │
│                                                   │
│  Layer 4: Custom Scripts (Python/Bash helpers)   │
│  Multi-step recipes for complicated operations   │
│  fathom-fetch.py, classify-transcript.py, etc.   │
│  → Reusable scripts that handle complex tasks    │
│                                                   │
│  Layer 5: Scheduled Automation (Routines)        │
│  Runs things automatically on a schedule         │
│  Cloud sessions triggered on a cadence (/eod)    │
│  → Unattended scheduled routines (advanced)       │
│                                                   │
├─────────────────────────────────────────────────┤
│              Git-backed Vault (Markdown)          │
│         (markdown files in a Git repo)           │
│        Source of truth for all task state         │
└─────────────────────────────────────────────────┘
```

---

## Layer 1: The .env File (Credential Management)

Every API key, OAuth token, and secret lives in a single `.env` file at the vault root. This file is:

- **Gitignored** (never committed to the repository)
- **Workspace-only** (it lives in your cloud workspace and is never pushed to the repo)
- **The single source of truth** for credentials

### What's in the .env

```bash
# Google OAuth (used for Gmail, Calendar, Drive, Docs)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...

# Fathom (meeting transcripts)
FATHOM_API_KEY=...

# Slack (one token per workspace)
SLACK_TOKEN_WORKSPACE_A=xoxp-...
SLACK_TOKEN_WORKSPACE_B=xoxp-...
SLACK_TOKEN_WORKSPACE_C=xoxp-...

# Rize (time tracking)
RIZE_API_KEY=...

# Add more services as needed:
# SERVICE_API_KEY=...
```

See `.env.example` for a full list of supported variables with descriptions.

### How the AI Uses It

At the start of any workflow that needs API access, the AI runs:

```bash
source "/path/to/vault/.env"
```

This loads all credentials as environment variables. Then API calls reference them:

```bash
curl -s -H "X-Api-Key: ${FATHOM_API_KEY}" \
  "https://api.fathom.ai/external/v1/meetings?include_transcript=true"
```

### Why Not Use a Secrets Manager?

Simplicity. The AI agent reads credentials straight from the `.env` file in your cloud workspace. A `.env` file is the simplest thing that works. No network calls to a vault service, no token rotation complexity, no extra dependencies. The security model is: the `.env` stays in your workspace and is never committed to the repo, so the secrets never leave with your Markdown files.

### Reference Pointers in the Vault

The vault has a `Resources/API Keys/` folder with markdown files that document which credentials exist and where they're stored, but contain zero actual secrets. Example content:

```markdown
# Fathom API Key
- **Stored in**: `.env` as `FATHOM_API_KEY`
- **Type**: API key (X-Api-Key header)
- **Scopes**: Read meetings, transcripts, summaries
- **Rate limit**: 60 calls/min
```

This lets you browse your integrations in the vault without exposing secrets.

---

## Layer 2: Direct Connections (MCP Servers)

Some tools have a direct connection built for Claude. Think of them as built-in apps -- Claude can use them directly without going through a browser or typing passwords. Technically these are called "MCP servers" (Model Context Protocol), but all you need to know is that once they are set up, they just work. Instead of writing commands, Claude calls tools as native functions (e.g., `clickup_create_task` or `gcal_list_events`).

### How MCP Servers Work

MCP-style direct connections are configured outside the vault, in Claude Code on the web. You add them through the app's **Customize** section in settings. **Only the user can add these** -- Claude cannot configure its own MCP connections. If a new integration is needed, tell the user what to connect and where to find it in the **Customize** section.

Each direct connection:
1. Connects to an external service (your task manager, Google Calendar, etc.)
2. Exposes a set of tools (functions) the AI can call directly
3. Handles authentication internally (credentials configured once during setup)

### When to Use MCP vs. REST API

| Use MCP When | Use REST API When |
|---|---|
| A server exists for the service | No MCP server available |
| You need structured tool calls (create task, run SQL) | You need raw API flexibility |
| The operation is common and well-supported | The operation is niche or custom |
| You want the AI to have typed parameters and validation | You need full control over headers, pagination, etc. |

### Example: Task Manager (ClickUp via MCP)

This example uses ClickUp. The same pattern applies to any task manager with an MCP server. The AI can call tools directly:

```
clickup_create_task(
  list_id: "901323564130",
  name: "Fix login page timeout",
  description: "Users report 504 errors after 30 seconds",
  status: "to do",
  priority: 2
)
```

No curl, no auth headers, no JSON parsing. The MCP server handles all of that.

---

## Layer 3: REST/GraphQL APIs (Via Shell Commands)

For services without MCP servers, the AI makes direct API calls using curl in the shell. This is more manual but gives full flexibility.

### OAuth2 Refresh Token Flow (Google Services)

Google services (Gmail, Calendar, Drive, Docs) use OAuth2. The `.env` stores a long-lived refresh token. The AI exchanges it for a short-lived access token at runtime:

```bash
source ".env"

# Get a fresh access token
ACCESS_TOKEN=$(curl -s -X POST "https://oauth2.googleapis.com/token" \
  --data "grant_type=refresh_token&client_id=${GOOGLE_CLIENT_ID}&client_secret=${GOOGLE_CLIENT_SECRET}&refresh_token=${GOOGLE_REFRESH_TOKEN}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Use it immediately
curl -s "https://gmail.googleapis.com/gmail/v1/users/me/messages?q=newer_than:1d" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

**Key gotcha**: Each shell command runs in an isolated session. Environment variables don't persist between commands. Either chain commands with `&&` or extract the token value and pass it explicitly.

### API Key Auth (Example: Fathom)

Simpler services use static API keys passed in headers:

```bash
source ".env"

# Fathom: list today's meetings
curl -s -H "X-Api-Key: ${FATHOM_API_KEY}" \
  "https://api.fathom.ai/external/v1/meetings?created_after=2026-03-06T00:00:00Z&include_transcript=true"
```

### Per-Workspace Tokens (Slack)

Slack requires a separate OAuth token for each workspace. The `.env` stores one per workspace:

```bash
# Check DMs in Workspace A
curl -s "https://slack.com/api/conversations.list?types=im" \
  -H "Authorization: Bearer ${SLACK_TOKEN_WORKSPACE_A}"

# Post to a channel in Workspace B
curl -s -X POST "https://slack.com/api/chat.postMessage" \
  -H "Authorization: Bearer ${SLACK_TOKEN_WORKSPACE_B}" \
  -H "Content-Type: application/json" \
  -d '{"channel":"C0AGY6548HH","text":"Hello from the AI"}'
```

### GraphQL (Example: Rize Time Tracking)

```bash
curl -s -X POST "https://api.rize.io/api/v1/graphql" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${RIZE_API_KEY}" \
  -d '{"query": "{ sessions(startTime: \"2026-03-06T05:00:00Z\", endTime: \"2026-03-07T05:00:00Z\") { id title startTime endTime type } }"}'
```

---

## Layer 4: Custom Scripts (Complex Operations)

When an operation is too complex for a single curl command, or needs to be reusable, it lives in a `scripts/` folder as a Python or Bash script.

### Why Scripts?

- **State management**: Some operations need to track what's already been processed (e.g., which Slack messages have been ingested)
- **Multi-step logic**: Pagination, deduplication, conditional branching
- **Reusability**: The AI calls the same script from different skills
- **Testability**: Scripts can be tested independently

### Script Catalog

| Script | Language | Purpose |
|--------|----------|---------|
| `fathom-fetch.py` | Python | Deterministic Fathom transcript download. Downloads today's calls, classifies per-client routing, returns JSON report. |
| `classify-transcript.py` | Python | Routes transcript files to the correct client folder based on participant names and call title. |
| `rize-triage.sh` | Bash | Fetches Rize time tracking sessions, detects gaps, generates classification input. |
| `rize-classify.py` | Python | Two-axis classification: client (who) + work_type (delivery/sales/audit/meeting/admin/internal). |
| `md-to-gdoc.py` | Python | Converts markdown to styled HTML and uploads to Google Drive as a Google Doc. Preferred method for formatted docs. |

### Transcript Routing Architecture

Call transcripts are auto-routed to the correct folder by `classify-transcript.py`:

```
Fathom API
    |
    v
fathom-fetch.py (downloads transcript)
    |
    v
classify-transcript.py (determines client from participants + title)
    |
    ├── Client contact detected ──> Work/Clients/<Client>/Transcripts/
    ├── Dev team only ────────────> Work/Transcripts/
    └── Partner/private ──────────> [YourCompany]/Transcripts/
```

The classifier uses a contact-to-client mapping (configured in the script) and falls back to title-based heuristics for edge cases. The AI can override classifications when the script gets it wrong.

### Time Tracking Architecture (Example: Rize)

If you use a time tracking tool, the system can classify sessions automatically. This example uses Rize, but the pattern works with any time tracker that has an API. Time tracking uses a two-axis classification system:

- **Axis 1: Client** -- Who is the time for? (Client A, Client B, internal, etc.)
- **Axis 2: Work Type** -- What kind of work? (delivery, sales, audit, meeting, admin, internal)

```
Rize API (sessions)
    |
    v
rize-triage.sh (fetch + gap detection)
    |
    v
rize-classify.py (two-axis classification)
    |
    v
EOD Phase 3: review + relabel via Rize API
```

The classifier uses app patterns (which apps map to which clients), calendar cross-referencing, and transcript matching to determine both axes. Sessions during detected gaps are reconstructed from per-hour app usage data.

### Scheduled Automation (Routines)

To run a workflow on a schedule without keeping anything on, use a **scheduled Routine** in [Claude Code on the web](https://code.claude.com/docs/en/routines): a saved configuration (prompt + repository + connectors) that runs on Anthropic's cloud infrastructure on a recurring cadence.

For the nightly EOD:

1. Create a routine pointed at your vault repository with the prompt `/eod`
2. Schedule it (e.g., weekdays at 11:30 PM in your timezone)
3. Each run starts a fresh cloud session, executes the pipeline, and pushes the results -- tomorrow's plan is ready when you sit down

Considerations for unattended runs:

- **Persistence**: The run must end with a successful `git push` (the `/eod` command's final step) or its output is lost with the workspace
- **Connectors**: The routine only has access to the connectors attached to it -- attach the same integrations your interactive sessions use
- **Overlap**: Leave enough gap between scheduled runs that they cannot overlap
- **Failure alerts**: Have the routine message you (e.g., Slack DM) when a step fails, so silent failures do not go unnoticed

Most users run `/eod` manually instead; the routine is for making it automatic.

**Local scheduled tasks (Claude Desktop app) are per-machine; back them up.** The Desktop app's Routines page can also run a task locally (kind Local), which is the right choice when the task needs your files or a local tool. A local task lives only on that computer: its prompt is at `~/.claude/scheduled-tasks/<name>/SKILL.md`, and its schedule, folder, model, permission mode, and always-allow approvals sit in the app's private state, which nothing exports; it does not appear in your account's cloud routine list. After creating, editing, pausing, or deleting one, run `bash scripts/local-routines-backup.sh` in the vault and update the task's row in `Resources/Reference/Local Routines Registry.md`. A replacement computer is then rebuilt from the vault, not from memory.

---

## Skills: Orchestrating Everything

Skills are the glue. They are markdown files in `.claude/commands/` that define multi-step workflows. When you type `/skill-name`, the AI reads the markdown file and executes each step.

### Anatomy of a Skill

Each skill file is essentially a detailed prompt with:

1. **Setup**: Load credentials, verify date, check preconditions
2. **Data gathering**: Pull from APIs, read vault files, query databases
3. **Processing**: Classify, extract, transform, score
4. **Routing**: Write results to the right vault files
5. **Sync**: Push state to external systems (task manager, database, Slack)
6. **Summary**: Report what was done

### Skill Catalog

#### EOD Phase 1: `/eod-gather` (Data Gathering)

The daily workhorse. Touches nearly every integration:

| Section | Integration | What It Does |
|---|---|---|
| 0. Brain Dump Triage | Vault files | Classify and route brain dump items to client files |
| 1. Call Transcripts | Fathom API + classify-transcript.py | Pull today's meetings, save transcripts, classify per-client, extract action items |
| 2. Tomorrow's Calendar | Google Calendar API | Fetch tomorrow's schedule, flag early meetings |
| 3. Email Check | Gmail API | Surface emails needing responses, cross-reference with tasks |
| 4. Slack Check | Slack API (all workspaces) | Surface unread DMs and mentions across all workspaces |

**Key pattern: Route-as-you-go.** Every section routes its extracted items to client files immediately, rather than batching them for later. This prevents items from being lost if the session runs long and context gets compressed.

**Key pattern: Manifest tracking.** A manifest file (`/tmp/eod-manifest-TODAY.md`) tracks every extracted item with its source, type, destination, and status. This serves as an audit trail and prevents items from falling through the cracks.

#### EOD Phase 2: `/eod-sync` (Verify + Sync)

| Step | Integration | What It Does |
|---|---|---|
| Deduplication | Vault files | Remove duplicate tasks across client files |
| Completed cleanup | Vault files | Move checked items to Completed sections |
| Task sync | Task Manager MCP | Create new tasks, update statuses |
| Vault hygiene | Vault files | Flag stale items, Monday weekly archiving |

#### EOD Phase 3: `/eod-time` (Time Tracking, if configured)

| Step | Integration | What It Does |
|---|---|---|
| Fetch sessions | Rize GraphQL API | Pull today's time tracking data |
| Gap detection | Rize API + calendar | Find untracked periods, reconstruct from app data |
| Classification | rize-classify.py | Two-axis: client + work type |
| Relabeling | Rize API mutations | Apply correct labels via API |

#### EOD Phase 4: `/eod-note` (Daily Note)

| Step | Integration | What It Does |
|---|---|---|
| Generate summary | Vault files + manifest | Create `Work/Daily/YYYY-MM-DD.md` with full day summary |

#### EOD Phase 5: `/eod-today` (Tomorrow's Plan)

| Step | Integration | What It Does |
|---|---|---|
| Calendar fetch | Google Calendar API (or cached from Phase 1) | Tomorrow's schedule |
| Priority ranking | Vault files (inbox + manifest) | Select top 5-7 tasks by tier and deadline |
| Meeting prep | Vault files (transcripts + profiles) | Context for each meeting |
| Carry forward | Today's Today.md | Detect unchecked tasks, increment carry count |
| Team priorities | Vault files + task manager | Generate delegation message |
| Write Today.md | Vault write | Overwrite `Inbox/Today.md` |

#### `/morning` (Morning Review)

Interactive command with `AskUserQuestion` at every decision point:

| Step | Integration | What It Does |
|---|---|---|
| Load + stale check | Vault read | Read Today.md, verify date matches |
| Summary | Vault read | Present 8-10 line overview |
| Client review | AskUserQuestion | Batch review with adjustment options |
| Goal check | Vault read + AskUserQuestion | Detect stale goals, prompt for refresh |
| Time blocks | Google Calendar MCP | Create deep work blocks |
| Send-off | Text output | Confirm plan, announce first priority |

#### `/monthly-review` (Monthly Review)

| Step | Integration | What It Does |
|---|---|---|
| System feedback | AskUserQuestion | Collect improvement ideas |
| Vault cleanup | Vault scan | Surface stuck, stale, or misplaced items |
| Testimonial scan | Slack API + vault search | Find positive client feedback |
| Apply updates | Vault writes | Route improvements to appropriate files |

#### Other Skills

| Command | What It Does |
|---|---|
| `/debrief [Name]` | Post-interview candidate assessment against criteria |
| `/audit-research [Client]` | Pull assessment data, generate research doc |
| `/audit-roadmap [Client]` | Transform research into client-facing roadmap |
| `/audit-review [Client]` | 11-point QC gate with auto-fix offer |
| `/audit-deliver [Client]` | Populate portal, create projects/milestones, draft email |

---

## How It All Connects: Data Flow

Here's how data flows through a typical end-of-day:

```
Fathom API ─────► fathom-fetch.py ──► classify-transcript.py ──► Client Transcripts/
                                                                        │
                  Transcript text ──► Action item extraction ──────────┐
                                                                       │
Gmail API ──────► Important emails ──► Email tasks ───────────────────┤
                                                                       │
Slack API ──────► Unread messages ───► Slack tasks ───────────────────┤
(N workspaces)                                                         │
                                                                       ├──► Client files in Inbox/
Time Tracker ───► Time sessions ─────► classification ─────────────────┤    (if configured)
                                       (client + work type)            │
                                                                       │
Google Calendar ► Tomorrow's events ─► Schedule ──────────────────────┤
                                                                       │
Brain Dump ─────► Classify + route ──► Client tasks ──────────────────┘
                                          │
                                     Manifest (audit trail)
                                          │
                                          ▼
                                    Task Manager Sync
                                    (new tasks → task manager)
                                    (done tasks → update status)
                                          │
                                          ▼
                                    Daily Summary Note
                                    (Work/Daily/YYYY-MM-DD.md)
                                          │
                                          ▼
                                    Today.md
                                    (Inbox/Today.md -- tomorrow's plan)
```

---

## Setting This Up From Scratch

### Step 1: Create the .env File

Start with whichever integrations matter most to you:

```bash
# Minimum viable setup: calendar + email + meeting transcripts
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REFRESH_TOKEN=your_refresh_token
FATHOM_API_KEY=your_fathom_key
```

There are two ways to connect Google services. Choose whichever works for you:

- **Easy way (recommended): Claude.ai managed connections.** You sign in to Google through Claude.ai's Settings > Connectors page. No Cloud Console project needed. Claude gets direct access to Gmail and Google Calendar as built-in tools. Add `"mcp__claude_ai_Gmail__*"` and `"mcp__claude_ai_Google_Calendar__*"` to `permissions.allow` in your vault's `.claude/settings.json` so the tools are pre-approved in every session.

- **Full-control way (recommended): `gws` CLI.** Use the `gws` CLI to create or reuse Google access for the system. It is the preferred custom path because it is faster and less error-prone than clicking through Cloud Console. If `gws` is unavailable, use the Cloud Console walkthrough below.

### `gws` CLI First, Cloud Console Fallback

If you are using the easy way (Claude.ai managed connections), skip this entire section.

Preferred path: use the `gws` CLI if it is available in the workspace. Cloud Console is the fallback path when the CLI is unavailable or fails.

This fallback walkthrough assumes you have never used Google Cloud Console and have no existing project. If you run `/onboard`, Claude will walk you through these same steps interactively.

#### Check: Can You Access Cloud Console?

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Sign in with the Google account you want to connect

**If you see a dashboard:** You have access. Continue below.

**If you see "This service is not available" or a blocked page:** Your organization's IT team has restricted access. Your options:
- **Ask IT:** Request access to Google Cloud Console. Tell them: "I need to create OAuth credentials for a personal productivity tool that reads my calendar and email. I need access to create a project, enable APIs, and generate OAuth client credentials."
- **Use a personal Gmail:** Set up with your personal account instead. You can still access your work calendar if it is shared with your personal account.
- **Use the easy way instead:** Connect through Claude.ai's managed integrations (no Cloud Console needed).
- **Skip Google for now:** Use other tools first and come back later.

#### 1. Create a Project

1. At the top of the Cloud Console page, click the **project selector dropdown** (it might say "Select a project" or show an existing project name)
2. In the popup, click **New Project** (top-right corner)
3. For **Project name**, type **Claude Assistant** (or whatever you like -- this is just a label)
4. Leave **Location** as "No organization" (or select your organization if one appears)
5. Click **Create**
6. Wait a few seconds for the notification, then click **Select Project** in the notification, or use the project dropdown to select your new project

You should now see "Claude Assistant" (or your name) in the top-left dropdown.

#### 2. Enable APIs

You need to turn on each Google service Claude will use. Think of this like flipping switches.

For each API below:
1. Click the **search bar** at the top of the page
2. Type the API name and press Enter
3. Click on the API in the results
4. Click the blue **Enable** button

Enable these APIs:
- **Google Calendar API** (required for calendar access)
- **Gmail API** (required for email access)
- **Google Drive API** (optional -- only if you want document management)

#### 3. Set Up the OAuth Consent Screen

This tells Google what "app" is requesting access. You are just filling in a few fields.

1. In the left sidebar, click **APIs & Services**, then **OAuth consent screen**
   - If you cannot find the sidebar, click the hamburger menu (three horizontal lines) in the top-left corner
2. Choose a user type:
   - **Internal** (if available and you are using a Google Workspace/company account) -- simpler, recommended
   - **External** (if using a personal Gmail or Internal is not available) -- works fine, one extra step later
3. Click **Create**

Fill in the form:
- **App name:** Claude Assistant
- **User support email:** Select your email from the dropdown
- **Developer contact information** (at the bottom): Enter your email again
- Skip the logo and app domain fields -- leave them blank
- Click **Save and Continue**

On the **Scopes** page:
1. Click **Add or Remove Scopes**
2. Search for and check these scopes:
   - `https://www.googleapis.com/auth/calendar` (full calendar access)
   - `https://www.googleapis.com/auth/gmail.modify` (read and send email)
   - `https://www.googleapis.com/auth/drive` (only if you enabled Drive API)
3. Click **Update**, then **Save and Continue**

On the **Test Users** page (only appears for External user type):
1. Click **Add Users**
2. Enter your own email address
3. Click **Add**, then **Save and Continue**

On the **Summary** page, click **Back to Dashboard**.

#### 4. Create OAuth Credentials

1. In the left sidebar, go to **APIs & Services** > **Credentials**
2. Click **+ Create Credentials** at the top
3. Choose **OAuth client ID**
4. For **Application type**, choose **Desktop app** (not Web application)
5. For **Name**, type **Claude Assistant**
6. Click **Create**

A popup appears showing your **Client ID** and **Client Secret**. Copy both values and save them somewhere safe. You can also click **Download JSON** to save them as a file.

#### 5. Get a Refresh Token

This is a one-time sign-in so Google gives Claude a long-lasting key to access your account.

1. Open [developers.google.com/oauthplayground](https://developers.google.com/oauthplayground) in a new tab
2. Click the **gear icon** (Settings) in the top-right corner
3. Check **Use your own OAuth credentials**
4. Paste your **Client ID** and **Client Secret** into the fields
5. Click **Close**
6. On the left side, find and check these scopes (scroll or use the search box):
   - Under **Google Calendar API v3**: `https://www.googleapis.com/auth/calendar`
   - Under **Gmail API v1**: `https://www.googleapis.com/auth/gmail.modify`
   - Under **Google Drive API v3**: `https://www.googleapis.com/auth/drive` (if applicable)
7. Click **Authorize APIs** (blue button)
8. Sign in with your Google account and click **Allow**
   - You may see a warning: "Google hasn't verified this app." Click **Advanced**, then **Go to Claude Assistant (unsafe)**. This is normal for personal projects -- you are authorizing your own app.
9. After approving, you are redirected back to the playground with an **Authorization code**
10. Click **Exchange authorization code for tokens**
11. Copy the **Refresh token** from the response (it is a long string starting with `1//`)

#### 6. Save Your Credentials

Add these three values to your password keychain file (`.env`) at the root of your notes folder:

```bash
GOOGLE_CLIENT_ID=paste_your_client_id_here
GOOGLE_CLIENT_SECRET=paste_your_client_secret_here
GOOGLE_REFRESH_TOKEN=paste_your_refresh_token_here
```

#### 7. Test the Connection

Ask Claude to test it by running a quick calendar check. If Claude can pull your upcoming events, the connection is working.

### Check: Do You Have Google Admin Access?

This section is only relevant if you are a Google Workspace administrator (you manage your organization's Google accounts). Most people are not.

1. Go to [admin.google.com](https://admin.google.com)
2. If you can sign in, you are a Google Workspace administrator
3. This means you can enable APIs and create OAuth credentials for your entire organization
4. This is separate from Cloud Console access -- you can have one without the other

If you are a Workspace admin, you can also pre-approve the OAuth consent screen for your organization so other team members do not see the "unverified app" warning.

### Step 2: Configure Direct Connections

Add direct connections for services you use outside the vault. Built-in connectors are added through claude.ai's **Settings > Connectors** page -- Claude cannot configure these connections itself; only you can add them. Self-configured MCP servers go in the vault's `.mcp.json` (committed with the repository, with secrets referenced as `${ENV_VAR}` placeholders). Your task manager and any database tools are common first choices. Each connection has its own setup process (usually an API key or OAuth flow). See the `/connect` skill for step-by-step guidance.

### Step 3: Document Your Integrations

Create an API Integration Guide in your vault that documents every connected service: auth method, base URL, key endpoints, gotchas learned the hard way. This is critical because the AI references this guide when making API calls. Without it, the AI has to guess at endpoint structures.

### Step 4: Build Your First Skill

Start with something simple. An end-of-day that just checks your calendar and email:

```markdown
# End of Day

## Step 1: Tomorrow's Calendar
1. Source .env and get a Google access token
2. Fetch tomorrow's events from the Calendar API
3. Format as a readable schedule

## Step 2: Email Check
1. Fetch today's important emails from Gmail API
2. Surface anything needing a response

## Step 3: Summary
Present a brief end-of-day report.
```

Then add sections as you connect more integrations: meeting transcripts, Slack, time tracking, task sync.

### Step 5: Add Scripts for Complex Operations

When a skill step gets too complex for inline curl commands (pagination, state tracking, multi-step logic), extract it into a Python script in `scripts/`. Give the script a `--json` output flag so the AI can parse results programmatically.

### Step 6 (Advanced): Schedule Automation

Most users just run `/eod` manually before wrapping up. If you want it to run on a schedule (e.g., 11:30 PM weekdays), create a scheduled Routine in Claude Code on the web pointed at your vault repository with the prompt `/eod` (see "Scheduled Automation (Routines)" above). No terminal, no cron, and your computer does not need to be on.

---

## Alternatives: Zapier and Manual Connections

Not every tool has a direct connection (MCP server) built for Claude. When a direct connection is not available, there are other ways to connect:

### Zapier

Zapier connects apps together without coding, like a middleman. You set up a "Zap" that says "when X happens in App A, do Y in App B." This is useful for:
- Connecting tools that Claude cannot reach directly
- Simple automations like "when I get an email from [sender], create a task in my task manager"
- Bridging tools without building custom scripts

Zapier has a free tier for basic use. Visit [zapier.com](https://zapier.com) to explore.

### Manual Connections (WebFetch/WebSearch)

For occasional use, Claude can access many tools through the web. Using WebFetch and WebSearch, Claude can visit websites, read pages, and extract information without any special connection. This is slower and less reliable than a direct connection, but works for tools you only use occasionally.

---

## Lessons Learned

### Shell Isolation

Each shell command runs in a fresh session. Environment variables from `source .env` don't persist to the next command. Always source credentials and use them in the same command chain (`&&`), or extract values and pass them explicitly.

### File Edits Are Safe

The vault is a Git repository in your cloud workspace -- there is no background file sync, so the built-in editor is safe for reads and writes. You do not need special atomic-write handling; edit files normally. Git is the durability layer: commit and push to persist your changes.

### MCP Tool Payload Limits

MCP tools can struggle with very large text payloads (e.g., inserting a full 30-page roadmap into a database field). For large content, use the REST API directly via curl with jq for JSON construction, bypassing the MCP tool.

### Rate Limits and Pagination

Slack's API in particular has aggressive rate limits. When scanning multiple workspaces, space out requests. Fathom's API paginates with `next_cursor`. Always handle pagination rather than assuming all results fit in one response.

### OAuth Token Freshness

Google's OAuth refresh endpoint issues a new token on every call. If you call it twice, only the most recent token is valid. Get one token and use it immediately across all requests in that session.

### Deduplication Everywhere

Every system that syncs data between two sources needs deduplication. The AI checks for existing items before creating new ones: fuzzy-matching task names against vault items, checking Slack message timestamps against a processed-messages state file, comparing new call action items against existing tasks in client files. Without this, you get duplicates within a week.

### The Manifest Pattern

For long-running workflows (like EOD with multiple sections), use a manifest file to track every item extracted. This prevents items from being lost to context compression (when the AI's conversation gets too long, older context gets summarized). The manifest serves as a persistent ledger the AI can read back at any point.

### Unattended Runs Need an Explicit Push

A scheduled Routine's session is recycled the moment it ends, exactly like an interactive one. If the workflow it runs does not finish with a successful `git push`, the run's output is silently lost -- the routine "worked" and nothing arrived. The `/eod` command ends with a persist step for this reason; keep that step when customizing.
