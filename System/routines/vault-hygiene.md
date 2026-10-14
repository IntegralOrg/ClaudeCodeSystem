---
name: vault-hygiene
title: Vault Hygiene
schedule: "7 1 * * *"
timezone: SET_AT_SETUP
model: claude-opus-5-5
prompt: "/vault-audit"
connectors: []
keys: []
optional_keys: []
description: Nightly self-healing pass: a system check first (Step 0b), then frontmatter, duplicate-subject detection, canonical markers, a report in _generated/vault-hygiene/, and tuning from the week's sessions (Step 5b).
---
# Vault Hygiene

Runs nightly at 1:07 AM (seven minutes past the hour, because a routine set for :00 can start minutes late) on `claude-opus-5-5`: the pass makes canonical and supersession rulings and edits files on its own, so it gets the same model as End of Day; the `model:` line above is the one place to change it. Needs no keys. First step every run: `python3 scripts/check-keys.py --routine vault-hygiene`. If this run's keys check exits 0, then in `System/Routines.md`, under this routine's `## <title>` heading, if the first bullet reads `- live_since: not live` (or is missing), change that same bullet to `- live_since: <today's date>`; never add a second live_since bullet. Its report is `_generated/vault-hygiene/audit-log.md`; End of Day reads that file's newest date to confirm this ran. It does not repair duplicated frontmatter lines: the autosync workflow does that on branch merges only, and a duplicate left by a local rebase is reported by this routine's frontmatter check and fixed by hand.
