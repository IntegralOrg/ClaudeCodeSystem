---
type: reference
created: 2026-10-08
updated: 2026-10-08
---
# Connecting Tools

Connectors (Gmail, Google Calendar, and the like) are added by the person, in Claude's **Customize** settings; the agent cannot add them for you. Keys and tokens go in one of two places. In a local session they go into the credentials file, which is `.env` at the vault root (a hidden file: in Claude Desktop's file pane turn on hidden files, or on a Mac press Command+Shift+Period in the Open dialog); it contains one `NAME=` line per key with nothing after the `=` until you paste. The agent never opens it; the person does. For routines, keys go into the environment's **Environment variables** in Claude (Routines, then the environment). You never paste a value into the chat. A session that was started before a connector was added cannot see it, so start a new session after connecting.

Connect one tool at a time and test each with real data before moving to the next. Do not leave a tool half-connected. Walk through each step as "click this, then click that"; never assume the person knows what an API key is or where a setting lives.

## How connections work here

- **Built-in connectors** (Gmail, Google Calendar, ClickUp, and so on) are connected by the person in **Customize**. The agent cannot create or modify those connections. If a new one is needed, the agent says which tool to connect and where to find it.
- **Permissions and MCP config live in the vault repository**, so they survive between sessions. Pre-approve a connected tool by adding a `"mcp__...__*"` entry to `permissions.allow` in the vault's `.claude/settings.json`. Self-configured MCP servers are defined in the vault's `.mcp.json`; both files are committed, so reference secrets there as `${ENV_VAR}` placeholders, never raw values.
- **API-based tools** (called with scripts) read their keys from the environment: from the credentials file in a local session, and from the environment's variables in a routine. A key that exists only in the local file is gone when a cloud container is recycled, so the permanent copy of every key is an environment variable in the environment's settings.
- After any tool is connected, the agent runs `python3 scripts/check-keys.py` (it prints names, never values) to see what is still missing for each routine.

## Before you connect anything

The agent runs these checks quietly and only mentions a problem.

- **Python packages:** `python3 -c "import markdown, requests"`. If it fails (ModuleNotFoundError), say: "I need to install two small Python packages that the system uses for creating Google Docs and calling APIs. This is a one-time setup." Then `pip3 install markdown requests`. If pip3 is not found, `python3 -m pip install markdown requests`; if that also fails, `python3 -m ensurepip --upgrade` and retry.
- **Node.js and npx:** only needed if an MCP server or script being set up requires it. Check `npx --version`. If it is missing, say: "One of your tools needs Node.js, a free runtime that works behind the scenes." In a cloud session run `curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt-get install -y nodejs` (drop `sudo` if it is unavailable) and verify with `npx --version`. On a local machine, install it from nodejs.org and verify the same way.

If everything passes, skip this entirely.

## Gmail

**What it is.** A connector that lets Claude read your mail and draft or send messages, through your Google account.

**Our recommendation.** Connect it. End of Day uses it to read the day and to email you when something needs you. Read access is what the routines need; sending is used only for that one note to you. If your work account blocks it (Google says the organization does not allow this), try a personal Gmail, use the full control way under Google Calendar below, or skip Google for now.

**The steps (easy way).**
1. Open your browser and go to **claude.ai**. Sign in to your account.
2. Click your **profile icon** in the bottom-left corner, then click **Settings**.
3. In the left sidebar, open **Customize** (the connectors section; some accounts show it as **Integrations** or **Connected Apps**).
4. Find **Gmail** and click **Connect**.
5. Google asks you to sign in and approve access. Sign in with your work email and click **Allow** on each permissions screen.
6. Start a new session so it can see the connector. The agent then adds `"mcp__claude_ai_Gmail__*"` to the allow list in the vault's `.claude/settings.json` (the connection itself lives in **Customize**; this only pre-approves the tools) and tests it by listing a few recent message subjects.

**The steps (full control way).** One full control setup covers both Gmail and Google Calendar. If Google Calendar was connected the full control way, Gmail is already done (the Gmail API, the `gmail.modify` scope, and the same three `GOOGLE_*` values); only run the test. Otherwise follow the full control way under Google Calendar: enable the **Gmail API**, include the `https://www.googleapis.com/auth/gmail.modify` scope on the consent screen and in the OAuth Playground, and save the same `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REFRESH_TOKEN` values.

**What changes afterwards.** On the connector path (the easy way), attach the connector to the End of Day routine (Routines, the routine, Connectors; or `update_trigger`), then start a new session. The full control (key) path needs no attaching; it works once the three `GOOGLE_*` values are in the environment's variables. End of Day then reads your email and can reach you by email when Vault Hygiene is stale or a key or connector is missing.

## Google Calendar

**What it is.** A connector that lets Claude see your schedule and create time blocks.

**Our recommendation.** Connect it, the easy way (about two minutes, no technical setup). Choose the full control way only if you also want Claude to create Google Docs or manage files in Google Drive; it can be added later. If you do want that, prefer the `gws` CLI. End of Day uses the calendar to read the day and, when it cannot send email, to put a "Brain needs you" all-day event on your calendar.

**The steps (easy way).**
1. Open your browser and go to **claude.ai**. Sign in to your account.
2. Click your **profile icon** in the bottom-left corner, then **Settings**.
3. In the left sidebar, open **Customize** (or **Integrations** / **Connected Apps**).
4. Find **Google Calendar** and click **Connect**.
5. Sign in with your work email and click **Allow** on each permissions screen. If the work account is blocked (Google says the organization does not allow this), the options are: try a personal Gmail, switch to the full control way, or skip Google for now.
6. Start a new session. The agent adds `"mcp__claude_ai_Google_Calendar__*"` to the allow list in `.claude/settings.json`, then lists three to five upcoming events to confirm it works. If it does: "Google Calendar is connected. Claude can now see your schedule, create time blocks, and prep you for meetings."

**The steps (full control way).** Prefer the `gws` CLI if it is available on the machine, since it automates most of this. If `gws` is unavailable or fails, use the Cloud Console path below. It assumes you have never seen Cloud Console and have no existing project.

*Check access.* Go to **console.cloud.google.com** and sign in with the Google account you want to use. If a terms of service page appears, click **Agree and Continue**. If your organization blocks Cloud Console, the options are: switch to the easy way, try a personal Gmail account, ask IT for access and come back later, or skip Google for now.

*Create a project.*
1. At the top of the page, click the **project selector dropdown** (it might say "Select a project" or show a project name).
2. Click **New Project** in the top-right corner of the popup.
3. For **Project name**, type **Claude Assistant**. Leave Location as is. Click **Create**.
4. Wait a few seconds, then select your new project from the dropdown at the top (you should see "Claude Assistant" in the top-left).

If you already have a project you want to use, use that one.

*Enable APIs, one at a time.*
- **Google Calendar API:** type **Google Calendar API** in the search bar at the top and press Enter, click it in the results, click the blue **Enable** button.
- **Gmail API:** search bar again, type **Gmail API**, click it, click **Enable**.
- **Google Drive API** (only if you want Drive and Docs): same process.

*OAuth consent screen.*
1. In the left sidebar: **APIs & Services**, then **OAuth consent screen**. If there is no sidebar, click the hamburger menu (three lines) top-left and scroll to APIs & Services.
2. If choosing a type: pick **Internal** if available (company account), otherwise **External**. Click **Create**.
3. Fill in the form: **App name:** Claude Assistant. **User support email:** select your email. **Developer contact:** your email again at the bottom. Skip logo and domain fields. Click **Save and Continue**.
4. Scopes page: click **Add or Remove Scopes**, search for and check `https://www.googleapis.com/auth/calendar`, `https://www.googleapis.com/auth/gmail.modify`, and `https://www.googleapis.com/auth/drive` (if applicable). Click **Update**, then **Save and Continue**.
5. Test users (External only): click **Add Users**, enter your email, click **Add**, then **Save and Continue**.
6. Summary: click **Back to Dashboard**.

If an organization policy error appears, the consent screen cannot be completed with that account; fall back to the easy way or a personal account.

*Create credentials.*
1. Left sidebar: **APIs & Services**, then **Credentials**.
2. Click **+ Create Credentials**, then **OAuth client ID** (if it complains about the consent screen, finish the consent screen first).
3. **Application type:** Desktop app. **Name:** Claude Assistant. Click **Create**.
4. A popup shows your **Client ID** and **Client Secret**. Copy both now. You can also click **Download JSON**. (If the popup was closed, you are on the Credentials page; open the client to find both values again.)

*Get a refresh token (a one-time sign-in that gives a long-lasting key).*
1. Open a new tab: **developers.google.com/oauthplayground**.
2. Click the **gear icon** (top-right). Check **Use your own OAuth credentials**. Paste your Client ID and Secret. Click **Close**.
3. On the left, find and check: Google Calendar API v3 `https://www.googleapis.com/auth/calendar`; Gmail API v1 `https://www.googleapis.com/auth/gmail.modify`; (Drive if applicable).
4. Click **Authorize APIs**.
5. Sign in and click **Allow**. If you see "Google hasn't verified this app", click **Advanced**, then **Go to Claude Assistant (unsafe)**; this is normal for personal projects.
6. Click **Exchange authorization code for tokens**.
7. Copy the **Refresh token** (a long string starting with `1//`).

*Save and test.* Save three values, by name: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`. In a local session you paste them into the credentials file yourself; for routines, also add each as an environment variable in the environment's settings (the permanent copy). Then the agent runs this test (the script loads the values itself):

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

If it lists upcoming events: Google is connected.

**What changes afterwards.** On the connector path (the easy way), attach the connector to the End of Day routine (Routines, the routine, Connectors; or `update_trigger`), then start a new session. The full control (key) path needs no attaching; it works once the three `GOOGLE_*` values are in the environment's variables. End of Day then reads today's and tomorrow's calendar and can place the "Brain needs you" event when it has to reach you.

## Slack

**What it is.** A Slack app you create in your own workspace, giving Claude a token to read channels and direct messages.

**Our recommendation.** Connect it if your team lives in Slack; skip it otherwise. It is optional for End of Day. Use a user token with read scopes plus `chat:write`; connect each workspace separately. Some workspaces need an admin to approve a new app. Slack takes a few more steps than the others, but each is one click.

**The steps.**
1. Open **api.slack.com/apps** in your browser.
2. Click **Create New App**, then **From scratch**.
3. **App Name:** Claude Assistant. **Workspace:** yours. Click **Create App**. (An error about workspace permissions means a workspace admin may need to approve.)
4. In the left sidebar, click **OAuth & Permissions**.
5. Scroll to **Scopes**, then **User Token Scopes**. Add these one at a time: `channels:history`, `channels:read`, `chat:write`, `im:history`, `im:read`, `mpim:history`, `mpim:read`, `users:read`.
6. Scroll up and click **Install to Workspace**, then **Allow**.
7. Copy the **User OAuth Token** (it starts with `xoxp-`).
8. Save it as `SLACK_TOKEN_WORKSPACE_A` (you paste it into the credentials file locally; add it as an environment variable for routines). If you have multiple workspaces, repeat for each one: the next token is `SLACK_TOKEN_WORKSPACE_B`, and so on.
9. The agent tests it:

```bash
python3 scripts/with-env.py -- bash <<'SH'
curl -s "https://slack.com/api/conversations.list?types=public_channel&limit=5" \
  -H "Authorization: Bearer ${SLACK_TOKEN_WORKSPACE_A}" \
  | python3 -c "import sys,json; chs=json.load(sys.stdin).get('channels',[]); [print(f'  #{c[\"name\"]}') for c in chs[:5]]" 2>/dev/null
SH
```

**What changes afterwards.** End of Day reads the day's Slack messages and pulls action items from them.

## Fathom

**What it is.** A meeting recorder; its API gives Claude your call transcripts and summaries.

**Our recommendation.** Connect it if you record calls. API access may need a paid Fathom plan; if yours does not include it, skip it and process transcripts by hand (check fathom.video/pricing for the plan that has the API). It is optional for End of Day.

**The steps.**
1. Open **fathom.video** and sign in.
2. Go to your **Settings** (profile icon or menu).
3. Look for **API**, **Integrations**, or **Developer**. Find your API key or generate one.
4. Save it as `FATHOM_API_KEY` (credentials file locally; environment variable for routines).
5. The agent tests it:

```bash
python3 scripts/with-env.py -- bash <<'SH'
curl -s -H "X-Api-Key: ${FATHOM_API_KEY}" \
  "https://api.fathom.ai/external/v1/meetings?limit=3" \
  | python3 -c "import sys,json; meetings=json.load(sys.stdin).get('meetings',[]); [print(f'  {m.get(\"title\",\"(no title)\")} -- {m.get(\"date\",\"\")}') for m in meetings[:3]]" 2>/dev/null
SH
```

No meetings can simply mean the account is new.

**What changes afterwards.** End of Day pulls the day's call transcripts and extracts the action items.

## ClickUp

**What it is.** A task manager. Claude can create and update tasks in it.

**Our recommendation.** Connect it only if ClickUp is where your team already tracks tasks; otherwise keep tasks in the vault. Prefer the built-in connector over an API token, since it needs no token at all.

**The steps.**

1. **Choose the connection path first.** Check whether ClickUp is available in **Customize** (the connectors section) in Claude. If yes, connect it there and sign in; only you can add it. Then add the matching `"mcp__...__*"` entry to `permissions.allow` in `.claude/settings.json` and skip straight to the test in step 3. No API token is needed. If there is no built-in connector, use a workspace MCP server (step 2) or the API-token fallback; both need an API token.

2. **Collect the API token (only for the MCP-server or API-token paths).** Open **ClickUp** in your browser and sign in. Click your **avatar** (bottom-left), then **Settings**. In the left sidebar, click **Apps** (or **Integrations**) and look for **API Token**; click **Generate** if needed and copy the token. Save it as `CLICKUP_API_KEY` (credentials file locally; environment variable for routines).

   **Workspace MCP server (if there is no connector, or it does not work).** Read the vault's `.mcp.json` (create it at the vault root if missing) and add a `mcpServers` block for ClickUp, merging with any existing `mcpServers`. The file is committed with the vault, so the definition persists across sessions:

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

   The exact server URL or package depends on the ClickUp MCP server version available at the time. Search the web for the current ClickUp MCP server setup command if the above does not work. Common alternatives: `npx -y @anthropic/mcp-remote https://mcp.clickup.com/s/<connection_id>` (ClickUp's hosted MCP) and `npx -y clickup-mcp-server` (community package with the `CLICKUP_API_KEY` env var). Also add `"mcp__clickup__*"` to `permissions.allow` in `.claude/settings.json`.

   If you use an API-key-based server, pass the key through the env block **as a placeholder, never the raw value** (`.mcp.json` is committed; the real value lives in the credentials file and the environment's variables):

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

   After writing the config, say: "I have added the ClickUp connection to your workspace settings. Let me test it."

3. **Test the connection.** If ClickUp was connected through **Customize** or a workspace MCP server, use the ClickUp tools to list your workspaces or spaces and show the results. If you used the API-token fallback, test with a lightweight ClickUp API call through `python3 scripts/with-env.py`.

If there is an error, read the message. Common fixes: "command not found" means Node.js/npx is not installed (see "Before you connect anything"); "unauthorized" means the API key is wrong, so regenerate it; "ENOTFOUND" means the server URL is wrong, so search for the current package name. If it works: "ClickUp is connected. I can now create tasks, update statuses, and sync your vault with ClickUp."

**What changes afterwards.** End of Day's task sync creates and updates tasks in ClickUp instead of only in the vault.

## Rize

**What it is.** A time tracker; with a key, Claude can read how your time was spent.

**Our recommendation.** Connect it only if you already use Rize. It is optional, and your plan may not include API access.

**The steps.**
1. Open **rize.io** and sign in.
2. Go to account settings.
3. Find the API key and copy it. (Your plan might not include API access.)
4. Save it under a name such as `RIZE_API_KEY` (credentials file locally; environment variable for routines), then the agent tests it with a lightweight call.

**What changes afterwards.** When `CLAUDE.md` lists a time tracking integration, End of Day's pipeline classifies your time by client and work type.

## Other tools

**What it is.** Anything not covered above: Asana, Trello, Todoist, Teams, Otter, Fireflies, Toggl, Harvest, and so on.

**Our recommendation.** Prefer a built-in connector, then an MCP server, then a plain API key. First check whether an integration exists: search the web for `"[tool name] Claude integration"`, `"[tool name] MCP server" claude`, or `"[tool name] model context protocol"`.

**The steps.**

*If a built-in connector exists:*
1. Tell the person which connector to add and walk them through finding it in **Customize**. Only the person can add it.
2. Once they confirm it is connected, add `"mcp__toolname__*"` to `permissions.allow` in `.claude/settings.json`, then test with a lightweight tool call.
3. Update the `CLAUDE.md` integrations section.

*If no connector exists but an MCP server does:*
1. Search for the install command (usually `npx -y @some-org/mcp-server-toolname`).
2. Walk the person through getting credentials (API key, OAuth token, and so on).
3. Save the credentials: the person pastes them into the credentials file for local sessions, and they are also added as an environment variable in the environment's settings (the permanent copy).
4. Add the `mcpServers` entry to the vault's `.mcp.json` (committed; use `${...}` placeholders for secrets):
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
5. Add `"mcp__toolname__*"` to `permissions.allow` in `.claude/settings.json`.
6. Test with a lightweight MCP tool call.
7. Update the `CLAUDE.md` integrations section (add to "Direct Connections").

*If no usable connector or MCP server exists:*
1. Search for the tool's REST API documentation.
2. Walk the person through getting an API key or personal access token.
3. Save it as above (credentials file locally, and an environment variable in the environment's settings).
4. Test with a curl call.
5. Update the `CLAUDE.md` integrations section (add to "Tools That Need Login Credentials").

*For Python-based tools (scripts that need pip packages):*
1. Check whether the required packages are installed: `python3 -c "import packagename"`.
2. If missing: `pip3 install packagename`.
3. Document the dependency in the script's docstring and in `CLAUDE.md` under Local Tools.

**What changes afterwards.** The tool appears in `CLAUDE.md`, and any routine or command that uses it can find it.

## Claude plugins

**What it is.** A plugin adds extra skills to Claude Desktop (reusable ways of working, such as planning and debugging). Plugins run code with your permissions, so install only the ones named here.

**Our recommendation.** Install **Superpowers**. Local only, and once per machine.

**The steps.**
1. In Claude Desktop, open **Settings**, then **Plugins**.
2. Pick **Superpowers** from the directory and install it.
3. If it is not in the directory, add the marketplace repository `obra/superpowers-marketplace` as a custom source, then install Superpowers from it.
4. Reload Claude Desktop (or start a new session). In a terminal, `/plugin` is the fallback way to do the same thing.

**What changes afterwards.** Brainstorming, systematic debugging, and planning skills appear and are used by name or when the task calls for them.

## Final check

When every tool is either connected or deliberately skipped, the agent:

1. Runs `python3 scripts/check-keys.py` and confirms it exits 0 (nothing required is missing). It lists names only; never open the credentials file to check.
2. Confirms every connected connector has a matching allow entry in `.claude/settings.json`, that every workspace-configured MCP server has an entry in `.mcp.json`, and that no raw secret sits in either committed file (use `${ENV_VAR}` placeholders).
3. Asks the person to confirm that every key they pasted into the credentials file is also an environment variable in the environment's settings, since a value that exists only in the local file is not there when a routine runs in the cloud.
4. Confirms `CLAUDE.md` lists the connected tools under the correct section (Direct Connections or Tools That Need Login Credentials), no longer lists skipped ones, and documents any new Local Tools scripts.
5. Summarises: each tool as connected and tested, or skipped and why; which were built-in connectors, which were workspace MCP servers, and which keys are present or missing.
