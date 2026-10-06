#!/usr/bin/env python3
"""Vault embedding + same-subject canonical detection.

Local, in-process embedding (fastembed / bge-small, ONNX/CPU). No data leaves the
machine except a one-time model-weights download. report, judge, survivorship,
queue, and migrate write only the vector cache, candidate JSON, the review queue,
and a markdown report under _generated/vault-hygiene/; `apply` is the ONLY path
that modifies an authored doc, and only on a human-decided review-queue block
(fold and retire). All decision logic is pure stdlib and testable without numpy
or fastembed; the model and matrix math are lazily imported in the embed path.

Real run: uv run --python 3.12 --with fastembed,numpy scripts/vault-embed.py report --vault "$VAULT"
Phase 2 (stdlib-only, no deps): `pending` hands unjudged pairs to Claude, `judge`
validates + caches verdicts in vault-index.json canonical_judgments. Phase 3:
`survivorship` + the review queue. Phase 4: `apply` is the ONLY path that modifies
an authored doc, and only on a human-decided queue block (fold and retire).
"""
import argparse
import difflib
import hashlib
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import math
import os
import re
import sys
from datetime import date

HYGIENE_DIR = os.path.join("_generated", "vault-hygiene")
VECTOR_MODEL = "bge-small-en-v1.5"
DIMS = 384
# The entity-gate drops the vault owner (and, for a company vault, the company's
# own name) before measuring entity overlap: a shared owner/company entity is not
# a real linking signal. This is per-vault, so it ships EMPTY and is supplied by
# config (the schema's `embedding:` block, key `owners:`) or the --owner flag.
DEFAULT_OWNERS = ()
GATE_HIGH = 0.86
GATE_FALLBACK = 0.90

# ---- reuse vault-audit.py (hyphenated filename -> importlib) ----
_AUDIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vault-audit.py")
_aspec = importlib.util.spec_from_file_location("vault_audit", _AUDIT)
va = importlib.util.module_from_spec(_aspec)
_aspec.loader.exec_module(va)

FM_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)


# ---------- config (schema `embedding:` block; CLI flags override) ----------
# Config, not constants: the owner/company exclusion list, the cosine gate
# thresholds, the staleness window, and the canonical-home folders live in the
# vault-schema.md `embedding:` block so each vault tunes them without touching
# code. Example:
#   embedding:
#     owners: [Acme Corp]          # owner/company entities dropped before overlap
#     gate_high: 0.86              # cosine gate when both docs share a non-owner entity
#     gate_fallback: 0.90          # single-signal gate (entity-less or disjoint docs)
#     stale_days: 180              # canonical-doc staleness window (read by vault-audit)
#     canonical_home_dirs: [Resources/Reference, Resources/SOPs]

def _as_list(v):
    if v is None:
        return []
    return [v] if isinstance(v, str) else list(v)


def load_embed_config(schema):
    cfg = (schema or {}).get("embedding") or {}

    def _num(key, default, cast):
        try:
            return cast(cfg[key])
        except (KeyError, TypeError, ValueError):
            return default

    home = tuple(str(d).strip() for d in _as_list(cfg.get("canonical_home_dirs")) if str(d).strip())
    return {
        "owners": tuple(str(o).strip().lower() for o in _as_list(cfg.get("owners")) if str(o).strip()),
        "gate_high": _num("gate_high", GATE_HIGH, float),
        "gate_fallback": _num("gate_fallback", GATE_FALLBACK, float),
        "stale_days": _num("stale_days", 180, int),
        "canonical_home_dirs": home or CANONICAL_HOME_DIRS,
    }


# ---------- pure helpers ----------

def strip_frontmatter(text):
    return FM_RE.sub("", text, count=1)


def embed_input(title, concept, body):
    return f"{title}\n{concept or ''}\n{(body or '')[:1500]}"


def embed_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize(vec):
    n = math.sqrt(sum(x * x for x in vec))
    if n < 1e-12:
        return list(vec)
    return [x / n for x in vec]


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return dot / (na * nb)


# ---------- entity gate ----------

def non_owner_entities(entities, owners):
    owners = {o.lower() for o in owners}
    return {e.lower() for e in (entities or [])} - owners


def shared_non_owner_entity(a_ents, b_ents, owners):
    a = non_owner_entities(a_ents, owners)
    b = non_owner_entities(b_ents, owners)
    return bool(a & b)


def passes_gate(cos, a_ents, b_ents, owners, high=0.86, fallback=0.90):
    a = non_owner_entities(a_ents, owners)
    b = non_owner_entities(b_ents, owners)
    # Two-signal path: both docs are entity-tagged AND share a non-owner entity.
    if a and b and (a & b):
        return cos >= high
    # Otherwise (entity-less doc, or disjoint entities): single-signal fallback.
    return cos >= fallback


# ---------- pre-filters / pair id / scope ----------

NUMBERED_RE = re.compile(r"^\d{2,}[-_. ]")
# A date prefix (YYYY-MM-DD) is not a series number: two dated docs in one
# folder are the classic fork shape (Phase 3 correction; the AI Ladder pilot
# pair was dropped as "numbered siblings" before this).
DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _parent(rel):
    return os.path.dirname(rel)


def _base(rel):
    return os.path.basename(rel)


def is_numbered_series_pair(relA, relB):
    if _parent(relA) != _parent(relB):
        return False
    if DATE_PREFIX_RE.match(_base(relA)) or DATE_PREFIX_RE.match(_base(relB)):
        return False
    return bool(NUMBERED_RE.match(_base(relA))) and bool(NUMBERED_RE.match(_base(relB)))


def is_template_instance_pair(relA, relB):
    if _parent(relA) == _parent(relB):
        return False
    return _base(relA) == _base(relB)


def pair_id(relA, hashA, relB, hashB):
    key = "\n".join(sorted([relA, hashA, relB, hashB]))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def already_judged(pid, judgments):
    """A withdrawn judgment (a doc of the pair vanished before apply) or a stale one
    (a doc changed between judgment and apply) does not count: if the pair ever
    reappears unchanged it is judged afresh."""
    j = (judgments or {}).get(pid)
    return j is not None and j.get("status") not in ("withdrawn", "stale")


def prefiltered(relA, relB):
    if is_numbered_series_pair(relA, relB):
        return "numbered_series"
    if is_template_instance_pair(relA, relB):
        return "template_instance"
    return None


ARCHIVE_SEG_RE = re.compile(r"^Archive(?!\w)")


def in_scope(rel, schema):
    # Spec: an archived doc is a retired decision. The schema only protects the
    # root Archive/; any folder segment named Archive (or "Archive - X") is out.
    if any(ARCHIVE_SEG_RE.match(seg) for seg in rel.split("/")[:-1]):
        return False
    return not va.is_record(os.path.dirname(rel), schema)


def watched_pairs_from_index(index):
    pairs = set()
    for cl in index.get("watched_clusters", []):
        cl = sorted(cl)
        for a in range(len(cl)):
            for b in range(a + 1, len(cl)):
                pairs.add((cl[a], cl[b]))
    return pairs


# ---------- doc loading + embed cache ----------

def load_scope_docs(vault, schema, index):
    docs = []
    for rel, row in index.get("files", {}).items():
        if not in_scope(rel, schema):
            continue
        full = os.path.join(vault, rel)
        if not os.path.exists(full):
            continue
        try:
            with open(full, encoding="utf-8", errors="ignore") as f:
                raw = f.read()
        except OSError:
            continue
        body = strip_frontmatter(raw).strip()
        concept = row.get("concept") or ""
        title = os.path.splitext(os.path.basename(rel))[0]
        text = embed_input(title, concept, body)
        docs.append({
            "rel": rel, "title": title, "concept": concept,
            "entities": list(row.get("entities") or []),
            "text": text, "embed_hash": embed_hash(text),
            "hash": row.get("hash") or "",
        })
    return docs


def _vectors_path(vault):
    return os.path.join(vault, HYGIENE_DIR, "vault-vectors.json")


def load_vectors(vault):
    path = _vectors_path(vault)
    if not os.path.exists(path):
        return {"meta": {"vector_model": VECTOR_MODEL, "dims": DIMS}, "files": {}}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_vectors(vault, cache):
    path = _vectors_path(vault)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, path)


INSTALL_CMD = [sys.executable, "-m", "pip", "install", "--quiet", "fastembed", "numpy"]


def ensure_fastembed(auto_install=False, runner=None, log=None):
    """Phase 5: the nightly run self-installs its one heavy dependency at run
    start (cloud: ~10 s, proven 2026-09-18). Returns True when fastembed
    imports. Never raises: a failed install is logged and the caller skips
    embedding exactly as before. `runner` is injectable for tests."""
    log = log or sys.stderr.write
    try:
        import fastembed  # noqa: F401
        return True
    except ImportError:
        pass
    if not auto_install:
        return False
    runner = runner or (lambda cmd: subprocess.run(cmd, capture_output=True, text=True, timeout=600).returncode)
    try:
        rc = runner(INSTALL_CMD)
    except Exception as e:  # noqa: BLE001
        log("embedding: install failed (%s)\n" % e)
        return False
    if rc != 0:
        log("embedding: install failed (exit %s)\n" % rc)
        return False
    try:
        import importlib
        importlib.invalidate_caches()
        import fastembed  # noqa: F401
        log("embedding: installed fastembed + numpy at run start\n")
        return True
    except ImportError:
        log("embedding: install ran but fastembed still unavailable\n")
        return False


def embed_missing(docs, cache, auto_install=False):
    """Embed docs whose embed_hash is not already cached. Returns (cache, ok).

    Lazily imports fastembed (self-installing when auto_install, Phase 5);
    when unavailable logs a skip and returns ok=False.
    """
    if not ensure_fastembed(auto_install):
        sys.stderr.write("embedding: skipped (fastembed unavailable)\n")
        return cache, False
    from fastembed import TextEmbedding

    by_hash = {row["embed_hash"]: row["vector"]
               for row in cache.get("files", {}).values() if "vector" in row}
    need = [d for d in docs if d["embed_hash"] not in by_hash]
    sys.stderr.write(
        "  %d docs | cached %d | embedding %d new\n"
        % (len(docs), len(docs) - len(need), len(need)))
    if need:
        model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        vecs = list(model.embed([d["text"] for d in need]))
        for d, v in zip(need, vecs):
            by_hash[d["embed_hash"]] = [round(float(x), 4) for x in list(v)]
    cache["meta"] = {"vector_model": VECTOR_MODEL, "dims": DIMS}
    cache["files"] = {
        d["rel"]: {"embed_hash": d["embed_hash"], "vector": by_hash[d["embed_hash"]]}
        for d in docs if d["embed_hash"] in by_hash
    }
    return cache, True


# ---------- candidate generation ----------

def human_rejected_pairs(judgments):
    """(relA, relB) path pairs a human rejected. A comparator verdict is
    hash-gated (re-judged when a doc changes); a human reject is sticky across
    content changes, because the human decided the *relationship* of the two
    docs, not their bytes. Only a human reopens it (delete the record, or
    `judge --force`)."""
    out = set()
    for j in (judgments or {}).values():
        if j.get("status") == "rejected" and j.get("decided_by") == "human":
            out.add(tuple(sorted((j["relA"], j["relB"]))))
    return out


def generate_candidates(docs, vecs_by_rel, watched_pairs, judgments,
                        owners=DEFAULT_OWNERS, high=0.86, fallback=0.90):
    by_rel = {d["rel"]: d for d in docs}
    watched_pairs = set(watched_pairs or set())
    sticky = human_rejected_pairs(judgments)
    out = []
    seen = set()
    n = len(docs)
    for i in range(n):
        a = docs[i]
        va_vec = vecs_by_rel.get(a["rel"])
        if va_vec is None:
            continue
        for j in range(i + 1, n):
            b = docs[j]
            vb_vec = vecs_by_rel.get(b["rel"])
            if vb_vec is None:
                continue
            relA, relB = sorted((a["rel"], b["rel"]))
            key = (relA, relB)
            if key in seen or key in sticky:
                continue
            is_watched = key in watched_pairs
            cos = cosine(va_vec, vb_vec)
            if not is_watched and not passes_gate(
                    cos, a["entities"], b["entities"], owners, high, fallback):
                continue
            # Watched pairs were flagged explicitly (audit or human); they
            # bypass the deterministic pre-filters as well as the gate.
            if not is_watched and prefiltered(relA, relB):
                continue
            da, db = by_rel[relA], by_rel[relB]
            # Pair id is keyed on the index CONTENT hash (spec: re-judge only when
            # a doc's content changes); embed_hash is the fallback for rows
            # that carry no index hash.
            ca = da.get("hash") or da["embed_hash"]
            cb = db.get("hash") or db["embed_hash"]
            pid = pair_id(relA, ca, relB, cb)
            if already_judged(pid, judgments):
                continue
            seen.add(key)
            out.append({
                "pair_id": pid, "relA": relA, "relB": relB,
                "hashA": ca, "hashB": cb,
                "cosine": round(cos, 4),
                "shared_entity": shared_non_owner_entity(
                    a["entities"], b["entities"], owners),
                "source": "watched" if is_watched else "gate",
            })
    out.sort(key=lambda c: c["cosine"], reverse=True)
    return out


# ---------- judgments (Phase 2: LLM comparator cache) ----------
# Claude is the comparator (the /vault-audit session); this script only hands
# out unjudged pairs (`pending`) and validates + caches verdicts (`judge`) in
# vault-index.json under canonical_judgments. Hash-gated: a cached verdict is
# replayed until either doc's content hash changes. Still report-only.

VERDICTS = ("version-fork", "duplicate", "distinct-purpose")
REASON_MAX = 300


def load_candidates(vault):
    path = os.path.join(vault, HYGIENE_DIR, "canonical-candidates.json")
    if not os.path.exists(path):
        return {"meta": {"count": 0}, "candidates": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def judgment_is_fresh(pid, j, index_files):
    a = (index_files.get(j.get("relA")) or {}).get("hash")
    b = (index_files.get(j.get("relB")) or {}).get("hash")
    if not a or not b:
        return False
    return pair_id(j["relA"], a, j["relB"], b) == pid


def judgment_summary(judgments, index_files):
    by_verdict, by_status = {}, {}
    stale = 0
    for pid, j in (judgments or {}).items():
        v = j.get("verdict", "?")
        st = j.get("status", "?")
        by_verdict[v] = by_verdict.get(v, 0) + 1
        by_status[st] = by_status.get(st, 0) + 1
        if not judgment_is_fresh(pid, j, index_files):
            stale += 1
    return {"total": len(judgments or {}), "by_verdict": by_verdict,
            "by_status": by_status, "stale": stale}


def list_pending(candidates, judgments, limit=0, contains="", sources=()):
    out = []
    needle = (contains or "").lower()
    for c in candidates:
        if already_judged(c["pair_id"], judgments):
            continue
        if sources and c.get("source") not in sources:
            continue
        if needle and needle not in (c["relA"] + "\n" + c["relB"]).lower():
            continue
        out.append(c)
        if limit and len(out) >= limit:
            break
    return out


def attach_text(vault, pairs, max_chars=6000):
    def read(rel):
        try:
            with open(os.path.join(vault, rel), encoding="utf-8", errors="ignore") as f:
                return f.read()[:max_chars]
        except OSError:
            return ""
    out = []
    for c in pairs:
        d = dict(c)
        d["textA"] = read(c["relA"])
        d["textB"] = read(c["relB"])
        out.append(d)
    return out


def sanitize_reason(s):
    s = re.sub(r"\s*[\u2014\u2013]\s*", ", ", str(s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s[:REASON_MAX]


def validate_verdict(v, cands_by_pid):
    pid = v.get("pair_id")
    if not pid:
        return "missing_pair_id"
    if pid not in cands_by_pid:
        return "unknown_pair"
    if v.get("verdict") not in VERDICTS:
        return "bad_verdict"
    conf = v.get("confidence")
    if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not (0.0 <= conf <= 1.0):
        return "bad_confidence"
    if not sanitize_reason(v.get("reason")):
        return "missing_reason"
    return None


def apply_verdicts(judgments, cands_by_pid, verdicts, model, today, force=False):
    """Validate each verdict against the live candidates and cache it.

    Existing judgments are replayed (never overwritten) unless force=True;
    confirmed judgments (a Phase 4 human decision) are locked even then.
    Returns {"accepted": [pid], "replayed": [pid], "rejected": [{pair_id, error}]}.
    """
    res = {"accepted": [], "replayed": [], "rejected": []}
    if force:
        # A forced re-judge may target a pair the report already dropped from
        # the candidate list (judged pairs are not re-emitted); the cached
        # record carries everything a candidate does, so it stands in.
        cands_by_pid = dict(cands_by_pid)
        for pid, j in judgments.items():
            cands_by_pid.setdefault(pid, j)
    for v in verdicts:
        err = validate_verdict(v, cands_by_pid)
        if err:
            res["rejected"].append({"pair_id": v.get("pair_id"), "error": err})
            continue
        pid = v["pair_id"]
        existing = judgments.get(pid)
        if existing is not None and existing.get("status") in ("withdrawn", "stale"):
            existing = None  # closed judgments do not block a fresh verdict (already_judged agrees)
        prior = None
        if existing is not None:
            if existing.get("status") == "confirmed":
                res["rejected"].append({"pair_id": pid, "error": "confirmed_locked"})
                continue
            if not force:
                res["replayed"].append(pid)
                continue
            prior = {"verdict": existing.get("verdict"), "judge_model": existing.get("judge_model"),
                     "decided_at": existing.get("decided_at")}
        c = cands_by_pid[pid]
        judgments[pid] = {
            "relA": c["relA"], "relB": c["relB"],
            "hashA": c["hashA"], "hashB": c["hashB"],
            "verdict": v["verdict"], "winner": None,
            "confidence": round(float(v["confidence"]), 3),
            "reason": sanitize_reason(v["reason"]),
            "judge_model": model, "decided_at": today, "status": "proposed",
            "source": c.get("source", "gate"), "cosine": c.get("cosine"),
        }
        if prior:
            judgments[pid]["superseded_verdict"] = prior
        res["accepted"].append(pid)
    return res


def build_pending(vault, limit=0, contains="", sources=(), with_text=False, max_chars=6000):
    index = va.load_index(vault)
    judgments = index.get("canonical_judgments", {}) or {}
    cands = load_candidates(vault).get("candidates", [])
    pending = list_pending(cands, judgments)
    pairs = list_pending(cands, judgments, limit, contains, tuple(sources or ()))
    if with_text:
        pairs = attach_text(vault, pairs, max_chars)
    judged = sum(1 for c in cands if already_judged(c["pair_id"], judgments))
    return {"meta": {"candidates": len(cands), "judged": judged, "pending": len(pending),
                     "returned": len(pairs),
                     "judgments": judgment_summary(judgments, index.get("files", {}))},
            "pairs": pairs}


def run_judge(vault, verdicts_path, model, force=False, today=None):
    with open(verdicts_path, encoding="utf-8") as f:
        payload = json.load(f)
    verdicts = payload.get("verdicts", []) if isinstance(payload, dict) else payload
    return judge_verdicts(vault, verdicts, model, force, today)


# ---------- survivorship (Phase 3: deterministic winner) ----------
# The comparator proposes the cluster; this rule picks the canonical winner.
# Order is fixed by the spec: existing canonical > type/folder priority >
# most recent > tie (no pick; routed to the queue flagged tie).

CANONICAL_HOME_TYPES = {"sop", "client-profile", "person", "concept"}
# Generic default canonical-home folders. A live doc here (or of a canonical-home
# TYPE) outranks a draft or dated one-off in survivorship. Override per-vault via
# the schema's `embedding.canonical_home_dirs`.
CANONICAL_HOME_DIRS = ("Resources/Reference", "Resources/People", "Resources/Concepts")
LOW_PRIORITY_SEGMENTS = {"_originals", "drafts", "draft", "scratch", "brainstorms"}
DATED_BASENAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
FM_SCALAR_KEYS = ("canonical", "status", "type", "updated")
SURVIVOR_VERDICTS = ("version-fork", "duplicate")


def read_fm_scalars(path, keys=FM_SCALAR_KEYS):
    """Top-level scalar frontmatter keys only (line scan, not a YAML parser)."""
    out = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return out
    if not text.startswith("---\n"):
        return out
    end = text.find("\n---", 4)
    if end == -1:
        return out
    for ln in text[4:end].splitlines():
        if not ln or ln.startswith((" ", "-", "#")) or ":" not in ln:
            continue
        k, _, v = ln.partition(":")
        k = k.strip()
        if k in keys:
            out[k] = v.strip().strip("\"'")
    return out


def doc_facts(vault, rel):
    full = os.path.join(vault, rel)
    fm = read_fm_scalars(full)
    try:
        mtime_date = date.fromtimestamp(os.path.getmtime(full)).isoformat()
    except OSError:
        mtime_date = ""
    upd = fm.get("updated", "")
    return {"rel": rel,
            "canonical": fm.get("canonical", "").lower() == "true",
            "status": fm.get("status", "").lower(),
            "type": fm.get("type", "").lower(),
            "updated": upd if DATED_BASENAME_RE.match(upd or "") else "",
            "mtime_date": mtime_date}


def priority_rank(f, home_dirs=None):
    """3 = live canonical-home doc, 2 = ordinary live doc, 1 = draft /
    _Originals / dated one-off, 0 = already superseded or archived."""
    home_dirs = CANONICAL_HOME_DIRS if home_dirs is None else home_dirs
    rel = f["rel"]
    segs = rel.split("/")
    base, dirs = segs[-1], segs[:-1]
    status = (f.get("status") or "").lower()
    typ = (f.get("type") or "").lower()
    if status in ("superseded", "archived"):
        return 0
    if (any(seg.lower() in LOW_PRIORITY_SEGMENTS for seg in dirs) or status == "draft"
            or typ == "draft" or "draft" in base.lower()):
        return 1
    in_home = any(rel.startswith(d + "/") for d in home_dirs)
    if typ in CANONICAL_HOME_TYPES or base == "Company Profile.md" or in_home:
        return 3
    if DATED_BASENAME_RE.match(base):
        return 1
    return 2


def recency_date(f):
    return f.get("updated") or f.get("mtime_date") or ""


def survivorship(fa, fb, home_dirs=None):
    """Returns (winner_rel or None, rule)."""
    ca, cb = bool(fa.get("canonical")), bool(fb.get("canonical"))
    if ca != cb:
        return (fa["rel"] if ca else fb["rel"]), "existing_canonical"
    if ca and cb:
        return None, "tie"
    ra, rb = priority_rank(fa, home_dirs), priority_rank(fb, home_dirs)
    if ra != rb:
        return (fa["rel"] if ra > rb else fb["rel"]), "priority"
    da, db = recency_date(fa), recency_date(fb)
    if da and db and da != db:
        return (fa["rel"] if da > db else fb["rel"]), "recency"
    return None, "tie"


def apply_survivorship(judgments, facts_fn, today, recompute=False, home_dirs=None):
    """Set winner/loser/winner_rule/survivorship_at on proposed fork/duplicate
    judgments that lack a rule (anti-flip-flop: computed once unless recompute).
    Returns the number of judgments changed."""
    changed = 0
    for j in judgments.values():
        if j.get("verdict") not in SURVIVOR_VERDICTS or j.get("status") != "proposed":
            continue
        if j.get("winner_rule") and not recompute:
            continue
        fa, fb = facts_fn(j["relA"]), facts_fn(j["relB"])
        winner, rule = survivorship(fa, fb, home_dirs)
        j["winner"] = winner
        j["loser"] = (j["relB"] if winner == j["relA"] else j["relA"]) if winner else None
        j["winner_rule"] = rule
        j["survivorship_at"] = today
        changed += 1
    return changed


# ---------- review queue (Phase 3: human gate, report-only) ----------

REVIEW_PATH = os.path.join(HYGIENE_DIR, "pending-supersession-review.md")
DECISIONS = ("pending", "confirm", "confirm-keep", "reject", "swap")


def short_id(pid):
    return pid[:12]


def queue_proposals(judgments):
    """Proposed survivor judgments in review order: ties first, then by confidence."""
    props = [(pid, j) for pid, j in judgments.items()
             if j.get("verdict") in SURVIVOR_VERDICTS and j.get("status") == "proposed"
             and j.get("winner_rule")]
    props.sort(key=lambda x: (x[1].get("winner_rule") != "tie", -(x[1].get("confidence") or 0), x[0]))
    return props


def render_review_queue(judgments, decisions, today):
    props = queue_proposals(judgments)
    n_open = sum(1 for pid, _ in props if decisions.get(pid, "pending") == "pending")
    lines = [
        "# Pending supersession review", "",
        "Generated: %s. %d open, %d decided (applied by the next audit run). Nothing is "
        "stamped until a decision is applied (`apply`)." % (today, n_open, len(props) - n_open), "",
        "How to use: edit each block's `decision:` to `confirm` (fold the loser's unique facts into "
        "the winner, stamp both, repoint links, retire the loser to audit-trash), `confirm-keep` (stamp "
        "only; the loser stays readable in place), `reject` (they legitimately coexist; cached so the "
        "pair never returns unless a doc changes), or `swap` (the loser is really the winner, then "
        "confirm). Blocks are regenerated each run "
        "and your edits survive regeneration. Ties (no deterministic winner) are listed first with "
        "the docs in path order. Rule legend: existing_canonical (a prior human stamp), priority "
        "(canonical-home type/folder outranks drafts, _Originals, dated one-offs), recency "
        "(`updated`, else file mtime), tie.", ""]
    for pid, j in props:
        tie = j.get("winner_rule") == "tie"
        winner = j.get("winner") or j["relA"]
        loser = j.get("loser") or (j["relB"] if winner == j["relA"] else j["relA"])
        lines.append("### %s  verdict: %s  confidence: %.2f  rule: %s" % (
            short_id(pid), j["verdict"], j.get("confidence") or 0, j.get("winner_rule")))
        lines.append("pair_id: %s" % pid)
        lines.append("winner:  %s" % winner)
        lines.append("loser:   %s" % loser)
        lines.append("reason:  %s" % (j.get("reason") or ""))
        if tie:
            lines.append("tie: true")
        lines.append("decision: %s      # edit to: confirm | confirm-keep | reject | swap (make loser the winner)"
                     % decisions.get(pid, "pending"))
        lines.append("")
    return "\n".join(lines) + "\n"


def parse_review_decisions(text):
    out, pid = {}, None
    for ln in text.splitlines():
        if ln.startswith("pair_id:"):
            pid = ln.partition(":")[2].strip()
        elif ln.startswith("decision:") and pid:
            val = ln.partition(":")[2].split("#")[0].strip().lower()
            out[pid] = val if val in DECISIONS else "pending"
            pid = None
    return out


def queue_counts(text):
    d = parse_review_decisions(text)
    c = {"open": 0, "confirm": 0, "confirm-keep": 0, "reject": 0, "swap": 0, "total": len(d)}
    for v in d.values():
        c["open" if v == "pending" else v] += 1
    return c


def queue_line(c):
    if not c.get("total"):
        return ""
    return "%d supersession proposals pending review (%d decided, applied by the next audit run)" % (
        c["open"], c["total"] - c["open"])


def read_queue_counts(vault):
    path = os.path.join(vault, REVIEW_PATH)
    if not os.path.exists(path):
        return {"open": 0, "confirm": 0, "confirm-keep": 0, "reject": 0, "swap": 0, "total": 0}
    with open(path, encoding="utf-8") as f:
        return queue_counts(f.read())


def write_review_queue(vault, judgments, today=None):
    path = os.path.join(vault, REVIEW_PATH)
    prior = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            prior = parse_review_decisions(f.read())
    text = render_review_queue(judgments, prior, today or date.today().isoformat())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return queue_counts(text)


# ---------- review-queue decisions (file mode) ----------
# The template has no external decision surface: the human reviews by editing the
# `decision:` line in each block of pending-supersession-review.md directly, and
# `apply` reads those lines. (In a deployment with a chat/email decision surface,
# an export/import pair would sit here to round-trip the same `decision:` lines;
# the file is the source of truth either way.)


def run_survivorship(vault, recompute=False, today=None):
    today = today or date.today().isoformat()
    cfg = load_embed_config(va.load_schema(vault))
    index = va.load_index(vault)
    judgments = index.get("canonical_judgments") or {}
    index["canonical_judgments"] = judgments
    changed = apply_survivorship(judgments, lambda rel: doc_facts(vault, rel), today,
                                 recompute, cfg["canonical_home_dirs"])
    if changed:
        va.save_index(vault, index)
    counts = write_review_queue(vault, judgments, today)
    return {"survivorship_applied": changed, "queue": counts}


# ---------- golden eval set + claude -p runner (Phase 3 calibration / sweep) ----------
# The golden set is hand-marked truth (contains vault file names; keep it private).
# `calibrate` measures a comparator model against it; `sweep` uses the same
# invocation to judge the pending backlog and records the model id in
# judge_model. The runner shells out to the `claude` CLI: no tools, no MCP,
# neutral cwd (no CLAUDE.md), structured JSON output, CLAUDECODE unset so it
# runs nested inside a Claude Code session.

GOLDEN_PATH = os.path.join(HYGIENE_DIR, "golden-pairs.json")
CALIBRATION_LOG = os.path.join(HYGIENE_DIR, "calibration-log.md")

RUBRIC = """You are a document comparator for a personal knowledge vault. You will be given two markdown documents (path + text, possibly truncated). Classify the PAIR on one dimension and answer only in the JSON schema provided.

Verdicts:
- version-fork: the two docs are versions of the same document (one evolved from the other, or both from a common ancestor); a reader should only ever land on one of them.
- duplicate: same content and same purpose, both current (a copy/paste, an export, the same doc filed twice).
- distinct-purpose: they legitimately coexist: different audience, different stage of one pipeline (an agenda vs the decisions it produced, discovery vs research), a record of an event vs a living doc, a person profile vs a sales-lead note, a talk track vs a plan, two different people or clients on the same template, an internal analysis vs the client-facing summary built on it, two sessions of one series.

When unsure, answer distinct-purpose: a wrong fork/duplicate call is the costly error (it can hide a doc from retrieval later); a missed one just resurfaces. A "Supersedes:" line, a "canonical version" line naming the other doc, or a "consolidated rewrite of" note is strong fork evidence. An _Originals/ or draft path is NOT by itself: a pre-cleanup source with the same skeleton as the living doc (same sections, same recipes, same steps, tidied) is a version-fork; a raw scribble, seed note, or meeting fragment whose facts were folded into a living doc is a record of that moment and is distinct-purpose. Also distinct-purpose: a project runbook beside the generic reference rewritten from it; two entry files for two agent runtimes (AGENTS.md vs CLAUDE.md); a design spec or plan beside the living doc it fed (the spec is history, the living doc is canon; two generations of a spec in the same folder are a fork only when the later one names the earlier). Sharing a client, a template, or a topic is not fork evidence.

confidence is in [0, 1]. reason is one line naming the concrete tell; no em dashes."""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "confidence", "reason"],
}

_RUNNER_DIR = None


def _runner_dir():
    global _RUNNER_DIR
    if _RUNNER_DIR is None:
        _RUNNER_DIR = tempfile.mkdtemp(prefix="vault-embed-runner-")
        with open(os.path.join(_RUNNER_DIR, "empty-mcp.json"), "w") as f:
            f.write('{"mcpServers": {}}')
    return _RUNNER_DIR


def load_golden(vault):
    with open(os.path.join(vault, GOLDEN_PATH), encoding="utf-8") as f:
        return json.load(f)


def validate_golden(golden, vault):
    errs = []
    for i, p in enumerate(golden.get("pairs", [])):
        if p.get("expected") not in VERDICTS:
            errs.append("bad_expected:%d" % i)
        for k in ("relA", "relB"):
            if not os.path.exists(os.path.join(vault, p.get(k) or "")):
                errs.append("missing_file:%d:%s" % (i, p.get(k)))
    return errs


GOLDEN_FIXTURES_DIR = os.path.join(HYGIENE_DIR, "golden-fixtures")


def _golden_key(relA, relB):
    return frozenset((relA, relB))


def record_golden_from_apply(vault, entries, today):
    """Grow golden-pairs.json from human decisions (canon section 5: the golden set
    grows from corrections). Each entry: {relA, relB, expected, snapshot, note};
    `snapshot` maps a live rel path to its pre-apply text for docs the apply is
    about to rewrite or retire, written once under golden-fixtures/ so the
    positive survives the fold. Pairs already present (by path set, live or
    fixture) are skipped. Returns the number of pairs added."""
    path = os.path.join(vault, GOLDEN_PATH)
    if os.path.exists(path):
        golden = load_golden(vault)
    else:
        golden = {"meta": {"created": today, "updated": today,
                           "notes": "grown from decision-surface presses (apply step)"}, "pairs": []}
    have = {_golden_key(p.get("relA"), p.get("relB")) for p in golden.get("pairs", [])}
    added = 0
    for e in entries:
        fixture_of = {}
        for rel, text in (e.get("snapshot") or {}).items():
            frel = os.path.join(GOLDEN_FIXTURES_DIR, rel)
            fpath = os.path.join(vault, frel)
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            if not os.path.exists(fpath):
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(text)
            fixture_of[rel] = frel
        relA = fixture_of.get(e["relA"], e["relA"])
        relB = fixture_of.get(e["relB"], e["relB"])
        if _golden_key(relA, relB) in have or _golden_key(e["relA"], e["relB"]) in have:
            continue
        pair = {"relA": relA, "relB": relB, "expected": e["expected"],
                "source": "decision-surface", "note": e.get("note") or ""}
        if fixture_of:
            pair["fixture"] = "pre-apply snapshot %s (the decision rewrote or retired the live doc)" % today
        golden.setdefault("pairs", []).append(pair)
        have.add(_golden_key(relA, relB))
        added += 1
    if added:
        golden.setdefault("meta", {})["updated"] = today
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(golden, f, indent=1, ensure_ascii=False)
        os.replace(tmp, path)
    return added


def build_prompt(relA, textA, relB, textB):
    return ("DOC A path: %s\n<<<DOC A>>>\n%s\n<<<END DOC A>>>\n\n"
            "DOC B path: %s\n<<<DOC B>>>\n%s\n<<<END DOC B>>>\n\n"
            "Classify the pair." % (relA, textA, relB, textB))


def _coerce_verdict(obj):
    if not isinstance(obj, dict) or obj.get("verdict") not in VERDICTS:
        return None
    conf = obj.get("confidence")
    if isinstance(conf, bool) or not isinstance(conf, (int, float)):
        conf = 0.5
    return {"verdict": obj["verdict"], "confidence": max(0.0, min(1.0, float(conf))),
            "reason": sanitize_reason(obj.get("reason") or "no reason given")}


def parse_claude_output(stdout):
    try:
        d = json.loads(stdout)
    except (ValueError, TypeError):
        return None
    if not isinstance(d, dict):
        return None
    v = _coerce_verdict(d.get("structured_output"))
    if v:
        return v
    res = d.get("result")
    if isinstance(res, str):
        txt = res.strip()
        txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt)
        try:
            return _coerce_verdict(json.loads(txt))
        except ValueError:
            return None
    return None


def invoke_judge(prompt, model, claude_cmd="claude", timeout=300):
    """Run one comparator call. Returns (verdict_dict_or_None, raw_stdout, cost_usd)."""
    rd = _runner_dir()
    cmd = [claude_cmd, "-p", "--model", model, "--output-format", "json",
           "--tools", "", "--strict-mcp-config", "--mcp-config", os.path.join(rd, "empty-mcp.json"),
           "--system-prompt", RUBRIC, "--json-schema", json.dumps(JUDGE_SCHEMA)]
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              cwd=rd, env=env, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, "invoke_error: %s" % e, 0.0
    out = proc.stdout or ""
    cost = 0.0
    try:
        cost = float(json.loads(out).get("total_cost_usd") or 0.0)
    except (ValueError, AttributeError, TypeError):
        pass
    return parse_claude_output(out), out if out else (proc.stderr or ""), cost


def score_calibration(results):
    n = len(results)
    sup = ("version-fork", "duplicate")
    exact = sum(1 for r in results if r["predicted"] == r["expected"])
    cls = sum(1 for r in results if r["predicted"] is not None
              and (r["predicted"] in sup) == (r["expected"] in sup))
    neg = [r for r in results if r["expected"] == "distinct-purpose"]
    pos = [r for r in results if r["expected"] in sup]
    false_sup = sum(1 for r in neg if r["predicted"] in sup)
    hits = sum(1 for r in pos if r["predicted"] in sup)
    return {"n": n,
            "exact_accuracy": round(exact / n, 3) if n else 0.0,
            "class_accuracy": round(cls / n, 3) if n else 0.0,
            "false_supersede_rate": round(false_sup / len(neg), 3) if neg else 0.0,
            "fork_recall": round(hits / len(pos), 3) if pos else 0.0,
            "negatives": len(neg), "positives": len(pos),
            "errors": sum(1 for r in results if r["predicted"] is None)}


def _read_head(vault, rel, max_chars):
    try:
        with open(os.path.join(vault, rel), encoding="utf-8", errors="ignore") as f:
            return f.read()[:max_chars]
    except OSError:
        return ""


def _judge_many(vault, pairs, model, parallel, claude_cmd, max_chars):
    """pairs: [{relA, relB, ...}] -> [(pair, verdict_or_None, raw, cost)] in order."""
    def one(p):
        prompt = build_prompt(p["relA"], _read_head(vault, p["relA"], max_chars),
                              p["relB"], _read_head(vault, p["relB"], max_chars))
        v, raw, cost = invoke_judge(prompt, model, claude_cmd)
        sys.stderr.write("  %s | %s -> %s\n" % (
            p["relA"], p["relB"], v["verdict"] if v else "NO PARSE"))
        return p, v, raw, cost
    with ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
        return list(ex.map(one, pairs))


def run_calibrate(vault, model, limit=0, parallel=2, claude_cmd="claude", dry_run=False,
                  max_chars=6000, today=None):
    today = today or date.today().isoformat()
    golden = load_golden(vault)
    errs = validate_golden(golden, vault)
    if errs:
        raise SystemExit("golden set invalid: " + ", ".join(errs))
    pairs = golden.get("pairs", [])
    if limit:
        pairs = pairs[:limit]
    if dry_run:
        return {"model": model, "dry_run": len(pairs), "metrics": score_calibration([]), "results": []}
    results, cost = [], 0.0
    for p, v, raw, c in _judge_many(vault, pairs, model, parallel, claude_cmd, max_chars):
        cost += c
        results.append({"relA": p["relA"], "relB": p["relB"], "expected": p["expected"],
                        "source": p.get("source", ""), "note": p.get("note", ""),
                        "predicted": v["verdict"] if v else None,
                        "confidence": v["confidence"] if v else None,
                        "reason": v["reason"] if v else raw[:300]})
    metrics = score_calibration(results)
    safe_model = re.sub(r"[^A-Za-z0-9.-]+", "-", model)
    out_rel = os.path.join(HYGIENE_DIR, "calibration-%s-%s.json" % (today, safe_model))
    report = {"model": model, "date": today, "rubric_sha": embed_hash(RUBRIC)[:12],
              "cost_usd": round(cost, 4), "metrics": metrics, "results": results, "out": out_rel}
    os.makedirs(os.path.join(vault, HYGIENE_DIR), exist_ok=True)
    with open(os.path.join(vault, out_rel), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, ensure_ascii=False)
    log = os.path.join(vault, CALIBRATION_LOG)
    if not os.path.exists(log):
        with open(log, "w", encoding="utf-8") as f:
            f.write("# Comparator calibration log\n\nOne line per `calibrate` run against "
                    "`golden-pairs.json`. false_supersede_rate is the costly error "
                    "(expected distinct-purpose, predicted fork/duplicate).\n\n"
                    "| date | model | n | class_acc | exact_acc | false_supersede | fork_recall | errors | cost_usd | rubric | file |\n"
                    "|---|---|---|---|---|---|---|---|---|---|---|\n")
    with open(log, "a", encoding="utf-8") as f:
        f.write("| %s | %s | %d | %.3f | %.3f | %.3f | %.3f | %d | %.4f | %s | %s |\n" % (
            today, model, metrics["n"], metrics["class_accuracy"], metrics["exact_accuracy"],
            metrics["false_supersede_rate"], metrics["fork_recall"], metrics["errors"],
            cost, report["rubric_sha"], os.path.basename(out_rel)))
    return report


def judge_verdicts(vault, verdicts, model, force=False, today=None):
    index = va.load_index(vault)
    judgments = index.get("canonical_judgments") or {}
    index["canonical_judgments"] = judgments
    cands_by_pid = {c["pair_id"]: c for c in load_candidates(vault).get("candidates", [])}
    res = apply_verdicts(judgments, cands_by_pid, verdicts, model,
                         today or date.today().isoformat(), force)
    if res["accepted"]:
        va.save_index(vault, index)
    res["total_judgments"] = len(judgments)
    return res


def run_sweep(vault, model, limit=0, parallel=2, claude_cmd="claude", max_chars=6000):
    pending = build_pending(vault, limit=limit)["pairs"]
    verdicts, errors, cost = [], [], 0.0
    for p, v, raw, c in _judge_many(vault, pending, model, parallel, claude_cmd, max_chars):
        cost += c
        if v is None:
            errors.append({"pair_id": p["pair_id"], "relA": p["relA"], "relB": p["relB"],
                           "raw": raw[:300]})
            continue
        verdicts.append({"pair_id": p["pair_id"], "verdict": v["verdict"],
                         "confidence": v["confidence"], "reason": v["reason"]})
    res = judge_verdicts(vault, verdicts, model)
    res.update({"invoked": len(pending), "errors": errors, "cost_usd": round(cost, 4),
                "judge_model": model})
    return res


# ---------- apply (Phase 4: gated stamping, fold and retire) ----------
# The human decision in the review queue is the trigger; this section does the
# deterministic consequences (stamp, repoint, stage, cache, receipt). The one
# semantic step, writing the loser's unique facts into the winner, is supplied
# by the reviewer through --folds and is refused when missing. Only the winner
# (markers + one appended section), the loser (markers, then staged), and the
# files whose wikilinks to the loser repoint ever change, and only on a decided
# block whose judgment is still proposed; a re-run applies nothing. A decided block
# whose documents no longer hash to what the judgment recorded, or that changed
# under an earlier action in the same batch, is closed as `stale` and re-queued as
# a fresh candidate.

FM_QUOTE_KEYS = ("superseded_by", "superseded_reason")
FOLD_MIN_CHARS = 12


def split_frontmatter(text):
    """(fm_lines or None, body). fm_lines excludes the --- fences."""
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    if end == -1:
        return None, text
    fm = text[4:end].split("\n")
    rest = text[end + 4:]
    if rest.startswith("\n"):
        rest = rest[1:]
    return fm, rest


def _fm_value(key, val):
    val = str(val)
    if key in FM_QUOTE_KEYS and not (val.startswith('"') and val.endswith('"')):
        return '"%s"' % val.replace('"', "'")
    return val


def set_fm_keys(text, updates):
    """Replace or insert top-level scalar keys; everything else byte-identical."""
    fm, body = split_frontmatter(text)
    if fm is None:
        lines = ["%s: %s" % (k, _fm_value(k, v)) for k, v in updates.items()]
        return "---\n" + "\n".join(lines) + "\n---\n" + text
    done = set()
    out = []
    for ln in fm:
        key = None
        if ":" in ln and not ln.startswith((" ", "-", "#")):
            key = ln.partition(":")[0].strip()
        if key in updates:
            out.append("%s: %s" % (key, _fm_value(key, updates[key])))
            done.add(key)
        else:
            out.append(ln)
    for k, v in updates.items():
        if k not in done:
            out.append("%s: %s" % (k, _fm_value(k, v)))
    return "---\n" + "\n".join(out) + "\n---\n" + body


def doc_stem(rel):
    return rel[:-3] if rel.endswith(".md") else rel


def norm_line(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def body_lines(text, min_chars=FOLD_MIN_CHARS):
    _, body = split_frontmatter(text)
    out = []
    for ln in body.split("\n"):
        if len(norm_line(ln)) >= min_chars:
            out.append(ln.strip())
    return out


def unique_lines(loser_text, winner_text, min_chars=FOLD_MIN_CHARS):
    """Loser body lines (normalized) absent from the winner: the candidate
    unique facts the fold must carry. Heuristic and verbatim only; the
    reviewer's semantic read decides what is a fact."""
    have = {norm_line(l) for l in body_lines(winner_text, 1)}
    return [l for l in body_lines(loser_text, min_chars) if norm_line(l) not in have]


def fold_section(loser_rel, fold_text, today):
    title = os.path.splitext(os.path.basename(loser_rel))[0]
    return "\n\n## Folded from %s (%s)\n\n%s\n" % (title, today, fold_text.strip("\n"))


def repoint_text(text, loser_rel, winner_rel):
    """Rewrite every wikilink that resolves to the loser so it resolves to the
    winner at the same qualification level (bare stem stays bare, a
    path-qualified form becomes the winner's full path stem). Aliases and
    heading anchors after the target are preserved. Returns (text, count)."""
    forms = set(va._link_forms(loser_rel))
    w_bare = os.path.basename(doc_stem(winner_rel))
    w_full = doc_stem(winner_rel)
    count = [0]

    def sub(m):
        target = m.group(1).strip()
        if target not in forms:
            return m.group(0)
        count[0] += 1
        return "[[" + (w_full if "/" in target else w_bare)

    out = re.sub(r"\[\[([^\]|#]+)(?=[\]|#])", sub, text)
    return out, count[0]


def repoint_links(vault, files, loser_rel, winner_rel, write=True):
    changed = []
    for rel in files:
        if rel == loser_rel:
            continue
        full = os.path.join(vault, rel)
        try:
            with open(full, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        new, n = repoint_text(text, loser_rel, winner_rel)
        if n:
            changed.append(rel)
            if write:
                with open(full, "w", encoding="utf-8") as f:
                    f.write(new)
    return changed


def load_folds(path):
    if not path:
        return {}
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    out = {}
    for pid, v in d.items():
        if isinstance(v, dict):
            v = v.get("section", "")
        out[pid] = "" if v is None else str(v)
    return out


def _read_doc(vault, rel):
    with open(os.path.join(vault, rel), encoding="utf-8", errors="replace") as f:
        return f.read()


def plan_apply(vault, schema, index, decisions, folds, files, today):
    """One action per decided block whose judgment is still proposed. Pure
    planning: reads docs, computes the new texts, writes nothing."""
    judgments = index.get("canonical_judgments") or {}
    protected = schema.get("protected", [])
    actions = []
    for pid, decision in sorted(decisions.items()):
        j = judgments.get(pid)
        if decision == "pending" or j is None or j.get("status") != "proposed":
            continue
        if j.get("verdict") not in SURVIVOR_VERDICTS:
            continue
        winner = j.get("winner") or j["relA"]
        loser = j.get("loser") or (j["relB"] if winner == j["relA"] else j["relA"])
        if decision == "swap":
            winner, loser = loser, winner
        a = {"pair_id": pid, "decision": decision, "effective": None, "winner": winner, "loser": loser,
             "reason": sanitize_reason(j.get("reason")), "skip_reason": None, "downgraded_reason": None,
             "unique": [], "fold_text": None, "fold_declared_subset": False,
             "winner_old": None, "winner_new": None, "loser_old": None, "loser_new": None,
             "links": [], "stage_dest": None}
        actions.append(a)
        if decision == "reject":
            a["effective"] = "rejected"
            continue
        for rel in (winner, loser):
            if va.is_protected(rel, protected):
                a["effective"], a["skip_reason"] = "skip", "protected:" + rel
                break
            if not os.path.isfile(os.path.join(vault, rel)):
                # The pair cannot be applied and cannot come back under this
                # pair_id at this path: close it as withdrawn (not a verdict).
                a["effective"], a["skip_reason"] = "withdrawn", "missing:" + rel
                break
        if a["effective"] in ("skip", "withdrawn"):
            continue
        # Stale-approval guard (audit finding 2): the hashes in the judgment are the
        # content the comparator and the reviewer saw. Any drift since then means the
        # decision was made about a different document; refuse and re-queue.
        for rel, want in ((j["relA"], j.get("hashA")), (j["relB"], j.get("hashB"))):
            if not want or va.sha256_file(os.path.join(vault, rel)) != want:
                a["effective"], a["skip_reason"] = "stale", "stale:" + rel
                break
        if a["effective"] == "stale":
            continue
        mode = "kept" if decision == "confirm-keep" else "folded"
        if mode == "folded":
            for rel in (winner, loser):
                if va.is_record(os.path.dirname(rel), schema):
                    mode, a["downgraded_reason"] = "kept", "no_merge:" + rel
                    break
        a["winner_old"] = _read_doc(vault, winner)
        a["loser_old"] = _read_doc(vault, loser)
        if mode == "folded":
            a["unique"] = unique_lines(a["loser_old"], a["winner_old"])
            if pid in folds:
                a["fold_text"] = folds[pid]
                a["fold_declared_subset"] = not folds[pid].strip()
            elif a["unique"]:
                a["effective"], a["skip_reason"] = "skip", "fold_missing"
                continue
            else:
                a["fold_text"] = ""
        a["effective"] = mode
        w_upd = {"canonical": "true"}
        if "status" not in read_fm_scalars(os.path.join(vault, winner), ("status",)):
            w_upd["status"] = "active"
        w_new = set_fm_keys(a["winner_old"], w_upd)
        if mode == "folded" and a["fold_text"] and a["fold_text"].strip():
            w_new = w_new.rstrip("\n") + fold_section(loser, a["fold_text"], today)
        a["winner_new"] = w_new
        a["loser_new"] = set_fm_keys(a["loser_old"], {
            "status": "superseded", "superseded_by": "[[%s]]" % doc_stem(winner),
            "superseded_at": today, "superseded_reason": a["reason"]})
        if mode == "folded":
            a["links"] = repoint_links(vault, files, loser, winner, write=False)
            a["stage_dest"] = os.path.join(HYGIENE_DIR, "audit-trash", today, loser)
    return actions


def _diff(old, new, name):
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                        "a/" + name, "b/" + name, n=2))


def render_plan(actions):
    out = []
    for a in actions:
        out.append("=== %s  decision: %s  ->  %s" % (short_id(a["pair_id"]), a["decision"], a["effective"]))
        out.append("winner: %s\nloser:  %s" % (a["winner"], a["loser"]))
        if a["skip_reason"]:
            tag = {"withdrawn": "WITHDRAWN: ", "stale": "STALE: "}.get(a["effective"], "SKIP: ")
            out.append(tag + a["skip_reason"])
        if a["downgraded_reason"]:
            out.append("DOWNGRADED to confirm-keep: " + a["downgraded_reason"])
        if a["effective"] in ("folded", "skip") and a["unique"]:
            out.append("unique loser lines (%d, verbatim check; the fold must carry every fact among them):"
                       % len(a["unique"]))
            out.extend("  | " + l for l in a["unique"])
        if a["winner_new"] is not None:
            out.append(_diff(a["winner_old"], a["winner_new"], a["winner"]))
            out.append(_diff(a["loser_old"], a["loser_new"], a["loser"]))
        if a["links"]:
            out.append("repoint links in: " + ", ".join(a["links"]))
        if a["stage_dest"]:
            out.append("stage loser to: " + a["stage_dest"])
        out.append("")
    return "\n".join(out)


def _empty_receipt():
    return {"applied": 0, "folded": [], "kept": [], "rejected": [], "withdrawn": [], "stale": [],
            "downgraded": [], "skipped": [], "links_repointed": 0, "staged": [], "invariant_violations": [],
            "proposals_open": 0}


def _stale_update(a, why, today):
    return {"status": "stale", "outcome": "stale", "decision": a["decision"],
            "stale_reason": why, "applied_at": today}


def _changed_since_plan(vault, a):
    """Batch revalidation: an earlier action may have rewritten, repointed, or staged
    one of this action's docs after plan_apply read them."""
    for rel, old in ((a["winner"], a["winner_old"]), (a["loser"], a["loser_old"])):
        p = os.path.join(vault, rel)
        if not os.path.isfile(p) or _read_doc(vault, rel) != old:
            return "changed_during_batch:" + rel
    return None


def execute_apply(vault, actions, today):
    receipt = _empty_receipt()
    schema = va.load_schema(vault)
    files = va.walk_vault(vault, schema.get("protected", []))
    updates = {}
    pre_texts = {}
    for a in actions:
        pid = a["pair_id"]
        label = "%s > %s" % (a["winner"], a["loser"])
        if a["effective"] == "skip":
            receipt["skipped"].append("%s: %s" % (label, a["skip_reason"]))
            continue
        if a["effective"] == "withdrawn":
            updates[pid] = {"status": "withdrawn", "outcome": "withdrawn", "decision": a["decision"],
                            "withdrawn_reason": a["skip_reason"], "applied_at": today}
            receipt["withdrawn"].append("%s: %s" % (label, a["skip_reason"]))
            receipt["applied"] += 1
            continue
        if a["effective"] == "stale":
            updates[pid] = _stale_update(a, a["skip_reason"], today)
            receipt["stale"].append("%s: %s" % (label, a["skip_reason"]))
            continue
        if a["effective"] in ("folded", "kept"):
            why = _changed_since_plan(vault, a)
            if why:
                updates[pid] = _stale_update(a, why, today)
                receipt["stale"].append("%s: %s" % (label, why))
                continue
        upd = {"status": "confirmed", "decision": a["decision"], "applied_at": today,
               "decided_by": "human", "winner": a["winner"], "loser": a["loser"]}
        if a["decision"] == "swap":
            upd["winner_rule"] = "swap"
        if a["effective"] == "rejected":
            upd.update({"status": "rejected", "outcome": "rejected"})
            receipt["rejected"].append("%s | %s" % (a["winner"], a["loser"]))
        else:
            for rel in (a["winner"], a["loser"]):
                with open(os.path.join(vault, rel), encoding="utf-8") as f:
                    pre_texts.setdefault(pid, {})[rel] = f.read()
            with open(os.path.join(vault, a["winner"]), "w", encoding="utf-8") as f:
                f.write(a["winner_new"])
            with open(os.path.join(vault, a["loser"]), "w", encoding="utf-8") as f:
                f.write(a["loser_new"])
            if a["effective"] == "folded":
                links = repoint_links(vault, files, a["loser"], a["winner"], write=True)
                va.stage_files(vault, [a["loser"]], today=today)
                upd.update({"outcome": "folded", "folded_chars": len(a["fold_text"] or ""),
                            "fold_declared_subset": a["fold_declared_subset"],
                            "links_repointed": links, "staged_to": a["stage_dest"]})
                receipt["links_repointed"] += len(links)
                receipt["staged"].append(a["stage_dest"])
                receipt["folded"].append("%s <- %s" % (a["winner"], a["loser"]))
            else:
                upd["outcome"] = "kept"
                receipt["kept"].append(label)
                if a["downgraded_reason"]:
                    upd["downgraded_reason"] = a["downgraded_reason"]
                    receipt["downgraded"].append("%s: %s" % (a["loser"], a["downgraded_reason"]))
        updates[pid] = upd
        receipt["applied"] += 1
    # Reload AFTER staging: stage_files rewrites the index on disk.
    index = va.load_index(vault)
    judgments = index.setdefault("canonical_judgments", {})
    golden_entries = []
    for pid, upd in updates.items():
        j = judgments.get(pid)
        if j is None:
            continue
        if upd.get("outcome") in ("folded", "kept", "rejected"):
            expected = "distinct-purpose" if upd["outcome"] == "rejected" else (
                j.get("verdict") if j.get("verdict") in SURVIVOR_VERDICTS else "version-fork")
            golden_entries.append({"relA": upd["winner"], "relB": upd["loser"], "expected": expected,
                                   "snapshot": pre_texts.get(pid, {}),
                                   "note": "human %s via the review queue on %s" % (upd["decision"], today)})
        if upd.get("outcome") == "rejected":
            j["superseded_verdict"] = {"verdict": j.get("verdict"), "judge_model": j.get("judge_model"),
                                       "decided_at": j.get("decided_at")}
            j["verdict"] = "distinct-purpose"
        j.update(upd)
    if updates:
        va.save_index(vault, index)
    receipt["golden_added"] = record_golden_from_apply(vault, golden_entries, today) if golden_entries else 0
    counts = write_review_queue(vault, judgments, today)
    receipt["proposals_open"] = counts["open"]
    files = va.walk_vault(vault, schema.get("protected", []))
    receipt["invariant_violations"] = va.invariant_check(vault, files, index)
    return receipt


def append_apply_receipt(vault, receipt, today):
    path = os.path.join(vault, HYGIENE_DIR, "audit-log.md")

    def j(xs):
        return ", ".join(xs) if xs else "none"

    block = ("\n## %s (apply)\napplied: %d (folded %d, kept %d, rejected %d, withdrawn %d, stale %d)\n"
             "folded: %s\nkept: %s\nrejected: %s\nwithdrawn: %s\nstale: %s\ndowngraded: %s\nskipped: %s\n"
             "links_repointed: %d\nstaged: %s\ninvariant_violations: %s\nproposals_open: %d\n") % (
        today, receipt["applied"], len(receipt["folded"]), len(receipt["kept"]), len(receipt["rejected"]),
        len(receipt["withdrawn"]), len(receipt["stale"]), j(receipt["folded"]), j(receipt["kept"]),
        j(receipt["rejected"]), j(receipt["withdrawn"]), j(receipt["stale"]), j(receipt["downgraded"]),
        j(receipt["skipped"]), receipt["links_repointed"], j(receipt["staged"]),
        j(receipt["invariant_violations"]), receipt["proposals_open"])
    with open(path, "a", encoding="utf-8") as f:
        f.write(block)


def run_apply(vault, folds_path=None, dry_run=False, only=None, today=None):
    today = today or date.today().isoformat()
    schema = va.load_schema(vault)
    index = va.load_index(vault)
    qpath = os.path.join(vault, REVIEW_PATH)
    decisions = {}
    if os.path.exists(qpath):
        with open(qpath, encoding="utf-8") as f:
            decisions = parse_review_decisions(f.read())
    if only:
        decisions = {pid: d for pid, d in decisions.items() if pid == only or pid.startswith(only)}
    files = va.walk_vault(vault, schema.get("protected", []))
    actions = plan_apply(vault, schema, index, decisions, load_folds(folds_path), files, today)
    plan = render_plan(actions)
    if dry_run:
        receipt = _empty_receipt()
        receipt["skipped"] = ["%s > %s: %s" % (a["winner"], a["loser"], a["skip_reason"])
                              for a in actions if a["effective"] == "skip"]
        receipt["withdrawn"] = ["%s > %s: %s" % (a["winner"], a["loser"], a["skip_reason"])
                                for a in actions if a["effective"] == "withdrawn"]
        receipt["stale"] = ["%s > %s: %s" % (a["winner"], a["loser"], a["skip_reason"])
                            for a in actions if a["effective"] == "stale"]
        return {"dry_run": True, "plan": plan, "actions": len(actions), "receipt": receipt}
    receipt = execute_apply(vault, actions, today)
    if receipt["applied"] or receipt["stale"]:
        append_apply_receipt(vault, receipt, today)
    return {"dry_run": False, "plan": plan, "actions": len(actions), "receipt": receipt}


# ---------- migrate (re-key loop state after a rename) ----------
# A rename or archive is a state migration for the loop, not just a `mv`: the
# vault-relative paths are keys in the index, the vector cache, the judgment
# cache (and the pair_id derived from them), the watched clusters, and the
# golden set. This re-keys all of them in place so nothing re-embeds or
# re-judges. It does NOT move files on disk (do the `mv`/`git mv` yourself,
# before or after); it only repairs the recorded state.

def remap_path(p, old, new):
    if not p:
        return p
    if p == old:
        return new
    if p.startswith(old + "/"):
        return new + p[len(old):]
    return p


def run_migrate(vault, old, new, today=None, dry_run=False):
    old = old.rstrip("/")
    new = new.rstrip("/")
    changed = {"index_files": 0, "watched_clusters": 0, "judgments": 0,
               "vectors": 0, "golden": 0}
    index = va.load_index(vault)

    new_files = {}
    for rel, row in index.get("files", {}).items():
        nr = remap_path(rel, old, new)
        if nr != rel:
            changed["index_files"] += 1
        new_files[nr] = row
    index["files"] = new_files

    wc = []
    for cl in index.get("watched_clusters", []):
        ncl = sorted(remap_path(x, old, new) for x in cl)
        if ncl != sorted(cl):
            changed["watched_clusters"] += 1
        wc.append(ncl)
    index["watched_clusters"] = wc

    judg = index.get("canonical_judgments") or {}
    new_judg = {}
    for pid, j in judg.items():
        nj = dict(j)
        touched = False
        for k in ("relA", "relB", "winner", "loser"):
            if nj.get(k):
                r = remap_path(nj[k], old, new)
                if r != nj[k]:
                    nj[k] = r
                    touched = True
        if touched:
            nj["renamed_from_pair_id"] = pid
            if nj.get("relA") and nj.get("relB") and nj.get("hashA") and nj.get("hashB"):
                npid = pair_id(nj["relA"], nj["hashA"], nj["relB"], nj["hashB"])
            else:
                npid = pid
            new_judg[npid] = nj
            changed["judgments"] += 1
        else:
            new_judg[pid] = nj
    if judg:
        index["canonical_judgments"] = new_judg

    vecs = load_vectors(vault)
    new_vf = {}
    for rel, row in vecs.get("files", {}).items():
        nr = remap_path(rel, old, new)
        if nr != rel:
            changed["vectors"] += 1
        new_vf[nr] = row
    vecs["files"] = new_vf

    golden = None
    gpath = os.path.join(vault, GOLDEN_PATH)
    if os.path.exists(gpath):
        golden = load_golden(vault)
        for p in golden.get("pairs", []):
            for k in ("relA", "relB"):
                if p.get(k):
                    r = remap_path(p[k], old, new)
                    if r != p[k]:
                        p[k] = r
                        changed["golden"] += 1

    if not dry_run:
        va.save_index(vault, index)
        save_vectors(vault, vecs)
        if golden is not None:
            tmp = gpath + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(golden, f, indent=1, ensure_ascii=False)
            os.replace(tmp, gpath)
        # Pair ids in the queue may have changed; regenerate from the re-keyed judgments.
        write_review_queue(vault, index.get("canonical_judgments") or {},
                           today or date.today().isoformat())
    return {"old": old, "new": new, "dry_run": dry_run, "changed": changed}


def cmd_migrate(args):
    old, new = args.rename
    print(json.dumps(run_migrate(args.vault, old, new, dry_run=args.dry_run),
                     indent=1, ensure_ascii=False))


# ---------- output ----------

def write_candidates_json(vault, candidates):
    path = os.path.join(vault, HYGIENE_DIR, "canonical-candidates.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {"meta": {"generated": date.today().isoformat(),
                        "vector_model": VECTOR_MODEL, "count": len(candidates)},
               "candidates": candidates}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, path)
    return path


def write_report(vault, docs, candidates, embedded_ok, judgments=None, index_files=None):
    path = os.path.join(vault, HYGIENE_DIR, "embed-candidate-report.md")
    lines = []
    lines.append("# Embedding candidate report (local, non-destructive)\n")
    lines.append("Generated: %s. Nothing stamped or modified.\n" % date.today().isoformat())
    lines.append("Corpus: **%d** in-scope docs (records and protected folders excluded)."
                 % len(docs))
    lines.append("Model: %s (in-process, no data egress)." % VECTOR_MODEL)
    if not embedded_ok:
        lines.append("\n**Embedding skipped this run (fastembed unavailable): the candidate list below is the "
                     "last successful run's, left untouched.**")
    lines.append("\n## Candidate pairs (%d)\n" % len(candidates))
    lines.append("Pairs above the gate (or watched), pre-filtered, not yet judged. "
                 "The Phase 2 comparator adjudicates these; a high count is expected "
                 "(precision is roughly one-third, per the prototype).\n")
    lines.append("| cosine | shared entity | source | doc A | doc B |")
    lines.append("|---|---|---|---|---|")
    for c in candidates[:200]:
        lines.append("| %.3f | %s | %s | %s | %s |" % (
            c["cosine"], "yes" if c["shared_entity"] else "no",
            c["source"], c["relA"], c["relB"]))
    judgments = judgments or {}
    summ = judgment_summary(judgments, index_files or {})
    lines.append("\n## Judgments (%d cached, report-only)\n" % summ["total"])
    lines.append("Verdicts from the Phase 2 comparator, cached in vault-index.json under "
                 "canonical_judgments and replayed until a doc changes. Nothing is stamped; "
                 "Phase 3 adds survivorship and the review queue.\n")
    lines.append("- by verdict: %s" % (", ".join(
        "%s %d" % kv for kv in sorted(summ["by_verdict"].items())) or "none"))
    lines.append("- by status: %s" % (", ".join(
        "%s %d" % kv for kv in sorted(summ["by_status"].items())) or "none"))
    lines.append("- stale (a doc changed since judging; re-judged when re-emitted): %d\n"
                 % summ["stale"])
    props = [(pid, j) for pid, j in judgments.items()
             if j.get("verdict") in ("version-fork", "duplicate")]
    props.sort(key=lambda x: -(x[1].get("confidence") or 0))
    lines.append("| verdict | conf | winner (rule) | loser | reason |")
    lines.append("|---|---|---|---|---|")
    for pid, j in props:
        rule = j.get("winner_rule") or "unassigned"
        winner = j.get("winner") or ("tie: " + j["relA"] if rule == "tie" else j["relA"])
        loser = j.get("loser") or j["relB"]
        lines.append("| %s | %.2f | %s (%s) | %s | %s |" % (
            j["verdict"], j.get("confidence") or 0, winner, rule, loser,
            (j.get("reason") or "").replace("|", "/")))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


# ---------- CLI ----------

def cmd_report(args):
    vault = args.vault
    schema = va.load_schema(vault)
    index = va.load_index(vault)
    docs = load_scope_docs(vault, schema, index)
    cache = load_vectors(vault)
    auto = bool(args.install or os.environ.get("VAULT_EMBED_AUTO_INSTALL"))
    cache, ok = embed_missing(docs, cache, auto_install=auto)
    candidates = []
    if not ok:
        # Skipped run: leave the last candidate list in place (a local run under
        # the Mac's python3 must not wipe what a uv run produced) and only
        # refresh the report so the skip is visible.
        prior = load_candidates(vault)
        rp = write_report(vault, docs, prior.get("candidates", []), ok,
                          index.get("canonical_judgments", {}) or {}, index.get("files", {}))
        sys.stderr.write("wrote %s (candidates left as-is: %d)\n" % (rp, len(prior.get("candidates", []))))
        return
    if ok:
        save_vectors(vault, cache)
        vecs_by_rel = {rel: row["vector"] for rel, row in cache.get("files", {}).items()}
        judgments = index.get("canonical_judgments", {}) or {}
        cfg = load_embed_config(schema)
        # CLI flags override the schema `embedding:` config, which overrides the defaults.
        if args.owner:
            owners = tuple(o.strip().lower() for o in args.owner.split(",") if o.strip())
        else:
            owners = cfg["owners"]
        owners = owners or DEFAULT_OWNERS
        high = args.high if args.high is not None else cfg["gate_high"]
        fallback = args.fallback if args.fallback is not None else cfg["gate_fallback"]
        candidates = generate_candidates(
            docs, vecs_by_rel, watched_pairs_from_index(index),
            judgments, owners, high, fallback)
    cj = write_candidates_json(vault, candidates)
    rp = write_report(vault, docs, candidates, ok,
                      index.get("canonical_judgments", {}) or {}, index.get("files", {}))
    sys.stderr.write("wrote %s\nwrote %s\ncandidates: %d\n"
                     % (cj, rp, len(candidates)))


def cmd_pending(args):
    out = build_pending(args.vault, args.limit, args.contains,
                        tuple(args.source or ()), args.with_text, args.max_chars)
    print(json.dumps(out, indent=1, ensure_ascii=False))


def cmd_judge(args):
    res = run_judge(args.vault, args.json, args.model, args.force)
    print(json.dumps(res, indent=1, ensure_ascii=False))
    if res["rejected"]:
        sys.stderr.write("judge: %d verdict(s) rejected\n" % len(res["rejected"]))
        sys.exit(2)


def cmd_survivorship(args):
    print(json.dumps(run_survivorship(args.vault, args.recompute), indent=1, ensure_ascii=False))


def cmd_queue(args):
    c = read_queue_counts(args.vault)
    if args.line:
        line = queue_line(c)
        if line:
            print(line)
        return
    print(json.dumps(c, indent=1))


def cmd_apply(args):
    res = run_apply(args.vault, args.folds, args.dry_run, args.only, today=args.today)
    sys.stderr.write(res["plan"])
    print(json.dumps(res["receipt"], indent=1, ensure_ascii=False))
    if res["receipt"]["invariant_violations"]:
        sys.stderr.write("apply: invariant violations after apply\n")
        sys.exit(3)


def cmd_calibrate(args):
    rep = run_calibrate(args.vault, args.model, args.limit, args.parallel, args.claude_cmd,
                        args.dry_run, args.max_chars)
    print(json.dumps({k: rep[k] for k in rep if k != "results"}, indent=1, ensure_ascii=False))


def cmd_sweep(args):
    res = run_sweep(args.vault, args.model, args.limit, args.parallel, args.claude_cmd, args.max_chars)
    print(json.dumps(res, indent=1, ensure_ascii=False))
    if res["rejected"] or res["errors"]:
        sys.stderr.write("sweep: %d rejected, %d unparsed\n" % (len(res["rejected"]), len(res["errors"])))
        sys.exit(2)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("report")
    sp.add_argument("--vault", required=True)
    sp.add_argument("--owner", default="",
                    help="comma-separated owner/company entities to drop before overlap "
                         "(overrides the schema embedding.owners config)")
    sp.add_argument("--high", type=float, default=None,
                    help="cosine gate with a shared non-owner entity (default: schema embedding.gate_high or 0.86)")
    sp.add_argument("--fallback", type=float, default=None,
                    help="single-signal cosine gate (default: schema embedding.gate_fallback or 0.90)")
    sp.add_argument("--install", action="store_true",
                    help="self-install fastembed + numpy if missing (nightly cloud run); also VAULT_EMBED_AUTO_INSTALL=1")
    sp.set_defaults(func=cmd_report)
    sp = sub.add_parser("pending", help="unjudged candidate pairs (stdlib-only)")
    sp.add_argument("--vault", required=True)
    sp.add_argument("--limit", type=int, default=0)
    sp.add_argument("--contains", default="")
    sp.add_argument("--source", action="append", choices=["gate", "watched"])
    sp.add_argument("--with-text", action="store_true")
    sp.add_argument("--max-chars", type=int, default=6000)
    sp.set_defaults(func=cmd_pending)
    sp = sub.add_parser("judge", help="validate + cache comparator verdicts (stdlib-only)")
    sp.add_argument("--vault", required=True)
    sp.add_argument("--json", required=True, help="[{pair_id, verdict, confidence, reason}]")
    sp.add_argument("--model", required=True, help="judge_model id recorded on each verdict")
    sp.add_argument("--force", action="store_true",
                    help="overwrite an existing proposed judgment (confirmed stay locked)")
    sp.set_defaults(func=cmd_judge)
    sp = sub.add_parser("survivorship", help="pick winners + (re)write the review queue (stdlib-only)")
    sp.add_argument("--vault", required=True)
    sp.add_argument("--recompute", action="store_true",
                    help="re-run the rule on proposals that already have a winner_rule")
    sp.set_defaults(func=cmd_survivorship)
    sp = sub.add_parser("queue", help="read-only counts of the review queue")
    sp.add_argument("--vault", required=True)
    sp.add_argument("--line", action="store_true", help="print the one-line summary (empty if no queue)")
    sp.set_defaults(func=cmd_queue)
    sp = sub.add_parser("migrate", help="re-key loop state after a file/folder rename (stdlib-only)")
    sp.add_argument("--vault", required=True)
    sp.add_argument("--rename", nargs=2, metavar=("OLD", "NEW"), required=True,
                    help="old and new vault-relative path (a file, or a folder prefix)")
    sp.add_argument("--dry-run", action="store_true", help="report the re-key counts, write nothing")
    sp.set_defaults(func=cmd_migrate)
    sp = sub.add_parser("apply", help="apply decided review-queue blocks (Phase 4: fold and retire; stdlib-only)")
    sp.add_argument("--vault", required=True)
    sp.add_argument("--dry-run", action="store_true", help="print the exact per-block diff, write nothing")
    sp.add_argument("--folds", default=None,
                    help='JSON {pair_id: "<folded section markdown>"}; "" declares the loser a subset')
    sp.add_argument("--only", default=None, help="apply one block (pair_id or its 12-char prefix)")
    sp.add_argument("--today", default=None, help="ISO date to stamp; default the local date")
    sp.set_defaults(func=cmd_apply)
    for name, fn, hlp in (("calibrate", cmd_calibrate, "score a comparator model against golden-pairs.json via claude -p"),
                          ("sweep", cmd_sweep, "judge the pending backlog via claude -p (records --model in judge_model)")):
        sp = sub.add_parser(name, help=hlp)
        sp.add_argument("--vault", required=True)
        sp.add_argument("--model", required=True, help="exact model id passed to claude -p")
        sp.add_argument("--limit", type=int, default=0)
        sp.add_argument("--parallel", type=int, default=2)
        sp.add_argument("--claude-cmd", default="claude")
        sp.add_argument("--max-chars", type=int, default=6000)
        if name == "calibrate":
            sp.add_argument("--dry-run", action="store_true", help="validate + count, no calls")
        sp.set_defaults(func=fn)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
