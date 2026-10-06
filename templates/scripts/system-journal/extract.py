#!/usr/bin/env python3
"""System Journal, stage 1: the EVIDENCE record. Deterministic extraction of a Claude Code
session transcript into one JSON file that is kept forever in the vault.

Design: full transcripts are not stored anywhere (git history never
shrinks; an object store is infrastructure per client; and a transcript is ~88% tool output
nobody re-reads). Instead this script keeps the 7% that carries the session: the user's
words verbatim, the agent's visible words (capped), the agent's actions (tool names and
capped inputs, files touched), every tool error, and identity/timing. It is CODE, not a
model: the same transcript always yields the same bytes, so a future distiller re-reads
the same evidence instead of re-summarizing a summary, and every claim in a journal line
can be checked against the user's actual words. Nothing non-deterministic touches this tier.

What is dropped, on purpose: tool outputs (what the agent read), attachments, thinking,
system-injected reminders, subagent sidechains. If a journal line says "the query returned
zero rows", the evidence shows the query the agent ran and what it said next, not the rows.

Output: <vault>/_generated/system-journal/evidence/<YYYY-MM>/<session_id>.json
        (one file per session, rewritten in place when the session grows; no timestamps of
        extraction inside the file, so an unchanged transcript never dirties git).
State:  ~/.system-journal/state.json (per machine), merged per session under a lock so a
        Stop-hook extract and a sweep's distill never clobber each other.

Usage:
  extract.py [--vault <path>] [--idle-min 30] [--session <id>]... [--stop] [--force] [--redistill]
             [--projects <glob>]

  (no args)          sweep: extract every transcript that grew and has been idle >= --idle-min
  --session <id>     extract that session now regardless of idleness and mark it FINAL (the
                     SessionEnd path); the distiller will journal it on the next run
  --stop             with --session: a Stop-hook extract of a LIVE session. Writes the evidence
                     file but does not mark it final, so the distiller waits for the session to
                     end or go idle (no paid distill of a half-finished session)
  --force            re-extract everything, keeping journal lines (safe after an extractor change)
  --redistill        with --force: also queue every re-extracted session for a new journal line
"""
import argparse
import fcntl
import glob
import json
import os
import re
import sys
import time

HOME = os.path.expanduser("~")
STATE_DIR = os.path.join(HOME, ".system-journal")
STATE_FILE = os.path.join(STATE_DIR, "state.json")
STATE_LOCK = os.path.join(STATE_DIR, "state.lock")
CONFIG_FILE = os.path.join(STATE_DIR, "config.json")

# Where the vault lives. Resolution order: env `SYSTEM_JOURNAL_VAULT`, then the installed
# config file (`install.sh --vault <path>` writes it), then a script-relative fallback.
# The fallback is the directory three levels up from this file, which is the vault root when
# the scripts sit at `<vault>/scripts/system-journal/`. Once `install.sh` copies the scripts
# to `~/scripts/system-journal/`, that fallback no longer points at a vault, so the installed
# copies need the config (or the env var) -- `install.sh --vault` is the setup step. See
# README "Configuration".
_FALLBACK_VAULT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resolve_vault():
    v = os.environ.get("SYSTEM_JOURNAL_VAULT")
    if v:
        return os.path.expanduser(v)
    try:
        with open(CONFIG_FILE) as f:
            v = json.load(f).get("vault")
        if v:
            return os.path.expanduser(v)
    except (OSError, ValueError):
        pass
    return _FALLBACK_VAULT


DEFAULT_VAULT = resolve_vault()
PROJECTS_GLOB = os.path.join(HOME, ".claude", "projects", "*", "*.jsonl")

SCHEMA = "evidence/1"

# Caps (agreed 2026-09-21). Measured on 439 sessions: median 9 KB, p95 62 KB, max ~400 KB.
MAX_USER_CHARS = 8000        # a pasted document is capped; the document exists elsewhere
MAX_ASSISTANT_CHARS = 1000   # per visible assistant turn
MAX_TOOL_INPUT_CHARS = 200   # enough to keep the exact command / SQL the agent ran
MAX_ERROR_CHARS = 400
MAX_FINAL_CHARS = 3000
MAX_FILES = 200

# System-injected user turns that are not the user's words.
NOISE_PREFIXES = (
    "<command-name>",
    "<local-command-stdout>",
    "<local-command-caveat>",
    "<task-notification>",
    "<system-reminder>",
    "[Request interrupted",
    "<bash-input>",
    "<bash-stdout>",
    "<bash-stderr>",
)


# ----------------------------------------------------------------------------- state

def _load_state_unlocked():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def load_state():
    return _load_state_unlocked()


def merge_state(updates):
    """Reload the file, apply per-session patches, write atomically. Under a lock, so two
    processes (a Stop-hook extract and a sweep's distill) never overwrite each other's keys."""
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE_LOCK, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        state = _load_state_unlocked()
        for sid, patch in updates.items():
            cur = state.get(sid, {})
            cur.update(patch)
            state[sid] = cur
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f, indent=1, sort_keys=True)
        os.replace(tmp, STATE_FILE)
        fcntl.flock(lk, fcntl.LOCK_UN)
    return state


# ----------------------------------------------------------------------------- helpers

def clean_text(text):
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.S)
    text = re.sub(r"\[Image[^\]]*\]", "[image]", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def cap(text, limit):
    if len(text) <= limit:
        return text, False
    return text[:limit] + f" …[+{len(text) - limit} chars]", True


def slash_command(text):
    m = re.search(r"<command-name>\s*(/[\w-]+)", text)
    return m.group(1) if m else None


def tool_input_summary(name, inp):
    """A capped, deterministic one-liner of what the agent asked the tool to do."""
    if not isinstance(inp, dict):
        return cap(json.dumps(inp, ensure_ascii=False, sort_keys=True), MAX_TOOL_INPUT_CHARS)[0]
    for key in ("command", "file_path", "notebook_path", "pattern", "query", "url", "prompt", "description"):
        v = inp.get(key)
        if isinstance(v, str) and v.strip():
            return cap(re.sub(r"\s+", " ", v).strip(), MAX_TOOL_INPUT_CHARS)[0]
    return cap(json.dumps(inp, ensure_ascii=False, sort_keys=True), MAX_TOOL_INPUT_CHARS)[0]


def session_id_of(path):
    name = os.path.basename(path)
    return name[:-6] if name.endswith(".jsonl") else os.path.splitext(name)[0]


# ----------------------------------------------------------------------------- extraction

def extract_session(path):
    sid = session_id_of(path)
    project = os.path.basename(os.path.dirname(path))
    turns = []
    files, cmds, tool_counts, models = [], [], {}, {}
    first_ts = last_ts = None
    title = cwd = git_branch = None
    user_turns = assistant_turns = error_count = subagent_runs = 0
    final_text = ""
    prs = set()
    last_assistant = None  # the turn dict tool errors attach to

    with open(path, errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            t = d.get("type")
            if t == "ai-title":
                title = d.get("aiTitle") or title
                continue
            if t not in ("user", "assistant") or d.get("isSidechain"):
                continue
            ts = d.get("timestamp")
            if ts:
                first_ts = first_ts or ts
                last_ts = ts
            cwd = cwd or d.get("cwd")
            git_branch = git_branch or d.get("gitBranch")
            msg = d.get("message") or {}
            content = msg.get("content")

            if t == "user":
                texts = []
                if isinstance(content, str):
                    texts = [content]
                elif isinstance(content, list):
                    for c in content:
                        if not isinstance(c, dict):
                            continue
                        if c.get("type") == "text" and isinstance(c.get("text"), str):
                            texts.append(c["text"])
                        elif c.get("type") == "tool_result" and c.get("is_error"):
                            body = c.get("content")
                            if isinstance(body, list):
                                body = " ".join(x.get("text", "") for x in body if isinstance(x, dict))
                            body = re.sub(r"\s+", " ", str(body or "")).strip()
                            if body:
                                error_count += 1
                                if last_assistant is not None:
                                    last_assistant.setdefault("errors", []).append(cap(body, MAX_ERROR_CHARS)[0])
                for raw in texts:
                    cmd = slash_command(raw)
                    if cmd:
                        cmds.append(cmd)
                    if raw.startswith(NOISE_PREFIXES):
                        continue
                    text = clean_text(raw)
                    if not text:
                        continue
                    text, truncated = cap(text, MAX_USER_CHARS)
                    turn = {"i": len(turns), "t": ts, "role": "user", "text": text}
                    if truncated:
                        turn["truncated"] = True
                    turns.append(turn)
                    user_turns += 1
            else:
                assistant_turns += 1
                m = msg.get("model")
                if m:
                    models[m] = models.get(m, 0) + 1
                texts, tools = [], []
                if isinstance(content, list):
                    for c in content:
                        if not isinstance(c, dict):
                            continue
                        if c.get("type") == "text" and c.get("text"):
                            texts.append(c["text"])
                        elif c.get("type") == "tool_use":
                            name = c.get("name", "?")
                            tool_counts[name] = tool_counts.get(name, 0) + 1
                            inp = c.get("input") or {}
                            entry = {"name": name, "input": tool_input_summary(name, inp)}
                            fp = None
                            if isinstance(inp, dict):
                                fp = inp.get("file_path") or inp.get("notebook_path")
                            if isinstance(fp, str) and fp and name in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
                                entry["file"] = fp
                                files.append(fp)
                            if name in ("Agent", "Task"):
                                subagent_runs += 1
                            tools.append(entry)
                if not texts and not tools:
                    continue
                turn = {"i": len(turns), "t": ts, "role": "assistant"}
                if texts:
                    joined = re.sub(r"\s+", " ", "\n".join(texts)).strip()
                    final_text = "\n".join(texts)
                    turn["text"] = cap(joined, MAX_ASSISTANT_CHARS)[0]
                    for pm in re.finditer(r"(?:PR\s*#\d+|pull/\d+|https://github\.com/\S+)", joined):
                        prs.add(pm.group(0)[:120])
                if tools:
                    turn["tools"] = tools
                turns.append(turn)
                last_assistant = turn

    if user_turns == 0 and not final_text:
        return None

    seen, uniq = set(), []
    for fp in files:
        rel = fp.replace(HOME + "/", "~/")
        if rel not in seen:
            seen.add(rel)
            uniq.append(rel)

    return {
        "schema": SCHEMA,
        "session_id": sid,
        "project": project,
        "cwd": cwd,
        "git_branch": git_branch,
        "title": title,
        "started": first_ts,
        "ended": last_ts,
        "models": dict(sorted(models.items(), key=lambda kv: (-kv[1], kv[0]))),
        "user_turns": user_turns,
        "assistant_turns": assistant_turns,
        "subagent_runs": subagent_runs,
        "slash_commands": sorted(set(cmds)),
        "tool_counts": dict(sorted(tool_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "tool_error_count": error_count,
        "files_touched": uniq[:MAX_FILES],
        "pr_refs": sorted(prs)[:20],
        "turns": turns,
        "final": cap(re.sub(r"\s+", " ", final_text).strip(), MAX_FINAL_CHARS)[0],
    }


def evidence_path(vault, started, sid):
    month = (started or "0000-00")[:7]
    d = os.path.join(vault, "_generated", "system-journal", "evidence", month)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, sid + ".json")


def write_if_changed(path, record):
    data = json.dumps(record, ensure_ascii=False, indent=1) + "\n"
    try:
        with open(path) as f:
            if f.read() == data:
                return False
    except OSError:
        pass
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(data)
    os.replace(tmp, path)
    return True


# ----------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=DEFAULT_VAULT)
    ap.add_argument("--idle-min", type=int, default=30, help="skip transcripts modified within N minutes")
    ap.add_argument("--session", action="append", default=[], help="always extract this session id (marks it final unless --stop)")
    ap.add_argument("--stop", action="store_true", help="Stop-hook extract of a live session: write evidence, do not mark final")
    ap.add_argument("--force", action="store_true", help="re-extract everything (keeps journal lines)")
    ap.add_argument("--redistill", action="store_true", help="with --force: also queue paid re-distills")
    ap.add_argument("--projects", default=PROJECTS_GLOB, help="glob of transcript files")
    ap.add_argument("--out", default="", help="TEST ONLY: write evidence as <out>/<sid>.json and do not touch state.json (for determinism checks)")
    args = ap.parse_args()

    if not os.path.isdir(args.vault):
        print(f"extract: vault not found at {args.vault}", file=sys.stderr)
        return 2

    state = load_state()
    now = time.time()
    done = skipped = kept = 0
    updates = {}

    for path in sorted(glob.glob(args.projects)):
        sid = session_id_of(path)
        proj = os.path.basename(os.path.dirname(path))
        # Never journal the distiller's own headless runs or /private/tmp scratch.
        # Temp-dir projects (-private-var-folders-*) are headless tool runs like vault-embed's judge.
        if proj.endswith("-system-journal") or proj == "-private-tmp" or proj.startswith("-private-var-folders-"):
            continue
        try:
            st = os.stat(path)
        except OSError:
            continue
        prev = state.get(sid, {})
        named = sid in args.session
        if args.session and not named and not args.force:
            continue  # a targeted run touches only the named sessions
        fresh = (now - st.st_mtime) < args.idle_min * 60
        unchanged = prev.get("size") == st.st_size and prev.get("mtime") == st.st_mtime
        if not args.force and not named:
            if unchanged or fresh:
                skipped += 1
                continue
        rec = extract_session(path)
        if rec is None:
            if not args.out:
                updates[sid] = {"size": st.st_size, "mtime": st.st_mtime, "empty": True}
            continue
        if args.out:
            # Test mode: byte-identical evidence to an alternate dir, no state side effects.
            os.makedirs(args.out, exist_ok=True)
            write_if_changed(os.path.join(args.out, sid + ".json"), rec)
            done += 1
            continue
        epath = evidence_path(args.vault, rec["started"], sid)
        write_if_changed(epath, rec)
        # Journal-line bookkeeping. A transcript that actually grew (or was named at
        # SessionEnd) needs a fresh line. A --force re-extract keeps the line unless
        # --redistill. A Stop-hook extract never queues one: the session is still live.
        if args.stop and named:
            distilled = bool(prev.get("distilled"))
            final = False
        else:
            requeue = named or not unchanged or args.redistill
            distilled = (not requeue) and bool(prev.get("distilled"))
            final = named or not fresh
        patch = {
            "size": st.st_size,
            "mtime": st.st_mtime,
            "extracted": True,
            "evidence": os.path.relpath(epath, args.vault),
            "final": final,
            "distilled": distilled,
        }
        updates[sid] = patch
        done += 1
        kept += distilled

    if updates:
        merge_state(updates)
    print(f"extract: {done} sessions written ({kept} kept their journal line), {skipped} skipped (unchanged or still active)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
