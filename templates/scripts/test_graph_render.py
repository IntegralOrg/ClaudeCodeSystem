#!/usr/bin/env python3
"""Tiny self-contained test for graph-render.py.

Builds a throwaway vault in a temp dir, runs the renderer twice, and checks:
  - Graph/index.md and at least one MOC are generated from frontmatter.
  - A private top-level folder (Personal/) never appears in Graph/.
  - A second run is idempotent (it reports "changed: none" and rewrites nothing).

Stdlib only. Run: python3 templates/scripts/test_graph_render.py
"""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER = os.path.join(HERE, "graph-render.py")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def doc(type_, body, **extra):
    fm = ["---", f"type: {type_}", "status: active", "created: 2026-01-01"]
    for k, v in extra.items():
        fm.append(f"{k}: {v}")
    fm.append("---")
    return "\n".join(fm) + "\n\n" + body + "\n"


def build_vault(root):
    os.makedirs(os.path.join(root, "Graph"))
    write(os.path.join(root, "Work", "Clients", "Acme", "Company Profile.md"),
          doc("client-profile", "Acme makes widgets for the enterprise market.", client="Acme"))
    write(os.path.join(root, "Resources", "Concepts", "Widget Pipeline.md"),
          doc("concept", "How widgets flow from intake to delivery.", summary="The widget pipeline"))
    write(os.path.join(root, "Resources", "People", "Jane Roe.md"),
          doc("person", "Primary contact at Acme.", org="Acme", role="operations-lead"))
    write(os.path.join(root, "SOPs", "Deploy Process.md"),
          doc("sop", "Step by step deploy runbook.", summary="Deploy process"))
    # Private: must never appear in Graph/.
    write(os.path.join(root, "Personal", "Private Journal.md"),
          doc("note", "A private note that should never be rendered into Graph."))


def run_render(root):
    p = subprocess.run([sys.executable, RENDER, "--vault", root],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(f"renderer failed: {p.stderr}\n{p.stdout}")
    return p.stdout.strip()


class GraphRenderTest(unittest.TestCase):
    def test_render(self):
        with tempfile.TemporaryDirectory() as root:
            build_vault(root)

            first = run_render(root)
            graph = os.path.join(root, "Graph")

            index_path = os.path.join(graph, "index.md")
            self.assertTrue(os.path.exists(index_path), "index.md was not generated")
            with open(index_path, encoding="utf-8") as fh:
                index = fh.read()
            self.assertIn("Acme", index)
            self.assertIn("Widget Pipeline", index)

            # At least one MOC generated.
            mocs = [f for f in ("Clients.md", "People.md", "Projects.md", "Concepts.md", "SOPs.md")
                    if os.path.exists(os.path.join(graph, f))]
            self.assertTrue(mocs, "no MOC files were generated")

            # Private folder never leaks into any Graph/ file.
            for f in ["index.md"] + mocs:
                with open(os.path.join(graph, f), encoding="utf-8") as fh:
                    text = fh.read()
                self.assertNotIn("Private Journal", text,
                                 f"private doc leaked into Graph/{f}")

            # Idempotent: a second run changes nothing.
            second = run_render(root)
            self.assertIn("changed: none", second,
                          f"second run was not idempotent: {second}")


if __name__ == "__main__":
    unittest.main()
