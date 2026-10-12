import re
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
DOWNLOAD = "https://github.com/IntegralOrg/ClaudeCodeSystem/archive/refs/heads/main.zip"
RAW_START = "https://raw.githubusercontent.com/IntegralOrg/ClaudeCodeSystem/main/System/Start.md"


def start_line_from_readme():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    block = text.split("## Get Started")[1].split("## ")[0]
    lines = [l[2:].strip() for l in block.splitlines() if l.startswith("> Set up my Brain.")]
    assert len(lines) == 1, lines
    return lines[0]


def test_index_html_has_one_start_button_that_opens_claude_in_the_home_folder():
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    hrefs = re.findall(r'href="(claude://code/new\?[^"]+)"', html)
    assert len(hrefs) == 2, hrefs                       # top and bottom buttons, same link
    assert len(set(hrefs)) == 1
    url = urlparse(unescape(hrefs[0]))
    qs = parse_qs(url.query)
    assert qs["folder"] == ["~"]
    assert qs["q"] == [start_line_from_readme()]       # the button and the README carry the same line
    assert RAW_START in qs["q"][0] and DOWNLOAD in qs["q"][0] and "Brain/System/Start.md" in qs["q"][0]
    assert len(qs["q"][0]) < 1000
    assert html.count("Start in Claude") >= 3           # two buttons and the step that names it


def test_index_html_keeps_the_hand_path_and_the_cloud_path():
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    assert "claude.com/download" in html and DOWNLOAD in html
    assert html.index("claude://code/new") < html.index(DOWNLOAD) < html.index("github.com/new?template_owner=IntegralOrg")
    for needle in ("Open Claude", "Trust", "Enter", "copy the line", "Extract All", "ClaudeCodeSystem-main", "inside it",
                   "Mac", "Windows", "No computer", "Claude Code"):
        assert needle in html, needle
    assert "send any message" in html                   # the hand and cloud paths still say it
    assert "—" not in html and "<title>" in html and "prefers-color-scheme" in html


def test_readme_get_started_is_three_steps_with_the_line_and_both_fallbacks():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    block = text.split("## Get Started")[1].split("## ")[0]
    assert "1." in block and "2." in block and "3." in block and "4." not in block
    missing = [n for n in ("Max", "Trust", "Enter", "copy the line", DOWNLOAD, "ClaudeCodeSystem-main", "inside it",
                           "Use this template", "claude.ai/code", "send any message", "Start in Claude") if n not in block]
    assert not missing, missing
    assert RAW_START in start_line_from_readme()
    assert "integralorg.github.io" not in text
