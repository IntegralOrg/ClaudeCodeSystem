---
name: system-check
description: Check how this system is set up and whether it is working, and say so in six plain lines.
---

# /system-check

Tells you how this vault is set up and whether it is working, before anyone has to explain a problem. It runs by itself every night inside Vault Hygiene (Step 0b of `/vault-audit`); run it by hand on a support call or when something feels off. A fix is confirmed by the next night's check, never by someone pressing Done.

Rules for the whole run:
- **Names only, never a value.** No key, token, password, hook command line, or note text goes into anything this command writes or says. The script already holds to this; keep it that way in what you add.
- **Read-only**, except `_generated/system-check/<date>.json` and `.md`, the report for your contact in `Inbox/`, one line in today's daily note, and `_generated/routine-alerts.json`.
- **The owner is never the approver** (`System/Who Decides.md`): no approve or skip, no list of choices. Who fixes what follows `docs/DEVELOPING.md`, section "Decision tiers".
- Do not read or source the credentials file; `scripts/check-keys.py`, which the script runs, reports key names only.

## 1. Run the script

`python3 scripts/system-check.py`

It reads the vault only (never the home folder, `~/.claude.json`, or `~/.config`), writes `_generated/system-check/<date>.json` (every finding with its severity, tier, count, dates and file paths, for the maintainers) and `_generated/system-check/<date>.md` (the summary), and prints the summary. It always exits 0. Severities: **blocks cloud** (a routine or cloud session will fail or lose work), **local only** (this computer is affected), **fine** (recorded, not a problem).

On a support call with GitHub reachable, compare against a fresh copy of the template for an exact answer: clone it into a new, empty folder as `/update` does (`TPL="$(mktemp -d)/ccs-template" && git clone --quiet https://github.com/IntegralOrg/ClaudeCodeSystem "$TPL"`), run `python3 scripts/system-check.py --template "$TPL"`, then remove the clone. The nightly run skips this and reads the vault's own history instead.

## 2. What the script cannot see

- **Routines in the Claude account.** In a session that has the routine tools, call `list_triggers`, then `get_trigger` for each routine in `System/routines/`: note any routine that is missing, disabled, or lacks a connector its file declares. Names only (routine, connector).
- **Open pull requests.** If the JSON's `facts.open_pull_requests` is `null` and GitHub tools are available, count open pull requests and `claude/*` branches on the vault's repository.

Add each gap you find to the summary in step 4 at the severity it deserves (a missing or disabled routine blocks cloud).

## 3. Send what the system must not decide

Tier 1 findings (wording the nightly tuning step may fix) need nothing here: the tuning step applies them and the next night's check confirms whether they held. Do not change files in this command.

Tier 2 findings go to the people who maintain the template, packaged as names and counts only. The JSON's `tier2_package` already holds them in that format (routine, error class, count, first and last date, file paths) and marks each `"due": true` or `false` from `_generated/routine-alerts.json`, so each reason goes at most once per reason per 7 days.

1. If no item is due, skip to step 4.
2. Write the due items, one line each (`<reason>: <routine>, <error_class>, <count>x, <first> to <last>, <paths>`), to a scratch file with the Write tool (never a shell heredoc), then run `python3 scripts/setup/help_report.py --step "System check" --error-file <scratch file> --tried "nightly system check; details in _generated/system-check/<date>.json"`. It masks anything that looks like a key and writes the report into `Inbox/`.
3. If `Work/Daily/<date>.md` exists, add one plain line under its `## Routine health` section: `A report for your contact is in Inbox/; please send it on.`
4. Read `_generated/routine-alerts.json` (treat missing or malformed as `{}`), set each sent reason to today's date, and write it back with the Write tool.

Never put note content, a value, or anything from a session marked `"private": true` into the report.

## 4. Write the summary

Write `_generated/system-check/<date>.md` with the Write tool: the script's summary with step 2's gaps folded in by severity. End the run with that summary as your last message: at most six numbered plain lines, the top three problems first, each with its fix and the `System/` page it comes from. No tier numbers, no finding ids, no JSON; the JSON is for the maintainers. When nothing is wrong, one line says so and that the next nightly run checks again.
