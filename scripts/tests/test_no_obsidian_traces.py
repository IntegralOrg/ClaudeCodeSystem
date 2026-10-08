import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
SKIP_DIRS = {".git", "node_modules", ".pytest_cache", "__pycache__", ".venv"}
WORD = "obsi" + "dian"            # built from pieces so this file is not its own first hit
PATTERN = re.compile(WORD, re.IGNORECASE)
EXTS = {".md", ".py", ".sh", ".json", ".yml", ".yaml", ".html", ".txt", ".example", ".toml", ".cfg"}
NAMES = {".gitignore", ".gitattributes", "LICENSE", ".gitkeep"}


def _entry_date(changelog, lineno):
    date = "9999-99-99"
    for i, line in enumerate(changelog.read_text(encoding="utf-8").splitlines(), 1):
        m = re.match(r"## \[(\d{4}-\d{2}-\d{2})\]", line)
        if m:
            date = m.group(1)
        if i == lineno:
            return date
    return date


def test_no_obsidian_anywhere():
    hits = []
    for p in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts) or not p.is_file() or (p.suffix not in EXTS and p.name not in NAMES) or p.resolve() == SELF:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if PATTERN.search(line):
                if p.name == "CHANGELOG.md" and _entry_date(p, i) < "2026-10-08":
                    continue
                hits.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()[:80]}")
    assert not hits, "\n".join(hits)
