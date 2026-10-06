# Claude Code hooks

Stdlib-only Python 3 (3.11+). Each hook reads the Claude Code JSON payload on stdin and fails OPEN: any unexpected error exits 0.

| Hook | Event | Job |
|------|-------|-----|
| `guard_secrets.py` | PreToolUse | Blocks credential files, env dumps, naming `.env`, destructive commands |
| `log_tool_use.py` | PostToolUse, PostToolUseFailure | Appends one masked JSONL row per call to `_generated/agent-actions/` |
| `guard_state_writes.py` | PreToolUse (Edit, Write, MultiEdit) | Keeps `## Current State` / `## Log` structure in state-bearing files |
| `session_context.py` | SessionStart | Injects branch, uncommitted count, recent commits, newest handoff |

`_common.py` holds the shared helpers (`read_payload`, `project_dir`, `block`, `allow`, `run`).

## Exit codes

- `0` allow
- `2` block (stderr message goes back to the agent)
- `1` is NOT a block; Claude Code treats it as a non-blocking error

## Proof commands

```bash
echo '{"tool_name":"Read","tool_input":{"file_path":".env"}}' | python3 scripts/hooks/guard_secrets.py; echo "exit=$?"   # expect 2
echo '{"tool_name":"Read","tool_input":{"file_path":"README.md"}}' | python3 scripts/hooks/guard_secrets.py; echo "exit=$?" # expect 0
```

Tests: `python -m pytest scripts/tests/test_hooks.py scripts/tests/test_sanitize_ingest.py -q`

## Credentialed commands

Variables are expanded by the shell before with-env runs, so put the command in single quotes: `python3 scripts/with-env.py -- bash -c 'curl -H "Authorization: Bearer $TOKEN" https://...'`.
