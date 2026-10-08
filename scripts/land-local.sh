#!/bin/bash
# Land a LOCAL Claude session's edits on main from the Stop / SessionEnd hook, so nothing on a
# machine is ever more than one turn away from the repo. Cloud containers use cloud-land.sh; this
# script exits at once inside one, and in the template repository itself. macOS /bin/bash 3.2.
#
# Rules: ff-only pull first; add -A honoring .gitignore (never -f, so the credentials file never
# lands); commit; push; on a rejected push rebase once (Markdown union-merges via .gitattributes);
# on any conflict abort the rebase, keep the local commit, leave the working tree untouched, log,
# and let the next Stop retry. Never force, never reset --hard. 60 s throttle (--final bypasses).
# Single-flight lock. Never prints to stdout. landing_health.py reads the log at session start.
STATE_DEFAULT_ROOT="$HOME/.claude-land"
THROTTLE_SECS=60
FINAL=0; [ "${1:-}" = "--final" ] && FINAL=1

# Session id: hook stdin JSON first (local hooks often have no env var), then the env var, then "local".
HOOK_JSON=$(cat 2>/dev/null || true)
SID=$(printf '%s' "$HOOK_JSON" | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("session_id","") or "")
except Exception: print("")' 2>/dev/null)
[ -z "$SID" ] && SID="${CLAUDE_CODE_SESSION_ID:-local}"

if [ -n "$LAND_LOCAL_FORCE_CLOUD" ]; then exit 0; fi
if [ -z "$LAND_LOCAL_FORCE_LOCAL" ] && [ "$HOME" = "/root" ] && [ -d /home/user ]; then exit 0; fi

REPO="${LAND_LOCAL_REPO:-${CLAUDE_PROJECT_DIR:-$PWD}}"
cd "$REPO" 2>/dev/null || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
mkdir -p "$REPO/_generated" 2>/dev/null
LOG="$REPO/_generated/landing.log"
log() { printf '%s %s\n' "$(date '+%F %T')" "$*" >> "$LOG" 2>/dev/null; }

ORIGIN=$(git remote get-url origin 2>/dev/null) || { log "no origin remote; nothing to land"; exit 0; }

# Template check: the origin's "owner/repo" path must equal a template path exactly (case-insensitive,
# optional .git suffix and trailing slash, https or scp-style). A lookalike such as ClaudeCodeSystem-Foo is not the template.
O=$(printf '%s' "$ORIGIN" | tr 'A-Z' 'a-z')
O="${O%/}"; O="${O%.git}"; O="${O%/}"
O_REPO="${O##*[/:]}"
O_REST="${O%[/:]*}"
O_OWNER="${O_REST##*[/:]}"
case "$O_OWNER/$O_REPO" in
  integralorg/claudecodesystem|integralorg/claudecodesystem-cloud|stackdev223/claudecodesystem)
    log "origin is the template repository; landing disabled"; exit 0 ;;
esac

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null); [ "$BRANCH" = "main" ] || { log "on branch $BRANCH, not main; skipped"; exit 0; }

if [ -n "$LAND_LOCAL_STATE" ]; then STATE="$LAND_LOCAL_STATE"; else
  KEY=$(printf '%s' "$REPO" | shasum 2>/dev/null | cut -c1-12); STATE="$STATE_DEFAULT_ROOT/${KEY:-default}"; fi
mkdir -p "$STATE" 2>/dev/null
STAMP="$STATE/last-run"
if [ "$FINAL" -eq 0 ] && [ -f "$STAMP" ]; then
  age=$(( $(date +%s) - $(stat -f %m "$STAMP" 2>/dev/null || stat -c %Y "$STAMP" 2>/dev/null || echo 0) ))
  [ "$age" -lt "$THROTTLE_SECS" ] && { log "throttled (${age}s since last run)"; exit 0; }
fi
if ! mkdir "$STATE/lock" 2>/dev/null; then log "locked: another landing is running"; exit 0; fi
trap 'rmdir "$STATE/lock" 2>/dev/null' EXIT
touch "$STAMP"

SID8=$(printf '%s' "$SID" | cut -c1-8)
git fetch -q origin main 2>>"$LOG" || { log "fetch failed"; exit 0; }

# 1. Bring in other machines' work. ff-only refuses when dirty files overlap or local commits exist; we never revert.
if ! git merge --ff-only -q origin/main 2>>"$LOG"; then
  log "cannot fast-forward now (overlapping dirty files or local commits); continuing"
fi

# 2. Stage everything .gitignore allows and commit.
git add -A 2>>"$LOG"
if git diff --cached --quiet; then
  log "nothing to land"
else
  N=$(git diff --cached --name-only | wc -l | tr -d ' ')
  git -c user.name="${LAND_LOCAL_GIT_NAME:-$(git config user.name || echo claude-land)}" \
      -c user.email="${LAND_LOCAL_GIT_EMAIL:-$(git config user.email || echo claude-land@localhost)}" \
      commit -q -m "Session ${SID8}: land ${N} file(s) (hook)" 2>>"$LOG" || { log "commit failed"; exit 0; }
fi
[ "$(git rev-list --count origin/main..HEAD)" -gt 0 ] || { log "nothing to push"; exit 0; }

# 3. Push; on rejection rebase once and push again; a conflict aborts and keeps the local commit.
for i in 1 2 3; do
  if git push -q origin main 2>>"$LOG"; then log "landed on main (attempt $i)"; exit 0; fi
  git fetch -q origin main 2>>"$LOG"
  if ! git rebase -q origin/main 2>>"$LOG"; then
    git rebase --abort 2>/dev/null
    log "conflict with origin/main; rebase aborted, working tree untouched, will retry next time"
    exit 0
  fi
done
log "push failed after 3 attempts"
exit 0
