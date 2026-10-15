---
name: eod
title: End of Day
schedule: "7 23 * * 1-5"
timezone: SET_AT_SETUP
model: claude-opus-5-5
prompt: "/eod"
connectors: [Gmail, Google Calendar]
keys: []
optional_keys:
  - name: FATHOM_API_KEY
    probe_url: https://api.fathom.ai/external/v1/meetings?limit=1
    header: X-Api-Key
    header_prefix: ""
  - name: SLACK_TOKEN_WORKSPACE_A
    probe_url: https://slack.com/api/auth.test
    header: Authorization
    header_prefix: "Bearer "
description: Reads the day (calendar, email, calls, Slack when connected), extracts action items, writes the daily note, updates client pages, checks that the other routines ran, and reaches you when something needs you.
---
# End of Day

Runs every weeknight at 11:07 PM in your time zone (seven minutes past the hour, because a routine set for :00 can start minutes late) on `claude-opus-5-5`. Needs the Gmail and Google Calendar connectors; Fathom and Slack add call transcripts and messages when their keys are present. First step every run: `python3 scripts/check-keys.py --routine eod` plus a list of connected tools. If this run's keys check exits 0, then in `System/Routines.md`, under this routine's `## <title>` heading, if the first bullet reads `- live_since: not live` (or is missing), change that same bullet to `- live_since: <today's date>`; never add a second live_since bullet. Last step every run: one status line, and when Vault Hygiene is stale or a key or connector is missing, a message to you outside the vault (an email through the Gmail connector when it can send; otherwise an all-day calendar event titled "Brain needs you: <reason>"). Before sending, check `_generated/routine-alerts.json` (create if missing); send only if the reason is new or was last sent 7 or more days ago. After sending, record `{"<reason>": "<YYYY-MM-DD sent>"}` in `_generated/routine-alerts.json`.
