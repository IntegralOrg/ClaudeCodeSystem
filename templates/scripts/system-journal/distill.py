#!/usr/bin/env python3
"""System Journal, stage 2: distill each extracted session into ONE journal line.

For every ~/.system-journal/raw/<sid>.json not yet marked distilled in state.json, call
`claude -p` headless with a fixed prompt and write a single JSON line to the vault at
_generated/system-journal/<YYYY-MM>.<host>.jsonl (per-machine file so two machines never
write the same file through a file sync). A session that grew since it was journaled
(resume, reopened terminal) REPLACES its earlier line: one line per session_id, always.

Audit tier (client telemetry, off-vault someday): every line is also routed through the
sanitizer. Lines whose tags touch a sensitive area are DROPPED before they exist in
_generated/system-journal/audit/, and every decision (kept or dropped, and why) is
written to _generated/system-journal/audit/sanitization-log.jsonl. That log is the
evidence that nothing personal reaches the shared tier. The private tier is untouched.

Failures are logged to ~/.system-journal/errors.log and the session stays pending, so
nothing is silently dropped. The journal is an INPUT TO REFLECTION ONLY (see README.md).

Usage:
  distill.py [--vault <path>] [--model <id>] [--limit N] [--workers N] [--dry-run] [--no-audit]
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
STATE_DIR = os.path.join(HOME, ".system-journal")
STATE_FILE = os.path.join(STATE_DIR, "state.json")
STATE_LOCK = os.path.join(STATE_DIR, "state.lock")
ERR_LOG = os.path.join(STATE_DIR, "errors.log")
CONFIG_FILE = os.path.join(STATE_DIR, "config.json")

# Where the vault lives. Resolution order: env `SYSTEM_JOURNAL_VAULT`, then the installed
# config file (`install.sh --vault <path>` writes it), then a script-relative fallback (the
# directory three levels up, i.e. the vault root when the scripts sit at
# `<vault>/scripts/system-journal/`). The installed copies under `~/scripts/system-journal/`
# rely on the config -- `install.sh --vault` is the setup step. See README "Configuration".
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
DEFAULT_MODEL = os.environ.get("SYSTEM_JOURNAL_MODEL", "claude-sonnet-5")

# Vocabulary (the `systems` controlled list and the sensitivity rules) is owner-specific, so
# it lives in <vault>/scripts/system-journal/vocab.json. When that file is absent (a fresh
# vault), fall back to a short, client-neutral default so the pipeline still runs and routes
# personal lines out of the audit tier. See README "Configuration".
_GENERIC_VOCAB = {
    "systems": [
        "tasks", "routines", "documentation", "email", "slack", "calendar", "transcripts",
        "vault-hygiene", "knowledge-graph", "claude-code", "hooks", "mcp", "skills", "subagents",
        "github", "deploy", "testing", "sales", "proposals", "hiring", "team",
        "personal", "health", "finance", "family", "relationships",
    ],
    "sensitive_tags": [
        "personal", "health", "medical", "therapy", "relationships", "family",
        "finance", "taxes", "legal-personal", "mental-health",
    ],
    "sensitive_path_prefixes": ["Personal/", "Personal\\"],
}


def load_vocab(vault):
    """Load vocab.json from the vault, falling back to the generic default per key."""
    data = {}
    try:
        with open(os.path.join(vault, "scripts", "system-journal", "vocab.json")) as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    out = {}
    for key in ("systems", "sensitive_tags", "sensitive_path_prefixes"):
        out[key] = list(data.get(key) or _GENERIC_VOCAB[key])
    return out


# The vocabulary is loaded per run from the SELECTED vault (in main(), after arg parsing), never
# at import time, so `--vault` and the cloud `--vault "$REPO"` pick up that vault's own vocab.json
# and the audit tier applies that vault's sensitivity rules. See load_vocab() and build_prompt().
#
# Audit tier (`sensitive_tags`): any tag (exact or as a prefix before ':' or '-') drops the whole
# line from the shared tier. Whole-line drop, never field scrubbing: a scrubbed line can still leak
# through `ask`/`why`. `sensitive_path_prefixes`: paths that mark a line personal regardless of
# tags. `systems`: the controlled vocabulary the distiller must pick from (plus "client:<slug>");
# anything off-list goes in the free-form `topics` list, so nothing is lost. Trend-spotting only
# works when the same thing gets the same tag every time.

PROMPT_TEMPLATE = """You are distilling one Claude Code session into a single journal entry for a weekly
trend-spotting review. The reviewer will read hundreds of these lines at once and ask
"what keeps coming back, and why?". Be concrete and short. Quote the user's own words
for complaints. Never invent facts not present in the input. The input is a deterministic
evidence record: "turns" is the session in order, where role "user" entries are the user's
own words verbatim and role "assistant" entries are what the agent said (capped) plus the
tools it called ("tools", with capped inputs) and any tool errors that came back ("errors").
Tool OUTPUTS are not included, so never claim what a tool returned; only what was asked,
what the agent did, and what it said.

One message is expected noise and never evidence of a problem: a user-role turn that starts
"Stop hook feedback:" and names stop-hook-git-check.sh ("There are uncommitted changes in the
repository"). Cloud runs are told to run no git because a landing hook publishes their files,
so this message fires after every cloud run and the agent correctly declines it. Do not let it
change "outcome", and do not list it under "failures" or "open_loop". Judge the session only on
the work it was asked to do.

Return ONLY a JSON object with exactly these keys:
- "ask": what the user wanted from this session, one sentence, max 200 chars.
- "outcome": one of "done", "partial", "failed", "abandoned", "unknown".
- "outcome_note": what actually happened, one sentence, max 220 chars.
- "failures": list of up to 3 short strings; tool, process, or agent failures (empty list if none).
- "complaints": list of up to 3 short verbatim-ish quotes where the user expressed frustration, corrected the agent, or repeated a request (empty list if none).
- "shipped": list of up to 5 short strings; files, PRs, deploys, docs, tasks that were actually produced.
- "decisions": list of up to 4 short strings; decisions the user made or confirmed in this session (rules, directions, "do X not Y"). Prefix with "reopened: " when the session re-argued something the input shows was already decided. Empty list if none.
- "open_loop": one sentence on what was left undone or deferred, or "" if nothing.
- "systems": list of 1 to 5 tags chosen ONLY from this controlled list: %s. You may also use "client:<slug>" for a specific client (lowercase, e.g. "client:acme"). ALWAYS include "personal" when the session is about the user's own life rather than work, plus the specific area tag (health, finance, relationships, taxes, family) when one applies. Do not invent tags.
- "topics": list of up to 5 short lowercase free-form topic phrases for anything the controlled tags do not capture (empty list if none).
- "why": one sentence guessing the deeper reason this session was needed (the first "why" of five), max 200 chars.

Session data follows as JSON.
"""


def build_prompt(systems_vocab):
    """Build the distiller prompt with the selected vault's controlled `systems` list."""
    return PROMPT_TEMPLATE % ", ".join(sorted(systems_vocab))


def normalize_systems(summary, systems_vocab):
    """Enforce the vocabulary after the fact: unknown tags move to `topics` instead of vanishing."""
    systems, topics = [], list(summary.get("topics") or [])
    for t in summary.get("systems") or []:
        t = str(t).strip().lower()
        if not t:
            continue
        if t in systems_vocab or (t.startswith("client:") and len(t) > 7):
            if t not in systems:
                systems.append(t)
        elif t not in topics:
            topics.append(t)
    summary["systems"] = systems[:5] or ["claude-code"]
    summary["topics"] = [str(x).strip().lower() for x in topics if str(x).strip()][:8]
    summary["decisions"] = [str(x).strip() for x in (summary.get("decisions") or []) if str(x).strip()][:4]
    return summary


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def merge_state(updates):
    """Reload, patch per session, write atomically, under a file lock. Never write a
    whole in-memory copy back: a concurrent Stop-hook extract or a second sweep would be
    clobbered (that race cost ~$40 on 2026-09-21)."""
    import fcntl
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE_LOCK, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        state = load_state()
        for sid, patch in updates.items():
            cur = state.get(sid, {})
            cur.update(patch)
            state[sid] = cur
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f, indent=1, sort_keys=True)
        os.replace(tmp, STATE_FILE)
        fcntl.flock(lk, fcntl.LOCK_UN)


def log_error(sid, msg):
    with open(ERR_LOG, "a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {sid} {msg}\n")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fallback_title(ask, limit=60):
    """Short title for sessions Claude Code never auto-titled (too few turns to fire an
    ai-title event). Derived from the LLM 'ask', trimmed at a word boundary."""
    ask = (ask or "").strip()
    if not ask:
        return None
    if len(ask) <= limit:
        return ask.rstrip(".")
    cut = ask[:limit].rsplit(" ", 1)[0].rstrip(",.;: ")
    return (cut or ask[:limit]) + "…"


def call_claude(raw, model, prompt_text):
    env = dict(os.environ)
    env.pop("CLAUDECODE", None)  # allow running from inside a SessionEnd hook
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    prompt = prompt_text + "\n" + json.dumps(raw, ensure_ascii=False)
    # Pass the prompt on stdin, NOT as an argv element: the evidence record contains verbatim user
    # turns, and process arguments are world-readable (and bounded by ARG_MAX). `claude -p` with no
    # prompt argument reads the prompt from stdin.
    cmd = ["claude", "-p", "--model", model, "--output-format", "json"]
    # cwd is the state dir so the headless run's own transcript lands under a project dir
    # that extract.py skips (otherwise the journal would journal itself).
    p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=240, env=env, cwd=STATE_DIR)
    if p.returncode != 0:
        raise RuntimeError(f"claude exit {p.returncode}: {p.stderr.strip()[:300]}")
    outer = json.loads(p.stdout)
    text = (outer.get("result") or "").strip()
    cost = outer.get("total_cost_usd")
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise RuntimeError(f"no JSON in result: {text[:200]}")
    return json.loads(text[start:end + 1]), cost


def host_tag():
    return socket.gethostname().split(".")[0].lower().replace(" ", "-")


def month_of(started):
    return (started or now_iso())[:7]


def journal_path(vault, started):
    d = os.path.join(vault, "_generated", "system-journal")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{month_of(started)}.{host_tag()}.jsonl")


def audit_path(vault, started):
    d = os.path.join(vault, "_generated", "system-journal", "audit")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{month_of(started)}.{host_tag()}.audit.jsonl")


def sanitization_log_path(vault):
    d = os.path.join(vault, "_generated", "system-journal", "audit")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "sanitization-log.jsonl")


def upsert_line(path, entry, key="session_id"):
    """Replace any existing line with the same key, else append. One line per session."""
    rows = []
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get(key) != entry.get(key):
                    rows.append(line)
    rows.append(json.dumps(entry, ensure_ascii=False))
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write("\n".join(rows) + "\n")
    os.replace(tmp, path)


def remove_line(path, sid, key="session_id"):
    if not os.path.exists(path):
        return
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get(key) != sid:
                rows.append(line)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(("\n".join(rows) + "\n") if rows else "")
    os.replace(tmp, path)


def vault_relative(path, vault):
    """Path relative to the vault, so the sensitive-prefix test is vault-agnostic. Handles the
    `~/`-prefixed form that files_touched uses (extract.py stores vault files as ~/...). Returns
    the original string when the path is not under the vault (e.g. a path outside it)."""
    s = str(path)
    expanded = os.path.expanduser(s) if s.startswith("~") else s
    for base in (os.path.abspath(vault), os.path.realpath(vault)):
        prefix = base.rstrip("/") + "/"
        if expanded == base:
            return ""
        if expanded.startswith(prefix):
            return expanded[len(prefix):]
    return s


def sensitivity(entry, vault, sensitive_tags, sensitive_path_prefixes):
    """Return (is_sensitive, reasons). Tag match is exact or on the segment before ':'/'-'.
    The sensitivity rules come from the SELECTED vault's vocab (passed in by the caller)."""
    reasons = []
    for t in entry.get("systems") or []:
        t = str(t).lower()
        head = t.split(":")[0]
        if t in sensitive_tags or head in sensitive_tags or any(seg in sensitive_tags for seg in t.split("-")):
            reasons.append(f"tag:{t}")
    for fp in entry.get("files_touched") or []:
        s = str(fp)
        rel = vault_relative(s, vault)
        if rel.startswith(sensitive_path_prefixes) or "/Personal/" in s:
            reasons.append(f"path:{rel[:60]}")
    return (len(reasons) > 0, reasons)


def audit_entry(entry):
    """The shared-tier projection of a kept line. Work-only fields; no verbatim quotes."""
    return {
        "session_id": entry["session_id"],
        "project": entry.get("project"),
        "started": entry.get("started"),
        "ended": entry.get("ended"),
        "title": entry.get("title"),
        "user_turns": entry.get("user_turns"),
        "slash_commands": entry.get("slash_commands", []),
        "tool_error_count": entry.get("tool_error_count", 0),
        "pr_refs": entry.get("pr_refs", []),
        "session_models": entry.get("session_models", {}),
        "ask": entry.get("ask"),
        "outcome": entry.get("outcome"),
        "outcome_note": entry.get("outcome_note"),
        "failures": entry.get("failures") or [],
        "complaint_count": len(entry.get("complaints") or []),
        "shipped": entry.get("shipped") or [],
        "decisions": entry.get("decisions") or [],
        "open_loop": entry.get("open_loop"),
        "systems": entry.get("systems") or [],
        "topics": entry.get("topics") or [],
        "why": entry.get("why"),
        "distilled_at": entry.get("distilled_at"),
        "audit_tier_version": 1,
    }


def route_audit(vault, entry, lock, sensitive_tags, sensitive_path_prefixes):
    """Write the audit-tier line or drop it, and log the decision either way."""
    sensitive, reasons = sensitivity(entry, vault, sensitive_tags, sensitive_path_prefixes)
    apath = audit_path(vault, entry.get("started"))
    decision = {
        "ts": now_iso(),
        "session_id": entry["session_id"],
        "started": entry.get("started"),
        "action": "dropped" if sensitive else "kept",
        "reasons": reasons,
        "tags": entry.get("systems") or [],
        "audit_file": os.path.relpath(apath, vault),
        "audit_tier_version": 1,
    }
    with lock:
        if sensitive:
            remove_line(apath, entry["session_id"])  # in case an earlier version was kept
        else:
            upsert_line(apath, audit_entry(entry))
        with open(sanitization_log_path(vault), "a") as f:
            f.write(json.dumps(decision, ensure_ascii=False) + "\n")
    return decision["action"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=DEFAULT_VAULT)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=0, help="max sessions this run (0 = all)")
    ap.add_argument("--workers", type=int, default=int(os.environ.get("SYSTEM_JOURNAL_WORKERS", "4")))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-audit", action="store_true", help="skip the audit tier + sanitization log")
    ap.add_argument("--reaudit", action="store_true", help="re-route every existing journal line through the sanitizer (no LLM calls)")
    ap.add_argument("--cloud-dir", default="", help="cloud mode: write one JSON file per session into this dir instead of the monthly jsonl (used by cloud-journal.sh inside containers)")
    args = ap.parse_args()

    if not os.path.isdir(args.vault):
        print(f"distill: vault not found at {args.vault}", file=sys.stderr)
        return 2

    # Load the vocabulary from the SELECTED vault (not import-time DEFAULT_VAULT), so --vault and
    # the cloud's --vault "$REPO" apply that vault's own controlled list and sensitivity rules.
    vocab = load_vocab(args.vault)
    systems_vocab = set(vocab["systems"])
    sensitive_tags = set(vocab["sensitive_tags"])
    sensitive_path_prefixes = tuple(vocab["sensitive_path_prefixes"])
    prompt_text = build_prompt(systems_vocab)

    if args.reaudit:
        import glob as _glob
        lock = threading.Lock()
        kept = dropped = 0
        top = os.path.join(args.vault, "_generated", "system-journal")
        entries = []
        for path in sorted(_glob.glob(os.path.join(top, "*.jsonl"))):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except ValueError:
                        continue
        for path in sorted(_glob.glob(os.path.join(top, "cloud", "*.json"))):
            try:
                with open(path) as f:
                    entries.append(json.load(f))
            except (OSError, ValueError):
                continue
        for entry in entries:
            if not entry.get("session_id"):
                continue
            if route_audit(args.vault, entry, lock, sensitive_tags, sensitive_path_prefixes) == "dropped":
                dropped += 1
            else:
                kept += 1
        print(f"reaudit: {kept} kept in audit tier, {dropped} dropped, log at {os.path.relpath(sanitization_log_path(args.vault), args.vault)}")
        return 0
    state = load_state()
    # Pending = has an evidence file, is FINAL (session ended or idle; a Stop-hook extract
    # of a live session never sets final), and has no journal line for its current size.
    pending = [
        sid for sid, s in state.items()
        if s.get("evidence") and s.get("final") and not s.get("distilled")
    ]
    pending.sort(key=lambda sid: state[sid].get("mtime", 0))
    if args.limit:
        pending = pending[: args.limit]
    ok = fail = replaced = dropped = 0
    total_cost = 0.0
    t0 = time.time()
    lock = threading.Lock()

    def work(sid):
        ev_path = os.path.join(args.vault, state[sid]["evidence"])
        try:
            with open(ev_path) as f:
                raw = json.load(f)
        except (OSError, ValueError) as e:
            log_error(sid, f"evidence unreadable: {e}")
            return ("fail", 0.0, None)
        if args.dry_run:
            print(f"would distill {sid} ({raw.get('title')}, {raw.get('user_turns')} turns)")
            return ("dry", 0.0, None)
        try:
            summary, cost = call_claude(raw, args.model, prompt_text)
            summary = normalize_systems(summary, systems_vocab)
        except Exception as e:  # noqa: BLE001
            log_error(sid, f"distill failed: {e}")
            return ("fail", 0.0, None)
        entry = {
            "session_id": sid,
            "project": raw.get("project"),
            "started": raw.get("started"),
            "ended": raw.get("ended"),
            "title": raw.get("title") or fallback_title(summary.get("ask")),
            "user_turns": raw.get("user_turns"),
            "slash_commands": raw.get("slash_commands", []),
            "tool_error_count": raw.get("tool_error_count", 0),
            "files_touched": raw.get("files_touched", [])[:10],
            "pr_refs": raw.get("pr_refs", []),
            "session_models": raw.get("models") or raw.get("session_models", {}),
            "evidence": state[sid]["evidence"],
            **{k: summary.get(k) for k in ("ask", "outcome", "outcome_note", "failures", "complaints", "shipped", "decisions", "open_loop", "systems", "topics", "why")},
            "distilled_at": now_iso(),
            "model": args.model,  # the distiller, NOT the session model (see session_models)
        }
        was_replaced = bool(state[sid].get("journal"))
        if args.cloud_dir:
            # Cloud mode: one whole-JSON file per session, overwritten on re-distill, so
            # concurrent containers never touch the same file and git never sees a merge.
            entry["project"] = "cloud:" + (raw.get("project") or "").lstrip("-")
            os.makedirs(args.cloud_dir, exist_ok=True)
            path = os.path.join(args.cloud_dir, f"{(raw.get('started') or now_iso())[:10]}.{sid[:8]}.json")
            with lock:
                tmp = path + ".tmp"
                with open(tmp, "w") as f:
                    json.dump(entry, f, ensure_ascii=False, indent=1)
                os.replace(tmp, path)
                merge_state({sid: {
                    "distilled": True,
                    "journal": path,
                    "distill_count": int(state[sid].get("distill_count", 0)) + 1,
                }})
            return ("replaced" if was_replaced else "ok", cost or 0.0, None)
        path = journal_path(args.vault, raw.get("started"))
        with lock:
            upsert_line(path, entry)
            merge_state({sid: {
                "distilled": True,
                "journal": os.path.relpath(path, args.vault),
                "distill_count": int(state[sid].get("distill_count", 0)) + 1,
            }})
        action = None
        if not args.no_audit:
            action = route_audit(args.vault, entry, lock, sensitive_tags, sensitive_path_prefixes)
        return ("replaced" if was_replaced else "ok", cost or 0.0, action)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        for status, cost, action in ex.map(work, pending):
            if status in ("ok", "replaced"):
                ok += 1
                total_cost += cost
                replaced += status == "replaced"
                dropped += action == "dropped"
            elif status == "fail":
                fail += 1

    print(
        f"distill: {ok} written ({replaced} replaced earlier lines), {fail} failed, "
        f"{len(pending) - ok - fail} untouched, audit-tier dropped {dropped}, ${total_cost:.2f}, {time.time() - t0:.0f}s"
    )
    if fail:
        print(f"distill: see {ERR_LOG}", file=sys.stderr)
    return 1 if fail and not ok else 0


if __name__ == "__main__":
    sys.exit(main())
