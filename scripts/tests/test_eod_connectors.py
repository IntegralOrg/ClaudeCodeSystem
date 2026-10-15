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


def _gather_section(text, start, end):
    return text[text.index(start):text.index(end)]


def test_eod_gather_sections_2_to_4_read_through_connectors():
    for f in (ROOT / ".claude" / "commands" / "eod-gather.md", ROOT / "cowork-commands" / "eod-gather.md"):
        text = f.read_text(encoding="utf-8")
        for start, end, connectors in (
                ("## Section 2", "## Section 3", ("Google Calendar", "Microsoft 365")),
                ("## Section 3", "## Section 4", ("Gmail", "Microsoft 365")),
                ("## Section 4", "## Section 5", ("Slack connector",))):
            sec = _gather_section(text, start, end)
            assert "System/Tools.md" in sec, (f.name, start)
            for c in connectors:
                assert c in sec, (f.name, start, c)


def test_eod_gather_names_raw_tokens_only_beside_the_appendix():
    for f in (".claude/commands/eod-gather.md", "cowork-commands/eod-gather.md", ".claude/commands/eod.md",
              "cowork-commands/eod.md"):
        text = (ROOT / f).read_text(encoding="utf-8")
        for sentence in text.replace("\n", " ").split(". "):
            if "GOOGLE_REFRESH_TOKEN" in sentence or "SLACK_TOKEN" in sentence:
                assert "Appendix" in sentence, (f, sentence)
        assert "googleapis.com" not in text and "conversations.history" not in text, f


def test_daily_note_step_keeps_the_setup_completed_line():
    for f in (".claude/commands/eod.md", "cowork-commands/eod.md", ".claude/commands/eod-note.md",
              "cowork-commands/eod-note.md"):
        text = (ROOT / f).read_text(encoding="utf-8")
        assert "Create the daily note" not in text and "ask before overwriting" not in text, f
        assert "keep every existing line" in text and "Setup completed" in text and "never overwrite" in text, f
