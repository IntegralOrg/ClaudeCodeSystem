"""This repository is PUBLIC. Internal names never appear in it, and the two Integral people who
help clients appear only in the two System docs that introduce them."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
SKIP_DIRS = {".git", "node_modules", ".pytest_cache", "__pycache__", ".venv"}
EXTS = {".md", ".py", ".sh", ".json", ".yml", ".yaml", ".html", ".txt", ".example", ".toml", ".cfg", ".css", ".js", ".ps1", ".csv"}
NAMES = {".gitignore", ".gitattributes", "LICENSE", ".gitkeep"}
# Built from pieces so this file is not its own first hit.
FORBIDDEN = re.compile("|".join(["ste" + "phen", "go" + "integral", "integral" + "/sops", "brain" + "-private"]), re.IGNORECASE)
PEOPLE = re.compile(r"\b(" + "|".join(["de" + "an", "e" + "va"]) + r")\b", re.IGNORECASE)
PEOPLE_ALLOWED = {"System/Getting Help.md", "System/Setup Procedure.md"}
# LICENSE carries the public company attribution URL on purpose; test_system_docs.py asserts the names are absent.
EXEMPT = {"LICENSE", "scripts/tests/test_system_docs.py"}


def text_files():
    for p in sorted(ROOT.rglob("*")):
        if any(part in SKIP_DIRS for part in p.parts) or not p.is_file() or p.resolve() == SELF:
            continue
        if p.relative_to(ROOT).as_posix() in EXEMPT:
            continue
        if p.suffix in EXTS or p.name in NAMES:
            yield p


def test_no_internal_names_anywhere():
    hits = []
    for p in text_files():
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if FORBIDDEN.search(line):
                hits.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()[:80]}")
    assert not hits, "\n".join(hits)


def test_support_people_named_only_in_the_two_system_docs():
    hits = []
    for p in text_files():
        rel = p.relative_to(ROOT).as_posix()
        if rel in PEOPLE_ALLOWED:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if PEOPLE.search(line):
                hits.append(f"{rel}:{i}: {line.strip()[:80]}")
    assert not hits, "\n".join(hits)
