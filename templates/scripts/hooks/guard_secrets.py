#!/usr/bin/env python3
"""PreToolUse gate: the agent can never reach a credential, never name the env
file, never dump the environment, and never run a destructive command.

Policy lives in the regexes below. Fails OPEN on any error. Exit 2 blocks."""
import os
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import allow, block, run  # noqa: E402

ENV_TEMPLATE = re.compile(r"\.env\.(example|sample|template)\b", re.IGNORECASE)

# Credential files. `.env`, `.env.local`, `.env.production` ... but not `.env.example`.
SECRET_PATH = re.compile(
    r"(^|[/\s'\"=])\.env(\.[A-Za-z0-9_-]+)?(?=$|[\s'\"|;&)*`$])"
    r"|\.pem\b|\.key\b|id_rsa|id_ed25519|(^|/)\.ssh(/|$)|\.aws/credentials|\.netrc"
    r"|credentials\.json|google_token\.json|token\.json|service[-_]account.*\.json",
    re.IGNORECASE,
)

_PRINT_ENV = "print" + "env"
_ENVIRON = "en" + "viron"

# A word is "in command position" at line start, after a control operator, after
# `--` / `-c`, or after a launcher (exec, sudo, xargs, time, nice); flags allowed.
_CMD = r"(?:(?:^|[;&|(`])\s*|(?:\s-c|\s--|\b(?:exec|sudo|xargs|time|nice))\s+)(?:-\S+\s+)*"
_END = r"\s*(?:$|[|;&<>)`])"
_CRED_VAR = r"\$\{?[A-Za-z_]*(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|API)[A-Za-z_]*\}?"

ENV_DUMP = (
    re.compile(r"\b" + _PRINT_ENV + r"\b", re.IGNORECASE),
    # env with no command and no assignment (flags such as -0 allowed); `env VAR=x cmd` stays legal.
    re.compile(_CMD + r"(?:/usr/bin/)?env(?:\s+-\S+)*" + _END, re.IGNORECASE | re.MULTILINE),
    # bare set / export / declare / typeset list every variable; `set -e` and `export X=1` stay legal.
    re.compile(_CMD + r"(?:set|export|declare|typeset)" + _END, re.IGNORECASE | re.MULTILINE),
    re.compile(r"\b(export\s+-p|set\s*\|)", re.IGNORECASE),
    re.compile(r"\b(?:declare|typeset)\s+-[a-zA-Z]*[px]", re.IGNORECASE),
    re.compile(r"/proc/[^\s]*/" + _ENVIRON, re.IGNORECASE),
    re.compile(r"\b(?:echo|printf)\b[^|;&]*" + _CRED_VAR, re.IGNORECASE),
    re.compile(r"os\." + _ENVIRON + r"|process\.env|ENV\[|\bgetenv\s*\(|GetEnvironmentVariable", re.IGNORECASE),
    re.compile(r"\$env:|\b(?:get-childitem|gci|ls|dir|get-item|gi)\s+(?:-path\s+)?env:", re.IGNORECASE),
)

TMP_PREFIXES = ("/tmp/", "/private/tmp/", "/private/var/folders/", "/var/folders/", "$TMPDIR", "${TMPDIR")

DESTRUCTIVE = (
    (re.compile(r"\bgit\s+push\b(?!.*--force-with-lease).*(\s--force\b|\s-f\b)"), "git push --force"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "git reset --hard"),
    (re.compile(r"\bgit\s+clean\s+-[a-z]*f"), "git clean -f"),
    (re.compile(r"\bgit\s+branch\s+-D\b"), "git branch -D"),
    (re.compile(r"\b(DROP\s+(TABLE|DATABASE|SCHEMA)|TRUNCATE\s+TABLE)\b", re.IGNORECASE), "SQL drop/truncate"),
)

BLOCK_SECRET = ("BLOCKED: access to credentials is not allowed (env files, keys, environment dumps). "
                "Credentials are loaded inside scripts; run the script instead, or read a committed .env.example.")
BLOCK_RM = "BLOCKED: recursive force delete outside the temp directories."
BLOCK_DESTRUCTIVE = "BLOCKED: destructive command ({}). Ask the owner to run it by hand."


def _normalize(command):
    return " ".join(command.replace("'", "").replace('"', "").split())


REDIRECT = re.compile(r"(?<=\s)\d*[<>]{1,2}&?\s*\S*")


def _strip_comment(command):
    """Drop a trailing shell `#` comment (quote-aware, so quoted # survives)."""
    quote = None
    for i, ch in enumerate(command):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or command[i - 1].isspace()):
            return command[:i]
    return command


def _normalize_target(target):
    t = target
    if t == "~" or t.startswith("~/"):
        t = "/HOME/" + t[2:]
    t = t.replace("${HOME}", "/HOME").replace("$HOME", "/HOME")
    return os.path.normpath(t)


def _rm_invocations(command):
    """Yield (recursive, force, targets) for every `rm` in the command."""
    command = REDIRECT.sub(" ", _strip_comment(command))
    for segment in re.split(r"\|\||&&|[;|&\n]", command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            tokens = segment.split()
        for i, tok in enumerate(tokens):
            if tok == "rm" or tok.endswith("/rm"):
                flags = [t for t in tokens[i + 1:] if t.startswith("-") and t != "-"]
                targets = [t for t in tokens[i + 1:] if not t.startswith("-")]
                short = "".join(f[1:] for f in flags if not f.startswith("--"))
                recursive = "r" in short.lower() or "--recursive" in flags
                force = "f" in short or "--force" in flags
                yield recursive, force, targets
                break


def _is_secret_access(tool_name, tool_input):
    if tool_name in ("Read", "Edit", "MultiEdit", "Write", "NotebookEdit"):
        for key in ("file_path", "notebook_path"):
            path = str(tool_input.get(key, "") or "").replace("\\", "/")
            if SECRET_PATH.search(ENV_TEMPLATE.sub("", path)):
                return True
        return False
    if tool_name in ("Grep", "Glob"):
        for key in ("pattern", "path", "glob", "type"):
            target = str(tool_input.get(key, "") or "").replace("\\", "/")
            if SECRET_PATH.search(ENV_TEMPLATE.sub("", target)):
                return True
        return False
    if tool_name in ("Bash", "PowerShell"):
        raw = str(tool_input.get("command", "")).replace("\\", "/")
        for command in (raw, _normalize(raw)):
            if any(p.search(command) for p in ENV_DUMP):
                return True
            stripped = ENV_TEMPLATE.sub("", command)
            if SECRET_PATH.search(stripped):
                return True
    return False


def decide(tool_name, tool_input):
    """Return a block message, or None to allow."""
    tool_input = tool_input or {}
    if _is_secret_access(tool_name, tool_input):
        return BLOCK_SECRET
    if tool_name in ("Bash", "PowerShell"):
        raw = str(tool_input.get("command", ""))
        command = " ".join(raw.split())
        for recursive, force, targets in _rm_invocations(raw):
            if recursive and force and targets:
                if not all(_normalize_target(t).startswith(TMP_PREFIXES) for t in targets):
                    return BLOCK_RM
        for pattern, label in DESTRUCTIVE:
            if pattern.search(command):
                return BLOCK_DESTRUCTIVE.format(label)
    return None


def main(payload):
    msg = decide(payload.get("tool_name", ""), payload.get("tool_input") or {})
    if msg:
        block(msg, payload)
    allow()


if __name__ == "__main__":
    run(main)
