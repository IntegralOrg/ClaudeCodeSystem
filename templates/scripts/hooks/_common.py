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


def block(message):
    """Exit 2: Claude Code stops the tool and hands `message` back to the agent."""
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
