#!/usr/bin/env python3
"""
graph-render.py -- deterministic renderer for the vault's navigation layer.

Renders `Graph/index.md` and the generated block of each MOC (`Graph/Clients.md`,
`People.md`, `Projects.md`, `Concepts.md`, `SOPs.md`) from frontmatter plus the
nightly concept index (`_generated/vault-hygiene/vault-index.json`). Replaces the
hand-maintained index/MOC edits that the daily graph sync and /graph-sync used to
make: the graph is derived from metadata, not from inline wiki-links written for
Obsidian's graph view.

Each MOC keeps its frontmatter and any hand-written intro above the marker
`<!-- graph-render:begin -->`; everything between the begin and end markers is
regenerated. `index.md` is regenerated whole below its frontmatter.

A file is rewritten only when its generated body changed, so a quiet night does
not dirty git. `updated:` in frontmatter and the "Last updated" line move only
on a real change.

Usage:
  python3 scripts/graph-render.py                 # render index + MOCs (writes)
  python3 scripts/graph-render.py --dry-run       # report what would change
  python3 scripts/graph-render.py --stats         # counts only, no writes
  python3 scripts/graph-render.py --json out.json # also export the graph
                                                   # (nodes + edges) for a viewer

Scope: authored, non-record docs. Excluded: transcripts, daily notes, journals,
Archive* segments (except the Inactive Clients profiles listed under Clients),
Templates, Graph, docs, scripts, .claude, _generated, Attachments, Inbox, and every
top-level folder in PRIVATE_TOP (default Personal/), so a private folder stays out of
an exported or shared copy of Graph/. Docs with `status: superseded` or
`status: archived` are excluded.

Stdlib only.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
from collections import defaultdict

# Default vault: the directory two levels up from this script (the vault root when the script
# sits at `<vault>/scripts/`). Override at runtime with --vault. All other paths (Graph/, the
# concept index, schema, and vector cache) are derived from the selected vault inside main().
VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKIP_DIRS = {".git", ".obsidian", ".claude", "Attachments", "Templates", "Graph",
             "node_modules", "scripts", "docs", "_generated", "Inbox", ".handoffs",
             ".superpowers", ".playwright-mcp"}
# Top-level folders that never appear in Graph/ (so a private folder stays out of an exported
# or shared copy of Graph/). Default is {"Personal"}; override per vault with a
# `graph_private_top:` inline list in the vault schema YAML (see load_graph_config).
DEFAULT_PRIVATE_TOP = {"Personal"}
PRIVATE_TOP = set(DEFAULT_PRIVATE_TOP)
# The vault's own internal/agency folder (work that is not tied to a single client), if the
# vault uses one. Empty by default; set it with `graph_company_folder:` in the schema YAML and
# docs under that folder group under a "<folder> team" heading in People.md and count as that
# folder's own client in Clients/Projects.
COMPANY = ""
RECORD_TYPES = {"transcript", "daily", "inbox", "index"}
EXCLUDED_STATUS = {"superseded", "archived"}
ARCHIVE_SEG = re.compile(r"^Archive(?!\w)")
INACTIVE_CLIENTS_DIR = "Archive/Inactive Clients"
ACTIVE_MARK = "🟢"

BEGIN = "<!-- graph-render:begin -->"
END = "<!-- graph-render:end -->"
MAX_DESC = 160


# ---------- frontmatter ----------

def read_frontmatter(text):
    """Top-level scalar and inline-list keys only. Returns (dict, body)."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    block = text[4:end]
    body = text[end + 4:]
    fm = {}
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val.startswith("[") and val.endswith("]"):
            items = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",")]
            fm[key] = [i for i in items if i]
        else:
            fm[key] = val.strip('"').strip("'")
    return fm, body


def first_paragraph(body):
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("*") and s.endswith("*") \
                or s.startswith("---") or s.startswith("|") or s.startswith("```"):
            continue
        if s.startswith("- ") or s.startswith(">"):
            s = s[2:].strip()
        return s
    return ""


def clean_desc(s):
    s = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"\*\*|__|`", "", s)
    s = re.sub(r"\s+", " ", s).strip().rstrip(".")
    if len(s) > MAX_DESC:
        s = s[:MAX_DESC - 1].rstrip() + "…"
    return s


# ---------- scan ----------

def load_no_merge(schema_path):
    """Folder patterns flagged `no_merge: true` in the vault schema YAML (records:
    transcripts, batch outputs, archives). Records never appear in Graph/."""
    pats = []
    try:
        with open(schema_path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return pats
    m = re.search(r"```yaml\n(.*?)```", text, re.S)
    if not m:
        return pats
    cur = None
    for line in m.group(1).splitlines():
        pm = re.match(r"^\s*-\s*path:\s*(.+?)\s*$", line)
        if pm:
            cur = pm.group(1).strip().strip('"')
            continue
        if cur and re.match(r"^\s*no_merge:\s*true", line):
            pats.append(cur)
    return pats


def load_graph_config(schema_path):
    """Read optional graph keys from the first ```yaml block of the vault schema:
      graph_private_top:   inline list, e.g. [Personal, Finance] -- top folders kept out of Graph/
      graph_company_folder: scalar, e.g. MyCompany -- the vault's internal/agency folder
    Missing keys fall back to the defaults. Stdlib-only parsing (no yaml dependency)."""
    private_top = set(DEFAULT_PRIVATE_TOP)
    company = ""
    try:
        with open(schema_path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return private_top, company
    m = re.search(r"```yaml\n(.*?)```", text, re.S)
    block = m.group(1) if m else text
    pm = re.search(r"(?m)^graph_private_top:\s*\[([^\]]*)\]\s*$", block)
    if pm:
        items = [v.strip().strip('"').strip("'") for v in pm.group(1).split(",")]
        items = [i for i in items if i]
        if items:
            private_top = set(items)
    cm = re.search(r"(?m)^graph_company_folder:\s*(.+?)\s*$", block)
    if cm:
        company = cm.group(1).strip().strip('"').strip("'")
    return private_top, company


def _glob_to_re(pat):
    out = ""
    for ch in pat:
        if ch == "*":
            out += "[^/]*"
        else:
            out += re.escape(ch)
    return re.compile("^" + out + "(/|$)")


NO_MERGE_RE = []


def is_record_path(rel):
    d = os.path.dirname(rel)
    return any(r.match(d) for r in NO_MERGE_RE)


def in_scope_rel(rel):
    parts = rel.split("/")
    if parts[0] in PRIVATE_TOP:
        return False
    if is_record_path(rel) and not rel.endswith("/Company Profile.md"):
        return False
    if "/Transcripts/" in "/" + rel or "/Daily/" in "/" + rel or "/Journals/" in "/" + rel:
        return False
    if any(ARCHIVE_SEG.match(p) for p in parts[:-1]) and not rel.startswith(INACTIVE_CLIENTS_DIR + "/"):
        return False
    return True


def scan(vault):
    docs = {}
    for root, dirs, fnames in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in fnames:
            if not fn.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(root, fn), vault).replace(os.sep, "/")
            if not in_scope_rel(rel):
                continue
            try:
                with open(os.path.join(vault, rel), encoding="utf-8") as fh:
                    text = fh.read()
            except OSError:
                continue
            fm, body = read_frontmatter(text)
            docs[rel] = {"fm": fm, "body": body}
    return docs


def load_index(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh).get("files", {})
    except (OSError, ValueError):
        return {}


def strip_emoji(s):
    return re.sub(r"[\U0001F300-\U0001FAFF☀-➿️]", "", s).strip()


def stem(rel):
    return os.path.splitext(rel)[0]


def display_name(rel, fm):
    base = os.path.splitext(os.path.basename(rel))[0]
    if base == "Company Profile":
        return strip_emoji(rel.split("/")[-2])
    return strip_emoji(base)


def description(rel, doc, index):
    fm = doc["fm"]
    cands = [fm.get("summary", ""), (index.get(rel) or {}).get("concept", ""),
             first_paragraph(doc["body"])]
    for c in cands:
        if isinstance(c, str) and c.strip():
            return clean_desc(c)
    return ""


def link(rel, fm, label=None):
    return "[[%s|%s]]" % (stem(rel), label or display_name(rel, fm))


def entry(rel, doc, index):
    d = description(rel, doc, index)
    return "- %s%s" % (link(rel, doc["fm"]), (" -- " + d) if d else "")


def is_core(rel, doc):
    fm = doc["fm"]
    t = str(fm.get("type", "")).lower()
    if t in RECORD_TYPES:
        return False
    if str(fm.get("status", "")).lower() in EXCLUDED_STATUS and not rel.startswith(INACTIVE_CLIENTS_DIR + "/"):
        return False
    if rel.startswith(INACTIVE_CLIENTS_DIR + "/") and not rel.endswith("/Company Profile.md"):
        return False
    if os.path.basename(rel).startswith("_"):
        return False
    return True


def client_of(rel, fm):
    c = fm.get("client")
    if isinstance(c, str) and c:
        return strip_emoji(c)
    parts = rel.split("/")
    if len(parts) >= 3 and parts[0] == "Work" and parts[1] == "Clients":
        return strip_emoji(parts[2])
    if rel.startswith(INACTIVE_CLIENTS_DIR + "/"):
        return strip_emoji(parts[2])
    if COMPANY and parts[0] == COMPANY:
        return COMPANY
    return ""


# ---------- renderers ----------

def render_index(core, index):
    groups = defaultdict(list)
    for rel, doc in core.items():
        name = display_name(rel, doc["fm"])
        key = name[:1].upper()
        if not key.isalpha():
            key = "#"
        groups[key].append((name.lower(), rel))
    out = ["# Wiki Index", "",
           "Master directory of every core page in this vault, alphabetical by title. "
           "Does not include transcripts, daily notes, journals, archived or superseded docs, or anything under Personal/.",
           "",
           "*Generated by `scripts/graph-render.py` from frontmatter and the nightly concept index. "
           "Edit the source docs, not this file. Last updated: {DATE}.*", ""]
    for key in sorted(groups, key=lambda k: (k == "#", k)):
        out.append("## " + key)
        out.append("")
        for _, rel in sorted(groups[key]):
            out.append(entry(rel, core[rel], index))
        out.append("")
    return "\n".join(out).rstrip() + "\n", sum(len(v) for v in groups.values())


def client_sections(core, index):
    profiles = {rel: doc for rel, doc in core.items() if rel.endswith("/Company Profile.md")}
    people = {rel: doc for rel, doc in core.items() if str(doc["fm"].get("type", "")).lower() == "person"}
    projects = {rel: doc for rel, doc in core.items() if str(doc["fm"].get("type", "")).lower() == "project"}
    active, other, inactive = [], [], []
    for rel, doc in profiles.items():
        name = client_of(rel, doc["fm"])
        folder = rel.split("/")[-2]
        if rel.startswith(INACTIVE_CLIENTS_DIR + "/"):
            inactive.append((name.lower(), rel))
        elif ACTIVE_MARK in folder:
            active.append((name.lower(), rel))
        elif rel.startswith("Work/Clients/"):
            other.append((name.lower(), rel))

    def block(rel):
        doc = core[rel]
        name = client_of(rel, doc["fm"])
        lines = [entry(rel, doc, index)]
        contacts = sorted((display_name(p, d["fm"]), p) for p, d in people.items()
                          if strip_emoji(str(d["fm"].get("org", ""))).lower() == name.lower())
        if contacts:
            lines.append("  - Contacts: " + ", ".join(link(p, people[p]["fm"], n) for n, p in contacts))
        projs = sorted((display_name(p, d["fm"]), p) for p, d in projects.items()
                       if client_of(p, d["fm"]).lower() == name.lower())
        if projs:
            lines.append("  - Projects: " + ", ".join(link(p, projects[p]["fm"], n) for n, p in projs))
        folder = os.path.dirname(rel) + "/"
        n_docs = sum(1 for r in core if r.startswith(folder) and r != rel)
        if n_docs:
            lines.append("  - Other docs in folder: %d" % n_docs)
        return lines

    # Active client folders that have no Company Profile yet: list the folder with its doc count.
    profiled = {os.path.dirname(r) for r in profiles}
    folders = defaultdict(list)
    for r in core:
        if r.startswith("Work/Clients/") and r.count("/") >= 3:
            folders["/".join(r.split("/")[:3])].append(r)
    no_profile = []
    for folder, rels in folders.items():
        if folder in profiled:
            continue
        name = strip_emoji(folder.split("/")[-1])
        first = sorted(rels, key=lambda r: (not r.lower().startswith(folder.lower() + "/" + name.lower()), r))[0]
        no_profile.append((name.lower(), name, folder, first, len(rels)))

    out = []
    for title, rows in (("Active clients", active), ("Other client folders", other),
                        ("Inactive clients (archived)", inactive)):
        if not rows:
            continue
        out.append("## " + title)
        out.append("")
        for _, rel in sorted(rows):
            out.extend(block(rel))
        out.append("")
    if no_profile:
        out.append("## Client folders without a Company Profile yet")
        out.append("")
        for _, name, folder, first, n in sorted(no_profile):
            out.append("- **%s** -- %d doc%s in `%s/`; start at %s" % (
                name, n, "" if n == 1 else "s", folder, link(first, core[first]["fm"])))
        out.append("")
    return out, len(active) + len(other) + len(inactive) + len(no_profile)


def people_sections(core, index):
    people = {rel: doc for rel, doc in core.items() if str(doc["fm"].get("type", "")).lower() == "person"}
    groups = defaultdict(list)
    for rel, doc in people.items():
        org = strip_emoji(str(doc["fm"].get("org", ""))) or "Other"
        groups[org].append((display_name(rel, doc["fm"]).lower(), rel))
    out = []
    order = sorted(groups, key=lambda o: (not (COMPANY and o == COMPANY), o == "Other", o.lower()))
    for org in order:
        out.append("## " + (COMPANY + " team" if (COMPANY and org == COMPANY) else org))
        out.append("")
        for _, rel in sorted(groups[org]):
            doc = core[rel]
            role = str(doc["fm"].get("role", "")).replace("-", " ")
            line = entry(rel, doc, index)
            if role and role not in line:
                line += " (%s)" % role
            out.append(line)
        out.append("")
    return out, len(people)


def projects_sections(core, index):
    projects = {rel: doc for rel, doc in core.items() if str(doc["fm"].get("type", "")).lower() == "project"}
    groups = defaultdict(list)
    for rel, doc in projects.items():
        c = client_of(rel, doc["fm"]) or ("Projects" if rel.startswith("Projects/") else "Other")
        groups[c].append((display_name(rel, doc["fm"]).lower(), rel))
    out = []
    for c in sorted(groups, key=lambda k: (k in ("Projects", "Other"), k.lower())):
        out.append("## " + c)
        out.append("")
        for _, rel in sorted(groups[c]):
            out.append(entry(rel, core[rel], index))
        out.append("")
    return out, len(projects)


def concepts_sections(core, index):
    concepts = {rel: doc for rel, doc in core.items()
                if str(doc["fm"].get("type", "")).lower() == "concept" or rel.startswith("Resources/Concepts/")}
    out = ["## Concepts", ""]
    for rel in sorted(concepts, key=lambda r: display_name(r, concepts[r]["fm"]).lower()):
        doc = core[rel]
        out.append(entry(rel, doc, index))
        tags = doc["fm"].get("tags")
        if isinstance(tags, list) and tags:
            out.append("  - Tags: " + ", ".join(tags[:6]))
    out.append("")
    return out, len(concepts)


def sops_sections(core, index):
    sops = {rel: doc for rel, doc in core.items() if str(doc["fm"].get("type", "")).lower() == "sop"}
    guides = {rel: doc for rel, doc in core.items()
              if rel.startswith("Resources/Reference/") and str(doc["fm"].get("type", "")).lower() == "reference"}
    eng = {rel: doc for rel, doc in core.items() if rel.startswith("Work/Engineering/")}
    out = []
    for title, rows in (("Engineering (company-wide)", eng), ("SOPs", sops), ("Reference guides", guides)):
        if not rows:
            continue
        out.append("## " + title)
        out.append("")
        for rel in sorted(rows, key=lambda r: display_name(r, rows[r]["fm"]).lower()):
            out.append(entry(rel, core[rel], index))
        out.append("")
    return out, len(sops) + len(guides) + len(eng)


MOCS = {
    "Clients.md": ("Clients", client_sections,
                   "Every client with a Company Profile, grouped by status (folder marker 🟢 = active). Contacts come from "
                   "`type: person` pages whose `org` matches; projects from `type: project` pages with the client's `client:`."),
    "People.md": ("People", people_sections,
                  "One entry per `type: person` page, grouped by `org`."),
    "Projects.md": ("Projects", projects_sections,
                    "One entry per `type: project` page, grouped by client."),
    "Concepts.md": ("Concepts", concepts_sections,
                    "Concept pages (`Resources/Concepts/`, `type: concept`) that cut across clients."),
    "SOPs.md": ("SOPs & Guides", sops_sections,
                "Engineering process docs, `type: sop` pages, and reference guides."),
}


# ---------- writing ----------

def split_moc(text):
    """Returns (frontmatter_block, intro, old_generated, tail)."""
    fm_block = ""
    rest = text
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end >= 0:
            fm_block = text[:end + 4].rstrip("\n") + "\n"
            rest = text[end + 4:].lstrip("\n")
    if BEGIN in rest and END in rest:
        intro = rest[:rest.index(BEGIN)].rstrip("\n")
        tail = rest[rest.index(END) + len(END):].lstrip("\n")
        return fm_block, intro, True, tail
    # First conversion: keep the H1 and any italic/plain intro lines before the first H2.
    lines = rest.splitlines()
    intro_lines = []
    for line in lines:
        if line.startswith("## ") or line.startswith("- "):
            break
        if line.strip().startswith("*Last updated"):
            continue
        intro_lines.append(line)
    return fm_block, "\n".join(intro_lines).rstrip("\n"), False, ""


def set_updated(fm_block, today):
    if not fm_block:
        return fm_block
    if re.search(r"^updated:.*$", fm_block, re.M):
        return re.sub(r"^updated:.*$", "updated: " + today, fm_block, flags=re.M)
    return fm_block.replace("\n---", "\nupdated: %s\n---" % today, 1)


def render_moc(path, title, note, body_lines, today):
    old = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            old = fh.read()
    fm_block, intro, _, tail = split_moc(old)
    if not intro.strip():
        intro = "# " + title
    gen = [BEGIN, "", "*Generated by `scripts/graph-render.py`. %s Edit the source docs, not this block. Last updated: {DATE}.*" % note, ""]
    gen.extend(body_lines)
    gen.append(END)
    new_body = "\n".join(gen).rstrip() + "\n"
    # Compare ignoring the date placeholder.
    old_gen = ""
    if BEGIN in old and END in old:
        old_gen = old[old.index(BEGIN):old.index(END) + len(END)] + "\n"
    old_cmp = re.sub(r"Last updated: \d{4}-\d{2}-\d{2}", "Last updated: {DATE}", old_gen)
    changed = old_cmp.strip() != new_body.strip()
    if not changed:
        return old, False
    fm_block = set_updated(fm_block, today)
    # Normalize blank-line runs ONLY inside the generated block; the hand-written intro and tail
    # (which the docs promise to preserve) are joined verbatim with a single blank-line separator.
    gen_block = re.sub(r"\n{3,}", "\n\n", new_body.replace("{DATE}", today)).strip("\n")
    sections = [fm_block.rstrip("\n"), intro.rstrip("\n"), gen_block]
    if tail.strip():
        sections.append(tail.rstrip("\n"))
    return "\n\n".join(s for s in sections if s.strip()) + "\n", True


def render_index_file(path, body, today):
    old = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            old = fh.read()
    fm_block = ""
    old_body = old
    if old.startswith("---\n"):
        end = old.find("\n---", 4)
        if end >= 0:
            fm_block = old[:end + 4].rstrip("\n") + "\n"
            old_body = old[end + 4:].lstrip("\n")
    old_cmp = re.sub(r"Last updated: \d{4}-\d{2}-\d{2}", "Last updated: {DATE}", old_body)
    if old_cmp.strip() == body.strip():
        return old, False
    fm_block = set_updated(fm_block, today)
    return fm_block + "\n" + body.replace("{DATE}", today), True


# ---------- graph export ----------

WIKILINK = re.compile(r"\[\[([^\]|#]+)")


def export_graph(core, docs, index, out_path, vectors_path, top_k=3):
    rels = sorted(core)
    stems = {stem(r).lower(): r for r in rels}
    bases = defaultdict(list)
    for r in rels:
        bases[os.path.splitext(os.path.basename(r))[0].lower()].append(r)

    def resolve(t):
        t = t.strip()
        if t.lower() in stems:
            return stems[t.lower()]
        b = os.path.basename(t).lower()
        if b in bases and len(bases[b]) == 1:
            return bases[b][0]
        return None

    def node_of(r, fm):
        return {"id": r, "title": display_name(r, fm), "type": fm.get("type", ""),
                "client": client_of(r, fm), "status": fm.get("status", ""),
                "canonical": str(fm.get("canonical", "")).lower() == "true",
                "concept": (index.get(r) or {}).get("concept", ""),
                "entities": (index.get(r) or {}).get("entities", [])}

    node_ids = set(rels)
    nodes = [node_of(r, core[r]["fm"]) for r in rels]
    edges = []
    seen = set()

    def add(a, b, kind, w=1.0):
        if a == b or not a or not b:
            return
        key = (a, b, kind)
        if key in seen:
            return
        seen.add(key)
        edges.append({"source": a, "target": b, "kind": kind, "weight": round(w, 4)})

    for r in rels:
        body = core[r]["body"]
        for m in WIKILINK.finditer(body):
            t = resolve(m.group(1))
            if t:
                add(r, t, "link")
    # superseded_by edges: the SOURCE docs carry `status: superseded`, so they were filtered out
    # of `core`. Iterate the full scanned set, resolve the target against core, and add the
    # superseded source as a node so the edge is not dangling (it stays out of the navigation MOCs).
    for r in sorted(docs):
        sb = docs[r]["fm"].get("superseded_by")
        if isinstance(sb, str) and sb.startswith("[["):
            t = resolve(sb.strip("[]").split("|")[0])
            if t:
                if r not in node_ids:
                    node_ids.add(r)
                    nodes.append(node_of(r, docs[r]["fm"]))
                add(r, t, "superseded_by")
    # entity co-occurrence (from the concept index)
    by_entity = defaultdict(list)
    for r in rels:
        for e in (index.get(r) or {}).get("entities", []) or []:
            by_entity[str(e).lower()].append(r)
    for e, members in by_entity.items():
        if 2 <= len(members) <= 40:
            for i, a in enumerate(members):
                for b in members[i + 1:]:
                    add(a, b, "entity:" + e, 0.5)
    # semantic neighbors (optional, from the vector cache of the SELECTED vault)
    try:
        with open(vectors_path, encoding="utf-8") as fh:
            vec = json.load(fh).get("files", {})
    except (OSError, ValueError):
        vec = {}
    have = [r for r in rels if r in vec and vec[r].get("vector")]
    if have:
        import math
        def norm(v):
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            return [x / n for x in v]
        V = {r: norm(vec[r]["vector"]) for r in have}
        for a in have:
            sims = []
            va = V[a]
            for b in have:
                if a == b:
                    continue
                sims.append((sum(x * y for x, y in zip(va, V[b])), b))
            sims.sort(reverse=True)
            for s, b in sims[:top_k]:
                if s >= 0.80:
                    add(a, b, "semantic", s)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"generated": dt.date.today().isoformat(), "nodes": nodes, "edges": edges}, fh,
                  indent=1, ensure_ascii=False)
    return len(nodes), len(edges)


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=VAULT)
    ap.add_argument("--schema", default="", help="path to the vault schema YAML (default: "
                    "<vault>/_generated/vault-hygiene/vault-schema.md); supplies no_merge folders "
                    "and the optional graph_private_top / graph_company_folder keys")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stats", action="store_true", help="print counts only, write nothing")
    ap.add_argument("--json", help="also export nodes + edges to this path")
    args = ap.parse_args()

    global PRIVATE_TOP, COMPANY
    vault = args.vault
    graph_dir = os.path.join(vault, "Graph")
    schema_path = args.schema or os.path.join(vault, "_generated", "vault-hygiene", "vault-schema.md")
    PRIVATE_TOP, COMPANY = load_graph_config(schema_path)
    NO_MERGE_RE[:] = [_glob_to_re(p) for p in load_no_merge(schema_path)]
    docs = scan(vault)
    index = load_index(os.path.join(vault, "_generated", "vault-hygiene", "vault-index.json"))
    core = {r: d for r, d in docs.items() if is_core(r, d)}
    today = dt.date.today().isoformat()

    index_body, n_index = render_index(core, index)
    outputs = [("index.md", index_body, True)]
    counts = {"index": n_index}
    for fname, (title, fn, note) in MOCS.items():
        lines, n = fn(core, index)
        counts[fname[:-3].lower()] = n
        outputs.append((fname, (title, note, lines), False))

    writing = not (args.dry_run or args.stats)
    if writing:
        os.makedirs(graph_dir, exist_ok=True)  # first-time setup: Graph/ may not exist yet
    changed = []
    for fname, payload, is_index in outputs:
        path = os.path.join(graph_dir, fname)
        if is_index:
            text, did = render_index_file(path, payload, today)
        else:
            title, note, lines = payload
            text, did = render_moc(path, title, note, lines, today)
        if did:
            changed.append(fname)
            if writing:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(text)

    if args.json and not args.stats:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        vectors_path = os.path.join(vault, "_generated", "vault-hygiene", "vault-vectors.json")
        n, e = export_graph(core, docs, index, args.json, vectors_path)
        counts["graph_nodes"], counts["graph_edges"] = n, e

    mode = "dry-run" if args.dry_run else ("stats" if args.stats else "wrote")
    print("graph-render: %s | core docs %d | index %d | clients %d | people %d | projects %d | concepts %d | sops %d%s | changed: %s"
          % (mode, len(core), counts["index"], counts["clients"], counts["people"], counts["projects"],
             counts["concepts"], counts["sops"],
             (" | graph %d nodes / %d edges" % (counts["graph_nodes"], counts["graph_edges"])) if "graph_nodes" in counts else "",
             ", ".join(changed) if changed else "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
