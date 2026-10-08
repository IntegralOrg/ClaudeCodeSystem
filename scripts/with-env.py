#!/usr/bin/env python3
"""Run a command with the repo's .env loaded: python3 scripts/with-env.py -- curl ...
The agent never sees the values; the child process does."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import envload  # noqa: E402


def main():
    args = sys.argv[1:]
    if args and args[0] == "--":
        args = args[1:]
    if not args:
        sys.stderr.write("usage: with-env.py -- <command> [args...]\n")
        sys.exit(64)
    if envload.load(Path.cwd()) is None:
        envload.load()
    try:
        os.execvp(args[0], args)
    except FileNotFoundError:
        sys.stderr.write(f"with-env: command not found: {args[0]}\n")
        sys.exit(127)


if __name__ == "__main__":
    main()
