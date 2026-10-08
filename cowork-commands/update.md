---
name: update
description: Bring this vault up to the newest version of the system without losing anything you have built.
---

# /update

Bring this vault up to the newest version of the system, without losing anything the owner has built.

1. Clone the template fresh into a new, empty folder outside the vault: `TPL="$(mktemp -d)/ccs-template" && git clone --quiet https://github.com/IntegralOrg/ClaudeCodeSystem "$TPL"` (on Windows, make a new empty folder under the temp directory and use its path as `TPL`). Keep `$TPL` for the whole update; never reuse a folder from an earlier run.
2. Read `$TPL/System/Updating.md` **from that clone** (the vault's copy may be older) and follow it to the end: adopt by default, never destroy the owner's work, one commit, a short report.
3. Do not stop to ask the owner which changes to take. Ask only if the clone fails; then say plainly that GitHub could not be reached.
