import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNED = ["*.md", "*.py", "*.sh", "*.yml", "*.json", "*.example"]
RETIRED = ["onboard", "train", "connect", "finish", "morning-precheck", "monthly-review"]


def test_retired_commands_are_gone_from_both_folders():
    for name in RETIRED:
        assert not (ROOT / ".claude" / "commands" / f"{name}.md").exists(), name
        assert not (ROOT / "cowork-commands" / f"{name}.md").exists(), name


def test_monthly_review_is_gone_everywhere_but_history():
    assert not (ROOT / "System" / "routines" / "monthly-review.md").exists()
    files = [ROOT / "CLAUDE.md", ROOT / "README.md"] + [p for p in (ROOT / "System").rglob("*") if p.is_file()]
    hits = [str(p.relative_to(ROOT)) for p in files
            if re.search(r"monthly[ -]review|/monthly-review", p.read_text(encoding="utf-8", errors="replace"), re.I)]
    assert not hits, hits


def test_every_code_command_has_a_cowork_mirror():
    code = {p.name for p in (ROOT / ".claude" / "commands").glob("*.md")} - {"rabbit.md"}
    cowork = {p.name for p in (ROOT / "cowork-commands").glob("*.md")}
    assert code <= cowork, sorted(code - cowork)


def test_no_doc_tells_the_user_to_type_a_retired_command():
    pat = re.compile(r"(?<![\w/])/(onboard|train|connect|finish|morning-precheck|monthly-review)\b")
    hits = []
    for p in (q for ext in SCANNED for q in ROOT.rglob(ext)):
        if (".git" in p.parts or "node_modules" in p.parts or p.name == "CHANGELOG.md" or "superpowers" in p.parts
                or p.resolve() == Path(__file__).resolve() or not p.is_file()):
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if pat.search(line):
                hits.append(f"{p.relative_to(ROOT)}:{i}")
    assert not hits, hits
