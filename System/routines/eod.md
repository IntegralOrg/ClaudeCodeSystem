---
name: eod
title: End of Day
schedule: "0 23 * * 1-5"
timezone: SET_AT_SETUP
prompt: "/eod"
connectors: [Gmail, Google Calendar]
keys: []
optional_keys: [FATHOM_API_KEY, SLACK_TOKEN_WORKSPACE_A]
description: Reads the day (calendar, email, calls, Slack when connected), extracts action items, writes the daily note, updates client pages, checks that the other routines ran, and reaches you when something needs you.
---
# End of Day

Runs every weeknight at 11 PM in your time zone. Needs the Gmail and Google Calendar connectors; Fathom and Slack add call transcripts and messages when their keys are present. First step every run: `python3 scripts/check-keys.py --routine eod` plus a list of connected tools. If this run's keys check exits 0 and `System/Routines.md` has no `live_since` for this routine, add `live_since: <today>` there. Last step every run: one status line, and when Vault Hygiene is stale or a key or connector is missing, a message to you outside the vault (an email through the Gmail connector when it can send; otherwise an all-day calendar event titled "Brain needs you: <reason>"). Before sending, check `_generated/routine-alerts.json` (create if missing); send only if the reason is new or was last sent 7 or more days ago. After sending, record `{"<reason>": "<YYYY-MM-DD sent>"}` in `_generated/routine-alerts.json`.
