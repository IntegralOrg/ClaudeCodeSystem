#!/usr/bin/env python3
"""Vault audit: deterministic hygiene checks + concept-index bookkeeping.

Semantic judgment (concepts, merges) is done by Claude via the
/vault-audit command; this script never reads meaning, only structure.
Stdlib only, Python 3.9+.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import date, datetime, timedelta

ALWAYS_PROTECTED = [".git", ".git-cloud", ".claude", ".obsidian", "Attachments",
                    "node_modules", "cowork-commands", "_generated"]

# The audit's own operational files (schema, index, staged trash) live here,
# deliberately OUT of .claude/. Cloud `acceptEdits` auto-approves Edit/Write
# everywhere in the working dir EXCEPT under .claude/ (settings/hooks/commands
# can escalate the session), so a scheduled cloud routine that writes its
# receipt/schema there stalls on a permission prompt every run. _generated/ is
# both audit-protected (never swept) and auto-approved, so writes flow silently.
HYGIENE_DIR = os.path.join("_generated", "vault-hygiene")

# ---------- schema ----------

def extract_schema_block(md_text):
    m = re.search(r"```yaml\n(.*?)\n```", md_text, re.S)
    if not m:
        raise ValueError("no ```yaml block found in schema file")
    return m.group(1)


def parse_yaml_subset(text):
    lines = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, raw.strip()))
    value, _ = _parse_block(lines, 0, 0)
    return value


def _strip_inline_comment(s):
    """Drop a trailing ' #...' inline comment (whitespace before the hash) from a
    value, so `gate_high: 0.86  # note` parses as 0.86. Quote-aware: a '#' inside
    single or double quotes is preserved, so `owners: ["Acme #1"]` stays intact."""
    quote = None
    for i, ch in enumerate(s):
        if quote is not None:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and i > 0 and s[i - 1] in " \t":
            return s[:i].rstrip()
    return s


def _parse_scalar(s):
    s = _strip_inline_comment(s.strip())
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [_parse_scalar(x) for x in inner.split(",")] if inner else []
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    if s == "true":
        return True
    if s == "false":
        return False
    try:
        return int(s)
    except ValueError:
        return s


def _parse_block(lines, pos, indent):
    if pos >= len(lines):
        return {}, pos
    is_list = lines[pos][1].startswith("- ")
    result = [] if is_list else {}
    while pos < len(lines):
        ind, content = lines[pos]
        if ind < indent:
            break
        if ind > indent:
            raise ValueError("unexpected indent at: " + content)
        if is_list:
            if not content.startswith("- "):
                break
            item = content[2:].strip()
            if ":" in item and not item.startswith("["):
                key, _, val = item.partition(":")
                obj = {key.strip(): _parse_scalar(val)}
                pos += 1
                while pos < len(lines) and lines[pos][0] > ind:
                    k2, _, v2 = lines[pos][1].partition(":")
                    obj[k2.strip()] = _parse_scalar(v2)
                    pos += 1
                result.append(obj)
            else:
                result.append(_parse_scalar(item))
                pos += 1
        else:
            key, _, val = content.partition(":")
            if val.strip():
                result[key.strip()] = _parse_scalar(val)
                pos += 1
            else:
                pos += 1
                if pos < len(lines) and lines[pos][0] > ind:
                    sub, pos = _parse_block(lines, pos, lines[pos][0])
                else:
                    sub = None
                result[key.strip()] = sub
    return result, pos


def load_schema(vault):
    path = os.path.join(vault, HYGIENE_DIR, "vault-schema.md")
    if not os.path.exists(path):
        raise ValueError("schema missing: " + path)
    with open(path, encoding="utf-8") as f:
        return parse_yaml_subset(extract_schema_block(f.read()))


# ---------- walking + index ----------

def is_protected(rel, protected):
    rel = rel.replace(os.sep, "/").rstrip("/")
    for p in list(protected or []) + ALWAYS_PROTECTED:
        p = str(p).rstrip("/")
        if rel == p or rel.startswith(p + "/"):
            return True
    return False


def walk_vault(vault, protected):
    out = []
    for root, dirs, files in os.walk(vault):
        rel_root = os.path.relpath(root, vault).replace(os.sep, "/")
        if rel_root == ".":
            rel_root = ""
        dirs[:] = [d for d in sorted(dirs)
                   if not is_protected((rel_root + "/" + d).lstrip("/"), protected)]
        for f in sorted(files):
            if not f.endswith(".md"):
                continue
            rel = (rel_root + "/" + f).lstrip("/")
            if not is_protected(rel, protected):
                out.append(rel)
    return sorted(out)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _index_path(vault):
    return os.path.join(vault, HYGIENE_DIR, "vault-index.json")


def load_index(vault):
    path = _index_path(vault)
    if not os.path.exists(path):
        return {"meta": {}, "files": {}, "watched_clusters": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_index(vault, index):
    index["meta"]["last_run"] = date.today().isoformat()
    path = _index_path(vault)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=1, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, path)


def refresh_index(vault, index, files, today=None):
    """hash_since (Phase 5) records the day a row's content hash last changed;
    the staleness flag reads it. Rows from before the field exists are
    backfilled with today, so the 180-day clock starts honestly, not at zero."""
    today = today or date.today().isoformat()
    added, changed, deleted = [], [], []
    current = set(files)
    for rel in files:
        h = sha256_file(os.path.join(vault, rel))
        row = index["files"].get(rel)
        if row is None:
            index["files"][rel] = {"hash": h, "concept": "", "entities": [],
                                   "verdict": "", "stale": True, "hash_since": today}
            added.append(rel)
        elif row.get("hash") != h:
            row["hash"] = h
            row["stale"] = True
            row["hash_since"] = today
            changed.append(rel)
        elif not row.get("hash_since"):
            row["hash_since"] = today
    for rel in sorted(index["files"]):
        if rel not in current:
            del index["files"][rel]
            deleted.append(rel)
    index["watched_clusters"] = [c for c in index.get("watched_clusters", [])
                                 if all(p in index["files"] for p in c)]
    return added, changed, deleted


# ---------- structural checks ----------

def naming_regex(pattern):
    esc = re.escape(pattern)
    esc = esc.replace("YYYY", r"\d{4}").replace("MM", r"\d{2}").replace("DD", r"\d{2}")
    esc = esc.replace(r"\*", ".*")
    return re.compile("^" + esc + "$")


def _segment_matches(dirpath, pattern):
    """Check if dirpath matches pattern using segment-aware fnmatch.

    Both dirpath and pattern are split on "/" and fnmatch is applied
    per-segment. This prevents * from spanning directory boundaries.
    """
    dir_segs = dirpath.split("/")
    pat_segs = pattern.split("/")
    if len(dir_segs) != len(pat_segs):
        return False
    for d, p in zip(dir_segs, pat_segs):
        if not fnmatch.fnmatch(d, p):
            return False
    return True


def matching_folder(dirpath, folders, exact=False):
    best, best_len = None, -1
    for entry in folders or []:
        pat = str(entry.get("path", "")).rstrip("/")
        if not pat:
            continue
        if exact:
            if _segment_matches(dirpath, pat) and len(pat) > best_len:
                best, best_len = entry, len(pat)
            continue
        cur = dirpath
        while cur:
            if _segment_matches(cur, pat):
                if len(pat) > best_len:
                    best, best_len = entry, len(pat)
                break
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
    return best


def read_frontmatter_keys_and_body(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            fm = text[4:end]
            keys = [ln.partition(":")[0].strip() for ln in fm.splitlines()
                    if ":" in ln and not ln.startswith((" ", "-", "#"))]
            return keys, text[end + 4:]
    return [], text


def read_frontmatter_values(path):
    """Parse the handful of top-level scalar frontmatter keys the invariant
    check needs: canonical (bool), status (str), superseded_by (wikilink text).
    Line scan only; not a full YAML parser."""
    vals = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return vals
    if not text.startswith("---\n"):
        return vals
    end = text.find("\n---", 4)
    if end == -1:
        return vals
    for ln in text[4:end].splitlines():
        if not ln or ln.startswith((" ", "-", "#")) or ":" not in ln:
            continue
        key, _, raw = ln.partition(":")
        key = key.strip()
        val = _strip_inline_comment(raw.strip())
        if key == "canonical":
            vals["canonical"] = (val.strip("\"'").lower() == "true")
        elif key == "status":
            vals["status"] = val.strip("\"'")
        elif key == "superseded_by":
            m = re.search(r"\[\[([^\]|#]+)", val)
            vals["superseded_by"] = m.group(1).strip() if m else val.strip("\"'")
    return vals


def resolve_wikilink(target_text, files):
    forms = {}
    for t in files:
        for form in _link_forms(t):
            forms[form] = t
    return forms.get(target_text)


def invariant_check(vault, files, index=None):
    """Deterministic integrity check over docs carrying a canonical/superseded
    marker. Returns violation strings shaped invariant:<rule>:<rel>. Never
    modifies anything; the audit fails loudly rather than silently drifting."""
    violations = []
    marks = {}
    for rel in files:
        vals = read_frontmatter_values(os.path.join(vault, rel))
        if vals.get("canonical") or vals.get("status") == "superseded":
            marks[rel] = vals
    superseded = {rel for rel, v in marks.items() if v.get("status") == "superseded"}
    for rel, v in sorted(marks.items()):
        is_canon = bool(v.get("canonical"))
        is_sup = v.get("status") == "superseded"
        if is_canon and is_sup:
            violations.append("invariant:canonical_and_superseded:" + rel)
        if is_sup:
            target = v.get("superseded_by")
            if not target:
                violations.append("invariant:superseded_no_pointer:" + rel)
                continue
            resolved = resolve_wikilink(target, files)
            if resolved is None:
                violations.append("invariant:dangling_superseded_by:" + rel)
            elif resolved in superseded:
                violations.append("invariant:superseded_chain:" + rel)
    violations.extend(_cluster_invariants(marks, index))
    return violations


STALE_CANONICAL_DAYS = 180


def stale_days_from_schema(schema):
    """Config, not a constant: the staleness threshold may be set in the
    schema's `embedding:` block (`stale_days: N`). Falls back to the default."""
    cfg = (schema or {}).get("embedding") or {}
    try:
        return int(cfg.get("stale_days", STALE_CANONICAL_DAYS))
    except (TypeError, ValueError):
        return STALE_CANONICAL_DAYS


def stale_canonical(vault, files, index, days=STALE_CANONICAL_DAYS, today=None):
    """Report-only staleness flag (Phase 5): a doc stamped canonical whose
    content hash has not changed in `days`. Drift in a canonical doc is the
    failure the research called near-invisible; this makes it visible. Returns
    [{rel, hash_since, days_unchanged}] sorted oldest first."""
    today_d = date.fromisoformat(today) if today else date.today()
    rows = (index or {}).get("files") or {}
    out = []
    for rel in files:
        row = rows.get(rel)
        since = (row or {}).get("hash_since")
        if not since:
            continue
        vals = read_frontmatter_values(os.path.join(vault, rel))
        if not vals.get("canonical"):
            continue
        try:
            age = (today_d - date.fromisoformat(since)).days
        except ValueError:
            continue
        if age > days:
            out.append({"rel": rel, "hash_since": since, "days_unchanged": age})
    out.sort(key=lambda r: (-r["days_unchanged"], r["rel"]))
    return out


def _cluster_invariants(marks, index):
    """A confirmed fork/duplicate cluster must hold exactly one canonical.
    No-op until Phase 2 populates canonical_judgments."""
    if not index:
        return []
    judgments = index.get("canonical_judgments") or {}
    adj = {}
    for j in judgments.values():
        if j.get("status") != "confirmed":
            continue
        if j.get("verdict") not in ("version-fork", "duplicate"):
            continue
        a, b = j.get("relA"), j.get("relB")
        if not a or not b:
            continue
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    seen = set()
    out = []
    for node in sorted(adj):
        if node in seen:
            continue
        stack = [node]
        comp = []
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            comp.append(x)
            stack.extend(adj.get(x, ()))
        canon = [r for r in comp if marks.get(r, {}).get("canonical")]
        if len(canon) != 1:
            out.append("invariant:cluster_multi_canonical:" + "+".join(sorted(comp)))
    return out


def structural_checks(vault, schema, files):
    findings = {"root_clutter": [], "unknown_folder": [], "naming_violations": [],
                "missing_frontmatter": [], "empty_stubs": []}
    whitelist = set(schema.get("root_whitelist") or [])
    folders = schema.get("folders") or []
    required = schema.get("frontmatter_required") or []
    # Per-file frontmatter exemptions (glob patterns matched against rel path).
    # For repo-canonical mirror files that refuse local edits / are overwritten
    # on their next sync, so stamping vault frontmatter is futile and corrupting.
    fm_exempt = schema.get("frontmatter_exempt") or []
    now = time.time()
    for rel in files:
        full = os.path.join(vault, rel)
        d = os.path.dirname(rel)
        name = os.path.basename(rel)
        stem = name[:-3]
        if d == "":
            if name not in whitelist:
                findings["root_clutter"].append(rel)
            continue
        if matching_folder(d, folders) is None:
            findings["unknown_folder"].append(rel)
        exact = matching_folder(d, folders, exact=True)
        if exact and exact.get("naming"):
            if not naming_regex(str(exact["naming"])).match(stem):
                findings["naming_violations"].append(rel)
        # Records under a no_merge folder are never merged, split, or
        # rewritten, so neither check below fires for them: adding
        # frontmatter is a rewrite, and staging/expanding a stub is too.
        if is_record(d, schema):
            continue
        keys, body = read_frontmatter_keys_and_body(full)
        exempt = any(fnmatch.fnmatch(rel, pat) for pat in fm_exempt)
        if required and not exempt and not all(k in keys for k in required):
            findings["missing_frontmatter"].append(rel)
        if len("".join(body.split())) < 40 and (now - os.path.getmtime(full)) > 3 * 86400:
            findings["empty_stubs"].append(rel)
    return findings


def find_exact_duplicates(vault, files, schema):
    # Records under a no_merge folder are never staged, merged, or
    # repointed, so they never enter duplicate repair (same reasoning as
    # the stub/frontmatter exclusions in structural_checks).
    by_hash = {}
    for rel in files:
        if is_record(os.path.dirname(rel), schema):
            continue
        by_hash.setdefault(sha256_file(os.path.join(vault, rel)), []).append(rel)
    return [sorted(v) for v in by_hash.values() if len(v) > 1]


def no_merge_paths(schema):
    return [f["path"] for f in (schema.get("folders") or []) if f.get("no_merge")]


def is_record(dirpath, schema):
    """True if dirpath (or an ancestor) belongs to a no_merge folder.

    Uses matching_folder's segment-aware ancestor walk rather than plain
    prefix matching, so wildcard patterns like Work/Clients/*/Transcripts
    correctly match a real path such as Work/Clients/Acme/Transcripts.
    is_protected()-style prefix matching never matches those, since "*"
    isn't a literal path segment any real directory can prefix-equal.
    """
    entry = matching_folder(dirpath, schema.get("folders") or [])
    return bool(entry and entry.get("no_merge"))


# ---------- links, staging, purge ----------

WIKILINK = re.compile(r"\[\[([^\]|#]+)")


def _link_forms(target):
    """All wikilink text forms that should resolve to this target: the bare
    basename stem, plus every path-qualified suffix ending at the stem
    (e.g. for Resources/Reference/Server Logins.md: 'Server Logins',
    'Reference/Server Logins', 'Resources/Reference/Server Logins')."""
    stem_path = target[:-3] if target.endswith(".md") else target
    parts = stem_path.split("/")
    return ["/".join(parts[i:]) for i in range(len(parts))]


def inbound_links(vault, targets, files):
    forms = {}
    for t in targets:
        for form in _link_forms(t):
            forms[form] = t
    result = {t: [] for t in targets}
    for rel in files:
        if rel in targets:
            continue
        try:
            with open(os.path.join(vault, rel), encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        hits = set()
        for m in WIKILINK.finditer(text):
            name = m.group(1).strip()
            if name in forms:
                hits.add(forms[name])
        for t in hits:
            result[t].append(rel)
    return result


def stage_files(vault, rels, today=None):
    schema = load_schema(vault)
    protected = schema.get("protected", [])
    day = today or date.today().isoformat()
    dest_dir = os.path.join(vault, HYGIENE_DIR, "audit-trash", day)
    os.makedirs(dest_dir, exist_ok=True)
    index = load_index(vault)
    for rel in rels:
        # Validation checks
        if not rel.endswith(".md"):
            sys.stderr.write("warning: skipping %s (not .md)\n" % rel)
            continue
        if ".." in rel or os.path.isabs(rel):
            sys.stderr.write("warning: skipping %s (contains .. or is absolute)\n" % rel)
            continue
        if is_protected(rel, protected):
            sys.stderr.write("warning: skipping %s (protected)\n" % rel)
            continue
        src = os.path.join(vault, rel)
        if not os.path.isfile(src):
            sys.stderr.write("warning: skipping %s (not a regular file)\n" % rel)
            continue
        # All checks passed, stage the file. Preserve the relative directory
        # structure under the dated trash dir instead of flattening the path
        # into the filename: two distinct paths (e.g. "a/b__c.md" and
        # "a__b/c.md") can otherwise collide on the same flattened name.
        dest = os.path.join(dest_dir, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(src, dest)
        index["files"].pop(rel, None)
    index["watched_clusters"] = [c for c in index.get("watched_clusters", [])
                                 if all(p in index["files"] for p in c)]
    save_index(vault, index)


def purge_trash(vault, days=7):
    base = os.path.join(vault, HYGIENE_DIR, "audit-trash")
    if not os.path.isdir(base):
        return 0
    cutoff = date.today() - timedelta(days=days)
    n = 0
    for name in sorted(os.listdir(base)):
        try:
            d = datetime.strptime(name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if d < cutoff:
            shutil.rmtree(os.path.join(base, name))
            n += 1
    return n


def apply_row_update(vault, rel, concept, entities, verdict):
    index = load_index(vault)
    row = index["files"].get(rel)
    if row is None:
        raise SystemExit("not in index: " + rel)
    row["concept"] = concept or row["concept"]
    if entities is not None:
        row["entities"] = entities
    if verdict is not None:
        row["verdict"] = verdict
    row["stale"] = False
    save_index(vault, index)


# ---------- CLI ----------

def cmd_scan(args):
    schema = load_schema(args.vault)
    protected = schema.get("protected", [])
    purged = 0 if getattr(args, "no_purge", False) else purge_trash(args.vault)
    files = walk_vault(args.vault, protected)
    index = load_index(args.vault)
    added, changed, deleted = refresh_index(args.vault, index, files)
    save_index(args.vault, index)
    order = structural_checks(args.vault, schema, files)
    order.update({
        "added": added, "changed": changed, "deleted": deleted,
        "exact_duplicates": find_exact_duplicates(args.vault, files, schema),
        "stale": sorted(r for r, row in index["files"].items() if row.get("stale")),
        "watched_clusters": index.get("watched_clusters", []),
        "no_merge_paths": no_merge_paths(schema),
        "trash_purged": purged, "file_count": len(files),
        "invariant_violations": invariant_check(args.vault, files, index),
        "stale_canonical": stale_canonical(args.vault, files, index,
                                           days=stale_days_from_schema(schema)),
    })
    print(json.dumps(order, indent=1, ensure_ascii=False))


def cmd_invariant(args):
    schema = load_schema(args.vault)
    files = walk_vault(args.vault, schema.get("protected", []))
    print(json.dumps(invariant_check(args.vault, files, load_index(args.vault)),
                     indent=1, ensure_ascii=False))


def cmd_links(args):
    schema = load_schema(args.vault)
    files = walk_vault(args.vault, schema.get("protected", []))
    print(json.dumps(inbound_links(args.vault, args.files, files),
                     indent=1, ensure_ascii=False))


def cmd_stage(args):
    stage_files(args.vault, args.files)
    print("staged: " + ", ".join(args.files))


def cmd_update_row(args):
    entities = None
    if args.entities is not None:
        entities = [e.strip() for e in args.entities.split(",") if e.strip()]
    apply_row_update(args.vault, args.file, args.concept, entities, args.verdict)


def cmd_bulk_update(args):
    with open(args.json, encoding="utf-8") as f:
        rows = json.load(f)
    index = load_index(args.vault)
    for r in rows:
        row = index["files"].get(r["file"])
        if row is None:
            continue
        row["concept"] = r.get("concept", row["concept"])
        row["entities"] = r.get("entities", row["entities"])
        row["verdict"] = r.get("verdict", row["verdict"])
        row["stale"] = False
    save_index(args.vault, index)
    print("updated %d rows" % len(rows))


def cmd_watch(args):
    index = load_index(args.vault)
    cluster = sorted(args.files)
    if cluster not in index["watched_clusters"]:
        index["watched_clusters"].append(cluster)
    save_index(args.vault, index)
    print("watching: " + ", ".join(cluster))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn, extra in [
        ("scan", cmd_scan, []),
        ("links", cmd_links, ["files"]),
        ("stage", cmd_stage, ["files"]),
        ("watch", cmd_watch, ["files"]),
        ("invariant", cmd_invariant, []),
    ]:
        sp = sub.add_parser(name)
        sp.add_argument("--vault", required=True)
        if extra:
            sp.add_argument("files", nargs="+")
        sp.set_defaults(func=fn)
        if name == "scan":
            sp.add_argument("--no-purge", action="store_true",
                            help="skip the 7-day trash purge (freshness gate: input not current)")
    sp = sub.add_parser("update-row")
    sp.add_argument("--vault", required=True)
    sp.add_argument("--file", required=True)
    sp.add_argument("--concept", default=None)
    sp.add_argument("--entities", default=None)
    sp.add_argument("--verdict", default=None)
    sp.set_defaults(func=cmd_update_row)
    sp = sub.add_parser("bulk-update")
    sp.add_argument("--vault", required=True)
    sp.add_argument("--json", required=True)
    sp.set_defaults(func=cmd_bulk_update)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
