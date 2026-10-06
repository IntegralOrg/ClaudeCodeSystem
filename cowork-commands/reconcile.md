---
name: reconcile
description: Interactive EOD time-block reconciliation: check off completed tasks, mark carried/skipped, patch the calendar to actuals with done/carried/skipped prefixes, and log plan adherence.
---

# /reconcile -- EOD Time-Block Reconciliation

Interactive end-of-day command. Run when the user finishes deep-work blocks. It takes the time blocks `/morning` created, walks through what actually got done, checks off + updates the tasks in the vault, writes the day's actuals back to Google Calendar so the calendar becomes a **historical record of how long was spent on what**, and logs a **plan-adherence score** so the user can see how well they follow the plan day over day.

**This is NOT the full `/eod`.** It does the fast "did I do my blocks?" pass + calendar actualization only. It does NOT touch time tracking, meeting transcripts, the knowledge graph, or the daily note. `/eod` still owns all of that and points here for the reconciliation step.

---

## First action: live time check

Run `date`. Set `TODAY=YYYY-MM-DD`. Trust the live clock, never the system-prompt date. Run every calendar helper through the credential wrapper so it has credentials without you reading the credentials file:

The exact invocations are in Sections 1 and 2 (`python3 scripts/with-env.py -- python3 - ... <<'PY'`).

(The wrapper exports the variables into the child process only. Never read, source, or print the credentials file.)

## When to use

- The user "just finished" deep work / wants to "run through" the day / "check off" the blocks / "update the calendar to what I actually did."
- Any time the planned blocks and reality have diverged (block ran long, an ad-hoc call happened, something slipped to tomorrow).

**When NOT to use:** a full closeout (use `/eod`); a morning plan (use `/morning`).

---

## Section 1: Load the plan and the blocks

1. Read `Inbox/Today.md` for the human-readable day plan -- today's planned blocks/tasks. (Items the morning explicitly deferred still show in Today.md but are NOT "today's blocks" -- do not auto-check them.) For task identity (to update it later), open the client Inbox files (`Inbox/<Client>.md`) that Today.md references.
2. Pull today's **live** calendar events and capture their event IDs (the morning's blocks contain "Deep Work" in the title):

   ```bash
   python3 scripts/with-env.py -- python3 - "$TODAY" <<'PY'
   import os, sys, json, urllib.request, urllib.parse
   def _v(k): return os.getenv(k) or sys.exit('missing ' + k)
   d = sys.argv[1]
   TZ_OFFSET = "[YOUR_UTC_OFFSET]"  # replace with your UTC offset. Examples: -05:00 (EST), -08:00 (PST), +00:00 (UTC), +01:00 (CET), +05:30 (IST), +09:00 (JST)
   tok = json.load(urllib.request.urlopen('https://oauth2.googleapis.com/token',
       urllib.parse.urlencode({
           'grant_type': 'refresh_token',
           'client_id': _v('GOOGLE_CLIENT_ID'),
           'client_secret': _v('GOOGLE_CLIENT_SECRET'),
           'refresh_token': _v('GOOGLE_REFRESH_TOKEN'),
       }).encode()))['access_token']
   url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events?timeMin={d}T00:00:00{TZ_OFFSET}&timeMax={d}T23:59:59{TZ_OFFSET}&singleEvents=true&orderBy=startTime"
   for e in json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'Authorization': f'Bearer {tok}'}))).get('items', []):
       s = e.get('start', {}).get('dateTime', '')
       en = e.get('end', {}).get('dateTime', '')
       print(f"{s[11:16]}-{en[11:16]}  {e.get('summary', '')}  id={e['id']}")
   PY
   ```

## Section 2: Run-through (interactive, fast)

The point is a **brief** pass, not a 20-question interrogation. Present the blocks with their tasks grouped underneath, then:

- Ask the user to **name the exceptions** (what did NOT get done) rather than confirming every line. Default assumption: everything in the day's blocks is done unless flagged.
- For items the morning explicitly **deferred** but that still appear in Today.md, confirm explicitly with one `AskUserQuestion` (multi-select "which of these actually got done?") -- do not assume either way.
- Capture **four** states for every planned block/task, because the point is plan-adherence tracking, not just checkoff:
  - **done** (checkmark) -- happened, task finished.
  - **carried** (hourglass) -- the block ran but the work didn't finish (or only partly); it rolls to a later day.
  - **skipped** (X) -- the planned block did NOT happen at all (displaced by a meeting, slept through it, abandoned). This is the state easy to silently drop -- it MUST be captured so adherence is honest.
  - **new follow-ups** -- work that surfaced (a scope change, a new request, a blocker). Example: "Feature X shipped, but the client then asked for a scope change" = shipped is done AND a new follow-up task is born.
- A clean midday run will have **pending** blocks too (later today, not yet attempted). Those are neither done nor missed -- exclude them from the adherence denominator and note the run was a midday/partial pass.

**Never fabricate completion.** If you don't know, ask. Under-checking and flagging beats over-checking. An honest `X` you flagged is more valuable than a silent gap -- the whole point is to see the real adherence pattern.

## Section 3: Check off + update tasks in the vault

For each task, write the outcome to the client file where it lives.

- **Done tasks**: read the file, change `- [ ]` to `- [x]`, append ` -- <one-line note of what was actually done>` if useful, write it back.
- **Not-done tasks stay open**: no action needed by default. If something changed (priority shifted, new blocker, waiting-on changed), edit the line to reflect it.
- **New follow-ups** get appended under `## Open Tasks` in the appropriate client file as flat bullets, with a source note (e.g., `*from EOD reconcile <date>*`).
- **Do not hand-edit `Inbox/Today.md`.** It's a rendered snapshot; if you want a mid-day refresh, re-run the render (see `/eod-today`), not an in-place edit.

## Section 4: Reconcile the calendar to actuals

Goal: the calendar should show **what actually happened**, so future-you can see how long each thing really took -- and so missed blocks are **visible**, not silently deleted. For each morning block, `PATCH` it to reality; `POST` new events for unplanned time that actually occurred (naps, ad-hoc calls).

**Title-prefix convention (this is what makes adherence skimmable on the calendar):**
- `[done]` -- block happened, task finished. Rewrite the description to the **specific tasks actually finished**.
- `[carried]` -- block happened but the work didn't finish; note what's carried and to when.
- `[skipped]` -- the planned block did NOT happen. **Do not delete it** -- prefix `[skipped]`, keep it in place, and note why in the description (e.g., "displaced by ad-hoc call"). A deleted block erases the evidence of a missed plan; a `[skipped]` block is the record. (Only delete an event that is a genuine duplicate/artifact, and ask first.)
- Adjust `start` / `end` to the real times (block started late, ended early, got interrupted). Use your IANA timezone name (e.g., `America/New_York`, `America/Los_Angeles`, `Europe/London`) in the `timeZone` field.
- If a block was interrupted (e.g., a nap + an ad-hoc call landed mid-block), split it: shorten the block to its real focused window and add the interrupting events so the timeline is honest.

```bash
python3 scripts/with-env.py -- python3 - <<'PY'
import os, sys, json, urllib.request, urllib.parse
def _v(k): return os.getenv(k) or sys.exit('missing ' + k)
tok = json.load(urllib.request.urlopen('https://oauth2.googleapis.com/token',
    urllib.parse.urlencode({
        'grant_type': 'refresh_token',
        'client_id': _v('GOOGLE_CLIENT_ID'),
        'client_secret': _v('GOOGLE_CLIENT_SECRET'),
        'refresh_token': _v('GOOGLE_REFRESH_TOKEN'),
    }).encode()))['access_token']
H = {'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'}
BASE = 'https://www.googleapis.com/calendar/v3/calendars/primary/events'
TZ = "[YOUR_IANA_TIMEZONE]"  # replace with your IANA timezone name. Examples: America/New_York, America/Los_Angeles, America/Chicago, Europe/London, Europe/Berlin, Asia/Kolkata, Asia/Tokyo

def patch(eid, body):
    r = json.load(urllib.request.urlopen(urllib.request.Request(
        f'{BASE}/{eid}', data=json.dumps(body).encode(), headers=H, method='PATCH')))
    print('PATCHED', r['summary'])

def insert(body):
    r = json.load(urllib.request.urlopen(urllib.request.Request(
        BASE, data=json.dumps(body).encode(), headers=H, method='POST')))
    print('CREATED', r['summary'])

# Example patch (fill in eventId + real times):
# patch('<eventId>', {
#   'summary': '[done] Deep Work 2a: [Client A] roadmap',
#   'description': 'Completed: rewrote onboarding email + set up welcome sequence.',
#   'start': {'dateTime': 'YYYY-MM-DDTHH:MM:SS', 'timeZone': TZ},
#   'end':   {'dateTime': 'YYYY-MM-DDTHH:MM:SS', 'timeZone': TZ},
# })
# Example insert (unplanned event):
# insert({
#   'summary': 'Ad-hoc call: [Contact]',
#   'start': {'dateTime': 'YYYY-MM-DDTHH:MM:SS', 'timeZone': TZ},
#   'end':   {'dateTime': 'YYYY-MM-DDTHH:MM:SS', 'timeZone': TZ},
# })
PY
```

## Section 5: Log plan adherence (the day-over-day record)

Append/update one row in the rolling log **`Work/Daily/Plan Adherence Log.md`** (create it from the header below if missing) so the user can see how well they follow the plan over time. This is the persistent home for the metric -- `Inbox/Today.md` is an ephemeral render and cannot hold history.

- **Upsert by date**: one row per day. If today's row already exists (e.g., an earlier midday run), **replace it** rather than adding a second. Use an atomic read-modify-write.
- **Adherence % = done / (done + carried + skipped)** over the planned blocks/tasks that *should have happened by now*. Exclude **pending** (later-today) blocks from the denominator. Round to a whole number.
- **Mark midday runs** as `(midday)` in the Note column -- they're provisional; the EOD run finalizes the row.
- Keep the "What slipped (why)" note to one line: the carried/skipped items + the real reason (ran into meetings, slept through it, scope change). The *why* is what makes the trend actionable.

Log header (create once if the file is missing):

```markdown
# Plan Adherence Log

> One row per day, written by `/reconcile`. Adherence = done / (done + carried + skipped) of the planned blocks that should have happened. Pending/later-today blocks excluded. Midday runs are provisional and finalized at EOD.

| Date | Day | Planned | Done | Carried | Skipped | Adherence | Note (what slipped + why) |
|------|-----|---------|------|---------|---------|-----------|----------------------------|
```

## Section 6: Summary

Report back, tight:

- Checked off (by client) + new follow-ups created.
- Carried and skipped, with the one-line reason each.
- Calendar: blocks updated (done/carried/skipped), events added, and the final actual timeline with total focused hours.
- **Adherence score** for the day (and whether it's provisional/midday), plus a one-line read on the pattern if the log shows a recent trend (e.g., "afternoons keep getting eaten by meetings").

---

## Section 7: Persist to Git

Commit and push before finishing. The vault runs in a temporary cloud workspace; unpushed changes are lost when the container ends. The push auto-retries on rejection so a concurrent commit from another session (e.g. an EOD Routine) doesn't strand the reconcile:

```bash
git add -A
if git diff --cached --quiet; then
  echo "No changes to commit."
else
  git commit -m "Reconcile YYYY-MM-DD"
  for attempt in 1 2 3; do
    if git push; then
      break
    fi
    echo "Push rejected on attempt $attempt; rebasing and retrying..."
    git pull --rebase origin main || { echo "Rebase failed; tell the user."; exit 1; }
  done
fi
```

If all 3 attempts fail, tell the user plainly: today's reconcile lives only in this workspace until a push succeeds.

---

## Quick Reference

| Step | Action |
|------|--------|
| Time check | `date`; run helpers via `python3 scripts/with-env.py -- ...` |
| Load | Read `Inbox/Today.md` for the plan; use client Inbox files for task identity; pull live calendar event IDs ("Deep Work" titles) |
| Run-through | Ask for **exceptions**, confirm **deferred** items explicitly, capture done/carried/**skipped**/new follow-ups |
| Tasks | Check off `- [ ]` -> `- [x]` in client files with actuals; append new follow-ups under `## Open Tasks` with source note; never hand-edit Today.md |
| Calendar | `PATCH` blocks to actuals: `[done]` / `[carried]` / `[skipped]` (keep, don't delete) + real times; `POST` unplanned events |
| Adherence | Upsert today's row in `Work/Daily/Plan Adherence Log.md`: done/(done+carried+skipped), exclude pending; midday = provisional |
| Git | `git add -A && git commit -m "Reconcile YYYY-MM-DD" && git push` |
| Scope | `/reconcile` is the light pass; `/eod` still owns time tracking, transcripts, graph, daily note |

## Common Mistakes

- **Auto-checking deferred items.** Tasks the morning pushed to a later day still appear in Today.md; they are not "today's blocks." Confirm before checking.
- **Inventing what was done.** A `[x]` with a specific note you made up is worse than an honest `[ ]`. Ask.
- **Editing the calendar to the *plan* instead of *reality*.** The whole point is actuals: real start/end, real interruptions, what actually shipped.
- **Silently dropping the misses.** A planned block that didn't happen must become a `[skipped]` on the calendar AND in the adherence log, never just vanish. Deleting it inflates the day's adherence and hides the pattern the user is trying to see. Only delete genuine duplicates/artifacts (ask first).
- **Skipping the adherence log.** Even a clean 100% day gets a row -- the value is the trend, and gaps in the log read as "didn't reconcile," not "perfect day."
- **Counting pending blocks as misses on a midday run.** Later-today blocks aren't skipped yet; exclude them from the denominator and mark the row `(midday)`.
- **Forgetting the new follow-up.** "Done, but the client then asked for X" means the task is done AND a new task exists. Capture both.
- **Running the calendar helper without the wrapper.** The Python helper can't see `GOOGLE_*` and dies with `KeyError`. Run it as `python3 scripts/with-env.py -- python3 - ...`; never source the credentials file.
- **Treating this as `/eod`.** No time tracking / transcripts / graph here. Run `/eod` for the full closeout.

## Related

- `/morning` -- creates the blocks this command reconciles.
- `/eod` -- full closeout; references this command for the time-block reconciliation step.
