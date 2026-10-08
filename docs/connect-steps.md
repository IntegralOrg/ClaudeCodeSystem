# Connection Steps

Per-tool connection steps, one section per tool. Each section gives the exact click path, the token or key names, the line that goes in `.env`, and a quick test. Connect one tool at a time and test each connection with real data before moving to the next one. Do not leave a tool half-connected.

Voice for any walkthrough: patient and step by step. Never assume the user knows what an API key is or where a setting lives. Every instruction should read "click this, then click that."

## How connections work here

The vault runs in **Claude Code on the web**.

- **Built-in integrations** (Gmail, Google Calendar, ClickUp, and so on) are connected by the user through the **Customize** / connectors section of Claude Code on the web. Claude cannot create or modify those connections itself. If a new integration is needed, tell the user what to connect and where to find it in the **Customize** section.
- **Permissions and MCP config live in the vault repository** so they survive between cloud sessions. Pre-approve connected tools by adding `"mcp__...__*"` entries to `permissions.allow` in the vault's `.claude/settings.json` (committed). Define self-configured MCP servers in the vault's `.mcp.json` (also committed). Reference secrets there as `${ENV_VAR}` placeholders, never paste raw values into a committed file.
- **API-based integrations** (called with curl or scripts) work directly in the workspace. Credentials go in `.env` for the current session, but `.env` is untracked and the workspace is temporary. The **permanent** home for every credential is an environment variable in the Claude Code **environment settings**. Whenever a key is saved to `.env`, also add it there so future sessions have it.

## Before connecting anything

Run these checks silently and only surface issues.

### Python packages

Run `python3 -c "import markdown, requests" 2>&1`.

If it fails (ModuleNotFoundError), say: "I need to install two small Python packages that the system uses for creating Google Docs and calling APIs. This is a one-time setup." Then run `pip3 install markdown requests`.

If pip3 is not found, try `python3 -m pip install markdown requests`. If that also fails, run `python3 -m ensurepip --upgrade` and retry.

### Node.js and npx

Only needed if an MCP server or script being set up requires Node.js. Check with `npx --version 2>&1`.

If npx is not found, say: "One of your tools needs Node.js, a free runtime that works behind the scenes. I can install it in the workspace."

Run `curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt-get install -y nodejs` (drop `sudo` if it is unavailable in the workspace). Verify with `npx --version`.

If everything passes, skip this entirely.

## Google Calendar

There are two ways to connect Google.

- **Easy way (recommended):** sign in through Claude.ai's settings page. Takes 2 minutes, no technical setup.
- **Full control way:** use the `gws` CLI to set up your own Google access. This is the preferred custom path if you also want Google Drive and Docs. Cloud Console is the fallback if the CLI is unavailable.

The easy way is best for most people. The only reason to choose the full control way is if you also want Claude to create Google Docs or manage files in Google Drive. If so, prefer the `gws` CLI. The full control way can be added later.

The connector steps for Gmail and Google Calendar are the same, and one full control setup covers both (see the Gmail section for its easy way steps).

### Easy way: Claude.ai managed connections

1. "Open your browser and go to **claude.ai**. Sign in to your account."
2. "Click your **profile icon** in the bottom-left corner, then click **Settings**."
3. "In the left sidebar, look for **Integrations** or **Connected Apps**. Click on it."
4. "Find **Google Calendar** and click **Connect**."
5. "Google will ask you to sign in and approve access. Sign in with your work email and click **Allow** on each permissions screen."

If the work account is blocked (Google says the organization does not allow this), the options are: try with a personal Gmail instead, switch to the full control way (`gws` CLI / Cloud Console fallback), or skip Google for now.

6. Update permissions in the vault's `.claude/settings.json`, adding `"mcp__claude_ai_Google_Calendar__*"` to the allow list. (The connection itself lives in the **Customize** section. This only pre-approves the tools so Claude does not have to ask every time.)
7. Test the connection: "Let me pull up your calendar to make sure it is working..." Use the Google Calendar MCP tools to list upcoming events and show 3 to 5 of them. Confirm they look right.

If successful: "Google Calendar is connected! Claude can now see your schedule, create time blocks, and prep you for meetings."

### Full control way: `gws` CLI (Cloud Console fallback)

Prefer the `gws` CLI if it is available in the workspace. It is the recommended full-control path because it automates most of the Google setup. If `gws` is unavailable or fails, use the Cloud Console fallback below.

This fallback walkthrough assumes the user has never seen Cloud Console and has no existing project.

#### Check access

"Open your browser and go to **console.cloud.google.com**. Sign in with the Google account you want to use."

If a terms of service page appears: "Click **Agree and Continue**."

If the organization blocks Cloud Console, the options are: switch to the easy way (Claude.ai managed connections), try with a personal Gmail account, ask IT for access and come back later, or skip Google for now.

#### Create a project

1. "At the top of the page, click the **project selector dropdown** (it might say 'Select a project' or show a project name)."
2. "Click **New Project** in the top-right corner of the popup."
3. "For **Project name**, type **Claude Assistant**. Leave Location as-is. Click **Create**."
4. "Wait a few seconds, then select your new project from the dropdown at the top." (You should see 'Claude Assistant' in the top-left.)

If the user already has a project they want to use, use that one.

#### Enable APIs

"Now we flip the switches to allow access to your Google services." For each API, one at a time:

**Google Calendar API:**
- "Type **Google Calendar API** in the search bar at the top. Press Enter."
- "Click **Google Calendar API** in the results."
- "Click the blue **Enable** button."

**Gmail API:**
- "Search bar again: type **Gmail API**. Click it, click **Enable**."

**Google Drive API** (only if they want Drive/Docs): same process.

#### OAuth consent screen

"Now Google needs to know what app is asking for access. Just a few form fields."

1. "In the left sidebar: **APIs & Services** > **OAuth consent screen**." If there is no sidebar: "Click the hamburger menu (three lines) top-left, scroll to APIs & Services."
2. If choosing a type: "Pick **Internal** if available (company account). Otherwise pick **External**. Click **Create**."
3. Fill in the form:
   - "**App name:** Claude Assistant"
   - "**User support email:** Select your email"
   - "**Developer contact:** Your email again at the bottom"
   - "Skip logo and domain fields"
   - "Click **Save and Continue**"
4. Scopes page:
   - "Click **Add or Remove Scopes**"
   - "Search for and check:"
     - `https://www.googleapis.com/auth/calendar`
     - `https://www.googleapis.com/auth/gmail.modify`
     - `https://www.googleapis.com/auth/drive` (if applicable)
   - "Click **Update**, then **Save and Continue**"
5. Test users (External only): "Click **Add Users**, enter your email, click **Add**, then **Save and Continue**"
6. Summary: "Click **Back to Dashboard**"

If an organization policy error appears, the consent screen cannot be completed with that account; fall back to the easy way or a personal account.

#### Create credentials

1. "Left sidebar: **APIs & Services** > **Credentials**"
2. "Click **+ Create Credentials** > **OAuth client ID**" (if it complains about the consent screen, finish the consent screen first)
3. "**Application type:** Desktop app. **Name:** Claude Assistant. Click **Create**."
4. "A popup shows your **Client ID** and **Client Secret**. Copy both now. You can also click **Download JSON**." (If the popup was closed, they are on the Credentials page and can open the client to find both values again.)

#### Get a refresh token

"Last step. One-time sign-in to get a long-lasting key."

1. "New tab: **developers.google.com/oauthplayground**"
2. "Click the **gear icon** (top-right). Check **Use your own OAuth credentials**. Paste your Client ID and Secret. Click **Close**."
3. "On the left, find and check:"
   - Google Calendar API v3: `https://www.googleapis.com/auth/calendar`
   - Gmail API v1: `https://www.googleapis.com/auth/gmail.modify`
   - (Drive if applicable)
4. "Click **Authorize APIs**."
5. "Sign in and click **Allow**."
   - "If you see 'Google hasn't verified this app': click **Advanced** > **Go to Claude Assistant (unsafe)**. This is normal for personal projects."
6. "Click **Exchange authorization code for tokens**."
7. "Copy the **Refresh token** (long string starting with `1//`)."

#### Save and test

Save all three values to `.env` (ask the user to paste each value):

```
GOOGLE_CLIENT_ID=<value>
GOOGLE_CLIENT_SECRET=<value>
GOOGLE_REFRESH_TOKEN=<value>
```

Also save each one as an environment variable in the Claude Code environment settings (the permanent copy).

Test:

```bash
python3 scripts/with-env.py -- bash <<'SH'
ACCESS_TOKEN=$(curl -s -X POST "https://oauth2.googleapis.com/token" \
  --data "grant_type=refresh_token&client_id=${GOOGLE_CLIENT_ID}&client_secret=${GOOGLE_CLIENT_SECRET}&refresh_token=${GOOGLE_REFRESH_TOKEN}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -s "https://www.googleapis.com/calendar/v3/calendars/primary/events?maxResults=3&timeMin=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -c "import sys,json; events=json.load(sys.stdin).get('items',[]); [print(f'  {e.get(\"summary\",\"(no title)\")}') for e in events[:3]]" 2>/dev/null
SH
```

If it lists upcoming events: "Google is connected!"

## Gmail

The connector steps are the same as for Google Calendar, and one full control setup covers both. If Google Calendar was connected through the full control way, Gmail is already done (the Gmail API, the `gmail.modify` scope, and the same three `GOOGLE_*` values in `.env`); only run the test below.

### Easy way: Claude.ai managed connections

1. "Open your browser and go to **claude.ai**. Sign in to your account."
2. "Click your **profile icon** in the bottom-left corner, then click **Settings**."
3. "In the left sidebar, look for **Integrations** or **Connected Apps**. Click on it."
4. "Find **Gmail** and click **Connect**."
5. "Google will ask you to sign in and approve access. Sign in with your work email and click **Allow** on each permissions screen."

If the work account is blocked, the options are the same as for Google Calendar: try a personal Gmail, switch to the full control way, or skip Google for now.

6. Update permissions in the vault's `.claude/settings.json`, adding `"mcp__claude_ai_Gmail__*"` to the allow list. (The connection itself lives in the **Customize** section. This only pre-approves the tools.)
7. Test the connection with the Gmail MCP tools (for example, list a few recent message subjects) and confirm they look right.

### Full control way

Follow the full control way in the Google Calendar section. Enable the **Gmail API**, include the `https://www.googleapis.com/auth/gmail.modify` scope on the consent screen and in the OAuth Playground, and save the same `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REFRESH_TOKEN` values.

## ClickUp

1. **Choose the connection path first.**

   **Built-in integration (check this first):**
   - Check whether ClickUp is available in the **Customize** / connectors section of Claude Code on the web.
   - If yes, walk the user through connecting it there. **Only the user can add it.** Do not try to configure the built-in integration yourself. Once connected, add the matching `"mcp__...__*"` entry to the `permissions.allow` array in the vault's `.claude/settings.json`, then skip straight to the connection test below. No API token is needed.
   - If no built-in integration exists, use a workspace MCP server (below) or fall back to the API-based integration. Both of those need an API token, so collect one now (step 2).

2. **Collect the API token (only for the MCP-server or API-fallback paths).**

   "Open **ClickUp** in your browser and sign in."

   "Click your **avatar** (bottom-left), then **Settings**."

   "In the left sidebar, click **Apps** (or **Integrations**). Look for **API Token**. Click **Generate** if needed. Copy the token."

   Save to `.env`:

   ```
   CLICKUP_API_KEY=<token>
   ```

   **Workspace MCP server (if there is no built-in integration, or it does not work):**

   Read the vault's `.mcp.json` (create it at the vault root if missing). Add a `mcpServers` block for ClickUp (merge with existing mcpServers if any). This file is committed with the vault, so the server definition persists across cloud sessions:

   ```json
   {
     "mcpServers": {
       "clickup": {
         "command": "npx",
         "args": ["-y", "@anthropic/mcp-remote", "https://mcp.clickup.com/s/mc_live_XXX"],
         "env": {}
       }
     }
   }
   ```

   **Important:** The exact server URL or package depends on the ClickUp MCP server version available at setup time. Use WebSearch to find the current ClickUp MCP server setup command if the above does not work. Common alternatives:
   - `npx -y @anthropic/mcp-remote https://mcp.clickup.com/s/<connection_id>` (ClickUp's hosted MCP)
   - `npx -y clickup-mcp-server` (community package with `CLICKUP_API_KEY` env var)

   Also add `"mcp__clickup__*"` to the `permissions.allow` array in the vault's `.claude/settings.json`.

   If using an API-key-based server, pass the key via the env block **as a placeholder, never the raw value** (`.mcp.json` is committed; the real value lives in the Claude Code environment settings):

   ```json
   {
     "mcpServers": {
       "clickup": {
         "command": "npx",
         "args": ["-y", "clickup-mcp-server"],
         "env": {
           "CLICKUP_API_KEY": "${CLICKUP_API_KEY}"
         }
       }
     }
   }
   ```

   After writing the config, tell the user: "I have added the ClickUp connection to your workspace settings. Let me test it."

3. **Test the connection.**
   - If they connected ClickUp through the **Customize** section or a workspace MCP server, use the ClickUp tools to list their workspaces or spaces. Show results.
   - If they are using the API-token fallback, test with a lightweight ClickUp API call using the token saved in `.env`.

**If there is an error,** read the message. Common fixes:
- "command not found": Node.js/npx is not installed (see "Before connecting anything")
- "unauthorized": the API key is wrong, ask them to regenerate it
- "ENOTFOUND": the server URL is wrong, search for the current package name

If successful: "ClickUp is connected! I can now create tasks, update statuses, and sync your vault with ClickUp."

## Fathom (Meeting Transcripts)

1. "Open **fathom.video** and sign in."
2. "Go to your **Settings** (profile icon or menu)."
3. "Look for **API**, **Integrations**, or **Developer**. Find your API key or generate one."

   API access may require a paid plan. If the plan does not include it: "We can skip this for now and use manual transcript processing. Or check fathom.video/pricing to see which plan includes API."

4. Save to `.env`:

   ```
   FATHOM_API_KEY=<key>
   ```

5. Test:

   ```bash
   python3 scripts/with-env.py -- bash <<'SH'
   curl -s -H "X-Api-Key: ${FATHOM_API_KEY}" \
     "https://api.fathom.ai/external/v1/meetings?limit=3" \
     | python3 -c "import sys,json; meetings=json.load(sys.stdin).get('meetings',[]); [print(f'  {m.get(\"title\",\"(no title)\")} -- {m.get(\"date\",\"\")}') for m in meetings[:3]]" 2>/dev/null
   SH
   ```

   No meetings can simply mean the account is new.

If successful: "Fathom is connected! Your call transcripts will be pulled automatically during end-of-day."

## Slack

"Slack takes a few more steps than the others, but we will go through each one."

1. "Open **api.slack.com/apps** in your browser."
2. "Click **Create New App** > **From scratch**."
3. "**App Name:** Claude Assistant. **Workspace:** [their workspace]. Click **Create App**." (An error about workspace permissions means a workspace admin may need to approve.)
4. "Left sidebar: **OAuth & Permissions**."
5. "Scroll to **Scopes** > **User Token Scopes**. Add these one at a time:"
   - `channels:history`
   - `channels:read`
   - `chat:write`
   - `im:history`
   - `im:read`
   - `mpim:history`
   - `mpim:read`
   - `users:read`
6. "Scroll up: **Install to Workspace** > **Allow**."
7. "Copy the **User OAuth Token** (starts with `xoxp-`)."
8. Save to `.env`:

   ```
   SLACK_TOKEN_WORKSPACE_A=<token>
   ```

9. Test:

   ```bash
   python3 scripts/with-env.py -- bash <<'SH'
   curl -s "https://slack.com/api/conversations.list?types=public_channel&limit=5" \
     -H "Authorization: Bearer ${SLACK_TOKEN_WORKSPACE_A}" \
     | python3 -c "import sys,json; chs=json.load(sys.stdin).get('channels',[]); [print(f'  #{c[\"name\"]}') for c in chs[:5]]" 2>/dev/null
   SH
   ```

If they have multiple workspaces, repeat for each one (the next token is `SLACK_TOKEN_WORKSPACE_B`, and so on).

## Rize (Time Tracking)

1. "Open **rize.io** and sign in."
2. "Go to account settings."
3. "Find API key and copy it." (Their plan might not include API access.)
4. Save to `.env` and test.

## Other Tools

For tools not covered above (Asana, Trello, Todoist, Teams, Otter, Fireflies, Toggl, Harvest, and so on):

**First, check if an integration exists for the tool.** Use WebSearch: `"[tool name] Claude integration"`, `"[tool name] MCP server" claude`, or `"[tool name] model context protocol"`.

**If a built-in integration exists in Claude Code on the web:**
1. Tell the user which integration to add and walk them through finding it in the **Customize** / connectors section. **Do not attempt to configure this yourself.** Only the user can add built-in integrations through the **Customize** section.
2. Once they confirm it is connected, add `"mcp__toolname__*"` to the `permissions.allow` array in the vault's `.claude/settings.json`, then test with a lightweight tool call.
3. Update the CLAUDE.md integrations section.

**If no built-in integration exists but an MCP server does:**
1. Search for the install command (usually `npx -y @some-org/mcp-server-toolname`).
2. Walk the user through getting credentials (API key, OAuth token, etc.).
3. Save credentials to `.env` for this session AND as an environment variable in the Claude Code environment settings (the permanent copy).
4. Add the `mcpServers` entry to the vault's `.mcp.json` (committed, use `${...}` placeholders for secrets):
   ```json
   {
     "mcpServers": {
       "toolname": {
         "command": "npx",
         "args": ["-y", "@some-org/mcp-server-toolname"],
         "env": {
           "TOOL_API_KEY": "${TOOL_API_KEY}"
         }
       }
     }
   }
   ```
5. Add `"mcp__toolname__*"` to the `permissions.allow` array in the vault's `.claude/settings.json`.
6. Test with a lightweight MCP tool call.
7. Update the CLAUDE.md integrations section (add to "Direct Connections").

**If no usable built-in integration or MCP server exists:**
1. Search for the tool's REST API documentation.
2. Walk the user through getting an API key or personal access token.
3. Save to `.env` for this session AND as an environment variable in the Claude Code environment settings (the permanent copy).
4. Test with a curl call.
5. Update the CLAUDE.md integrations section (add to "Tools That Need Login Credentials").

**For Python-based tools** (scripts that need pip packages):
1. Check if the required packages are installed: `python3 -c "import packagename" 2>&1`
2. If missing: `pip3 install packagename`
3. Document the dependency in the script's docstring and in CLAUDE.md under Local Tools.

## Final check

When all tools are connected (or explicitly skipped):

### Verify integration setup

Read the vault's `.claude/settings.json` and `.mcp.json` and confirm:
1. Every workspace-configured MCP server has an entry in `.mcp.json`'s `mcpServers`.
2. Every connected MCP server and built-in integration has a matching `"mcp__servername__*"` entry in `permissions.allow`.
3. No raw secrets are pasted into either committed file. Env blocks reference `${ENV_VAR}` placeholders whose real values live in the Claude Code environment settings.

If anything is missing, fix it now.

### Verify .env

Read the vault's `.env` and confirm:
1. Every API-based tool has its credential filled in (not placeholder).
2. No commented-out credentials for tools that were successfully connected.
3. Every credential in `.env` is ALSO saved as an environment variable in the Claude Code environment settings (ask the user to confirm; a value that exists only in `.env` is gone when this workspace is recycled).

### Verify CLAUDE.md

Read CLAUDE.md and confirm:
1. Connected tools are listed under the correct section (Direct Connections or Tools That Need Login Credentials).
2. Skipped tools are removed or commented out.
3. Any new Local Tools scripts are documented.

### Present the summary

"Here is where we stand:"
- List each tool as connected and tested, or skipped with the reason.
- Note which tools were connected as built-in integrations in the **Customize** section, which were configured as workspace MCP servers, and which credentials were saved in `.env`.
