from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_index_html_buttons_prereqs_and_no_em_dash():
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    assert "github.com/new?template_owner=IntegralOrg&template_name=ClaudeCodeSystem&name=brain&visibility=private" in html
    assert "claude.ai/code" in html
    for needle in ("Max plan", "GitHub account", "Claude Desktop", "GitHub Desktop", "Python 3", "Accessibility"):
        assert needle in html, needle
    assert "—" not in html and "<title>" in html and "prefers-color-scheme" in html


def test_readme_get_started_is_three_steps():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    block = text.split("## Get Started")[1].split("## ")[0]
    assert "1." in block and "2." in block and "3." in block and "4." not in block
    assert "Use this template" in block and "claude.ai/code" in block and "Max" in block
