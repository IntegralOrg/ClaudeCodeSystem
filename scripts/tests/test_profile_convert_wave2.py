import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
LEGACY = "---\ntype: client-profile\n---\n# P\n\n## Recent Activity\n- **2026-10-02** — Did a thing happen here.\n"


def test_trash_root_defaults_to_repo_root_not_cwd(tmp_path):
    repo = tmp_path / "repo"
    (repo / "Work/Clients/A").mkdir(parents=True)
    (repo / "CLAUDE.md").write_text("# r\n")
    f = repo / "Work/Clients/A/Company Profile.md"
    f.write_text(LEGACY)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    r = subprocess.run([sys.executable, str(SCRIPTS / "profile-convert.py"), str(f), "--engagement", "paused", "--apply"],
                       capture_output=True, text=True, cwd=elsewhere)
    assert r.returncode == 0, r.stderr
    assert (repo / "_generated/vault-hygiene/audit-trash").is_dir()
    assert not (elsewhere / "_generated").exists()
    assert "engagement: paused" in f.read_text()


def test_paused_group_in_graph_render():
    import importlib
    sys.path.insert(0, str(SCRIPTS))
    gr = importlib.import_module("graph-render")
    if not hasattr(gr, "ENGAGEMENT_ORDER"):
        import pytest
        pytest.skip("this graph-render has no engagement grouping")
    assert gr.ENGAGEMENT_ORDER["paused"] == "Paused"
    keys = list(gr.ENGAGEMENT_ORDER)
    assert keys.index("paused") == keys.index("maintenance") + 1
