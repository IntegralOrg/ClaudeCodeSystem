---
name: eod-time
description: EOD Phase 3: Fetch, classify, and summarize today's time tracking sessions.
---

# EOD Phase 3: Time Tracking

Fetches today's time tracking sessions, detects untracked gaps, classifies each session by client and work type, and prints a summary. This example uses Rize, but the pattern adapts to any time tracker with an API.

**This phase only runs if time tracking is configured.** It runs in a fresh context and writes all state to disk. It reads the manifest from Phase 1 and calendar data from Phase 2.

**Critical rule: UTC conversion.** Rize stores timestamps in UTC. All date-range queries must convert local start/end of day to UTC before querying.

**Critical rule: Gap threshold.** Only flag untracked periods longer than 15 minutes. Shorter gaps are normal context-switch noise.

**Critical rule: Classification confidence.** Every session classification must carry a confidence tag (high, medium, low). Low-confidence items are flagged for manual review before relabeling.

---

## Step 1: Setup

1. Run `date` to confirm today's date and current time ([Your Timezone])
2. Do not read or source the credentials file. Run the Step 2 and Step 6 Rize requests through `python3 scripts/with-env.py -- ...` (export `START_UTC` and `END_UTC` first so the credential-loaded child sees them); `scripts/rize-classify.py` loads `RIZE_API_KEY` itself through `scripts/envload.py`
3. Set `TODAY` as the current date in `YYYY-MM-DD` format
4. Compute UTC boundaries for today:
   ```bash
   START_UTC=$(date -u -d "$TODAY 00:00:00 [Your Timezone]" +%Y-%m-%dT%H:%M:%SZ)
   END_UTC=$(date -u -d "$TODAY 23:59:59 [Your Timezone]" +%Y-%m-%dT%H:%M:%SZ)
   ```
5. Verify the Rize API key is set by checking inside the credential-loaded child (`python3 scripts/with-env.py -- bash -c '[ -n "$RIZE_API_KEY" ]'`; never print it); abort with a clear message if missing

---

## Step 2: Fetch Sessions

1. Query the Rize GraphQL API for today's sessions:
   ```bash
   export START_UTC END_UTC
   python3 scripts/with-env.py -- bash <<'SH'
   curl -s -X POST https://api.rize.io/api/v1/graphql \
     -H "Authorization: Bearer $RIZE_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"query":"{ sessions(startTime: \"'$START_UTC'\", endTime: \"'$END_UTC'\") { id title startTime endTime duration apps { name } } }"}'
   SH
   ```
2. Parse the response into a local sessions list
3. Write raw session data to `/tmp/eod-rize-sessions-$TODAY.json`
4. Print count of sessions fetched and total tracked hours

---

## Step 3: Gap Detection

1. Read today's calendar events from `/tmp/eod-calendar-$TODAY.md` (written by Phase 2)
2. Sort all Rize sessions by startTime
3. Walk the timeline from first session to last session, identifying periods with no Rize coverage
4. For each gap longer than 15 minutes during work hours (9 AM - 6 PM local):
   - Check if a calendar event covers the gap (meeting without screen activity)
   - If covered by calendar: log as "meeting (no screen)" with the event title
   - If not covered: log as "untracked" for manual review
5. Write gap report to `/tmp/eod-rize-gaps-$TODAY.md`
6. Print gap summary: count of gaps, total untracked minutes

---

## Step 4: Classification

1. Run the classification script:
   ```bash
   python3 scripts/rize-classify.py \
     --sessions /tmp/eod-rize-sessions-$TODAY.json \
     --calendar /tmp/eod-calendar-$TODAY.md \
     --output /tmp/eod-rize-classified-$TODAY.json
   ```
2. The script classifies each session on two axes:
   - **Client axis**: [Client A], [Client B], [Client C], [Client D], [Client E], or Internal
     - Uses app name patterns, calendar event cross-reference, and transcript keyword matching
   - **Work type axis**: `delivery`, `sales`, `audit`, `meeting`, `admin`, `internal`
3. Each classification includes a confidence level (high, medium, low)
4. Parse the output JSON for the review step

---

## Step 5: Review

1. Present classifications as a table:
   ```
   | # | Session | Start | End | Hrs  | Client     | Work Type | Confidence |
   |---|---------|-------|-----|------|------------|-----------|------------|
   | 1 | ...     | 9:00  | 10:30 | 1.5 | [Client A] | delivery  | high       |
   | 2 | ...     | 10:45 | 11:30 | 0.75| [Client B] | meeting   | low        |
   ```
2. Flag all low-confidence rows with a warning marker
3. List any untracked gaps beneath the table for manual classification
4. Pause for user confirmation or corrections before proceeding

---

## Step 6: Relabeling

1. For each confirmed classification, update the session label via Rize GraphQL mutation:
   ```bash
   python3 scripts/with-env.py -- bash <<'SH'
   curl -s -X POST https://api.rize.io/api/v1/graphql \
     -H "Authorization: Bearer $RIZE_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"query":"mutation { updateSession(id: \"SESSION_ID\", title: \"[Client] - WorkType\") { id title } }"}'
   SH
   ```
2. Log each mutation result (success or failure)
3. Skip any sessions the user marked as "skip" or left unconfirmed
4. Write relabel results to `/tmp/eod-rize-relabeled-$TODAY.json`

---

## Step 7: Summary

Print the final time tracking report:

1. **Hours per client**:
   ```
   [Client A]   3.25 hrs
   [Client B]   1.50 hrs
   Internal     0.75 hrs
   ```
2. **Hours per work type**:
   ```
   delivery     2.50 hrs
   meeting      1.75 hrs
   admin        0.50 hrs
   ```
3. **Totals**:
   - Total tracked: X.XX hrs
   - Total gaps (untracked): X.XX hrs
   - Sessions relabeled: N of M
4. Write summary to `/tmp/eod-rize-summary-$TODAY.md` for handoff to Phase 4
