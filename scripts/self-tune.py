#!/usr/bin/env python3
"""Nightly self-tuning from the week's System Journal (`/vault-audit` Step 5b).

The system improves itself from its own work: friction that repeats across sessions is grouped by
root cause and handed to the Vault Hygiene run as a work order. Tier 1 patterns (a rule in CLAUDE.md,
a command's wording, a System page, a Themes entry) are applied by the command step the same night
and recorded here; Tier 2 patterns (scripts, hooks, settings, guard rules, routines, or a fix that is
unclear) are reported to the owner's contact as names and counts only. The rule is the "Decision
tiers" section of docs/DEVELOPING.md; the client page is System/Who Decides.md.

Subcommands (all take --vault PATH and --today YYYY-MM-DD for tests):
  plan     read the last 7 days, write _generated/vault-hygiene/tuning-order.json, print it
  record   after the step applied (Tier 1) or reported (Tier 2) one pattern: update tuning.json and
           print the one audit-log line for the receipt (--dry-run first: is this change allowed?)
  themes   rewrite _generated/Themes.md (40 lines max; a theme not seen for 14 days drops out)
  package  print the Tier 2 package (names and counts only) for help_report.py
  summary  print the daily note's tuning line(s) for End of Day's Routine health section

Read-only on the journal. Writes only tuning-order.json, tuning.json, and Themes.md; every other
change is made by the command step with Edit/Write. Never reads private sessions, lines tagged with
a sensitive area (vocab.json `sensitive_tags`), or anything outside _generated/system-journal/.
Stdlib only, Python 3.9+, fails open (a broken journal file is skipped, telemetry that cannot load
is reported as unavailable). Every text that leaves the journal passes through the secret masker.
"""
import argparse
import glob
import importlib.util
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOW_DAYS = 7          # rolling window, every night
HISTORY_DAYS = 60        # how far back the "2 sessions 14+ days apart" signature looks
SPREAD_DAYS = 14         # ... and the gap that makes two sessions a recurrence
MIN_SESSIONS = 3         # a pattern needs 3+ sessions in the window (or the spread rule)
MIN_WINDOW = 3           # fewer sessions than this in the window: nothing is applied
COOLDOWN_DAYS = 14       # a tuned or reported pattern is left alone this long
THEME_TTL_DAYS = 14      # a theme not seen this long drops out of Themes.md
THEMES_MAX_LINES = 40
# Error classes that mean the system fought its own guard rails or settings. Exit codes, HTTP errors
# and generic tool errors are everyday noise, not template friction.
SYSTEM_CLASSES = ("hook_blocked", "permission_denied")
# Systems tags whose fix lives in scripts, hooks, connectors or deploy config: always Tier 2.
TECH_TAGS = {"hooks", "mcp", "deploy", "github"}
TECH_WORDS = re.compile(r"(scripts/|\bhooks?\b|settings\.json|\.mcp\.json|\bguard|\bpermission|credential|"
                        r"\btoken\b|api key|traceback|exception|\bcrash|\bschedul|\bcron\b|landing|\bgit\b|"
                        r"network|proxy|\bdns\b|allowlist|connector|env(ironment)? var|\bsecret|sandbox|"
                        r"\bhttp\b|\b[45]\d\d\b|rate limit|usage limit|timed? ?out)", re.I)
# Tier 1 targets: plain-words files the step may edit on its own.
TIER1_OK = re.compile(r"^(CLAUDE\.md|\.claude/commands/[^/]+\.md|cowork-commands/[^/]+\.md|System/[^/]+\.md|"
                      r"_generated/Themes\.md|(.+/)?memory/[^/]+\.md|MEMORY\.md)$")
NEVER_TIER1 = re.compile(r"(^scripts/|^\.claude/settings|^\.mcp\.json$|(^|/)hooks/|\.(py|sh|ps1|js|json)$)")
DEFAULT_SENSITIVE = ["personal", "health", "medical", "therapy", "relationships", "family", "finance", "taxes",
                     "legal-personal", "mental-health", "vent"]
EXTRA_MASKS = [
    (re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{16,}"
                r"|xox[abpr]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_.-]+)"), "[masked]"),
    (re.compile(r"\b([A-Za-z][A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD)[A-Za-z0-9_]*\s*[:=]\s*)\S+", re.I),
     r"\1[masked]"),
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]{12,}"), r"\1[masked]"),
    (re.compile(r"\b(?=[A-Za-z0-9_+-]*\d)(?=[A-Za-z0-9_+-]*[A-Za-z])[A-Za-z0-9_+-]{40,}\b"), "[masked]"),
]


# --- small helpers --------------------------------------------------------------------------------

def _load(name, path):
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_SHARED = []


def mask(text):
    """The shared masker (scripts/hooks/log_tool_use.py) when it loads, then this file's own patterns,
    which always run, so a missing shared masker never lets a key through."""
    text = "" if text is None else str(text)
    if not _SHARED:
        mod = _load("self_tune_log_tool_use", os.path.join(HERE, "hooks", "log_tool_use.py"))
        _SHARED.append(getattr(mod, "_mask", None) if mod else None)
    if _SHARED[0]:
        try:
            text = _SHARED[0](text)
        except Exception:
            pass
    for rx, rep in EXTRA_MASKS:
        text = rx.sub(rep, text)
    return text


def plain(text, limit=160):
    """Masked, one line, no em or en dashes, capped."""
    t = mask(text).replace(chr(0x2014), ", ").replace(chr(0x2013), "-")
    t = " ".join(t.split())
    return t if len(t) <= limit else t[: limit - 3].rstrip() + "..."


def _day(s):
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).date()
    except Exception:
        return None


def _iso(d):
    return d.isoformat() if d else ""


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
        return v if isinstance(v, type(default)) else default
    except (OSError, ValueError):
        return default


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def paths(vault):
    hyg = os.path.join(vault, "_generated", "vault-hygiene")
    return {"order": os.path.join(hyg, "tuning-order.json"), "state": os.path.join(hyg, "tuning.json"),
            "themes": os.path.join(vault, "_generated", "Themes.md"),
            "journal": os.path.join(vault, "_generated", "system-journal")}


def sensitive_tags(vault):
    v = _read_json(os.path.join(vault, "scripts", "system-journal", "vocab.json"), {})
    tags = v.get("sensitive_tags") if isinstance(v.get("sensitive_tags"), list) else DEFAULT_SENSITIVE
    return {str(t).lower() for t in tags}


# --- reading the journal --------------------------------------------------------------------------

def journal_lines(vault):
    """Every journal line (local monthly jsonl files and cloud per-session files), deduped by session id
    keeping the newest distillation. Unreadable lines and files are skipped."""
    root = paths(vault)["journal"]
    found = []
    for p in sorted(glob.glob(os.path.join(root, "*.jsonl"))):
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                for raw in f:
                    try:
                        rec = json.loads(raw)
                    except ValueError:
                        continue
                    if isinstance(rec, dict):
                        found.append(rec)
        except OSError:
            continue
    for p in sorted(glob.glob(os.path.join(root, "cloud", "*.json"))):
        rec = _read_json(p, {})
        if rec:
            found.append(rec)
    best = {}
    for rec in found:
        sid = rec.get("session_id")
        if not isinstance(sid, str) or not sid:
            continue
        if sid not in best or str(rec.get("distilled_at") or "") >= str(best[sid].get("distilled_at") or ""):
            best[sid] = rec
    return list(best.values())


def _list(v):
    return [x for x in v if isinstance(x, str) and x.strip()] if isinstance(v, list) else []


def project_name(rec):
    p = str(rec.get("project") or "")
    if p.startswith("cloud:"):
        return p[6:].strip("/").split("/")[-1]
    cwd = str(rec.get("cwd") or "")
    if cwd:
        return os.path.basename(cwd.rstrip("/"))
    return ""


def load_telemetry(vault, today):
    """Evidence records through telemetry-stats.py's own loader. Returns (records, status)."""
    mod = _load("self_tune_telemetry", os.path.join(HERE, "system-journal", "telemetry-stats.py"))
    if mod is None or not hasattr(mod, "load_records"):
        return [], "unavailable: telemetry-stats.py did not load"
    try:
        now = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc).isoformat()
        return mod.load_records(vault, HISTORY_DAYS, now), "ok"
    except Exception as e:  # fail open
        return [], "unavailable: " + type(e).__name__


# --- analysis -------------------------------------------------------------------------------------

def analyse(vault, today):
    lo_window = today - timedelta(days=WINDOW_DAYS - 1)
    lo_history = today - timedelta(days=HISTORY_DAYS)
    sens = sensitive_tags(vault)
    skipped_private = skipped_sensitive = 0
    private_ids = set()
    window_sessions = set()
    groups = {}
    for rec in journal_lines(vault):
        d = _day(rec.get("ended") or rec.get("started"))
        if d is None or d < lo_history or d > today:
            continue
        sid = rec["session_id"]
        if rec.get("private") is True or rec.get("outcome") == "private":
            private_ids.add(sid)
            skipped_private += 1
            continue
        if str(rec.get("project") or "").startswith("-private-var-folders-"):
            continue
        tags = [t.lower() for t in _list(rec.get("systems"))]
        if any(t in sens for t in tags):
            if d >= lo_window:
                skipped_sensitive += 1
            continue
        if d >= lo_window:
            window_sessions.add(sid)
        texts = [("complaint", t) for t in _list(rec.get("complaints"))] + [("failure", t) for t in _list(rec.get("failures"))]
        if not texts:
            continue
        primary = next((t for t in tags if t != "claude-code"), tags[0] if tags else "claude-code")
        g = groups.setdefault("journal:" + primary, {"source": "journal", "system": primary, "sessions": {}, "texts": [],
                                                     "whys": [], "slash": {}, "projects": set(), "files": set()})
        g["sessions"][sid] = d
        g["texts"].extend((d, kind, t) for kind, t in texts)
        if isinstance(rec.get("why"), str) and rec["why"].strip():
            g["whys"].append((d, rec["why"]))
        for s in _list(rec.get("slash_commands")):
            name = s.strip().lstrip("/").split(":")[-1].split()[0] if s.strip().lstrip("/") else ""
            if name:
                g["slash"][name] = g["slash"].get(name, 0) + 1
        if project_name(rec):
            g["projects"].add(project_name(rec))
        for f in _list(rec.get("files_touched")):
            f = f.replace("\\", "/")
            # Vault-relative paths only: an absolute path names the person's machine, and Personal/ is never reported.
            if not f.startswith(("/", "~")) and ":" not in f and not f.lstrip("./").startswith("Personal/"):
                g["files"].add(f)

    records, telemetry = load_telemetry(vault, today)
    for rec in records:
        sid = rec.get("session_id")
        if rec.get("private") is True or sid in private_ids:
            continue
        d = _day(rec.get("ended") or rec.get("started"))
        if d is None or d < lo_history or d > today:
            continue
        for turn in rec.get("turns") or []:
            if turn.get("role") != "assistant":
                continue
            for t in turn.get("tools") or []:
                cls = t.get("error_class")
                if t.get("ok") is not False or cls not in SYSTEM_CLASSES:
                    continue
                tool = str(t.get("name") or "?")
                key = "telemetry:%s:%s" % (tool, cls)
                g = groups.setdefault(key, {"source": "telemetry", "tool": tool, "error_class": cls, "sessions": {},
                                            "calls": 0, "projects": set(), "texts": [], "whys": [], "slash": {}, "files": set()})
                g["sessions"][sid] = d
                g["calls"] += 1
                name = project_name(rec)
                if name:
                    g["projects"].add(name)
    return {"groups": groups, "window_sessions": window_sessions, "lo_window": lo_window, "telemetry": telemetry,
            "skipped_private": skipped_private, "skipped_sensitive": skipped_sensitive}


def qualifies(g, lo_window):
    days = sorted(g["sessions"].values())
    in_window = sum(1 for d in days if d >= lo_window)
    if in_window >= MIN_SESSIONS:
        return True
    return in_window >= 1 and len(days) >= 2 and (days[-1] - days[0]).days >= SPREAD_DAYS


def tier_of(key, g, vault):
    """Return (tier, confidence, target, mirror, reason)."""
    if g["source"] == "telemetry":
        return 2, "high", "", "", "the %s guard or setting stopped %s calls; the fix is in scripts, hooks or settings" % (
            g["error_class"].replace("_", " "), g["tool"])
    texts = [t for _, _, t in g["texts"]]
    said = [t for _, kind, t in g["texts"] if kind == "complaint"]
    techy = sum(1 for t in texts if TECH_WORDS.search(t))
    # What the owner said is behavior the agent can be told to change (Tier 1) unless it is itself
    # technical; failures alone that are mostly technical belong in scripts, settings or the environment.
    behavior = bool(said) and sum(1 for t in said if TECH_WORDS.search(t)) * 2 < len(said)
    if g["system"] in TECH_TAGS or (not behavior and texts and techy * 2 >= len(texts)):
        return 2, "high", "", "", "the friction is in scripts, hooks, settings, connectors or the environment"
    if len(texts) < 2:
        return 2, "low", "", "", "too little evidence to choose a fix"
    target, mirror = "CLAUDE.md", ""
    if g["slash"]:
        name, n = sorted(g["slash"].items(), key=lambda kv: (-kv[1], kv[0]))[0]
        if n * 2 >= len(g["sessions"]) and os.path.isfile(os.path.join(vault, ".claude", "commands", name + ".md")):
            target = ".claude/commands/%s.md" % name
            if os.path.isfile(os.path.join(vault, "cowork-commands", name + ".md")):
                mirror = "cowork-commands/%s.md" % name
    return 1, "high", target, mirror, "the same friction repeated in plain-words instructions"


def title_of(g):
    if g["source"] == "telemetry":
        return "%s calls stopped by %s" % (g["tool"], g["error_class"].replace("_", " "))
    newest = sorted(g["texts"], key=lambda x: x[0])[-1][2] if g["texts"] else g["system"]
    return "%s: %s" % (g["system"], plain(newest, 70))


def build_patterns(vault, today, state):
    a = analyse(vault, today)
    patterns, cooldown, themes = [], [], []
    for key in sorted(a["groups"]):
        g = a["groups"][key]
        if not qualifies(g, a["lo_window"]):
            continue
        days = sorted(g["sessions"].values())
        sids = sorted(g["sessions"], key=lambda s: (g["sessions"][s], s), reverse=True)
        tier, conf, target, mirror, reason = tier_of(key, g, vault)
        if conf == "low":
            tier = 2
        whys = sorted(g["whys"], key=lambda x: x[0])
        p = {"key": key, "source": g["source"], "tier": tier, "confidence": conf, "target": target, "mirror": mirror,
             "reason": reason, "sessions": len(days), "in_window": sum(1 for d in days if d >= a["lo_window"]),
             "first": _iso(days[0]), "last": _iso(days[-1]),
             "session_ids": [s[:8] for s in sids[:6]], "projects": sorted(g["projects"])[:4],
             "title": title_of(g), "context": plain(whys[-1][1], 200) if whys else "",
             "samples": [plain(t, 160) for _, _, t in sorted(g["texts"], key=lambda x: x[0], reverse=True)[:3]],
             "files": sorted(plain(f, 120) for f in g["files"])[:10], "previous": None}
        if g["source"] == "telemetry":
            p.update({"tool": g["tool"], "error_class": g["error_class"], "calls": g["calls"]})
        else:
            p.update({"system": g["system"], "calls": len(days)})
        themes.append(p)
        prev = (state.get("patterns") or {}).get(key)
        if isinstance(prev, dict):
            when = _day(prev.get("tuned_at") or prev.get("reported_at"))
            if when and (today - when).days < COOLDOWN_DAYS:
                cooldown.append({"key": key, "tuned_at": _iso(when), "until": _iso(when + timedelta(days=COOLDOWN_DAYS))})
                continue
            p["previous"] = {k: prev.get(k) for k in ("tuned_at", "reported_at", "tier", "target", "change") if prev.get(k)}
        patterns.append(p)
    return a, patterns, cooldown, themes


# --- subcommands ----------------------------------------------------------------------------------

def cmd_plan(vault, today):
    P = paths(vault)
    state = _read_json(P["state"], {})
    a, patterns, cooldown, _ = build_patterns(vault, today, state)
    n = len(a["window_sessions"])
    order = {"generated": _iso(today), "window_days": WINDOW_DAYS, "sessions_in_window": n,
             "telemetry": a["telemetry"], "skipped_private": a["skipped_private"],
             "skipped_sensitive": a["skipped_sensitive"], "skipped_cooldown": cooldown}
    if n < MIN_WINDOW:
        order.update({"status": "not_enough_sessions", "patterns": [],
                      "audit_line": "tuning: not enough sessions yet (%d session%s in the last %d days)" % (
                          n, "" if n == 1 else "s", WINDOW_DAYS)})
    else:
        t1 = sum(1 for p in patterns if p["tier"] == 1)
        order.update({"status": "ok", "patterns": patterns,
                      "audit_line": "tuning: %d pattern%s over the bar (%d to apply, %d to report), %d in cooldown" % (
                          len(patterns), "" if len(patterns) == 1 else "s", t1, len(patterns) - t1, len(cooldown))})
    _write_json(P["order"], order)
    print(json.dumps(order, indent=1, ensure_ascii=False))
    return 0


def _fail(msg):
    print("self-tune: " + msg, file=sys.stderr)
    return 2


def cmd_record(vault, today, a):
    P = paths(vault)
    order = _read_json(P["order"], {})
    if order.get("generated") != _iso(today):
        return _fail("no work order for %s; run plan first" % _iso(today))
    if order.get("status") != "ok":
        return _fail("not enough sessions yet; nothing is applied tonight")
    p = next((x for x in order.get("patterns") or [] if x.get("key") == a.key), None)
    if p is None:
        return _fail("%s is not in tonight's work order (unknown, under the bar, or in cooldown)" % a.key)
    target = (a.target or "").replace("\\", "/").strip()
    while target.startswith("./"):
        target = target[2:]
    if a.tier == 1:
        if p["tier"] != 1:
            return _fail("%s is Tier 2: report it, never apply it" % a.key)
        if not target or NEVER_TIER1.search(target) or not TIER1_OK.match(target):
            return _fail("%s is not a plain-words file the system may change on its own" % (target or "(no target)"))
    state = _read_json(P["state"], {})
    pats = state.setdefault("patterns", {})
    prev = pats.get(a.key) or {}
    if _iso(today) in (prev.get("tuned_at"), prev.get("reported_at")):
        return _fail("%s was already changed or reported tonight (one change per pattern per night)" % a.key)
    change, why = plain(a.change, 160), plain(a.why, 200)
    entry = {"tier": a.tier, "target": plain(target, 160), "change": change, "why": why,
             "title": plain(a.title, 90) if a.title else p.get("title", ""),
             "sessions": p["sessions"], "first": p["first"], "last": p["last"]}
    if a.tier == 1:
        entry["tuned_at"] = _iso(today)
        if p.get("mirror"):
            entry["mirror"] = p["mirror"]
        line = "- tuned %s in %s: %s (why: %s; %d sessions, %s to %s)" % (
            a.key, entry["target"], change, why or p.get("reason", ""), p["sessions"], p["first"], p["last"])
    else:
        entry["reported_at"] = _iso(today)
        what = (p.get("error_class", "") + " in " + p.get("tool", "")) if p["source"] == "telemetry" else "system " + p.get("system", "")
        line = "- reported %s to your contact (%s): %s x%d, %s to %s" % (
            a.key, entry["target"] or "report", what, p.get("calls", p["sessions"]), p["first"], p["last"])
    if not a.dry_run:
        pats[a.key] = entry
        _write_json(P["state"], state)
    print(plain(line, 600))
    return 0


def cmd_themes(vault, today):
    P = paths(vault)
    state = _read_json(P["state"], {})
    order = _read_json(P["order"], {})
    store = state.get("themes") if isinstance(state.get("themes"), dict) else {}
    if order.get("generated") == _iso(today) and order.get("status") == "ok":
        _, _, _, current = build_patterns(vault, today, {})
        tuned = state.get("patterns") or {}
        for p in current:
            rec = tuned.get(p["key"]) or {}
            if rec.get("tuned_at"):
                ask = "Fixed %s: %s (%s)." % (rec["tuned_at"], rec.get("change", ""), rec.get("target", ""))
            elif rec.get("reported_at"):
                ask = "Reported to your contact %s; not something the system changes on its own." % rec["reported_at"]
            elif p["tier"] == 2:
                ask = "Goes to your contact as a report; the system does not change this on its own."
            else:
                ask = "Not fixed yet; the nightly run applies one fix when it is out of cooldown."
            old = store.get(p["key"]) if isinstance(store.get(p["key"]), dict) else {}
            store[p["key"]] = {"title": rec.get("title") or old.get("title") or p["title"], "sessions": p["sessions"],
                               "first": p["first"], "last": p["last"],
                               "root": rec.get("why") or old.get("root") or p["reason"], "evidence": p["session_ids"][:4],
                               "projects": p["projects"], "ask": plain(ask, 220)}
    cutoff = today - timedelta(days=THEME_TTL_DAYS)
    store = {k: v for k, v in store.items() if isinstance(v, dict) and (_day(v.get("last")) or date.min) >= cutoff}
    state["themes"] = store
    if not store and not os.path.exists(P["themes"]):
        if order.get("status") == "ok":
            _write_json(P["state"], state)
        print("themes: 0")
        return 0
    head = ["# Themes (read at session start; written nightly by Vault Hygiene from the System Journal)", "",
            "Generated %s. A theme needs 3+ sessions in 7 days, or 2 sessions 14+ days apart; it drops out after "
            "14 days without a new one. Max 40 lines." % _iso(today)]
    out = list(head)
    for key, v in sorted(store.items(), key=lambda kv: (kv[1].get("last", ""), kv[0]), reverse=True):
        block = ["", "## %s  (%d sessions, first %s, last %s)" % (plain(v.get("title"), 90), int(v.get("sessions") or 0),
                                                                    v.get("first", ""), v.get("last", "")),
                 "Root: " + plain(v.get("root") or "not yet known", 200),
                 "Evidence: " + (", ".join(plain(e, 12) for e in v.get("evidence") or []) or "none"),
                 "Ask: " + plain(v.get("ask"), 220),
                 "Projects: " + (", ".join(plain(x, 40) for x in v.get("projects") or []) or "all")]
        if len(out) + len(block) > THEMES_MAX_LINES:
            break
        out.extend(block)
    os.makedirs(os.path.dirname(P["themes"]), exist_ok=True)
    with open(P["themes"], "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    _write_json(P["state"], state)
    print("themes: %d" % (out.count("") - 1))
    return 0


def cmd_package(vault, today, only=None):
    order = _read_json(paths(vault)["order"], {})
    rows = (order.get("patterns") or []) if order.get("status") == "ok" else []
    # Named patterns only when --key is given (a Tier 1 pattern named here is one the step moved to Tier 2).
    rows = [p for p in rows if p.get("key") in only] if only else [p for p in rows if p.get("tier") == 2]
    if not rows:
        print("No reports tonight.")
        return 0
    print("Vault Hygiene found %d thing%s it must not change on its own (names and counts only):" % (
        len(rows), "" if len(rows) == 1 else "s"))
    for p in rows:
        if p["source"] == "telemetry":
            what = "error class %s, tool %s" % (p["error_class"], p["tool"])
        else:
            what = "system %s (%s confidence)" % (p.get("system", ""), p.get("confidence", ""))
        files = ", ".join(p.get("files") or []) or "none"
        print(plain("- %s: %s, x%d in %d sessions, %s to %s, files: %s" % (
            p["key"], what, p.get("calls", p["sessions"]), p["sessions"], p["first"], p["last"], files), 600))
    return 0


def cmd_summary(vault, today):
    state = _read_json(paths(vault)["state"], {})
    order = _read_json(paths(vault)["order"], {})
    lo = today - timedelta(days=WINDOW_DAYS - 1)
    tuned, reports = [], []
    for key, v in sorted((state.get("patterns") or {}).items()):
        if not isinstance(v, dict):
            continue
        d = _day(v.get("tuned_at"))
        if d and lo <= d <= today:
            tuned.append(v.get("change") or key)
        d = _day(v.get("reported_at"))
        if d and (today - d).days <= 1 and v.get("target"):
            reports.append(v["target"])
    if tuned:
        print(plain("Tuned %d thing%s this week: %s" % (len(tuned), "" if len(tuned) == 1 else "s", "; ".join(tuned)), 400))
    elif order.get("status") == "not_enough_sessions":
        print("Tuning: not enough sessions yet")
    else:
        print("Tuning: nothing needed this week")
    for r in sorted(set(reports)):
        print(plain("A short report for your contact is in %s: please send it to them as is." % r, 300))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "record", "themes", "package", "summary"):
        s = sub.add_parser(name)
        s.add_argument("--vault", default=os.getcwd())
        s.add_argument("--today", default="", help="YYYY-MM-DD (default: today)")
        if name == "package":
            s.add_argument("--key", action="append", default=[], help="only this pattern (repeat for several)")
        if name == "record":
            s.add_argument("--key", required=True)
            s.add_argument("--tier", type=int, choices=(1, 2), required=True)
            s.add_argument("--target", default="", help="Tier 1: the file changed; Tier 2: the report path or 'email'")
            s.add_argument("--change", required=True, help="plain words: what changed")
            s.add_argument("--why", default="", help="plain words: the root cause, for the audit log and Themes")
            s.add_argument("--title", default="", help="plain words: the theme's name (default: the newest sample)")
            s.add_argument("--dry-run", action="store_true", help="check the change is allowed and print the line; write nothing")
    a = ap.parse_args(argv)
    try:
        today = date.fromisoformat(a.today) if a.today else date.today()
    except ValueError:
        return _fail("--today must be YYYY-MM-DD")
    vault = os.path.abspath(a.vault)
    if a.cmd == "plan":
        return cmd_plan(vault, today)
    if a.cmd == "record":
        return cmd_record(vault, today, a)
    if a.cmd == "themes":
        return cmd_themes(vault, today)
    if a.cmd == "package":
        return cmd_package(vault, today, a.key)
    return cmd_summary(vault, today)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:  # fail open: a broken tuning step never breaks the nightly run
        print("self-tune: skipped (%s)" % type(e).__name__, file=sys.stderr)
        sys.exit(0)
