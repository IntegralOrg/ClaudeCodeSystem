---
name: vault-hygiene
title: Vault Hygiene
schedule: "0 1 * * *"
timezone: SET_AT_SETUP
prompt: "/vault-audit"
connectors: []
keys: []
optional_keys: []
description: Nightly self-healing pass: frontmatter, duplicate-subject detection, canonical markers, a report in _generated/vault-hygiene/.
---
# Vault Hygiene

Runs nightly at 1 AM. Needs no keys. First step every run: `python3 scripts/check-keys.py --routine vault-hygiene`. If this run's keys check exits 0, then in `System/Routines.md`, under this routine's `## <title>` heading, if the first bullet reads `- live_since: not live` (or is missing), change that same bullet to `- live_since: <today's date>`; never add a second live_since bullet. Its report is `_generated/vault-hygiene/audit-log.md`; End of Day reads that file's newest date to confirm this ran. It does not repair duplicated frontmatter lines: the autosync workflow does that on branch merges only, and a duplicate left by a local rebase is reported by this routine's frontmatter check and fixed by hand.
