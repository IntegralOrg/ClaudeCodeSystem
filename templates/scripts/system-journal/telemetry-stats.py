#!/usr/bin/env python3
"""Tool-call telemetry from the System Journal's evidence files (evidence/2 adds ok / ms /
error_class per call and tokens_by_model per session; evidence/1 files are read as "unknown").

Usage:
  telemetry-stats.py [--since-days 7] [--group-by tool|repo|session|model|day] [--json]
  telemetry-stats.py --session <id> [--json]        # one session: errors, slowest calls, tokens

Stdlib only. Reads files, never the transcripts, never the network. The store is the project:
this is the same script in every vault built from the template.
"""
import argparse
import glob
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone, tzinfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import resolve_vault  # noqa: E402

GROUPS = ("tool", "repo", "session", "model", "day")
SESSION_KEYED = ("repo", "session", "day")
# None means the machine's local zone, applied per timestamp (so a daylight-saving change inside the
# window still lands each call on the right local day). SYSTEM_JOURNAL_TZ names a zone instead;
# --tz NAME overrides either.
DEFAULT_TZ = os.environ.get("SYSTEM_JOURNAL_TZ") or None


def _parse_ts(s):
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _tz(name):
    """Accept an IANA zone name, a ready tzinfo object, or None (the machine's local zone, resolved
    per timestamp by datetime.astimezone). An unknown name falls back to UTC."""
    if name is None or isinstance(name, tzinfo):
        return name
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        return timezone.utc


def repo_of(rec):
    cwd = rec.get("cwd") or ""
    if cwd:
        return os.path.basename(cwd.rstrip("/")) or cwd
    return rec.get("project") or "unknown"


def _well_formed(rec):
    """True when the record's consumed fields have the shape the report code expects."""
    if not isinstance(rec, dict) or not rec.get("session_id"):
        return False
    turns = rec.get("turns")
    if turns is not None:
        if not isinstance(turns, list) or not all(isinstance(t, dict) for t in turns):
            return False
        for t in turns:
            tools = t.get("tools")
            if tools is not None and (not isinstance(tools, list) or not all(isinstance(x, dict) for x in tools)):
                return False
    for field in ("models", "tokens_by_model"):
        v = rec.get(field)
        if v is not None and not isinstance(v, dict):
            return False
    tbm = rec.get("tokens_by_model")
    if tbm and not all(isinstance(v, dict) for v in tbm.values()):
        return False
    return True


def calls_of(rec):
    for turn in rec.get("turns") or []:
        if turn.get("role") != "assistant":
            continue
        for t in turn.get("tools") or []:
            yield turn.get("t"), t


def load_records(vault, since_days, now=None):
    now_dt = _parse_ts(now) if now else datetime.now(timezone.utc)
    cutoff = now_dt - timedelta(days=since_days)
    out = []
    skipped = 0
    for path in sorted(glob.glob(os.path.join(vault, "_generated", "system-journal", "evidence", "*", "*.json"))):
        try:
            with open(path) as f:
                rec = json.load(f)
        except (OSError, ValueError):
            skipped += 1
            continue
        if not _well_formed(rec):
            skipped += 1
            continue
        ended = _parse_ts(rec.get("ended") or rec.get("started") or "")
        if ended is None or ended < cutoff:
            continue
        out.append(rec)
    if skipped:
        print(f"telemetry-stats: skipped {skipped} unreadable or malformed evidence file(s)", file=sys.stderr)
    return out


def _pct(sorted_vals, p):
    """Nearest-rank percentile: p50 of [100, 300] is 100, p95 is 300."""
    if not sorted_vals:
        return None
    i = max(0, min(len(sorted_vals) - 1, math.ceil(p / 100.0 * len(sorted_vals)) - 1))
    return sorted_vals[i]


def _tokens_zero():
    return {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}


def _add_tokens(acc, t):
    for k in acc:
        acc[k] += int((t or {}).get(k) or 0)


def _session_key(rec, group_by, tz):
    """Compute the group key for a session in repo/session/day groupings."""
    if group_by == "repo":
        return repo_of(rec)
    elif group_by == "session":
        return rec["session_id"]
    else:
        dt = _parse_ts(rec.get("ended") or rec.get("started") or "")
        return dt.astimezone(tz).strftime("%Y-%m-%d") if dt else "unknown"


def summarize(records, group_by, tz_name=DEFAULT_TZ):
    tz = _tz(tz_name)
    is_v2 = {r["session_id"]: r.get("schema") == "evidence/2" for r in records}
    groups = {}

    def bucket(key):
        return groups.setdefault(key, {"calls": [], "sessions": set(), "v2_sessions": set(), "model_tokens": _tokens_zero()})

    if group_by in ("repo", "session", "day"):
        for rec in records:
            sid = rec["session_id"]
            key = _session_key(rec, group_by, tz)
            b = bucket(key)
            b["sessions"].add(sid)
            if is_v2[sid]:
                b["v2_sessions"].add(sid)
                for tok in (rec.get("tokens_by_model") or {}).values():
                    _add_tokens(b["model_tokens"], tok)
        for rec in records:
            sid = rec["session_id"]
            key = _session_key(rec, group_by, tz)
            b = bucket(key)
            for ts, t in calls_of(rec):
                b["calls"].append((t, is_v2[sid]))
    elif group_by == "tool":
        for rec in records:
            sid = rec["session_id"]
            for ts, t in calls_of(rec):
                key = t.get("name") or "?"
                b = bucket(key)
                b["calls"].append((t, is_v2[sid]))
                b["sessions"].add(sid)
                if is_v2[sid]:
                    b["v2_sessions"].add(sid)
    else:
        for rec in records:
            sid = rec["session_id"]
            for ts, t in calls_of(rec):
                key = next(iter(rec.get("models") or {}), "unknown")
                b = bucket(key)
                b["calls"].append((t, is_v2[sid]))
                b["sessions"].add(sid)
                if is_v2[sid]:
                    b["v2_sessions"].add(sid)
            for model_id, tok in (rec.get("tokens_by_model") or {}).items():
                b = bucket(model_id)
                b["sessions"].add(sid)
                if is_v2[sid]:
                    b["v2_sessions"].add(sid)
                _add_tokens(b["model_tokens"], tok)

    out = []
    for key, b in groups.items():
        answered = [t for t, v2 in b["calls"] if "ok" in t]
        unknown = sum(1 for t, v2 in b["calls"] if not v2)
        pending = sum(1 for t, v2 in b["calls"] if v2 and "ok" not in t)
        errors = [t for t in answered if not t["ok"]]
        classes = {}
        for e in errors:
            classes[e.get("error_class") or "tool_error"] = classes.get(e.get("error_class") or "tool_error", 0) + 1
        durations = sorted(t["ms"] for t in answered if isinstance(t.get("ms"), int))
        tokens = None
        if group_by in SESSION_KEYED:
            tokens = b["model_tokens"] if bool(b["v2_sessions"]) else None
        elif group_by == "model":
            tokens = b["model_tokens"] if bool(b["v2_sessions"]) else None
        out.append({
            "key": key, "calls": len(b["calls"]), "answered": len(answered), "errors": len(errors),
            "pending": pending, "unknown": unknown,
            "error_rate": (round(len(errors) / len(answered), 3) if answered else None),
            "p50_ms": _pct(durations, 50), "p95_ms": _pct(durations, 95), "sessions": len(b["sessions"]),
            "top_error_classes": dict(sorted(classes.items(), key=lambda kv: (-kv[1], kv[0]))), "tokens": tokens,
        })
    return sorted(out, key=lambda g: (-g["calls"], g["key"]))


def session_detail(rec):
    calls = [dict(t, t=ts) for ts, t in calls_of(rec)]
    answered = [t for t in calls if "ok" in t]
    errors = [{"name": t.get("name") or "?", "input": t.get("input"), "ms": t.get("ms"), "error_class": t.get("error_class") or "tool_error"}
              for t in answered if not t["ok"]]
    slowest = sorted((t for t in answered if isinstance(t.get("ms"), int)), key=lambda t: -t["ms"])[:10]
    tokens = _tokens_zero()
    for tok in (rec.get("tokens_by_model") or {}).values():
        _add_tokens(tokens, tok)
    return {
        "session_id": rec["session_id"], "repo": repo_of(rec), "started": rec.get("started"), "ended": rec.get("ended"),
        "schema": rec.get("schema"), "models": rec.get("models") or {}, "tokens": tokens,
        "calls": len(calls), "answered": len(answered), "errors": errors,
        "pending": sum(1 for t in calls if "ok" not in t) if rec.get("schema") == "evidence/2" else 0,
        "unknown": len(calls) if rec.get("schema") != "evidence/2" else 0,
        "slowest": [{"name": t.get("name") or "?", "input": t.get("input"), "ms": t["ms"]} for t in slowest],
        "by_tool": sorted(((n, sum(1 for t in calls if t.get("name") == n)) for n in {t.get("name") for t in calls}),
                          key=lambda kv: (-kv[1], str(kv[0]))),
    }


def _print_groups(result):
    print(f"{result['group_by']:<10} calls  err  rate   p50ms  p95ms  sess  top errors")
    for g in result["groups"]:
        rate = "" if g["error_rate"] is None else f"{g['error_rate']:.0%}"
        top = ", ".join(f"{k}:{v}" for k, v in list(g["top_error_classes"].items())[:3])
        p50 = "" if g["p50_ms"] is None else g["p50_ms"]
        p95 = "" if g["p95_ms"] is None else g["p95_ms"]
        print(f"{str(g['key'])[:28]:<28} {g['calls']:>5} {g['errors']:>4} {rate:>5} {p50:>6} {p95:>6} {g['sessions']:>5}  {top}")
    print(f"total: {result['total_calls']} calls in {result['sessions']} sessions since {result['since']}")


def _print_session(d):
    print(f"session {d['session_id']} ({d['repo']}) {d['started']} -> {d['ended']} schema {d['schema']}")
    print(f"calls {d['calls']}, answered {d['answered']}, errors {len(d['errors'])}, pending {d['pending']}, unknown {d['unknown']}; tokens {d['tokens']}")
    for e in d["errors"]:
        print(f"  ERR {e['error_class']:<18} {e['name']:<10} {e['ms']!s:>7}ms  {e['input']}")
    for s in d["slowest"]:
        print(f"  SLOW {s['ms']:>7}ms {s['name']:<10} {s['input']}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=resolve_vault())
    ap.add_argument("--since-days", type=float, default=7)
    ap.add_argument("--group-by", choices=GROUPS, default="tool")
    ap.add_argument("--session", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--tz", default=DEFAULT_TZ, help="zone name (default: this machine's local zone)")
    ap.add_argument("--now", default="", help="TEST ONLY: ISO timestamp standing in for now")
    args = ap.parse_args(argv)

    if args.session:
        records = load_records(args.vault, 36500, args.now or None)
        rec = next((r for r in records if r.get("session_id") == args.session), None)
        if rec is None:
            print(f"no evidence file for session {args.session}", file=sys.stderr)
            return 1
        d = session_detail(rec)
        print(json.dumps(d, indent=1)) if args.json else _print_session(d)
        return 0

    records = load_records(args.vault, args.since_days, args.now or None)
    now_dt = _parse_ts(args.now) if args.now else datetime.now(timezone.utc)
    result = {
        "since": (now_dt - timedelta(days=args.since_days)).isoformat(timespec="seconds"),
        "group_by": args.group_by, "sessions": len(records),
        "total_calls": sum(1 for r in records for _ in calls_of(r)),
        "groups": summarize(records, args.group_by, args.tz),
    }
    print(json.dumps(result, indent=1)) if args.json else _print_groups(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
