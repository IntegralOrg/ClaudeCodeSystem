#!/bin/bash
# Copy the System Journal scripts from the vault to ~/scripts/system-journal/ (a plain local
# executable location; macOS can block direct execution of files synced from a cloud folder
# like iCloud Drive or Dropbox). Re-run after editing anything in scripts/system-journal/.
#
# Usage:
#   install.sh                       copy the scripts and print the hook lines (default)
#   install.sh --vault <path>        also record the vault in ~/.system-journal/config.json (merge-only)
#   install.sh --write-hooks         also merge the three hooks into ~/.claude/settings.json
#                                    (only if an identical command is not already present)
#   install.sh --settings <path>     with --write-hooks: target this settings.json instead
#                                    (for testing against a copy; default ~/.claude/settings.json)
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DST="$HOME/scripts/system-journal"

WRITE_HOOKS=0
VAULT_PATH=""
SETTINGS="$HOME/.claude/settings.json"
while [ $# -gt 0 ]; do
  case "$1" in
    --write-hooks) WRITE_HOOKS=1 ;;
    --vault) VAULT_PATH="$2"; shift ;;
    --settings) SETTINGS="$2"; shift ;;
    *) echo "install.sh: unknown argument '$1'" >&2; exit 2 ;;
  esac
  shift
done

mkdir -p "$DST"
cp "$SRC/extract.py" "$SRC/distill.py" "$SRC/run.sh" "$SRC/themes-inject.py" "$DST/"
chmod +x "$DST/run.sh" "$DST/extract.py" "$DST/distill.py" "$DST/themes-inject.py"
xattr -d com.apple.provenance "$DST"/* 2>/dev/null || true
echo "installed to $DST"

# --vault: record the vault path so the scripts resolve it without an env var.
if [ -n "$VAULT_PATH" ]; then
  python3 - "$VAULT_PATH" <<'PY'
import json, os, sys
vault = os.path.abspath(os.path.expanduser(sys.argv[1]))
cfg_dir = os.path.join(os.path.expanduser("~"), ".system-journal")
os.makedirs(cfg_dir, exist_ok=True)
cfg_path = os.path.join(cfg_dir, "config.json")
try:
    with open(cfg_path) as f:
        cfg = json.load(f)
    if not isinstance(cfg, dict):
        cfg = {}
except (OSError, ValueError):
    cfg = {}
cfg["vault"] = vault
tmp = cfg_path + ".tmp"
with open(tmp, "w") as f:
    json.dump(cfg, f, indent=2)
os.replace(tmp, cfg_path)
print(f"recorded vault in {cfg_path}: {vault}")
PY
fi

# --write-hooks: merge our three hooks into settings.json, skipping any that already exist.
if [ "$WRITE_HOOKS" -eq 1 ]; then
  python3 - "$SETTINGS" "$DST" <<'PY'
import json, os, sys
settings_path, dst = sys.argv[1], sys.argv[2]
# (event, matcher-or-None, command, timeout)
wanted = [
    ("Stop",         None,                       f"bash {dst}/run.sh --stop-hook",       30),
    ("SessionEnd",   None,                       f"bash {dst}/run.sh --hook",            10),
    ("SessionStart", "startup|resume|clear|compact", f"python3 {dst}/themes-inject.py", 10),
]
try:
    with open(settings_path) as f:
        settings = json.load(f)
    if not isinstance(settings, dict):
        settings = {}
except (OSError, ValueError):
    settings = {}
hooks = settings.setdefault("hooks", {})
added = []
for event, matcher, command, timeout in wanted:
    groups = hooks.setdefault(event, [])
    present = any(
        isinstance(h, dict) and h.get("command") == command
        for g in groups if isinstance(g, dict)
        for h in (g.get("hooks") or [])
    )
    if present:
        continue
    group = {"hooks": [{"type": "command", "command": command, "timeout": timeout}]}
    if matcher:
        group["matcher"] = matcher
    groups.append(group)
    added.append(f"{event}: {command}")
if added:
    os.makedirs(os.path.dirname(os.path.abspath(settings_path)), exist_ok=True)
    tmp = settings_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(settings, f, indent=2)
    os.replace(tmp, settings_path)
    print(f"wrote {len(added)} hook(s) to {settings_path}:")
    for a in added:
        print(f"  + {a}")
else:
    print(f"no hooks added to {settings_path} (all three already present)")
PY
  exit 0
fi

echo "SessionEnd hook command (lives in ~/.claude/settings.json, user-level, so it fires for every session on this Mac):"
echo "  bash $DST/run.sh --hook"
echo "Stop hook command (same file; extracts the live session, throttled):"
echo "  bash $DST/run.sh --stop-hook"
echo "SessionStart hook command (same file; injects cwd-matched Themes into non-vault sessions):"
echo "  python3 $DST/themes-inject.py"
echo "(run with --write-hooks to merge these into ~/.claude/settings.json automatically)"
