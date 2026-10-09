import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "template-diff.py"


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def write(root, files):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode())


def make_template(tmp_path):
    tpl = tmp_path / "tpl"
    tpl.mkdir()
    git(tpl, "init", "-q", "-b", "main")
    git(tpl, "config", "user.email", "t@example.com"); git(tpl, "config", "user.name", "t")
    v1 = {"a.md": "a1\nline\n", "b.md": "b1\n", "gone.md": "g1\n", "kept-gone.md": "k1\n", "CLAUDE.md": "skeleton 1\n",
          "SETUP_PENDING": "x\n", "same.md": "s\n", "System/routines/eod.md": "timezone: UTC\n"}
    write(tpl, v1)
    git(tpl, "add", "-A"); git(tpl, "commit", "-q", "-m", "v1")
    write(tpl, {"a.md": "a2\nline\n", "b.md": "b2\n", "CLAUDE.md": "skeleton 2\n", "new.md": "n\n",
                "System/routines/eod.md": "timezone: UTC\nkeys: []\n"})
    git(tpl, "rm", "-q", "gone.md", "kept-gone.md")
    git(tpl, "add", "-A"); git(tpl, "commit", "-q", "-m", "v2")
    return tpl, v1


def run(tpl, vault):
    out = subprocess.run([sys.executable, str(SCRIPT), "--template", str(tpl), "--vault", str(vault), "--json"],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def test_sorts_every_case(tmp_path):
    tpl, v1 = make_template(tmp_path)
    vault = tmp_path / "vault"
    write(vault, dict(v1))
    (vault / "SETUP_PENDING").unlink()  # setup deleted it
    write(vault, {"b.md": "b1\nmy addition\n", "kept-gone.md": "k1\nmine\n", "CLAUDE.md": "my vault\n",
                  "System/routines/eod.md": "timezone: America/New_York\n", "Work/mine.md": "private notes\n"})
    got = run(tpl, vault)
    assert got["take"] == ["a.md"]
    assert got["changed"] == ["b.md"]
    assert got["add"] == ["new.md"]
    assert got["retire"] == ["gone.md"]
    assert got["retire-changed"] == ["kept-gone.md"]
    assert sorted(got["owned"]) == ["CLAUDE.md", "System/routines/eod.md"]
    assert got["same"] == ["same.md"]
    listed = {p for paths in got.values() for p in paths}
    assert "SETUP_PENDING" not in listed  # never re-added: it would rerun setup
    assert "Work/mine.md" not in listed  # the owner's files are never listed


def test_windows_line_endings_count_as_unedited(tmp_path):
    tpl, v1 = make_template(tmp_path)
    vault = tmp_path / "vault"
    write(vault, {"a.md": v1["a.md"].replace("\n", "\r\n")})
    assert run(tpl, vault)["take"] == ["a.md"]


def test_updating_doc_and_command_are_wired():
    doc = (ROOT / "System" / "Updating.md").read_text(encoding="utf-8")
    for needle in ("Adopt by default", "Never destroy", "template-diff.py", "In an existing vault", "one commit",
                   "do not stop to ask", "from that clone"):
        assert needle.lower() in doc.lower(), needle
    for folder in (".claude/commands", "cowork-commands"):
        text = (ROOT / folder / "update.md").read_text(encoding="utf-8")
        assert "System/Updating.md" in text and "from that clone" in text.lower()
    assert "/update" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_case_only_rename_is_never_retired(tmp_path):
    tpl = tmp_path / "tpl"
    tpl.mkdir()
    git(tpl, "init", "-q", "-b", "main")
    git(tpl, "config", "user.email", "t@example.com"); git(tpl, "config", "user.name", "t")
    write(tpl, {"templates/Note.md": "n\n"})
    git(tpl, "add", "-A"); git(tpl, "commit", "-q", "-m", "v1")
    git(tpl, "mv", "templates/Note.md", "Templates/Note.md"); git(tpl, "commit", "-q", "-m", "v2")
    vault = tmp_path / "vault"
    write(vault, {"Templates/Note.md": "n\n"})
    got = run(tpl, vault)
    assert got["retire"] == [] and got["retire-changed"] == []
    # a vault that still has only the old spelling: on a case-sensitive filesystem the old path retires and the
    # new one is added; where the filesystem folds case the two are one file and nothing retires
    vault2 = tmp_path / "vault2"
    write(vault2, {"templates/Note.md": "n\n"})
    got = run(tpl, vault2)
    if (vault2 / "Templates" / "Note.md").is_file():
        assert got["retire"] == [] and got["add"] == []
    else:
        assert got["retire"] == ["templates/Note.md"] and got["add"] == ["Templates/Note.md"]
