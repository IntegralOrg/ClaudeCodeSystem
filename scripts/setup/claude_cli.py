#!/usr/bin/env python3
"""Find the Claude command line that a Desktop-only install bundles, and run it from a session.

Claude Desktop runs every session through its own copy of the command-line tool, but that copy is not on PATH,
so `claude plugin ...` fails in a session on a computer where nobody installed the CLI by hand. The copy is
findable: on a Mac it is the running process behind this session (`ps -xo command`, this user's processes only), or the newest
`~/Library/Application Support/Claude/claude-code/<version>/<hash>/claude.app/Contents/MacOS/claude`; on Windows
it is the running process whose path contains `claude-code` and ends in `claude.exe`.

  python3 scripts/setup/claude_cli.py                 prints `CLI <path>` (exit 0) or `CLI_MISSING` (exit 3)
  python3 scripts/setup/claude_cli.py -- <args...>    runs that CLI with the arguments, with the three variables a
                                                      session sets (CLAUDECODE, CLAUDE_CODE_ENTRYPOINT,
                                                      CLAUDE_CODE_CHILD_SESSION) unset so it starts clean; the
                                                      CLI's output and exit code come back unchanged;
                                                      with no CLI it prints `CLI_MISSING` and exits 1.

Test hooks: SETUP_CLAUDE_HOME (home folder), SETUP_CLAUDE_PS (a file with process lines, or empty for none).
"""
import glob
import os
import platform
import re
import shutil
import subprocess
import sys

SESSION_VARS = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_CHILD_SESSION")
MAC_TAIL = "/claude.app/Contents/MacOS/claude"
MAC_BUNDLE_GLOB = "Library/Application Support/Claude/claude-code/*/*" + MAC_TAIL


def _version_key(path):
    """Sort key for .../claude-code/<version>/<hash>/...: numeric version parts, so 2.1.295 beats 2.1.30."""
    m = re.search(r"[/\\]claude-code[/\\]([^/\\]+)[/\\]", path)
    parts = re.findall(r"\d+", m.group(1)) if m else []
    return tuple(int(x) for x in parts), os.path.getmtime(path)


def under_home(path, home):
    """Component-aware containment: `C:\\Users\\alice-elsewhere` is not under `C:\\Users\\alice`."""
    candidate = os.path.normcase(os.path.abspath(path))
    home = os.path.normcase(os.path.abspath(home))
    try:
        return os.path.commonpath([candidate, home]) == home
    except ValueError:        # different drives on Windows
        return False


def is_mine(path):
    """True when the current user owns the file (Windows has no uid: fall back to the home folder)."""
    try:
        if hasattr(os, "getuid"):
            return os.stat(path).st_uid == os.getuid()
    except OSError:
        return False
    return os.path.isfile(path) and under_home(path, os.path.expanduser("~"))


def ps_command(system):
    """The process listing: this user's processes only (`-x`, never `-a`), so a fake `claude` another account
    started on a shared computer is never picked up."""
    if system == "Windows":
        return ["powershell.exe", "-NoProfile", "-Command",
                "Get-Process | Where-Object { $_.Path } | ForEach-Object { $_.Path }"]
    return ["ps", "-xo", "command"]


def _from_process_line(line, system, is_mine=is_mine):
    """The bundled CLI path inside one `ps` command line, or None. The path may hold spaces
    ("Application Support"), and a wrapper such as `disclaimer --pgroup --` may precede it.
    Only a file the current user owns is accepted: the result gets run."""
    if system == "Darwin":
        end = line.find(MAC_TAIL)
        if end < 0:
            return None
        end += len(MAC_TAIL)
    else:
        m = re.search(r"claude-code[^\n]*?claude\.exe", line, re.I)
        if not m:
            return None
        end = m.end()
    head = line[:end]
    starts = [i + 1 for i in range(len(head)) if head[i] == " " and i + 1 < len(head) and head[i + 1] in "/\\"]
    if system == "Windows":
        starts += [m.start() for m in re.finditer(r"(?<![^\s\"'])[A-Za-z]:[\\/]", head)]
    start = max(starts) if starts else 0
    candidate = head[start:].strip("\"'")
    return candidate if os.path.isfile(candidate) and is_mine(candidate) else None


def find_cli(system=None, home=None, path_dirs=None, processes=None, is_mine=is_mine):
    """Return the path of a working Claude CLI, or None. Order: PATH, the running process, the bundle on disk."""
    system = system or platform.system()
    home = home or os.path.expanduser("~")
    exe = "claude.exe" if system == "Windows" else "claude"
    path = os.pathsep.join(path_dirs) if path_dirs is not None else os.environ.get("PATH", "")
    on_path = shutil.which(exe, path=path) or (shutil.which("claude", path=path) if system == "Windows" else None)
    if on_path and is_mine(on_path):      # the same rule as below: the result gets run, so only the user's own file
        return on_path
    for line in (processes if processes is not None else _process_lines(system)):
        found = _from_process_line(line, system, is_mine)
        if found:
            return found
    if system == "Darwin":
        bundled = [p for p in glob.glob(os.path.join(home, MAC_BUNDLE_GLOB)) if os.access(p, os.X_OK) and is_mine(p)]
        if bundled:
            return max(bundled, key=_version_key)
    return None


def _process_lines(system):
    ps_file = os.environ.get("SETUP_CLAUDE_PS")
    if ps_file is not None:
        if not ps_file:
            return []
        with open(ps_file, encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    try:
        r = subprocess.run(ps_command(system), capture_output=True, text=True, timeout=30)
        return r.stdout.splitlines()
    except Exception:
        return []


def clean_env(env):
    """The environment for a child CLI: a session's own markers removed, so the child does not think it is nested."""
    return {k: v for k, v in env.items() if k not in SESSION_VARS}


def main(argv):
    cli = find_cli(home=os.environ.get("SETUP_CLAUDE_HOME"))
    running = bool(argv) and argv[0] == "--"
    if not cli:
        print("CLI_MISSING", flush=True)
        return 1 if running else 3   # asking is "missing" (3); trying to run with none is a failure (1)
    if running:
        r = subprocess.run([cli, *argv[1:]], env=clean_env(os.environ))
        return r.returncode
    print(f"CLI {cli}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
