---
name: monthly-review
title: Monthly Review
schedule: "0 8 1 * *"
timezone: SET_AT_SETUP
prompt: "/monthly-review"
connectors: []
keys: []
optional_keys: []
description: First of the month: repairs the vault, rebuilds the graph, and writes a coaching note on how the system is being used.
---
# Monthly Review

Runs on the first of each month at 8 AM. Needs no keys. First step every run: `python3 scripts/check-keys.py --routine monthly-review`. If this run's keys check exits 0 and `System/Routines.md` has no `live_since` for this routine, add `live_since: <today>` there.
