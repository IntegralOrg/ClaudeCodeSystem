---
type: reference
created: 2026-10-08
updated: 2026-10-10
---
# Getting Help

**What it is.** Who to ask, in what order, and what to bring.

**Our recommendation.** Ask the agent first. When it cannot fix something, tell Dean, your onboarding contact, and book a session with Dean for anything that needs hands-on help with your screen.

## 1. The agent (this session)

The agent answers anything covered in `System/`: how the system works, how to connect a tool, what a routine does, how to add a computer, and what to do next. If `System/` does not cover your question, it says so and points you here; it will not guess at setup advice.

## 2. Dean, when the agent cannot fix it

When a step fails and the agent cannot repair it (setup stopped partway, saving to GitHub keeps failing, the agent cannot drive the screen), the agent says so plainly, tells you to let Dean know, and writes a short report into `Inbox/` that you can send to Dean as is. The report holds:

- the last error line you saw (copied as text),
- the routine name involved, if any (`End of Day` or `Vault Hygiene`),
- the **Routine health** section of the newest note in `Work/Daily/` (if setup stopped before any daily note existed, the report says "no daily note yet" and carries on),
- which setup step it was on, and what it already tried.

The agent writes it with `python3 scripts/setup/help_report.py`, which hides anything that looks like a key or token. Send it to Dean, your contact at Integral, however you usually reach them.

## 3. Dean, for white-glove sessions

Book a session with Dean when a step needs someone with you: connecting Gmail, Google Calendar, Slack, or Fathom; adding keys to the environment; the two installs (Claude Desktop and GitHub Desktop) and the macOS permission grants (Accessibility, Screen Recording, and the one-time "control System Events" prompt). Dean can drive the screen with you and leave nothing half-connected.

## What never to paste anywhere

Never paste a key, token, or password value into a chat, an email, a ticket, or a note in the vault. Names are fine (`FATHOM_API_KEY`); values are not. Keys go only into the credentials file on your own machine (opened in Claude Desktop's file pane) or into the environment's **Environment variables** in Claude.
