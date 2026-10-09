#!/bin/bash
# Land a LOCAL Claude session's edits on main from the Stop / SessionEnd hook, so nothing on a
# machine is ever more than one turn away from the repo. Cloud containers use cloud-land.sh; this
# script exits at once inside one, and in the template repository itself. macOS /bin/bash 3.2.
#
# Rules: skip while a merge/rebase/cherry-pick/revert is in progress (never commit conflict markers);
# ff-only pull first; add -A honoring .gitignore (never -f, so the credentials file never lands);
# commit; push; on a rejected push rebase once (Markdown union-merges via .gitattributes); on any
# conflict abort the rebase, keep the local commit, leave the working tree untouched, log, and let
# the next Stop retry. Never force, never reset --hard. 60 s throttle (--final bypasses).
# Single-flight lock (a lock older than 10 minutes is stale and removed).
#
# --pull (SessionStart hook): pull-only mode so a session opens on the latest main. Same guards as a
# normal run (cloud, template origin, work tree, branch main, mid-operation, lock), then fetch and
# `merge --ff-only` and nothing else: never commits, pushes, stashes, resets, or touches the working
# tree beyond a clean fast-forward. A refused fast-forward (dirty files overlap, or local commits)
# logs one line and leaves the next landing to reconcile. Ignores and never updates the 60 s throttle stamp.
# Never prints to stdout: every git call's output goes to _generated/landing-git.log, and only
# log() writes _generated/landing.log (timestamped lines). landing_health.py reads that log.
STATE_DEFAULT_ROOT="$HOME/.claude-land"
THROTTLE_SECS=60
STALE_LOCK_SECS=600
LOG_MAX_LINES=4000
LOG_KEEP_LINES=2000
FINAL=0; [ "${1:-}" = "--final" ] && FINAL=1
PULL=0; [ "${1:-}" = "--pull" ] && PULL=1

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
GITLOG="$REPO/_generated/landing-git.log"
# Cap a log file: past LOG_MAX_LINES lines keep the last LOG_KEEP_LINES.
cap_log() {
  local n
  n=$(wc -l < "$1" 2>/dev/null | tr -d ' ')
  if [ "${n:-0}" -gt "$LOG_MAX_LINES" ]; then
    tail -n "$LOG_KEEP_LINES" "$1" > "$REPO/_generated/landing.tmp.log" 2>/dev/null \
      && mv "$REPO/_generated/landing.tmp.log" "$1" 2>/dev/null
  fi
}
cap_log "$GITLOG"   # raw git output is capped the same way, once per run before this run appends to it
log() {
  printf '%s %s\n' "$(date '+%F %T')" "$*" >> "$LOG" 2>/dev/null
  cap_log "$LOG"
}
# File mtime in epoch seconds; empty when it cannot be read. GNU stat first (BSD stat rejects -c).
mtime_of() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null; }

ORIGIN=$(git remote get-url origin 2>>"$GITLOG") || { log "no origin remote; nothing to land"; exit 0; }

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

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>>"$GITLOG"); [ "$BRANCH" = "main" ] || { log "on branch $BRANCH, not main; skipped"; exit 0; }

if [ -n "$LAND_LOCAL_STATE" ]; then STATE="$LAND_LOCAL_STATE"; else
  KEY=$(printf '%s' "$REPO" | shasum 2>/dev/null | cut -c1-12); STATE="$STATE_DEFAULT_ROOT/${KEY:-default}"; fi
mkdir -p "$STATE" 2>/dev/null
STAMP="$STATE/last-run"
if [ "$FINAL" -eq 0 ] && [ "$PULL" -eq 0 ] && [ -f "$STAMP" ]; then
  age=$(( $(date +%s) - $(mtime_of "$STAMP" || echo 0) ))
  [ "$age" -lt "$THROTTLE_SECS" ] && { log "throttled (${age}s since last run)"; exit 0; }
fi
if ! mkdir "$STATE/lock" 2>/dev/null; then
  lock_mtime=$(mtime_of "$STATE/lock")
  if [ -n "$lock_mtime" ] && [ $(( $(date +%s) - lock_mtime )) -gt "$STALE_LOCK_SECS" ] \
     && rmdir "$STATE/lock" 2>/dev/null && mkdir "$STATE/lock" 2>/dev/null; then
    log "stale lock removed"
  else
    log "locked: another landing is running"; exit 0
  fi
fi
trap 'rmdir "$STATE/lock" 2>/dev/null' EXIT
[ "$PULL" -eq 1 ] || touch "$STAMP"

# Never commit while an operation is half done: conflict markers would land on main.
GITDIR=$(git rev-parse --git-dir 2>>"$GITLOG")
midop=0
for f in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply; do
  [ -e "$GITDIR/$f" ] && midop=1
done
[ -n "$(git ls-files -u 2>>"$GITLOG")" ] && midop=1
if [ "$midop" -eq 1 ]; then log "skipped: repository is mid-merge/rebase/cherry-pick/revert"; exit 0; fi

SID8=$(printf '%s' "$SID" | cut -c1-8)
git fetch -q origin main >>"$GITLOG" 2>&1 || { log "fetch failed"; exit 0; }

# --pull: fast-forward only, then stop (see the header).
if [ "$PULL" -eq 1 ]; then
  BEFORE=$(git rev-parse HEAD 2>>"$GITLOG")
  if git merge --ff-only -q origin/main >>"$GITLOG" 2>&1; then
    N=$(git rev-list --count "$BEFORE..HEAD" 2>>"$GITLOG" || echo 0)
    if [ "${N:-0}" -gt 0 ]; then log "pull: fast-forwarded $N commit(s)"; else log "pull: up to date"; fi
  else
    if [ "$(git rev-list --count origin/main..HEAD 2>>"$GITLOG")" -gt 0 ]; then WHY="local commits not on main"
    else WHY="unsaved edits overlap incoming changes"; fi
    log "pull: cannot fast-forward now ($WHY); the next landing reconciles"
  fi
  exit 0
fi

# 1. Bring in other machines' work. ff-only refuses when dirty files overlap or local commits exist; we never revert.
if ! git merge --ff-only -q origin/main >>"$GITLOG" 2>&1; then
  log "cannot fast-forward now (overlapping dirty files or local commits); continuing"
fi

# 2. Stage everything .gitignore allows (the landing logs never land, even if a repo forgot to ignore them) and commit.
# Credential-shaped files are excluded explicitly too (the way cloud-land.sh does), so a client repo whose
# ignore file was edited still never lands them.
git add -A -- . ':(exclude)_generated/landing.log' ':(exclude)_generated/landing-git.log' ':(exclude)_generated/landing.tmp.log' \
  ':(exclude,glob).env' ':(exclude,glob)**/.env' ':(exclude,glob).env.*' ':(exclude,glob)**/.env.*' \
  ':(exclude,glob)**/*.pem' ':(exclude,glob)**/*.key' ':(exclude,glob)**/*.p8' >>"$GITLOG" 2>&1
if git diff --cached --quiet >>"$GITLOG" 2>&1; then
  log "nothing to land"
else
  N=$(git diff --cached --name-only 2>>"$GITLOG" | wc -l | tr -d ' ')
  git -c user.name="${LAND_LOCAL_GIT_NAME:-$(git config user.name 2>>"$GITLOG" || echo claude-land)}" \
      -c user.email="${LAND_LOCAL_GIT_EMAIL:-$(git config user.email 2>>"$GITLOG" || echo claude-land@localhost)}" \
      commit -q -m "Session ${SID8}: land ${N} file(s) (hook)" >>"$GITLOG" 2>&1 || { log "commit failed"; exit 0; }
fi
[ "$(git rev-list --count origin/main..HEAD 2>>"$GITLOG")" -gt 0 ] || { log "nothing to push"; exit 0; }

# 3. Push; on rejection rebase once and push again; a conflict aborts and keeps the local commit.
for i in 1 2 3; do
  if git push -q origin main >>"$GITLOG" 2>&1; then log "landed on main (attempt $i)"; exit 0; fi
  git fetch -q origin main >>"$GITLOG" 2>&1
  if ! git rebase -q origin/main >>"$GITLOG" 2>&1; then
    git rebase --abort >>"$GITLOG" 2>&1
    log "conflict with origin/main; rebase aborted, working tree untouched, will retry next time"
    exit 0
  fi
done
log "push failed after 3 attempts"
exit 0
