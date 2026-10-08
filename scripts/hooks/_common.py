#!/usr/bin/env python3
"""Shared helpers for Claude Code hooks. Stdlib only. Every hook fails OPEN."""
import json
import os
import sys


def read_payload():
    """Parse the JSON payload Claude Code sends on stdin. Returns {} on any problem."""
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def project_dir(payload=None):
    return (os.environ.get("CLAUDE_PROJECT_DIR")
            or (payload or {}).get("cwd")
            or os.getcwd())


def _log_block(message, payload):
    """Append a masked PreToolUse.block row to the agent-actions log. Fails silent."""
    try:
        from datetime import datetime, timezone
        from pathlib import Path
        payload = payload or {}
        tool = payload.get("tool_name", "")
        summary = ""
        reason = message[:120]
        try:
            import log_tool_use
            summary = log_tool_use._summary(tool, payload.get("tool_input"))
            reason = log_tool_use._mask(reason)
        except Exception:
            pass
        row = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "session_id": payload.get("session_id", ""),
            "event": "PreToolUse.block",
            "tool": tool,
            "ok": False,
            "summary": summary,
            "reason": reason,
        }
        out_dir = Path(project_dir(payload)) / "_generated" / "agent-actions"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / (datetime.now(timezone.utc).strftime("%Y-%m") + ".jsonl")
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def block(message, payload=None):
    """Exit 2: Claude Code stops the tool and hands `message` back to the agent."""
    _log_block(message, payload)
    sys.stderr.write(message.rstrip() + "\n")
    sys.exit(2)


def allow():
    sys.exit(0)


def run(main_fn):
    """Call main_fn(payload). Any exception, including SystemExit(2) raised
    deliberately, propagates only when it is a block; everything else exits 0."""
    try:
        payload = read_payload()
        main_fn(payload)
    except SystemExit as e:
        raise e
    except Exception:
        sys.exit(0)
    sys.exit(0)


TEMPLATE_ORIGINS = ("IntegralOrg/ClaudeCodeSystem", "IntegralOrg/ClaudeCodeSystem-Cloud", "StackDev223/ClaudeCodeSystem")


def origin_repo_path(url):
    """'owner/repo' of a git remote URL (https or scp-style, optional .git and trailing slash), lowercased; '' if none."""
    import re
    m = re.search(r"[/:]([^/:]+)/([^/:]+?)(?:\.git)?/*$", (url or "").strip())
    return f"{m.group(1)}/{m.group(2)}".lower() if m else ""


def is_template_repo(root):
    """True when this checkout IS the public template (a maintainer's clone), not a client's brain.
    Exact match on the origin's owner/repo, so a lookalike such as ClaudeCodeSystem-Foo is not the template."""
    try:
        import subprocess
        p = subprocess.run(["git", "--no-optional-locks", "-C", str(root), "remote", "get-url", "origin"],
                           capture_output=True, text=True, timeout=2)
        url = p.stdout.strip() if p.returncode == 0 else ""
    except Exception:
        return False
    return origin_repo_path(url) in {t.lower() for t in TEMPLATE_ORIGINS}
