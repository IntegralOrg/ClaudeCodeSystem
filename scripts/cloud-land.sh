#!/bin/bash
# cloud-land.sh: land a cloud session's vault edits on the repo's main branch, deterministically.
# Local sessions land through land-local.sh; this script is cloud-only.
#
# Runs INSIDE an Anthropic cloud container as a Claude Code hook (SessionStart --start, Stop,
# SessionEnd --final; see .claude/settings.json). It replaces every "commit via the cloud git
# flow" step that would otherwise live in a scheduled command. Those steps have the agent run
# git add/commit/fetch/push in Bash, which the cloud permission classifier can flag, so an
# unattended run stalls on a permission prompt. Hooks never hit the classifier, so the landing
# lives here and the agent never runs git at all.
#
# What it does:
#  0. `--start` (SessionStart hook): snapshots the working tree as a git tree object BEFORE the
#     agent does anything and remembers its id. That snapshot, not git history, defines "what
#     the session changed". It also counts how many tracked files already differ from HEAD
#     (a container restored from a stale environment snapshot) and logs it.
#  1. Computes the session's delta: every file that differs between the working tree and the
#     start snapshot. A file the agent never touched is therefore never landed, even when the
#     container's copy of it is older than main (2026-10-13: a 13-second read-only session in a
#     four-day-old container landed 101 deletions and 109 reverts because the delta was taken
#     against the merge-base of HEAD and origin/main instead).
#     Without a start snapshot (the SessionStart hook did not run) it falls back to the
#     merge-base delta with two guards: deletions are refused, and a delta of more than
#     FALLBACK_MAX files is refused entirely. A refusal is recorded as a small JSON marker under
#     _generated/landing/cloud-refusals/ that IS landed, so landing_health.py reports it at the
#     next session start on every machine (the push channel for a silent cloud failure).
#  2. Applies exactly that delta on top of the CURRENT origin/main in a temporary index,
#     writes a tree, commits it with origin/main as parent, and pushes it to main. No
#     worktree checkout, no rebase, no touching the agent's branch. After a landing the start
#     snapshot is re-taken, so a later turn lands only what changed since.
#  3. Retries three times on a push race (re-fetch, re-apply). Gives up quietly and logs.
#
# Safety:
#  - Exits immediately unless it is running in a cloud container (HOME=/root, /home/user
#    exists, CLAUDE_CODE_SESSION_ID set) in a git work tree with an `origin` remote. It never
#    runs on a local machine, so it never races a local file sync that owns the vault there.
#  - Excludes secrets and junk from the landing: .env*, *.pem/*.key/*.p8, Attachments/,
#    files over 50 MB, worktrees, browser debug dirs, caches.
#    _generated/system-journal/cloud/ is left to cloud-journal.sh so the two hooks never
#    race on a half-written distill file.
#  - Never force-pushes. Always exits 0 and never prints to stdout, so it can never block
#    or steer the agent.
LOGDIR="/root/.cloud-land"
LOG="$LOGDIR/hook.log"
MAX_BYTES=52428800
FALLBACK_MAX=25          # without a start snapshot, a delta larger than this is refused entirely
REFUSAL_DIR="_generated/landing/cloud-refusals"

[ -n "$CLAUDE_CODE_SESSION_ID" ] || exit 0
if [ -z "$CLOUD_LAND_TEST_DIR" ]; then
  # Cloud container only. Never runs on a local machine.
  [ "$HOME" = "/root" ] && [ -d /home/user ] || exit 0
else
  # Local self-test against a throwaway repo.
  LOGDIR="$CLOUD_LAND_TEST_DIR/.cloud-land"; LOG="$LOGDIR/hook.log"
fi
command -v git >/dev/null 2>&1 || exit 0

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
# Must have an `origin` remote to push to. (Set SYSTEM_JOURNAL_ORIGIN_MATCH to a substring to
# restrict landing to a specific vault repo; empty means any origin is accepted.)
ORIGIN_URL="$(git remote get-url origin 2>/dev/null)" || exit 0
[ -n "$ORIGIN_URL" ] || exit 0
case "$ORIGIN_URL" in
  *"${SYSTEM_JOURNAL_ORIGIN_MATCH:-}"*) ;;
  *) exit 0 ;;
esac
mkdir -p "$LOGDIR"
# Template self-protection: the template repository itself must never land from a cloud session
# (settings are committed, so these hooks run there too). Same exact owner/repo match as land-local.sh:
# case-insensitive, optional .git suffix and trailing slash, https or scp-style.
O=$(printf '%s' "$ORIGIN_URL" | tr 'A-Z' 'a-z')
O="${O%/}"; O="${O%.git}"; O="${O%/}"
O_REPO="${O##*[/:]}"
O_REST="${O%[/:]*}"
O_OWNER="${O_REST##*[/:]}"
case "$O_OWNER/$O_REPO" in
  integralorg/claudecodesystem|integralorg/claudecodesystem-cloud|stackdev223/claudecodesystem)
    echo "$(date -u '+%FT%TZ') origin is the template repository; landing disabled" >> "$LOG" 2>&1
    cat >/dev/null 2>&1 || true
    exit 0 ;;
esac

# Drain stdin (hook JSON) so the parent never blocks on a full pipe.
cat >/dev/null 2>&1 || true

FINAL=0; MODE=land
case "${1:-}" in
  --final) FINAL=1 ;;
  --start) MODE=start ;;
esac
START_FILE="$LOGDIR/start-tree"
STALE_FILE="$LOGDIR/start-stale"

# Pathspec exclusions: secrets, caches, and volatile state never get landed.
EXCLUDES=(
  ':(exclude,glob).env' ':(exclude,glob)**/.env' ':(exclude,glob).env.*' ':(exclude,glob)**/.env.*'
  ':(exclude,glob)**/*.pem' ':(exclude,glob)**/*.key' ':(exclude,glob)**/*.p8'
  ':(exclude,glob)**/*.pyc' ':(exclude,glob)**/*.pyo' ':(exclude,glob)**/.DS_Store'
  ':(exclude)Attachments' ':(exclude).claude/worktrees' ':(exclude).playwright-mcp'
  ':(exclude)_generated/system-journal/cloud'
  # The cloud harness appends permission rules it approved at runtime (e.g. Bash(git push *)) to the
  # committed settings.local.json; landing those would widen every future run's permissions silently.
  # Permission changes are deliberate edits only.
  ':(exclude).claude/settings.local.json'
  ':(exclude,glob)**/__pycache__/**' ':(exclude,glob)**/node_modules/**'
  ':(exclude,glob)**/.venv/**' ':(exclude,glob)**/venv/**'
)

# The working tree as a tree object, same exclusions as the landing. Prints the tree id.
snapshot_tree() {
  local idx tree
  idx=$(mktemp /tmp/cl-snap.XXXXXX)
  GIT_INDEX_FILE="$idx" git read-tree --empty 2>/dev/null
  GIT_INDEX_FILE="$idx" git add -f -A -- . "${EXCLUDES[@]}" 2>/dev/null
  tree=$(GIT_INDEX_FILE="$idx" git write-tree 2>/dev/null)
  rm -f "$idx"
  printf '%s' "$tree"
}

# Write the refusal marker (one JSON file per session per day) and print its repo-relative path.
# $1 reason, $2 refused deletions, $3 refused changes, $4 file listing the refused paths (one per line).
write_refusal() {
  local path="$REFUSAL_DIR/$(date -u +%F)-${CLAUDE_CODE_SESSION_ID:0:8}.json"
  mkdir -p "$REPO/$REFUSAL_DIR"
  if command -v python3 >/dev/null 2>&1; then
    CL_REASON="$1" CL_DEL="$2" CL_CHG="$3" CL_LIST="$4" CL_SID="$CLAUDE_CODE_SESSION_ID" CL_STALE="$(cat "$STALE_FILE" 2>/dev/null || echo -1)" \
    python3 - "$REPO/$path" <<'PY' 2>/dev/null
import json, os, sys
from datetime import datetime, timezone
try:
    sample = [l.rstrip("\n") for l in open(os.environ["CL_LIST"], encoding="utf-8", errors="replace")][:20]
except Exception:
    sample = []
rec = {"session_id": os.environ["CL_SID"], "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
       "reason": os.environ["CL_REASON"], "refused_deletions": int(os.environ["CL_DEL"]), "refused_changes": int(os.environ["CL_CHG"]),
       "stale_at_start": int(os.environ["CL_STALE"]), "sample": sample,
       "what_to_do": "These edits from the cloud session are NOT on main. Re-run the routine, or make the change by hand. "
                     "If this keeps happening, the SessionStart hook (cloud-land.sh --start) is not running in the cloud."}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(rec, f, indent=1); f.write("\n")
PY
  else
    printf '{"session_id": "%s", "reason": "%s", "refused_deletions": %s, "refused_changes": %s, "sample": []}\n' \
      "$CLAUDE_CODE_SESSION_ID" "$1" "$2" "$3" > "$REPO/$path"
  fi
  printf '%s' "$path"
}

{
  if [ "$MODE" = "start" ]; then
    echo "$(date -u '+%FT%TZ') cloud-land snapshot sid=$CLAUDE_CODE_SESSION_ID"
  else
    echo "$(date -u '+%FT%TZ') cloud-land start final=$FINAL sid=$CLAUDE_CODE_SESSION_ID"
  fi

  if [ "$MODE" = "start" ]; then
    # 0. Start-of-session snapshot: the only trustworthy definition of "what this session changed".
    # A snapshot is replaced only after a successful landing (below). `/clear` runs SessionStart again
    # in the SAME container, so if the last landing failed (fetch or push), re-snapshotting here would
    # make the unlanded edits look untouched and lose them; a valid existing snapshot is retained.
    START=$(cat "$START_FILE" 2>/dev/null)
    if [ -n "$START" ] && git cat-file -e "$START^{tree}" 2>/dev/null; then
      echo "retaining start snapshot ${START:0:7} (last landing did not replace it)"
      exit 0
    fi
    START=$(snapshot_tree)
    if [ -z "$START" ]; then echo "start snapshot failed"; exit 0; fi
    printf '%s\n' "$START" > "$START_FILE"
    # Tracked files whose container copy already differs from HEAD (deleted or modified) are a stale
    # container, not agent work. Count them so the log explains itself and a refusal can say so.
    stale=$(git diff-tree -r --name-only --diff-filter=DM HEAD "$START" 2>/dev/null | wc -l | tr -d ' ')
    printf '%s\n' "${stale:-0}" > "$STALE_FILE"
    echo "start snapshot ${START:0:7}; stale at start: ${stale:-0} file(s)"
    exit 0
  fi

  git fetch -q origin main 2>&1 || { echo "fetch failed"; exit 0; }

  START=$(cat "$START_FILE" 2>/dev/null)
  if [ -n "$START" ] && git cat-file -e "$START^{tree}" 2>/dev/null; then
    BASE="$START"; HAVE_SNAPSHOT=1
  else
    BASE=$(git merge-base HEAD origin/main 2>/dev/null) || BASE=$(git rev-parse origin/main)
    HAVE_SNAPSHOT=0
    echo "no start snapshot; falling back to merge-base ${BASE:0:7} with deletions refused and a ${FALLBACK_MAX}-file cap"
  fi

  # 1. Session delta: working tree vs BASE, in a scratch index.
  DELTA_IDX=$(mktemp /tmp/cl-delta.XXXXXX)
  GIT_INDEX_FILE="$DELTA_IDX" git read-tree "$BASE" 2>&1
  GIT_INDEX_FILE="$DELTA_IDX" git add -f -A -- . "${EXCLUDES[@]}" 2>&1
  DELTA=$(mktemp /tmp/cl-list.XXXXXX)
  GIT_INDEX_FILE="$DELTA_IDX" git diff-index --cached --name-status -z "$BASE" > "$DELTA" 2>/dev/null
  rm -f "$DELTA_IDX"
  if [ ! -s "$DELTA" ]; then echo "nothing to land"; rm -f "$DELTA"; exit 0; fi

  # Fallback guards (no start snapshot): never delete, never land a large delta.
  if [ "$HAVE_SNAPSHOT" -eq 0 ]; then
    REFUSED=$(mktemp /tmp/cl-refused.XXXXXX)
    KEPT=$(mktemp /tmp/cl-kept.XXXXXX)
    n_total=0; n_rdel=0; n_keep=0; n_rchg=0
    while IFS= read -r -d '' status && IFS= read -r -d '' path; do
      n_total=$((n_total+1))
      if [ "$status" = "D" ]; then
        printf '%s\n' "$path" >> "$REFUSED"; n_rdel=$((n_rdel+1))
      else
        printf '%s\0%s\0' "$status" "$path" >> "$KEPT"; n_keep=$((n_keep+1))
      fi
    done < "$DELTA"
    reason=""
    if [ "$n_total" -gt "$FALLBACK_MAX" ]; then
      reason="delta of $n_total files exceeds $FALLBACK_MAX without a start snapshot (stale container?); nothing landed"
      n_rchg=$n_keep
      while IFS= read -r -d '' status && IFS= read -r -d '' path; do printf '%s\n' "$path" >> "$REFUSED"; done < "$KEPT"
      : > "$KEPT"
    elif [ "$n_rdel" -gt 0 ]; then
      reason="no start snapshot: $n_rdel deletion(s) refused, $n_keep change(s) landed"
    fi
    if [ -n "$reason" ]; then
      echo "refused $n_rdel deletion(s), $n_rchg change(s): $reason"
      marker=$(write_refusal "$reason" "$n_rdel" "$n_rchg" "$REFUSED")
      [ -n "$marker" ] && [ -f "$REPO/$marker" ] && printf 'A\0%s\0' "$marker" >> "$KEPT"
    fi
    mv "$KEPT" "$DELTA"
    rm -f "$REFUSED"
    if [ ! -s "$DELTA" ]; then echo "nothing to land"; rm -f "$DELTA"; exit 0; fi
  fi

  # Landing identity. Prefer env overrides, then whatever git identity the repo/container
  # already has, then a neutral placeholder so the commit never fails for lack of an identity.
  CL_NAME="${SYSTEM_JOURNAL_GIT_NAME:-$(git config user.name 2>/dev/null)}"
  CL_EMAIL="${SYSTEM_JOURNAL_GIT_EMAIL:-$(git config user.email 2>/dev/null)}"
  git config user.name "${CL_NAME:-cloud-land-bot}"
  git config user.email "${CL_EMAIL:-cloud-land-bot@users.noreply.github.com}"

  for i in 1 2 3; do
    git fetch -q origin main 2>&1
    MAIN=$(git rev-parse origin/main)
    LAND_IDX=$(mktemp /tmp/cl-land.XXXXXX)
    GIT_INDEX_FILE="$LAND_IDX" git read-tree "$MAIN" 2>&1

    # 2. Apply the delta on top of current main.
    n_add=0; n_del=0; n_skip=0
    while IFS= read -r -d '' status && IFS= read -r -d '' path; do
      case "$status" in
        D)
          GIT_INDEX_FILE="$LAND_IDX" git rm -q --cached --ignore-unmatch -- "$path" 2>&1 && n_del=$((n_del+1))
          ;;
        *)
          if [ -f "$path" ]; then
            size=$(stat -c %s "$path" 2>/dev/null || echo 0)
            if [ "$size" -gt "$MAX_BYTES" ]; then echo "skip >50M: $path"; n_skip=$((n_skip+1)); continue; fi
            GIT_INDEX_FILE="$LAND_IDX" git add -f -- "$path" 2>&1 && n_add=$((n_add+1))
          fi
          ;;
      esac
    done < "$DELTA"

    TREE=$(GIT_INDEX_FILE="$LAND_IDX" git write-tree 2>/dev/null)
    rm -f "$LAND_IDX"
    if [ -z "$TREE" ]; then echo "write-tree failed"; break; fi
    if [ "$TREE" = "$(git rev-parse "$MAIN^{tree}")" ]; then echo "delta already on main"; break; fi

    # Do NOT fold stderr into COMMIT: on failure that error text would be pushed as a ref and
    # miscounted as a push race. Check the exit status and stop the loop instead.
    COMMIT=$(git commit-tree "$TREE" -p "$MAIN" -m "Cloud session ${CLAUDE_CODE_SESSION_ID:0:8}: land $n_add file(s), $n_del deletion(s) (hook)") || { echo "commit-tree failed"; break; }
    if git push -q origin "$COMMIT:refs/heads/main" 2>&1; then
      echo "landed on main (attempt $i): +$n_add -$n_del skipped=$n_skip commit=${COMMIT:0:7}"
      # Move the local branch pointer so a later turn diffs against what is now on main.
      git update-ref refs/remotes/origin/main "$COMMIT" 2>/dev/null
      # Re-take the start snapshot: the next turn lands only what changes from here, so an edit
      # someone else makes to one of these files on main is not clobbered by a re-landing.
      NEXT=$(snapshot_tree); [ -n "$NEXT" ] && printf '%s\n' "$NEXT" > "$START_FILE"
      break
    fi
    echo "push attempt $i failed; retrying"
    sleep $((i * 3))
  done
  rm -f "$DELTA"
  echo "$(date -u '+%FT%TZ') cloud-land end"
} >> "$LOG" 2>&1

exit 0
