import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RETIRED = ["onboard", "train", "connect", "finish", "morning-precheck"]


def test_retired_commands_are_gone_from_both_folders():
    for name in RETIRED:
        assert not (ROOT / ".claude" / "commands" / f"{name}.md").exists(), name
        assert not (ROOT / "cowork-commands" / f"{name}.md").exists(), name


def test_every_code_command_has_a_cowork_mirror():
    code = {p.name for p in (ROOT / ".claude" / "commands").glob("*.md")} - {"rabbit.md"}
    cowork = {p.name for p in (ROOT / "cowork-commands").glob("*.md")}
    assert code <= cowork, sorted(code - cowork)


def test_no_doc_tells_the_user_to_type_a_retired_command():
    pat = re.compile(r"(?<![\w/])/(onboard|train|connect|finish|morning-precheck)\b")
    hits = []
    for p in ROOT.rglob("*.md"):
        if ".git" in p.parts or "node_modules" in p.parts or p.name == "CHANGELOG.md" or "superpowers" in p.parts:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if pat.search(line):
                hits.append(f"{p.relative_to(ROOT)}:{i}")
    assert not hits, hits
