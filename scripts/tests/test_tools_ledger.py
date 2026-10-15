import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("tools_ledger", Path(__file__).resolve().parents[1] / "tools_ledger.py")
tl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tl)

SAMPLE = """# Tools

One section per tool the owner named at setup or later. The first bullet under each heading is the status and is the only line the hooks read.

## Gmail
- status: not connected
- essential: yes
- how: connector "Gmail" (registry id 2701e52f-b826-4aaf-8b25-11f2a97c98b0)
- used by: End of Day (reads the day's mail)
- updated: 2026-10-14

## Fathom
- status: connected 2026-10-14
- essential: yes
- how: connector "Fathom"
- used by: End of Day (call transcripts)
- updated: 2026-10-14

## Slack
- status: skipped (later)
- essential: no
- how: connector "Slack"
- used by: End of Day (messages)
- updated: 2026-10-14
"""


def test_parse_reads_one_section_per_tool_with_the_first_status_bullet():
    entries = tl.parse(SAMPLE)
    assert [e["name"] for e in entries] == ["Gmail", "Fathom", "Slack"]
    assert entries[0]["status"] == "not connected" and entries[0]["essential"] is True
    assert entries[1]["status"] == "connected 2026-10-14"
    assert entries[2]["status"] == "skipped (later)" and entries[2]["essential"] is False
    assert entries[0]["how"].startswith('connector "Gmail"')


def test_parse_takes_only_the_first_status_bullet():
    text = SAMPLE.replace("- status: not connected\n", "- status: not connected\n- status: connected 2026-10-15\n", 1)
    assert tl.parse(text)[0]["status"] == "not connected"


def test_open_items_splits_essential_from_the_rest():
    text = SAMPLE.replace("- status: skipped (later)", "- status: not connected")
    ess, other = tl.open_items(tl.parse(text))
    assert ess == ["Gmail"] and other == ["Slack"]


def test_load_returns_empty_when_absent(tmp_path):
    assert tl.load(tmp_path) == []


def test_set_status_rewrites_in_place_and_bumps_updated(tmp_path):
    (tmp_path / "System").mkdir()
    (tmp_path / "System" / "Tools.md").write_text(SAMPLE, encoding="utf-8")
    assert tl.set_status(tmp_path, "Gmail", "connected 2026-10-15", "2026-10-15") is True
    text = (tmp_path / "System" / "Tools.md").read_text(encoding="utf-8")
    assert text.count("- status:") == 3
    gmail = text[text.index("## Gmail"):text.index("## Fathom")]
    assert "- status: connected 2026-10-15" in gmail and "- updated: 2026-10-15" in gmail
    assert tl.set_status(tmp_path, "Notion", "connected 2026-10-15", "2026-10-15") is False


def test_render_round_trips():
    entries = tl.parse(SAMPLE)
    assert tl.parse(tl.render(entries)) == entries
