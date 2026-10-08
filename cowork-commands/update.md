---
name: update
description: Bring this vault up to the newest version of the system without losing anything you have built.
---

# /update

Bring this vault up to the newest version of the system, without losing anything the owner has built.

1. Clone the template fresh, outside the vault: `git clone --quiet https://github.com/IntegralOrg/ClaudeCodeSystem "$TMPDIR/ccs-template"` (an empty folder; on Windows any temporary folder).
2. Read `System/Updating.md` **from that clone** (the vault's copy may be older) and follow it to the end: adopt by default, never destroy the owner's work, one commit, a short report.
3. Do not stop to ask the owner which changes to take. Ask only if the clone fails; then say plainly that GitHub could not be reached.
