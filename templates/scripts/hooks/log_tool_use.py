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

MASK = (
    re.compile(r"(\bAuthorization\s*:\s*(?:Basic|Bearer|Token)\s+)[^\s'\"]+", re.IGNORECASE),
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"(\bX-Api-Key\s*:\s*)[^\s'\"]+", re.IGNORECASE),
    re.compile(r"\b([A-Za-z][A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*=)[^\s'\"]+",
               re.IGNORECASE),
    re.compile(r"\b(token=|password=|secret=)[^\s'\"]+", re.IGNORECASE),
    re.compile(r"(\bapikey\s*[:=]\s*)[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"(\s(?:-u|--user)[\s=]+[^\s:'\"]*:)[^\s'\"]+"),
    re.compile(r"\b(xox[abpers]-)[A-Za-z0-9-]+"),
    re.compile(r"\b(sk_live_|sk_test_|pk_live_|pk_test_|pk_|sk-|key-|re_|ghp_|github_pat_)[A-Za-z0-9_\-]+"),
)
ERROR_CLASS = re.compile(r"\b([A-Z][A-Za-z]+(?:Error|Exception)|E[A-Z]{3,}|HTTP\s?\d{3}|\d{3}\s+[A-Z][a-z]+)\b")


def _mask(text):
    for p in MASK:
        text = p.sub(lambda m: m.group(1) + "***", text)
    return text


def _summary(tool, tool_input):
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
