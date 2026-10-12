#!/usr/bin/env python3
"""When a setup step fails twice: write a short report the person can send to their onboarding contact as is.

Never fails: a report that cannot be written is printed instead, and the exit code is always 0, so the report
never becomes one more failure. Masks anything that looks like a key or token before it is written or printed.

Usage: help_report.py --step S (--error-file F | --error LINE) (--tried-file F | --tried TEXT) [--details-file F] [--vault PATH]
Stdout: REPORT <path> (or REPORT_UNWRITTEN followed by the report), then SAY <one sentence for the person>.
"""
import argparse
import datetime
import importlib.util
import os
import platform
import re
import sys

# Patterns the shared masker (scripts/hooks/log_tool_use.py, the one source of truth) does not cover.
EXTRA_MASKS = [
    (re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}"
                r"|xox[abpr]-[A-Za-z0-9-]{10,})"), "[masked]"),
    (re.compile(r"\b([A-Za-z][A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Za-z0-9_]*\s*[:=]\s*)\S+", re.I),
     r"\1[masked]"),
]
SAY = ("SAY I wrote down what happened in a note in your Inbox folder. Please send it to your onboarding contact; "
       "it holds no passwords or keys.")
SAY_UNWRITTEN = ("SAY I could not save the note, so the details are in my message above. Please copy them to your "
                 "onboarding contact; they hold no passwords or keys.")


def _shared_mask():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks", "log_tool_use.py")
    try:
        spec = importlib.util.spec_from_file_location("help_report_log_tool_use", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod._mask
    except Exception:
        return None


def mask(text):
    shared = _shared_mask()
    if shared:
        text = shared(text)
    for rx, rep in EXTRA_MASKS:
        text = rx.sub(rep, text)
    return text


def tail(path, limit=3000):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()[-limit:]
    except OSError:
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", required=True)
    # Error text comes from command output, so the agent writes it to a file and passes the path: pasting it into
    # shell command text would let a `$(...)` in the error run as a command. --error/--tried stay for plain text.
    err = ap.add_mutually_exclusive_group(required=True)
    err.add_argument("--error")
    err.add_argument("--error-file")
    tried = ap.add_mutually_exclusive_group(required=True)
    tried.add_argument("--tried")
    tried.add_argument("--tried-file")
    ap.add_argument("--details-file")
    ap.add_argument("--vault", default=os.getcwd())
    a = ap.parse_args()
    if a.error_file:
        a.error = tail(a.error_file).strip() or "(error file empty or unreadable)"
    if a.tried_file:
        a.tried = tail(a.tried_file).strip() or "(not recorded)"
    now = datetime.datetime.now()
    details = tail(a.details_file) if a.details_file else ""
    body = mask(
        f"Setup stopped at: {a.step}\n"
        f"Error: {a.error}\n"
        f"What the agent tried: {a.tried}\n"
        f"Computer: {platform.system()} {platform.release()} ({platform.machine()})\n"
        + (f"\nDetails:\n{details}\n" if details else ""))
    text = (f"---\ntype: note\ncreated: {now:%Y-%m-%d}\n---\n# Setup help request {now:%Y-%m-%d %H:%M}\n\n"
            "Send this to your onboarding contact as is. It holds no keys or passwords.\n\n" + body)
    path = os.path.join(a.vault, "Inbox", f"Setup help request {now:%Y-%m-%d %H%M}.md")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"REPORT {path}")
        print(SAY)
    except OSError:
        print("REPORT_UNWRITTEN here is the report:\n" + text)
        print(SAY_UNWRITTEN)
    return 0


if __name__ == "__main__":
    sys.exit(main())
