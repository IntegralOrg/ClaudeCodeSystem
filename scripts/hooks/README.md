# Claude Code hooks

Stdlib-only Python 3 (3.11+). Each hook reads the Claude Code JSON payload on stdin and fails OPEN: any unexpected error exits 0.

| Hook | Event | Job |
|------|-------|-----|
| `guard_secrets.py` | PreToolUse | Blocks credential files, env dumps, naming `.env`, destructive commands |
| `log_tool_use.py` | PostToolUse, PostToolUseFailure | Appends one masked JSONL row per call to `_generated/agent-actions/` |
| `guard_state_writes.py` | PreToolUse (Edit, Write, MultiEdit) | Keeps `## Current State` / `## Log` structure in state-bearing files |
| `guard_vault_path.py` | SessionStart | Warns when the vault is inside a synced folder (iCloud, OneDrive, Dropbox, Google Drive) |
| `setup_pending.py` | SessionStart | Starts setup while SETUP_PENDING exists (silent in the template repo) |
| `landing_health.py` | SessionStart | Reports repeated local landing failures from `_generated/landing.log` (silent when the last attempt succeeded) |
| `routine_health.py` | SessionStart | Connector-free push channel: names a routine that is stale (no recent daily note or audit-log heading) or still not live after setup. Silent when healthy and in the template repo |
| `session_context.py` | SessionStart | Injects branch, uncommitted count, recent commits, newest handoff |

Besides the hooks, `.claude/settings.json` carries native `permissions.deny` rules for the credentials file (`Read(./.env)`, `Read(./.env.*)` and the `./**/` forms), so the file stays unreadable by Claude Code's own Read tool even on a computer where Python is missing and every hook is silently absent. `test_repo_layout.py` asserts the list.

`_common.py` holds the shared helpers (`read_payload`, `project_dir`, `block`, `allow`, `run`, `is_template_repo`).

`../land-local.sh` is not a hook script but runs from the `Stop` and `SessionEnd` hooks (`--final`): it lands a local session's edits on `main` (cloud sessions use `../cloud-land.sh`), never forces, never discards the local commit, skips while a merge, rebase, cherry-pick or revert is in progress, removes a lock older than 10 minutes, and prints nothing: its own log is `_generated/landing.log` (timestamped lines only, capped at 2000 lines once past 4000), raw git output goes to `_generated/landing-git.log`. `landing_health.py` reads the first and also reports when landing keeps being skipped (locked or on another branch). Override env vars: `LAND_LOCAL_REPO`, `LAND_LOCAL_STATE`, `LAND_LOCAL_FORCE_LOCAL`, `LAND_LOCAL_FORCE_CLOUD`. `routine_health.py` honors `ROUTINE_HEALTH_TODAY=YYYY-MM-DD` for tests. It reads `System/Routines.md` as one `## <title>` section per routine (the `title:` of `System/routines/*.md`; numbering, parentheses and markup in the heading are ignored) whose first bullet is `- live_since: YYYY-MM-DD` or `- live_since: not live`.

## Exit codes

- `0` allow
- `2` block (stderr message goes back to the agent)
- `1` is NOT a block; Claude Code treats it as a non-blocking error

## Proof commands

These are for a human terminal. An agent running them is blocked, because the command text itself names the env file. An agent can prove the same thing with Python, which never writes the file name literally (expect `2`):

```bash
python3 -c "import subprocess,json,sys; p=subprocess.run([sys.executable,'scripts/hooks/guard_secrets.py'],input=json.dumps({'tool_name':'Read','tool_input':{'file_path':'.' + 'env'}}),capture_output=True,text=True); print(p.returncode)"
```

Human terminal:

```bash
echo '{"tool_name":"Read","tool_input":{"file_path":".env"}}' | python3 scripts/hooks/guard_secrets.py; echo "exit=$?"   # expect 2
echo '{"tool_name":"Read","tool_input":{"file_path":"README.md"}}' | python3 scripts/hooks/guard_secrets.py; echo "exit=$?" # expect 0
CLAUDE_PROJECT_DIR=$PWD python3 scripts/hooks/setup_pending.py <<< '{}' # expect nothing (this is the template repo)
CLAUDE_PROJECT_DIR=$PWD python3 scripts/hooks/guard_vault_path.py <<< '{}' # expect nothing (path is not synced)
```

Tests: `python -m pytest scripts/tests/test_hooks.py scripts/tests/test_sanitize_ingest.py -q`

## Credentialed commands

Variables are expanded by the shell before with-env runs, so put the command in single quotes: `python3 scripts/with-env.py -- bash -c 'curl -H "Authorization: Bearer $TOKEN" https://...'`.
