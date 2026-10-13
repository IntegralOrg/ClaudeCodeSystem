# Claude Code hooks

Stdlib-only Python 3 (3.11+). Each hook reads the Claude Code JSON payload on stdin and fails OPEN: any unexpected error exits 0.

| Hook | Event | Job |
|------|-------|-----|
| `guard_secrets.py` | PreToolUse | Blocks credential files, env dumps, naming `.env`, destructive commands |
| `log_tool_use.py` | PostToolUse, PostToolUseFailure | Appends one masked JSONL row per call to `_generated/agent-actions/` |
| `guard_state_writes.py` | PreToolUse (Edit, Write, MultiEdit) | Keeps `## Current State` / `## Log` structure in state-bearing files |
| `bump_updated.py` | PostToolUse (Edit, MultiEdit, Write) | Sets a note's existing top-level `updated:` frontmatter date to today after every edit (Markdown notes with exactly one existing `updated:` key only; never adds the key, never touches the body; skips `.git/`, `_generated/`, `.claude/`, `node_modules/`, `.superpowers/`, `.handoffs/`, and the template repo). `BUMP_UPDATED_TODAY=YYYY-MM-DD` overrides the date for tests |
| `guard_vault_path.py` | SessionStart | Warns when the vault is inside a synced folder (iCloud, OneDrive, Dropbox, Google Drive) |
| `setup_pending.py` | SessionStart | Starts setup while SETUP_PENDING exists (silent in the template repo) |
| `landing_health.py` | SessionStart | Reports repeated local landing failures from `_generated/landing.log` (silent when the last attempt succeeded) and any cloud landing refusal of the last 3 days (`_generated/landing/cloud-refusals/*.json`, written by `../cloud-land.sh`) |
| `routine_health.py` | SessionStart | Connector-free push channel: names a routine that is stale (no recent daily note or audit-log heading) or still not live after setup. Silent when healthy and in the template repo |
| `session_context.py` | SessionStart | Injects branch, uncommitted count, recent commits, newest handoff |

Besides the hooks, `.claude/settings.json` carries native `permissions.deny` rules for the credentials file (`Read(./.env)`, `Read(./.env.*)` and the `./**/` forms), so the file stays unreadable by Claude Code's own Read tool even on a computer where Python is missing and every hook is silently absent. `test_repo_layout.py` asserts the list.

`_common.py` holds the shared helpers (`read_payload`, `project_dir`, `block`, `allow`, `run`, `is_template_repo`).

`../cloud-land.sh` runs only inside a cloud container: `--start` first in the `SessionStart` hook snapshots the working tree as a git tree before the agent does anything (the only trustworthy definition of "what this session changed"; it also logs how many tracked files already differ from HEAD, a stale container), then `Stop` and `SessionEnd` (`--final`) land exactly the files that differ from that snapshot on top of the current `origin/main`. A file the agent never touched is never landed, even when the container's copy is older than main. Without a snapshot it falls back to the merge-base delta with deletions refused and a 25-file cap, and records any refusal as `_generated/landing/cloud-refusals/<date>-<sid8>.json`, which it lands so `landing_health.py` reports it everywhere.

`../land-local.sh` is not a hook script but runs from the `Stop` and `SessionEnd` hooks (`--final`) and, as `--pull`, first in the `SessionStart` hook (fast-forward from `origin/main` only; never commits, pushes, stashes, or resets, ignores the throttle, and logs `pull: ...` lines): it lands a local session's edits on `main` (cloud sessions use `../cloud-land.sh`), never forces, never discards the local commit, skips while a merge, rebase, cherry-pick or revert is in progress, removes a lock older than 10 minutes, and prints nothing: its own log is `_generated/landing.log` (timestamped lines only, capped at 2000 lines once past 4000), raw git output goes to `_generated/landing-git.log`. `landing_health.py` reads the first and also reports when landing keeps being skipped (locked or on another branch). Override env vars: `LAND_LOCAL_REPO`, `LAND_LOCAL_STATE`, `LAND_LOCAL_FORCE_LOCAL`, `LAND_LOCAL_FORCE_CLOUD`, `LAND_LOCAL_LEGACY_MERGE_TREE` (tests: use the pre-2.38 prediction), `LAND_LOCAL_HOOKS_DIR` (where `guard_vault_path.py` lives; default `scripts/hooks`).

When a push is rejected, `land-local.sh` never lets a rebase touch the working tree for nothing (a rebase checks out upstream before it can see a conflict, and its abort rewrites the tree again; in a synced folder each rewrite can leave numbered copies). Inside a synced folder (the detection is `guard_vault_path.py`'s `synced_service`, not a copy) it does not rebase at all: the commit stays on the computer and it logs `rebase skipped: synced folder (<service>)`. Otherwise it predicts the merge first with `git merge-tree --write-tree` (git 2.38+; older git uses the trivial `git merge-tree <base> HEAD origin/main` and counts conflict markers plus any deleted-on-one-side or added-on-both-sides file, and any rename on either side, since it has no rename detection; it cannot see `merge=union`, so it errs toward predicting a conflict). It fails closed: when the synced-folder check cannot run it logs `rebase skipped: could not check for a synced folder`, and when the prediction cannot run (or git reports a conflict without naming a file) it logs `conflict predicted: ...` and does not rebase. A predicted conflict leaves the tree and `main` alone and logs `conflict predicted: <n> file(s): <paths>`; a clean prediction rebases and pushes; a rebase that still conflicts (another push raced in) is aborted once and logged as `conflict with origin/main ...`, never retried in a loop.

**Fixed log phrases** (other tools, such as a system check, match on them; never reword them): `conflict`, `push failed`, `fetch failed`, `commit failed`, `mid-merge`, `landed on main`, `nothing to push`, `conflict predicted`, `rebase skipped`. `landing_health.py` counts every line with a failure phrase since the last `landed on main` or `nothing to push`; a conflict notice carries the Git Autopilot rule 6 union rule, and `rebase skipped: synced folder` (a confirmed synced folder) gets its own notice pointing at moving the vault out of it; `rebase skipped: could not check for a synced folder` is reported as a plain landing failure, without that advice. `routine_health.py` honors `ROUTINE_HEALTH_TODAY=YYYY-MM-DD` for tests. It reads `System/Routines.md` as one `## <title>` section per routine (the `title:` of `System/routines/*.md`; numbering, parentheses and markup in the heading are ignored) whose first bullet is `- live_since: YYYY-MM-DD` or `- live_since: not live`.

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
