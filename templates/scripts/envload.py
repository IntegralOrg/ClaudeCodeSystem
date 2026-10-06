#!/usr/bin/env python3
"""Load the repo's .env into os.environ (setdefault). The agent never reads the
file; scripts do. In the cloud the variables are already exported and this is a no-op."""
import os
from pathlib import Path

ROOT_MARKERS = (".git", "CLAUDE.md")


def find_root(start=None):
    p = Path(start or Path(__file__).resolve().parent).resolve()
    for candidate in (p, *p.parents):
        if any((candidate / m).exists() for m in ROOT_MARKERS):
            return candidate
    return p


def parse(text):
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:]
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        key = key.strip()
        if key:
            out[key] = value
    return out


def load(start=None):
    env_path = find_root(start) / ".env"
    local_path = env_path.with_name(".env.local")
    found = False
    # .env.local first so it overrides .env; setdefault so exported vars always win.
    for p in (local_path, env_path):
        if p.is_file():
            found = True
            for k, v in parse(p.read_text(encoding="utf-8", errors="replace")).items():
                os.environ.setdefault(k, v)
    return env_path if found else None
