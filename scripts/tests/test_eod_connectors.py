# scripts/tests/test_eod_connectors.py
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {".git", "node_modules", ".superpowers", "worktrees", "__pycache__", ".pytest_cache"}
# Built by concatenation so this file does not match its own search.
MISSING_SCRIPT = "fathom" + "-fetch"


def test_no_file_references_the_missing_fathom_fetch_script():
    hits = []
    for p in ROOT.rglob("*"):
        if SKIP_DIRS & set(p.relative_to(ROOT).parts):
            continue
        if p.is_file() and p.suffix in (".md", ".py", ".sh", ".json") and p.name != "CHANGELOG.md":
            if MISSING_SCRIPT in p.read_text(encoding="utf-8", errors="replace"):
                hits.append(str(p.relative_to(ROOT)))
    assert hits == [], hits


def test_eod_gather_reads_transcripts_through_the_connected_notetaker():
    text = (ROOT / ".claude" / "commands" / "eod-gather.md").read_text(encoding="utf-8")
    sec = text[text.index("## Section 1"):text.index("## Section 2")]
    for needle in ("System/Tools.md", "list_meetings", "get_meeting_transcript", "get_meeting_summary", "Fireflies",
                   "Granola", "tldv", "Grain", "Zoom", "no notetaker connected"):
        assert needle in sec, needle
    assert (ROOT / "cowork-commands" / "eod-gather.md").read_text(encoding="utf-8").count("list_meetings") >= 1
