#!/usr/bin/env python3
"""PostToolUse / PostToolUseFailure: append one JSONL row per tool call.
Never records tool output and never records a credential value. Fails open."""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import project_dir, run  # noqa: E402

# An assignment value: a double-quoted string (spaces and backslash-escaped quotes allowed), a
# single-quoted string, or a bare word.
_VALUE = r"(?:\"(?:[^\"\\]|\\.)*\"|'[^']*'|[\"']?[^\s'\"]+)"

MASK = (
    re.compile(r"(\bAuthorization\s*:\s*(?:Basic|Bearer|Token)\s+)[^\s'\"]+", re.IGNORECASE),
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"(\bX-Api-Key\s*:\s*)[^\s'\"]+", re.IGNORECASE),
    re.compile(r"\b([A-Za-z][A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*=)" + _VALUE,
               re.IGNORECASE),
    re.compile(r"\b(token=|password=|secret=)" + _VALUE, re.IGNORECASE),
    re.compile(r"(\bapikey\s*[:=]\s*)[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"(\s(?:-u|--user)[\s=]+[^\s:'\"]*:)[^\s'\"]+"),
    re.compile(r"\b(xox[abpers]-)[A-Za-z0-9-]+"),
    re.compile(r"\b(sk_live_|sk_test_|pk_live_|pk_test_|pk_|sk-|key-|re_|ghp_|github_pat_)[A-Za-z0-9_\-]+"),
    # password in a URL authority: scheme://user:PASS@host
    re.compile(r"(\b[A-Za-z][A-Za-z0-9+.\-]*://[^\s:/@'\"]*:)[^\s@/'\"]+(?=@)"),
    # URL query secrets: ?key=... &token=... and similar
    re.compile(r"([?&](?:key|token|api_key|apikey|access_token|secret|password)=)[^\s&'\"]+", re.IGNORECASE),
    # JSON string values under secret-looking keys: "STRIPE_KEY": "..." and {"key": "K", "value": "..."}
    re.compile(r'("(?:value|[A-Za-z0-9_\-]*(?:secret|password|passwd|token|api_?key|credential)[A-Za-z0-9_\-]*|[A-Za-z0-9_\-]*_key)"\s*:\s*")(?:[^"\\]|\\.)*(?=")',
               re.IGNORECASE),
    # a token piped into a login command: echo TOKEN | gh auth login --with-token
    re.compile(r"()[A-Za-z0-9._\-]{16,}(?=['\"]?\s*\|\s*(?:gh\s+auth\s+login|docker\s+login|vercel\s+login"
               r"|npx\b[^|]*?\blogin\b))"),
)
SECRET_TOOLS = re.compile(r"secrets?[-_](?:set|put|create|update|add|write|upsert)"
                          r"|(?:set|put|create|update|add|write|upsert)[-_]secrets?|project_env|_env$", re.IGNORECASE)
WITHHELD_TOOL = "[input withheld: secret-bearing tool]"
ERROR_CLASS = re.compile(r"\b([A-Z][A-Za-z]+(?:Error|Exception)|E[A-Z]{3,}|HTTP\s?\d{3}|\d{3}\s+[A-Z][a-z]+)\b")


def _mask(text):
    for p in MASK:
        text = p.sub(lambda m: m.group(1) + "***", text)
    return text


def _summary(tool, tool_input):
    if SECRET_TOOLS.search(tool or ""):
        return WITHHELD_TOOL
    tool_input = tool_input or {}
    if "file_path" in tool_input:
        return _mask(str(tool_input["file_path"]))
    if tool in ("Bash", "PowerShell"):
        return _mask(" ".join(str(tool_input.get("command", "")).split())[:120])
    if "pattern" in tool_input:
        return _mask(str(tool_input.get("pattern", ""))[:120])
    return ""


def _error_class(response):
    try:
        text = response if isinstance(response, str) else json.dumps(response)
    except Exception:
        return None
    m = ERROR_CLASS.search(text)
    return m.group(1) if m else None


def main(payload):
    event = payload.get("hook_event_name", "PostToolUse")
    tool = payload.get("tool_name", "")
    ok = event != "PostToolUseFailure"
    row = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "session_id": payload.get("session_id", ""),
        "event": event,
        "tool": tool,
        "ok": ok,
        "error_class": None if ok else _error_class(
            payload.get("error") or payload.get("tool_response")),
        "summary": _summary(tool, payload.get("tool_input")),
    }
    out_dir = Path(project_dir(payload)) / "_generated" / "agent-actions"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (datetime.now(timezone.utc).strftime("%Y-%m") + ".jsonl")
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    run(main)
