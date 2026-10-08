---
type: reference
created: 2026-10-08
updated: 2026-10-08
---
# Connecting Tools

Connectors (Gmail, Google Calendar, and the like) are added by the person, in Claude's **Customize** settings; the agent cannot add them for you. Keys and tokens go in one of two places: in a local session, into the credentials file at the vault root, which you open in Claude Desktop's file pane and paste into yourself; for routines, into the environment's **Environment variables** in Claude (Routines, then the environment). The agent never opens the credentials file, and you never paste a value into the chat. A session that was started before a connector was added cannot see it, so start a new session after connecting.

Connect one tool at a time and test each with real data before moving to the next. Do not leave a tool half-connected. Walk through each step as "click this, then click that"; never assume the person knows what an API key is or where a setting lives.

After any tool is connected, run `python3 scripts/check-keys.py` (the agent runs it; it prints names, never values) to see what is still missing for each routine.

## Before you connect anything

The agent runs these checks quietly and only mentions a problem.

- Python packages: `python3 -c "import markdown, requests"`. If it fails: `pip3 install markdown requests` (or `python3 -m pip install markdown requests`; if pip is missing, `python3 -m ensurepip --upgrade` first).
- Node.js: only when a tool being set up needs `npx`. Check `npx --version`; if it is missing, say that one of the tools needs a small free runtime (Node.js) and install it from nodejs.org on a local machine.

## Gmail

**What it is.** A connector that lets Claude read your mail and draft or send messages, through your Google account.

**Our recommendation.** Connect it. End of Day uses it to read the day and to email you when something needs you. Read access is what the routines need; sending is used only for that one note to you. If your work account blocks it (Google says the organization does not allow this), try a personal Gmail, use the full control way under Google Calendar below, or skip Google for now.

**The steps.**
1. Open your browser and go to **claude.ai**. Sign in.
2. Click your **profile icon** in the bottom-left corner, then click **Settings**.
3. In the left sidebar, open **Customize** (the connectors section; some accounts show it as **Integrations** or **Connected Apps**).
4. Find **Gmail** and click **Connect**.
5. Google asks you to sign in and approve access. Sign in with your work email and click **Allow** on each permissions screen.
6. Start a new session so it can see the connector. The agent then adds `"mcp__claude_ai_Gmail__*"` to the allow list in the vault's `.claude/settings.json` so it does not have to ask every time, and tests it by listing a few recent message subjects.

Full control way (own Google access, for Drive and Docs too): follow the full control way under Google Calendar. One setup covers both. Enable the **Gmail API**, include the `https://www.googleapis.com/auth/gmail.modify` scope on the consent screen and in the OAuth Playground, and save the same `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REFRESH_TOKEN` values.

**What changes afterwards.** End of Day reads your email, and can reach you by email when Vault Hygiene is stale or a key or connector is missing.

## Google Calendar

**What it is.** A connector that lets Claude see your schedule and create time blocks.

**Our recommendation.** Connect it, the easy way (about two minutes, no technical setup). Choose the full control way only if you also want Claude to create Google Docs or manage files in Google Drive; it can be added later. End of Day uses the calendar to read the day and, when it cannot send email, to put a "Brain needs you" all-day event on your calendar.

**The steps (easy way).**
1. Open **claude.ai** and sign in.
2. Click your **profile icon** in the bottom-left corner, then **Settings**.
3. In the left sidebar, open **Customize** (or **Integrations** / **Connected Apps**).
4. Find **Google Calendar** and click **Connect**.
5. Sign in with your work email and click **Allow** on each permissions screen.
6. Start a new session. The agent adds `"mcp__claude_ai_Google_Calendar__*"` to the allow list in `.claude/settings.json`, then lists three to five upcoming events to confirm it works.

**The steps (full control way).** Prefer the `gws` CLI if it is available on the machine, since it automates most of this. If it is unavailable or fails, use the Cloud Console path:

1. Go to **console.cloud.google.com** and sign in. If a terms page appears, click **Agree and Continue**. (If your organization blocks it, use the easy way, a personal Gmail account, or skip.)
2. Create a project: click the **project selector** at the top, **New Project**, name it **Claude Assistant**, click **Create**, then select it.
3. Enable APIs, one at a time: search **Google Calendar API** and click **Enable**; search **Gmail API** and click **Enable**; **Google Drive API** only if you want Drive and Docs.
4. OAuth consent screen: **APIs & Services**, then **OAuth consent screen**. Pick **Internal** if offered, otherwise **External**, then **Create**. App name **Claude Assistant**, your email as support and developer contact, skip logo and domain, **Save and Continue**. On Scopes, **Add or Remove Scopes** and check `https://www.googleapis.com/auth/calendar`, `https://www.googleapis.com/auth/gmail.modify`, and (if wanted) `https://www.googleapis.com/auth/drive`; **Update**, **Save and Continue**. External only: **Add Users**, enter your email, **Save and Continue**. Then **Back to Dashboard**.
5. Credentials: **APIs & Services**, **Credentials**, **+ Create Credentials**, **OAuth client ID**, application type **Desktop app**, name **Claude Assistant**, **Create**. Copy the **Client ID** and **Client Secret**.
6. Refresh token: open **developers.google.com/oauthplayground**; click the **gear icon**, check **Use your own OAuth credentials**, paste the Client ID and Secret, **Close**. Select the Calendar and Gmail scopes above, click **Authorize APIs**, sign in and **Allow** (if you see "Google hasn't verified this app", click **Advanced**, then **Go to Claude Assistant (unsafe)**; this is normal for a personal project). Click **Exchange authorization code for tokens** and copy the **Refresh token** (a long string starting with `1//`).
7. Save three values, by name: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`. Local session: paste them into the credentials file at the vault root. Routines: also add each as an environment variable in the environment's settings (the permanent copy).
8. Test (the agent runs this; the script loads the values itself):

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

**What changes afterwards.** End of Day reads today's and tomorrow's calendar and can place the "Brain needs you" event when it has to reach you.

## Slack

**What it is.** A Slack app you create in your own workspace, giving Claude a token to read channels and direct messages.

**Our recommendation.** Connect it if your team lives in Slack; skip it otherwise. It is optional for End of Day. Use a user token with read scopes plus `chat:write`; connect each workspace separately. Some workspaces need an admin to approve a new app.

**The steps.**
1. Open **api.slack.com/apps**.
2. Click **Create New App**, then **From scratch**.
3. **App Name:** Claude Assistant. **Workspace:** yours. Click **Create App**. (An error about workspace permissions means a workspace admin may need to approve.)
4. In the left sidebar, click **OAuth & Permissions**.
5. Scroll to **Scopes**, then **User Token Scopes**. Add, one at a time: `channels:history`, `channels:read`, `chat:write`, `im:history`, `im:read`, `mpim:history`, `mpim:read`, `users:read`.
6. Scroll up and click **Install to Workspace**, then **Allow**.
7. Copy the **User OAuth Token** (it starts with `xoxp-`).
8. Save it as `SLACK_TOKEN_WORKSPACE_A` (credentials file locally; environment variable for routines). A second workspace uses `SLACK_TOKEN_WORKSPACE_B`, and so on.
9. Test (the agent runs this):

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
2. Open your **Settings** (profile icon or menu).
3. Look for **API**, **Integrations**, or **Developer**. Find your API key or generate one.
4. Save it as `FATHOM_API_KEY` (credentials file locally; environment variable for routines).
5. Test (the agent runs this):

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
1. Check **Customize** (the connectors section) in Claude for a ClickUp connector. If present, click **Connect** and sign in. Only you can add it. Then start a new session; the agent adds the matching allow entry (`"mcp__clickup__*"`) to `.claude/settings.json` and lists your workspaces to test.
2. If there is no connector, use the API token path: open **ClickUp**, click your **avatar** (bottom-left), then **Settings**, then **Apps** (or **Integrations**), find **API Token**, click **Generate** if needed, and copy it. Save it as `CLICKUP_API_KEY` (credentials file locally; environment variable for routines). The agent tests it with a lightweight ClickUp API call.

**What changes afterwards.** End of Day's task sync creates and updates tasks in ClickUp instead of only in the vault.

## Other tools

For anything else (Asana, Trello, Todoist, Teams, Otter, Fireflies, Toggl, Harvest, Rize, and so on): the agent first checks whether Claude has a built-in connector for it (search the connector list; if so, you add it under **Customize**, then the agent adds its allow entry and tests it with a light call). If not, and the tool has a web API, you get an API key or token from the tool's own settings page and save it under an upper-case name such as `TOOLNAME_API_KEY`, in the credentials file locally and as an environment variable for routines; the agent writes a small script in `scripts/` that loads it through `scripts/envload.py` and tests it. The agent never edits MCP server configuration on its own. If the tool has neither, say so: it is not connected yet. Raw secrets never go in a committed file.

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
2. Confirms every connected connector has a matching allow entry in `.claude/settings.json`, that every workspace-configured MCP server (only if you asked for one) has an entry in `.mcp.json`, and that no raw secret sits in either committed file (use `${ENV_VAR}` placeholders).
3. Asks you to confirm that every key you pasted into the credentials file is also an environment variable in the environment's settings, since a value that exists only in the local file is not there when a routine runs in the cloud.
4. Confirms `CLAUDE.md` lists the connected tools and no longer lists skipped ones.
5. Summarises: each tool as connected and tested, or skipped and why; and which keys are present or missing.
