import hashlib
import importlib.util
import json
import math
import os
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vault-embed.py")
_spec = importlib.util.spec_from_file_location("vault_embed", SCRIPT)
ve = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ve)


class TestPureHelpers(unittest.TestCase):
    def test_strip_frontmatter(self):
        raw = "---\ntype: note\ncreated: 2026-01-01\n---\nreal body here"
        self.assertEqual(ve.strip_frontmatter(raw).strip(), "real body here")

    def test_strip_frontmatter_none(self):
        self.assertEqual(ve.strip_frontmatter("no fm body").strip(), "no fm body")

    def test_embed_input_shape(self):
        s = ve.embed_input("Title", "concept line", "b" * 3000)
        self.assertTrue(s.startswith("Title\nconcept line\n"))
        self.assertEqual(len(s), len("Title\nconcept line\n") + 1500)

    def test_embed_hash_stable_and_sensitive(self):
        h1 = ve.embed_hash("abc")
        self.assertEqual(h1, ve.embed_hash("abc"))
        self.assertNotEqual(h1, ve.embed_hash("abd"))
        self.assertEqual(len(h1), 64)

    def test_normalize_unit_length(self):
        v = ve.normalize([3.0, 4.0])
        self.assertAlmostEqual(math.hypot(*v), 1.0, places=6)

    def test_normalize_zero_vector_safe(self):
        v = ve.normalize([0.0, 0.0])
        self.assertEqual(len(v), 2)
        self.assertTrue(all(math.isfinite(x) for x in v))

    def test_cosine_identical_and_orthogonal(self):
        self.assertAlmostEqual(ve.cosine([1.0, 0.0], [1.0, 0.0]), 1.0, places=6)
        self.assertAlmostEqual(ve.cosine([1.0, 0.0], [0.0, 1.0]), 0.0, places=6)


class TestGate(unittest.TestCase):
    def test_non_owner_entities_drops_owner_and_lowercases(self):
        self.assertEqual(
            ve.non_owner_entities(["Owner", "Acme"], ("owner",)),
            {"acme"},
        )

    def test_shared_non_owner_entity(self):
        self.assertTrue(ve.shared_non_owner_entity(
            ["Owner", "Acme"], ["acme", "Owner"], ("owner",)))
        self.assertFalse(ve.shared_non_owner_entity(
            ["Owner", "Acme"], ["Owner", "Bex"], ("owner",)))

    def test_gate_two_signal_path(self):
        self.assertTrue(ve.passes_gate(0.87, ["Acme"], ["Acme"], ("owner",)))
        self.assertFalse(ve.passes_gate(0.85, ["Acme"], ["Acme"], ("owner",)))
        self.assertFalse(ve.passes_gate(0.80, ["Acme"], ["Acme"], ("owner",)))

    def test_gate_requires_shared_entity_when_both_have_entities(self):
        self.assertFalse(ve.passes_gate(0.88, ["Acme"], ["Bex"], ("owner",)))
        self.assertTrue(ve.passes_gate(0.91, ["Acme"], ["Bex"], ("owner",)))

    def test_gate_empty_entity_fallback(self):
        self.assertTrue(ve.passes_gate(0.90, [], ["Acme"], ("owner",)))
        self.assertFalse(ve.passes_gate(0.89, [], ["Acme"], ("owner",)))
        self.assertTrue(ve.passes_gate(0.90, ["Owner"], ["Owner"], ("owner",)))


class TestPrefilters(unittest.TestCase):
    def test_numbered_series_pair(self):
        self.assertTrue(ve.is_numbered_series_pair(
            "Projects/Extraction/01-a.md", "Projects/Extraction/02-b.md"))
        self.assertFalse(ve.is_numbered_series_pair(
            "Projects/x/Onboarding.md", "Projects/x/Onboarding Guide.md"))
        self.assertFalse(ve.is_numbered_series_pair(
            "A/01-a.md", "B/02-b.md"))
        # date prefixes are not series numbers
        self.assertFalse(ve.is_numbered_series_pair(
            "specs/2026-06-04-ladder-design.md", "specs/2026-06-04-ladder-roadmap.md"))
        self.assertFalse(ve.is_numbered_series_pair(
            "specs/2026-06-04-ladder-design.md", "specs/01-intro.md"))

    def test_template_instance_pair(self):
        self.assertTrue(ve.is_template_instance_pair(
            "Work/Clients/Acme/Company Profile.md",
            "Work/Clients/Bex/Company Profile.md"))
        self.assertFalse(ve.is_template_instance_pair(
            "A/README.md", "A/README.md"))
        self.assertFalse(ve.is_template_instance_pair("A/x.md", "B/y.md"))

    def test_pair_id_stable_and_order_independent(self):
        p1 = ve.pair_id("a.md", "h1", "b.md", "h2")
        p2 = ve.pair_id("b.md", "h2", "a.md", "h1")
        self.assertEqual(p1, p2)
        self.assertNotEqual(p1, ve.pair_id("a.md", "h1x", "b.md", "h2"))

    def test_already_judged(self):
        pid = ve.pair_id("a.md", "h1", "b.md", "h2")
        self.assertFalse(ve.already_judged(pid, {}))
        self.assertTrue(ve.already_judged(pid, {pid: {"verdict": "distinct-purpose"}}))

    def test_prefiltered_reports_reason(self):
        self.assertEqual(
            ve.prefiltered("X/01-a.md", "X/02-b.md"), "numbered_series")
        self.assertEqual(
            ve.prefiltered("A/Company Profile.md", "B/Company Profile.md"),
            "template_instance")
        self.assertIsNone(ve.prefiltered("A/Onboarding.md", "A/Onboarding v2.md"))


class TestScope(unittest.TestCase):
    def test_archive_segment_out_of_scope(self):
        schema = {"folders": []}
        self.assertFalse(ve.in_scope("Notes/Archive/Old/Reasons.md", schema))
        self.assertFalse(ve.in_scope("Work/Reports/Archive - Old/Doc.md", schema))
        self.assertFalse(ve.in_scope("Archive/old.md", schema))
        self.assertTrue(ve.in_scope("Resources/Archives Guide/x.md", schema))
        self.assertTrue(ve.in_scope("Projects/SOPs/Archive Policy.md", schema))


def _mini_vault(tmp):
    hyg = os.path.join(tmp, ve.HYGIENE_DIR)
    os.makedirs(hyg)
    schema_md = (
        "# Schema\n\n```yaml\nversion: 1\nroot_whitelist:\n  - CLAUDE.md\n"
        "protected:\n  - _generated\nfolders:\n"
        "  - path: Resources/Reference\n    purpose: ref\n"
        "  - path: Work/Transcripts\n    purpose: records\n    no_merge: true\n"
        "frontmatter_required: [type, created]\n```\n"
    )
    with open(os.path.join(hyg, "vault-schema.md"), "w") as f:
        f.write(schema_md)

    def w(rel, text):
        p = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)
    return w


class TestLoaderAndEmbed(unittest.TestCase):
    def test_load_scope_docs_excludes_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = _mini_vault(tmp)
            w("Resources/Reference/A.md",
              "---\ntype: reference\ncreated: 2026-01-01\n---\nbody about topic A")
            w("Work/Transcripts/2026-01-01 call.md", "raw transcript, a record")
            schema = ve.va.load_schema(tmp)
            index = {"meta": {}, "files": {
                "Resources/Reference/A.md": {"concept": "A: topic", "entities": ["Acme"],
                                              "hash": "contentA"},
                "Work/Transcripts/2026-01-01 call.md": {"concept": "", "entities": []},
            }, "watched_clusters": []}
            docs = ve.load_scope_docs(tmp, schema, index)
            rels = {d["rel"] for d in docs}
            self.assertIn("Resources/Reference/A.md", rels)
            self.assertNotIn("Work/Transcripts/2026-01-01 call.md", rels)
            d = docs[0]
            self.assertTrue(d["text"].startswith("A\nA: topic\n"))
            self.assertEqual(len(d["embed_hash"]), 64)
            self.assertEqual(d["hash"], "contentA")

    def test_embed_missing_graceful_skip(self):
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "fastembed" or name.startswith("fastembed."):
                raise ImportError("no fastembed")
            return real_import(name, *a, **k)

        builtins.__import__ = fake_import
        try:
            cache = {"meta": {"vector_model": ve.VECTOR_MODEL, "dims": ve.DIMS}, "files": {}}
            docs = [{"rel": "A.md", "embed_hash": "h", "text": "x"}]
            out, ok = ve.embed_missing(docs, cache)
            self.assertFalse(ok)
            self.assertEqual(out, cache)
        finally:
            builtins.__import__ = real_import

    def test_vectors_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            _mini_vault(tmp)
            cache = {"meta": {"vector_model": ve.VECTOR_MODEL, "dims": ve.DIMS},
                     "files": {"A.md": {"embed_hash": "h", "vector": [0.1234, 0.5678]}}}
            ve.save_vectors(tmp, cache)
            back = ve.load_vectors(tmp)
            self.assertEqual(back["files"]["A.md"]["embed_hash"], "h")
            self.assertEqual(back["meta"]["dims"], ve.DIMS)


class TestGenerateCandidates(unittest.TestCase):
    def _docs(self):
        return [
            {"rel": "A/Onboarding.md", "entities": ["Acme"], "embed_hash": "hA", "hash": "cA"},
            {"rel": "A/Onboarding v2.md", "entities": ["Acme"], "embed_hash": "hB", "hash": "cB"},
            {"rel": "A/01-x.md", "entities": ["Acme"], "embed_hash": "hC", "hash": "cC"},
            {"rel": "A/02-y.md", "entities": ["Acme"], "embed_hash": "hD", "hash": "cD"},
        ]

    def test_emits_gated_pair_and_drops_series(self):
        docs = self._docs()
        vecs = {
            "A/Onboarding.md": [1.0, 0.0],
            "A/Onboarding v2.md": [0.98, 0.20],
            "A/01-x.md": [0.0, 1.0],
            "A/02-y.md": [0.10, 0.99],
        }
        cands = ve.generate_candidates(
            docs, vecs, watched_pairs=set(), judgments={}, owners=("owner",))
        pairs = {tuple(sorted((c["relA"], c["relB"]))) for c in cands}
        self.assertIn(tuple(sorted(("A/Onboarding.md", "A/Onboarding v2.md"))), pairs)
        self.assertNotIn(tuple(sorted(("A/01-x.md", "A/02-y.md"))), pairs)

    def test_watched_pair_bypasses_gate(self):
        docs = self._docs()[:2]
        vecs = {"A/Onboarding.md": [1.0, 0.0], "A/Onboarding v2.md": [0.0, 1.0]}
        wp = {tuple(sorted(("A/Onboarding.md", "A/Onboarding v2.md")))}
        cands = ve.generate_candidates(docs, vecs, watched_pairs=wp, judgments={}, owners=("owner",))
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["source"], "watched")

    def test_watched_pair_bypasses_prefilters(self):
        docs = self._docs()[2:]
        vecs = {"A/01-x.md": [1.0, 0.0], "A/02-y.md": [0.0, 1.0]}
        wp = {("A/01-x.md", "A/02-y.md")}
        cands = ve.generate_candidates(docs, vecs, watched_pairs=wp, judgments={}, owners=("owner",))
        self.assertEqual(len(cands), 1)
        self.assertEqual(ve.generate_candidates(docs, vecs, watched_pairs=set(), judgments={}, owners=("owner",)), [])

    def test_pair_id_uses_content_hash(self):
        docs = self._docs()[:2]
        vecs = {"A/Onboarding.md": [1.0, 0.0], "A/Onboarding v2.md": [0.98, 0.20]}
        cands = ve.generate_candidates(docs, vecs, watched_pairs=set(), judgments={}, owners=("owner",))
        self.assertEqual(cands[0]["pair_id"], ve.pair_id("A/Onboarding.md", "cA", "A/Onboarding v2.md", "cB"))
        self.assertEqual({cands[0]["hashA"], cands[0]["hashB"]}, {"cA", "cB"})

    def test_already_judged_dropped(self):
        docs = self._docs()[:2]
        vecs = {"A/Onboarding.md": [1.0, 0.0], "A/Onboarding v2.md": [0.98, 0.20]}
        pid = ve.pair_id("A/Onboarding.md", "cA", "A/Onboarding v2.md", "cB")
        cands = ve.generate_candidates(
            docs, vecs, watched_pairs=set(),
            judgments={pid: {"verdict": "distinct-purpose"}}, owners=("owner",))
        self.assertEqual(cands, [])


class TestJudgments(unittest.TestCase):
    def _cands(self):
        pid = ve.pair_id("A/x.md", "cA", "A/y.md", "cB")
        return {pid: {"pair_id": pid, "relA": "A/x.md", "relB": "A/y.md",
                      "hashA": "cA", "hashB": "cB", "cosine": 0.9, "source": "gate",
                      "shared_entity": True}}

    def test_list_pending_filters_and_caps(self):
        cands = list(self._cands().values())
        pid = cands[0]["pair_id"]
        self.assertEqual(len(ve.list_pending(cands, {})), 1)
        self.assertEqual(ve.list_pending(cands, {pid: {"verdict": "duplicate"}}), [])
        self.assertEqual(ve.list_pending(cands, {}, contains="nomatch"), [])
        self.assertEqual(len(ve.list_pending(cands, {}, contains="A/x")), 1)
        self.assertEqual(ve.list_pending(cands, {}, sources=("watched",)), [])
        self.assertEqual(len(ve.list_pending(cands * 3, {}, limit=2)), 2)

    def test_sanitize_reason(self):
        self.assertEqual(ve.sanitize_reason("a \u2014 b\n  c"), "a, b c")
        self.assertEqual(len(ve.sanitize_reason("x" * 500)), 300)

    def test_validate_verdict_codes(self):
        cands = self._cands()
        pid = next(iter(cands))
        ok = {"pair_id": pid, "verdict": "duplicate", "confidence": 0.7, "reason": "same doc"}
        self.assertIsNone(ve.validate_verdict(ok, cands))
        self.assertEqual(ve.validate_verdict({}, cands), "missing_pair_id")
        self.assertEqual(ve.validate_verdict(dict(ok, pair_id="nope"), cands), "unknown_pair")
        self.assertEqual(ve.validate_verdict(dict(ok, verdict="same"), cands), "bad_verdict")
        self.assertEqual(ve.validate_verdict(dict(ok, confidence=1.5), cands), "bad_confidence")
        self.assertEqual(ve.validate_verdict(dict(ok, confidence="high"), cands), "bad_confidence")
        self.assertEqual(ve.validate_verdict(dict(ok, confidence=True), cands), "bad_confidence")
        self.assertEqual(ve.validate_verdict(dict(ok, reason="  "), cands), "missing_reason")

    def test_apply_verdicts_writes_full_record(self):
        cands = self._cands()
        pid = next(iter(cands))
        js = {}
        res = ve.apply_verdicts(js, cands, [
            {"pair_id": pid, "verdict": "version-fork", "confidence": 0.8, "reason": "v2 \u2014 newer"}],
            model="test-model", today="2026-09-18")
        self.assertEqual(res["accepted"], [pid])
        j = js[pid]
        self.assertEqual(j["relA"], "A/x.md")
        self.assertEqual(j["hashB"], "cB")
        self.assertEqual(j["verdict"], "version-fork")
        self.assertIsNone(j["winner"])
        self.assertEqual(j["status"], "proposed")
        self.assertEqual(j["judge_model"], "test-model")
        self.assertEqual(j["decided_at"], "2026-09-18")
        self.assertEqual(j["reason"], "v2, newer")
        self.assertEqual(j["cosine"], 0.9)

    def test_apply_verdicts_replays_and_rejects(self):
        cands = self._cands()
        pid = next(iter(cands))
        js = {}
        v = {"pair_id": pid, "verdict": "duplicate", "confidence": 0.9, "reason": "r"}
        ve.apply_verdicts(js, cands, [v], "m", "2026-09-18")
        res = ve.apply_verdicts(js, cands, [dict(v, verdict="distinct-purpose")], "m", "2026-09-19")
        self.assertEqual(res["replayed"], [pid])
        self.assertEqual(js[pid]["verdict"], "duplicate")
        res = ve.apply_verdicts(js, cands, [dict(v, verdict="distinct-purpose")], "m", "2026-09-19", force=True)
        self.assertEqual(res["accepted"], [pid])
        self.assertEqual(js[pid]["verdict"], "distinct-purpose")
        js[pid]["status"] = "confirmed"
        res = ve.apply_verdicts(js, cands, [dict(v, verdict="duplicate")], "m", "2026-09-20", force=True)
        self.assertEqual(res["rejected"], [{"pair_id": pid, "error": "confirmed_locked"}])
        self.assertEqual(js[pid]["verdict"], "distinct-purpose")
        res = ve.apply_verdicts(js, cands, [{"pair_id": "zzz", "verdict": "duplicate",
                                             "confidence": 0.5, "reason": "r"}], "m", "2026-09-20")
        self.assertEqual(res["rejected"][0]["error"], "unknown_pair")

    def test_force_rejudges_cached_pair_without_live_candidate(self):
        cands = self._cands()
        pid = next(iter(cands))
        js = {}
        ve.apply_verdicts(js, cands, [{"pair_id": pid, "verdict": "distinct-purpose",
                                       "confidence": 0.7, "reason": "r"}], "m1", "2026-09-18")
        v = {"pair_id": pid, "verdict": "version-fork", "confidence": 0.9, "reason": "owner override"}
        # candidate list empty (report dropped judged pairs): plain submit is unknown, force replays from cache
        self.assertEqual(ve.apply_verdicts(js, {}, [v], "m2", "2026-09-19")["rejected"][0]["error"], "unknown_pair")
        res = ve.apply_verdicts(js, {}, [v], "m2", "2026-09-19", force=True)
        self.assertEqual(res["accepted"], [pid])
        self.assertEqual(js[pid]["verdict"], "version-fork")
        self.assertEqual(js[pid]["judge_model"], "m2")
        self.assertEqual(js[pid]["relA"], "A/x.md")
        self.assertEqual(js[pid]["cosine"], 0.9)
        self.assertEqual(js[pid]["superseded_verdict"], {"verdict": "distinct-purpose", "judge_model": "m1", "decided_at": "2026-09-18"})

    def test_fresh_and_summary(self):
        cands = self._cands()
        pid = next(iter(cands))
        js = {}
        ve.apply_verdicts(js, cands, [{"pair_id": pid, "verdict": "duplicate",
                                       "confidence": 0.9, "reason": "r"}], "m", "2026-09-18")
        files = {"A/x.md": {"hash": "cA"}, "A/y.md": {"hash": "cB"}}
        self.assertTrue(ve.judgment_is_fresh(pid, js[pid], files))
        files["A/y.md"]["hash"] = "changed"
        self.assertFalse(ve.judgment_is_fresh(pid, js[pid], files))
        s = ve.judgment_summary(js, files)
        self.assertEqual(s["total"], 1)
        self.assertEqual(s["by_verdict"], {"duplicate": 1})
        self.assertEqual(s["by_status"], {"proposed": 1})
        self.assertEqual(s["stale"], 1)


class TestJudgeCli(unittest.TestCase):
    def test_pending_then_judge_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = _mini_vault(tmp)
            w("Resources/Reference/A.md", "---\ntype: reference\n---\nalpha body")
            w("Resources/Reference/B.md", "---\ntype: reference\n---\nbeta body")
            pid = ve.pair_id("Resources/Reference/A.md", "cA", "Resources/Reference/B.md", "cB")
            cands = {"meta": {"count": 1}, "candidates": [{
                "pair_id": pid, "relA": "Resources/Reference/A.md", "relB": "Resources/Reference/B.md",
                "hashA": "cA", "hashB": "cB", "cosine": 0.91, "source": "gate", "shared_entity": True}]}
            with open(os.path.join(tmp, ve.HYGIENE_DIR, "canonical-candidates.json"), "w") as f:
                json.dump(cands, f)
            ve.va.save_index(tmp, {"meta": {}, "files": {
                "Resources/Reference/A.md": {"hash": "cA", "concept": "", "entities": [], "verdict": "ok"},
                "Resources/Reference/B.md": {"hash": "cB", "concept": "", "entities": [], "verdict": "ok"},
            }, "watched_clusters": []})

            out = ve.build_pending(tmp, limit=0, contains="", sources=(), with_text=True, max_chars=50)
            self.assertEqual(out["meta"]["pending"], 1)
            self.assertIn("alpha body", out["pairs"][0]["textA"])

            vpath = os.path.join(tmp, "verdicts.json")
            with open(vpath, "w") as f:
                json.dump([{"pair_id": pid, "verdict": "duplicate", "confidence": 0.9, "reason": "same"},
                           {"pair_id": "bogus", "verdict": "duplicate", "confidence": 0.9, "reason": "x"}], f)
            res = ve.run_judge(tmp, vpath, model="m", force=False)
            self.assertEqual(res["accepted"], [pid])
            self.assertEqual(res["rejected"][0]["error"], "unknown_pair")
            idx = ve.va.load_index(tmp)
            self.assertEqual(idx["canonical_judgments"][pid]["verdict"], "duplicate")

            # idempotent: second run replays, index untouched
            mtime = os.path.getmtime(os.path.join(tmp, ve.HYGIENE_DIR, "vault-index.json"))
            res = ve.run_judge(tmp, vpath, model="m", force=False)
            self.assertEqual(res["replayed"], [pid])
            self.assertEqual(mtime, os.path.getmtime(os.path.join(tmp, ve.HYGIENE_DIR, "vault-index.json")))

            out = ve.build_pending(tmp)
            self.assertEqual(out["meta"]["pending"], 0)
            self.assertEqual(out["meta"]["judged"], 1)

            # report renders the judgment section without touching any doc
            a_path = os.path.join(tmp, "Resources/Reference/A.md")
            with open(a_path) as f:
                before = f.read()
            ve.write_report(tmp, [], [], True, idx["canonical_judgments"], idx["files"])
            with open(os.path.join(tmp, ve.HYGIENE_DIR, "embed-candidate-report.md")) as f:
                rep = f.read()
            self.assertIn("## Judgments", rep)
            self.assertIn("duplicate", rep)
            with open(a_path) as f:
                self.assertEqual(before, f.read())


class TestSurvivorship(unittest.TestCase):
    def f(self, rel, **kw):
        d = {"rel": rel, "canonical": False, "status": "", "type": "", "updated": "", "mtime_date": "2026-01-01"}
        d.update(kw)
        return d

    def test_existing_canonical_wins(self):
        a = self.f("A/draft.md", canonical=True, status="draft")
        b = self.f("Projects/SOPs/Live.md", type="sop", updated="2026-09-01")
        self.assertEqual(ve.survivorship(a, b), ("A/draft.md", "existing_canonical"))
        self.assertEqual(ve.survivorship(a, dict(b, canonical=True))[1], "tie")

    def test_priority_ranks(self):
        self.assertEqual(ve.priority_rank(self.f("Projects/SOPs/X.md", type="sop")), 3)
        self.assertEqual(ve.priority_rank(self.f("Work/Clients/Acme/Company Profile.md")), 3)
        self.assertEqual(ve.priority_rank(self.f("Resources/Reference/Guide.md")), 3)
        self.assertEqual(ve.priority_rank(self.f("Projects/Plan.md")), 2)
        self.assertEqual(ve.priority_rank(self.f("Notes/_Originals/Notes.md")), 1)
        self.assertEqual(ve.priority_rank(self.f("Projects/2026-09-07-accord-draft.md")), 1)
        self.assertEqual(ve.priority_rank(self.f("Projects/2026-09-07-notes.md")), 1)
        self.assertEqual(ve.priority_rank(self.f("Resources/Reference/2026-06-04-x.md", status="draft")), 1)
        self.assertEqual(ve.priority_rank(self.f("Resources/Reference/2026-06-04-x.md")), 3)
        self.assertEqual(ve.priority_rank(self.f("A/old.md", status="superseded")), 0)

    def test_priority_beats_recency_then_recency_then_tie(self):
        sop = self.f("Projects/SOPs/Live.md", type="sop", updated="2026-01-01")
        newer_draft = self.f("Projects/Live draft.md", updated="2026-09-01")
        self.assertEqual(ve.survivorship(sop, newer_draft), ("Projects/SOPs/Live.md", "priority"))
        a = self.f("Projects/A.md", updated="2026-03-01")
        b = self.f("Projects/B.md", mtime_date="2026-05-01")
        self.assertEqual(ve.survivorship(a, b), ("Projects/B.md", "recency"))
        self.assertEqual(ve.survivorship(a, dict(b, mtime_date="2026-03-01")), (None, "tie"))

    def test_apply_survivorship_sets_fields_once(self):
        js = {"p1": {"relA": "Projects/A.md", "relB": "Projects/SOPs/B.md", "verdict": "version-fork", "status": "proposed"},
              "p2": {"relA": "X.md", "relB": "Y.md", "verdict": "distinct-purpose", "status": "proposed"}}
        facts = {"Projects/A.md": self.f("Projects/A.md"), "Projects/SOPs/B.md": self.f("Projects/SOPs/B.md", type="sop")}
        n = ve.apply_survivorship(js, lambda rel: facts[rel], "2026-09-18")
        self.assertEqual(n, 1)
        self.assertEqual(js["p1"]["winner"], "Projects/SOPs/B.md")
        self.assertEqual(js["p1"]["loser"], "Projects/A.md")
        self.assertEqual(js["p1"]["winner_rule"], "priority")
        self.assertEqual(js["p1"]["survivorship_at"], "2026-09-18")
        self.assertNotIn("winner_rule", js["p2"])
        facts["Projects/A.md"]["canonical"] = True
        self.assertEqual(ve.apply_survivorship(js, lambda rel: facts[rel], "2026-09-19"), 0)
        self.assertEqual(ve.apply_survivorship(js, lambda rel: facts[rel], "2026-09-19", recompute=True), 1)
        self.assertEqual(js["p1"]["winner"], "Projects/A.md")

    def test_read_fm_scalars_and_doc_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = _mini_vault(tmp)
            w("Resources/Reference/A.md",
              "---\ntype: sop\nstatus: active\ncanonical: true\nupdated: 2026-08-01\n---\nbody")
            f = ve.doc_facts(tmp, "Resources/Reference/A.md")
            self.assertTrue(f["canonical"])
            self.assertEqual(f["type"], "sop")
            self.assertEqual(f["updated"], "2026-08-01")
            self.assertEqual(len(f["mtime_date"]), 10)
            self.assertEqual(ve.doc_facts(tmp, "missing.md")["mtime_date"], "")


class TestReviewQueue(unittest.TestCase):
    def _js(self):
        return {"a" * 64: {"relA": "Projects/A.md", "relB": "Projects/SOPs/B.md", "verdict": "version-fork",
                           "confidence": 0.9, "reason": "B is the live SOP", "status": "proposed",
                           "winner": "Projects/SOPs/B.md", "loser": "Projects/A.md", "winner_rule": "priority"},
                "b" * 64: {"relA": "X.md", "relB": "Y.md", "verdict": "duplicate", "confidence": 0.7,
                           "reason": "same", "status": "proposed", "winner": None, "loser": None, "winner_rule": "tie"},
                "c" * 64: {"relA": "P.md", "relB": "Q.md", "verdict": "distinct-purpose", "status": "proposed"},
                "d" * 64: {"relA": "R.md", "relB": "S.md", "verdict": "duplicate", "status": "confirmed",
                           "winner": "R.md", "loser": "S.md", "winner_rule": "recency"}}

    def test_render_and_parse_roundtrip(self):
        text = ve.render_review_queue(self._js(), {}, "2026-09-18")
        self.assertIn("### aaaaaaaaaaaa  verdict: version-fork  confidence: 0.90  rule: priority", text)
        self.assertIn("winner:  Projects/SOPs/B.md", text)
        self.assertIn("tie: true", text)
        self.assertNotIn("P.md", text)
        self.assertNotIn("R.md", text)
        self.assertEqual(ve.parse_review_decisions(text), {"a" * 64: "pending", "b" * 64: "pending"})
        edited = text.replace("decision: pending", "decision: confirm", 1)
        # ties render first, so the first block is the tie (b)
        self.assertEqual(ve.parse_review_decisions(edited)["b" * 64], "confirm")

    def test_regeneration_preserves_decisions(self):
        text = ve.render_review_queue(self._js(), {"a" * 64: "swap"}, "2026-09-18")
        self.assertIn("decision: swap", text)
        self.assertEqual(ve.queue_counts(text), {"open": 1, "confirm": 0, "confirm-keep": 0, "reject": 0, "swap": 1, "total": 2})
        kept = ve.render_review_queue(self._js(), {"a" * 64: "confirm-keep"}, "2026-09-18")
        self.assertEqual(ve.parse_review_decisions(kept)["a" * 64], "confirm-keep")

    def test_write_review_queue_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            _mini_vault(tmp)
            c = ve.write_review_queue(tmp, self._js())
            self.assertEqual(c["open"], 2)
            p = os.path.join(tmp, ve.REVIEW_PATH)
            with open(p) as f:
                t = f.read().replace("decision: pending", "decision: reject", 1)
            with open(p, "w") as f:
                f.write(t)
            c = ve.write_review_queue(tmp, self._js())
            self.assertEqual(c["reject"], 1)
            self.assertEqual(c["open"], 1)
            self.assertEqual(ve.queue_line(c),
                             "1 supersession proposals pending review (1 decided, applied by the next audit run)")
            self.assertEqual(ve.queue_line({"open": 0, "confirm": 0, "confirm-keep": 0, "reject": 0, "swap": 0, "total": 0}), "")

    def test_run_survivorship_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = _mini_vault(tmp)
            w("Resources/Reference/A.md", "---\ntype: reference\n---\nlive")
            w("Resources/Reference/A draft.md", "---\ntype: reference\n---\nold")
            pid = ve.pair_id("Resources/Reference/A draft.md", "c1", "Resources/Reference/A.md", "c2")
            ve.va.save_index(tmp, {"meta": {}, "files": {}, "watched_clusters": [], "canonical_judgments": {
                pid: {"relA": "Resources/Reference/A draft.md", "relB": "Resources/Reference/A.md",
                      "hashA": "c1", "hashB": "c2", "verdict": "version-fork", "winner": None,
                      "confidence": 0.8, "reason": "r", "status": "proposed"}}})
            res = ve.run_survivorship(tmp)
            self.assertEqual(res["survivorship_applied"], 1)
            self.assertEqual(res["queue"]["open"], 1)
            j = ve.va.load_index(tmp)["canonical_judgments"][pid]
            self.assertEqual(j["winner"], "Resources/Reference/A.md")
            self.assertEqual(j["winner_rule"], "priority")
            res = ve.run_survivorship(tmp)
            self.assertEqual(res["survivorship_applied"], 0)
            with open(os.path.join(tmp, "Resources/Reference/A.md")) as f:
                self.assertEqual(f.read(), "---\ntype: reference\n---\nlive")


STUB = """#!/usr/bin/env python3
import sys, json
p = sys.stdin.read()
v = "duplicate" if "COPY" in p else "distinct-purpose"
print(json.dumps({"structured_output": {"verdict": v, "confidence": 0.8, "reason": "stub"}, "total_cost_usd": 0.001}))
"""


class TestGolden(unittest.TestCase):
    def test_validate_golden(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = _mini_vault(tmp)
            w("Resources/Reference/A.md", "a")
            w("Resources/Reference/B.md", "b")
            g = {"meta": {}, "pairs": [
                {"relA": "Resources/Reference/A.md", "relB": "Resources/Reference/B.md", "expected": "duplicate"},
                {"relA": "Resources/Reference/A.md", "relB": "nope.md", "expected": "duplicate"},
                {"relA": "Resources/Reference/A.md", "relB": "Resources/Reference/B.md", "expected": "same"}]}
            errs = ve.validate_golden(g, tmp)
            self.assertEqual(len(errs), 2)
            self.assertTrue(any("missing_file" in e for e in errs))
            self.assertTrue(any("bad_expected" in e for e in errs))


class TestCalibration(unittest.TestCase):
    def test_prompt_and_parse(self):
        p = ve.build_prompt("A.md", "alpha", "B.md", "beta")
        self.assertIn("A.md", p)
        self.assertIn("beta", p)
        self.assertEqual(ve.parse_claude_output(
            '{"structured_output": {"verdict": "duplicate", "confidence": 0.5, "reason": "r"}}')["verdict"], "duplicate")
        self.assertEqual(ve.parse_claude_output(
            '{"result": "{\\"verdict\\": \\"version-fork\\", \\"confidence\\": 0.6, \\"reason\\": \\"r\\"}"}')["verdict"], "version-fork")
        self.assertEqual(ve.parse_claude_output(
            '{"result": "```json\\n{\\"verdict\\": \\"duplicate\\", \\"confidence\\": 0.6, \\"reason\\": \\"r\\"}\\n```"}')["verdict"], "duplicate")
        self.assertIsNone(ve.parse_claude_output("not json"))
        self.assertIsNone(ve.parse_claude_output('{"result": "{\\"verdict\\": \\"same\\"}"}'))

    def test_score(self):
        r = [{"expected": "distinct-purpose", "predicted": "distinct-purpose"},
             {"expected": "distinct-purpose", "predicted": "duplicate"},
             {"expected": "version-fork", "predicted": "duplicate"},
             {"expected": "version-fork", "predicted": "distinct-purpose"},
             {"expected": "duplicate", "predicted": None}]
        m = ve.score_calibration(r)
        self.assertEqual(m["n"], 5)
        self.assertEqual(m["exact_accuracy"], 0.2)
        self.assertEqual(m["class_accuracy"], 0.4)
        self.assertEqual(m["false_supersede_rate"], 0.5)
        self.assertAlmostEqual(m["fork_recall"], 1 / 3, places=2)
        self.assertEqual(m["errors"], 1)

    def test_calibrate_and_sweep_with_stub(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = _mini_vault(tmp)
            stub = os.path.join(tmp, "stub.py")
            with open(stub, "w") as f:
                f.write(STUB)
            os.chmod(stub, 0o755)
            w("Resources/Reference/A.md", "---\ntype: reference\n---\nalpha COPY")
            w("Resources/Reference/B.md", "---\ntype: reference\n---\nalpha COPY")
            w("Resources/Reference/C.md", "---\ntype: reference\n---\ngamma")
            w("Resources/Reference/D.md", "---\ntype: reference\n---\ndelta")
            with open(os.path.join(tmp, ve.GOLDEN_PATH), "w") as f:
                json.dump({"meta": {}, "pairs": [
                    {"relA": "Resources/Reference/A.md", "relB": "Resources/Reference/B.md", "expected": "duplicate"},
                    {"relA": "Resources/Reference/C.md", "relB": "Resources/Reference/D.md", "expected": "version-fork"}]}, f)
            rep = ve.run_calibrate(tmp, "stub-model", limit=0, parallel=2, claude_cmd=stub,
                                   dry_run=False, max_chars=100)
            self.assertEqual(rep["metrics"]["n"], 2)
            self.assertEqual(rep["metrics"]["class_accuracy"], 0.5)
            self.assertTrue(os.path.exists(os.path.join(tmp, ve.HYGIENE_DIR, "calibration-log.md")))
            self.assertTrue(os.path.exists(os.path.join(tmp, rep["out"])))
            dry = ve.run_calibrate(tmp, "stub-model", limit=1, parallel=1, claude_cmd=stub,
                                   dry_run=True, max_chars=100)
            self.assertEqual(dry["metrics"]["n"], 0)
            self.assertEqual(dry["dry_run"], 1)

            pid = ve.pair_id("Resources/Reference/A.md", "cA", "Resources/Reference/B.md", "cB")
            with open(os.path.join(tmp, ve.HYGIENE_DIR, "canonical-candidates.json"), "w") as f:
                json.dump({"meta": {"count": 1}, "candidates": [{
                    "pair_id": pid, "relA": "Resources/Reference/A.md", "relB": "Resources/Reference/B.md",
                    "hashA": "cA", "hashB": "cB", "cosine": 0.95, "source": "gate"}]}, f)
            ve.va.save_index(tmp, {"meta": {}, "files": {
                "Resources/Reference/A.md": {"hash": "cA"}, "Resources/Reference/B.md": {"hash": "cB"}},
                "watched_clusters": []})
            res = ve.run_sweep(tmp, "stub-model", limit=0, parallel=1, claude_cmd=stub, max_chars=100)
            self.assertEqual(res["accepted"], [pid])
            self.assertEqual(res["errors"], [])
            j = ve.va.load_index(tmp)["canonical_judgments"][pid]
            self.assertEqual(j["judge_model"], "stub-model")
            self.assertEqual(j["verdict"], "duplicate")
            res = ve.run_sweep(tmp, "stub-model", limit=0, parallel=1, claude_cmd=stub, max_chars=100)
            self.assertEqual(res["accepted"], [])
            self.assertEqual(res["invoked"], 0)


if __name__ == "__main__":
    unittest.main()


class TestApplyHelpers(unittest.TestCase):
    def test_set_fm_keys_replaces_and_inserts(self):
        t = "---\ntype: note\nstatus: draft\ncreated: 2026-01-01\n---\nbody\n"
        out = ve.set_fm_keys(t, {"status": "superseded", "canonical": "true"})
        self.assertIn("status: superseded\n", out)
        self.assertNotIn("status: draft", out)
        self.assertIn("canonical: true\n", out)
        self.assertTrue(out.endswith("---\nbody\n"))
        self.assertEqual(out.count("---\n"), 2)

    def test_set_fm_keys_creates_block_when_missing(self):
        out = ve.set_fm_keys("just body\n", {"status": "superseded"})
        self.assertTrue(out.startswith("---\nstatus: superseded\n---\njust body\n"))

    def test_set_fm_keys_quotes_wikilink_values(self):
        out = ve.set_fm_keys("---\ntype: note\n---\nb", {"superseded_by": "[[A/B]]"})
        self.assertIn('superseded_by: "[[A/B]]"\n', out)

    def test_set_fm_keys_is_idempotent(self):
        t = "---\ntype: note\n---\nb\n"
        once = ve.set_fm_keys(t, {"canonical": "true"})
        self.assertEqual(once, ve.set_fm_keys(once, {"canonical": "true"}))

    def test_unique_lines_ignores_frontmatter_short_and_matched(self):
        winner = "---\ntype: a\n---\n# Title\n\nThe quick brown fox jumps over.\nShared fact line here.\n"
        loser = "---\ntype: b\n---\n# Title\n\nShared   fact line HERE.\nOnly in loser, a real fact.\nok\n"
        self.assertEqual(ve.unique_lines(loser, winner), ["Only in loser, a real fact."])

    def test_unique_lines_empty_for_subset(self):
        self.assertEqual(ve.unique_lines("---\nx: 1\n---\nsame long line of text\n",
                                         "same long line of text\nmore\n"), [])

    def test_fold_section_format(self):
        s = ve.fold_section("Notes/_Originals/Cooking Notes.md", "- fact one\n- fact two", "2026-09-18")
        self.assertEqual(s, "\n\n## Folded from Cooking Notes (2026-09-18)\n\n- fact one\n- fact two\n")

    def test_doc_stem(self):
        self.assertEqual(ve.doc_stem("A/B/C.md"), "A/B/C")

    def test_repoint_text_all_forms_keep_alias_and_heading(self):
        t = ("see [[Proposal]] and [[Acme/Proposal|alias]] and "
             "[[Work/Clients/Acme/Proposal#Sec]] not [[Proposals]]")
        out, n = ve.repoint_text(t, "Work/Clients/Acme/Proposal.md",
                                 "Work/Clients/Acme/Final.md")
        self.assertEqual(n, 3)
        self.assertIn("[[Final]]", out)
        self.assertIn("[[Work/Clients/Acme/Final|alias]]", out)
        self.assertIn("[[Work/Clients/Acme/Final#Sec]]", out)
        self.assertIn("[[Proposals]]", out)

    def test_repoint_links_writes_only_linking_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = _mini_vault(tmp)
            w("Projects/L.md", "---\ntype: note\n---\nold")
            w("Projects/W.md", "---\ntype: note\n---\nwin")
            w("Projects/X.md", "---\ntype: note\n---\nlink [[L]] here")
            w("Projects/Y.md", "---\ntype: note\n---\nno link")
            files = ["Projects/L.md", "Projects/W.md", "Projects/X.md", "Projects/Y.md"]
            changed = ve.repoint_links(tmp, files, "Projects/L.md", "Projects/W.md")
            self.assertEqual(changed, ["Projects/X.md"])
            with open(os.path.join(tmp, "Projects/X.md")) as f:
                self.assertIn("[[W]]", f.read())
            dry = ve.repoint_links(tmp, ["Projects/X.md"], "Projects/W.md", "Projects/L.md", write=False)
            self.assertEqual(dry, ["Projects/X.md"])
            with open(os.path.join(tmp, "Projects/X.md")) as f:
                self.assertIn("[[W]]", f.read())


def _apply_vault(tmp):
    """Three proposed judgments: pid1 a real fork with a linking third file,
    pid2 a pair with a no_merge record on the loser side, pid3 a fork whose
    loser is the linking file."""
    w = _mini_vault(tmp)
    w("Projects/SOPs/B.md", "---\ntype: sop\ncreated: 2026-01-01\n---\n# B\n\nShared fact line one here.\n")
    w("Projects/A.md", "---\ntype: note\ncreated: 2026-01-01\n---\n# A\n\nShared fact line one here.\nUnique fact only in A doc.\n")
    w("Projects/C.md", "---\ntype: note\n---\nlinks to [[A]]")
    w("Work/Transcripts/T.md", "---\ntype: transcript\n---\nrecord text that is long enough\n")
    w("Work/Clients/X/Company Profile.md", "---\ntype: client-profile\n---\nprofile\n")
    def h(rel):
        return ve.va.sha256_file(os.path.join(tmp, rel))
    hA, hB, hC = h("Projects/A.md"), h("Projects/SOPs/B.md"), h("Projects/C.md")
    hP, hT = h("Work/Clients/X/Company Profile.md"), h("Work/Transcripts/T.md")
    pid1, pid2, pid3 = "1" * 64, "2" * 64, "3" * 64
    js = {pid1: {"relA": "Projects/A.md", "relB": "Projects/SOPs/B.md", "verdict": "version-fork",
                 "confidence": 0.9, "reason": "B is the live SOP", "status": "proposed",
                 "winner": "Projects/SOPs/B.md", "loser": "Projects/A.md", "winner_rule": "priority",
                 "hashA": hA, "hashB": hB, "judge_model": "m", "decided_at": "2026-09-18"},
          pid2: {"relA": "Work/Clients/X/Company Profile.md", "relB": "Work/Transcripts/T.md",
                 "verdict": "duplicate", "confidence": 0.8, "reason": "r", "status": "proposed",
                 "winner": "Work/Clients/X/Company Profile.md", "loser": "Work/Transcripts/T.md",
                 "winner_rule": "priority", "hashA": hP, "hashB": hT},
          pid3: {"relA": "Projects/A.md", "relB": "Projects/C.md", "verdict": "version-fork",
                 "confidence": 0.7, "reason": "r3", "status": "proposed", "winner": "Projects/A.md",
                 "loser": "Projects/C.md", "winner_rule": "recency", "hashA": hA, "hashB": hC,
                 "judge_model": "m", "decided_at": "2026-09-18"}}
    index = {"meta": {}, "files": {}, "watched_clusters": [], "canonical_judgments": js}
    ve.va.save_index(tmp, index)
    return w, index, pid1, pid2, pid3


def _files(tmp):
    schema = ve.va.load_schema(tmp)
    return schema, ve.va.walk_vault(tmp, schema.get("protected", []))


class TestApplyPlan(unittest.TestCase):
    def test_confirm_without_fold_is_refused_when_unique_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            w, index, pid1, pid2, pid3 = _apply_vault(tmp)
            schema, files = _files(tmp)
            acts = ve.plan_apply(tmp, schema, index, {pid1: "confirm"}, {}, files, "2026-09-18")
            self.assertEqual(acts[0]["effective"], "skip")
            self.assertEqual(acts[0]["skip_reason"], "fold_missing")
            self.assertEqual(acts[0]["unique"], ["Unique fact only in A doc."])

    def test_confirm_with_fold_plans_stamp_fold_links_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            w, index, pid1, pid2, pid3 = _apply_vault(tmp)
            schema, files = _files(tmp)
            acts = ve.plan_apply(tmp, schema, index, {pid1: "confirm"},
                                 {pid1: "- Unique fact only in A doc."}, files, "2026-09-18")
            a = acts[0]
            self.assertEqual(a["effective"], "folded")
            self.assertIn("canonical: true", a["winner_new"])
            self.assertIn("status: active", a["winner_new"])
            self.assertTrue(a["winner_new"].endswith(
                "## Folded from A (2026-09-18)\n\n- Unique fact only in A doc.\n"))
            self.assertIn("status: superseded", a["loser_new"])
            self.assertIn('superseded_by: "[[Projects/SOPs/B]]"', a["loser_new"])
            self.assertIn("superseded_at: 2026-09-18", a["loser_new"])
            self.assertIn('superseded_reason: "B is the live SOP"', a["loser_new"])
            self.assertEqual(a["links"], ["Projects/C.md"])
            self.assertTrue(a["stage_dest"].endswith("audit-trash/2026-09-18/Projects/A.md"))
            text = ve.render_plan(acts)
            self.assertIn("+canonical: true", text)
            self.assertIn("repoint links in: Projects/C.md", text)

    def test_swap_reverses_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            w, index, pid1, pid2, pid3 = _apply_vault(tmp)
            schema, files = _files(tmp)
            acts = ve.plan_apply(tmp, schema, index, {pid1: "swap"}, {pid1: ""}, files, "2026-09-18")
            self.assertEqual(acts[0]["winner"], "Projects/A.md")
            self.assertEqual(acts[0]["loser"], "Projects/SOPs/B.md")
            self.assertEqual(acts[0]["effective"], "folded")
            self.assertTrue(acts[0]["fold_declared_subset"])
            self.assertNotIn("## Folded from", acts[0]["winner_new"])

    def test_no_merge_side_downgrades_to_keep(self):
        with tempfile.TemporaryDirectory() as tmp:
            w, index, pid1, pid2, pid3 = _apply_vault(tmp)
            schema, files = _files(tmp)
            acts = ve.plan_apply(tmp, schema, index, {pid2: "confirm"}, {}, files, "2026-09-18")
            self.assertEqual(acts[0]["effective"], "kept")
            self.assertEqual(acts[0]["downgraded_reason"], "no_merge:Work/Transcripts/T.md")
            self.assertIsNone(acts[0]["stage_dest"])
            self.assertEqual(acts[0]["links"], [])
            self.assertIn("DOWNGRADED", ve.render_plan(acts))

    def test_reject_pending_and_confirmed_locked(self):
        with tempfile.TemporaryDirectory() as tmp:
            w, index, pid1, pid2, pid3 = _apply_vault(tmp)
            index["canonical_judgments"][pid3]["status"] = "confirmed"
            schema, files = _files(tmp)
            acts = ve.plan_apply(tmp, schema, index, {pid1: "reject", pid2: "pending", pid3: "confirm"},
                                 {}, files, "2026-09-18")
            self.assertEqual([a["effective"] for a in acts], ["rejected"])
            self.assertIsNone(acts[0]["winner_new"])
            self.assertIn("reject", ve.render_plan(acts))

    def test_missing_doc_withdraws(self):
        with tempfile.TemporaryDirectory() as tmp:
            w, index, pid1, pid2, pid3 = _apply_vault(tmp)
            os.remove(os.path.join(tmp, "Projects/A.md"))
            schema, files = _files(tmp)
            acts = ve.plan_apply(tmp, schema, index, {pid1: "confirm-keep"}, {}, files, "2026-09-18")
            self.assertEqual(acts[0]["effective"], "withdrawn")
            self.assertEqual(acts[0]["skip_reason"], "missing:Projects/A.md")
            self.assertIn("WITHDRAWN: missing:Projects/A.md", ve.render_plan(acts))

    def test_withdrawn_end_to_end_reopens_on_reappearance(self):
        with tempfile.TemporaryDirectory() as tmp:
            w, index, pid1, pid2, pid3 = _apply_vault(tmp)
            ve.write_review_queue(tmp, index["canonical_judgments"], "2026-09-18")
            qp = os.path.join(tmp, ve.REVIEW_PATH)
            _set_decisions(qp, {pid1: "confirm"})
            os.remove(os.path.join(tmp, "Projects/A.md"))
            res = ve.run_apply(tmp, None, only=pid1[:12], today="2026-09-18")
            self.assertEqual(res["receipt"]["withdrawn"], ["Projects/SOPs/B.md > Projects/A.md: missing:Projects/A.md"])
            self.assertEqual(res["receipt"]["applied"], 1)
            js = ve.va.load_index(tmp)["canonical_judgments"]
            self.assertEqual(js[pid1]["status"], "withdrawn")
            self.assertFalse(ve.already_judged(pid1, js))
            self.assertTrue(ve.already_judged(pid2, js))
            with open(qp) as f:
                self.assertNotIn(pid1, f.read())
            with open(os.path.join(tmp, "_generated/vault-hygiene/audit-log.md")) as f:
                self.assertIn("withdrawn 1", f.read())


def _hashes(tmp):
    out = {}
    for root, _, fs in os.walk(tmp):
        for f in fs:
            p = os.path.join(root, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, tmp)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def _set_decisions(qp, mapping):
    with open(qp) as f:
        blocks = f.read().split("### ")
    new = []
    for b in blocks:
        for pid, dec in mapping.items():
            if ("pair_id: %s\n" % pid) in b:
                b = b.replace("decision: pending", "decision: " + dec)
        new.append(b)
    with open(qp, "w") as f:
        f.write("### ".join(new))


class TestApplyExecute(unittest.TestCase):
    def test_end_to_end_non_mutation_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            w, index, pid1, pid2, pid3 = _apply_vault(tmp)
            ve.write_review_queue(tmp, index["canonical_judgments"], "2026-09-18")
            qp = os.path.join(tmp, ve.REVIEW_PATH)
            _set_decisions(qp, {pid1: "confirm", pid2: "confirm", pid3: "reject"})
            folds = os.path.join(tmp, "folds.json")
            with open(folds, "w") as f:
                json.dump({pid1: "- Unique fact only in A doc."}, f)
            before = _hashes(tmp)
            dry = ve.run_apply(tmp, folds, dry_run=True, today="2026-09-18")
            self.assertEqual(_hashes(tmp), before)
            self.assertEqual(dry["receipt"]["applied"], 0)
            self.assertEqual(dry["actions"], 3)
            self.assertIn("## Folded from A", dry["plan"])
            res = ve.run_apply(tmp, folds, today="2026-09-18")
            r = res["receipt"]
            self.assertEqual(r["applied"], 3)
            self.assertEqual(r["folded"], ["Projects/SOPs/B.md <- Projects/A.md"])
            self.assertEqual(r["kept"], ["Work/Clients/X/Company Profile.md > Work/Transcripts/T.md"])
            self.assertEqual(r["rejected"], ["Projects/A.md | Projects/C.md"])
            self.assertEqual(r["downgraded"], ["Work/Transcripts/T.md: no_merge:Work/Transcripts/T.md"])
            self.assertEqual(r["links_repointed"], 1)
            self.assertEqual(r["invariant_violations"], [])
            self.assertEqual(r["proposals_open"], 0)
            after = _hashes(tmp)
            changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
            expected = {"Projects/SOPs/B.md", "Projects/A.md", "Projects/C.md",
                        "Work/Clients/X/Company Profile.md", "Work/Transcripts/T.md",
                        "_generated/vault-hygiene/audit-trash/2026-09-18/Projects/A.md",
                        "_generated/vault-hygiene/vault-index.json",
                        "_generated/vault-hygiene/pending-supersession-review.md",
                        "_generated/vault-hygiene/audit-log.md",
                        "_generated/vault-hygiene/golden-pairs.json",
                        "_generated/vault-hygiene/golden-fixtures/Projects/SOPs/B.md",
                        "_generated/vault-hygiene/golden-fixtures/Projects/A.md",
                        "_generated/vault-hygiene/golden-fixtures/Work/Clients/X/Company Profile.md",
                        "_generated/vault-hygiene/golden-fixtures/Work/Transcripts/T.md"}
            self.assertEqual(changed, expected)
            # Human decisions grow the golden set (canon section 5); fixtures hold the pre-apply text.
            self.assertEqual(r["golden_added"], 3)
            with open(os.path.join(tmp, ve.GOLDEN_PATH)) as f:
                golden = json.load(f)
            by = {(g["relA"], g["relB"]): g for g in golden["pairs"]}
            fold = by[("_generated/vault-hygiene/golden-fixtures/Projects/SOPs/B.md",
                       "_generated/vault-hygiene/golden-fixtures/Projects/A.md")]
            self.assertEqual(fold["expected"], "version-fork")
            self.assertEqual(fold["source"], "decision-surface")
            self.assertEqual(by[("Projects/A.md", "Projects/C.md")]["expected"], "distinct-purpose")
            self.assertNotIn("fixture", by[("Projects/A.md", "Projects/C.md")])
            with open(os.path.join(tmp, "_generated/vault-hygiene/golden-fixtures/Projects/SOPs/B.md")) as f:
                self.assertNotIn("## Folded from", f.read())
            self.assertFalse(os.path.exists(os.path.join(tmp, "Projects/A.md")))
            with open(os.path.join(tmp, "Projects/SOPs/B.md")) as f:
                b = f.read()
            self.assertIn("canonical: true", b)
            self.assertTrue(b.endswith("- Unique fact only in A doc.\n"))
            with open(os.path.join(tmp, "_generated/vault-hygiene/audit-trash/2026-09-18/Projects/A.md")) as f:
                self.assertIn('superseded_by: "[[Projects/SOPs/B]]"', f.read())
            with open(os.path.join(tmp, "Projects/C.md")) as f:
                self.assertIn("[[B]]", f.read())
            with open(os.path.join(tmp, "Work/Transcripts/T.md")) as f:
                t = f.read()
            self.assertIn("status: superseded", t)
            self.assertIn("record text that is long enough", t)
            js = ve.va.load_index(tmp)["canonical_judgments"]
            self.assertEqual(js[pid1]["status"], "confirmed")
            self.assertEqual(js[pid1]["outcome"], "folded")
            self.assertEqual(js[pid1]["links_repointed"], ["Projects/C.md"])
            self.assertEqual(js[pid1]["decided_by"], "human")
            self.assertEqual(js[pid2]["outcome"], "kept")
            self.assertEqual(js[pid2]["downgraded_reason"], "no_merge:Work/Transcripts/T.md")
            self.assertEqual(js[pid3]["status"], "rejected")
            self.assertEqual(js[pid3]["verdict"], "distinct-purpose")
            self.assertEqual(js[pid3]["superseded_verdict"]["verdict"], "version-fork")
            with open(qp) as f:
                self.assertEqual(ve.queue_counts(f.read())["total"], 0)
            with open(os.path.join(tmp, "_generated/vault-hygiene/audit-log.md")) as f:
                log = f.read()
            self.assertIn("## 2026-09-18 (apply)", log)
            self.assertIn("applied: 3 (folded 1, kept 1, rejected 1, withdrawn 0, stale 0)", log)
            again = ve.run_apply(tmp, folds, today="2026-09-18")
            self.assertEqual(again["receipt"]["applied"], 0)
            self.assertEqual(again["actions"], 0)
            self.assertEqual(_hashes(tmp), after)

    def test_only_filter_and_fold_missing_stays_in_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            w, index, pid1, pid2, pid3 = _apply_vault(tmp)
            ve.write_review_queue(tmp, index["canonical_judgments"], "2026-09-18")
            qp = os.path.join(tmp, ve.REVIEW_PATH)
            _set_decisions(qp, {pid1: "confirm", pid2: "confirm", pid3: "confirm"})
            before = _hashes(tmp)
            res = ve.run_apply(tmp, None, only=pid1[:12], today="2026-09-18")
            self.assertEqual(res["receipt"]["applied"], 0)
            self.assertEqual(res["receipt"]["skipped"], ["Projects/SOPs/B.md > Projects/A.md: fold_missing"])
            self.assertEqual(res["actions"], 1)
            with open(qp) as f:
                self.assertEqual(ve.queue_counts(f.read())["confirm"], 3)
            self.assertTrue(os.path.exists(os.path.join(tmp, "Projects/A.md")))
            after = _hashes(tmp)
            changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
            self.assertEqual(changed, {"_generated/vault-hygiene/pending-supersession-review.md"})

    def test_swap_end_to_end_keeps_invariant(self):
        with tempfile.TemporaryDirectory() as tmp:
            w, index, pid1, pid2, pid3 = _apply_vault(tmp)
            ve.write_review_queue(tmp, index["canonical_judgments"], "2026-09-18")
            qp = os.path.join(tmp, ve.REVIEW_PATH)
            _set_decisions(qp, {pid1: "swap"})
            folds = os.path.join(tmp, "folds.json")
            with open(folds, "w") as f:
                json.dump({pid1: ""}, f)
            res = ve.run_apply(tmp, folds, today="2026-09-18")
            self.assertEqual(res["receipt"]["folded"], ["Projects/A.md <- Projects/SOPs/B.md"])
            self.assertEqual(res["receipt"]["invariant_violations"], [])
            js = ve.va.load_index(tmp)["canonical_judgments"][pid1]
            self.assertEqual(js["winner"], "Projects/A.md")
            self.assertEqual(js["winner_rule"], "swap")
            self.assertTrue(js["fold_declared_subset"])


class TestApplyStaleGuard(unittest.TestCase):
    NEW_A = ("---\ntype: note\ncreated: 2026-01-01\n---\n# A\n\nShared fact line one here.\n"
             "Unique fact only in A doc.\nA brand new fact nobody reviewed.\n")

    def test_changed_doc_refuses_apply_and_closes_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            w, index, pid1, pid2, pid3 = _apply_vault(tmp)
            w("Projects/A.md", self.NEW_A)  # edited after the comparator judged it
            schema, files = _files(tmp)
            acts = ve.plan_apply(tmp, schema, index, {pid1: "confirm"},
                                 {pid1: "- Unique fact only in A doc."}, files, "2026-09-24")
            self.assertEqual(acts[0]["effective"], "stale")
            self.assertEqual(acts[0]["skip_reason"], "stale:Projects/A.md")
            self.assertIsNone(acts[0]["winner_new"])
            self.assertIn("STALE: stale:Projects/A.md", ve.render_plan(acts))
            # dry run reports it without touching anything
            ve.write_review_queue(tmp, index["canonical_judgments"], "2026-09-24")
            qp = os.path.join(tmp, ve.REVIEW_PATH)
            _set_decisions(qp, {pid1: "confirm"})
            dry = ve.run_apply(tmp, None, dry_run=True, only=pid1[:12], today="2026-09-24")
            self.assertEqual(dry["receipt"]["stale"], ["Projects/SOPs/B.md > Projects/A.md: stale:Projects/A.md"])
            # real run: docs untouched, judgment closed as stale, block leaves the queue
            before = _hashes(tmp)
            res = ve.run_apply(tmp, None, only=pid1[:12], today="2026-09-24")
            after = _hashes(tmp)
            self.assertEqual(res["receipt"]["applied"], 0)
            self.assertEqual(res["receipt"]["stale"], ["Projects/SOPs/B.md > Projects/A.md: stale:Projects/A.md"])
            self.assertEqual(after["Projects/A.md"], before["Projects/A.md"])
            self.assertEqual(after["Projects/SOPs/B.md"], before["Projects/SOPs/B.md"])
            self.assertFalse(os.path.isdir(os.path.join(tmp, ve.HYGIENE_DIR, "audit-trash")))
            js = ve.va.load_index(tmp)["canonical_judgments"]
            self.assertEqual(js[pid1]["status"], "stale")
            self.assertEqual(js[pid1]["stale_reason"], "stale:Projects/A.md")
            self.assertEqual(js[pid1]["decision"], "confirm")
            self.assertFalse(ve.already_judged(pid1, js))
            with open(qp) as f:
                self.assertNotIn(pid1, f.read())
            with open(os.path.join(tmp, "_generated/vault-hygiene/audit-log.md")) as f:
                log = f.read()
            self.assertIn("stale 1", log)
            self.assertIn("stale: Projects/SOPs/B.md > Projects/A.md: stale:Projects/A.md", log)

    def test_missing_hash_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            w, index, pid1, pid2, pid3 = _apply_vault(tmp)
            del index["canonical_judgments"][pid1]["hashB"]
            schema, files = _files(tmp)
            acts = ve.plan_apply(tmp, schema, index, {pid1: "confirm-keep"}, {}, files, "2026-09-24")
            self.assertEqual(acts[0]["effective"], "stale")
            self.assertEqual(acts[0]["skip_reason"], "stale:Projects/SOPs/B.md")

    def test_reject_ignores_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            w, index, pid1, pid2, pid3 = _apply_vault(tmp)
            w("Projects/A.md", self.NEW_A)
            schema, files = _files(tmp)
            acts = ve.plan_apply(tmp, schema, index, {pid1: "reject"}, {}, files, "2026-09-24")
            self.assertEqual(acts[0]["effective"], "rejected")

    def test_batch_revalidates_later_proposal_after_earlier_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            w, index, pid1, pid2, pid3 = _apply_vault(tmp)
            ve.write_review_queue(tmp, index["canonical_judgments"], "2026-09-24")
            qp = os.path.join(tmp, ve.REVIEW_PATH)
            # pid1 folds A into B: C's link to A is repointed and A is staged. pid3 (winner A,
            # loser C) was planned against the pre-pid1 texts, so it must not be written.
            _set_decisions(qp, {pid1: "confirm", pid3: "confirm-keep"})
            folds = os.path.join(tmp, "folds.json")
            with open(folds, "w") as f:
                json.dump({pid1: "- Unique fact only in A doc."}, f)
            res = ve.run_apply(tmp, folds, today="2026-09-24")
            self.assertEqual(res["receipt"]["folded"], ["Projects/SOPs/B.md <- Projects/A.md"])
            self.assertEqual(res["receipt"]["kept"], [])
            self.assertEqual(res["receipt"]["stale"],
                             ["Projects/A.md > Projects/C.md: changed_during_batch:Projects/A.md"])
            self.assertFalse(os.path.exists(os.path.join(tmp, "Projects/A.md")))  # never resurrected
            js = ve.va.load_index(tmp)["canonical_judgments"]
            self.assertEqual(js[pid1]["status"], "confirmed")
            self.assertEqual(js[pid3]["status"], "stale")
            with open(os.path.join(tmp, "Projects/C.md")) as f:
                self.assertNotIn("[[A]]", f.read())  # pid1's repoint survived, pid3 wrote nothing
            self.assertEqual(res["receipt"]["invariant_violations"], [])

    def test_stale_pair_is_rejudged_not_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            w, index, pid1, pid2, pid3 = _apply_vault(tmp)
            index["canonical_judgments"][pid1]["status"] = "stale"
            index["canonical_judgments"][pid1]["stale_reason"] = "stale:Projects/A.md"
            cands = {pid1: {"relA": "Projects/A.md", "relB": "Projects/SOPs/B.md",
                            "hashA": index["canonical_judgments"][pid1]["hashA"],
                            "hashB": index["canonical_judgments"][pid1]["hashB"], "source": "gate"}}
            res = ve.apply_verdicts(index["canonical_judgments"], cands,
                                    [{"pair_id": pid1, "verdict": "duplicate", "confidence": 0.8, "reason": "same doc"}],
                                    "m2", "2026-09-25")
            self.assertEqual(res["accepted"], [pid1])
            self.assertEqual(res["replayed"], [])
            j = index["canonical_judgments"][pid1]
            self.assertEqual(j["status"], "proposed")
            self.assertEqual(j["verdict"], "duplicate")
            self.assertNotIn("stale_reason", j)

    def test_apply_cli_accepts_today(self):
        import subprocess, sys
        with tempfile.TemporaryDirectory() as tmp:
            _apply_vault(tmp)
            p = subprocess.run([sys.executable, SCRIPT, "apply", "--vault", tmp, "--dry-run", "--today", "2026-01-02"],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)


class TestSelfInstall(unittest.TestCase):
    def test_no_auto_install_returns_false_without_running(self):
        calls = []
        ok = ve.ensure_fastembed(auto_install=False, runner=lambda cmd: calls.append(cmd) or 0, log=lambda s: None)
        self.assertFalse(ok)
        self.assertEqual(calls, [])

    def test_auto_install_runs_once_and_survives_failure(self):
        calls, logs = [], []
        ok = ve.ensure_fastembed(auto_install=True, runner=lambda cmd: calls.append(cmd) or 1, log=logs.append)
        self.assertFalse(ok)
        self.assertEqual(len(calls), 1)
        self.assertIn("fastembed", calls[0])
        self.assertTrue(any("install failed" in l for l in logs))

    def test_runner_exception_is_logged_not_raised(self):
        def boom(cmd):
            raise OSError("no pip")
        logs = []
        self.assertFalse(ve.ensure_fastembed(auto_install=True, runner=boom, log=logs.append))
        self.assertIn("no pip", logs[0])

    def test_skipped_report_keeps_prior_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = _mini_vault(tmp)
            w("Resources/Reference/A.md", "---\ntype: reference\ncreated: 2026-01-01\n---\nbody A")
            ve.va.save_index(tmp, {"meta": {}, "files": {"Resources/Reference/A.md": {"hash": "h", "concept": "", "entities": []}},
                                   "watched_clusters": [], "canonical_judgments": {}})
            prior = [{"pair_id": "p", "relA": "Resources/Reference/A.md", "relB": "Resources/Reference/B.md",
                      "hashA": "h", "hashB": "h2", "cosine": 0.95, "shared_entity": False, "source": "gate"}]
            ve.write_candidates_json(tmp, prior)
            args = type("A", (), {"vault": tmp, "owner": "Owner", "high": 0.86, "fallback": 0.90, "install": False})()
            ve.cmd_report(args)
            self.assertEqual(ve.load_candidates(tmp)["candidates"], prior)
            with open(os.path.join(tmp, ve.HYGIENE_DIR, "embed-candidate-report.md")) as f:
                self.assertIn("left untouched", f.read())


class TestStickyRejects(unittest.TestCase):
    def test_human_reject_survives_hash_change(self):
        docs = [{"rel": "A.md", "entities": ["X"], "hash": "a2", "embed_hash": "a2"},
                {"rel": "B.md", "entities": ["X"], "hash": "b1", "embed_hash": "b1"},
                {"rel": "C.md", "entities": ["X"], "hash": "c1", "embed_hash": "c1"}]
        vecs = {"A.md": [1.0, 0.0], "B.md": [1.0, 0.0], "C.md": [1.0, 0.0]}
        old_pid = ve.pair_id("A.md", "a1", "B.md", "b1")
        judgments = {old_pid: {"relA": "A.md", "relB": "B.md", "hashA": "a1", "hashB": "b1",
                               "status": "rejected", "decided_by": "human", "verdict": "distinct-purpose"}}
        out = ve.generate_candidates(docs, vecs, set(), judgments, ("owner",))
        pairs = {(c["relA"], c["relB"]) for c in out}
        self.assertNotIn(("A.md", "B.md"), pairs)
        self.assertIn(("A.md", "C.md"), pairs)
        self.assertIn(("B.md", "C.md"), pairs)
        # a comparator reject (not human) is hash-gated and does come back
        judgments[old_pid]["decided_by"] = "comparator"
        out = ve.generate_candidates(docs, vecs, set(), judgments, ("owner",))
        self.assertIn(("A.md", "B.md"), {(c["relA"], c["relB"]) for c in out})


class TestEmbedConfig(unittest.TestCase):
    def test_defaults_when_no_block(self):
        cfg = ve.load_embed_config({"folders": []})
        self.assertEqual(cfg["owners"], ())
        self.assertEqual(cfg["gate_high"], 0.86)
        self.assertEqual(cfg["gate_fallback"], 0.90)
        self.assertEqual(cfg["stale_days"], 180)
        self.assertEqual(cfg["canonical_home_dirs"], ve.CANONICAL_HOME_DIRS)

    def test_reads_block_and_casts(self):
        schema = {"embedding": {"owners": ["Acme Corp", "Owner"], "gate_high": "0.8",
                                "gate_fallback": 0.92, "stale_days": "90",
                                "canonical_home_dirs": ["Resources/Reference", "Resources/SOPs"]}}
        cfg = ve.load_embed_config(schema)
        self.assertEqual(cfg["owners"], ("acme corp", "owner"))
        self.assertEqual(cfg["gate_high"], 0.8)
        self.assertEqual(cfg["gate_fallback"], 0.92)
        self.assertEqual(cfg["stale_days"], 90)
        self.assertEqual(cfg["canonical_home_dirs"], ("Resources/Reference", "Resources/SOPs"))

    def test_string_owner_coerced_to_list(self):
        self.assertEqual(ve.load_embed_config({"embedding": {"owners": "Acme"}})["owners"], ("acme",))

    def test_bad_numbers_fall_back(self):
        cfg = ve.load_embed_config({"embedding": {"gate_high": "nope", "stale_days": None}})
        self.assertEqual(cfg["gate_high"], 0.86)
        self.assertEqual(cfg["stale_days"], 180)


class TestMigrate(unittest.TestCase):
    def test_rename_folder_rekeys_all_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            _mini_vault(tmp)
            old_a, old_b = "Work/Clients/Old Name/A.md", "Work/Clients/Old Name/B.md"
            pid = ve.pair_id(old_a, "ha", old_b, "hb")
            ve.va.save_index(tmp, {"meta": {}, "files": {
                old_a: {"hash": "ha", "concept": "", "entities": []},
                old_b: {"hash": "hb", "concept": "", "entities": []},
                "Resources/Reference/Keep.md": {"hash": "hk"}},
                "watched_clusters": [[old_a, old_b]],
                "canonical_judgments": {pid: {"relA": old_a, "relB": old_b,
                    "hashA": "ha", "hashB": "hb", "verdict": "version-fork",
                    "winner": old_b, "loser": old_a, "status": "proposed",
                    "winner_rule": "recency", "confidence": 0.8, "reason": "r"}}})
            ve.save_vectors(tmp, {"meta": {}, "files": {
                old_a: {"embed_hash": "e1", "vector": [0.1]},
                "Resources/Reference/Keep.md": {"embed_hash": "e2", "vector": [0.2]}}})
            with open(os.path.join(tmp, ve.GOLDEN_PATH), "w") as f:
                json.dump({"meta": {}, "pairs": [
                    {"relA": old_a, "relB": old_b, "expected": "version-fork"},
                    {"relA": "Resources/Reference/Keep.md", "relB": "Resources/Reference/Other.md",
                     "expected": "distinct-purpose"}]}, f)

            res = ve.run_migrate(tmp, "Work/Clients/Old Name", "Work/Clients/New Name", today="2026-10-06")
            # golden counts path fields remapped (both sides of the first pair matched).
            self.assertEqual(res["changed"],
                             {"index_files": 2, "watched_clusters": 1, "judgments": 1,
                              "vectors": 1, "golden": 2})

            idx = ve.va.load_index(tmp)
            new_a, new_b = "Work/Clients/New Name/A.md", "Work/Clients/New Name/B.md"
            self.assertIn(new_a, idx["files"])
            self.assertNotIn(old_a, idx["files"])
            self.assertIn("Resources/Reference/Keep.md", idx["files"])
            self.assertEqual(idx["watched_clusters"], [[new_a, new_b]])
            new_pid = ve.pair_id(new_a, "ha", new_b, "hb")
            self.assertIn(new_pid, idx["canonical_judgments"])
            self.assertNotIn(pid, idx["canonical_judgments"])
            j = idx["canonical_judgments"][new_pid]
            self.assertEqual(j["renamed_from_pair_id"], pid)
            self.assertEqual(j["relA"], new_a)
            self.assertEqual(j["winner"], new_b)
            self.assertEqual(j["loser"], new_a)
            vecs = ve.load_vectors(tmp)
            self.assertIn(new_a, vecs["files"])
            self.assertNotIn(old_a, vecs["files"])
            self.assertIn("Resources/Reference/Keep.md", vecs["files"])
            with open(os.path.join(tmp, ve.GOLDEN_PATH)) as f:
                golden = json.load(f)
            paths = {(p["relA"], p["relB"]) for p in golden["pairs"]}
            self.assertIn((new_a, new_b), paths)
            self.assertIn(("Resources/Reference/Keep.md", "Resources/Reference/Other.md"), paths)

    def test_rename_single_file_dry_run_then_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            _mini_vault(tmp)
            ve.va.save_index(tmp, {"meta": {}, "files": {
                "Notes/Old.md": {"hash": "h"}, "Notes/Keep.md": {"hash": "h2"}},
                "watched_clusters": []})
            res = ve.run_migrate(tmp, "Notes/Old.md", "Notes/New.md", dry_run=True)
            self.assertEqual(res["changed"]["index_files"], 1)
            self.assertTrue(res["dry_run"])
            self.assertIn("Notes/Old.md", ve.va.load_index(tmp)["files"])  # nothing written
            ve.run_migrate(tmp, "Notes/Old.md", "Notes/New.md")
            idx = ve.va.load_index(tmp)
            self.assertIn("Notes/New.md", idx["files"])
            self.assertNotIn("Notes/Old.md", idx["files"])
            self.assertIn("Notes/Keep.md", idx["files"])

    def test_remap_path(self):
        self.assertEqual(ve.remap_path("A/B.md", "A", "Z"), "Z/B.md")
        self.assertEqual(ve.remap_path("A.md", "A.md", "Z.md"), "Z.md")
        self.assertEqual(ve.remap_path("Archived/A.md", "A", "Z"), "Archived/A.md")
        self.assertEqual(ve.remap_path("Other/x.md", "A", "Z"), "Other/x.md")
