#!/bin/bash
# System Journal runner (Mac side). Two hooks in USER-level ~/.claude/settings.json call it:
#   SessionEnd:  bash ~/scripts/system-journal/run.sh --hook        (extract FINAL + distill, detached)
#   Stop:        bash ~/scripts/system-journal/run.sh --stop-hook   (extract the LIVE session, throttled, inline)
# Manual use: sweeps, backfills, re-derives.
#
# Canonical source: vault scripts/system-journal/. Installed copy: ~/scripts/system-journal/
# (macOS can refuse to execute scripts synced from a cloud folder like iCloud Drive or
# Dropbox directly; install.sh copies them to a plain local dir. See install.sh).
# Written for macOS /bin/bash 3.2: no `set -u` with empty arrays.
#
# Usage: run.sh [--hook | --stop-hook]
#        run.sh [--session <id>] [--force] [--redistill] [--limit N]     # sweep / backfill
#        run.sh --redistill-session <id>                                  # new journal line from the evidence file
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="$HOME/.system-journal"
LOG="$STATE_DIR/run.log"
LOCK="$STATE_DIR/run.lock"
STOP_THROTTLE_SECS=900   # a live session's evidence is at most 15 minutes stale
mkdir -p "$STATE_DIR/stop-stamps"

export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

read_hook_sid() {
  # Hook stdin carries JSON with session_id. Read it BEFORE any backgrounding: a detached
  # job loses the hook's stdin (that is why the id used to arrive empty).
  python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("session_id",""))
except Exception: print("")' 2>/dev/null
}

case "${1:-}" in
  --hook)
    SID=$(read_hook_sid)
    [ -z "$SID" ] && SID="${CLAUDE_CODE_SESSION_ID:-}"
    if [ -n "$SID" ]; then
      nohup bash "$DIR/run.sh" --session "$SID" >/dev/null 2>&1 </dev/null &
    else
      nohup bash "$DIR/run.sh" >/dev/null 2>&1 </dev/null &
    fi
    exit 0
    ;;
  --stop-hook)
    # Runs INLINE after every turn (a few hundred ms, no model call), throttled per session.
    # Writes the evidence file for the live session so a crash or a week-long session never
    # leaves the record more than 15 minutes stale. Never distills: the session is not over.
    SID=$(read_hook_sid)
    [ -z "$SID" ] && SID="${CLAUDE_CODE_SESSION_ID:-}"
    [ -z "$SID" ] && exit 0
    STAMP="$STATE_DIR/stop-stamps/$SID"
    if [ -f "$STAMP" ]; then
      age=$(( $(date +%s) - $(stat -f %m "$STAMP" 2>/dev/null || echo 0) ))
      [ "$age" -lt "$STOP_THROTTLE_SECS" ] && exit 0
    fi
    touch "$STAMP"
    python3 "$DIR/extract.py" --session "$SID" --stop >> "$LOG" 2>&1 </dev/null
    exit 0
    ;;
esac

# Split caller args: --force/--session/--redistill go to extract, --limit N goes to distill.
EXTRACT_ARGS=""
LIMIT_ARG=""
REDISTILL_SESSION=""
while [ $# -gt 0 ]; do
  case "$1" in
    --limit) LIMIT_ARG="--limit $2"; shift ;;
    --session) EXTRACT_ARGS="$EXTRACT_ARGS --session $2"; shift ;;
    --force) EXTRACT_ARGS="$EXTRACT_ARGS --force" ;;
    --redistill) EXTRACT_ARGS="$EXTRACT_ARGS --redistill" ;;
    --redistill-session) REDISTILL_SESSION="$2"; shift ;;
  esac
  shift
done

# Single-flight: a second invocation while one runs just exits (the next run sweeps).
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "$(date '+%F %T') skipped: another run holds $LOCK" >> "$LOG"
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

{
  if [ -n "$REDISTILL_SESSION" ]; then
    # Re-derive ONE journal line from the evidence file (no transcript needed). ~$0.10.
    echo "$(date '+%F %T') redistill from evidence: $REDISTILL_SESSION"
    python3 - "$REDISTILL_SESSION" <<'PY' 2>&1
import json, os, sys
sys.path.insert(0, os.path.expanduser("~/scripts/system-journal"))
from extract import load_state, merge_state
sid = sys.argv[1]
s = load_state().get(sid, {})
if not s.get("evidence"):
    print(f"no evidence file recorded for {sid}; run extract first"); sys.exit(1)
merge_state({sid: {"final": True, "distilled": False}})
PY
    python3 "$DIR/distill.py" 2>&1
    echo "$(date '+%F %T') run end"
    exit 0
  fi
  echo "$(date '+%F %T') run start [extract:$EXTRACT_ARGS] [distill:$LIMIT_ARG]"
  # shellcheck disable=SC2086
  python3 "$DIR/extract.py" $EXTRACT_ARGS 2>&1
  # shellcheck disable=SC2086
  python3 "$DIR/distill.py" $LIMIT_ARG 2>&1
  echo "$(date '+%F %T') run end"
} >> "$LOG" 2>&1
