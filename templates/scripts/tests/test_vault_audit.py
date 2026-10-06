import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import date

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vault-audit.py")
_spec = importlib.util.spec_from_file_location("vault_audit", SCRIPT)
va = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(va)

SCHEMA_MD = """# Vault Schema

```yaml
version: 1
root_whitelist:
  - CLAUDE.md
  - README.md
protected:
  - _generated
  - Archive
folders:
  - path: Work/Clients/*
    purpose: One folder per client
  - path: Work/Clients/*/Transcripts
    purpose: Call transcripts
    naming: "YYYY-MM-DD*"
    no_merge: true
  - path: Work/Transcripts
    purpose: Admin call transcripts, records
    no_merge: true
  - path: Resources/Reference
    purpose: Reference material
frontmatter_required: [type, created]
```

Prose layer here.

## Amendment Changelog
"""


class TestSchemaParser(unittest.TestCase):
    def test_parse_subset(self):
        block = va.extract_schema_block(SCHEMA_MD)
        schema = va.parse_yaml_subset(block)
        self.assertEqual(schema["version"], 1)
        self.assertEqual(schema["root_whitelist"], ["CLAUDE.md", "README.md"])
        self.assertEqual(len(schema["folders"]), 4)
        t = schema["folders"][1]
        self.assertEqual(t["path"], "Work/Clients/*/Transcripts")
        self.assertEqual(t["naming"], "YYYY-MM-DD*")
        self.assertIs(t["no_merge"], True)
        self.assertEqual(schema["frontmatter_required"], ["type", "created"])

    def test_scalar_with_colon_in_value(self):
        schema = va.parse_yaml_subset("purpose: Transcripts: raw text\n")
        self.assertEqual(schema["purpose"], "Transcripts: raw text")

    def test_missing_block_raises(self):
        with self.assertRaises(ValueError):
            va.extract_schema_block("# no fence here")


def make_vault(tmp):
    os.makedirs(os.path.join(tmp, ".claude"))
    os.makedirs(os.path.join(tmp, "Work", "Clients", "Acme", "Transcripts"))
    os.makedirs(os.path.join(tmp, "Resources", "Reference"))
    os.makedirs(os.path.join(tmp, va.HYGIENE_DIR))
    with open(os.path.join(tmp, va.HYGIENE_DIR, "vault-schema.md"), "w") as f:
        f.write(SCHEMA_MD)
    def w(rel, text):
        p = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)
    w("CLAUDE.md", "# rules")
    w("Work/Clients/Acme/Company Profile.md", "---\ntype: client-profile\ncreated: 2026-01-01\n---\nAcme profile body long enough to not be a stub.")
    w("_generated/Today.md", "render")
    return w


class TestWalkAndIndex(unittest.TestCase):
    def test_walk_skips_protected(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_vault(tmp)
            schema = va.load_schema(tmp)
            files = va.walk_vault(tmp, schema.get("protected", []))
            self.assertIn("CLAUDE.md", files)
            self.assertIn("Work/Clients/Acme/Company Profile.md", files)
            self.assertNotIn("_generated/Today.md", files)

    def test_refresh_index_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = make_vault(tmp)
            schema = va.load_schema(tmp)
            index = va.load_index(tmp)
            files = va.walk_vault(tmp, schema.get("protected", []))
            added, changed, deleted = va.refresh_index(tmp, index, files)
            self.assertIn("CLAUDE.md", added)
            self.assertTrue(index["files"]["CLAUDE.md"]["stale"])
            index["files"]["CLAUDE.md"]["stale"] = False
            va.save_index(tmp, index)
            # change one file, delete another
            w("CLAUDE.md", "# rules v2")
            os.remove(os.path.join(tmp, "Work", "Clients", "Acme", "Company Profile.md"))
            index = va.load_index(tmp)
            files = va.walk_vault(tmp, schema.get("protected", []))
            added, changed, deleted = va.refresh_index(tmp, index, files)
            self.assertEqual(added, [])
            self.assertEqual(changed, ["CLAUDE.md"])
            self.assertEqual(deleted, ["Work/Clients/Acme/Company Profile.md"])
            self.assertTrue(index["files"]["CLAUDE.md"]["stale"])


class TestStructuralChecks(unittest.TestCase):
    def test_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = make_vault(tmp)
            w("stray-root-note.md", "something at root")
            w("Randomplace/lost.md", "---\ntype: note\ncreated: 2026-01-01\n---\nlost file body that is long enough")
            w("Work/Clients/Acme/Transcripts/badname.md", "---\ntype: transcript\ncreated: 2026-01-01\n---\ncall text")
            w("Work/Clients/Acme/Transcripts/2026-08-01 Kickoff.md", "---\ntype: transcript\ncreated: 2026-08-01\n---\ncall text")
            w("Work/Clients/Acme/nofm.md", "no frontmatter here but a real body of text")
            w("Work/Clients/Acme/stub.md", "---\ntype: note\ncreated: 2026-01-01\n---\n")
            old = time.time() - 4 * 86400
            os.utime(os.path.join(tmp, "Work/Clients/Acme/stub.md"), (old, old))
            w("Work/Clients/Acme/dupe-a.md", "---\ntype: note\ncreated: 2026-01-01\n---\nsame body")
            w("Work/Clients/Acme/dupe-b.md", "---\ntype: note\ncreated: 2026-01-01\n---\nsame body")
            # Records under the no_merge Work/Transcripts folder: no frontmatter
            # and a near-empty body. Neither should be flagged -- adding
            # frontmatter or staging/expanding a stub would be a rewrite, and
            # records are never merged, split, or rewritten. Uses a literal
            # no_merge path. (The WILDCARD no_merge case -- e.g.
            # "Work/Clients/*/Transcripts" -- is covered separately in
            # test_wildcard_no_merge_excludes_records below.)
            w("Work/Transcripts/2026-08-02 no-frontmatter.md", "raw call text, no frontmatter at all")
            w("Work/Transcripts/2026-08-03 empty-stub.md", "---\ntype: transcript\ncreated: 2026-08-03\n---\n")
            old_transcript = time.time() - 4 * 86400
            os.utime(os.path.join(tmp, "Work/Transcripts/2026-08-03 empty-stub.md"),
                     (old_transcript, old_transcript))
            schema = va.load_schema(tmp)
            files = va.walk_vault(tmp, schema.get("protected", []))
            f = va.structural_checks(tmp, schema, files)
            self.assertIn("stray-root-note.md", f["root_clutter"])
            self.assertNotIn("CLAUDE.md", f["root_clutter"])
            self.assertIn("Randomplace/lost.md", f["unknown_folder"])
            self.assertIn("Work/Clients/Acme/Transcripts/badname.md", f["naming_violations"])
            self.assertNotIn("Work/Clients/Acme/Transcripts/2026-08-01 Kickoff.md", f["naming_violations"])
            self.assertIn("Work/Clients/Acme/nofm.md", f["missing_frontmatter"])
            self.assertIn("Work/Clients/Acme/stub.md", f["empty_stubs"])
            self.assertNotIn("Work/Transcripts/2026-08-02 no-frontmatter.md",
                             f["missing_frontmatter"])
            self.assertNotIn("Work/Transcripts/2026-08-03 empty-stub.md",
                             f["empty_stubs"])
            dupes = va.find_exact_duplicates(tmp, files, schema)
            self.assertEqual(len(dupes), 1)
            self.assertEqual(sorted(dupes[0]),
                             ["Work/Clients/Acme/dupe-a.md", "Work/Clients/Acme/dupe-b.md"])
            self.assertEqual(va.no_merge_paths(schema),
                             ["Work/Clients/*/Transcripts", "Work/Transcripts"])

    def test_wildcard_no_merge_excludes_records(self):
        # is_protected()-style plain prefix matching never matches a
        # wildcard no_merge pattern like "Work/Clients/*/Transcripts"
        # against a real path ("*" is never a literal segment a real
        # directory can prefix-equal), so that exclusion used to silently
        # fail. is_record() uses matching_folder's segment-aware ancestor
        # walk instead, so the wildcard case is excluded correctly too.
        with tempfile.TemporaryDirectory() as tmp:
            w = make_vault(tmp)
            # Record under the WILDCARD no_merge folder "Work/Clients/*/Transcripts":
            # no frontmatter at all. Must be excluded from missing_frontmatter.
            w("Work/Clients/Acme/Transcripts/2026-08-05 wildcard-no-fm.md",
              "raw call text for Acme, no frontmatter at all")
            # Non-record, frontmatter-less file in the same client folder but
            # NOT under Transcripts/. Must still be flagged.
            w("Work/Clients/Acme/plain-no-fm.md",
              "a plain client note with no frontmatter and a real body")
            schema = va.load_schema(tmp)
            files = va.walk_vault(tmp, schema.get("protected", []))
            f = va.structural_checks(tmp, schema, files)
            self.assertNotIn("Work/Clients/Acme/Transcripts/2026-08-05 wildcard-no-fm.md",
                             f["missing_frontmatter"])
            self.assertIn("Work/Clients/Acme/plain-no-fm.md", f["missing_frontmatter"])
            # Same story for empty_stubs, via is_record() directly.
            self.assertTrue(va.is_record("Work/Clients/Acme/Transcripts", schema))
            self.assertFalse(va.is_record("Work/Clients/Acme", schema))

    def test_matching_folder_segment_aware(self):
        folders = [
            {"path": "Work/Clients/*/Transcripts", "purpose": "Transcripts"},
        ]
        # Exact match: deep nested path should NOT match shallow pattern (segment-aware)
        self.assertIsNone(va.matching_folder("Work/Clients/Acme/Sub/Transcripts", folders, exact=True))
        # Exact match: correct path should match
        self.assertIsNotNone(va.matching_folder("Work/Clients/Acme/Transcripts", folders, exact=True))
        # Ancestor walk: deep nested path still doesn't match because no ancestor is 4 segments
        self.assertIsNone(va.matching_folder("Work/Clients/Acme/Sub/Transcripts", folders, exact=False))
        # But a file in the correct directory should match via exact match in ancestor walk
        self.assertIsNotNone(va.matching_folder("Work/Clients/Acme/Transcripts", folders, exact=False))


class TestCliHelpers(unittest.TestCase):
    def test_links_stage_purge(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = make_vault(tmp)
            w("Resources/Reference/Topic.md", "---\ntype: reference\ncreated: 2026-01-01\n---\nabout the topic in detail here")
            w("Work/Clients/Acme/notes.md", "---\ntype: note\ncreated: 2026-01-01\n---\nsee [[Topic]] for more")
            schema = va.load_schema(tmp)
            files = va.walk_vault(tmp, schema.get("protected", []))
            links = va.inbound_links(tmp, ["Resources/Reference/Topic.md"], files)
            self.assertEqual(links["Resources/Reference/Topic.md"],
                             ["Work/Clients/Acme/notes.md"])
            index = va.load_index(tmp)
            va.refresh_index(tmp, index, files)
            va.save_index(tmp, index)
            va.stage_files(tmp, ["Resources/Reference/Topic.md"])
            self.assertFalse(os.path.exists(os.path.join(tmp, "Resources/Reference/Topic.md")))
            trash = os.path.join(tmp, va.HYGIENE_DIR, "audit-trash", date.today().isoformat())
            self.assertTrue(os.path.exists(os.path.join(trash, "Resources", "Reference", "Topic.md")))
            self.assertNotIn("Resources/Reference/Topic.md", va.load_index(tmp)["files"])
            # purge: fake an old dated folder
            old_dir = os.path.join(tmp, va.HYGIENE_DIR, "audit-trash", "2020-01-01")
            os.makedirs(old_dir)
            self.assertEqual(va.purge_trash(tmp, days=7), 1)
            self.assertFalse(os.path.exists(old_dir))

    def test_inbound_links_path_qualified(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = make_vault(tmp)
            w("Resources/Reference/Topic.md", "---\ntype: reference\ncreated: 2026-01-01\n---\nabout the topic in detail here")
            # Full path-qualified and partial path-qualified link forms, no bare-stem link at all.
            w("Work/Clients/Acme/notes.md",
              "---\ntype: note\ncreated: 2026-01-01\n---\n"
              "see [[Resources/Reference/Topic]] for the full path form\n"
              "and [[Reference/Topic]] for the partial suffix form")
            schema = va.load_schema(tmp)
            files = va.walk_vault(tmp, schema.get("protected", []))
            links = va.inbound_links(tmp, ["Resources/Reference/Topic.md"], files)
            self.assertEqual(links["Resources/Reference/Topic.md"],
                             ["Work/Clients/Acme/notes.md"])

    def test_stage_files_preserves_directory_structure_no_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = make_vault(tmp)
            # Two distinct real paths that would have flattened to the
            # identical trash filename under the old "__"-joined scheme
            # because one folder segment itself contains "__". With the
            # relative directory structure preserved under the dated trash
            # dir, they land at their own distinct paths and never collide,
            # so no uniquify suffix is needed.
            w("Work__Clients/Acme/dup.md", "first file body long enough to matter")
            w("Work/Clients__Acme/dup.md", "second file body long enough, and different")
            schema = va.load_schema(tmp)
            files = va.walk_vault(tmp, schema.get("protected", []))
            index = va.load_index(tmp)
            va.refresh_index(tmp, index, files)
            va.save_index(tmp, index)
            va.stage_files(tmp, ["Work__Clients/Acme/dup.md", "Work/Clients__Acme/dup.md"])
            trash = os.path.join(tmp, va.HYGIENE_DIR, "audit-trash", date.today().isoformat())
            first = os.path.join(trash, "Work__Clients", "Acme", "dup.md")
            second = os.path.join(trash, "Work", "Clients__Acme", "dup.md")
            self.assertTrue(os.path.exists(first))
            self.assertTrue(os.path.exists(second))
            with open(first) as f:
                self.assertEqual(f.read(), "first file body long enough to matter")
            with open(second) as f:
                self.assertEqual(f.read(), "second file body long enough, and different")

    def test_update_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_vault(tmp)
            schema = va.load_schema(tmp)
            files = va.walk_vault(tmp, schema.get("protected", []))
            index = va.load_index(tmp)
            va.refresh_index(tmp, index, files)
            va.save_index(tmp, index)
            va.apply_row_update(tmp, "CLAUDE.md", "Vault rules and integrations",
                                ["Acme"], "ok")
            row = va.load_index(tmp)["files"]["CLAUDE.md"]
            self.assertEqual(row["concept"], "Vault rules and integrations")
            self.assertFalse(row["stale"])

    def test_stage_protected_files_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = make_vault(tmp)
            # Create a non-md file (should be skipped)
            w("Work/Clients/Acme/config.json", '{"key": "value"}')
            # Try to stage protected and non-md files
            schema = va.load_schema(tmp)
            files = va.walk_vault(tmp, schema.get("protected", []))
            index = va.load_index(tmp)
            va.refresh_index(tmp, index, files)
            va.save_index(tmp, index)
            # Attempt to stage .obsidian/workspace.json (protected) and config.json (non-md)
            # and _generated/Today.md (protected)
            va.stage_files(tmp, [
                ".obsidian/workspace.json",
                "Work/Clients/Acme/config.json",
                "_generated/Today.md"
            ])
            # All three should be skipped, files should still exist
            self.assertTrue(os.path.exists(os.path.join(tmp, "_generated", "Today.md")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "Work", "Clients", "Acme", "config.json")))
            # Trash should be empty (nothing actually staged)
            trash = os.path.join(tmp, va.HYGIENE_DIR, "audit-trash", date.today().isoformat())
            if os.path.exists(trash):
                self.assertEqual(len(os.listdir(trash)), 0)

    def test_stage_files_honours_today(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = make_vault(tmp)
            w("Resources/Reference/Old.md", "body long enough to be a real note here")
            schema = va.load_schema(tmp)
            files = va.walk_vault(tmp, schema.get("protected", []))
            index = va.load_index(tmp)
            va.refresh_index(tmp, index, files)
            va.save_index(tmp, index)
            va.stage_files(tmp, ["Resources/Reference/Old.md"], today="2026-01-02")
            dest = os.path.join(tmp, va.HYGIENE_DIR, "audit-trash", "2026-01-02",
                                "Resources", "Reference", "Old.md")
            self.assertTrue(os.path.exists(dest))
            self.assertFalse(os.path.exists(os.path.join(tmp, "Resources/Reference/Old.md")))

    def test_scan_no_purge_keeps_old_trash(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_vault(tmp)
            old = os.path.join(tmp, va.HYGIENE_DIR, "audit-trash", "2020-01-01")
            os.makedirs(old)
            with open(os.path.join(old, "x.md"), "w") as f:
                f.write("staged long ago")
            p = subprocess.run([sys.executable, SCRIPT, "scan", "--vault", tmp, "--no-purge"],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(json.loads(p.stdout)["trash_purged"], 0)
            self.assertTrue(os.path.isdir(old))
            p = subprocess.run([sys.executable, SCRIPT, "scan", "--vault", tmp],
                               capture_output=True, text=True)
            self.assertEqual(json.loads(p.stdout)["trash_purged"], 1)
            self.assertFalse(os.path.isdir(old))


class TestInvariantCheck(unittest.TestCase):
    def test_read_frontmatter_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = make_vault(tmp)
            w("Resources/Reference/Live.md",
              "---\ntype: reference\ncreated: 2026-01-01\ncanonical: true\n"
              "status: active\n---\nlive body")
            vals = va.read_frontmatter_values(
                os.path.join(tmp, "Resources/Reference/Live.md"))
            self.assertIs(vals.get("canonical"), True)
            self.assertEqual(vals.get("status"), "active")

    def test_clean_vault_no_violations(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = make_vault(tmp)
            w("Resources/Reference/Winner.md",
              "---\ntype: reference\ncreated: 2026-01-01\ncanonical: true\n"
              "status: active\n---\nthe live canonical doc body")
            w("Resources/Reference/Loser.md",
              "---\ntype: reference\ncreated: 2026-01-01\nstatus: superseded\n"
              "superseded_by: \"[[Winner]]\"\n---\nthe old superseded body")
            schema = va.load_schema(tmp)
            files = va.walk_vault(tmp, schema.get("protected", []))
            self.assertEqual(va.invariant_check(tmp, files), [])

    def test_dangling_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = make_vault(tmp)
            w("Resources/Reference/Loser.md",
              "---\ntype: reference\ncreated: 2026-01-01\nstatus: superseded\n"
              "superseded_by: \"[[Nonexistent]]\"\n---\nbody")
            schema = va.load_schema(tmp)
            files = va.walk_vault(tmp, schema.get("protected", []))
            v = va.invariant_check(tmp, files)
            self.assertTrue(any(x.startswith("invariant:dangling_superseded_by:") for x in v))

    def test_missing_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = make_vault(tmp)
            w("Resources/Reference/Loser.md",
              "---\ntype: reference\ncreated: 2026-01-01\nstatus: superseded\n---\nbody")
            schema = va.load_schema(tmp)
            files = va.walk_vault(tmp, schema.get("protected", []))
            v = va.invariant_check(tmp, files)
            self.assertTrue(any(x.startswith("invariant:superseded_no_pointer:") for x in v))

    def test_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = make_vault(tmp)
            w("Resources/Reference/A.md",
              "---\ntype: reference\ncreated: 2026-01-01\nstatus: superseded\n"
              "superseded_by: \"[[B]]\"\n---\nbody a")
            w("Resources/Reference/B.md",
              "---\ntype: reference\ncreated: 2026-01-01\nstatus: superseded\n"
              "superseded_by: \"[[C]]\"\n---\nbody b")
            w("Resources/Reference/C.md",
              "---\ntype: reference\ncreated: 2026-01-01\ncanonical: true\nstatus: active\n---\nbody c")
            schema = va.load_schema(tmp)
            files = va.walk_vault(tmp, schema.get("protected", []))
            v = va.invariant_check(tmp, files)
            self.assertTrue(any(x.startswith("invariant:superseded_chain:") for x in v))

    def test_canonical_and_superseded(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = make_vault(tmp)
            w("Resources/Reference/Bad.md",
              "---\ntype: reference\ncreated: 2026-01-01\ncanonical: true\n"
              "status: superseded\nsuperseded_by: \"[[Bad]]\"\n---\nbody")
            schema = va.load_schema(tmp)
            files = va.walk_vault(tmp, schema.get("protected", []))
            v = va.invariant_check(tmp, files)
            self.assertTrue(any(x.startswith("invariant:canonical_and_superseded:") for x in v))

    def test_confirmed_cluster_multi_canonical(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = make_vault(tmp)
            w("Resources/Reference/One.md",
              "---\ntype: reference\ncreated: 2026-01-01\ncanonical: true\nstatus: active\n---\none")
            w("Resources/Reference/Two.md",
              "---\ntype: reference\ncreated: 2026-01-01\ncanonical: true\nstatus: active\n---\ntwo")
            schema = va.load_schema(tmp)
            files = va.walk_vault(tmp, schema.get("protected", []))
            index = {"files": {}, "watched_clusters": [], "canonical_judgments": {
                "pid1": {"verdict": "version-fork", "status": "confirmed",
                         "relA": "Resources/Reference/One.md",
                         "relB": "Resources/Reference/Two.md"}}}
            v = va.invariant_check(tmp, files, index)
            self.assertTrue(any(x.startswith("invariant:cluster_multi_canonical:") for x in v))


class TestStaleCanonical(unittest.TestCase):
    def test_hash_since_set_backfilled_and_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_vault(tmp)
            files = va.walk_vault(tmp, ["_generated"])
            index = {"meta": {}, "files": {}, "watched_clusters": []}
            va.refresh_index(tmp, index, files, today="2026-01-01")
            rel = files[0]
            self.assertEqual(index["files"][rel]["hash_since"], "2026-01-01")
            va.refresh_index(tmp, index, files, today="2026-02-01")
            self.assertEqual(index["files"][rel]["hash_since"], "2026-01-01")
            index["files"][rel].pop("hash_since")
            va.refresh_index(tmp, index, files, today="2026-03-01")
            self.assertEqual(index["files"][rel]["hash_since"], "2026-03-01")
            with open(os.path.join(tmp, rel), "a") as f:
                f.write("\nchanged\n")
            va.refresh_index(tmp, index, files, today="2026-04-01")
            self.assertEqual(index["files"][rel]["hash_since"], "2026-04-01")

    def test_stale_canonical_flags_only_old_canonical_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_vault(tmp)
            for name, fm in (("Old Canon.md", "canonical: true\n"), ("Fresh Canon.md", "canonical: true\n"),
                             ("Old Plain.md", "")):
                with open(os.path.join(tmp, "Resources", "Reference", name), "w") as f:
                    f.write("---\ntype: reference\ncreated: 2026-01-01\n" + fm + "---\nbody\n")
            files = va.walk_vault(tmp, ["_generated"])
            index = {"meta": {}, "files": {}, "watched_clusters": []}
            va.refresh_index(tmp, index, files, today="2026-01-01")
            index["files"]["Resources/Reference/Fresh Canon.md"]["hash_since"] = "2026-09-01"
            out = va.stale_canonical(tmp, files, index, days=180, today="2026-09-18")
            self.assertEqual([r["rel"] for r in out], ["Resources/Reference/Old Canon.md"])
            self.assertEqual(out[0]["days_unchanged"], 260)
            self.assertEqual(va.stale_canonical(tmp, files, index, days=400, today="2026-09-18"), [])


class TestStaleDaysConfig(unittest.TestCase):
    def test_default_and_override(self):
        self.assertEqual(va.stale_days_from_schema({}), 180)
        self.assertEqual(va.stale_days_from_schema({"embedding": {"stale_days": 90}}), 90)
        self.assertEqual(va.stale_days_from_schema({"embedding": {"stale_days": "bad"}}), 180)


class TestInlineComments(unittest.TestCase):
    def test_inline_comments_stripped_in_embedding_block(self):
        block = ("version: 1\nembedding:\n"
                 "  owners: []                 # names dropped before overlap\n"
                 "  gate_high: 0.86            # cosine gate\n"
                 "  stale_days: 180            # staleness window\n"
                 "  canonical_home_dirs: [Resources/Reference]  # home folders\n")
        s = va.parse_yaml_subset(block)
        self.assertEqual(s["embedding"]["gate_high"], "0.86")
        self.assertEqual(s["embedding"]["stale_days"], 180)
        self.assertEqual(s["embedding"]["owners"], [])
        self.assertEqual(s["embedding"]["canonical_home_dirs"], ["Resources/Reference"])
        self.assertEqual(va.stale_days_from_schema(s), 180)

    def test_hash_inside_quotes_preserved(self):
        self.assertEqual(va.parse_yaml_subset('note: "a # b"\n')["note"], "a # b")

    def test_hash_inside_quoted_list_member_preserved(self):
        s = va.parse_yaml_subset('owners: ["Acme #1", plain]  # trailing\n')
        self.assertEqual(s["owners"], ["Acme #1", "plain"])

    def test_frontmatter_readers_strip_inline_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_vault(tmp)
            p = os.path.join(tmp, "Resources", "Reference", "C.md")
            with open(p, "w") as f:
                f.write("---\ntype: reference\ncanonical: true  # chosen\nstatus: active  # live\n---\nbody\n")
            vals = va.read_frontmatter_values(p)
            self.assertIs(vals.get("canonical"), True)
            self.assertEqual(vals.get("status"), "active")

    def test_invariant_sees_markers_with_inline_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = make_vault(tmp)
            w("Resources/Reference/Bad.md",
              "---\ntype: reference\ncreated: 2026-01-01\ncanonical: true  # keep\n"
              "status: superseded  # old\nsuperseded_by: \"[[Bad]]\"\n---\nbody")
            schema = va.load_schema(tmp)
            files = va.walk_vault(tmp, schema.get("protected", []))
            v = va.invariant_check(tmp, files)
            self.assertTrue(any(x.startswith("invariant:canonical_and_superseded:") for x in v))


if __name__ == "__main__":
    unittest.main()
