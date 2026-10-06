#!/bin/bash
# System Journal, cloud edition. Runs INSIDE an Anthropic cloud container as a Claude Code
# hook (Stop + SessionEnd, see .claude/settings.json) and does exactly what the Mac does:
# extract the container's own transcript, distill it with `claude -p`, and land ONE file
# per session at _generated/system-journal/cloud/<date>.<sid8>.json on the vault's main branch.
#
# Deterministic: it is a hook, not an instruction to the agent, so it does not depend on
# the agent remembering, and hooks never hit the permission classifier.
#
# Safety:
#  - Exits immediately unless it is running in a cloud container (HOME=/root, /home/user
#    exists, CLAUDE_CODE_SESSION_ID set). It never runs on a Mac, so no local git.
#  - Never touches the agent's branch. Commits the journal file on a throwaway worktree
#    of origin/main and fast-forward pushes; retries on a push race; gives up quietly.
#  - Throttle is 60s, only to absorb rapid-fire turns (~$0.09 per re-distill). PROVEN
#    2026-09-17: SessionEnd does NOT fire on idle-timeout teardown of a cloud container
#    (a turn skipped by a 15-min throttle was lost until the session was resumed), so
#    the Stop hook is the only reliable path in the cloud and any longer throttle drops
#    the final turns of an abandoned session. --final (SessionEnd) still bypasses the
#    throttle for explicit ends. Resume gets a fresh container but keeps the session id,
#    so the journal file is replaced, not duplicated.
#  - Always exits 0 and never prints to stdout, so it can never block or steer the agent.
LOGDIR="/root/.system-journal"
LOG="$LOGDIR/hook.log"
STAMP="$LOGDIR/last-run"
THROTTLE_SECS=60            # evidence write + landing, absorbs rapid-fire turns
DISTILL_THROTTLE_SECS=900   # the paid journal line, at most every 15 min (always on --final)

[ -n "$CLAUDE_CODE_SESSION_ID" ] || exit 0
[ "$HOME" = "/root" ] && [ -d /home/user ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0
command -v claude >/dev/null 2>&1 || exit 0

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLOUD_DIR="$REPO/_generated/system-journal/cloud"
EVIDENCE_DIR="$REPO/_generated/system-journal/evidence"
mkdir -p "$LOGDIR" "$CLOUD_DIR" "$EVIDENCE_DIR"

FINAL=0
[ "${1:-}" = "--final" ] && FINAL=1
if [ "$FINAL" -eq 0 ] && [ -f "$STAMP" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$STAMP" 2>/dev/null || echo 0) ))
  [ "$age" -lt "$THROTTLE_SECS" ] && exit 0
fi
touch "$STAMP"

# Drain stdin (hook JSON) so the parent never blocks on a full pipe.
cat >/dev/null 2>&1 || true

{
  echo "$(date -u '+%FT%TZ') cloud-journal start final=$FINAL sid=$CLAUDE_CODE_SESSION_ID"
  # Evidence on EVERY (throttled) Stop: deterministic, no model call, so a container torn
  # down on idle timeout has lost at most one throttle interval of the record. The
  # container is the only place this transcript ever exists (no 30-day window in the
  # cloud), so this write is the durable copy.
  python3 "$REPO/scripts/system-journal/extract.py" --vault "$REPO" --idle-min 0 --session "$CLAUDE_CODE_SESSION_ID" 2>&1
  # The journal line costs a model call, so distill at most every DISTILL_THROTTLE_SECS
  # (and always on --final). The evidence file above is what makes the line re-derivable.
  DSTAMP="$LOGDIR/last-distill"
  do_distill=1
  if [ "$FINAL" -eq 0 ] && [ -f "$DSTAMP" ]; then
    dage=$(( $(date +%s) - $(stat -c %Y "$DSTAMP" 2>/dev/null || echo 0) ))
    [ "$dage" -lt "$DISTILL_THROTTLE_SECS" ] && do_distill=0
  fi
  if [ "$do_distill" -eq 1 ]; then
    touch "$DSTAMP"
    python3 "$REPO/scripts/system-journal/distill.py" --vault "$REPO" --cloud-dir "$CLOUD_DIR" --workers 2 --no-audit 2>&1
  else
    echo "distill throttled (evidence written)"
  fi

  cd "$REPO" || exit 0
  # Anything new or changed under cloud/ or evidence/? (both are gitignored by the
  # default-deny .gitignore, so compare against origin/main by content, not git status.)
  git fetch -q origin main 2>&1 || { echo "fetch failed"; exit 0; }
  changed=0
  for f in "$CLOUD_DIR"/*.json "$EVIDENCE_DIR"/*/*.json; do
    [ -f "$f" ] || continue
    rel="${f#$REPO/}"
    if ! git cat-file -e "origin/main:$rel" 2>/dev/null || ! git show "origin/main:$rel" 2>/dev/null | cmp -s - "$f"; then
      changed=1; break
    fi
  done
  if [ "$changed" -eq 0 ]; then echo "nothing new to land"; exit 0; fi

  # Landing identity. Prefer the env overrides, then whatever git identity the repo/container
  # already has, then a neutral placeholder so the commit never fails for lack of an identity.
  GIT_NAME="${SYSTEM_JOURNAL_GIT_NAME:-$(git config user.name 2>/dev/null)}"
  GIT_EMAIL="${SYSTEM_JOURNAL_GIT_EMAIL:-$(git config user.email 2>/dev/null)}"
  git config user.name "${GIT_NAME:-system-journal-bot}"
  git config user.email "${GIT_EMAIL:-system-journal-bot@users.noreply.github.com}"
  for i in 1 2 3; do
    git fetch -q origin main 2>&1
    TMP=$(mktemp -d /tmp/sj-wt.XXXXXX)
    rmdir "$TMP"
    if git worktree add -q --detach "$TMP" origin/main 2>&1; then
      mkdir -p "$TMP/_generated/system-journal/cloud" "$TMP/_generated/system-journal/evidence"
      cp "$CLOUD_DIR"/*.json "$TMP/_generated/system-journal/cloud/" 2>/dev/null
      for m in "$EVIDENCE_DIR"/*/; do
        [ -d "$m" ] || continue
        mkdir -p "$TMP/_generated/system-journal/evidence/$(basename "$m")"
        cp "$m"*.json "$TMP/_generated/system-journal/evidence/$(basename "$m")/" 2>/dev/null
      done
      if (cd "$TMP" && git add -f _generated/system-journal/cloud _generated/system-journal/evidence && git commit -q -m "System Journal: cloud session ${CLAUDE_CODE_SESSION_ID} (hook)" && git push -q origin HEAD:main) 2>&1; then
        echo "landed on main (attempt $i)"
        git worktree remove --force "$TMP" 2>/dev/null
        break
      fi
      git worktree remove --force "$TMP" 2>/dev/null
    fi
    echo "land attempt $i failed; retrying"
    sleep $((i * 3))
  done
  echo "$(date -u '+%FT%TZ') cloud-journal end"
} >> "$LOG" 2>&1

exit 0
