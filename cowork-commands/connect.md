---
name: connect
description: Part 3 of 4 setup: connect your tools (calendar, email, task manager, etc.).
---

# Connect: Set Up Your Tool Connections

This is Part 3 of 4 in the setup process. The user has already run `/onboard` (built their vault) and `/train` (learned how the system works). Now we connect their actual tools.

**Prerequisites:** CLAUDE.md exists with tool preferences from `/onboard`. `.env` file exists with placeholder comments.

**Voice:** Patient, step-by-step guide. Never assume they know what an API key is or where to find settings in an app. Every instruction should be "click this, then click that."

**Important:** Use `AskUserQuestion` at EVERY step to confirm before moving on. Test EVERY connection with real data before moving to the next tool. Do not leave any tool half-connected.

---

## Step 0: Check Prerequisites

### How Connections Work Here

The user is running **Claude Code on the web** (that was recorded in CLAUDE.md during `/onboard`). No need to ask which interface they are using.

Connection rules:
- **Built-in integrations** (Gmail, Google Calendar, ClickUp, etc.) must be connected by the user through the **Customize** / connectors section of Claude Code on the web. **Claude cannot create or modify those connections itself.** Never try to set one up on the user's behalf. If a new integration is needed, tell the user what to connect and where to find it in the **Customize** section.
- **Permissions and MCP config live in the vault repository** so they survive between cloud sessions: pre-approve connected tools by adding `"mcp__...__*"` entries to `permissions.allow` in the vault's `.claude/settings.json` (committed), and define self-configured MCP servers in the vault's `.mcp.json` (also committed -- reference secrets as `${ENV_VAR}` placeholders, never paste raw values into a committed file).
- **API-based integrations** (called with curl or scripts) work directly in the workspace. Credentials go in `.env` for the current session, but `.env` is untracked and the workspace is temporary -- the **permanent** home for every credential is an environment variable in the Claude Code **environment settings**. Whenever you save a key to `.env`, also walk the user through adding it there so future sessions have it.

Before connecting any tools, verify the workspace has what we need. Run these checks silently and only surface issues.

### Python packages

Run: `python3 -c "import markdown, requests" 2>&1`

If it fails (ModuleNotFoundError), tell the user:
"I need to install two small Python packages that the system uses for creating Google Docs and calling APIs. This is a one-time setup."

Run: `pip3 install markdown requests`

If pip3 is not found, try `python3 -m pip install markdown requests`.

If that also fails: "Python's package installer (pip) is not set up. Let me fix that."
Run: `python3 -m ensurepip --upgrade` then retry.

AskUserQuestion: "Python packages installed. Ready to continue?"
Options:
- Yes
- I got an error

### Node.js and npx

Only relevant if an MCP server or script we are setting up needs Node.js. Some MCP servers need it. Check: `npx --version 2>&1`

If npx is not found, tell the user: "One of your tools needs Node.js -- a free runtime that works behind the scenes. I can install it in the workspace."

Run: `curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt-get install -y nodejs` (drop `sudo` if it is unavailable in the workspace).

After install, verify: `npx --version`

AskUserQuestion: "Node.js is ready. Continuing to tool connections."
Options:
- Sounds good

**If everything passes**, skip this step entirely -- no output needed.

---

## Step 1: Figure Out What to Connect

Read CLAUDE.md to find which tools the user selected during `/onboard`. Also read `.env` to see which credentials are still blank.

Present the list:

"During setup, you said you use these tools:"
- [List each tool with a one-line description]

"We are going to connect each one now. I will walk you through every step and test each connection before moving on."

AskUserQuestion: "Which one should we start with?"
Options:
- [List their tools as options, recommending the most impactful one first]
- Just go in order

---

## Step 2: Connect Each Tool

Go through each tool the user selected. After completing each one, say: "[Tool] is connected! [N] more to go. Ready for the next one ([next tool name])?"

**If the user wants to pause**, note which tools are done and which remain. Tell them: "When you come back, type `/connect` and I will pick up with [next tool]."

### Google Calendar and Gmail

**First, determine the connection method:**

AskUserQuestion: "There are two ways to connect Google. Which sounds better to you?"
Options:
- **Easy way (recommended):** Sign in through Claude.ai's settings page. Takes 2 minutes, no technical setup.
- **Full control way:** Use the `gws` CLI to set up your own Google access. This is the preferred custom path if you also want Google Drive and Docs. Cloud Console is the fallback if the CLI is unavailable.
- I am not sure, help me decide

**If they are not sure:** "The easy way is best for most people. It gives Claude access to your calendar and email in about 2 minutes. The only reason to choose the full control way is if you also want Claude to create Google Docs or manage files in Google Drive. If you do, prefer the `gws` CLI. You can always add the full control way later."

---

#### Easy Way: Claude.ai Managed Connections

Walk through step by step with AskUserQuestion confirmations:

1. "Open your browser and go to **claude.ai**. Sign in to your account."

AskUserQuestion: "Are you on the Claude.ai dashboard?"
Options:
- Yes
- I need to create an account first
- I am having trouble signing in

2. "Click your **profile icon** in the bottom-left corner, then click **Settings**."

AskUserQuestion: "Are you on the Settings page?"
Options:
- Yes
- I cannot find the profile icon
- I see something different

3. "In the left sidebar, look for **Integrations** or **Connected Apps**. Click on it."

4. "Find **Google Calendar** and click **Connect**."

5. "Google will ask you to sign in and approve access. Sign in with your work email and click **Allow** on each permissions screen."

AskUserQuestion: "Did Google Calendar connect?"
Options:
- Yes, it shows as connected
- I got an error
- My work account was blocked -- Google says my organization does not allow this

If blocked:
AskUserQuestion: "Your work Google account restricts this. What would you like to do?"
Options:
- Try with my personal Gmail instead
- Switch to the full control way (`gws` CLI / Cloud Console fallback)
- Skip Google for now

6. Repeat for **Gmail** if they want email connected.

7. Update permissions in the vault's `.claude/settings.json`, adding `"mcp__claude_ai_Google_Calendar__*"` and/or `"mcp__claude_ai_Gmail__*"` to the allow list. (The connection itself lives in the **Customize** section -- this just pre-approves the tools so Claude does not have to ask every time.)

8. Test the connection:
- "Let me pull up your calendar to make sure it is working..."
- Use the Google Calendar MCP tools to list upcoming events
- Show 3-5 upcoming events

AskUserQuestion: "I found these events on your calendar: [list]. Does that look right?"
Options:
- Yes, that is my calendar!
- Those do not look right
- It returned an error

If successful: "Google Calendar is connected! Claude can now see your schedule, create time blocks, and prep you for meetings."

Repeat test for Gmail if connected.

**Move to the next tool.**

---

#### Full Control Way: `gws` CLI (Cloud Console fallback)

Prefer the `gws` CLI if it is available in the workspace. It is the recommended full-control path because it automates most of the Google setup. If `gws` is unavailable or fails, use the Cloud Console fallback below.

This fallback walkthrough assumes the user has never seen Cloud Console and has no existing project.

##### Check Access
"Open your browser and go to **console.cloud.google.com**. Sign in with the Google account you want to use."

AskUserQuestion: "What do you see?"
Options:
- A dashboard or welcome page
- A page asking me to agree to terms of service
- "This service is not available" or a blocked page
- Something else / I am confused

If terms of service: "Click **Agree and Continue**. Let me know when you are through."

If blocked:
AskUserQuestion: "Your organization blocks Cloud Console. What would you like to do?"
Options:
- Switch to the easy way (Claude.ai managed connections) instead
- Try with my personal Gmail account
- Ask IT for access (I will do this later)
- Skip Google for now

##### Create a Project
1. "At the top of the page, click the **project selector dropdown** (it might say 'Select a project' or show a project name)."
2. "Click **New Project** in the top-right corner of the popup."

AskUserQuestion: "Do you see the New Project form?"
Options:
- Yes, I see fields for Project name and Location
- I do not see a New Project button
- I already have a project I want to use

3. "For **Project name**, type **Claude Assistant**. Leave Location as-is. Click **Create**."
4. "Wait a few seconds, then select your new project from the dropdown at the top."

AskUserQuestion: "Are you inside the project? You should see 'Claude Assistant' in the top-left."
Options:
- Yes
- Not sure

##### Enable APIs
"Now we flip the switches to allow access to your Google services."

For each API, one at a time:

**Google Calendar API:**
- "Type **Google Calendar API** in the search bar at the top. Press Enter."
- "Click **Google Calendar API** in the results."
- "Click the blue **Enable** button."

AskUserQuestion: "Does it say enabled?"
Options:
- Yes
- I see an error
- I cannot find it

**Gmail API:**
- "Search bar again: type **Gmail API**. Click it, click **Enable**."

AskUserQuestion: "Gmail API enabled?"
Options:
- Yes
- No / error

**Google Drive API** (only if they want Drive/Docs):
- Same process.

##### OAuth Consent Screen
"Now Google needs to know what app is asking for access. Just a few form fields."

1. "In the left sidebar: **APIs & Services** > **OAuth consent screen**."
   - If no sidebar: "Click the hamburger menu (three lines) top-left, scroll to APIs & Services."

AskUserQuestion: "What do you see?"
Options:
- Choosing between Internal and External
- A consent screen already configured
- Something else

2. If choosing: "Pick **Internal** if available (company account). Otherwise pick **External**. Click **Create**."

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

5. Test Users (External only):
   - "Click **Add Users**, enter your email, click **Add**, then **Save and Continue**"

6. Summary: "Click **Back to Dashboard**"

AskUserQuestion: "Did you get through the consent screen?"
Options:
- Yes, I am back at the dashboard
- I got stuck
- Error about organization policies

##### Create Credentials
1. "Left sidebar: **APIs & Services** > **Credentials**"
2. "Click **+ Create Credentials** > **OAuth client ID**"

AskUserQuestion: "Do you see the form?"
Options:
- Yes, asking for Application type
- Error about consent screen
- Something else

3. "**Application type:** Desktop app. **Name:** Claude Assistant. Click **Create**."

4. "A popup shows your **Client ID** and **Client Secret**. Copy both now. You can also click **Download JSON**."

AskUserQuestion: "Did you copy both values?"
Options:
- Yes, I have them
- I closed the popup (walk them to Credentials page to find it)
- Something went wrong

##### Get Refresh Token
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

AskUserQuestion: "Did you get the refresh token?"
Options:
- Yes
- Error during authorization
- No refresh token showing
- I got lost

##### Save and Test
Save all three values to their `.env` file:
```
GOOGLE_CLIENT_ID=<value>
GOOGLE_CLIENT_SECRET=<value>
GOOGLE_REFRESH_TOKEN=<value>
```

Ask the user to paste each value.

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

AskUserQuestion: "I found these events: [list]. Look right?"
Options:
- Yes!
- Not right
- Error

If successful: "Google is connected!"

**Move to the next tool.**

---

### ClickUp

Walk through every step:

1. **Choose the connection path first.**

**Built-in integration (check this first):**
- Check whether ClickUp is available in the **Customize** / connectors section of Claude Code on the web.
- If yes, walk the user through connecting it there. **Only the user can add it** -- do not try to configure the built-in integration yourself. Once connected, add the matching `"mcp__...__*"` entry to the `permissions.allow` array in the vault's `.claude/settings.json`, then skip straight to the connection test below -- no API token needed.
- If no built-in integration exists, use a workspace MCP server (below) or fall back to the API-based integration. Both of those need an API token, so collect one now (step 2).

2. **Collect the API token (only for the MCP-server or API-fallback paths).**

"Open **ClickUp** in your browser and sign in."

"Click your **avatar** (bottom-left), then **Settings**."

AskUserQuestion: "Are you in ClickUp Settings?"
Options:
- Yes
- Cannot find settings

"In the left sidebar, click **Apps** (or **Integrations**). Look for **API Token**. Click **Generate** if needed. Copy the token."

AskUserQuestion: "Got the API token?"
Options:
- Yes
- Cannot find the API Token section
- Error

Save to `.env`:
```
CLICKUP_API_KEY=<token>
```

**Workspace MCP server (if there is no built-in integration, or it does not work):**
- Read the vault's `.mcp.json` (create it at the vault root if missing). Add a `mcpServers` block for ClickUp (merge with existing mcpServers if any). This file is committed with the vault, so the server definition persists across cloud sessions:

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

AskUserQuestion: "I found these ClickUp spaces: [list]. Right?"
Options:
- Yes!
- Something is off
- Error / no results

**If error:** Read the error message. Common fixes:
- "command not found" → Node.js/npx is not installed (go back to Step 0)
- "unauthorized" → API key is wrong, ask them to regenerate
- "ENOTFOUND" → server URL is wrong, search for the current package name

If successful: "ClickUp is connected! I can now create tasks, update statuses, and sync your vault with ClickUp."

**Move to next tool.**

---

### Fathom (Meeting Transcripts)

1. "Open **fathom.video** and sign in."

2. "Go to your **Settings** (profile icon or menu)."

AskUserQuestion: "In Fathom settings?"
Options:
- Yes
- Cannot find settings

3. "Look for **API**, **Integrations**, or **Developer**. Find your API key or generate one."

AskUserQuestion: "Got the API key?"
Options:
- Yes
- Cannot find it (may require a specific Fathom plan)
- My plan does not seem to include this

If plan issue: "Fathom API access may require a paid plan. We can skip this for now and use manual transcript processing. Or check fathom.video/pricing to see which plan includes API."

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

AskUserQuestion: "Found these meetings: [list]. Look right?"
Options:
- Yes!
- No meetings (might be new)
- Error

If successful: "Fathom is connected! Your call transcripts will be pulled automatically during end-of-day."

**Move to next tool.**

---

### Slack

"Slack takes a few more steps than the others, but we will go through each one."

1. "Open **api.slack.com/apps** in your browser."

AskUserQuestion: "What do you see?"
Options:
- Your Apps page
- Slack login
- Something else

2. "Click **Create New App** > **From scratch**."
3. "**App Name:** Claude Assistant. **Workspace:** [their workspace]. Click **Create App**."

AskUserQuestion: "On the app settings page?"
Options:
- Yes
- Error about workspace permissions (admin may need to approve)
- Something else

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

AskUserQuestion: "All 8 scopes added?"
Options:
- Yes
- Cannot find where to add scopes
- Some are not available

6. "Scroll up: **Install to Workspace** > **Allow**."
7. "Copy the **User OAuth Token** (starts with `xoxp-`)."

AskUserQuestion: "Got the token?"
Options:
- Yes
- No token showing
- Error during install

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

AskUserQuestion: "Found these channels: [list]. Your workspace?"
Options:
- Yes!
- Not right
- Error

If they have multiple workspaces: "Want to connect the next workspace now?" Repeat for each.

**Move to next tool.**

---

### Rize (Time Tracking)

1. "Open **rize.io** and sign in."
2. "Go to account settings."
3. "Find API key and copy it."

AskUserQuestion: "Got it?"
Options:
- Yes
- Cannot find it
- My plan might not include API

4. Save to `.env` and test.

**Move to next tool.**

---

### Other Tools

For tools not covered above (Asana, Trello, Todoist, Teams, Otter, Fireflies, Toggl, Harvest, etc.):

**First, check if an integration exists for the tool.** Use WebSearch: `"[tool name] Claude integration"`, `"[tool name] MCP server" claude`, or `"[tool name] model context protocol"`.

**If a built-in integration exists in Claude Code on the web:**
1. Tell the user which integration to add and walk them through finding it in the **Customize** / connectors section. **Do not attempt to configure this yourself** -- only the user can add built-in integrations through the **Customize** section.
2. Once they confirm it is connected, add `"mcp__toolname__*"` to the `permissions.allow` array in the vault's `.claude/settings.json`, then test with a lightweight tool call
3. Update CLAUDE.md integrations section

**If no built-in integration exists but an MCP server does:**
1. Search for the install command (usually `npx -y @some-org/mcp-server-toolname`)
2. Walk the user through getting credentials (API key, OAuth token, etc.)
3. Save credentials to `.env` for this session AND as an environment variable in the Claude Code environment settings (the permanent copy)
4. Add the `mcpServers` entry to the vault's `.mcp.json` (committed -- use `${...}` placeholders for secrets):
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
5. Add `"mcp__toolname__*"` to the `permissions.allow` array in the vault's `.claude/settings.json`
6. Test with a lightweight MCP tool call
7. Update CLAUDE.md integrations section (add to "Direct Connections")

**If no usable built-in integration or MCP server exists:**
1. Search for the tool's REST API documentation
2. Walk the user through getting an API key or personal access token
3. Save to `.env` for this session AND as an environment variable in the Claude Code environment settings (the permanent copy)
4. Test with a curl call
5. Update CLAUDE.md integrations section (add to "Tools That Need Login Credentials")

**For Python-based tools** (scripts that need pip packages):
1. Check if the required packages are installed: `python3 -c "import packagename" 2>&1`
2. If missing: `pip3 install packagename`
3. Document the dependency in the script's docstring and in CLAUDE.md under Local Tools

---

## Step 3: Final Check

When all tools are connected (or explicitly skipped):

### Verify integration setup

Read the vault's `.claude/settings.json` and `.mcp.json` and confirm:
1. Every workspace-configured MCP server has an entry in `.mcp.json`'s `mcpServers`
2. Every connected MCP server and built-in integration has a matching `"mcp__servername__*"` entry in `permissions.allow`
3. No raw secrets are pasted into either committed file -- env blocks reference `${ENV_VAR}` placeholders whose real values live in the Claude Code environment settings

If anything is missing, fix it now.

### Verify .env

Read the vault's `.env` and confirm:
1. Every API-based tool has its credential filled in (not placeholder)
2. No commented-out credentials for tools that were successfully connected
3. Every credential in `.env` is ALSO saved as an environment variable in the Claude Code environment settings (ask the user to confirm -- a value that exists only in `.env` is gone when this workspace is recycled)

### Verify CLAUDE.md

Read CLAUDE.md and confirm:
1. Connected tools are listed under the correct section (Direct Connections or Tools That Need Login Credentials)
2. Skipped tools are removed or commented out
3. Any new Local Tools scripts are documented

### Present the summary

"Here is where we stand:"
- List each tool with ✓ (connected and tested) or ○ (skipped, with reason)
- Note which tools were connected as built-in integrations in the **Customize** section, which were configured as workspace MCP servers, and which credentials were saved in `.env`

Then: "All your tools are connected and tested. The last step is `/finish` -- I will show you the system in action with your real data and teach you how to get the most out of it over time. Type `/finish` when you are ready."
