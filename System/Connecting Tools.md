---
type: reference
created: 2026-10-08
updated: 2026-10-15
---
# Connecting Tools

Tool access decides how capable your agent is: it can only read what it is connected to. Every tool you named at setup is on the ledger, `System/Tools.md`, with its status; say "connect my tools" in any session and the agent runs the connect step for whatever is still open. The rule is connector first: when a tool has a good connector, that is the whole setup, no key. A key is the fallback for a tool with no good connector, or for a gap the table names.

You do the clicking (sign in, Allow); the agent cannot sign in for you, and it walks you through each step as "click this, then click that". You never paste a key or password into the chat. A session that was started before a connector was added may not see it, so the agent checks again in the next session.

## The table

| Tool | Connector | Covers | Gap | Ruling |
|---|---|---|---|---|
| Gmail | Gmail | read, search, draft, send | none known | connector |
| Google Calendar | Google Calendar | list, search, create events | none known | connector |
| Outlook and Teams | Microsoft 365 | mail search, calendar search, chat search | no send, no event create | connector; End of Day's push to you (an email or a calendar event) is not available on Microsoft today, so Routine health is where it tells you |
| Slack | Slack | read channels, search, send | none known | connector |
| Fathom | Fathom | meetings, summaries, transcripts, search | none known | connector (the API key path is retired) |
| Fireflies, Granola, tl;dv, Grain, Zoom, Tactiq, Circleback | each | transcripts | varies; judged live | connector |
| Asana, ClickUp, Notion, Linear, monday | each | tasks | varies | connector |
| HubSpot, Salesforce, QuickBooks, Google Drive | each | read, some write | varies | connector |
| Text messages, WhatsApp | none | | | `skipped (no route reads it today)` |
| Rize, Toggl, Harvest, anything not above | none in the registry | | | key, judged live |

A tool not in the table is judged live: the agent compares the connector's tool list (from the registry) against what the routines need (read mail, read calendar, read transcripts, send one message to the owner) and rules connector, key, or both.

## How a connector gets connected

This is the connect step setup runs (section 3 of `System/Setup Procedure.md`), and the one "connect my tools" runs again in any later session.

1. **First, the ones waiting for a check.** A tool marked `connected <date> (verify next session)` on the ledger was connected in a session that could not confirm it. The agent reads the connectors this session can see (`session_connectors_status`). If the tool's row says `connected` (or `disabled`, which the agent switches on with `set_session_connector_enabled`), the ledger line becomes `connected <today>`. Any other answer, or no row at all, puts it back to `not connected`, and it is connected again below.
2. **Then each tool still `not connected`,** the essential ones first (email, calendar, and your notetaker if you record calls), then the others if you want them now. The agent says in one sentence why it wants the tool ("Gmail, so End of Day can read what came in today") and puts a **Connect** button in the chat. Click **Connect**, sign in with the account you use for work, click **Allow** on each permissions screen, then tell the agent: **Connected** or **Later**.
3. **If no button appears** (a cloud session, or an older Claude Desktop), use the Connectors page: in Claude, open **Customize**, then **Connectors**, find the tool (for example **Gmail**), click **Connect**, sign in, click **Allow**, then tell the agent. After the first one, the agent can drive the screen for you if you say yes. The last resort is the browser at claude.ai/customize/connectors; your browser asks you to sign in to Claude once there, with the same email as the app.
4. **The agent checks and records it.** It reads `session_connectors_status` again and writes `- status: connected <today>` in that tool's section of `System/Tools.md`. When this session cannot see the new connector yet (it started before the connector was added, or you used the Connectors page), it writes `- status: connected <today> (verify next session)`, and the next "connect my tools" settles it (step 1). A sign-in that failed, or a connector still waiting for sign-in, counts as Later: the tool stays `not connected`.
5. **It pre-approves the tool,** so you are not asked every time it is used: it adds `"<prefix>__*"` to `permissions.allow` in the vault's `.claude/settings.json`, where `<prefix>` is everything before the second `__` in that connector's tool names. For a tool settled in step 1, this happens then, because the session that connected it could not read the names.

One try per tool, and it never blocks: on Later the tool stays open on the ledger and the agent moves on. While an essential tool is open, every session starts with one line saying so ("say 'connect my tools'"); for the others the line comes at most once a week.

**A connector added after a routine was created.** The routine does not pick it up by itself. On the connector path, open in Claude: Routines, End of Day, the arrow by its name, Edit, Advanced settings, the **Connectors** tab, and tick the new connector. In a cloud session the agent can try `update_trigger` instead. Then the agent updates the routine's `- connectors:` line in `System/Routines.md`.

## Keys, for a tool with no good connector

Only for a tool whose ruling in the table is a key (Rize, Toggl, Harvest, or a tool judged that way), or a gap the table names; Rize is the example below. Fathom and Slack are connectors now: an old `FATHOM_API_KEY` or Slack token from an earlier vault is no longer read, and End of Day declares no keys. A key a routine uses lives in two places, and both are needed for a routine to use it:

1. **The agent finds what is missing.** It runs `python3 scripts/check-keys.py --where`, which lists each missing key by name (never a value) and says where it goes: the `set-key.py` command for this computer, and the network secret for the routine's cloud environment, with its Allowed websites host and its header.
2. **On this computer: the pop-up.** The agent runs `python3 scripts/set-key.py NAME` (for example `python3 scripts/set-key.py RIZE_API_KEY --label "Rize API key"`). A box opens on your screen with a hidden field: on a Mac a dialog, on Windows a masked box, and elsewhere a hidden prompt in the terminal. Paste the key there and click **Save**. The agent sees only `SAVED RIZE_API_KEY`, never the value. If you cancel or the box was empty, it asks once more or moves on, and the ledger keeps the tool open. If no box can open at all, the agent follows "When a step fails" in `System/Setup Procedure.md`. In a cloud session there is no box; the copy on your computer is added later, in step 4 of `System/Adding Your Computer.md`.
3. **For the nightly routines: a network secret.** The routines run in the cloud, where your computer's copy does not exist. The same key goes on the routine's cloud environment as a **network secret**: Claude adds it to the request on the way out, so the session never sees it. In Claude, open Routines, End of Day, the arrow by its name, Edit, Advanced settings, the Cloud environment button, hover over the environment and click the gear. Under **Network secrets** click **Add secret**: Name `Rize`, Credential type Bearer, Allowed websites `api.rize.io`, paste the key, then click Connect. For a key whose `--where` line names another header (for example `X-Api-Key` with no prefix), set Credential type Bearer and, under Custom headers, set that name with no prefix and paste the key as the value. The secret's Name is the tool's name.
4. **Your plan.** Network secrets exist on the Pro and Max plans. On a Team plan the cloud copy is not available yet, so the tool is local-only: it works in your sessions on this computer, not in the nightly routines.
5. **The agent proves it.** It runs `python3 scripts/check-keys.py` again. For each key it makes one small call to the tool and reports it present, missing, or "could not check (network)"; could not check never blocks, and the routine's first run checks again. A key that answers is written to the ledger as `- status: key present <today>`.

For the agent: the pop-up writes the vault's credentials file, which the agent never opens, reads, or names to the person; the Local environment editor in Claude Desktop is the other place a value for this computer can go.

## When End of Day reports connector-missing

The **Routine health** section of the daily note (`Work/Daily/<date>.md`) says `connector-missing` with the connector's name when End of Day ran without a connector it needs (the ones listed under `connectors:` in `System/routines/eod.md`: Gmail and Google Calendar, or Microsoft 365). It means one of two things: the tool is not connected for your account (the ledger says `not connected`), or it is connected but the routine does not carry it. For the first, say "connect my tools". For the second, tick it in the routine's **Connectors** tab (the last paragraph of "How a connector gets connected"). The same reason is also sent to you outside the vault, at most once a week (on Google; Microsoft 365 has no push today).

## Claude plugins

**What it is.** A plugin adds extra skills to Claude Desktop (reusable ways of working, such as planning and debugging). Plugins run code with your permissions, so install only the ones named here.

**Our recommendation.** Install **Superpowers**. Local only, and once per machine. Setup installs it for you in your first local session; the steps below are for doing it by hand.

**The steps.**
1. In Claude Desktop, open **Settings**, then **Plugins**.
2. Pick **Superpowers** from the directory and install it.
3. If it is not in the directory, add the marketplace repository `obra/superpowers-marketplace` as a custom source, then install Superpowers from it.
4. Reload Claude Desktop (or start a new session). In a terminal, `/plugin` is the fallback way to do the same thing.

**What changes afterwards.** Brainstorming, systematic debugging, and planning skills appear and are used by name or when the task calls for them.

## Final check

When every tool on the ledger is connected, has its key, or is deliberately skipped, the agent:

1. Runs `python3 scripts/check-keys.py --where` and confirms nothing required is missing (it exits 0). It lists names only; never open the credentials file to check.
2. Confirms every connected connector has a matching allow entry in `.claude/settings.json` and that no raw secret sits in that committed file.
3. Asks the person to confirm that every key a routine uses is also a network secret on the routine's environment, since a value on this computer is not there when a routine runs in the cloud. The agent cannot read network secrets; the proof is `python3 scripts/check-keys.py` (the probe) or the routine's first run.
4. Confirms `CLAUDE.md` lists the connected tools under the correct section (Direct Connections or Tools That Need Login Credentials), no longer lists skipped ones, and documents any new Local Tools scripts.
5. Summarises: each tool as connected and tested, or skipped and why; which are connectors and which keys are present or missing; and `System/Tools.md` says the same.

## Appendix: the full control way for Google (Cloud Console)

Only when the table names a gap for the Gmail or Google Calendar connector that your routines need closed, or on a Team plan where the connector cannot do the job. This is the last resort; everyone else uses the Gmail and Google Calendar connectors. One full control setup covers both Gmail and Google Calendar.

For the agent: the three values this path saves (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`) live in the vault's credentials file, `.env` at the vault root, one `NAME=` line per key with nothing after the `=` until `scripts/set-key.py` saves a value; the agent never opens it. In a routine they are read from the environment's Environment variables, because a network secret only adds a header and cannot do Google's token exchange.

**The steps (full control way).** Prefer the `gws` CLI if it is available on the machine, since it automates most of this. If `gws` is unavailable or fails, use the Cloud Console path below. It assumes you have never seen Cloud Console and have no existing project.

*Check access.* Go to **console.cloud.google.com** and sign in with the Google account you want to use. If a terms of service page appears, click **Agree and Continue**. If your organization blocks Cloud Console, the options are: use the Gmail and Google Calendar connectors, try a personal Gmail account, ask IT for access and come back later, or skip Google for now.

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

If an organization policy error appears, the consent screen cannot be completed with that account; fall back to the Gmail and Google Calendar connectors or a personal account.

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

*Save and test.* Save three values, by name: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`. In a local session the agent runs `python3 scripts/set-key.py GOOGLE_CLIENT_ID`, `python3 scripts/set-key.py GOOGLE_CLIENT_SECRET` and `python3 scripts/set-key.py GOOGLE_REFRESH_TOKEN`, once each, and you paste each value in the box that opens; for routines, also add each as an environment variable in the environment's settings (the permanent copy). Then the agent runs this test (the script loads the values itself):

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
