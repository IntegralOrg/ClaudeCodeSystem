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

Runs nightly at 1 AM. Needs no keys. First step every run: `python3 scripts/check-keys.py --routine vault-hygiene`. If this run's keys check exits 0 and `System/Routines.md` has no `live_since` for this routine, add `live_since: <today>` there. Its report is `_generated/vault-hygiene/audit-log.md`; End of Day reads that file's newest date to confirm this ran. It also repairs duplicated frontmatter lines that a merge can leave behind.
