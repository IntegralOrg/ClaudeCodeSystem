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


def test_end_of_day_declares_no_keys_and_setup_writes_its_connectors():
    eod = (ROOT / "System" / "routines" / "eod.md").read_text(encoding="utf-8")
    assert "optional_keys: []" in eod and "FATHOM_API_KEY" not in eod and "SLACK_TOKEN" not in eod
    setup = (ROOT / "System" / "Setup Procedure.md").read_text(encoding="utf-8")
    build = setup[setup.index("## 2. Build the vault"):setup.index("## 3. Connect your tools")]
    assert "`[Gmail, Google Calendar]` for Google" in build and "`[Microsoft 365]` for Microsoft" in build
    ct = (ROOT / "System" / "Connecting Tools.md").read_text(encoding="utf-8")
    row = [line for line in ct.splitlines() if line.startswith("| Outlook and Teams")][0]
    assert "not available on Microsoft today, so Routine health in the daily note is where it tells you" in row
    assert "falls back to the calendar event path" not in ct
    routines = (ROOT / "System" / "Routines.md").read_text(encoding="utf-8")
    assert "RIZE_API_KEY" in routines and "probe_url:" in routines


def test_first_local_session_opens_a_pop_up_only_for_a_ledger_key():
    text = (ROOT / "System" / "Adding Your Computer.md").read_text(encoding="utf-8")
    step = [line for line in text.splitlines() if line.startswith("2. ") and "check-keys.py --where" in line][0]
    assert "System/Tools.md" in step and "key <NAME>" in step and "(optional)" in step


def test_eod_never_sends_email_and_pushes_a_calendar_event():
    for rel in (".claude/commands/eod.md", "cowork-commands/eod.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "send tool" not in text, rel
        assert "Email route" not in text, rel
        assert "Brain needs you: <reason>" in text, rel
        assert "all-day event" in text, rel
        assert "never sends an email" in text, rel
