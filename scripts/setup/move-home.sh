#!/bin/bash
# Move a freshly downloaded vault to its home, make it a Git repository, and open it in Claude.
# Runs in the first session on a clean Mac, before Python exists: /bin/bash 3.2 and built-in tools only.
# Every step checks first, so a rerun after a crash resumes.
#
# Usage: move-home.sh --name "Owner Name" --email owner@example.com [--dest DIR] [--no-open]
# Stdout: one line per outcome, first token stable. Exit: 0 ok (HOME_READY + OPEN_URL, or ALREADY_HOME);
# 2 USAGE; 3 DEST_NOT_EMPTY; 4 SYNCED_PATH; 5 NOT_A_DOWNLOAD; 6 GIT_MISSING; 7 COPY_FAILED; 8 GIT_FAILED.
set -u
SRC="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="$HOME/Brain"; NAME=""; EMAIL=""; OPEN=1
while [ $# -gt 0 ]; do
  case "$1" in
    --dest) DEST="${2:-}"; shift 2 || { echo "USAGE: --dest needs a folder"; exit 2; } ;;
    --name) NAME="${2:-}"; shift 2 || { echo "USAGE: --name needs a value"; exit 2; } ;;
    --email) EMAIL="${2:-}"; shift 2 || { echo "USAGE: --email needs a value"; exit 2; } ;;
    --no-open) OPEN=0; shift ;;
    *) echo "USAGE: unknown argument $1"; exit 2 ;;
  esac
done
[ -n "$NAME" ] && [ -n "$EMAIL" ] || { echo "USAGE: --name and --email are required"; exit 2; }
# A quoted ~ or a relative path would otherwise land inside the download (the session's folder) and copy it into itself.
case "$DEST" in
  "~") DEST="$HOME" ;;
  "~/"*) DEST="$HOME/${DEST#\~/}" ;;
  /*) ;;
  *) DEST="$HOME/$DEST" ;;
esac
DEST="${DEST%/}"
case "$DEST/" in
  "$SRC/"?*) echo "USAGE: $DEST is inside the downloaded folder; choose a folder outside it"; exit 2 ;;
esac

urlencode() {
  local LC_ALL=C s="$1" out="" c i
  for ((i = 0; i < ${#s}; i++)); do
    c="${s:i:1}"
    case "$c" in
      [a-zA-Z0-9.~_-]) out="$out$c" ;;
      *) out="$out$(printf '%%%02X' "'$c")" ;;
    esac
  done
  printf '%s' "$out"
}

open_url() {
  URL="claude://code/new?folder=$(urlencode "$DEST")&q=$(urlencode "Continue setup")"
  echo "OPEN_URL $URL"
  if [ "$OPEN" = 1 ]; then
    if command -v open >/dev/null 2>&1; then open "$URL"; else xdg-open "$URL" >/dev/null 2>&1 || true; fi
  fi
}

if [ -d "$DEST" ] && [ "$(cd "$DEST" && pwd)" = "$SRC" ]; then echo "ALREADY_HOME $DEST"; exit 0; fi
[ -f "$SRC/SETUP_PENDING" ] || { echo "NOT_A_DOWNLOAD: $SRC has no SETUP_PENDING marker"; exit 5; }
case "$DEST/" in
  *"/Library/Mobile Documents/"*|*"/Library/CloudStorage/"*|*"/iCloud Drive/"*|*"/OneDrive"*|*"/Dropbox/"*|*"/Google Drive/"*|"$HOME/Documents/"*|"$HOME/Desktop/"*)
    echo "SYNCED_PATH: $DEST is inside a folder that syncs to the cloud"; exit 4 ;;
esac
if [ "$(uname)" = "Darwin" ] && ! xcode-select -p >/dev/null 2>&1; then
  echo "GIT_MISSING: the command line tools are not installed yet"; exit 6
fi
command -v git >/dev/null 2>&1 || { echo "GIT_MISSING: git is not installed"; exit 6; }

if [ ! -f "$DEST/SETUP_PENDING" ]; then
  if [ -d "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then
    echo "DEST_NOT_EMPTY: $DEST already has files in it"; exit 3
  fi
  mkdir -p "$DEST" || { echo "COPY_FAILED: could not create $DEST"; exit 7; }
fi
# The first commit happens only after a full copy, so a home with a commit is finished: never copy over it again
# (that would undo what Part B changed). Otherwise copy the marker first, so a crash midway can be resumed.
if ! { [ -d "$DEST/.git" ] && git -C "$DEST" rev-parse -q --verify HEAD >/dev/null 2>&1; }; then
  cp "$SRC/SETUP_PENDING" "$DEST/SETUP_PENDING" || { echo "COPY_FAILED: copying into $DEST failed"; exit 7; }
  # SRC/. copies hidden files too; a resumed copy simply rewrites the same bytes.
  cp -R "$SRC/." "$DEST/" || { echo "COPY_FAILED: copying into $DEST failed"; exit 7; }
  command -v xattr >/dev/null 2>&1 && xattr -dr com.apple.quarantine "$DEST" 2>/dev/null
fi

cd "$DEST" || { echo "COPY_FAILED: cannot enter $DEST"; exit 7; }
if [ ! -d .git ]; then
  { git init -q -b main 2>/dev/null || { git init -q && git symbolic-ref HEAD refs/heads/main; }; } \
    || { echo "GIT_FAILED: git init failed"; exit 8; }
fi
{ git config user.name "$NAME" && git config user.email "$EMAIL"; } || { echo "GIT_FAILED: git config failed"; exit 8; }
if ! git rev-parse -q --verify HEAD >/dev/null 2>&1; then
  { git add -A && git commit -q -m "Start my Brain" >/dev/null; } || { echo "GIT_FAILED: first commit failed"; exit 8; }
fi
echo "HOME_READY $DEST"
open_url
exit 0
