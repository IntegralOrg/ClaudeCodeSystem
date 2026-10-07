---
description: For one session, answer "what durable change would have prevented this?" (or honestly, "nothing")
argument-hint: <session-id>
---

# /opportunity-scan

Reactive, one session at a time. Input: `$ARGUMENTS` (a Claude Code session id; if empty, ask for one).

1. Run `python3 scripts/system-journal/telemetry-stats.py --session $ARGUMENTS --json`. Note the failed calls and their `error_class`, repeated calls of the same tool on the same input (retries), and the slowest calls.
2. Read the session's evidence file: `_generated/system-journal/evidence/<YYYY-MM>/$ARGUMENTS.json`. Use its turns and `errors` for context only; never quote personal content.
3. Answer in at most 8 lines:
   - **What went wrong or cost time**, from the numbers (counts, classes, durations), not impressions.
   - **The one durable change** that would have prevented it: a rule (CLAUDE.md or a command), a hook, a memory, a script fix, or a doc pointer. Name the exact file.
   - Or **"Nothing durable"** when the friction was one-off. Say so plainly; do not invent a change.
4. Do not apply the change. If the user says go, apply it in the same session (edit the file; commit per your repo's rules).
