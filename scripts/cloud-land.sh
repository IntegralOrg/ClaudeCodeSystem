#!/bin/bash
# cloud-land.sh: land a cloud session's vault edits on the repo's main branch, deterministically.
#
# Runs INSIDE an Anthropic cloud container as a Claude Code hook (Stop + SessionEnd, see
# .claude/settings.json). It replaces every "commit via the cloud git flow" step that would
# otherwise live in a scheduled command. Those steps have the agent run git add/commit/fetch/
# push in Bash, which the cloud permission classifier can flag, so an unattended run stalls on
# a permission prompt. Hooks never hit the classifier, so the landing lives here and the agent
# never runs git at all.
#
# What it does:
#  1. Computes the session's delta: every file that differs between the working tree and
#     the merge-base of HEAD and origin/main (so commits the agent made on a claude/... branch
#     are included, and files that moved on main since the clone are NOT reverted).
#  2. Applies exactly that delta on top of the CURRENT origin/main in a temporary index,
#     writes a tree, commits it with origin/main as parent, and pushes it to main. No
#     worktree checkout, no rebase, no touching the agent's branch.
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

# Drain stdin (hook JSON) so the parent never blocks on a full pipe.
cat >/dev/null 2>&1 || true

FINAL=0
[ "${1:-}" = "--final" ] && FINAL=1

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

{
  echo "$(date -u '+%FT%TZ') cloud-land start final=$FINAL sid=$CLAUDE_CODE_SESSION_ID"

  git fetch -q origin main 2>&1 || { echo "fetch failed"; exit 0; }
  BASE=$(git merge-base HEAD origin/main 2>/dev/null) || BASE=$(git rev-parse origin/main)

  # 1. Session delta: working tree vs BASE, in a scratch index.
  DELTA_IDX=$(mktemp /tmp/cl-delta.XXXXXX)
  GIT_INDEX_FILE="$DELTA_IDX" git read-tree "$BASE" 2>&1
  GIT_INDEX_FILE="$DELTA_IDX" git add -f -A -- . "${EXCLUDES[@]}" 2>&1
  DELTA=$(mktemp /tmp/cl-list.XXXXXX)
  GIT_INDEX_FILE="$DELTA_IDX" git diff-index --cached --name-status -z "$BASE" > "$DELTA" 2>/dev/null
  rm -f "$DELTA_IDX"
  if [ ! -s "$DELTA" ]; then echo "nothing to land"; rm -f "$DELTA"; exit 0; fi

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
      break
    fi
    echo "push attempt $i failed; retrying"
    sleep $((i * 3))
  done
  rm -f "$DELTA"
  echo "$(date -u '+%FT%TZ') cloud-land end"
} >> "$LOG" 2>&1

exit 0
